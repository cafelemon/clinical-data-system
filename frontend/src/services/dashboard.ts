import { http } from "@/services/http";
import type {
  DashboardCenter,
  DashboardCompleteness,
  DashboardProjectSummary,
  DashboardReviewStatus,
  DashboardTrendPoint,
} from "@/types/dashboard";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

export const dashboardApi = {
  getProjectSummary: (projectId: number) =>
    read<DashboardProjectSummary>(`/dashboard/project/${projectId}`),
  listProjectCenters: (projectId: number) =>
    read<DashboardCenter[]>(`/dashboard/project/${projectId}/centers`),
  getProjectTrend: (projectId: number, granularity: "week" | "month" = "week") =>
    read<DashboardTrendPoint[]>(`/dashboard/project/${projectId}/trend`, { granularity }),
  getReviewStatus: (projectId: number) =>
    read<DashboardReviewStatus>(`/dashboard/project/${projectId}/review-status`),
  getCompleteness: (projectId: number) =>
    read<DashboardCompleteness>(`/dashboard/project/${projectId}/completeness`),
};
