from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FileAsset(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_ext: Mapped[str | None] = mapped_column(String(30))
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    storage_type: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
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
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
    )
    stage_id: Mapped[int | None] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"),
        index=True,
    )
    stage_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("stage_files.id", ondelete="CASCADE"),
        index=True,
    )
    ssu_progress_id: Mapped[int | None] = mapped_column(
        ForeignKey("clinical_ssu_progress.id", ondelete="CASCADE"),
        index=True,
    )
    subject_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_items.id", ondelete="CASCADE"),
        index=True,
    )
    source_pdf_packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("pdf_packets.id", ondelete="SET NULL"),
        index=True,
    )
    source_page_start: Mapped[int | None] = mapped_column(Integer)
    source_page_end: Mapped[int | None] = mapped_column(Integer)
    file_category: Mapped[str] = mapped_column(String(50), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    project = relationship("Project", back_populates="file_assets")
    center = relationship("Center", back_populates="file_assets")
    subject = relationship("Subject", back_populates="file_assets")
    stage = relationship("Stage", back_populates="file_assets")
    stage_file = relationship("StageFile", back_populates="file_assets")
    ssu_progress = relationship("ClinicalSsuProgress", back_populates="file_assets")
    subject_item = relationship("SubjectItem", back_populates="file_assets")
    source_pdf_packet = relationship("PdfPacket")
    versions = relationship(
        "FileVersion",
        back_populates="file_asset",
        cascade="all, delete-orphan",
        order_by="FileVersion.version",
    )


class FileVersion(Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("file_id", "version", name="uq_file_versions_file_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text)

    file_asset = relationship("FileAsset", back_populates="versions")
