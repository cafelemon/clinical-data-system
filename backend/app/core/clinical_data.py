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
        description="完成知情同意、筛选评估和纳排标准确认。",
        items=(
            SubjectItemSpec("SCREENING_CONSENT", "知情同意", 1),
            SubjectItemSpec("SCREENING_ASSESSMENT", "筛选评估", 2),
            SubjectItemSpec("SCREENING_CRITERIA", "纳排标准确认", 3),
        ),
    ),
    SubjectSectionSpec(
        code="ENROLLMENT_PREP",
        name="入组与检查准备阶段",
        visit_name="入组准备访视",
        time_window="入组至检查前",
        sort_order=2,
        description="完成入组登记、基线信息和检查准备确认。",
        items=(
            SubjectItemSpec("ENROLLMENT_REGISTRATION", "入组登记", 1),
            SubjectItemSpec("BASELINE_INFORMATION", "基线信息", 2),
            SubjectItemSpec("EXAM_PREPARATION", "检查准备确认", 3),
        ),
    ),
    SubjectSectionSpec(
        code="EXAM_EXECUTION",
        name="检查执行阶段",
        visit_name="检查访视",
        time_window="检查当天",
        sort_order=3,
        description="记录检查执行、原始检查资料和检查结论摘要。",
        items=(
            SubjectItemSpec("EXAM_EXECUTION_RECORD", "检查执行记录", 1),
            SubjectItemSpec("EXAM_RAW_DATA", "原始检查资料", 2),
            SubjectItemSpec("EXAM_SUMMARY", "检查结论摘要", 3),
        ),
    ),
    SubjectSectionSpec(
        code="EARLY_FOLLOWUP",
        name="检查后早期随访阶段",
        visit_name="早期随访",
        time_window="检查后早期",
        sort_order=4,
        description="完成检查后早期随访和不良事件确认。",
        items=(
            SubjectItemSpec("EARLY_FOLLOWUP_RECORD", "早期随访记录", 1),
            SubjectItemSpec("ADVERSE_EVENT_CHECK", "不良事件确认", 2),
        ),
    ),
    SubjectSectionSpec(
        code="DELAYED_FOLLOWUP",
        name="异常或延迟随访阶段",
        visit_name="异常/延迟随访",
        time_window="按需触发",
        sort_order=5,
        description="记录异常处理和延迟随访情况。",
        items=(
            SubjectItemSpec("EXCEPTION_HANDLING", "异常处理记录", 1),
            SubjectItemSpec("DELAYED_FOLLOWUP_RECORD", "延迟随访记录", 2),
        ),
    ),
    SubjectSectionSpec(
        code="COMPLETION",
        name="试验完成阶段",
        visit_name="完成访视",
        time_window="试验结束",
        sort_order=6,
        description="完成受试者完成/退出记录和资料完整性确认。",
        items=(
            SubjectItemSpec("COMPLETION_OR_EXIT", "完成/退出记录", 1),
            SubjectItemSpec("DATA_COMPLETENESS_CONFIRM", "资料完整性确认", 2),
        ),
    ),
)


DEFAULT_UPLOAD_STATUS = "not_uploaded"
DEFAULT_REVIEW_STATUS = "pending_review"
DEFAULT_DATA_STATUS = "not_started"
