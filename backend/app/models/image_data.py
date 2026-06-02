from sqlalchemy import (
    JSON,
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


class SubjectImageRecord(Base):
    __tablename__ = "subject_image_records"
    __table_args__ = (
        UniqueConstraint("subject_id", "image_type", name="uq_subject_image_records_subject_type"),
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
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    image_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    screening_no_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    upload_status: Mapped[str] = mapped_column(
        String(30),
        default="not_uploaded",
        server_default="not_uploaded",
        nullable=False,
    )
    original_name: Mapped[str | None] = mapped_column(String(255))
    stored_name: Mapped[str | None] = mapped_column(String(255))
    file_ext: Mapped[str | None] = mapped_column(String(30))
    mime_type: Mapped[str | None] = mapped_column(String(120))
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
    )
    file_hash: Mapped[str | None] = mapped_column(String(64))
    storage_path: Mapped[str | None] = mapped_column(Text)
    extracted_dir: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    image_total_size: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        server_default="0",
        nullable=False,
    )
    image_extensions_json: Mapped[dict | None] = mapped_column(JSON)
    parse_warning: Mapped[str | None] = mapped_column(Text)
    source_raw_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_image_records.id", ondelete="SET NULL"),
        index=True,
    )
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = mapped_column(DateTime(timezone=True))
    copied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    copied_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="image_records")
    center = relationship("Center", back_populates="image_records")
    subject = relationship("Subject", back_populates="image_records")
    source_raw_record = relationship("SubjectImageRecord", remote_side=[id])
