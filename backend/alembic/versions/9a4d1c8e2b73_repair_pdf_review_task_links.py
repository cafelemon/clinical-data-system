"""repair pdf review task links

Revision ID: 9a4d1c8e2b73
Revises: 7e1c3f4a9b52
Create Date: 2026-05-12 21:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a4d1c8e2b73"
down_revision: str | Sequence[str] | None = "7e1c3f4a9b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_TASK_WHERE = "status NOT IN ('closed', 'cancelled')"
ACTIONABLE_ANNOTATION_SQL = "('open', 'task_created', 'submitted', 'rejected')"


def upgrade() -> None:
    """Repair existing duplicate links, then enforce one active task per file."""
    if op.get_bind().dialect.name == "postgresql":
        repair_postgresql_data()

    op.create_index(
        "uq_correction_tasks_one_active_per_file",
        "correction_tasks",
        ["file_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_TASK_WHERE),
        sqlite_where=sa.text(ACTIVE_TASK_WHERE),
    )
    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "uq_correction_task_annotation_annotation",
            "correction_task_annotations",
            ["annotation_id"],
            unique=True,
        )
    else:
        op.create_unique_constraint(
            "uq_correction_task_annotation_annotation",
            "correction_task_annotations",
            ["annotation_id"],
        )


def downgrade() -> None:
    """Drop constraints added by this migration."""
    if op.get_bind().dialect.name == "sqlite":
        op.drop_index(
            "uq_correction_task_annotation_annotation",
            table_name="correction_task_annotations",
        )
    else:
        op.drop_constraint(
            "uq_correction_task_annotation_annotation",
            "correction_task_annotations",
            type_="unique",
        )
    op.drop_index("uq_correction_tasks_one_active_per_file", table_name="correction_tasks")


def repair_postgresql_data() -> None:
    op.execute(
        """
        WITH ranked_links AS (
            SELECT
                id,
                row_number() OVER (PARTITION BY annotation_id ORDER BY id DESC) AS rn
            FROM correction_task_annotations
        )
        DELETE FROM correction_task_annotations AS cta
        USING ranked_links AS ranked
        WHERE cta.id = ranked.id
          AND ranked.rn > 1
        """
    )
    op.execute("DROP TABLE IF EXISTS _pdf_review_primary_tasks")
    op.execute(
        f"""
        CREATE TEMP TABLE _pdf_review_primary_tasks ON COMMIT DROP AS
        WITH task_scores AS (
            SELECT
                t.id,
                t.file_id,
                t.status,
                t.updated_at,
                count(a.id) FILTER (
                    WHERE a.deleted_at IS NULL
                      AND a.status IN {ACTIONABLE_ANNOTATION_SQL}
                ) AS actionable_count
            FROM correction_tasks AS t
            LEFT JOIN correction_task_annotations AS cta ON cta.task_id = t.id
            LEFT JOIN pdf_annotations AS a ON a.id = cta.annotation_id
            WHERE t.status NOT IN ('closed', 'cancelled')
            GROUP BY t.id
        ),
        ranked_tasks AS (
            SELECT
                id,
                file_id,
                row_number() OVER (
                    PARTITION BY file_id
                    ORDER BY
                        CASE
                            WHEN actionable_count > 0 OR status <> 'pending' THEN 1
                            ELSE 0
                        END DESC,
                        actionable_count DESC,
                        CASE status
                            WHEN 'submitted' THEN 4
                            WHEN 'returned' THEN 3
                            WHEN 'processing' THEN 2
                            WHEN 'pending' THEN 1
                            ELSE 0
                        END DESC,
                        updated_at DESC,
                        id DESC
                ) AS rn,
                actionable_count,
                status
            FROM task_scores
        )
        SELECT id, file_id
        FROM ranked_tasks
        WHERE rn = 1
          AND (actionable_count > 0 OR status <> 'pending')
        """
    )
    op.execute(
        f"""
        UPDATE correction_task_annotations AS cta
        SET task_id = primary_task.id
        FROM correction_tasks AS duplicate_task,
             _pdf_review_primary_tasks AS primary_task,
             pdf_annotations AS annotation
        WHERE cta.task_id = duplicate_task.id
          AND primary_task.file_id = duplicate_task.file_id
          AND annotation.id = cta.annotation_id
          AND duplicate_task.id <> primary_task.id
          AND duplicate_task.status NOT IN ('closed', 'cancelled')
          AND annotation.deleted_at IS NULL
          AND annotation.status IN {ACTIONABLE_ANNOTATION_SQL}
        """
    )
    op.execute(
        """
        DELETE FROM correction_task_annotations AS cta
        USING correction_tasks AS duplicate_task
        JOIN _pdf_review_primary_tasks AS primary_task
          ON primary_task.file_id = duplicate_task.file_id
        WHERE cta.task_id = duplicate_task.id
          AND duplicate_task.id <> primary_task.id
          AND duplicate_task.status NOT IN ('closed', 'cancelled')
        """
    )
    op.execute(
        """
        UPDATE correction_tasks AS duplicate_task
        SET
            status = 'cancelled',
            review_result = 'cancelled',
            review_comment = '合并到整改任务 ' || primary_task.id::text,
            closed_at = now(),
            updated_at = now()
        FROM _pdf_review_primary_tasks AS primary_task
        WHERE duplicate_task.file_id = primary_task.file_id
          AND duplicate_task.id <> primary_task.id
          AND duplicate_task.status NOT IN ('closed', 'cancelled')
        """
    )
    op.execute(
        f"""
        UPDATE correction_tasks AS task
        SET
            status = 'cancelled',
            review_result = 'cancelled',
            review_comment = '空整改任务自动撤销',
            closed_at = now(),
            updated_at = now()
        WHERE task.status = 'pending'
          AND NOT EXISTS (
              SELECT 1
              FROM correction_task_annotations AS cta
              JOIN pdf_annotations AS annotation ON annotation.id = cta.annotation_id
              WHERE cta.task_id = task.id
                AND annotation.deleted_at IS NULL
                AND annotation.status IN {ACTIONABLE_ANNOTATION_SQL}
          )
        """
    )
    op.execute(
        f"""
        WITH files_needing_task AS (
            SELECT
                file_asset.id AS file_id,
                file_asset.project_id,
                file_asset.center_id,
                file_asset.subject_id,
                file_asset.subject_item_id,
                min(annotation.file_version_id) AS source_file_version_id,
                file_asset.original_name,
                file_asset.uploaded_by,
                min(annotation.created_by) AS created_by
            FROM pdf_annotations AS annotation
            JOIN files AS file_asset ON file_asset.id = annotation.file_id
            WHERE annotation.deleted_at IS NULL
              AND annotation.status IN {ACTIONABLE_ANNOTATION_SQL}
              AND NOT EXISTS (
                  SELECT 1
                  FROM correction_task_annotations AS cta
                  WHERE cta.annotation_id = annotation.id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM correction_tasks AS active_task
                  WHERE active_task.file_id = annotation.file_id
                    AND active_task.status NOT IN ('closed', 'cancelled')
              )
            GROUP BY
                file_asset.id,
                file_asset.project_id,
                file_asset.center_id,
                file_asset.subject_id,
                file_asset.subject_item_id,
                file_asset.original_name,
                file_asset.uploaded_by
        )
        INSERT INTO correction_tasks (
            task_no,
            project_id,
            center_id,
            subject_id,
            subject_item_id,
            file_id,
            source_file_version_id,
            latest_file_version_id,
            title,
            description,
            previous_upload_status,
            previous_review_status,
            assigned_to,
            created_by,
            status,
            due_date,
            submitted_at,
            reviewed_at,
            closed_at,
            submission_remark,
            review_comment,
            review_result,
            created_at,
            updated_at
        )
        SELECT
            'CORR-' || upper(substr(md5(file_id::text || clock_timestamp()::text), 1, 12)),
            project_id,
            center_id,
            subject_id,
            subject_item_id,
            file_id,
            source_file_version_id,
            NULL,
            original_name || ' 整改任务',
            NULL,
            NULL,
            NULL,
            uploaded_by,
            created_by,
            'pending',
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            now(),
            now()
        FROM files_needing_task
        """
    )
    op.execute(
        f"""
        WITH active_tasks AS (
            SELECT DISTINCT ON (file_id) id, file_id, status
            FROM correction_tasks
            WHERE status NOT IN ('closed', 'cancelled')
            ORDER BY file_id, updated_at DESC, id DESC
        )
        INSERT INTO correction_task_annotations (task_id, annotation_id)
        SELECT active_task.id, annotation.id
        FROM pdf_annotations AS annotation
        JOIN active_tasks AS active_task ON active_task.file_id = annotation.file_id
        WHERE annotation.deleted_at IS NULL
          AND annotation.status IN {ACTIONABLE_ANNOTATION_SQL}
          AND NOT EXISTS (
              SELECT 1
              FROM correction_task_annotations AS cta
              WHERE cta.annotation_id = annotation.id
          )
        """
    )
    op.execute(
        f"""
        UPDATE pdf_annotations AS annotation
        SET
            status = CASE task.status
                WHEN 'submitted' THEN 'submitted'
                WHEN 'returned' THEN 'rejected'
                WHEN 'closed' THEN 'resolved'
                ELSE 'task_created'
            END,
            updated_at = now()
        FROM correction_task_annotations AS cta
        JOIN correction_tasks AS task ON task.id = cta.task_id
        WHERE annotation.id = cta.annotation_id
          AND annotation.deleted_at IS NULL
          AND annotation.status IN {ACTIONABLE_ANNOTATION_SQL}
          AND task.status NOT IN ('closed', 'cancelled')
        """
    )
    op.execute(
        """
        WITH descriptions AS (
            SELECT
                task.id,
                left(
                    string_agg(
                        '第' || annotation.page_no::text || '页 '
                        || CASE annotation.issue_type
                            WHEN 'missing_page' THEN '缺页'
                            WHEN 'wrong_page' THEN '错页'
                            WHEN 'unclear_scan' THEN '扫描不清晰'
                            WHEN 'inconsistent_info' THEN '信息不一致'
                            WHEN 'missing_signature' THEN '签名缺失'
                            WHEN 'missing_stamp' THEN '盖章缺失'
                            WHEN 'missing_date' THEN '日期缺失'
                            WHEN 'wrong_subject' THEN '受试者不匹配'
                            WHEN 'wrong_document' THEN '资料类型不匹配'
                            ELSE annotation.issue_type
                        END || '：'
                        || btrim(annotation.comment),
                        E'\n'
                        ORDER BY annotation.page_no, annotation.id
                    ),
                    4000
                ) AS description
            FROM correction_tasks AS task
            JOIN correction_task_annotations AS cta ON cta.task_id = task.id
            JOIN pdf_annotations AS annotation ON annotation.id = cta.annotation_id
            WHERE annotation.deleted_at IS NULL
            GROUP BY task.id
        )
        UPDATE correction_tasks AS task
        SET description = descriptions.description,
            updated_at = now()
        FROM descriptions
        WHERE task.id = descriptions.id
        """
    )
