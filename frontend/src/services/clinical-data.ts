import { http } from "@/services/http";
import type {
  ClinicalDataset,
  StageFile,
  Subject,
  SubjectItem,
  SubjectItemPayload,
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
    update<Subject, SubjectPayload>(`/subjects/${id}`, payload),
  getSubject: (id: number) => read<Subject>(`/subjects/${id}`),
  listSubjectSections: (id: number) => read<SubjectSection[]>(`/subjects/${id}/sections`),
  listSubjectItems: (id: number) => read<SubjectItem[]>(`/subjects/${id}/items`),
  updateSubjectItem: (id: number, payload: SubjectItemPayload) =>
    update<SubjectItem, SubjectItemPayload>(`/subject-items/${id}`, payload),
};
