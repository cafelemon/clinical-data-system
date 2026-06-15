import { http } from "@/services/http";
import type {
  DashboardCenter,
  DashboardCompleteness,
  DashboardProjectSummary,
  DashboardReviewStatus,
  DashboardTrendPoint,
  DashboardV31ImportResult,
  DashboardV31Kind,
  DashboardV31Overview,
  DashboardV31Record,
  DashboardV323Overview,
} from "@/types/dashboard";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

async function create<T, P>(url: string, payload: P) {
  const response = await http.post<T>(url, payload);
  return response.data;
}

async function patch<T, P>(url: string, payload: P) {
  const response = await http.patch<T>(url, payload);
  return response.data;
}

async function remove(url: string) {
  await http.delete(url);
}

async function downloadBlob(url: string, params?: Record<string, unknown>) {
  const response = await http.get<Blob>(url, { params, responseType: "blob" });
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
  getV31Overview: (projectId: number) =>
    read<DashboardV31Overview>(`/dashboard/v31/project/${projectId}/overview`),
  getV323Overview: (projectId?: number, centerId?: number) =>
    read<DashboardV323Overview>("/dashboard/v323/overview", {
      project_id: projectId,
      center_id: centerId,
    }),
  listV31Records: (kind: DashboardV31Kind, projectId: number, centerId?: number) =>
    read<DashboardV31Record[]>(`/dashboard/v31/${kind}`, {
      project_id: projectId,
      center_id: centerId,
    }),
  createV31Record: (kind: DashboardV31Kind, payload: Record<string, unknown>) =>
    create<DashboardV31Record, Record<string, unknown>>(`/dashboard/v31/${kind}`, payload),
  updateV31Record: (kind: DashboardV31Kind, id: number, payload: Record<string, unknown>) =>
    patch<DashboardV31Record, Record<string, unknown>>(`/dashboard/v31/${kind}/${id}`, payload),
  deleteV31Record: (kind: DashboardV31Kind, id: number) => remove(`/dashboard/v31/${kind}/${id}`),
  downloadV31Template: (kind: DashboardV31Kind) =>
    downloadBlob(`/dashboard/v31/import-template/${kind}`),
  exportV31Records: (kind: DashboardV31Kind, projectId: number, centerId?: number) =>
    downloadBlob(`/dashboard/v31/export/${kind}`, {
      project_id: projectId,
      center_id: centerId,
    }),
  importV31Records: async (kind: DashboardV31Kind, projectId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await http.post<DashboardV31ImportResult>(
      `/dashboard/v31/import/${kind}`,
      formData,
      { params: { project_id: projectId } },
    );
    return response.data;
  },
};
