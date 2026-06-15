from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AccessContext, CurrentAccess, DBSession
from app.models import (
    Center,
    CorrectionTask,
    DashboardClinicalEvent,
    DashboardDeviceHandover,
    DashboardDeviceIssue,
    DashboardEnrollmentPlan,
    DashboardImportantTask,
    DashboardMilestone,
    DashboardSubjectOverview,
    DashboardSubjectResult,
    Dictionary,
    OperationLog,
    PdfPacket,
    PdfPacketSegment,
    Project,
    Role,
    Stage,
    StageTemplate,
    User,
)
from app.schemas.system_management import (
    SystemManagementAuditRead,
    SystemManagementIdentityRead,
    SystemManagementManualMaintenanceRead,
    SystemManagementMasterDataRead,
    SystemManagementOverviewRead,
    SystemManagementWorkflowsRead,
)

router = APIRouter()


def require_admin(access: CurrentAccess) -> CurrentAccess:
    if not access.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return access


AdminAccess = Annotated[AccessContext, Depends(require_admin)]


def count_rows(db: DBSession, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


@router.get("/system-management/overview", response_model=SystemManagementOverviewRead)
def system_management_overview(
    db: DBSession,
    _: AdminAccess,
) -> SystemManagementOverviewRead:
    manual_counts = {
        "milestone_count": count_rows(db, DashboardMilestone),
        "enrollment_plan_count": count_rows(db, DashboardEnrollmentPlan),
        "subject_overview_count": count_rows(db, DashboardSubjectOverview),
        "device_handover_count": count_rows(db, DashboardDeviceHandover),
        "subject_result_count": count_rows(db, DashboardSubjectResult),
        "clinical_event_count": count_rows(db, DashboardClinicalEvent),
        "device_issue_count": count_rows(db, DashboardDeviceIssue),
        "important_task_count": count_rows(db, DashboardImportantTask),
    }
    return SystemManagementOverviewRead(
        master_data=SystemManagementMasterDataRead(
            project_count=count_rows(db, Project),
            center_count=count_rows(db, Center),
            stage_count=count_rows(db, Stage),
            disabled_stage_count=db.scalar(
                select(func.count()).select_from(Stage).where(Stage.enabled.is_(False))
            )
            or 0,
            stage_template_count=count_rows(db, StageTemplate),
            dictionary_count=count_rows(db, Dictionary),
            disabled_dictionary_count=db.scalar(
                select(func.count()).select_from(Dictionary).where(Dictionary.enabled.is_(False))
            )
            or 0,
        ),
        identity=SystemManagementIdentityRead(
            user_count=count_rows(db, User),
            active_user_count=db.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
            or 0,
            inactive_user_count=db.scalar(
                select(func.count()).select_from(User).where(User.is_active.is_(False))
            )
            or 0,
            role_count=count_rows(db, Role),
            system_role_count=db.scalar(
                select(func.count()).select_from(Role).where(Role.system.is_(True))
            )
            or 0,
        ),
        audit=SystemManagementAuditRead(operation_log_count=count_rows(db, OperationLog)),
        workflows=SystemManagementWorkflowsRead(
            pdf_packet_count=count_rows(db, PdfPacket),
            pdf_packet_segment_count=count_rows(db, PdfPacketSegment),
            correction_task_count=count_rows(db, CorrectionTask),
            open_correction_task_count=db.scalar(
                select(func.count())
                .select_from(CorrectionTask)
                .where(CorrectionTask.status.notin_(["closed", "cancelled"]))
            )
            or 0,
            pending_review_task_count=db.scalar(
                select(func.count())
                .select_from(CorrectionTask)
                .where(CorrectionTask.status == "submitted")
            )
            or 0,
        ),
        manual_maintenance=SystemManagementManualMaintenanceRead(
            **manual_counts,
            total_count=sum(manual_counts.values()),
        ),
    )
