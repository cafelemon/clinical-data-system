from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

IMAGE_EVIDENCE_RAW_PACKAGE = "raw_package"
IMAGE_EVIDENCE_ENHANCED_PACKAGE = "enhanced_package"
IMAGE_EVIDENCE_REPORT_PACKAGE = "report_package"
IMAGE_EVIDENCE_REPORT_IMAGE = "report_image"
IMAGE_EVIDENCE_MARKED_IMAGE = "marked_image"
IMAGE_EVIDENCE_LANDMARK_IMAGE = "landmark_image"

IMAGE_EVIDENCE_MATCH_RESOLVED = "resolved"
IMAGE_EVIDENCE_MATCH_APPROX = "approx_matched"
IMAGE_EVIDENCE_MATCH_UNRESOLVED = "unresolved"
IMAGE_EVIDENCE_MATCH_NOT_SUPPORTED = "not_supported"


class ImageEvidenceIndex(Base):
    __tablename__ = "image_evidence_index"
    __table_args__ = (
        CheckConstraint(
            "evidence_type in ("
            "'raw_package', 'enhanced_package', 'report_package', "
            "'report_image', 'marked_image', 'landmark_image'"
            ")",
            name="ck_image_evidence_index_evidence_type",
        ),
        CheckConstraint(
            "match_status is null or match_status in ("
            "'resolved', 'approx_matched', 'unresolved', 'not_supported'"
            ")",
            name="ck_image_evidence_index_match_status",
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
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    subject_image_record_id: Mapped[int] = mapped_column(
        ForeignKey("subject_image_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    evidence_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    evidence_source: Mapped[str | None] = mapped_column(String(80), index=True)
    relative_path: Mapped[str | None] = mapped_column(Text)
    match_status: Mapped[str | None] = mapped_column(String(30), index=True)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    gastrointestinal_location: Mapped[str | None] = mapped_column(String(120), index=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    indexed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    indexed_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="image_evidence")
    center = relationship("Center", back_populates="image_evidence")
    subject = relationship("Subject", back_populates="image_evidence")
    subject_image_record = relationship("SubjectImageRecord", back_populates="image_evidence")
    indexer = relationship("User")
