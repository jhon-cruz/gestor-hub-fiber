"""Short-lived cache for explicit user-triggered geocoding searches."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GeocodeCache(Base):
    __tablename__ = "geocode_cache"
    __table_args__ = (Index("ix_geocode_cache_expires_at", "expires_at"),)

    query_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
