export type SystemManagementMasterData = {
  project_count: number;
  center_count: number;
  stage_count: number;
  disabled_stage_count: number;
  stage_template_count: number;
  dictionary_count: number;
  disabled_dictionary_count: number;
};

export type SystemManagementIdentity = {
  user_count: number;
  active_user_count: number;
  inactive_user_count: number;
  role_count: number;
  system_role_count: number;
};

export type SystemManagementAudit = {
  operation_log_count: number;
};

export type SystemManagementWorkflows = {
  pdf_packet_count: number;
  pdf_packet_segment_count: number;
  correction_task_count: number;
  open_correction_task_count: number;
  pending_review_task_count: number;
};

export type SystemManagementManualMaintenance = {
  milestone_count: number;
  enrollment_plan_count: number;
  subject_overview_count: number;
  device_handover_count: number;
  subject_result_count: number;
  clinical_event_count: number;
  device_issue_count: number;
  important_task_count: number;
  total_count: number;
};

export type SystemManagementOverview = {
  master_data: SystemManagementMasterData;
  identity: SystemManagementIdentity;
  audit: SystemManagementAudit;
  workflows: SystemManagementWorkflows;
  manual_maintenance: SystemManagementManualMaintenance;
};
