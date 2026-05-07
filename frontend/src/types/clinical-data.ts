import type { Stage } from "@/types/master-data";

export type Subject = {
  id: number;
  project_id: number;
  center_id: number;
  screening_no: string;
  gender: string | null;
  age: number | null;
  enrolled_at: string | null;
  informed_at: string | null;
  visit1_date: string | null;
  visit2_date: string | null;
  visit3_date: string | null;
  visit4_date: string | null;
  visit5_date: string | null;
  added_by: number | null;
  review_status: string;
  data_status: string;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SubjectPayload = {
  project_id: number;
  center_id: number;
  screening_no: string;
  gender?: string | null;
  age?: number | null;
  enrolled_at?: string | null;
  informed_at?: string | null;
  visit1_date?: string | null;
  visit2_date?: string | null;
  visit3_date?: string | null;
  visit4_date?: string | null;
  visit5_date?: string | null;
  review_status?: string;
  data_status?: string;
};

export type SubjectSection = {
  id: number;
  project_id: number;
  stage_id: number | null;
  subject_id: number;
  section_code: string;
  name: string;
  visit_name: string | null;
  time_window: string | null;
  sort_order: number;
  description: string | null;
};

export type SubjectItem = {
  id: number;
  subject_id: number;
  section_id: number;
  stage_template_id: number | null;
  item_name: string;
  item_code: string;
  sort_order: number;
  required: boolean;
  upload_status: string;
  review_status: string;
  remark: string | null;
  uploaded_by: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string | null;
  reviewer_id: number | null;
  reviewer_name: string | null;
  reviewed_at: string | null;
  completeness_status: string | null;
  created_at: string;
  updated_at: string;
};

export type SubjectItemPayload = {
  upload_status?: string;
  review_status?: string;
  remark?: string | null;
};

export type StageFile = {
  id: number;
  project_id: number;
  center_id: number;
  stage_id: number;
  stage_template_id: number | null;
  file_name: string;
  file_type: string | null;
  upload_status: string;
  review_status: string;
  added_by: number | null;
  added_at: string;
  uploaded_by: number | null;
  uploaded_by_name: string | null;
  uploaded_at: string | null;
  reviewer_id: number | null;
  reviewer_name: string | null;
  reviewed_at: string | null;
  completeness_status: string | null;
  remark: string | null;
  updated_at: string;
};

export type StageFileGroup = {
  stage: Stage;
  files: StageFile[];
};

export type ClinicalPhase = {
  phase: Stage;
  child_stages: Stage[];
  files: StageFile[];
  file_groups: StageFileGroup[];
  subjects: Subject[];
};

export type ClinicalDataset = {
  project_id: number | null;
  center_id: number | null;
  stages: Stage[];
  child_stages: Stage[];
  phases: ClinicalPhase[];
  startup_file_groups: StageFileGroup[];
  startup_files: StageFile[];
  trial_stages: Stage[];
  trial_files: StageFile[];
  subjects: Subject[];
  closeout_file_groups: StageFileGroup[];
  closeout_files: StageFile[];
  stage_file_count: number;
  subject_count: number;
};

export type ReviewTargetType = "stage_file" | "subject_item";

export type ReviewRecord = {
  id: number;
  target_type: ReviewTargetType;
  target_id: number;
  action: string;
  review_status: string;
  reviewer_id: number | null;
  comment: string | null;
  created_at: string;
};

export type ReviewActionPayload = {
  target_type: ReviewTargetType;
  target_id: number;
  comment?: string | null;
};

export type ReviewBatchApproveTarget = {
  target_type: ReviewTargetType;
  target_id: number;
};

export type ReviewBatchApprovePayload = {
  targets: ReviewBatchApproveTarget[];
};

export type ReviewBatchApproveResultItem = ReviewBatchApproveTarget & {
  status: string;
  message: string;
  submitted: boolean;
  approved: boolean;
};

export type ReviewBatchApproveResult = {
  approved_count: number;
  skipped_count: number;
  results: ReviewBatchApproveResultItem[];
};

export type CompletenessStatusCount = {
  complete: number;
  checking: number;
  incomplete: number;
};

export type StageCompleteness = {
  stage_id: number;
  stage_name: string;
  status: string;
  required_count: number;
  complete_count: number;
  checking_count: number;
  incomplete_count: number;
};

export type CenterCompleteness = {
  center_id: number;
  center_name: string;
  status: string;
  stage_files: CompletenessStatusCount;
  subjects: CompletenessStatusCount;
};

export type CompletenessSummary = {
  project_id: number | null;
  center_id: number | null;
  status: string;
  stage_files: CompletenessStatusCount;
  subjects: CompletenessStatusCount;
  centers: CenterCompleteness[];
  stages: StageCompleteness[];
};
