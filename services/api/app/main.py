"""Gestor Hub Fiber ASGI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import __version__
from app.api.dependencies import DbSession
from app.api.routes import auth, map_features, users
from app.core.config import get_settings

settings = get_settings()

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


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/ready", tags=["operations"])
def readiness(db: DbSession) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready"}
