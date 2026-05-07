from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import AccessContext, require_permission
from app.core.database import get_db
from app.schemas import ExcelImportResultRead
from app.services.audit import record_operation
from app.services.excel_io import (
    XLSX_MEDIA_TYPE,
    build_center_status_export,
    build_missing_items_export,
    build_project_progress_export,
    build_subject_completeness_export,
    build_template_workbook,
    import_excel,
)

router = APIRouter()
DBSession = Annotated[Session, Depends(get_db)]
ImportReadAccess = Annotated[AccessContext, Depends(require_permission("imports:read"))]
ImportWriteAccess = Annotated[AccessContext, Depends(require_permission("imports:write"))]
ExportReadAccess = Annotated[AccessContext, Depends(require_permission("exports:read"))]


def excel_response(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def read_xlsx_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are supported",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    return content


def ensure_admin_import(access: AccessContext) -> None:
    if not access.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can import master data",
        )


@router.get("/import/templates/{kind}")
def download_import_template(kind: str, _: ImportReadAccess) -> Response:
    return excel_response(build_template_workbook(kind), f"{kind}-template.xlsx")


@router.post("/import/projects", response_model=ExcelImportResultRead)
async def import_projects(
    db: DBSession,
    access: ImportWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ExcelImportResultRead:
    ensure_admin_import(access)
    result = import_excel(db, access, "projects", await read_xlsx_upload(file))
    record_excel_import(db, access, request, "projects", result)
    db.commit()
    return result


@router.post("/import/centers", response_model=ExcelImportResultRead)
async def import_centers(
    db: DBSession,
    access: ImportWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ExcelImportResultRead:
    ensure_admin_import(access)
    result = import_excel(db, access, "centers", await read_xlsx_upload(file))
    record_excel_import(db, access, request, "centers", result)
    db.commit()
    return result


@router.post("/import/subjects", response_model=ExcelImportResultRead)
async def import_subjects(
    db: DBSession,
    access: ImportWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ExcelImportResultRead:
    result = import_excel(db, access, "subjects", await read_xlsx_upload(file))
    record_excel_import(db, access, request, "subjects", result)
    db.commit()
    return result


@router.post("/import/stage-templates", response_model=ExcelImportResultRead)
async def import_stage_templates(
    db: DBSession,
    access: ImportWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> ExcelImportResultRead:
    ensure_admin_import(access)
    result = import_excel(db, access, "stage-templates", await read_xlsx_upload(file))
    record_excel_import(db, access, request, "stage-templates", result)
    db.commit()
    return result


@router.get("/export/project-progress")
def export_project_progress(
    db: DBSession,
    access: ExportReadAccess,
    request: Request,
    project_id: int | None = None,
) -> Response:
    content = build_project_progress_export(db, access, project_id)
    record_excel_export(db, access, request, "project-progress", project_id=project_id)
    db.commit()
    return excel_response(content, "project-progress.xlsx")


@router.get("/export/center-status")
def export_center_status(
    db: DBSession,
    access: ExportReadAccess,
    request: Request,
    project_id: int | None = None,
    center_id: int | None = None,
) -> Response:
    content = build_center_status_export(db, access, project_id, center_id)
    record_excel_export(
        db, access, request, "center-status", project_id=project_id, center_id=center_id
    )
    db.commit()
    return excel_response(content, "center-status.xlsx")


@router.get("/export/subject-completeness")
def export_subject_completeness(
    db: DBSession,
    access: ExportReadAccess,
    request: Request,
    project_id: int | None = None,
    center_id: int | None = None,
) -> Response:
    content = build_subject_completeness_export(db, access, project_id, center_id)
    record_excel_export(
        db, access, request, "subject-completeness", project_id=project_id, center_id=center_id
    )
    db.commit()
    return excel_response(content, "subject-completeness.xlsx")


@router.get("/export/missing-items")
def export_missing_items(
    db: DBSession,
    access: ExportReadAccess,
    request: Request,
    project_id: int | None = None,
    center_id: int | None = None,
) -> Response:
    content = build_missing_items_export(db, access, project_id, center_id)
    record_excel_export(
        db, access, request, "missing-items", project_id=project_id, center_id=center_id
    )
    db.commit()
    return excel_response(content, "missing-items.xlsx")


def record_excel_import(
    db: Session,
    access: AccessContext,
    request: Request,
    kind: str,
    result: ExcelImportResultRead,
) -> None:
    record_operation(
        db,
        action="excel.import",
        request=request,
        access=access,
        target_type="excel_import",
        detail={
            "kind": kind,
            "total_rows": result.total_rows,
            "created_count": result.created_count,
            "updated_count": result.updated_count,
            "error_count": len(result.errors),
        },
    )


def record_excel_export(
    db: Session,
    access: AccessContext,
    request: Request,
    kind: str,
    project_id: int | None = None,
    center_id: int | None = None,
) -> None:
    record_operation(
        db,
        action="excel.export",
        request=request,
        access=access,
        target_type="excel_export",
        project_id=project_id,
        center_id=center_id,
        detail={"kind": kind},
    )
