from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import PERMISSIONS, ROLE_SPECS
from app.core.security import get_password_hash
from app.models import Permission, Role, User


def bootstrap_identity(db: Session) -> None:
    permissions_by_code: dict[str, Permission] = {}
    for spec in PERMISSIONS:
        permission = db.scalar(select(Permission).where(Permission.code == spec.code))
        if permission is None:
            permission = Permission(
                code=spec.code,
                label=spec.label,
                module=spec.module,
                description=spec.description,
            )
            db.add(permission)
            db.flush()
        else:
            permission.label = spec.label
            permission.module = spec.module
            permission.description = spec.description
        permissions_by_code[permission.code] = permission

    roles_by_name: dict[str, Role] = {}
    for name, spec in ROLE_SPECS.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(
                name=name,
                label=spec["label"],
                description=spec["description"],
                system=True,
            )
            db.add(role)
            db.flush()
        else:
            role.label = spec["label"]
            role.description = spec["description"]
            role.system = True
        if not role.permissions:
            role.permissions = [permissions_by_code[code] for code in spec["permissions"]]
        roles_by_name[name] = role

    admin = db.scalar(select(User).where(User.username == settings.initial_admin_username))
    if admin is None:
        admin = User(
            username=settings.initial_admin_username,
            full_name=settings.initial_admin_full_name,
            email=settings.initial_admin_email or None,
            hashed_password=get_password_hash(settings.initial_admin_password),
            is_active=True,
        )
        db.add(admin)
        db.flush()
    admin.roles = [roles_by_name["admin"]]
    db.commit()


def try_bootstrap_identity(db: Session) -> None:
    try:
        bootstrap_identity(db)
    except SQLAlchemyError:
        db.rollback()
