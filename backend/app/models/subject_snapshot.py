from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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

SUBJECT_SNAPSHOT_SCHEMA_VERSION = "subject-snapshot-json/v0"
SUBJECT_SNAPSHOT_DRAFT = "draft_snapshot"
SUBJECT_SNAPSHOT_RELEASED = "released_snapshot"
SUBJECT_SNAPSHOT_STATUS_DRAFT = "draft"


class SubjectSnapshot(Base):
    __tablename__ = "subject_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "snapshot_version",
            name="uq_subject_snapshots_subject_version",
        ),
        CheckConstraint(
            "snapshot_type in ('draft_snapshot', 'released_snapshot')",
            name="ck_subject_snapshots_snapshot_type",
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
    screening_no_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(80),
        default=SUBJECT_SNAPSHOT_SCHEMA_VERSION,
        server_default=SUBJECT_SNAPSHOT_SCHEMA_VERSION,
        nullable=False,
    )
    snapshot_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    snapshot_type: Mapped[str] = mapped_column(
        String(30),
        index=True,
        default=SUBJECT_SNAPSHOT_DRAFT,
        server_default=SUBJECT_SNAPSHOT_DRAFT,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        index=True,
        default=SUBJECT_SNAPSHOT_STATUS_DRAFT,
        server_default=SUBJECT_SNAPSHOT_STATUS_DRAFT,
        nullable=False,
    )
    storage_path: Mapped[str | None] = mapped_column(Text)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    generated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    generated_at = mapped_column(DateTime(timezone=True))
    locked_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="subject_snapshots")
    center = relationship("Center", back_populates="subject_snapshots")
    subject = relationship("Subject", back_populates="snapshots")
    generator = relationship("User")
