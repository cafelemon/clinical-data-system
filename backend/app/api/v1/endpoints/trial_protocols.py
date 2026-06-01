from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.config import settings
from app.core.database import get_db
from app.core.files import ensure_relative_path
from app.models import Project, TrialProtocolVersion
from app.schemas import (
    TrialProtocolApplyResult,
    TrialProtocolDraft,
    TrialProtocolVersionRead,
    TrialProtocolVersionSummary,
)
from app.services.audit import record_operation
from app.services.trial_protocols import (
    TrialProtocolError,
    apply_protocol_draft,
    next_protocol_version_number,
    parse_protocol_file,
    write_protocol_upload,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
ProtocolReadAccess = Annotated[AccessContext, Depends(require_permission("master_data:read"))]
ProtocolUpload = Annotated[UploadFile, File(...)]


def get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


def ensure_project_read(access: AccessContext, project_id: int) -> None:
    if not access.can_access_project(project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def ensure_protocol_write(access: AccessContext, project_id: int) -> None:
    if access.is_admin:
        return
    if "project_manager" in access.roles and project_id in access.project_ids:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project scope denied")


def get_protocol_version_or_404(
    db: Session,
    project_id: int,
    version_id: int,
) -> TrialProtocolVersion:
    version = db.get(TrialProtocolVersion, version_id)
    if version is None or version.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="trial protocol version not found",
        )
    return version


@router.get(
    "/projects/{project_id}/protocol-versions",
    response_model=list[TrialProtocolVersionSummary],
)
def list_protocol_versions(
    project_id: int,
    db: DBSession,
    access: ProtocolReadAccess,
) -> list[TrialProtocolVersion]:
    get_project_or_404(db, project_id)
    ensure_project_read(access, project_id)
    return list(
        db.scalars(
            select(TrialProtocolVersion)
            .where(TrialProtocolVersion.project_id == project_id)
            .order_by(TrialProtocolVersion.version_number.desc(), TrialProtocolVersion.id.desc())
        )
    )


@router.post(
    "/projects/{project_id}/protocol-versions",
    response_model=TrialProtocolVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_protocol_version(
    project_id: int,
    db: DBSession,
    access: ProtocolReadAccess,
    request: Request,
    file: ProtocolUpload,
) -> TrialProtocolVersion:
    project = get_project_or_404(db, project_id)
    ensure_protocol_write(access, project_id)
    version_number = next_protocol_version_number(db, project_id)
    stored = write_protocol_upload(project, file, version_number)
    storage_path = ensure_relative_path(settings.file_storage_root, stored.storage_path)
    draft: dict = {"visits": [], "centers": [], "deactivate_missing": {}}
    page_count = 0
    protocol_no = None
    protocol_version = None
    protocol_date = None
    parsing_status = "parsed"
    try:
        page_count, draft, protocol_no, protocol_version, protocol_date = parse_protocol_file(
            storage_path
        )
    except TrialProtocolError as exc:
        parsing_status = "parse_failed"
        draft = {
            "visits": [],
            "centers": [],
            "deactivate_missing": {"visits": False, "items": False, "centers": False},
            "error": str(exc),
        }

    version = TrialProtocolVersion(
        project_id=project_id,
        version_number=version_number,
        original_name=stored.original_name,
        storage_path=stored.storage_path,
        file_hash=stored.file_hash,
        file_size=stored.file_size,
        page_count=page_count,
        parsing_status=parsing_status,
        protocol_no=protocol_no,
        protocol_version=protocol_version,
        protocol_date=protocol_date,
        draft_json=draft,
        uploaded_by=access.user.id,
    )
    db.add(version)
    try:
        db.flush()
        record_operation(
            db,
            action="trial_protocol.upload",
            request=request,
            access=access,
            target_type="trial_protocol_version",
            target_id=version.id,
            project_id=project_id,
            detail={
                "version_number": version_number,
                "original_name": stored.original_name,
                "parsing_status": parsing_status,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        Path(storage_path).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="trial protocol version already exists",
        ) from exc
    db.refresh(version)
    return version


@router.get(
    "/projects/{project_id}/protocol-versions/{version_id}",
    response_model=TrialProtocolVersionRead,
)
def get_protocol_version(
    project_id: int,
    version_id: int,
    db: DBSession,
    access: ProtocolReadAccess,
) -> TrialProtocolVersion:
    get_project_or_404(db, project_id)
    ensure_project_read(access, project_id)
    return get_protocol_version_or_404(db, project_id, version_id)


@router.patch(
    "/projects/{project_id}/protocol-versions/{version_id}/draft",
    response_model=TrialProtocolVersionRead,
)
def update_protocol_draft(
    project_id: int,
    version_id: int,
    payload: TrialProtocolDraft,
    db: DBSession,
    access: ProtocolReadAccess,
    request: Request,
) -> TrialProtocolVersion:
    get_project_or_404(db, project_id)
    ensure_protocol_write(access, project_id)
    version = get_protocol_version_or_404(db, project_id, version_id)
    version.draft_json = payload.model_dump(mode="json")
    if version.parsing_status == "parsed":
        version.parsing_status = "draft_edited"
    record_operation(
        db,
        action="trial_protocol.draft_update",
        request=request,
        access=access,
        target_type="trial_protocol_version",
        target_id=version.id,
        project_id=project_id,
        detail={"version_number": version.version_number},
    )
    db.commit()
    db.refresh(version)
    return version


@router.post(
    "/projects/{project_id}/protocol-versions/{version_id}/apply",
    response_model=TrialProtocolApplyResult,
)
def apply_protocol_version(
    project_id: int,
    version_id: int,
    db: DBSession,
    access: ProtocolReadAccess,
    request: Request,
) -> TrialProtocolApplyResult:
    project = get_project_or_404(db, project_id)
    ensure_protocol_write(access, project_id)
    version = get_protocol_version_or_404(db, project_id, version_id)
    try:
        result = apply_protocol_draft(db, project, version.draft_json)
    except TrialProtocolError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    version.apply_result_json = result
    version.applied_by = access.user.id
    version.applied_at = datetime.now(UTC)
    version.parsing_status = "applied"
    record_operation(
        db,
        action="trial_protocol.apply",
        request=request,
        access=access,
        target_type="trial_protocol_version",
        target_id=version.id,
        project_id=project_id,
        detail={"version_number": version.version_number, **result},
    )
    db.commit()
    db.refresh(version)
    return TrialProtocolApplyResult(
        version=TrialProtocolVersionRead.model_validate(version),
        result=result,
    )
