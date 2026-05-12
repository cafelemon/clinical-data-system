import { http } from "@/services/http";
import type {
  ClinicalDataset,
  CompletenessSummary,
  ReviewActionPayload,
  ReviewBatchApprovePayload,
  ReviewBatchApproveResult,
  ReviewRecord,
  ReviewTargetType,
  StageFile,
  Subject,
  SubjectItem,
  SubjectItemPayload,
  SubjectItemRemarkPayload,
  SubjectItemRemarkResponse,
  SubjectItemTimelineEntry,
  SubjectPayload,
  SubjectSection,
} from "@/types/clinical-data";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

async function create<T, P>(url: string, payload: P) {
  const response = await http.post<T>(url, payload);
  return response.data;
}

async function update<T, P>(url: string, payload: Partial<P>) {
  const response = await http.put<T>(url, payload);
  return response.data;
}

export const clinicalDataApi = {
  getDataset: (projectId: number, centerId: number) =>
    read<ClinicalDataset>("/clinical-datasets", {
      project_id: projectId,
      center_id: centerId,
    }),
  listStageFiles: (projectId: number, centerId: number, stageId?: number) =>
    read<StageFile[]>("/stage-files", {
      project_id: projectId,
      center_id: centerId,
      stage_id: stageId,
    }),
  listSubjects: (projectId?: number, centerId?: number) =>
    read<Subject[]>("/subjects", { project_id: projectId, center_id: centerId }),
  createSubject: (payload: SubjectPayload) => create<Subject, SubjectPayload>("/subjects", payload),
  updateSubject: (id: number, payload: Partial<SubjectPayload>) =>
    update<Subject, Partial<SubjectPayload>>(`/subjects/${id}`, payload),
  deleteSubject: (id: number) => http.delete(`/subjects/${id}`),
  getSubject: (id: number) => read<Subject>(`/subjects/${id}`),
  listSubjectSections: (id: number) => read<SubjectSection[]>(`/subjects/${id}/sections`),
  listSubjectItems: (id: number) => read<SubjectItem[]>(`/subjects/${id}/items`),
  updateSubjectItem: (id: number, payload: SubjectItemPayload) =>
    update<SubjectItem, SubjectItemPayload>(`/subject-items/${id}`, payload),
  updateSubjectItemRemark: async (id: number, payload: SubjectItemRemarkPayload) => {
    const response = await http.patch<SubjectItemRemarkResponse>(
      `/subject-items/${id}/remark`,
      payload,
    );
    return response.data;
  },
  listSubjectItemTimeline: (id: number, limit = 20) =>
    read<SubjectItemTimelineEntry[]>(`/subject-items/${id}/timeline`, { limit }),
  submitReview: (payload: ReviewActionPayload) =>
    create<ReviewRecord, ReviewActionPayload>("/reviews/submit", payload),
  approveReview: (payload: ReviewActionPayload) =>
    create<ReviewRecord, ReviewActionPayload>("/reviews/approve", payload),
  approveReviewsBatch: (payload: ReviewBatchApprovePayload) =>
    create<ReviewBatchApproveResult, ReviewBatchApprovePayload>("/reviews/approve-batch", payload),
  rejectReview: (payload: ReviewActionPayload) =>
    create<ReviewRecord, ReviewActionPayload>("/reviews/reject", payload),
  listReviewRecords: (targetType: ReviewTargetType, targetId: number) =>
    read<ReviewRecord[]>("/reviews", {
      target_type: targetType,
      target_id: targetId,
    }),
  recalculateCompleteness: (payload: {
    project_id?: number;
    center_id?: number;
    subject_id?: number;
  }) => create<CompletenessSummary, typeof payload>("/completeness/recalculate", payload),
  getCompletenessSummary: (projectId?: number, centerId?: number) =>
    read<CompletenessSummary>("/completeness/summary", {
      project_id: projectId,
      center_id: centerId,
    }),
};
