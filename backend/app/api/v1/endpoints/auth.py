from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DBSession, build_access_context
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Role, User
from app.schemas import ChangePasswordRequest, CurrentUserRead, LoginRequest, TokenRead

router = APIRouter(prefix="/auth")


def serialize_current_user(user: User) -> CurrentUserRead:
    access = build_access_context(user)
    return CurrentUserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        role_ids=[role.id for role in user.roles],
        roles=sorted(access.roles),
        permissions=sorted(access.permissions),
        project_ids=sorted(access.project_ids),
        center_ids=sorted(access.center_ids),
        created_at=user.created_at,
        updated_at=user.updated_at,
        is_admin=access.is_admin,
    )


def get_user_for_login(db: Session, username: str) -> User | None:
    return db.scalar(
        select(User)
        .where(User.username == username)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.project_scopes),
            selectinload(User.center_scopes),
        )
    )


@router.post("/login", response_model=TokenRead)
def login(payload: LoginRequest, db: DBSession) -> TokenRead:
    user = get_user_for_login(db, payload.username)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return TokenRead(access_token=create_access_token(str(user.id)))


@router.post("/logout")
def logout(_: CurrentUser) -> dict[str, str]:
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUserRead)
def me(current_user: CurrentUser) -> CurrentUserRead:
    return serialize_current_user(current_user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict[str, str]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is wrong",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()
    return {"status": "ok"}
