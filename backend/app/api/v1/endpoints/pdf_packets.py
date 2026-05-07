from pathlib import Path
from typing import Annotated, TypeVar
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from app.api.deps import AccessContext, require_permission
from app.core.clinical_data import DEFAULT_REVIEW_STATUS, UPLOAD_UPLOADED
from app.core.config import settings
from app.core.database import get_db
from app.core.files import ensure_relative_path
from app.models import (
    Center,
    FileAsset,
    FileVersion,
    PdfPacket,
    PdfPacketSegment,
    Project,
    Subject,
    SubjectItem,
)
from app.schemas import (
    PdfPacketRead,
    PdfPacketSegmentCreate,
    PdfPacketSegmentRead,
    PdfPacketSegmentUpdate,
    PdfPacketSegmentUpload,
    PdfPacketSegmentUploadRead,
)
from app.services.audit import record_operation
from app.services.clinical_status import recalculate_subject_status
from app.services.pdf_packets import (
    PdfPacketError,
    analyze_packet,
    derived_relative_directory,
    extract_pdf_pages,
    hash_file,
    packet_relative_directory,
    pdf_page_count,
    remove_packet_physical_file,
    write_upload_file,
)

router = APIRouter()
ModelT = TypeVar("ModelT", Project, Center, Subject, SubjectItem, PdfPacket, PdfPacketSegment)
DBSession = Annotated[Session, Depends(get_db)]
PacketReadAccess = Annotated[AccessContext, Depends(require_permission("pdf_packets:read"))]
PacketWriteAccess = Annotated[AccessContext, Depends(require_permission("pdf_packets:write"))]
PacketDeleteAccess = Annotated[AccessContext, Depends(require_permission("pdf_packets:delete"))]


def get_or_404(db: Session, model: type[ModelT], item_id: int, label: str) -> ModelT:
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return item


def ensure_center_scope(access: AccessContext, project_id: int, center_id: int) -> None:
    if not access.can_access_center(center_id, project_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Center scope denied")


def ensure_packet_scope(access: AccessContext, packet: PdfPacket) -> None:
    ensure_center_scope(access, packet.project_id, packet.center_id)


def ensure_subject_matches_scope(subject: Subject, project_id: int, center_id: int) -> None:
    if subject.project_id != project_id or subject.center_id != center_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subject does not belong to selected project center",
        )


def ensure_item_matches_packet(subject_item: SubjectItem, packet: PdfPacket) -> Subject:
    subject = get_or_404_for_session(subject_item, packet)
    if subject.id != packet.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subject item does not belong to packet subject",
        )
    return subject


def get_or_404_for_session(subject_item: SubjectItem, packet: PdfPacket) -> Subject:
    subject = subject_item.subject
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="subject not found")
    if subject.project_id != packet.project_id or subject.center_id != packet.center_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subject item scope does not match packet",
        )
    return subject


def response_packet(packet: PdfPacket) -> PdfPacket:
    packet.segment_count = len(packet.segments)
    return packet


def validate_packet_page_range(packet: PdfPacket, page_start: int, page_end: int) -> None:
    if page_end < page_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_end must be greater than or equal to page_start",
        )
    if packet.page_count and page_end > packet.page_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page range exceeds packet page count",
        )


def packet_query(access: AccessContext):
    statement = select(PdfPacket).order_by(PdfPacket.uploaded_at.desc(), PdfPacket.id.desc())
    if access.is_admin:
        return statement
    conditions = []
    if access.project_ids:
        conditions.append(PdfPacket.project_id.in_(access.project_ids))
    if access.center_ids:
        conditions.append(PdfPacket.center_id.in_(access.center_ids))
    if not conditions:
        statement = statement.where(PdfPacket.id == -1)
    else:
        statement = statement.where(or_(*conditions))
    return statement


@router.get("/pdf-packets", response_model=list[PdfPacketRead])
def list_pdf_packets(
    db: DBSession,
    access: PacketReadAccess,
    project_id: int | None = None,
    center_id: int | None = None,
    subject_id: int | None = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[PdfPacket]:
    statement = packet_query(access)
    if project_id is not None:
        statement = statement.where(PdfPacket.project_id == project_id)
    if center_id is not None:
        statement = statement.where(PdfPacket.center_id == center_id)
    if subject_id is not None:
        statement = statement.where(PdfPacket.subject_id == subject_id)
    if status_filter is not None:
        statement = statement.where(PdfPacket.status == status_filter)
    packets = list(db.scalars(statement))
    for packet in packets:
        ensure_packet_scope(access, packet)
        response_packet(packet)
    return packets


@router.post(
    "/pdf-packets/upload",
    response_model=PdfPacketRead,
    status_code=status.HTTP_201_CREATED,
)
def upload_pdf_packet(
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
    file: Annotated[UploadFile, File()],
    project_id: Annotated[int, Form()],
    center_id: Annotated[int, Form()],
    subject_id: Annotated[int, Form()],
) -> PdfPacket:
    project = get_or_404(db, Project, project_id, "project")
    center = get_or_404(db, Center, center_id, "center")
    if center.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="center does not belong to project",
        )
    ensure_center_scope(access, project.id, center.id)
    subject = get_or_404(db, Subject, subject_id, "subject")
    ensure_subject_matches_scope(subject, project.id, center.id)

    original_name = Path(file.filename or "packet.pdf").name
    if Path(original_name).suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF is supported")

    stored = write_upload_file(file, packet_relative_directory(project, center, subject))
    storage_path = ensure_relative_path(settings.file_storage_root, stored.storage_path)
    try:
        page_count = pdf_page_count(storage_path)
    except PdfPacketError as exc:
        storage_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid PDF: {exc}",
        ) from exc

    packet = PdfPacket(
        packet_id=str(uuid4()),
        original_name=stored.original_name,
        stored_name=stored.stored_name,
        file_ext=stored.file_ext,
        mime_type=stored.mime_type,
        file_size=stored.file_size,
        file_hash=stored.file_hash,
        storage_path=stored.storage_path,
        storage_type="local",
        project_id=project.id,
        center_id=center.id,
        subject_id=subject.id,
        screening_no=subject.screening_no,
        filename_screening_no=Path(stored.original_name).stem or None,
        page_count=page_count,
        status="uploaded",
        uploaded_by=access.user.id,
    )
    db.add(packet)
    db.flush()
    analyze_packet(db, packet)
    record_operation(
        db,
        action="pdf_packet.upload",
        request=request,
        access=access,
        target_type="pdf_packet",
        target_id=packet.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={
            "original_name": packet.original_name,
            "subject_id": packet.subject_id,
            "screening_no": packet.screening_no,
            "page_count": packet.page_count,
        },
    )
    db.commit()
    db.refresh(packet)
    return response_packet(packet)


@router.get("/pdf-packets/{packet_id}", response_model=PdfPacketRead)
def get_pdf_packet(packet_id: int, db: DBSession, access: PacketReadAccess) -> PdfPacket:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    return response_packet(packet)


@router.post("/pdf-packets/{packet_id}/analyze", response_model=PdfPacketRead)
def analyze_pdf_packet(
    packet_id: int,
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
) -> PdfPacket:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    analyze_packet(db, packet)
    record_operation(
        db,
        action="pdf_packet.analyze",
        request=request,
        access=access,
        target_type="pdf_packet",
        target_id=packet.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={"page_count": packet.page_count, "status": packet.status},
    )
    db.commit()
    db.refresh(packet)
    return response_packet(packet)


@router.get("/pdf-packets/{packet_id}/preview")
def preview_pdf_packet(packet_id: int, db: DBSession, access: PacketReadAccess) -> FileResponse:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    path = ensure_relative_path(settings.file_storage_root, packet.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="packet file not found")
    return FileResponse(
        path,
        media_type=packet.mime_type,
        filename=packet.original_name,
        content_disposition_type="inline",
    )


@router.delete("/pdf-packets/{packet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdf_packet(
    packet_id: int,
    db: DBSession,
    access: PacketDeleteAccess,
    request: Request,
) -> None:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    uploaded_segment = db.scalar(
        select(PdfPacketSegment.id)
        .where(
            PdfPacketSegment.packet_id == packet.id,
            PdfPacketSegment.file_asset_id.is_not(None),
        )
        .limit(1)
    )
    if uploaded_segment is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="packet has uploaded segments and cannot be deleted",
        )
    record_operation(
        db,
        action="pdf_packet.delete",
        request=request,
        access=access,
        target_type="pdf_packet",
        target_id=packet.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={"original_name": packet.original_name, "screening_no": packet.screening_no},
    )
    remove_packet_physical_file(packet)
    db.delete(packet)
    db.commit()


@router.get("/pdf-packets/{packet_id}/segments", response_model=list[PdfPacketSegmentRead])
def list_pdf_packet_segments(
    packet_id: int,
    db: DBSession,
    access: PacketReadAccess,
) -> list[PdfPacketSegment]:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    return list(
        db.scalars(
            select(PdfPacketSegment)
            .where(PdfPacketSegment.packet_id == packet.id)
            .order_by(PdfPacketSegment.page_start, PdfPacketSegment.id)
        )
    )


@router.post(
    "/pdf-packets/{packet_id}/segments",
    response_model=PdfPacketSegmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_pdf_packet_segment(
    packet_id: int,
    payload: PdfPacketSegmentCreate,
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
) -> PdfPacketSegment:
    packet = get_or_404(db, PdfPacket, packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    validate_packet_page_range(packet, payload.page_start, payload.page_end)
    if payload.subject_item_id is not None:
        subject_item = get_or_404(db, SubjectItem, payload.subject_item_id, "subject item")
        ensure_item_matches_packet(subject_item, packet)
    if payload.suggested_subject_item_id is not None:
        suggested_item = get_or_404(
            db,
            SubjectItem,
            payload.suggested_subject_item_id,
            "suggested subject item",
        )
        ensure_item_matches_packet(suggested_item, packet)
    segment = PdfPacketSegment(packet_id=packet.id, status="pending", **payload.model_dump())
    db.add(segment)
    db.flush()
    record_operation(
        db,
        action="pdf_packet.segment_create",
        request=request,
        access=access,
        target_type="pdf_packet_segment",
        target_id=segment.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={
            "packet_id": packet.id,
            "page_start": segment.page_start,
            "page_end": segment.page_end,
        },
    )
    db.commit()
    db.refresh(segment)
    return segment


@router.put("/pdf-packet-segments/{segment_id}", response_model=PdfPacketSegmentRead)
def update_pdf_packet_segment(
    segment_id: int,
    payload: PdfPacketSegmentUpdate,
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
) -> PdfPacketSegment:
    segment = get_or_404(db, PdfPacketSegment, segment_id, "pdf packet segment")
    packet = get_or_404(db, PdfPacket, segment.packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    if segment.file_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploaded segment cannot be edited",
        )
    update_data = payload.model_dump(exclude_unset=True)
    next_start = update_data.get("page_start", segment.page_start)
    next_end = update_data.get("page_end", segment.page_end)
    validate_packet_page_range(packet, next_start, next_end)
    for field in ("subject_item_id", "suggested_subject_item_id"):
        if field in update_data and update_data[field] is not None:
            subject_item = get_or_404(db, SubjectItem, update_data[field], "subject item")
            ensure_item_matches_packet(subject_item, packet)
    for field, value in update_data.items():
        setattr(segment, field, value)
    record_operation(
        db,
        action="pdf_packet.segment_update",
        request=request,
        access=access,
        target_type="pdf_packet_segment",
        target_id=segment.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={"changed_fields": sorted(update_data), "packet_id": packet.id},
    )
    db.commit()
    db.refresh(segment)
    return segment


@router.delete("/pdf-packet-segments/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pdf_packet_segment(
    segment_id: int,
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
) -> None:
    segment = get_or_404(db, PdfPacketSegment, segment_id, "pdf packet segment")
    packet = get_or_404(db, PdfPacket, segment.packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    if segment.file_asset_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uploaded segment cannot be deleted",
        )
    record_operation(
        db,
        action="pdf_packet.segment_delete",
        request=request,
        access=access,
        target_type="pdf_packet_segment",
        target_id=segment.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={
            "packet_id": packet.id,
            "page_start": segment.page_start,
            "page_end": segment.page_end,
        },
    )
    db.delete(segment)
    db.commit()


@router.post(
    "/pdf-packet-segments/{segment_id}/upload",
    response_model=PdfPacketSegmentUploadRead,
)
def upload_pdf_packet_segment(
    segment_id: int,
    payload: PdfPacketSegmentUpload,
    db: DBSession,
    access: PacketWriteAccess,
    request: Request,
) -> PdfPacketSegmentUploadRead:
    segment = get_or_404(db, PdfPacketSegment, segment_id, "pdf packet segment")
    packet = get_or_404(db, PdfPacket, segment.packet_id, "pdf packet")
    ensure_packet_scope(access, packet)
    if segment.file_asset_id is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="segment already uploaded")
    validate_packet_page_range(packet, segment.page_start, segment.page_end)
    subject_item = get_or_404(db, SubjectItem, payload.subject_item_id, "subject item")
    subject = ensure_item_matches_packet(subject_item, packet)
    project = get_or_404(db, Project, packet.project_id, "project")
    center = get_or_404(db, Center, packet.center_id, "center")

    source_path = ensure_relative_path(settings.file_storage_root, packet.storage_path)
    if not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="packet file not found")

    original_name = (
        f"{packet.screening_no}_{subject_item.item_name}_p{segment.page_start}-{segment.page_end}.pdf"
    )
    stored_name = f"{uuid4().hex}.pdf"
    relative_path = derived_relative_directory(project, center, subject, subject_item) / stored_name
    target_path = ensure_relative_path(settings.file_storage_root, relative_path.as_posix())
    try:
        extract_pdf_pages(source_path, target_path, segment.page_start, segment.page_end)
    except PdfPacketError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    file_size, file_hash = hash_file(target_path)
    file_asset = FileAsset(
        file_id=str(uuid4()),
        original_name=original_name,
        stored_name=stored_name,
        file_ext="pdf",
        mime_type="application/pdf",
        file_size=file_size,
        file_hash=file_hash,
        storage_path=relative_path.as_posix(),
        storage_type="local",
        project_id=packet.project_id,
        center_id=packet.center_id,
        subject_id=packet.subject_id,
        subject_item_id=subject_item.id,
        file_category="clinical_document",
        version=1,
        uploaded_by=access.user.id,
        status="active",
        source_pdf_packet_id=packet.id,
        source_page_start=segment.page_start,
        source_page_end=segment.page_end,
    )
    db.add(file_asset)
    db.flush()
    db.add(
        FileVersion(
            file_id=file_asset.id,
            version=1,
            storage_path=file_asset.storage_path,
            file_hash=file_asset.file_hash,
            file_size=file_asset.file_size,
            mime_type=file_asset.mime_type,
            original_name=file_asset.original_name,
            stored_name=file_asset.stored_name,
            uploaded_by=access.user.id,
            change_note=f"PDF资料包拆解：p{segment.page_start}-{segment.page_end}",
        )
    )
    subject_item.upload_status = UPLOAD_UPLOADED
    subject_item.review_status = DEFAULT_REVIEW_STATUS
    recalculate_subject_status(db, subject)
    segment.subject_item_id = subject_item.id
    segment.file_asset_id = file_asset.id
    segment.status = "uploaded"
    record_operation(
        db,
        action="pdf_packet.segment_upload",
        request=request,
        access=access,
        target_type="pdf_packet_segment",
        target_id=segment.id,
        project_id=packet.project_id,
        center_id=packet.center_id,
        detail={
            "packet_id": packet.id,
            "subject_item_id": subject_item.id,
            "file_id": file_asset.id,
            "page_start": segment.page_start,
            "page_end": segment.page_end,
        },
    )
    db.commit()
    db.refresh(segment)
    db.refresh(file_asset)
    return PdfPacketSegmentUploadRead(segment=segment, file=file_asset)
