"""Rate-limited forward geocoding client with a replaceable provider URL."""

import asyncio
import time
from typing import Any

import httpx2

from app.core.config import get_settings

_request_lock = asyncio.Lock()
_last_request_at = 0.0
USER_AGENT = "GestorHubFiber/0.6 (+https://github.com/jhon-cruz/gestor-hub-fiber)"


class GeocodingUnavailableError(RuntimeError):
    """Raised when the configured provider cannot answer safely."""


async def search_nominatim(query: str, limit: int) -> list[dict[str, Any]]:
    global _last_request_at

    settings = get_settings()
    if not settings.geocoding_enabled:
        raise GeocodingUnavailableError("address search is disabled")

    async with _request_lock:
        wait_seconds = 1.05 - (time.monotonic() - _last_request_at)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        try:
            async with httpx2.AsyncClient(
                timeout=8.0,
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            ) as client:
                response = await client.get(
                    f"{settings.geocoding_base_url}/search",
                    params={
                        "q": query,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "countrycodes": "br",
                        "limit": limit,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx2.HTTPError, ValueError, TypeError) as exc:
            raise GeocodingUnavailableError("address provider is temporarily unavailable") from exc
        finally:
            _last_request_at = time.monotonic()

    results: list[dict[str, Any]] = []
    for item in payload if isinstance(payload, list) else []:
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
            south, north, west, east = [float(value) for value in item["boundingbox"]]
        except KeyError, TypeError, ValueError:
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        results.append(
            {
                "label": str(item.get("display_name", ""))[:500],
                "latitude": latitude,
                "longitude": longitude,
                "viewport": [west, south, east, north],
                "category": str(item.get("category", "address"))[:80],
                "type": str(item.get("type", "place"))[:80],
            }
        )
    return results
