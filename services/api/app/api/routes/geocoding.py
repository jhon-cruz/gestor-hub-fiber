"""Authenticated, cached, user-triggered address search."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CurrentUser, DbSession
from app.core.config import get_settings
from app.models.geocode import GeocodeCache
from app.services.geocoding import GeocodingUnavailableError, search_nominatim

router = APIRouter(prefix="/geocoding", tags=["geocoding"])


@router.get("/search")
async def search_address(
    _: CurrentUser,
    db: DbSession,
    q: str = Query(min_length=3, max_length=200),
    limit: int = Query(default=5, ge=1, le=5),
) -> dict[str, Any]:
    normalized = " ".join(q.strip().lower().split())
    query_key = hashlib.sha256(f"br:{limit}:{normalized}".encode()).hexdigest()
    cached = db.get(GeocodeCache, query_key)
    now = datetime.now(UTC)
    if cached is not None and cached.expires_at > now:
        return {
            "results": cached.results,
            "cached": True,
            "attribution": "© OpenStreetMap contributors",
        }
    if cached is not None:
        db.delete(cached)
        db.flush()

    try:
        results = await search_nominatim(q.strip(), limit)
    except GeocodingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    settings = get_settings()
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
        "attribution": "© OpenStreetMap contributors",
    }
