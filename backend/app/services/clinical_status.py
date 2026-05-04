from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import DEFAULT_DATA_STATUS, DEFAULT_REVIEW_STATUS, DEFAULT_UPLOAD_STATUS
from app.models import Subject, SubjectItem


def recalculate_subject_status(db: Session, subject: Subject) -> None:
    items = list(db.scalars(select(SubjectItem).where(SubjectItem.subject_id == subject.id)))
    if not items or all(item.upload_status == DEFAULT_UPLOAD_STATUS for item in items):
        subject.data_status = DEFAULT_DATA_STATUS
    elif all(item.upload_status == "uploaded" for item in items) and all(
        item.review_status == "approved" for item in items
    ):
        subject.data_status = "complete"
    else:
        subject.data_status = "in_progress"

    if items and all(item.review_status == "approved" for item in items):
        subject.review_status = "approved"
    elif any(item.review_status == "rejected" for item in items):
        subject.review_status = "rejected"
    else:
        subject.review_status = DEFAULT_REVIEW_STATUS
