from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.database import get_db
from app.models import Center, OperationLog, Project
from app.schemas import OperationLogListRead

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
OperationLogsReadAccess = Annotated[
    AccessContext,
    Depends(require_permission("operation_logs:read")),
]


def ensure_project_access(db: Session, access: AccessContext, project_id: int) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_center_access(
    db: Session,
    access: AccessContext,
    center_id: int,
    project_id: int | None = None,
) -> None:
    center = db.get(Center, center_id)
    if center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="center not found")
    if project_id is not None and center.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="center does not belong to project",
        )
    if not access.can_access_center(center.id, center.project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def apply_scope(statement: Select, access: AccessContext) -> Select:
    if access.is_admin:
        return statement
    if access.project_ids:
        return statement.where(OperationLog.project_id.in_(access.project_ids))
    if access.center_ids:
        return statement.where(OperationLog.center_id.in_(access.center_ids))
    return statement.where(OperationLog.id == -1)


@router.get("/operation-logs", response_model=OperationLogListRead)
def list_operation_logs(
    db: DBSession,
    access: OperationLogsReadAccess,
    user_id: int | None = None,
    username: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    project_id: int | None = None,
    center_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OperationLogListRead:
    if project_id is not None:
        ensure_project_access(db, access, project_id)
    if center_id is not None:
        ensure_center_access(db, access, center_id, project_id)

    statement = select(OperationLog)
    if user_id is not None:
        statement = statement.where(OperationLog.user_id == user_id)
    if username:
        statement = statement.where(OperationLog.username.ilike(f"%{username}%"))
    if action:
        statement = statement.where(OperationLog.action.ilike(f"%{action}%"))
    if target_type:
        statement = statement.where(OperationLog.target_type == target_type)
    if target_id is not None:
        statement = statement.where(OperationLog.target_id == target_id)
    if project_id is not None:
        statement = statement.where(OperationLog.project_id == project_id)
    if center_id is not None:
        statement = statement.where(OperationLog.center_id == center_id)
    if created_from is not None:
        statement = statement.where(OperationLog.created_at >= created_from)
    if created_to is not None:
        statement = statement.where(OperationLog.created_at <= created_to)
    statement = apply_scope(statement, access)

    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items = list(
        db.scalars(
            statement.order_by(OperationLog.created_at.desc(), OperationLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return OperationLogListRead(items=items, total=total, limit=limit, offset=offset)
