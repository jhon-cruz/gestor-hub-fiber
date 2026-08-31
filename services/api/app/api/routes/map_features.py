"""Read-for-all, write-for-admin PostGIS map endpoints."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models.map_feature import MapFeature
from app.schemas.map_feature import MapFeatureCreate, MapFeatureUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/map-features", tags=["map"])


def _properties(feature: MapFeature) -> dict[str, Any]:
    return {
        **feature.properties,
        "fiberq_uuid": str(feature.fiberq_uuid) if feature.fiberq_uuid else None,
        "feature_type": feature.feature_type,
        "name": feature.name,
        "status": feature.status,
        "revision": feature.revision,
    }


def _snapshot(feature: MapFeature) -> dict[str, Any]:
    return {
        "id": str(feature.id),
        "fiberq_uuid": str(feature.fiberq_uuid) if feature.fiberq_uuid else None,
        "feature_type": feature.feature_type,
        "name": feature.name,
        "status": feature.status,
        "properties": feature.properties,
        "revision": feature.revision,
    }


def _geojson_feature(db: DbSession, feature: MapFeature) -> dict[str, Any]:
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
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    features = list(
        db.scalars(select(MapFeature).order_by(MapFeature.created_at).limit(limit).offset(offset))
    )
    return {
        "type": "FeatureCollection",
        "features": [_geojson_feature(db, feature) for feature in features],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_map_feature(
    payload: MapFeatureCreate, actor: AdminUser, db: DbSession
) -> dict[str, Any]:
    feature = MapFeature(
        fiberq_uuid=payload.fiberq_uuid,
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
    changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision", "geometry"})
    for key, value in changes.items():
        setattr(feature, key, value)
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
