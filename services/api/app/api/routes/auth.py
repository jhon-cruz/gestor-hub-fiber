"""Login and identity endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select, text

from app.api.dependencies import CurrentUser, DbSession
from app.models.user import User, UserRole
from app.schemas.auth import AccessToken
from app.schemas.user import BootstrapAdmin, UserRead
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/bootstrap-status")
def bootstrap_status(db: DbSession) -> dict[str, bool]:
    """Tell the local interface whether the first administrator must be created."""

    return {"setup_required": db.scalar(select(func.count(User.id))) == 0}


@router.post("/bootstrap", response_model=AccessToken, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: BootstrapAdmin, db: DbSession) -> AccessToken:
    """Create exactly one initial administrator on an empty installation."""

    db.execute(text("SELECT pg_advisory_xact_lock(74002604)"))
    if db.scalar(select(func.count(User.id))) != 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="installation already initialized",
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.flush()
    return AccessToken(access_token=create_access_token(user))


@router.post("/token", response_model=AccessToken)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> AccessToken:
    username = form.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessToken(access_token=create_access_token(user))


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user
