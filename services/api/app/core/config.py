"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(env_prefix="APP_", case_sensitive=False)

    database_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    cors_origins: list[str] = ["http://localhost:3030"]
    environment: str = "development"
    map_provider: Literal["openstreetmap", "google"] = "openstreetmap"
    google_maps_browser_api_key: SecretStr | None = None
    geocoding_enabled: bool = True
    geocoding_provider: Literal["nominatim", "geoapify", "google"] = "nominatim"
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_api_key: SecretStr | None = None
    google_geocoding_base_url: str = "https://maps.googleapis.com/maps/api/geocode"
    viacep_enabled: bool = True
    geocoding_cache_days: int = Field(default=30, ge=1, le=365)

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard CORS is not allowed")
        return value

    @field_validator("geocoding_base_url", "google_geocoding_base_url")
    @classmethod
    def validate_geocoding_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("geocoding base URL must use HTTPS")
        return value.rstrip("/")

    @model_validator(mode="after")
    def require_provider_credentials(self) -> Settings:
        if self.geocoding_provider in {"geoapify", "google"} and (
            self.geocoding_api_key is None or not self.geocoding_api_key.get_secret_value().strip()
        ):
            raise ValueError("APP_GEOCODING_API_KEY is required for the selected provider")
        if self.map_provider == "google" and (
            self.google_maps_browser_api_key is None
            or not self.google_maps_browser_api_key.get_secret_value().strip()
        ):
            raise ValueError("APP_GOOGLE_MAPS_BROWSER_API_KEY is required for Google Maps")
        if self.geocoding_provider == "google" and self.map_provider != "google":
            raise ValueError("Google Geocoding must be displayed with Google Maps")
        if self.geocoding_provider == "google" and self.geocoding_cache_days > 30:
            raise ValueError("Google Geocoding cache cannot exceed 30 days")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
