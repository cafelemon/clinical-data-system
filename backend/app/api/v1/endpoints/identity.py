from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DBSession, require_permission
from app.core.security import get_password_hash
from app.models import Center, Permission, Project, Role, User
from app.schemas import (
    PermissionRead,
    RoleCreate,
    RoleRead,
    RoleUpdate,
    UserCreate,
    UserRead,
    UserUpdate,
)

router = APIRouter()
UsersRead = Depends(require_permission("users:read"))
UsersWrite = Depends(require_permission("users:write"))
RolesRead = Depends(require_permission("roles:read"))
RolesWrite = Depends(require_permission("roles:write"))
PermissionsRead = Depends(require_permission("permissions:read"))


def commit_or_conflict(db: DBSession, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


def load_roles(db: DBSession, role_ids: list[int]) -> list[Role]:
    if not role_ids:
        return []
    roles = list(db.scalars(select(Role).where(Role.id.in_(set(role_ids)))))
    if len(roles) != len(set(role_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid role_ids")
    return roles


def load_permissions(db: DBSession, permission_ids: list[int]) -> list[Permission]:
    if not permission_ids:
        return []
    permissions = list(db.scalars(select(Permission).where(Permission.id.in_(set(permission_ids)))))
    if len(permissions) != len(set(permission_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid permission_ids",
        )
    return permissions


def load_projects(db: DBSession, project_ids: list[int]) -> list[Project]:
    if not project_ids:
        return []
    projects = list(db.scalars(select(Project).where(Project.id.in_(set(project_ids)))))
    if len(projects) != len(set(project_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid project_ids")
    return projects


def load_centers(db: DBSession, center_ids: list[int]) -> list[Center]:
    if not center_ids:
        return []
    centers = list(db.scalars(select(Center).where(Center.id.in_(set(center_ids)))))
    if len(centers) != len(set(center_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid center_ids")
    return centers


def get_user_or_404(db: DBSession, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


def get_role_or_404(db: DBSession, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="role not found")
    return role


def serialize_user(user: User) -> UserRead:
    permissions = {
        permission.code
        for role in user.roles
        for permission in role.permissions
    }
    return UserRead(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        role_ids=[role.id for role in user.roles],
        roles=[role.name for role in user.roles],
        permissions=sorted(permissions),
        project_ids=[project.id for project in user.project_scopes],
        center_ids=[center.id for center in user.center_scopes],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def serialize_role(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        label=role.label,
        description=role.description,
        system=role.system,
        permission_ids=[permission.id for permission in role.permissions],
        permissions=[permission.code for permission in role.permissions],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/users", response_model=list[UserRead], dependencies=[UsersRead])
def list_users(db: DBSession) -> list[UserRead]:
    users = db.scalars(
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.project_scopes),
            selectinload(User.center_scopes),
        )
        .order_by(User.id)
    )
    return [serialize_user(user) for user in users]


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[UsersWrite],
)
def create_user(payload: UserCreate, db: DBSession) -> UserRead:
    user = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        is_active=payload.is_active,
    )
    user.roles = load_roles(db, payload.role_ids)
    user.project_scopes = load_projects(db, payload.project_ids)
    user.center_scopes = load_centers(db, payload.center_ids)
    db.add(user)
    commit_or_conflict(db, "username or email already exists")
    db.refresh(user)
    return serialize_user(get_user_or_404(db, user.id))


@router.put("/users/{user_id}", response_model=UserRead, dependencies=[UsersWrite])
def update_user(user_id: int, payload: UserUpdate, db: DBSession) -> UserRead:
    user = get_user_or_404(db, user_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    if "email" in update_data:
        user.email = update_data["email"]
    if "is_active" in update_data:
        user.is_active = update_data["is_active"]
    if update_data.get("password"):
        user.hashed_password = get_password_hash(update_data["password"])
    if "role_ids" in update_data:
        user.roles = load_roles(db, update_data["role_ids"])
    if "project_ids" in update_data:
        user.project_scopes = load_projects(db, update_data["project_ids"])
    if "center_ids" in update_data:
        user.center_scopes = load_centers(db, update_data["center_ids"])
    commit_or_conflict(db, "username or email already exists")
    db.refresh(user)
    return serialize_user(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[UsersWrite],
)
def delete_user(user_id: int, current_user: CurrentUser, db: DBSession) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cannot delete yourself",
        )
    user = get_user_or_404(db, user_id)
    db.delete(user)
    db.commit()


@router.get("/roles", response_model=list[RoleRead], dependencies=[RolesRead])
def list_roles(db: DBSession) -> list[RoleRead]:
    roles = db.scalars(select(Role).options(selectinload(Role.permissions)).order_by(Role.id))
    return [serialize_role(role) for role in roles]


@router.post(
    "/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RolesWrite],
)
def create_role(payload: RoleCreate, db: DBSession) -> RoleRead:
    role = Role(
        name=payload.name,
        label=payload.label,
        description=payload.description,
        system=False,
    )
    role.permissions = load_permissions(db, payload.permission_ids)
    db.add(role)
    commit_or_conflict(db, "role name already exists")
    db.refresh(role)
    return serialize_role(role)


@router.put("/roles/{role_id}", response_model=RoleRead, dependencies=[RolesWrite])
def update_role(role_id: int, payload: RoleUpdate, db: DBSession) -> RoleRead:
    role = get_role_or_404(db, role_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "label" in update_data:
        role.label = update_data["label"]
    if "description" in update_data:
        role.description = update_data["description"]
    if "permission_ids" in update_data:
        role.permissions = load_permissions(db, update_data["permission_ids"])
    commit_or_conflict(db, "role update failed")
    db.refresh(role)
    return serialize_role(role)


@router.get("/permissions", response_model=list[PermissionRead], dependencies=[PermissionsRead])
def list_permissions(db: DBSession) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.id)))
