from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Subject, SubjectSnapshot
from app.models.subject_snapshot import (
    SUBJECT_SNAPSHOT_DRAFT,
    SUBJECT_SNAPSHOT_SCHEMA_VERSION,
    SUBJECT_SNAPSHOT_STATUS_DRAFT,
)
from tests.test_dashboard import create_center, create_project, create_subject


@contextmanager
def db_session(client: TestClient) -> Generator[Session, None, None]:
    override = client.app.dependency_overrides[get_db]
    session_generator = override()
    db = next(session_generator)
    try:
        yield db
    finally:
        session_generator.close()


def create_snapshot(
    db: Session,
    *,
    project_id: int,
    center_id: int,
    subject_id: int,
    screening_no: str,
    snapshot_version: int = 1,
) -> SubjectSnapshot:
    snapshot = SubjectSnapshot(
        project_id=project_id,
        center_id=center_id,
        subject_id=subject_id,
        screening_no_snapshot=screening_no,
        snapshot_version=snapshot_version,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def test_subject_snapshot_model_defaults_and_unique_version(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "SNAP_MODEL")
    center_id = create_center(client, admin_headers, project_id, "SNAP_MODEL")
    subject = create_subject(client, admin_headers, project_id, center_id, "SNAP-001")

    with db_session(client) as db:
        snapshot = create_snapshot(
            db,
            project_id=project_id,
            center_id=center_id,
            subject_id=subject["id"],
            screening_no=subject["screening_no"],
        )

        assert snapshot.schema_version == SUBJECT_SNAPSHOT_SCHEMA_VERSION
        assert snapshot.snapshot_version == 1
        assert snapshot.snapshot_type == SUBJECT_SNAPSHOT_DRAFT
        assert snapshot.status == SUBJECT_SNAPSHOT_STATUS_DRAFT
        assert snapshot.storage_path is None
        assert snapshot.file_hash is None
        assert snapshot.file_size is None
        assert snapshot.generated_at is None
        assert snapshot.locked_at is None

        db.add(
            SubjectSnapshot(
                project_id=project_id,
                center_id=center_id,
                subject_id=subject["id"],
                screening_no_snapshot=subject["screening_no"],
                snapshot_version=1,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_subject_snapshot_versions_are_scoped_by_subject(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "SNAP_SCOPE")
    center_id = create_center(client, admin_headers, project_id, "SNAP_SCOPE")
    first_subject = create_subject(client, admin_headers, project_id, center_id, "SNAP-101")
    second_subject = create_subject(client, admin_headers, project_id, center_id, "SNAP-102")

    with db_session(client) as db:
        first_snapshot = create_snapshot(
            db,
            project_id=project_id,
            center_id=center_id,
            subject_id=first_subject["id"],
            screening_no=first_subject["screening_no"],
        )
        second_snapshot = create_snapshot(
            db,
            project_id=project_id,
            center_id=center_id,
            subject_id=second_subject["id"],
            screening_no=second_subject["screening_no"],
        )

        assert first_snapshot.snapshot_version == 1
        assert second_snapshot.snapshot_version == 1


def test_subject_snapshot_cascades_when_subject_is_deleted(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "SNAP_CASCADE")
    center_id = create_center(client, admin_headers, project_id, "SNAP_CASCADE")
    subject = create_subject(client, admin_headers, project_id, center_id, "SNAP-DEL")

    with db_session(client) as db:
        create_snapshot(
            db,
            project_id=project_id,
            center_id=center_id,
            subject_id=subject["id"],
            screening_no=subject["screening_no"],
        )

        loaded_subject = db.get(Subject, subject["id"])
        assert loaded_subject is not None
        db.delete(loaded_subject)
        db.commit()

        remaining = list(
            db.scalars(
                select(SubjectSnapshot).where(SubjectSnapshot.subject_id == subject["id"])
            )
        )
        assert remaining == []
