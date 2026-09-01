"""Authenticated, cached, user-triggered address search."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.geocode import GeocodeCache
from app.models.network import ServiceNetwork
from app.services.geocoding import (
    GeocodingUnavailableError,
    provider_attribution,
    search_addresses,
)

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.get("/search")
async def search_address(
    _: CurrentUser,
    db: DbSession,
    q: str = Query(min_length=3, max_length=200),
    limit: int = Query(default=5, ge=1, le=5),
    network_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    network = None
    if network_id:
        network = db.get(ServiceNetwork, network_id)
        if network is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="network not found")
    viewport = list(network.viewport) if network and network.viewport else None
    normalized = " ".join(q.strip().lower().split())
    effective_query = q.strip()
    if network and network.city.casefold() not in normalized.casefold():
        effective_query = f"{effective_query}, {network.city}, {network.state}"
    settings = get_settings()
    query_key = hashlib.sha256(
        f"{settings.geocoding_provider}:br:{limit}:{network_id}:{viewport}:{normalized}".encode()
    ).hexdigest()
    cached = db.get(GeocodeCache, query_key)
    now = datetime.now(UTC)
    if cached is not None and cached.expires_at > now:
        return {
            "results": cached.results,
            "cached": True,
            "attribution": provider_attribution(),
            "network_bias": bool(viewport),
        }
    if cached is not None:
        db.delete(cached)
        db.flush()

    try:
        results = await search_addresses(effective_query, limit, viewport)
    except GeocodingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    db.add(
        GeocodeCache(
            query_key=query_key,
            results=results,
            expires_at=now + timedelta(days=settings.geocoding_cache_days),
        )
    )
    return {
        "results": results,
        "cached": False,
        "attribution": provider_attribution(),
        "network_bias": bool(viewport),
    }
