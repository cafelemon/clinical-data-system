from sqlalchemy.orm import Session

from app.core.clinical_data import (
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
)
from app.models import Stage, StageTemplate, Subject, SubjectItem
from app.models.clinical_data import SubjectSection
from app.services.stage_config import SUBJECT_ITEM_SCOPE, ensure_project_stage_config


def create_default_subject_sections(db: Session, subject: Subject) -> None:
    ensure_project_stage_config(db, subject.project_id)
    stages = (
        db.query(Stage)
        .filter(
            Stage.project_id == subject.project_id,
            Stage.phase_code == "TRIAL",
            Stage.parent_id.is_not(None),
            Stage.enabled.is_(True),
        )
        .order_by(Stage.sort_order, Stage.id)
        .all()
    )
    for stage in stages:
        section = SubjectSection(
            project_id=subject.project_id,
            stage_id=stage.id,
            subject_id=subject.id,
            section_code=stage.code,
            name=stage.name,
            visit_name=stage.name,
            time_window=None,
            sort_order=stage.sort_order,
            description=stage.description,
        )
        db.add(section)
        db.flush()
        templates = (
            db.query(StageTemplate)
            .filter(
                StageTemplate.project_id == subject.project_id,
                StageTemplate.stage_id == stage.id,
                StageTemplate.template_scope == SUBJECT_ITEM_SCOPE,
            )
            .order_by(StageTemplate.sort_order, StageTemplate.id)
            .all()
        )
        for template in templates:
            db.add(
                SubjectItem(
                    subject_id=subject.id,
                    section_id=section.id,
                    stage_template_id=template.id,
                    item_name=template.item_name,
                    item_code=template.item_code,
                    sort_order=template.sort_order,
                    required=template.required,
                    upload_status=DEFAULT_UPLOAD_STATUS,
                    review_status=DEFAULT_REVIEW_STATUS,
                )
            )
