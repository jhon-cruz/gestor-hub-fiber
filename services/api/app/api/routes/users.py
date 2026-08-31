"""Administrator-managed application accounts."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import AdminUser, DbSession
from app.models.user import User
from app.schemas.user import UserCreate, UserRead
from app.services.audit import record_audit
from app.services.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserRead])
def list_users(_: AdminUser, db: DbSession) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, actor: AdminUser, db: DbSession) -> User:
    if db.scalar(select(User.id).where(User.username == payload.username)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username already exists")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        after_data={"username": user.username, "role": user.role.value},
    )
    return user
