from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
DBSession = Annotated[Session, Depends(get_db)]
Token = Annotated[str, Depends(oauth2_scheme)]


@dataclass(frozen=True)
class AccessContext:
    user: User
    roles: set[str]
    permissions: set[str]
    project_ids: set[int]
    center_ids: set[int]
    center_project_ids: set[int]

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    def has_permission(self, code: str) -> bool:
        return self.is_admin or code in self.permissions

    def can_access_project(self, project_id: int) -> bool:
        return (
            self.is_admin
            or project_id in self.project_ids
            or project_id in self.center_project_ids
        )

    def can_access_center(self, center_id: int, project_id: int) -> bool:
        return self.is_admin or center_id in self.center_ids or self.can_access_project(project_id)


def build_access_context(user: User) -> AccessContext:
    roles = {role.name for role in user.roles}
    permissions = {
        permission.code
        for role in user.roles
        for permission in role.permissions
    }
    project_ids = {project.id for project in user.project_scopes}
    center_ids = {center.id for center in user.center_scopes}
    center_project_ids = {center.project_id for center in user.center_scopes}
    return AccessContext(
        user=user,
        roles=roles,
        permissions=permissions,
        project_ids=project_ids,
        center_ids=center_ids,
        center_project_ids=center_project_ids,
    )


def get_current_user(db: DBSession, token: Token) -> User:
    subject = decode_access_token(token)
    try:
        user_id = int(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.project_scopes),
            selectinload(User.center_scopes),
        )
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or missing user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_access_context(current_user: Annotated[User, Depends(get_current_user)]) -> AccessContext:
    return build_access_context(current_user)


def require_permission(permission_code: str) -> Callable[[AccessContext], AccessContext]:
    def dependency(access: Annotated[AccessContext, Depends(get_access_context)]) -> AccessContext:
        if not access.has_permission(permission_code):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return access

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAccess = Annotated[AccessContext, Depends(get_access_context)]
