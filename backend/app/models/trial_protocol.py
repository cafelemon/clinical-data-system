from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TrialProtocolVersion(Base):
    __tablename__ = "trial_protocol_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_trial_protocol_project_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parsing_status: Mapped[str] = mapped_column(String(30), default="parsed", nullable=False)
    protocol_no: Mapped[str | None] = mapped_column(String(80))
    protocol_version: Mapped[str | None] = mapped_column(String(80))
    protocol_date: Mapped[str | None] = mapped_column(String(80))
    draft_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    apply_result_json: Mapped[dict | None] = mapped_column(JSON)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    applied_at = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="trial_protocol_versions")
