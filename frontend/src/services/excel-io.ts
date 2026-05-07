import { http } from "@/services/http";
import type { ExportKind, ImportKind, ImportResult } from "@/types/excel-io";

const exportPath: Record<ExportKind, string> = {
  "project-progress": "/export/project-progress",
  "center-status": "/export/center-status",
  "subject-completeness": "/export/subject-completeness",
  "missing-items": "/export/missing-items",
};

function filenameFromDisposition(disposition: string | undefined, fallback: string) {
  if (!disposition) return fallback;
  const match = disposition.match(/filename="?([^"]+)"?/);
  return match?.[1] ?? fallback;
}

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

async function download(url: string, fallbackFilename: string, params?: Record<string, unknown>) {
  const response = await http.get<Blob>(url, { params, responseType: "blob" });
  const filename = filenameFromDisposition(response.headers["content-disposition"], fallbackFilename);
  saveBlob(response.data, filename);
}

export const excelIoApi = {
  downloadImportTemplate: (kind: ImportKind) =>
    download(`/import/templates/${kind}`, `${kind}-template.xlsx`),

  importExcel: async (kind: ImportKind, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await http.post<ImportResult>(`/import/${kind}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 30000,
    });
    return response.data;
  },

  exportExcel: (kind: ExportKind, projectId?: number, centerId?: number) =>
    download(exportPath[kind], `${kind}.xlsx`, {
      project_id: projectId,
      center_id: centerId,
    }),
};
