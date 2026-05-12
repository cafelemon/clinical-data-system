import { http } from "@/services/http";
import type {
  CorrectionTask,
  CorrectionTaskCreatePayload,
  CorrectionTaskQuery,
  PdfAnnotation,
  PdfAnnotationPayload,
  PdfAnnotationUpdate,
  PdfReviewFile,
} from "@/types/pdf-review";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

export const pdfReviewApi = {
  getReviewFile: (fileId: number, version?: number, fileVersionId?: number) =>
    read<PdfReviewFile>(`/pdf-review/files/${fileId}`, {
      version,
      file_version_id: fileVersionId,
    }),
  listAnnotations: (fileId: number, version?: number, fileVersionId?: number) =>
    read<PdfAnnotation[]>(`/pdf-review/files/${fileId}/annotations`, {
      version,
      file_version_id: fileVersionId,
    }),
  createAnnotation: async (payload: PdfAnnotationPayload) => {
    const response = await http.post<PdfAnnotation>("/pdf-review/annotations", payload);
    return response.data;
  },
  updateAnnotation: async (id: number, payload: PdfAnnotationUpdate) => {
    const response = await http.patch<PdfAnnotation>(`/pdf-review/annotations/${id}`, payload);
    return response.data;
  },
  deleteAnnotation: async (id: number) => {
    await http.delete(`/pdf-review/annotations/${id}`);
  },
  listTasks: (params?: CorrectionTaskQuery) => read<CorrectionTask[]>("/correction-tasks", params),
  getTask: (id: number) => read<CorrectionTask>(`/correction-tasks/${id}`),
  createTask: async (payload: CorrectionTaskCreatePayload) => {
    const response = await http.post<CorrectionTask>("/correction-tasks", payload);
    return response.data;
  },
  submitTask: async (id: number, file: File, remark?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (remark) formData.append("remark", remark);
    const response = await http.post<{ task: CorrectionTask }>(
      `/correction-tasks/${id}/submit`,
      formData,
      { timeout: 600000 },
    );
    return response.data.task;
  },
  approveTask: async (id: number, comment?: string) => {
    const response = await http.post<CorrectionTask>(`/correction-tasks/${id}/approve`, {
      comment: comment || null,
    });
    return response.data;
  },
  returnTask: async (id: number, comment: string) => {
    const response = await http.post<CorrectionTask>(`/correction-tasks/${id}/return`, {
      comment,
    });
    return response.data;
  },
};
