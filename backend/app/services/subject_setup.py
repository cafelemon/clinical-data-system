from sqlalchemy.orm import Session

from app.core.clinical_data import (
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
)
from app.models import Stage, StageTemplate, Subject, SubjectItem
from app.models.clinical_data import SubjectSection
from app.services.stage_config import SUBJECT_ITEM_SCOPE, ensure_project_stage_config


EXPERIMENTAL_VISIT_CODES = frozenset(
    {"V1_SCREENING_VISIT", "V2_EXPERIMENTAL_FOLLOWUP_VISIT", "V4_UNSCHEDULED_VISIT"}
)
CONTROL_VISIT_CODES = frozenset(
    {"V1_SCREENING_VISIT", "V3_CONTROL_FOLLOWUP_VISIT", "V4_UNSCHEDULED_VISIT"}
)


def visit_codes_for_subject_arm(subject_arm: str | None) -> frozenset[str]:
    if subject_arm == "control":
        return CONTROL_VISIT_CODES
    return EXPERIMENTAL_VISIT_CODES


def create_default_subject_sections(db: Session, subject: Subject) -> None:
    ensure_project_stage_config(db, subject.project_id)
    enabled_visit_codes = visit_codes_for_subject_arm(subject.subject_arm)
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
        if stage.code not in enabled_visit_codes:
            continue
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
        if not templates:
            continue
        section = (
            db.query(SubjectSection)
            .filter(
                SubjectSection.subject_id == subject.id,
                SubjectSection.section_code == stage.code,
            )
            .one_or_none()
        )
        if section is None:
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
        else:
            section.stage_id = stage.id
            section.name = stage.name
            section.visit_name = stage.name
            section.sort_order = stage.sort_order
            section.description = stage.description

        existing_item_codes = {
            item_code
            for (item_code,) in db.query(SubjectItem.item_code)
            .filter(SubjectItem.subject_id == subject.id)
            .all()
        }
        for template in templates:
            if template.item_code in existing_item_codes:
                continue
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
