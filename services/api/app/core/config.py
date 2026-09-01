"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration."""

    model_config = SettingsConfigDict(env_prefix="APP_", case_sensitive=False)

    database_url: str
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    cors_origins: list[str] = ["http://localhost:3030"]
    environment: str = "development"
    geocoding_enabled: bool = True
    geocoding_base_url: str = "https://nominatim.openstreetmap.org"
    geocoding_cache_days: int = Field(default=30, ge=1, le=365)

    @field_validator("cors_origins")
    @classmethod
    def reject_wildcard_cors(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("wildcard CORS is not allowed")
        return value

    @field_validator("geocoding_base_url")
    @classmethod
    def validate_geocoding_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("geocoding base URL must use HTTPS")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
