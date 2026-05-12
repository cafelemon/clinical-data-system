from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PdfAnnotation(Base):
    __tablename__ = "pdf_annotations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    file_version_id: Mapped[int] = mapped_column(
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    center_id: Mapped[int] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"),
        index=True,
    )
    subject_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_items.id", ondelete="SET NULL"),
        index=True,
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    resolved_at = mapped_column(DateTime(timezone=True))
    deleted_at = mapped_column(DateTime(timezone=True))

    file_asset = relationship("FileAsset", foreign_keys=[file_id])
    file_version = relationship("FileVersion", foreign_keys=[file_version_id])


class CorrectionTask(Base):
    __tablename__ = "correction_tasks"
    __table_args__ = (
        Index(
            "uq_correction_tasks_one_active_per_file",
            "file_id",
            unique=True,
            postgresql_where=text("status NOT IN ('closed', 'cancelled')"),
            sqlite_where=text("status NOT IN ('closed', 'cancelled')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_no: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    center_id: Mapped[int] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"),
        index=True,
    )
    subject_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_items.id", ondelete="SET NULL"),
        index=True,
    )
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_file_version_id: Mapped[int] = mapped_column(
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    latest_file_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_versions.id", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    previous_upload_status: Mapped[str | None] = mapped_column(String(30))
    previous_review_status: Mapped[str | None] = mapped_column(String(30))
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    due_date = mapped_column(Date)
    submitted_at = mapped_column(DateTime(timezone=True))
    reviewed_at = mapped_column(DateTime(timezone=True))
    closed_at = mapped_column(DateTime(timezone=True))
    submission_remark: Mapped[str | None] = mapped_column(Text)
    review_comment: Mapped[str | None] = mapped_column(Text)
    review_result: Mapped[str | None] = mapped_column(String(30))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    file_asset = relationship("FileAsset", foreign_keys=[file_id])
    source_file_version = relationship("FileVersion", foreign_keys=[source_file_version_id])
    latest_file_version = relationship("FileVersion", foreign_keys=[latest_file_version_id])
    task_annotations = relationship(
        "CorrectionTaskAnnotation",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="CorrectionTaskAnnotation.id",
    )


class CorrectionTaskAnnotation(Base):
    __tablename__ = "correction_task_annotations"
    __table_args__ = (
        UniqueConstraint("task_id", "annotation_id", name="uq_correction_task_annotation"),
        UniqueConstraint(
            "annotation_id",
            name="uq_correction_task_annotation_annotation",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("correction_tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    annotation_id: Mapped[int] = mapped_column(
        ForeignKey("pdf_annotations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task = relationship("CorrectionTask", back_populates="task_annotations")
    annotation = relationship("PdfAnnotation")
