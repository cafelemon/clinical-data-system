import { http } from "@/services/http";
import type { FileQuery, FileRecord, FileVersion } from "@/types/files";

function filenameFromDisposition(disposition: string | undefined, fallback: string) {
  if (!disposition) return fallback;
  const utf8Match = disposition.match(/filename\\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) return decodeURIComponent(utf8Match[1]);
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? fallback;
}

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

export const filesApi = {
  listFiles: (params: FileQuery) => read<FileRecord[]>("/files", params),
  getFile: (id: number) => read<FileRecord>(`/files/${id}`),
  listVersions: (id: number) => read<FileVersion[]>(`/files/${id}/versions`),
  uploadFile: async (payload: {
    file: File;
    fileCategory: string;
    stageFileId?: number;
    subjectItemId?: number;
    changeNote?: string;
  }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    formData.append("file_category", payload.fileCategory);
    if (payload.stageFileId) formData.append("stage_file_id", String(payload.stageFileId));
    if (payload.subjectItemId) formData.append("subject_item_id", String(payload.subjectItemId));
    if (payload.changeNote) formData.append("change_note", payload.changeNote);
    const response = await http.post<FileRecord>("/files/upload", formData);
    return response.data;
  },
  replaceFile: async (id: number, file: File, changeNote?: string) => {
    const formData = new FormData();
    formData.append("file", file);
    if (changeNote) formData.append("change_note", changeNote);
    const response = await http.post<FileRecord>(`/files/${id}/replace`, formData);
    return response.data;
  },
  deleteFile: async (id: number) => {
    await http.delete(`/files/${id}`);
  },
  downloadFile: async (id: number, version?: number) => {
    const response = await http.get<Blob>(`/files/${id}/download`, {
      params: { version },
      responseType: "blob",
    });
    return {
      blob: response.data,
      filename: filenameFromDisposition(
        response.headers["content-disposition"],
        `file-${id}`,
      ),
    };
  },
  previewFile: async (id: number, version?: number) => {
    const response = await http.get<Blob>(`/files/${id}/preview`, {
      params: { version },
      responseType: "blob",
      timeout: 600000,
    });
    return response.data;
  },
};
