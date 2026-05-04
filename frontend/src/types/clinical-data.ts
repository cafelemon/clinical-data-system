import type { Stage } from "@/types/master-data";

export type Subject = {
  id: number;
  project_id: number;
  center_id: number;
  screening_no: string;
  gender: string | null;
  age: number | null;
  enrolled_at: string | null;
  added_by: number | null;
  review_status: string;
  data_status: string;
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
  review_status?: string;
  data_status?: string;
};

export type SubjectSection = {
  id: number;
  project_id: number;
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
  item_name: string;
  item_code: string;
  sort_order: number;
  upload_status: string;
  review_status: string;
  remark: string | null;
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
  remark: string | null;
  updated_at: string;
};

export type ClinicalDataset = {
  project_id: number | null;
  center_id: number | null;
  stages: Stage[];
  startup_files: StageFile[];
  subjects: Subject[];
  closeout_files: StageFile[];
  stage_file_count: number;
  subject_count: number;
};
