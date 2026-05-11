import { http } from "@/services/http";
import type {
  PdfPacket,
  PdfPacketSegment,
  PdfPacketSegmentPayload,
  PdfPacketSegmentUploadResult,
} from "@/types/pdf-packets";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

export const pdfPacketsApi = {
  listPackets: (params?: {
    project_id?: number;
    center_id?: number;
    subject_id?: number;
    status?: string;
  }) => read<PdfPacket[]>("/pdf-packets", params),
  getPacket: (id: number) => read<PdfPacket>(`/pdf-packets/${id}`),
  uploadPacket: async (payload: {
    file: File;
    projectId: number;
    centerId: number;
    subjectId: number;
  }) => {
    const formData = new FormData();
    formData.append("file", payload.file);
    formData.append("project_id", String(payload.projectId));
    formData.append("center_id", String(payload.centerId));
    formData.append("subject_id", String(payload.subjectId));
    const response = await http.post<PdfPacket>("/pdf-packets/upload", formData, {
      timeout: 1800000,
    });
    return response.data;
  },
  analyzePacket: async (id: number) => {
    const response = await http.post<PdfPacket>(`/pdf-packets/${id}/analyze`, undefined, {
      timeout: 1800000,
    });
    return response.data;
  },
  deletePacket: async (id: number) => {
    await http.delete(`/pdf-packets/${id}`);
  },
  listSegments: (packetId: number) =>
    read<PdfPacketSegment[]>(`/pdf-packets/${packetId}/segments`),
  createSegment: async (packetId: number, payload: Required<PdfPacketSegmentPayload>) => {
    const response = await http.post<PdfPacketSegment>(
      `/pdf-packets/${packetId}/segments`,
      payload,
    );
    return response.data;
  },
  updateSegment: async (id: number, payload: PdfPacketSegmentPayload) => {
    const response = await http.put<PdfPacketSegment>(`/pdf-packet-segments/${id}`, payload);
    return response.data;
  },
  deleteSegment: async (id: number) => {
    await http.delete(`/pdf-packet-segments/${id}`);
  },
  uploadSegment: async (id: number, subjectItemId: number) => {
    const response = await http.post<PdfPacketSegmentUploadResult>(
      `/pdf-packet-segments/${id}/upload`,
      { subject_item_id: subjectItemId },
    );
    return response.data;
  },
  previewPacket: async (id: number) => {
    const response = await http.get<Blob>(`/pdf-packets/${id}/preview`, {
      responseType: "blob",
    });
    return response.data;
  },
};
