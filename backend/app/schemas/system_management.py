from pydantic import BaseModel


class SystemManagementMasterDataRead(BaseModel):
    project_count: int = 0
    center_count: int = 0
    stage_count: int = 0
    disabled_stage_count: int = 0
    stage_template_count: int = 0
    dictionary_count: int = 0
    disabled_dictionary_count: int = 0


class SystemManagementIdentityRead(BaseModel):
    user_count: int = 0
    active_user_count: int = 0
    inactive_user_count: int = 0
    role_count: int = 0
    system_role_count: int = 0


class SystemManagementAuditRead(BaseModel):
    operation_log_count: int = 0


class SystemManagementWorkflowsRead(BaseModel):
    pdf_packet_count: int = 0
    pdf_packet_segment_count: int = 0
    correction_task_count: int = 0
    open_correction_task_count: int = 0
    pending_review_task_count: int = 0


class SystemManagementManualMaintenanceRead(BaseModel):
    milestone_count: int = 0
    enrollment_plan_count: int = 0
    subject_overview_count: int = 0
    device_handover_count: int = 0
    subject_result_count: int = 0
    clinical_event_count: int = 0
    device_issue_count: int = 0
    important_task_count: int = 0
    total_count: int = 0


class SystemManagementOverviewRead(BaseModel):
    master_data: SystemManagementMasterDataRead = SystemManagementMasterDataRead()
    identity: SystemManagementIdentityRead = SystemManagementIdentityRead()
    audit: SystemManagementAuditRead = SystemManagementAuditRead()
    workflows: SystemManagementWorkflowsRead = SystemManagementWorkflowsRead()
    manual_maintenance: SystemManagementManualMaintenanceRead = SystemManagementManualMaintenanceRead()
