import { http } from "@/services/http";
import type {
  ImageDataType,
  SubjectImageRow,
  SubjectImageUploadResult,
} from "@/types/image-data";

const IMAGE_UPLOAD_TIMEOUT_MS = 3 * 60 * 60 * 1000;

function filenameFromDisposition(disposition?: string) {
  if (!disposition) return null;
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? null;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export const imageDataApi = {
  listRows: async (params: {
    project_id?: number;
    center_id?: number;
    image_type: ImageDataType;
  }) => {
    const response = await http.get<SubjectImageRow[]>("/image-data", { params });
    return response.data;
  },
  upload: async (recordId: number, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await http.post<SubjectImageUploadResult>(
      `/image-data/${recordId}/upload`,
      form,
      { headers: { "Content-Type": "multipart/form-data" }, timeout: IMAGE_UPLOAD_TIMEOUT_MS },
    );
    return response.data;
  },
  download: async (recordId: number, fallbackName: string) => {
    const response = await http.get<Blob>(`/image-data/${recordId}/download`, {
      responseType: "blob",
      timeout: 120000,
    });
    downloadBlob(
      response.data,
      filenameFromDisposition(response.headers["content-disposition"]) ?? fallbackName,
    );
  },
  rawCopy: async (recordId: number, fallbackName: string) => {
    const response = await http.get<Blob>(`/image-data/${recordId}/raw-copy`, {
      responseType: "blob",
      timeout: 120000,
    });
    downloadBlob(
      response.data,
      filenameFromDisposition(response.headers["content-disposition"]) ?? fallbackName,
    );
  },
  delete: async (recordId: number) => {
    await http.delete(`/image-data/${recordId}`);
  },
};
