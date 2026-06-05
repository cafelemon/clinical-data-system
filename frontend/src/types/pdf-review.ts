import type { FileVersion } from "@/types/files";

export type AnnotationSeverity = "low" | "medium" | "high";

export type PdfAnnotation = {
  id: number;
  file_id: number;
  file_version_id: number;
  project_id: number;
  center_id: number;
  subject_id: number | null;
  subject_item_id: number | null;
  page_no: number;
  x: number;
  y: number;
  width: number;
  height: number;
  comment: string;
  issue_type: string;
  severity: AnnotationSeverity;
  status: string;
  created_by: number | null;
  updated_by: number | null;
  resolved_by: number | null;
  deleted_by: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  deleted_at: string | null;
};

export type PdfAnnotationPayload = {
  file_id: number;
  file_version_id: number;
  page_no: number;
  x: number;
  y: number;
  width: number;
  height: number;
  comment: string;
  issue_type: string;
  severity: AnnotationSeverity;
};

export type PdfAnnotationUpdate = Partial<
  Pick<
    PdfAnnotation,
    "page_no" | "x" | "y" | "width" | "height" | "comment" | "issue_type" | "severity" | "status"
  >
>;

export type PdfReviewFile = {
  file_id: number;
  file_version_id: number;
  file_name: string;
  preview_url: string;
  version: number;
  mime_type: string;
  status: string;
  project_id: number;
  center_id: number;
  subject_id: number | null;
  subject_item_id: number | null;
  ssu_progress_id: number | null;
  read_only: boolean;
  active_task_id: number | null;
  active_task_status: string | null;
  active_task_annotation_count: number;
  versions: FileVersion[];
  annotations: PdfAnnotation[];
};

export type CorrectionTask = {
  id: number;
  task_no: string;
  project_id: number;
  center_id: number;
  subject_id: number | null;
  subject_item_id: number | null;
  file_id: number;
  source_file_version_id: number;
  latest_file_version_id: number | null;
  title: string;
  description: string | null;
  assigned_to: number | null;
  created_by: number | null;
  status: string;
  due_date: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  closed_at: string | null;
  submission_remark: string | null;
  review_comment: string | null;
  review_result: string | null;
  created_at: string;
  updated_at: string;
  annotations: PdfAnnotation[];
};

export type CorrectionTaskCreatePayload = {
  file_id: number;
  file_version_id: number;
  annotation_ids: number[];
  assigned_to?: number | null;
  title?: string | null;
  description?: string | null;
  due_date?: string | null;
};

export type CorrectionTaskQuery = {
  assigned_to_me?: boolean;
  status?: string;
  file_id?: number;
  subject_id?: number;
};
