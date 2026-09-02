"""Administrator-only preview and idempotent KMZ import endpoints."""

import json
import re
import uuid
from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text

from app.api.dependencies import AdminUser, DbSession
from app.models.map_feature import MapFeature
from app.models.map_import import MapImport
from app.models.network import ServiceNetwork
from app.services.audit import record_audit
from app.services.kmz_export import build_kmz
from app.services.kmz_import import MAX_UPLOAD_BYTES, KmzValidationError, ParsedKmz, parse_kmz

router = APIRouter(prefix="/imports", tags=["imports"])

KmzFile = Annotated[UploadFile, File()]
SourceNamespace = Annotated[str, Form(min_length=1, max_length=120)]
DefaultStatus = Annotated[str, Form()]


async def _parse_upload(file: UploadFile, source_namespace: str, default_status: str) -> ParsedKmz:
    filename = file.filename or "network.kmz"
    if not filename.lower().endswith(".kmz"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="only .kmz files are supported",
        )
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        return parse_kmz(
            content,
            filename=filename,
            source_namespace=source_namespace,
            default_status=default_status,
        )
    except KmzValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


def _existing_refs(db: DbSession, namespace: str) -> set[str]:
    return set(
        db.scalars(
            select(MapFeature.source_ref).where(
                MapFeature.source_namespace == namespace,
                MapFeature.source_ref.is_not(None),
            )
        )
    )


def _import_response(item: MapImport, *, already_imported: bool = False) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "network_id": str(item.network_id) if item.network_id else None,
        "filename": item.filename,
        "source_namespace": item.source_namespace,
        "file_sha256": item.file_sha256,
        "status": item.status,
        "feature_count": item.feature_count,
        "created_count": item.created_count,
        "updated_count": item.updated_count,
        "skipped_count": item.skipped_count,
        "warnings": item.warnings,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
        "already_imported": already_imported,
    }


@router.post("/kmz/preview")
async def preview_kmz(
    file: KmzFile,
    source_namespace: SourceNamespace,
    default_status: DefaultStatus,
    _: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    parsed = await _parse_upload(file, source_namespace, default_status)
    result = parsed.preview(_existing_refs(db, parsed.source_namespace))
    result["already_imported"] = (
        db.scalar(
            select(MapImport.id).where(
                MapImport.source_namespace == parsed.source_namespace,
                MapImport.file_sha256 == parsed.file_sha256,
            )
        )
        is not None
    )
    return result


@router.post("/kmz", status_code=status.HTTP_201_CREATED)
async def import_kmz(
    file: KmzFile,
    source_namespace: SourceNamespace,
    default_status: DefaultStatus,
    actor: AdminUser,
    db: DbSession,
    network_id: Annotated[uuid.UUID | None, Form()] = None,
) -> dict[str, Any]:
    parsed = await _parse_upload(file, source_namespace, default_status)
    if network_id is not None and db.get(ServiceNetwork, network_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:namespace, 0))"),
        {"namespace": f"map-import:{parsed.source_namespace}"},
    )
    previous = db.scalar(
        select(MapImport).where(
            MapImport.source_namespace == parsed.source_namespace,
            MapImport.file_sha256 == parsed.file_sha256,
        )
    )
    if previous is not None:
        return _import_response(previous, already_imported=True)

    existing = {
        feature.source_ref: feature
        for feature in db.scalars(
            select(MapFeature).where(MapFeature.source_namespace == parsed.source_namespace)
        )
        if feature.source_ref is not None
    }
    batch = MapImport(
        network_id=network_id,
        filename=parsed.filename,
        source_namespace=parsed.source_namespace,
        file_sha256=parsed.file_sha256,
        source_format="kmz",
        status="completed",
        feature_count=len(parsed.features),
        created_count=0,
        updated_count=0,
        skipped_count=0,
        warnings=parsed.warnings,
        created_by=actor.id,
    )
    db.add(batch)
    db.flush()

    for incoming in parsed.features:
        feature = existing.get(incoming.source_ref)
        properties = {
            **(feature.properties if feature is not None else {}),
            **incoming.properties,
            "source_namespace": parsed.source_namespace,
            "import_id": str(batch.id),
        }
        geometry = _geometry_expression(incoming.geometry)
        if feature is None:
            feature = MapFeature(
                import_id=batch.id,
                network_id=network_id,
                source_namespace=parsed.source_namespace,
                source_ref=incoming.source_ref,
                feature_type=incoming.feature_type,
                name=incoming.name,
                status=incoming.status,
                geometry=geometry,
                properties=properties,
                created_by=actor.id,
                updated_by=actor.id,
            )
            db.add(feature)
            batch.created_count += 1
        else:
            feature.import_id = batch.id
            if network_id is not None:
                feature.network_id = network_id
            feature.feature_type = properties.get("feature_type_override", incoming.feature_type)
            feature.name = incoming.name
            feature.status = incoming.status
            feature.geometry = geometry
            feature.properties = properties
            feature.revision += 1
            feature.updated_by = actor.id
            batch.updated_count += 1

    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="map_import.kmz",
        entity_type="map_import",
        entity_id=str(batch.id),
        after_data={
            "filename": batch.filename,
            "source_namespace": batch.source_namespace,
            "feature_count": batch.feature_count,
            "created_count": batch.created_count,
            "updated_count": batch.updated_count,
            "file_sha256": batch.file_sha256,
        },
    )
    return _import_response(batch)


@router.get("")
def list_imports(_: AdminUser, db: DbSession) -> list[dict[str, Any]]:
    items = db.scalars(select(MapImport).order_by(MapImport.created_at.desc()).limit(50))
    return [_import_response(item) for item in items]


@router.get("/kmz/export")
def export_kmz(
    _: AdminUser,
    db: DbSession,
    network_id: uuid.UUID | None = None,
) -> StreamingResponse:
    network = db.get(ServiceNetwork, network_id) if network_id else None
    if network_id and network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    query = select(MapFeature, func.ST_AsGeoJSON(MapFeature.geometry)).order_by(
        MapFeature.created_at, MapFeature.id
    )
    if network_id:
        query = query.where(MapFeature.network_id == network_id)
    features = [
        {
            "id": str(feature.id),
            "geometry": json.loads(geometry_json),
            "properties": {
                **feature.properties,
                "feature_type": feature.feature_type,
                "name": feature.name,
                "status": feature.status,
            },
        }
        for feature, geometry_json in db.execute(query)
    ]
    if not features:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no map features available for export",
        )
    document_name = network.name if network else "Gestor Hub Fiber"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", document_name).strip("-").lower()
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
    filename = f"{safe_name or 'gestor-hub-fiber'}-{timestamp}.kmz"
    content = build_kmz(features, document_name)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.google-earth.kmz",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Feature-Count": str(len(features)),
        },
    )


def _geometry_expression(geometry: dict[str, Any]):
    from sqlalchemy import func

    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), 4326)
