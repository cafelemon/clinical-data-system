from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class DocumentExtractedField(Base):
    __tablename__ = "document_extracted_fields"
    __table_args__ = (
        UniqueConstraint(
            "file_version_id",
            "field_key",
            name="uq_document_fields_file_version_key",
        ),
        UniqueConstraint(
            "pdf_packet_segment_id",
            "field_key",
            name="uq_document_fields_segment_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    file_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("file_versions.id", ondelete="CASCADE"),
        index=True,
    )
    pdf_packet_segment_id: Mapped[int | None] = mapped_column(
        ForeignKey("pdf_packet_segments.id", ondelete="CASCADE"),
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    field_label: Mapped[str] = mapped_column(String(120), nullable=False)
    value_type: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    source_page_no: Mapped[int | None] = mapped_column(Integer)
    source_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="needs_input", nullable=False)
    manually_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    file_version = relationship("FileVersion")
    pdf_packet_segment = relationship("PdfPacketSegment")
