from dataclasses import dataclass


@dataclass(frozen=True)
class SubjectItemSpec:
    code: str
    name: str
    sort_order: int


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
        code="SCREENING",
        name="筛选阶段",
        visit_name="筛选访视",
        time_window="入组前",
        sort_order=1,
        description="完成筛选阶段资料收集。",
        items=(
            SubjectItemSpec("知情同意书", "知情同意书", 0),
            SubjectItemSpec("知情同意书交接表", "知情同意书交接表", 1),
            SubjectItemSpec("生命体征记录表", "生命体征记录表", 2),
            SubjectItemSpec("CT报告", "CT报告", 3),
            SubjectItemSpec("胃肠镜检查报告", "胃肠镜检查报告", 4),
            SubjectItemSpec("入组审核记录表", "入组审核记录表", 5),
            SubjectItemSpec("其他辅助检查结果", "其他辅助检查结果", 6),
            SubjectItemSpec("HIS记录", "HIS记录", 7),
        ),
    ),
    SubjectSectionSpec(
        code="ENROLLMENT_PREP",
        name="入组与检查准备阶段",
        visit_name="入组准备访视",
        time_window="入组至检查前",
        sort_order=2,
        description="完成入组与检查准备资料收集。",
        items=(
            SubjectItemSpec("随机记录表", "随机记录表", 0),
            SubjectItemSpec("肠道准备情况", "肠道准备情况", 1),
        ),
    ),
    SubjectSectionSpec(
        code="EXAM_EXECUTION",
        name="检查执行阶段",
        visit_name="检查访视",
        time_window="检查当天",
        sort_order=3,
        description="完成检查执行阶段资料收集。",
        items=(
            SubjectItemSpec("舒适度评价表", "舒适度评价表", 0),
            SubjectItemSpec("设备常用功能评价表", "设备常用功能评价表", 1),
            SubjectItemSpec("图像质量评价表", "图像质量评价表", 2),
            SubjectItemSpec("其他次要指标评价表", "其他次要指标评价表", 3),
            SubjectItemSpec("胶囊内镜报告", "胶囊内镜报告", 4),
        ),
    ),
    SubjectSectionSpec(
        code="EARLY_FOLLOWUP",
        name="检查后早期随访阶段",
        visit_name="早期随访",
        time_window="检查后早期",
        sort_order=4,
        description="保留检查后早期随访阶段。",
        items=(),
    ),
    SubjectSectionSpec(
        code="DELAYED_FOLLOWUP",
        name="异常或延迟随访阶段",
        visit_name="异常/延迟随访",
        time_window="按需触发",
        sort_order=5,
        description="完成异常或延迟随访资料收集。",
        items=(
            SubjectItemSpec("X线检查报告", "X线检查报告", 0),
        ),
    ),
    SubjectSectionSpec(
        code="COMPLETION",
        name="试验完成阶段",
        visit_name="完成访视",
        time_window="试验结束",
        sort_order=6,
        description="完成试验完成阶段资料收集。",
        items=(
            SubjectItemSpec("中心阅片评价结果表", "中心阅片评价结果表", 0),
            SubjectItemSpec("安全事件", "安全事件", 1),
            SubjectItemSpec("器械缺陷", "器械缺陷", 2),
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
