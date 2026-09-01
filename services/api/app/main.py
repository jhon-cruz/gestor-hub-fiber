"""Gestor Hub Fiber ASGI application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import __version__
from app.api.dependencies import DbSession
from app.api.routes import (
    auth,
    fiber_topology,
    geocoding,
    imports,
    map_config,
    map_features,
    networks,
    optical,
    optical_trace,
    users,
)
from app.core.config import get_settings

settings = get_settings()
static_dir = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Gestor Hub Fiber API",
    version=__version__,
    description="API multiusuário para domínio GIS FTTx e integrações ERP.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(map_features.router, prefix="/api/v1")
app.include_router(map_config.router, prefix="/api/v1")
app.include_router(imports.router, prefix="/api/v1")
app.include_router(optical.router, prefix="/api/v1")
app.include_router(optical.ports_router, prefix="/api/v1")
app.include_router(networks.router, prefix="/api/v1")
app.include_router(geocoding.router, prefix="/api/v1")
app.include_router(fiber_topology.router, prefix="/api/v1")
app.include_router(fiber_topology.fibers_router, prefix="/api/v1")
app.include_router(fiber_topology.connections_router, prefix="/api/v1")
app.include_router(optical_trace.links_router, prefix="/api/v1")
app.include_router(optical_trace.trace_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://maps.googleapis.com https://maps.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: blob: https://tile.openstreetmap.org https://unpkg.com "
        "https://*.googleapis.com https://*.gstatic.com; "
        "connect-src 'self' https://*.googleapis.com; worker-src 'self' blob:; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/", include_in_schema=False)
def interface() -> FileResponse:
    return FileResponse(static_dir / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/ready", tags=["operations"])
def readiness(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
