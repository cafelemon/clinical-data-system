from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import ImageEvidenceIndex, Subject, SubjectImageRecord
from app.models.image_evidence import (
    IMAGE_EVIDENCE_ENHANCED_PACKAGE,
    IMAGE_EVIDENCE_LANDMARK_IMAGE,
    IMAGE_EVIDENCE_MATCH_APPROX,
    IMAGE_EVIDENCE_MATCH_RESOLVED,
    IMAGE_EVIDENCE_RAW_PACKAGE,
    IMAGE_EVIDENCE_REPORT_PACKAGE,
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


def image_records_for_subject(db: Session, subject_id: int) -> dict[str, SubjectImageRecord]:
    records = list(
        db.scalars(
            select(SubjectImageRecord)
            .where(SubjectImageRecord.subject_id == subject_id)
            .order_by(SubjectImageRecord.image_type)
        )
    )
    return {record.image_type: record for record in records}


def create_evidence(
    db: Session,
    *,
    record: SubjectImageRecord,
    evidence_type: str,
    match_status: str | None = None,
) -> ImageEvidenceIndex:
    evidence = ImageEvidenceIndex(
        project_id=record.project_id,
        center_id=record.center_id,
        subject_id=record.subject_id,
        subject_image_record_id=record.id,
        evidence_type=evidence_type,
        evidence_source="v4_2_0_model_test",
        relative_path=None,
        match_status=match_status,
        file_hash=None,
        file_size=None,
        gastrointestinal_location=None,
        payload_json={"source_image_type": record.image_type},
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)
    return evidence


def test_image_evidence_index_table_exists(client: TestClient) -> None:
    with db_session(client) as db:
        assert inspect(db.bind).has_table("image_evidence_index")


def test_image_evidence_index_accepts_multiple_evidence_types(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "IMG_EVIDENCE_MODEL")
    center_id = create_center(client, admin_headers, project_id, "IMG_EVIDENCE_MODEL")
    subject = create_subject(client, admin_headers, project_id, center_id, "EVID-001")

    with db_session(client) as db:
        records = image_records_for_subject(db, subject["id"])
        assert set(records) == {"enhanced", "raw", "report"}

        raw_evidence = create_evidence(
            db,
            record=records["raw"],
            evidence_type=IMAGE_EVIDENCE_RAW_PACKAGE,
            match_status=None,
        )
        enhanced_evidence = create_evidence(
            db,
            record=records["enhanced"],
            evidence_type=IMAGE_EVIDENCE_ENHANCED_PACKAGE,
            match_status=None,
        )
        report_evidence = create_evidence(
            db,
            record=records["report"],
            evidence_type=IMAGE_EVIDENCE_REPORT_PACKAGE,
            match_status=IMAGE_EVIDENCE_MATCH_RESOLVED,
        )

        assert raw_evidence.subject_id == subject["id"]
        assert enhanced_evidence.subject_image_record_id == records["enhanced"].id
        assert report_evidence.match_status == IMAGE_EVIDENCE_MATCH_RESOLVED


def test_image_evidence_index_match_status_constraint(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "IMG_EVIDENCE_STATUS")
    center_id = create_center(client, admin_headers, project_id, "IMG_EVIDENCE_STATUS")
    subject = create_subject(client, admin_headers, project_id, center_id, "EVID-002")

    with db_session(client) as db:
        records = image_records_for_subject(db, subject["id"])
        landmark = create_evidence(
            db,
            record=records["raw"],
            evidence_type=IMAGE_EVIDENCE_LANDMARK_IMAGE,
            match_status=IMAGE_EVIDENCE_MATCH_APPROX,
        )
        assert landmark.match_status == IMAGE_EVIDENCE_MATCH_APPROX

        db.add(
            ImageEvidenceIndex(
                project_id=records["raw"].project_id,
                center_id=records["raw"].center_id,
                subject_id=records["raw"].subject_id,
                subject_image_record_id=records["raw"].id,
                evidence_type=IMAGE_EVIDENCE_LANDMARK_IMAGE,
                match_status="matched",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_image_evidence_index_cascades_when_subject_is_deleted(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "IMG_EVIDENCE_SUBJECT_DEL")
    center_id = create_center(client, admin_headers, project_id, "IMG_EVIDENCE_SUBJECT_DEL")
    subject = create_subject(client, admin_headers, project_id, center_id, "EVID-003")

    with db_session(client) as db:
        records = image_records_for_subject(db, subject["id"])
        create_evidence(db, record=records["raw"], evidence_type=IMAGE_EVIDENCE_RAW_PACKAGE)

        loaded_subject = db.get(Subject, subject["id"])
        assert loaded_subject is not None
        db.delete(loaded_subject)
        db.commit()

        remaining = list(
            db.scalars(
                select(ImageEvidenceIndex).where(ImageEvidenceIndex.subject_id == subject["id"])
            )
        )
        assert remaining == []


def test_image_evidence_index_cascades_when_image_record_is_deleted(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    project_id = create_project(client, admin_headers, "IMG_EVIDENCE_RECORD_DEL")
    center_id = create_center(client, admin_headers, project_id, "IMG_EVIDENCE_RECORD_DEL")
    subject = create_subject(client, admin_headers, project_id, center_id, "EVID-004")

    with db_session(client) as db:
        records = image_records_for_subject(db, subject["id"])
        evidence = create_evidence(
            db,
            record=records["raw"],
            evidence_type=IMAGE_EVIDENCE_RAW_PACKAGE,
        )
        evidence_id = evidence.id

        db.delete(records["raw"])
        db.commit()

        assert db.get(ImageEvidenceIndex, evidence_id) is None
