from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PdfPacket(Base):
    __tablename__ = "pdf_packets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    packet_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
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
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    screening_no: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    filename_screening_no: Mapped[str | None] = mapped_column(String(80), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="pdf_packets")
    center = relationship("Center", back_populates="pdf_packets")
    subject = relationship("Subject", back_populates="pdf_packets")
    segments = relationship(
        "PdfPacketSegment",
        back_populates="packet",
        cascade="all, delete-orphan",
        order_by="PdfPacketSegment.page_start",
    )


class PdfPacketSegment(Base):
    __tablename__ = "pdf_packet_segments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("pdf_packets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    detected_name: Mapped[str | None] = mapped_column(String(150))
    detected_code: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    suggested_subject_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_items.id", ondelete="SET NULL"),
        index=True,
    )
    subject_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("subject_items.id", ondelete="SET NULL"),
        index=True,
    )
    file_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"),
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    packet = relationship("PdfPacket", back_populates="segments")
    suggested_subject_item = relationship(
        "SubjectItem",
        foreign_keys=[suggested_subject_item_id],
    )
    subject_item = relationship("SubjectItem", foreign_keys=[subject_item_id])
    file_asset = relationship("FileAsset", foreign_keys=[file_asset_id])
