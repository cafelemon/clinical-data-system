import type { CompletenessSummary } from "@/types/clinical-data";

export type DashboardProjectSummary = {
  project_id: number;
  project_name: string;
  completed_subject_count: number;
  visible_center_count: number;
  project_days: number;
  average_days_per_subject: number;
  median_days_per_subject: number;
  subject_count: number;
};

export type DashboardCenter = {
  center_id: number;
  center_name: string;
  subject_count: number;
  completed_subject_count: number;
  completion_rate: number;
  completeness_status: string;
  pending_review_count: number;
  rejected_review_count: number;
};

export type DashboardTrendPoint = {
  period: string;
  completed_count: number;
};

export type DashboardReviewStatus = {
  unreviewed: number;
  pending: number;
  approved: number;
  rejected: number;
};

export type DashboardCompleteness = CompletenessSummary;

export type DashboardV31Kind =
  | "milestones"
  | "enrollment-plans"
  | "subject-overviews"
  | "device-handovers"
  | "subject-results"
  | "clinical-events"
  | "device-issues"
  | "important-tasks";

export type DashboardV31Record = {
  id: number;
  project_id: number;
  center_id: number | null;
  created_at: string;
  updated_at: string;
  [key: string]: string | number | null;
};

export type DashboardV31Warning = {
  source: "milestone" | "important_task";
  id: number;
  title: string;
  center_id: number | null;
  planned_date: string;
  status: string;
  warning_level: "overdue" | "due_soon";
};

export type DashboardV31Overview = {
  project_id: number;
  counts: Record<string, number>;
  enrollment: Record<string, number>;
  important_task_status: Record<string, number>;
  deviation_warnings: DashboardV31Warning[];
};

export type DashboardV31ImportResult = {
  total_rows: number;
  created_count: number;
  updated_count: number;
  errors: Array<{ row: number; field: string; message: string }>;
  rows: Array<{ row: number; id: number }>;
};

export type DashboardV323Scope = {
  level: "all" | "project" | "center";
  project_id: number | null;
  project_name: string | null;
  center_id: number | null;
  center_name: string | null;
};

export type DashboardV323Kpis = {
  project_count: number;
  center_count: number;
  subject_count: number;
  completed_subject_count: number;
  completion_rate: number;
  active_warning_count: number;
  pending_review_count: number;
  rejected_review_count: number;
};

export type DashboardV323Center = {
  project_id: number;
  project_name: string;
  center_id: number;
  center_name: string;
  subject_count: number;
  completed_subject_count: number;
  completion_rate: number;
  completeness_status: string;
  pending_review_count: number;
  rejected_review_count: number;
};

export type DashboardV323Warning = {
  source: string;
  project_id: number;
  project_name: string;
  id: number;
  title: string;
  center_id: number | null;
  center_name: string | null;
  planned_date: string;
  status: string;
  warning_level: "overdue" | "due_soon";
};

export type DashboardV323Overview = {
  scope: DashboardV323Scope;
  kpis: DashboardV323Kpis;
  completeness: { complete: number; checking: number; incomplete: number };
  stage_files: { complete: number; checking: number; incomplete: number };
  subjects: { complete: number; checking: number; incomplete: number };
  reviews: DashboardReviewStatus;
  enrollment: {
    subject_count: number;
    completed_subject_count: number;
    contract_count: number;
    planned_next_week: number;
    maintained_current_enrolled: number;
  };
  centers: DashboardV323Center[];
  trends: Array<{ period: string; completed_count: number }>;
  warnings: DashboardV323Warning[];
  manual_supplements: {
    counts: Record<string, number>;
    important_task_status: Record<string, number>;
    clinical_event_count: number;
    device_issue_count: number;
  };
};
