"""Read-for-all, write-for-admin PostGIS map endpoints."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.core.config import get_settings
from app.models.map_feature import MapFeature
from app.models.map_import import MapImport
from app.models.network import ServiceNetwork
from app.schemas.map_feature import MapFeatureCreate, MapFeatureUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/map-features", tags=["map"])


def _properties(feature: MapFeature) -> dict[str, Any]:
    return {
        **feature.properties,
        "fiberq_uuid": str(feature.fiberq_uuid) if feature.fiberq_uuid else None,
        "network_id": str(feature.network_id) if feature.network_id else None,
        "feature_type": feature.feature_type,
        "name": feature.name,
        "status": feature.status,
        "revision": feature.revision,
    }


def _snapshot(feature: MapFeature) -> dict[str, Any]:
    return {
        "id": str(feature.id),
        "fiberq_uuid": str(feature.fiberq_uuid) if feature.fiberq_uuid else None,
        "network_id": str(feature.network_id) if feature.network_id else None,
        "feature_type": feature.feature_type,
        "name": feature.name,
        "status": feature.status,
        "properties": feature.properties,
        "revision": feature.revision,
    }


def _geojson_feature(
    db: DbSession, feature: MapFeature, geometry_json: str | None = None
) -> dict[str, Any]:
    if geometry_json is None:
        geometry_json = db.scalar(select(func.ST_AsGeoJSON(feature.geometry)))
    return {
        "type": "Feature",
        "id": str(feature.id),
        "geometry": json.loads(geometry_json),
        "properties": _properties(feature),
    }


@router.get("")
def list_map_features(
    _: CurrentUser,
    db: DbSession,
    limit: int = Query(default=5000, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    network_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    query = select(MapFeature, func.ST_AsGeoJSON(MapFeature.geometry)).order_by(
        MapFeature.created_at
    )
    if network_id is not None:
        query = query.where(MapFeature.network_id == network_id)
    rows = list(db.execute(query.limit(limit).offset(offset)))
    latest_import = db.scalar(select(MapImport).order_by(MapImport.created_at.desc()).limit(1))
    base_map = (
        "Google Maps — cartografia carregada sob demanda"
        if get_settings().map_provider == "google"
        else "OpenStreetMap — mosaicos carregados sob demanda"
    )
    return {
        "type": "FeatureCollection",
        "features": [
            _geojson_feature(db, feature, geometry_json) for feature, geometry_json in rows
        ],
        "data_status": {
            "latest_feature_update_at": db.scalar(select(func.max(MapFeature.updated_at))),
            "latest_import_at": latest_import.created_at if latest_import else None,
            "latest_import_filename": latest_import.filename if latest_import else None,
            "base_map": base_map,
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_map_feature(
    payload: MapFeatureCreate, actor: AdminUser, db: DbSession
) -> dict[str, Any]:
    if payload.network_id is not None and db.get(ServiceNetwork, payload.network_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    feature = MapFeature(
        fiberq_uuid=payload.fiberq_uuid,
        network_id=payload.network_id,
        feature_type=payload.feature_type,
        name=payload.name,
        status=payload.status,
        geometry=func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(payload.geometry)), 4326),
        properties=payload.properties,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(feature)
    try:
        db.flush()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid geometry or duplicate FiberQ UUID",
        ) from exc
    record_audit(
        db,
        actor_user_id=actor.id,
        action="map_feature.create",
        entity_type="map_feature",
        entity_id=str(feature.id),
        after_data=_snapshot(feature),
    )
    return _geojson_feature(db, feature)


@router.patch("/{feature_id}")
def update_map_feature(
    feature_id: uuid.UUID,
    payload: MapFeatureUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    feature = db.get(MapFeature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature not found")
    if feature.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale feature revision")

    before = _snapshot(feature)
    if (
        "network_id" in payload.model_fields_set
        and payload.network_id is not None
        and db.get(ServiceNetwork, payload.network_id) is None
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision", "geometry"})
    for key, value in changes.items():
        setattr(feature, key, value)
    if "feature_type" in payload.model_fields_set and payload.feature_type is not None:
        feature.properties = {
            **feature.properties,
            "feature_type_override": payload.feature_type,
        }
    if payload.geometry is not None:
        feature.geometry = func.ST_SetSRID(
            func.ST_GeomFromGeoJSON(json.dumps(payload.geometry)), 4326
        )
    feature.revision += 1
    feature.updated_by = actor.id
    try:
        db.flush()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid update"
        ) from exc
    record_audit(
        db,
        actor_user_id=actor.id,
        action="map_feature.update",
        entity_type="map_feature",
        entity_id=str(feature.id),
        before_data=before,
        after_data=_snapshot(feature),
    )
    return _geojson_feature(db, feature)


@router.delete("/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map_feature(
    feature_id: uuid.UUID,
    actor: AdminUser,
    db: DbSession,
) -> Response:
    feature = db.get(MapFeature, feature_id)
    if feature is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feature not found")
    before = _snapshot(feature)
    record_audit(
        db,
        actor_user_id=actor.id,
        action="map_feature.delete",
        entity_type="map_feature",
        entity_id=str(feature.id),
        before_data=before,
    )
    db.delete(feature)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
