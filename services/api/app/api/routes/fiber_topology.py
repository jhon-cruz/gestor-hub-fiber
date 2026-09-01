"""Cable inventory, individual fibers and integrity-safe splice connections."""

import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select, tuple_
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models.fiber_topology import (
    CableTube,
    FiberConnection,
    FiberConnectionEndpoint,
    FiberPortLink,
    OpticalCable,
    OpticalFiber,
)
from app.models.map_feature import MapFeature
from app.models.network import ServiceNetwork
from app.schemas.fiber_topology import (
    FiberConnectionCreate,
    OpticalCableCreate,
    OpticalCableUpdate,
    OpticalFiberUpdate,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/optical-cables", tags=["fiber-topology"])
fibers_router = APIRouter(prefix="/optical-fibers", tags=["fiber-topology"])
connections_router = APIRouter(prefix="/fiber-connections", tags=["fiber-topology"])

COLOR_SEQUENCE = [
    "green",
    "yellow",
    "white",
    "blue",
    "red",
    "violet",
    "brown",
    "pink",
    "black",
    "gray",
    "orange",
    "aqua",
]
ENCLOSURE_TYPES = {"splice_box", "cto", "dio", "splitter"}


def _color(position: int) -> str:
    base = COLOR_SEQUENCE[(position - 1) % len(COLOR_SEQUENCE)]
    cycle = (position - 1) // len(COLOR_SEQUENCE) + 1
    return base if cycle == 1 else f"{base}-{cycle}"


def _get_cable(db: DbSession, cable_id: uuid.UUID) -> OpticalCable:
    cable = db.get(OpticalCable, cable_id)
    if cable is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="optical cable not found")
    return cable


def _cable_snapshot(cable: OpticalCable) -> dict[str, Any]:
    return {
        "id": str(cable.id),
        "network_id": str(cable.network_id) if cable.network_id else None,
        "map_feature_id": str(cable.map_feature_id) if cable.map_feature_id else None,
        "name": cable.name,
        "cable_class": cable.cable_class,
        "status": cable.status,
        "fiber_count": cable.fiber_count,
        "tube_count": cable.tube_count,
        "fibers_per_tube": cable.fibers_per_tube,
        "measured_length_m": cable.measured_length_m,
        "technical_reserve_m": cable.technical_reserve_m,
        "properties": cable.properties,
        "revision": cable.revision,
    }


def _fiber_summary(db: DbSession, cable_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    summaries: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    if not cable_ids:
        return summaries
    rows = db.execute(
        select(OpticalFiber.cable_id, OpticalFiber.status, func.count(OpticalFiber.id))
        .where(OpticalFiber.cable_id.in_(cable_ids))
        .group_by(OpticalFiber.cable_id, OpticalFiber.status)
    )
    for cable_id, fiber_status, count in rows:
        summaries[cable_id][fiber_status] = count
    return summaries


def _cable_response(cable: OpticalCable, summary: dict[str, int]) -> dict[str, Any]:
    return {
        **_cable_snapshot(cable),
        "fiber_summary": {
            "total": sum(summary.values()),
            "available": summary.get("available", 0),
            "reserved": summary.get("reserved", 0),
            "occupied": summary.get("occupied", 0),
            "damaged": summary.get("damaged", 0),
            "deactivated": summary.get("deactivated", 0),
        },
        "created_at": cable.created_at,
        "updated_at": cable.updated_at,
    }


def _fiber_response(
    fiber: OpticalFiber,
    tube: CableTube | None = None,
    connected_ends: list[str] | None = None,
) -> dict[str, Any]:
    tube = tube or fiber.tube
    return {
        "id": str(fiber.id),
        "cable_id": str(fiber.cable_id),
        "tube_id": str(fiber.tube_id),
        "tube_position": tube.position,
        "tube_color": tube.color_code,
        "position": fiber.position,
        "global_position": fiber.global_position,
        "color_code": fiber.color_code,
        "status": fiber.status,
        "properties": fiber.properties,
        "revision": fiber.revision,
        "connected_ends": (
            sorted(endpoint.end_side for endpoint in fiber.endpoints)
            if connected_ends is None
            else connected_ends
        ),
    }


@router.get("")
def list_cables(
    _: CurrentUser,
    db: DbSession,
    network_id: uuid.UUID | None = None,
    limit: int = Query(default=1000, ge=1, le=2000),
) -> list[dict[str, Any]]:
    query = select(OpticalCable).order_by(OpticalCable.name).limit(limit)
    if network_id is not None:
        query = query.where(OpticalCable.network_id == network_id)
    cables = list(db.scalars(query))
    summaries = _fiber_summary(db, [cable.id for cable in cables])
    return [_cable_response(cable, summaries[cable.id]) for cable in cables]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_cable(payload: OpticalCableCreate, actor: AdminUser, db: DbSession) -> dict[str, Any]:
    if payload.network_id is not None and db.get(ServiceNetwork, payload.network_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    feature = None
    feature_before = None
    if payload.map_feature_id is not None:
        feature = db.get(MapFeature, payload.map_feature_id)
        if feature is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="map feature not found"
            )
        if feature.feature_type not in {"cable", "route"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="map feature must be a cable or route",
            )
        if db.scalar(
            select(OpticalCable.id).where(OpticalCable.map_feature_id == payload.map_feature_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="map feature already linked to an optical cable",
            )
        feature_before = {"properties": feature.properties, "revision": feature.revision}

    cable = OpticalCable(**payload.model_dump(), created_by=actor.id, updated_by=actor.id)
    db.add(cable)
    db.flush()
    tubes = [
        CableTube(
            cable_id=cable.id,
            position=position,
            color_code=_color(position),
            label=f"Tubo {position}",
        )
        for position in range(1, payload.tube_count + 1)
    ]
    db.add_all(tubes)
    db.flush()
    fibers: list[OpticalFiber] = []
    for global_position in range(1, payload.fiber_count + 1):
        tube_index = (global_position - 1) // payload.fibers_per_tube
        position = (global_position - 1) % payload.fibers_per_tube + 1
        fibers.append(
            OpticalFiber(
                cable_id=cable.id,
                tube_id=tubes[tube_index].id,
                position=position,
                global_position=global_position,
                color_code=_color(position),
                created_by=actor.id,
                updated_by=actor.id,
            )
        )
    db.add_all(fibers)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="optical cable conflicts with existing inventory",
        ) from exc

    if feature is not None:
        feature.properties = {
            **feature.properties,
            "optical_cable_id": str(cable.id),
            "fiber_count": payload.fiber_count,
            "capacity": payload.fiber_count,
        }
        feature.revision += 1
        feature.updated_by = actor.id
        record_audit(
            db,
            actor_user_id=actor.id,
            action="map_feature.cable_link",
            entity_type="map_feature",
            entity_id=str(feature.id),
            before_data=feature_before,
            after_data={"properties": feature.properties, "revision": feature.revision},
        )
    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_cable.create",
        entity_type="optical_cable",
        entity_id=str(cable.id),
        after_data=_cable_snapshot(cable),
    )
    return _cable_response(cable, {"available": len(fibers)})


@router.get("/{cable_id}")
def get_cable(cable_id: uuid.UUID, _: CurrentUser, db: DbSession) -> dict[str, Any]:
    cable = _get_cable(db, cable_id)
    summary = _fiber_summary(db, [cable.id])
    return _cable_response(cable, summary[cable.id])


@router.patch("/{cable_id}")
def update_cable(
    cable_id: uuid.UUID,
    payload: OpticalCableUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    cable = _get_cable(db, cable_id)
    if cable.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale cable revision")
    before = _cable_snapshot(cable)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        setattr(cable, key, value)
    cable.revision += 1
    cable.updated_by = actor.id
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_cable.update",
        entity_type="optical_cable",
        entity_id=str(cable.id),
        before_data=before,
        after_data=_cable_snapshot(cable),
    )
    summary = _fiber_summary(db, [cable.id])
    return _cable_response(cable, summary[cable.id])


@router.get("/{cable_id}/fibers")
def list_cable_fibers(cable_id: uuid.UUID, _: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    _get_cable(db, cable_id)
    rows = list(
        db.execute(
            select(OpticalFiber, CableTube)
            .join(CableTube, CableTube.id == OpticalFiber.tube_id)
            .where(OpticalFiber.cable_id == cable_id)
            .order_by(OpticalFiber.global_position)
        )
    )
    fiber_ids = [fiber.id for fiber, _ in rows]
    connected: dict[uuid.UUID, list[str]] = defaultdict(list)
    if fiber_ids:
        for fiber_id, end_side in db.execute(
            select(FiberConnectionEndpoint.fiber_id, FiberConnectionEndpoint.end_side).where(
                FiberConnectionEndpoint.fiber_id.in_(fiber_ids)
            )
        ):
            connected[fiber_id].append(end_side)
        for fiber_id, fiber_end in db.execute(
            select(FiberPortLink.fiber_id, FiberPortLink.fiber_end).where(
                FiberPortLink.fiber_id.in_(fiber_ids)
            )
        ):
            connected[fiber_id].append(fiber_end)
    return [_fiber_response(fiber, tube, sorted(connected[fiber.id])) for fiber, tube in rows]


@fibers_router.patch("/{fiber_id}")
def update_fiber(
    fiber_id: uuid.UUID,
    payload: OpticalFiberUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    fiber = db.get(OpticalFiber, fiber_id)
    if fiber is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="optical fiber not found")
    if fiber.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale fiber revision")
    before = _fiber_response(fiber)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        setattr(fiber, key, value)
    fiber.revision += 1
    fiber.updated_by = actor.id
    db.flush()
    after = _fiber_response(fiber)
    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_fiber.update",
        entity_type="optical_fiber",
        entity_id=str(fiber.id),
        before_data=before,
        after_data=after,
    )
    return after


def _connection_response(connection: FiberConnection) -> dict[str, Any]:
    return {
        "id": str(connection.id),
        "enclosure_feature_id": str(connection.enclosure_feature_id),
        "connection_type": connection.connection_type,
        "loss_db": connection.loss_db,
        "notes": connection.notes,
        "revision": connection.revision,
        "endpoints": [
            {
                "id": str(endpoint.id),
                "fiber_id": str(endpoint.fiber_id),
                "end_side": endpoint.end_side,
                "role": endpoint.role,
            }
            for endpoint in sorted(connection.endpoints, key=lambda item: item.role)
        ],
        "created_at": connection.created_at,
        "updated_at": connection.updated_at,
    }


def _connection_snapshot(connection: FiberConnection) -> dict[str, Any]:
    response = _connection_response(connection)
    response.pop("created_at", None)
    response.pop("updated_at", None)
    return response


@connections_router.get("")
def list_connections(
    _: CurrentUser,
    db: DbSession,
    enclosure_feature_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    query = select(FiberConnection).order_by(FiberConnection.created_at)
    if enclosure_feature_id is not None:
        query = query.where(FiberConnection.enclosure_feature_id == enclosure_feature_id)
    return [_connection_response(item) for item in db.scalars(query)]


@connections_router.post("", status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: FiberConnectionCreate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    enclosure = db.get(MapFeature, payload.enclosure_feature_id)
    if enclosure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="enclosure not found")
    if enclosure.feature_type not in ENCLOSURE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="feature cannot contain fiber connections",
        )
    requested = [(item.fiber_id, item.end_side) for item in payload.endpoints]
    fibers = {
        fiber.id: fiber
        for fiber in db.scalars(
            select(OpticalFiber).where(OpticalFiber.id.in_([fiber_id for fiber_id, _ in requested]))
        )
    }
    if len(fibers) != 2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fiber not found")
    occupied = db.scalar(
        select(FiberConnectionEndpoint.id).where(
            tuple_(FiberConnectionEndpoint.fiber_id, FiberConnectionEndpoint.end_side).in_(
                requested
            )
        )
    )
    if occupied is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fiber endpoint is already connected",
        )
    linked_to_port = db.scalar(
        select(FiberPortLink.id).where(
            tuple_(FiberPortLink.fiber_id, FiberPortLink.fiber_end).in_(requested)
        )
    )
    if linked_to_port is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fiber endpoint is already connected to an optical port",
        )
    connection = FiberConnection(
        enclosure_feature_id=payload.enclosure_feature_id,
        connection_type=payload.connection_type,
        loss_db=payload.loss_db,
        notes=payload.notes,
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(connection)
    db.flush()
    connection.endpoints = [
        FiberConnectionEndpoint(
            fiber_id=endpoint.fiber_id,
            end_side=endpoint.end_side,
            role=role,
        )
        for role, endpoint in zip(("a", "b"), payload.endpoints, strict=True)
    ]
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fiber endpoint is already connected",
        ) from exc
    for fiber in fibers.values():
        fiber.status = "occupied"
        fiber.revision += 1
        fiber.updated_by = actor.id
    record_audit(
        db,
        actor_user_id=actor.id,
        action="fiber_connection.create",
        entity_type="fiber_connection",
        entity_id=str(connection.id),
        after_data=_connection_snapshot(connection),
    )
    return _connection_response(connection)


@connections_router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: uuid.UUID,
    actor: AdminUser,
    db: DbSession,
) -> Response:
    connection = db.get(FiberConnection, connection_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connection not found")
    before = _connection_snapshot(connection)
    fiber_ids = [endpoint.fiber_id for endpoint in connection.endpoints]
    record_audit(
        db,
        actor_user_id=actor.id,
        action="fiber_connection.delete",
        entity_type="fiber_connection",
        entity_id=str(connection.id),
        before_data=before,
    )
    db.delete(connection)
    db.flush()
    for fiber_id in fiber_ids:
        has_connection = db.scalar(
            select(FiberConnectionEndpoint.id).where(FiberConnectionEndpoint.fiber_id == fiber_id)
        )
        has_port = db.scalar(select(FiberPortLink.id).where(FiberPortLink.fiber_id == fiber_id))
        fiber = db.get(OpticalFiber, fiber_id)
        if fiber and not has_connection and not has_port:
            fiber.status = "available"
            fiber.revision += 1
            fiber.updated_by = actor.id
    return Response(status_code=status.HTTP_204_NO_CONTENT)
