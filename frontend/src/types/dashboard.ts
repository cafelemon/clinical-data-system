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
