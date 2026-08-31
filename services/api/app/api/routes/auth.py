"""Login and identity endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.dependencies import CurrentUser, DbSession
from app.models.user import User
from app.schemas.auth import AccessToken
from app.schemas.user import UserRead
from app.services.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])


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
