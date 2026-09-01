"""Named network areas with automatic map navigation bounds."""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models.map_feature import MapFeature
from app.models.network import ServiceNetwork
from app.schemas.network import NetworkAssign, NetworkCreate, NetworkUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/networks", tags=["networks"])


def _get_network(db: DbSession, network_id: uuid.UUID) -> ServiceNetwork:
    network = db.get(ServiceNetwork, network_id)
    if network is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    return network


def _network_snapshot(network: ServiceNetwork) -> dict[str, Any]:
    return {
        "id": str(network.id),
        "name": network.name,
        "city": network.city,
        "state": network.state,
        "country": network.country,
        "viewport": network.viewport,
        "properties": network.properties,
        "revision": network.revision,
    }


def _network_response(network: ServiceNetwork, feature_count: int) -> dict[str, Any]:
    return {
        **_network_snapshot(network),
        "feature_count": feature_count,
        "created_at": network.created_at,
        "updated_at": network.updated_at,
    }


def _namespace_extent(db: DbSession, source_namespace: str) -> tuple[list[float] | None, int]:
    extent = func.ST_Extent(MapFeature.geometry)
    row = db.execute(
        select(
            func.ST_XMin(extent),
            func.ST_YMin(extent),
            func.ST_XMax(extent),
            func.ST_YMax(extent),
            func.count(MapFeature.id),
        ).where(MapFeature.source_namespace == source_namespace)
    ).one()
    if not row[4]:
        return None, 0
    return [float(row[0]), float(row[1]), float(row[2]), float(row[3])], int(row[4])


def _assign_namespace(
    db: DbSession,
    *,
    network: ServiceNetwork,
    source_namespace: str,
    actor_id: uuid.UUID,
) -> int:
    extent, count = _namespace_extent(db, source_namespace)
    if extent is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="source namespace has no map features",
        )
    result = db.execute(
        update(MapFeature)
        .where(MapFeature.source_namespace == source_namespace)
        .values(
            network_id=network.id,
            revision=MapFeature.revision + 1,
            updated_by=actor_id,
        )
    )
    network.viewport = extent
    record_audit(
        db,
        actor_user_id=actor_id,
        action="network.assign_namespace",
        entity_type="service_network",
        entity_id=str(network.id),
        after_data={"source_namespace": source_namespace, "feature_count": count},
    )
    return int(result.rowcount or 0)


@router.get("")
def list_networks(_: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    networks = list(db.scalars(select(ServiceNetwork).order_by(ServiceNetwork.name)))
    counts = {
        network_id: count
        for network_id, count in db.execute(
            select(MapFeature.network_id, func.count(MapFeature.id))
            .where(MapFeature.network_id.is_not(None))
            .group_by(MapFeature.network_id)
        )
    }
    return [_network_response(network, counts.get(network.id, 0)) for network in networks]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_network(payload: NetworkCreate, actor: AdminUser, db: DbSession) -> dict[str, Any]:
    duplicate = db.scalar(
        select(ServiceNetwork.id).where(func.lower(ServiceNetwork.name) == payload.name.lower())
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="network name already exists"
        )

    viewport = payload.viewport
    source_count = 0
    if payload.source_namespace is not None:
        viewport, source_count = _namespace_extent(db, payload.source_namespace)
        if viewport is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="source namespace has no map features",
            )
    if viewport is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="viewport or source namespace is required",
        )

    network = ServiceNetwork(
        name=payload.name.strip(),
        city=payload.city.strip(),
        state=payload.state.strip(),
        country=payload.country.strip(),
        viewport=viewport,
        properties=payload.properties,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(network)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="network name already exists"
        ) from exc

    assigned = 0
    if payload.source_namespace is not None:
        assigned = _assign_namespace(
            db,
            network=network,
            source_namespace=payload.source_namespace,
            actor_id=actor.id,
        )
    record_audit(
        db,
        actor_user_id=actor.id,
        action="network.create",
        entity_type="service_network",
        entity_id=str(network.id),
        after_data=_network_snapshot(network),
    )
    return _network_response(network, assigned or source_count)


@router.patch("/{network_id}")
def update_network(
    network_id: uuid.UUID,
    payload: NetworkUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    network = _get_network(db, network_id)
    if network.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale network revision")
    before = _network_snapshot(network)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        setattr(network, key, value)
    network.revision += 1
    network.updated_by = actor.id
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="network name already exists"
        ) from exc
    record_audit(
        db,
        actor_user_id=actor.id,
        action="network.update",
        entity_type="service_network",
        entity_id=str(network.id),
        before_data=before,
        after_data=_network_snapshot(network),
    )
    count = db.scalar(select(func.count(MapFeature.id)).where(MapFeature.network_id == network.id))
    return _network_response(network, count or 0)


@router.post("/{network_id}/assign")
def assign_network_namespace(
    network_id: uuid.UUID,
    payload: NetworkAssign,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    network = _get_network(db, network_id)
    _assign_namespace(
        db,
        network=network,
        source_namespace=payload.source_namespace,
        actor_id=actor.id,
    )
    network.revision += 1
    network.updated_by = actor.id
    count = db.scalar(select(func.count(MapFeature.id)).where(MapFeature.network_id == network.id))
    return _network_response(network, count or 0)
