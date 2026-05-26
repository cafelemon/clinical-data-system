from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectItemSpec:
    code: str
    name: str
    sort_order: int
    required: bool = True


@dataclass(frozen=True)
class SubjectSectionSpec:
    code: str
    name: str
    visit_name: str
    time_window: str
    sort_order: int
    description: str
    items: tuple[SubjectItemSpec, ...]


SUBJECT_SECTION_SPECS = (
    SubjectSectionSpec(
        code="V1_SCREENING_VISIT",
        name="V1筛选访视阶段",
        visit_name="V1筛选访视",
        time_window="入组前",
        sort_order=1,
        description="完成知情同意、筛选评估和入组前资料收集。",
        items=(
            SubjectItemSpec("V1_INFORMED_CONSENT", "知情同意书", 0),
            SubjectItemSpec("V1_INFORMED_CONSENT_HANDOVER", "知情同意书交接表（若有）", 1, False),
            SubjectItemSpec("V1_VITAL_SIGNS", "生命体征记录", 2),
            SubjectItemSpec("V1_CT_REPORT", "CT检查报告", 3),
            SubjectItemSpec("V1_GASTROINTESTINAL_ENDOSCOPY_REPORT", "胃肠镜检查报告", 4),
            SubjectItemSpec("V1_ENROLLMENT_REVIEW", "入组审核记录表", 5),
            SubjectItemSpec("V1_AUXILIARY_EXAM_RESULTS", "其他辅助检查结果", 6),
            SubjectItemSpec("V1_HIS_DESCRIPTION", "HIS描述", 7),
            SubjectItemSpec("V1_RANDOMIZATION_PACKET", "随机记录包（若有）", 8, False),
        ),
    ),
    SubjectSectionSpec(
        code="V2_EXPERIMENTAL_FOLLOWUP_VISIT",
        name="V2试验组随访访视",
        visit_name="V2试验组随访访视",
        time_window="随方案确定",
        sort_order=2,
        description="完成试验组随访访视资料收集。",
        items=(
            SubjectItemSpec("V2_VITAL_SIGNS", "生命体征记录", 0),
            SubjectItemSpec("V2_BOWEL_PREPARATION", "肠道准备情况", 1),
            SubjectItemSpec("V2_HIS_DESCRIPTION", "HIS描述", 2),
            SubjectItemSpec("V2_PRIMARY_ENDPOINT_RESULT", "主要评价指标结果（若有）", 3, False),
            SubjectItemSpec("V2_SECONDARY_ENDPOINT_RESULT", "次要评价指标结果（若有）", 4, False),
            SubjectItemSpec("V2_CAPSULE_ENDOSCOPY_REPORT", "胶囊内镜报告", 5),
        ),
    ),
    SubjectSectionSpec(
        code="V3_CONTROL_FOLLOWUP_VISIT",
        name="V3对照组随访访视（若有）",
        visit_name="V3对照组随访访视",
        time_window="随方案确定",
        sort_order=3,
        description="完成对照组随访访视资料收集。",
        items=(
            SubjectItemSpec("V3_VITAL_SIGNS", "生命体征记录", 0),
            SubjectItemSpec("V3_BOWEL_PREPARATION", "肠道准备情况", 1),
            SubjectItemSpec("V3_HIS_DESCRIPTION", "HIS描述", 2),
            SubjectItemSpec("V3_PRIMARY_ENDPOINT_RESULT", "主要评价指标结果（若有）", 3, False),
            SubjectItemSpec("V3_SECONDARY_ENDPOINT_RESULT", "次要评价指标结果（若有）", 4, False),
            SubjectItemSpec("V3_CONTROL_REPORT", "对照组报告", 5),
        ),
    ),
    SubjectSectionSpec(
        code="V4_UNSCHEDULED_VISIT",
        name="V4非预期访视（若有）",
        visit_name="V4非预期访视",
        time_window="按需触发",
        sort_order=4,
        description="按需记录非预期访视资料。",
        items=(
            SubjectItemSpec("V4_HIS_RECORD", "HIS记录", 0, False),
        ),
    ),
)


UPLOAD_NOT_UPLOADED = "not_uploaded"
UPLOAD_UPLOADED = "uploaded"
UPLOAD_SUPPLEMENT_REQUIRED = "supplement_required"
UPLOAD_REPLACED = "replaced"

REVIEW_UNREVIEWED = "unreviewed"
REVIEW_PENDING = "pending"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"

DATA_INCOMPLETE = "incomplete"
DATA_CHECKING = "checking"
DATA_COMPLETE = "complete"

DEFAULT_UPLOAD_STATUS = UPLOAD_NOT_UPLOADED
DEFAULT_REVIEW_STATUS = REVIEW_UNREVIEWED
DEFAULT_DATA_STATUS = DATA_INCOMPLETE

UPLOADED_STATUSES = {UPLOAD_UPLOADED, UPLOAD_REPLACED}
CHECKING_REVIEW_STATUSES = {REVIEW_UNREVIEWED, REVIEW_PENDING}
