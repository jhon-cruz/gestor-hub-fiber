"""Fiber-to-port terminations, end-to-end tracing and optical budget."""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models.fiber_topology import (
    FiberConnectionEndpoint,
    FiberPortLink,
    OpticalFiber,
)
from app.models.optical import OpticalDevice, OpticalPort
from app.schemas.fiber_topology import FiberPortLinkCreate
from app.services.audit import record_audit
from app.services.optical_trace import trace_from_port

links_router = APIRouter(prefix="/fiber-port-links", tags=["optical-trace"])
trace_router = APIRouter(prefix="/optical-traces", tags=["optical-trace"])


def _response(link: FiberPortLink, db: DbSession) -> dict[str, Any]:
    fiber = db.get(OpticalFiber, link.fiber_id)
    port = db.get(OpticalPort, link.port_id)
    device = db.get(OpticalDevice, port.device_id) if port else None
    return {
        "id": str(link.id),
        "fiber_id": str(link.fiber_id),
        "fiber_end": link.fiber_end,
        "port_id": str(link.port_id),
        "port_side": link.port_side,
        "insertion_loss_db": link.insertion_loss_db,
        "notes": link.notes,
        "revision": link.revision,
        "fiber": (
            {
                "cable_id": str(fiber.cable_id),
                "global_position": fiber.global_position,
                "color_code": fiber.color_code,
            }
            if fiber
            else None
        ),
        "port": (
            {
                "device_id": str(port.device_id),
                "device_name": device.name if device else None,
                "device_type": device.device_type if device else None,
                "position": port.position,
                "label": port.label,
                "port_kind": port.port_kind,
            }
            if port
            else None
        ),
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def _snapshot(link: FiberPortLink) -> dict[str, Any]:
    return {
        "id": str(link.id),
        "fiber_id": str(link.fiber_id),
        "fiber_end": link.fiber_end,
        "port_id": str(link.port_id),
        "port_side": link.port_side,
        "insertion_loss_db": link.insertion_loss_db,
        "notes": link.notes,
        "revision": link.revision,
    }


@links_router.get("")
def list_links(
    _: CurrentUser,
    db: DbSession,
    port_id: uuid.UUID | None = None,
    fiber_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    query = select(FiberPortLink).order_by(FiberPortLink.created_at)
    if port_id is not None:
        query = query.where(FiberPortLink.port_id == port_id)
    if fiber_id is not None:
        query = query.where(FiberPortLink.fiber_id == fiber_id)
    if device_id is not None:
        query = query.join(OpticalPort, OpticalPort.id == FiberPortLink.port_id).where(
            OpticalPort.device_id == device_id
        )
    return [_response(link, db) for link in db.scalars(query)]


@links_router.post("", status_code=status.HTTP_201_CREATED)
def create_link(
    payload: FiberPortLinkCreate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    fiber = db.get(OpticalFiber, payload.fiber_id)
    if fiber is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="optical fiber not found")
    port = db.get(OpticalPort, payload.port_id)
    if port is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="optical port not found")
    if payload.port_side == "b" and port.port_kind != "adapter":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="side B is only supported by adapter ports",
        )
    if db.scalar(
        select(FiberConnectionEndpoint.id).where(
            FiberConnectionEndpoint.fiber_id == payload.fiber_id,
            FiberConnectionEndpoint.end_side == payload.fiber_end,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fiber endpoint is already connected to another fiber",
        )
    link = FiberPortLink(**payload.model_dump(), created_by=actor.id, updated_by=actor.id)
    db.add(link)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="fiber endpoint or port side is already connected",
        ) from exc
    port.status = "occupied"
    port.revision += 1
    port.updated_by = actor.id
    fiber.status = "occupied"
    fiber.revision += 1
    fiber.updated_by = actor.id
    record_audit(
        db,
        actor_user_id=actor.id,
        action="fiber_port_link.create",
        entity_type="fiber_port_link",
        entity_id=str(link.id),
        after_data=_snapshot(link),
    )
    return _response(link, db)


@links_router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: uuid.UUID, actor: AdminUser, db: DbSession) -> Response:
    link = db.get(FiberPortLink, link_id)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="fiber-port link not found"
        )
    before = _snapshot(link)
    fiber_id, port_id = link.fiber_id, link.port_id
    db.delete(link)
    db.flush()
    port = db.get(OpticalPort, port_id)
    if port and not db.scalar(select(FiberPortLink.id).where(FiberPortLink.port_id == port_id)):
        port.status = "available"
        port.revision += 1
        port.updated_by = actor.id
    fiber = db.get(OpticalFiber, fiber_id)
    has_link = db.scalar(select(FiberPortLink.id).where(FiberPortLink.fiber_id == fiber_id))
    has_fusion = db.scalar(
        select(FiberConnectionEndpoint.id).where(FiberConnectionEndpoint.fiber_id == fiber_id)
    )
    if fiber and not has_link and not has_fusion:
        fiber.status = "available"
        fiber.revision += 1
        fiber.updated_by = actor.id
    record_audit(
        db,
        actor_user_id=actor.id,
        action="fiber_port_link.delete",
        entity_type="fiber_port_link",
        entity_id=str(link_id),
        before_data=before,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@trace_router.get("/from-port/{port_id}")
def get_trace(
    port_id: uuid.UUID,
    _: CurrentUser,
    db: DbSession,
    tx_power_dbm: float = Query(default=3.0, ge=-20, le=20),
    receiver_min_dbm: float = Query(default=-27.0, ge=-50, le=0),
) -> dict[str, Any]:
    try:
        return trace_from_port(db, port_id, tx_power_dbm, receiver_min_dbm)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
