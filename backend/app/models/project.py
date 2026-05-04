from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    centers = relationship("Center", back_populates="project", cascade="all, delete-orphan")
    stages = relationship("Stage", back_populates="project", cascade="all, delete-orphan")
    stage_templates = relationship(
        "StageTemplate",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    subjects = relationship("Subject", back_populates="project", cascade="all, delete-orphan")
    stage_files = relationship("StageFile", back_populates="project", cascade="all, delete-orphan")
    file_assets = relationship("FileAsset", back_populates="project", cascade="all, delete-orphan")
