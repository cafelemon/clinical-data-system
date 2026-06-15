from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clinical_data import (
    DEFAULT_REVIEW_STATUS,
    DEFAULT_UPLOAD_STATUS,
    SUBJECT_SECTION_SPECS,
)
from app.models import FileAsset, Stage, StageTemplate, Subject, SubjectItem
from app.models.clinical_data import SubjectSection
from app.services.stage_config import SUBJECT_ITEM_SCOPE, ensure_project_stage_config


PROTOCOL_VISIT_PREFIX = "PROTOCOL_VISIT_"
DEFAULT_SUBJECT_VISIT_CODES = frozenset(section.code for section in SUBJECT_SECTION_SPECS)


@dataclass
class SubjectSyncResult:
    synced_subjects: int = 0
    created_subject_sections: int = 0
    created_subject_items: int = 0
    removed_empty_legacy_sections: int = 0
    retained_legacy_sections: int = 0

    def add(self, other: "SubjectSyncResult") -> None:
        self.synced_subjects += other.synced_subjects
        self.created_subject_sections += other.created_subject_sections
        self.created_subject_items += other.created_subject_items
        self.removed_empty_legacy_sections += other.removed_empty_legacy_sections
        self.retained_legacy_sections += other.retained_legacy_sections

    def to_dict(self) -> dict[str, int]:
        return {
            "synced_subjects": self.synced_subjects,
            "created_subject_sections": self.created_subject_sections,
            "created_subject_items": self.created_subject_items,
            "removed_empty_legacy_sections": self.removed_empty_legacy_sections,
            "retained_legacy_sections": self.retained_legacy_sections,
        }


def create_default_subject_sections(db: Session, subject: Subject) -> SubjectSyncResult:
    return sync_subject_sections(db, subject)


def sync_project_subject_sections(db: Session, project_id: int) -> SubjectSyncResult:
    ensure_project_stage_config(db, project_id)
    result = SubjectSyncResult()
    subjects = list(
        db.scalars(select(Subject).where(Subject.project_id == project_id).order_by(Subject.id))
    )
    for subject in subjects:
        result.add(sync_subject_sections(db, subject))
    return result


def sync_subject_sections(db: Session, subject: Subject) -> SubjectSyncResult:
    ensure_project_stage_config(db, subject.project_id)
    result = SubjectSyncResult(synced_subjects=1)
    stages = subject_item_stages_for_project(db, subject.project_id)
    active_stage_codes = {stage.code for stage, _templates in stages}
    uses_protocol_visits = any(stage.code.startswith(PROTOCOL_VISIT_PREFIX) for stage, _ in stages)
    if uses_protocol_visits:
        result.add(remove_empty_legacy_default_sections(db, subject, active_stage_codes))

    existing_item_codes = {
        item_code
        for (item_code,) in db.query(SubjectItem.item_code)
        .filter(SubjectItem.subject_id == subject.id)
        .all()
    }
    for stage, templates in stages:
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
                time_window=stage.description,
                sort_order=stage.sort_order,
                description=stage.description,
            )
            db.add(section)
            db.flush()
            result.created_subject_sections += 1
        else:
            section.stage_id = stage.id
            section.name = stage.name
            section.visit_name = stage.name
            section.time_window = stage.description
            section.sort_order = stage.sort_order
            section.description = stage.description

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
            existing_item_codes.add(template.item_code)
            result.created_subject_items += 1
    return result


def subject_item_stages_for_project(
    db: Session,
    project_id: int,
) -> list[tuple[Stage, list[StageTemplate]]]:
    stages = (
        db.query(Stage)
        .filter(
            Stage.project_id == project_id,
            Stage.phase_code == "TRIAL",
            Stage.parent_id.is_not(None),
            Stage.enabled.is_(True),
        )
        .order_by(Stage.sort_order, Stage.id)
        .all()
    )
    stages_with_templates: list[tuple[Stage, list[StageTemplate]]] = []
    for stage in stages:
        templates = (
            db.query(StageTemplate)
            .filter(
                StageTemplate.project_id == project_id,
                StageTemplate.stage_id == stage.id,
                StageTemplate.template_scope == SUBJECT_ITEM_SCOPE,
            )
            .order_by(StageTemplate.sort_order, StageTemplate.id)
            .all()
        )
        if not templates:
            continue
        stages_with_templates.append((stage, templates))
    protocol_stages = [
        (stage, templates)
        for stage, templates in stages_with_templates
        if stage.code.startswith(PROTOCOL_VISIT_PREFIX)
    ]
    if protocol_stages:
        return protocol_stages
    return [
        (stage, templates)
        for stage, templates in stages_with_templates
        if stage.code in DEFAULT_SUBJECT_VISIT_CODES
    ]


def remove_empty_legacy_default_sections(
    db: Session,
    subject: Subject,
    active_stage_codes: set[str],
) -> SubjectSyncResult:
    result = SubjectSyncResult()
    legacy_sections = list(
        db.scalars(
            select(SubjectSection)
            .where(
                SubjectSection.subject_id == subject.id,
                SubjectSection.section_code.in_(DEFAULT_SUBJECT_VISIT_CODES - active_stage_codes),
            )
            .order_by(SubjectSection.sort_order, SubjectSection.id)
        )
    )
    for section in legacy_sections:
        if section_has_preserved_data(db, section):
            result.retained_legacy_sections += 1
            continue
        db.delete(section)
        result.removed_empty_legacy_sections += 1
    return result


def section_has_preserved_data(db: Session, section: SubjectSection) -> bool:
    item_ids: list[int] = []
    for item in section.items:
        item_ids.append(item.id)
        if item.upload_status != DEFAULT_UPLOAD_STATUS:
            return True
        if item.review_status != DEFAULT_REVIEW_STATUS:
            return True
        if item.remark:
            return True
    if not item_ids:
        return False
    return (
        db.scalar(select(FileAsset.id).where(FileAsset.subject_item_id.in_(item_ids)).limit(1))
        is not None
    )
