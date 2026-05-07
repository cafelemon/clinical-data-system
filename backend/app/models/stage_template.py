from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StageTemplate(Base):
    __tablename__ = "stage_templates"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "stage_id",
            "template_scope",
            "item_code",
            name="uq_stage_templates_item_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("stages.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(String(150), nullable=False)
    item_code: Mapped[str] = mapped_column(String(80), nullable=False)
    template_scope: Mapped[str] = mapped_column(String(30), default="center_file", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recognition_keywords: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="stage_templates")
    stage = relationship("Stage", back_populates="stage_templates")
    stage_files = relationship(
        "StageFile",
        back_populates="stage_template",
        cascade="all, delete-orphan",
    )
