"""RBAC-protected optical equipment and port inventory endpoints."""

import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import AdminUser, CurrentUser, DbSession
from app.models.map_feature import MapFeature
from app.models.optical import OpticalDevice, OpticalPort
from app.schemas.optical import OpticalDeviceCreate, OpticalDeviceUpdate, OpticalPortUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/optical-devices", tags=["optical-domain"])
ports_router = APIRouter(prefix="/optical-ports", tags=["optical-domain"])

DEVICE_PORT_KIND = {
    "olt": "pon",
    "dio": "adapter",
    "splitter": "splitter_output",
    "cto": "cto_distribution",
}


def _port_snapshot(port: OpticalPort) -> dict[str, Any]:
    return {
        "id": str(port.id),
        "device_id": str(port.device_id),
        "port_kind": port.port_kind,
        "position": port.position,
        "label": port.label,
        "status": port.status,
        "properties": port.properties,
        "revision": port.revision,
    }


def _port_response(port: OpticalPort) -> dict[str, Any]:
    return {
        **_port_snapshot(port),
        "created_at": port.created_at,
        "updated_at": port.updated_at,
    }


def _device_snapshot(device: OpticalDevice) -> dict[str, Any]:
    return {
        "id": str(device.id),
        "map_feature_id": str(device.map_feature_id) if device.map_feature_id else None,
        "device_type": device.device_type,
        "name": device.name,
        "status": device.status,
        "manufacturer": device.manufacturer,
        "model": device.model,
        "serial_number": device.serial_number,
        "port_capacity": device.port_capacity,
        "properties": device.properties,
        "revision": device.revision,
    }


def _port_summaries(db: DbSession, device_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
    summaries: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    if not device_ids:
        return summaries
    rows = db.execute(
        select(OpticalPort.device_id, OpticalPort.status, func.count(OpticalPort.id))
        .where(OpticalPort.device_id.in_(device_ids))
        .group_by(OpticalPort.device_id, OpticalPort.status)
    )
    for device_id, port_status, count in rows:
        summaries[device_id][port_status] = count
    return summaries


def _device_response(device: OpticalDevice, port_summary: dict[str, int]) -> dict[str, Any]:
    return {
        **_device_snapshot(device),
        "port_summary": {
            "total": sum(port_summary.values()),
            "available": port_summary.get("available", 0),
            "reserved": port_summary.get("reserved", 0),
            "occupied": port_summary.get("occupied", 0),
            "damaged": port_summary.get("damaged", 0),
            "deactivated": port_summary.get("deactivated", 0),
        },
        "created_at": device.created_at,
        "updated_at": device.updated_at,
    }


def _get_device(db: DbSession, device_id: uuid.UUID) -> OpticalDevice:
    device = db.get(OpticalDevice, device_id)
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="optical device not found"
        )
    return device


@router.get("")
def list_devices(
    _: CurrentUser,
    db: DbSession,
    device_type: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    query = select(OpticalDevice).order_by(OpticalDevice.created_at).limit(limit).offset(offset)
    if device_type is not None:
        if device_type not in DEVICE_PORT_KIND:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="unsupported optical device type",
            )
        query = query.where(OpticalDevice.device_type == device_type)
    devices = list(db.scalars(query))
    summaries = _port_summaries(db, [device.id for device in devices])
    return [_device_response(device, summaries[device.id]) for device in devices]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(payload: OpticalDeviceCreate, actor: AdminUser, db: DbSession) -> dict[str, Any]:
    feature = None
    feature_before = None
    if payload.map_feature_id is not None:
        feature = db.get(MapFeature, payload.map_feature_id)
        if feature is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="map feature not found"
            )
        if feature.feature_type != payload.device_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="map feature type does not match optical device type",
            )
        linked = db.scalar(
            select(OpticalDevice.id).where(OpticalDevice.map_feature_id == payload.map_feature_id)
        )
        if linked is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="map feature already linked to an optical device",
            )
        feature_before = {
            "properties": feature.properties,
            "revision": feature.revision,
        }

    device = OpticalDevice(
        **payload.model_dump(),
        created_by=actor.id,
        updated_by=actor.id,
    )
    db.add(device)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="optical device conflicts with existing inventory",
        ) from exc
    if payload.device_type == "splitter":
        db.add(
            OpticalPort(
                device_id=device.id,
                port_kind="splitter_input",
                position=1,
                label="Entrada",
                created_by=actor.id,
                updated_by=actor.id,
            )
        )
    port_kind = DEVICE_PORT_KIND[payload.device_type]
    db.add_all(
        [
            OpticalPort(
                device_id=device.id,
                port_kind=port_kind,
                position=position,
                label=f"Porta {position}",
                created_by=actor.id,
                updated_by=actor.id,
            )
            for position in range(1, payload.port_capacity + 1)
        ]
    )
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="optical device conflicts with existing inventory",
        ) from exc

    if feature is not None:
        feature.properties = {
            **feature.properties,
            "optical_device_id": str(device.id),
            "capacity": payload.port_capacity,
        }
        feature.revision += 1
        feature.updated_by = actor.id
        record_audit(
            db,
            actor_user_id=actor.id,
            action="map_feature.optical_link",
            entity_type="map_feature",
            entity_id=str(feature.id),
            before_data=feature_before,
            after_data={"properties": feature.properties, "revision": feature.revision},
        )

    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_device.create",
        entity_type="optical_device",
        entity_id=str(device.id),
        after_data=_device_snapshot(device),
    )
    total_ports = payload.port_capacity + (1 if payload.device_type == "splitter" else 0)
    return _device_response(device, {"available": total_ports})


@router.get("/{device_id}")
def get_device(device_id: uuid.UUID, _: CurrentUser, db: DbSession) -> dict[str, Any]:
    device = _get_device(db, device_id)
    summary = _port_summaries(db, [device.id])
    return _device_response(device, summary[device.id])


@router.patch("/{device_id}")
def update_device(
    device_id: uuid.UUID,
    payload: OpticalDeviceUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    device = _get_device(db, device_id)
    if device.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale device revision")
    before = _device_snapshot(device)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        setattr(device, key, value)
    device.revision += 1
    device.updated_by = actor.id
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_device.update",
        entity_type="optical_device",
        entity_id=str(device.id),
        before_data=before,
        after_data=_device_snapshot(device),
    )
    summary = _port_summaries(db, [device.id])
    return _device_response(device, summary[device.id])


@router.get("/{device_id}/ports")
def list_ports(device_id: uuid.UUID, _: CurrentUser, db: DbSession) -> list[dict[str, Any]]:
    _get_device(db, device_id)
    ports = db.scalars(
        select(OpticalPort)
        .where(OpticalPort.device_id == device_id)
        .order_by(OpticalPort.port_kind, OpticalPort.position)
    )
    return [_port_response(port) for port in ports]


@ports_router.patch("/{port_id}")
def update_port(
    port_id: uuid.UUID,
    payload: OpticalPortUpdate,
    actor: AdminUser,
    db: DbSession,
) -> dict[str, Any]:
    port = db.get(OpticalPort, port_id)
    if port is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="optical port not found")
    if port.revision != payload.expected_revision:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="stale port revision")
    before = _port_snapshot(port)
    for key, value in payload.model_dump(exclude_unset=True, exclude={"expected_revision"}).items():
        setattr(port, key, value)
    port.revision += 1
    port.updated_by = actor.id
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="optical_port.update",
        entity_type="optical_port",
        entity_id=str(port.id),
        before_data=before,
        after_data=_port_snapshot(port),
    )
    return _port_response(port)
