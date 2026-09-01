"""Brazil-focused, cached upstream geocoding with replaceable providers."""

import asyncio
import re
import time
from typing import Any

import httpx2

from app.core.config import get_settings

_request_lock = asyncio.Lock()
_last_request_at = 0.0
USER_AGENT = "GestorHubFiber/0.9 (+https://github.com/jhon-cruz/gestor-hub-fiber)"
CEP_PATTERN = re.compile(r"(?<!\d)(\d{5})-?(\d{3})(?!\d)")


class GeocodingUnavailableError(RuntimeError):
    """Raised when the configured provider cannot answer safely."""


def provider_attribution() -> str:
    """Return the attribution required by the active coordinate provider."""
    provider = get_settings().geocoding_provider
    if provider == "google":
        return "Google Maps"
    if provider == "geoapify":
        return "© OpenStreetMap contributors · geocodificação Geoapify"
    return "© OpenStreetMap contributors · Nominatim"


async def _lookup_cep(client: httpx2.AsyncClient, query: str) -> str:
    """Expand an explicit Brazilian CEP into searchable address components."""
    settings = get_settings()
    match = CEP_PATTERN.search(query)
    if not match or not settings.viacep_enabled:
        return query
    cep = "".join(match.groups())
    try:
        response = await client.get(f"https://viacep.com.br/ws/{cep}/json/")
        response.raise_for_status()
        payload = response.json()
    except httpx2.HTTPError, ValueError, TypeError:
        return query
    if not isinstance(payload, dict) or payload.get("erro"):
        return query
    query_without_cep = CEP_PATTERN.sub("", query)
    number_match = re.search(r"\b\d{1,6}[A-Za-z]?\b", query_without_cep)
    parts = [
        payload.get("logradouro"),
        number_match.group(0) if number_match else None,
        payload.get("bairro"),
        payload.get("localidade"),
        payload.get("uf"),
        payload.get("cep"),
    ]
    expanded = ", ".join(str(part).strip() for part in parts if part)
    return expanded or query


def _viewport_param(viewport: list[float] | None) -> str | None:
    if not viewport or len(viewport) != 4:
        return None
    west, south, east, north = viewport
    return f"{west},{north},{east},{south}"


def _nominatim_results(payload: Any) -> list[dict[str, Any]]:
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
        address = item.get("address") if isinstance(item.get("address"), dict) else {}
        results.append(
            {
                "label": str(item.get("display_name", ""))[:500],
                "latitude": latitude,
                "longitude": longitude,
                "viewport": [west, south, east, north],
                "category": str(item.get("category", "address"))[:80],
                "type": str(item.get("type", "place"))[:80],
                "precision": str(item.get("addresstype", item.get("type", "place")))[:80],
                "relevance": round(float(item.get("importance", 0)), 6),
                "address": {str(key)[:80]: str(value)[:200] for key, value in address.items()},
                "provider": "nominatim",
            }
        )
    return results


def _geoapify_results(payload: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    items = payload.get("results", []) if isinstance(payload, dict) else []
    for item in items:
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
        except KeyError, TypeError, ValueError:
            continue
        bbox = item.get("bbox") if isinstance(item.get("bbox"), dict) else {}
        west = float(bbox.get("lon1", longitude))
        south = float(bbox.get("lat1", latitude))
        east = float(bbox.get("lon2", longitude))
        north = float(bbox.get("lat2", latitude))
        rank = item.get("rank") if isinstance(item.get("rank"), dict) else {}
        results.append(
            {
                "label": str(item.get("formatted", item.get("address_line1", "")))[:500],
                "latitude": latitude,
                "longitude": longitude,
                "viewport": [west, south, east, north],
                "category": str(item.get("category", "address"))[:80],
                "type": str(item.get("result_type", "place"))[:80],
                "precision": str(rank.get("match_type", "unknown"))[:80],
                "relevance": round(float(rank.get("confidence", 0)), 6),
                "address": {
                    key: str(item[key])[:200]
                    for key in (
                        "housenumber",
                        "street",
                        "suburb",
                        "district",
                        "city",
                        "state",
                        "postcode",
                    )
                    if item.get(key)
                },
                "provider": "geoapify",
            }
        )
    return results


def _google_results(payload: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    items = payload.get("results", []) if isinstance(payload, dict) else []
    for item in items:
        geometry = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
        location = geometry.get("location") if isinstance(geometry.get("location"), dict) else {}
        viewport = geometry.get("viewport") if isinstance(geometry.get("viewport"), dict) else {}
        southwest = (
            viewport.get("southwest") if isinstance(viewport.get("southwest"), dict) else location
        )
        northeast = (
            viewport.get("northeast") if isinstance(viewport.get("northeast"), dict) else location
        )
        try:
            latitude = float(location["lat"])
            longitude = float(location["lng"])
            west = float(southwest.get("lng", longitude))
            south = float(southwest.get("lat", latitude))
            east = float(northeast.get("lng", longitude))
            north = float(northeast.get("lat", latitude))
        except KeyError, TypeError, ValueError:
            continue
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            continue
        address: dict[str, str] = {}
        for component in item.get("address_components", []):
            if not isinstance(component, dict):
                continue
            value = str(component.get("long_name", ""))[:200]
            for component_type in component.get("types", []):
                address[str(component_type)[:80]] = value
        types = item.get("types") if isinstance(item.get("types"), list) else []
        results.append(
            {
                "label": str(item.get("formatted_address", ""))[:500],
                "latitude": latitude,
                "longitude": longitude,
                "viewport": [west, south, east, north],
                "category": "address",
                "type": str(types[0] if types else "place")[:80],
                "precision": str(geometry.get("location_type", "APPROXIMATE"))[:80],
                "relevance": 1.0,
                "address": address,
                "provider": "google",
            }
        )
    return results


async def search_addresses(
    query: str,
    limit: int,
    viewport: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Search Brazil, prioritizing the selected network and explicit CEP data."""
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
                timeout=10.0,
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            ) as client:
                expanded_query = await _lookup_cep(client, query)
                if settings.geocoding_provider == "google":
                    params: dict[str, Any] = {
                        "address": expanded_query,
                        "key": settings.geocoding_api_key.get_secret_value(),
                        "language": "pt-BR",
                        "region": "br",
                        "components": "country:BR",
                    }
                    if viewport:
                        west, south, east, north = viewport
                        params["bounds"] = f"{south},{west}|{north},{east}"
                    response = await client.get(
                        f"{settings.google_geocoding_base_url}/json", params=params
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if payload.get("status") not in {"OK", "ZERO_RESULTS"}:
                        raise GeocodingUnavailableError(
                            f"Google Geocoding returned {payload.get('status', 'UNKNOWN_ERROR')}"
                        )
                    results = _google_results(payload)
                elif settings.geocoding_provider == "geoapify":
                    params: dict[str, Any] = {
                        "text": expanded_query,
                        "format": "json",
                        "lang": "pt",
                        "limit": limit,
                        "filter": "countrycode:br",
                        "apiKey": settings.geocoding_api_key.get_secret_value(),
                    }
                    if viewport:
                        west, south, east, north = viewport
                        params["bias"] = f"rect:{west},{south},{east},{north}"
                    response = await client.get(
                        f"{settings.geocoding_base_url}/v1/geocode/search", params=params
                    )
                    response.raise_for_status()
                    results = _geoapify_results(response.json())
                else:
                    params = {
                        "q": expanded_query,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "countrycodes": "br",
                        "layer": "address",
                        "dedupe": 1,
                        "accept-language": "pt-BR,pt",
                        "limit": limit,
                    }
                    viewbox = _viewport_param(viewport)
                    if viewbox:
                        params["viewbox"] = viewbox
                        params["bounded"] = 0
                    response = await client.get(
                        f"{settings.geocoding_base_url}/search", params=params
                    )
                    response.raise_for_status()
                    results = _nominatim_results(response.json())
        except (httpx2.HTTPError, ValueError, TypeError, AttributeError) as exc:
            raise GeocodingUnavailableError("address provider is temporarily unavailable") from exc
        finally:
            _last_request_at = time.monotonic()

    # Both providers already rank with the requested geographic bias. Preserve that order.
    return results[:limit]
