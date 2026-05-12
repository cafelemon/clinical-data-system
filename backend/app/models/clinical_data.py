from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.clinical_data import (
    DEFAULT_DATA_STATUS,
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
)
from app.core.database import Base


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "screening_no",
            name="uq_subjects_project_center_screening_no",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
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
    screening_no: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    subject_arm: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(30))
    age: Mapped[int | None] = mapped_column(Integer)
    enrolled_at: Mapped[date | None] = mapped_column(Date)
    informed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    visit1_date: Mapped[date | None] = mapped_column(Date)
    visit2_date: Mapped[date | None] = mapped_column(Date)
    visit3_date: Mapped[date | None] = mapped_column(Date)
    visit4_date: Mapped[date | None] = mapped_column(Date)
    visit5_date: Mapped[date | None] = mapped_column(Date)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    review_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_REVIEW_STATUS,
        nullable=False,
    )
    data_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_DATA_STATUS,
        nullable=False,
    )
    completed_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="subjects")
    center = relationship("Center", back_populates="subjects")
    sections = relationship(
        "SubjectSection",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="SubjectSection.sort_order",
    )
    items = relationship(
        "SubjectItem",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="SubjectItem.sort_order",
    )
    file_assets = relationship("FileAsset", back_populates="subject", cascade="all, delete-orphan")
    pdf_packets = relationship("PdfPacket", back_populates="subject", cascade="all, delete-orphan")


class SubjectSection(Base):
    __tablename__ = "subject_sections"
    __table_args__ = (
        UniqueConstraint("subject_id", "section_code", name="uq_subject_sections_subject_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="SET NULL"),
        index=True,
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    visit_name: Mapped[str | None] = mapped_column(String(100))
    time_window: Mapped[str | None] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    subject = relationship("Subject", back_populates="sections")
    items = relationship(
        "SubjectItem",
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="SubjectItem.sort_order",
    )


class SubjectItem(Base):
    __tablename__ = "subject_items"
    __table_args__ = (
        UniqueConstraint("subject_id", "item_code", name="uq_subject_items_subject_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("subject_sections.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("stage_templates.id", ondelete="SET NULL"),
        index=True,
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    item_code: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    upload_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_UPLOAD_STATUS,
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_REVIEW_STATUS,
        nullable=False,
    )
    remark: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    subject = relationship("Subject", back_populates="items")
    section = relationship("SubjectSection", back_populates="items")
    file_assets = relationship(
        "FileAsset",
        back_populates="subject_item",
        cascade="all, delete-orphan",
    )


class StageFile(Base):
    __tablename__ = "stage_files"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "stage_id",
            "stage_template_id",
            name="uq_stage_files_template_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
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
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("stage_templates.id", ondelete="CASCADE"),
        index=True,
    )
    file_name: Mapped[str] = mapped_column(String(150), nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(80))
    upload_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_UPLOAD_STATUS,
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(30),
        default=DEFAULT_REVIEW_STATUS,
        nullable=False,
    )
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    added_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    remark: Mapped[str | None] = mapped_column(Text)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="stage_files")
    center = relationship("Center", back_populates="stage_files")
    stage = relationship("Stage", back_populates="stage_files")
    stage_template = relationship("StageTemplate", back_populates="stage_files")
    file_assets = relationship(
        "FileAsset",
        back_populates="stage_file",
        cascade="all, delete-orphan",
    )
