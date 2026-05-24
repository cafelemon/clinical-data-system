from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DashboardMilestone(Base):
    __tablename__ = "dashboard_milestones"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "milestone_name",
            name="uq_dashboard_milestones_scope_name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    milestone_name: Mapped[str] = mapped_column(String(120), nullable=False)
    planned_date: Mapped[date | None] = mapped_column(Date)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="not_started", nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardEnrollmentPlan(Base):
    __tablename__ = "dashboard_enrollment_plans"
    __table_args__ = (
        UniqueConstraint("project_id", "center_id", name="uq_dashboard_enrollment_plans_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    contract_count: Mapped[int | None] = mapped_column(Integer)
    screening_count: Mapped[int | None] = mapped_column(Integer)
    current_enrolled_count: Mapped[int | None] = mapped_column(Integer)
    positive_enrolled_count: Mapped[int | None] = mapped_column(Integer)
    identified_polyp_count: Mapped[int | None] = mapped_column(Integer)
    unidentified_polyp_count: Mapped[int | None] = mapped_column(Integer)
    whole_colon_completed_count: Mapped[int | None] = mapped_column(Integer)
    whole_colon_incomplete_count: Mapped[int | None] = mapped_column(Integer)
    sigmoid_unidentified_count: Mapped[int | None] = mapped_column(Integer)
    next_week_plan_count: Mapped[int | None] = mapped_column(Integer)
    eligible_count: Mapped[int | None] = mapped_column(Integer)
    enrollment_arrangement: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardSubjectOverview(Base):
    __tablename__ = "dashboard_subject_overviews"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "screening_no",
            name="uq_dashboard_subject_overviews_screening",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    screening_no: Mapped[str] = mapped_column(String(80), nullable=False)
    informed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    swallow_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    swallow_time_2: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gastric_transit_time: Mapped[str | None] = mapped_column(String(80))
    colon_entry_duration: Mapped[str | None] = mapped_column(String(80))
    capsule_batch_no: Mapped[str | None] = mapped_column(String(80))
    capsule_serial_no: Mapped[str | None] = mapped_column(String(80))
    recorder_batch_no: Mapped[str | None] = mapped_column(String(80))
    recorder_serial_no: Mapped[str | None] = mapped_column(String(80))
    image_count: Mapped[int | None] = mapped_column(Integer)
    video_duration: Mapped[str | None] = mapped_column(String(80))
    colon_work_duration: Mapped[str | None] = mapped_column(String(80))
    condition_description: Mapped[str | None] = mapped_column(Text)
    capsule_excreted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardDeviceHandover(Base):
    __tablename__ = "dashboard_device_handovers"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "device_name",
            "device_serial_no",
            name="uq_dashboard_device_handovers_device",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    device_name: Mapped[str] = mapped_column(String(120), nullable=False)
    batch_no: Mapped[str | None] = mapped_column(String(80))
    device_serial_no: Mapped[str] = mapped_column(String(120), nullable=False)
    handed_over_at: Mapped[date | None] = mapped_column(Date)
    returned_at: Mapped[date | None] = mapped_column(Date)
    handover_status: Mapped[str] = mapped_column(String(30), default="in_use", nullable=False)
    handover_person: Mapped[str | None] = mapped_column(String(100))
    receiver: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardSubjectResult(Base):
    __tablename__ = "dashboard_subject_results"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "screening_no",
            name="uq_dashboard_subject_results_screening",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    reading_no: Mapped[str | None] = mapped_column(String(80))
    screening_no: Mapped[str] = mapped_column(String(80), nullable=False)
    enrollment_no: Mapped[str | None] = mapped_column(String(80))
    whole_colon_completed: Mapped[str | None] = mapped_column(String(30))
    is_positive: Mapped[str | None] = mapped_column(String(30))
    max_polyp_size: Mapped[str | None] = mapped_column(String(80))
    capsule_polyp_count: Mapped[int | None] = mapped_column(Integer)
    colonoscopy_polyp_count: Mapped[int | None] = mapped_column(Integer)
    matched_polyp_count: Mapped[int | None] = mapped_column(Integer)
    is_fully_matched: Mapped[str | None] = mapped_column(String(30))
    max_polyp_matched: Mapped[str | None] = mapped_column(String(30))
    other_diagnosis: Mapped[str | None] = mapped_column(Text)
    result_notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardClinicalEvent(Base):
    __tablename__ = "dashboard_clinical_events"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "event_name", "occurred_at", name="uq_dashboard_clinical_events_event"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    event_name: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_type: Mapped[str | None] = mapped_column(String(80))
    severity: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardDeviceIssue(Base):
    __tablename__ = "dashboard_device_issues"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "center_id",
            "problem_time",
            "problem_description",
            name="uq_dashboard_device_issues_problem",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    problem_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[str] = mapped_column(String(30), default="no", nullable=False)
    problem_type: Mapped[str | None] = mapped_column(String(80))
    center_institution: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DashboardImportantTask(Base):
    __tablename__ = "dashboard_important_tasks"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "title", "planned_due_date", name="uq_dashboard_important_tasks_title_due"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    center_id: Mapped[int | None] = mapped_column(
        ForeignKey("centers.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    owner: Mapped[str | None] = mapped_column(String(100))
    planned_due_date: Mapped[date | None] = mapped_column(Date)
    actual_completed_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    importance: Mapped[str] = mapped_column(String(30), default="important", nullable=False)
    urgency: Mapped[str] = mapped_column(String(30), default="urgent", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
