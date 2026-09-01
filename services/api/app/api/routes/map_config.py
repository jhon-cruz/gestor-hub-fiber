"""Authenticated runtime map configuration for the browser client."""

from typing import Any

from fastapi import APIRouter, Response

from app.api.dependencies import CurrentUser
from app.core.config import get_settings

router = APIRouter(prefix="/map-config", tags=["map"])


@router.get("")
def map_config(_: CurrentUser, response: Response) -> dict[str, Any]:
    """Expose only the browser-safe configuration needed to load the map SDK."""
    response.headers["Cache-Control"] = "no-store"
    settings = get_settings()
    browser_key = (
        settings.google_maps_browser_api_key.get_secret_value()
        if settings.map_provider == "google" and settings.google_maps_browser_api_key
        else None
    )
    return {
        "provider": settings.map_provider,
        "geocoding_provider": settings.geocoding_provider,
        "google_maps_browser_api_key": browser_key,
    }
