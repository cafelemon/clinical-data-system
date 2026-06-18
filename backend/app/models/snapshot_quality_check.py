from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

SNAPSHOT_CHECK_PASS = "pass"
SNAPSHOT_CHECK_WARN = "warn"
SNAPSHOT_CHECK_FAIL = "fail"
SNAPSHOT_CHECK_NOT_SUPPORTED = "not_supported"


class SnapshotQualityCheck(Base):
    __tablename__ = "snapshot_quality_checks"
    __table_args__ = (
        CheckConstraint(
            "snapshot_type in ('draft_snapshot', 'released_snapshot')",
            name="ck_snapshot_quality_checks_snapshot_type",
        ),
        CheckConstraint(
            "check_status in ('pass', 'warn', 'fail', 'not_supported')",
            name="ck_snapshot_quality_checks_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    check_run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
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
    snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_snapshots.id", ondelete="SET NULL"),
        index=True,
    )
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    check_code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    check_status: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    blocking: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project")
    center = relationship("Center")
    subject = relationship("Subject")
    snapshot = relationship("SubjectSnapshot")
