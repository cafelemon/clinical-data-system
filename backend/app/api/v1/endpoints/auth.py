from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import CurrentUser, DBSession, build_access_context
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import Role, User
from app.schemas import ChangePasswordRequest, CurrentUserRead, LoginRequest, TokenRead
from app.services.audit import record_operation

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
def login(payload: LoginRequest, db: DBSession, request: Request) -> TokenRead:
    user = get_user_for_login(db, payload.username)
    if user is None or not verify_password(payload.password, user.hashed_password):
        record_operation(
            db,
            action="auth.login_failed",
            request=request,
            username=payload.username,
            target_type="auth",
            detail={"reason": "invalid_credentials"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        record_operation(
            db,
            action="auth.login_failed",
            request=request,
            user=user,
            target_type="auth",
            detail={"reason": "disabled"},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    record_operation(
        db,
        action="auth.login",
        request=request,
        user=user,
        target_type="auth",
        detail={"status": "success"},
    )
    db.commit()
    return TokenRead(access_token=create_access_token(str(user.id)))


@router.post("/logout")
def logout(current_user: CurrentUser, db: DBSession, request: Request) -> dict[str, str]:
    record_operation(
        db,
        action="auth.logout",
        request=request,
        user=current_user,
        target_type="auth",
    )
    db.commit()
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUserRead)
def me(current_user: CurrentUser) -> CurrentUserRead:
    return serialize_current_user(current_user)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> dict[str, str]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is wrong",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    record_operation(
        db,
        action="auth.change_password",
        request=request,
        user=current_user,
        target_type="user",
        target_id=current_user.id,
        detail={"changed_fields": ["password"]},
    )
    db.commit()
    return {"status": "ok"}
