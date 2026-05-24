"""create v31 dashboard workbench

Revision ID: 8b6d2f4c9a31
Revises: 9a4d1c8e2b73
Create Date: 2026-05-24 11:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b6d2f4c9a31"
down_revision: str | Sequence[str] | None = "9a4d1c8e2b73"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def scope_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("center_id", sa.Integer(), nullable=True),
    ]


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def create_scoped_indexes(table_name: str) -> None:
    op.create_index(op.f(f"ix_{table_name}_id"), table_name, ["id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_project_id"), table_name, ["project_id"], unique=False)
    op.create_index(op.f(f"ix_{table_name}_center_id"), table_name, ["center_id"], unique=False)


def create_foreign_keys(table_name: str) -> None:
    op.create_foreign_key(
        op.f(f"fk_{table_name}_project_id_projects"),
        table_name,
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f(f"fk_{table_name}_center_id_centers"),
        table_name,
        "centers",
        ["center_id"],
        ["id"],
        ondelete="CASCADE",
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "dashboard_milestones",
        *scope_columns(),
        sa.Column("milestone_name", sa.String(length=120), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "center_id", "milestone_name", name="uq_dashboard_milestones_scope_name"
        ),
    )
    op.create_table(
        "dashboard_enrollment_plans",
        *scope_columns(),
        sa.Column("contract_count", sa.Integer(), nullable=True),
        sa.Column("screening_count", sa.Integer(), nullable=True),
        sa.Column("current_enrolled_count", sa.Integer(), nullable=True),
        sa.Column("positive_enrolled_count", sa.Integer(), nullable=True),
        sa.Column("identified_polyp_count", sa.Integer(), nullable=True),
        sa.Column("unidentified_polyp_count", sa.Integer(), nullable=True),
        sa.Column("whole_colon_completed_count", sa.Integer(), nullable=True),
        sa.Column("whole_colon_incomplete_count", sa.Integer(), nullable=True),
        sa.Column("sigmoid_unidentified_count", sa.Integer(), nullable=True),
        sa.Column("next_week_plan_count", sa.Integer(), nullable=True),
        sa.Column("eligible_count", sa.Integer(), nullable=True),
        sa.Column("enrollment_arrangement", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "center_id", name="uq_dashboard_enrollment_plans_scope"),
    )
    op.create_table(
        "dashboard_subject_overviews",
        *scope_columns(),
        sa.Column("screening_no", sa.String(length=80), nullable=False),
        sa.Column("informed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("swallow_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("swallow_time_2", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gastric_transit_time", sa.String(length=80), nullable=True),
        sa.Column("colon_entry_duration", sa.String(length=80), nullable=True),
        sa.Column("capsule_batch_no", sa.String(length=80), nullable=True),
        sa.Column("capsule_serial_no", sa.String(length=80), nullable=True),
        sa.Column("recorder_batch_no", sa.String(length=80), nullable=True),
        sa.Column("recorder_serial_no", sa.String(length=80), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=True),
        sa.Column("video_duration", sa.String(length=80), nullable=True),
        sa.Column("colon_work_duration", sa.String(length=80), nullable=True),
        sa.Column("condition_description", sa.Text(), nullable=True),
        sa.Column("capsule_excreted_at", sa.DateTime(timezone=True), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "screening_no",
            name="uq_dashboard_subject_overviews_screening",
        ),
    )
    op.create_table(
        "dashboard_device_handovers",
        *scope_columns(),
        sa.Column("device_name", sa.String(length=120), nullable=False),
        sa.Column("batch_no", sa.String(length=80), nullable=True),
        sa.Column("device_serial_no", sa.String(length=120), nullable=False),
        sa.Column("handed_over_at", sa.Date(), nullable=True),
        sa.Column("returned_at", sa.Date(), nullable=True),
        sa.Column("handover_status", sa.String(length=30), nullable=False),
        sa.Column("handover_person", sa.String(length=100), nullable=True),
        sa.Column("receiver", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "device_name",
            "device_serial_no",
            name="uq_dashboard_device_handovers_device",
        ),
    )
    op.create_table(
        "dashboard_subject_results",
        *scope_columns(),
        sa.Column("reading_no", sa.String(length=80), nullable=True),
        sa.Column("screening_no", sa.String(length=80), nullable=False),
        sa.Column("enrollment_no", sa.String(length=80), nullable=True),
        sa.Column("whole_colon_completed", sa.String(length=30), nullable=True),
        sa.Column("is_positive", sa.String(length=30), nullable=True),
        sa.Column("max_polyp_size", sa.String(length=80), nullable=True),
        sa.Column("capsule_polyp_count", sa.Integer(), nullable=True),
        sa.Column("colonoscopy_polyp_count", sa.Integer(), nullable=True),
        sa.Column("matched_polyp_count", sa.Integer(), nullable=True),
        sa.Column("is_fully_matched", sa.String(length=30), nullable=True),
        sa.Column("max_polyp_matched", sa.String(length=30), nullable=True),
        sa.Column("other_diagnosis", sa.Text(), nullable=True),
        sa.Column("result_notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "center_id", "screening_no", name="uq_dashboard_subject_results_screening"
        ),
    )
    op.create_table(
        "dashboard_clinical_events",
        *scope_columns(),
        sa.Column("event_name", sa.String(length=160), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=True),
        sa.Column("severity", sa.String(length=30), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "event_name", "occurred_at", name="uq_dashboard_clinical_events_event"
        ),
    )
    op.create_table(
        "dashboard_device_issues",
        *scope_columns(),
        sa.Column("problem_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("problem_description", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.String(length=30), nullable=False),
        sa.Column("problem_type", sa.String(length=80), nullable=True),
        sa.Column("center_institution", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "center_id",
            "problem_time",
            "problem_description",
            name="uq_dashboard_device_issues_problem",
        ),
    )
    op.create_table(
        "dashboard_important_tasks",
        *scope_columns(),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=True),
        sa.Column("planned_due_date", sa.Date(), nullable=True),
        sa.Column("actual_completed_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("importance", sa.String(length=30), nullable=False),
        sa.Column("urgency", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id", "title", "planned_due_date", name="uq_dashboard_important_tasks_title_due"
        ),
    )

    for table_name in (
        "dashboard_milestones",
        "dashboard_enrollment_plans",
        "dashboard_subject_overviews",
        "dashboard_device_handovers",
        "dashboard_subject_results",
        "dashboard_clinical_events",
        "dashboard_device_issues",
        "dashboard_important_tasks",
    ):
        create_scoped_indexes(table_name)
        create_foreign_keys(table_name)

    op.execute(
        sa.text(
            """
            insert into permissions (code, label, module, description)
            select 'dashboard:write', '维护数据看板', 'dashboard', ''
            where not exists (select 1 from permissions where code = 'dashboard:write')
            """
        )
    )
    op.execute(
        sa.text(
            """
            insert into role_permissions (role_id, permission_id)
            select r.id, p.id
            from roles r
            join permissions p on p.code = 'dashboard:write'
            where r.name in ('admin', 'project_manager', 'center_manager', 'clinical_coordinator')
              and not exists (
                select 1 from role_permissions rp
                where rp.role_id = r.id and rp.permission_id = p.id
              )
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        sa.text(
            """
            delete from role_permissions
            where permission_id in (select id from permissions where code = 'dashboard:write')
            """
        )
    )
    op.execute(sa.text("delete from permissions where code = 'dashboard:write'"))
    for table_name in (
        "dashboard_important_tasks",
        "dashboard_device_issues",
        "dashboard_clinical_events",
        "dashboard_subject_results",
        "dashboard_device_handovers",
        "dashboard_subject_overviews",
        "dashboard_enrollment_plans",
        "dashboard_milestones",
    ):
        op.drop_table(table_name)
