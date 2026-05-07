import type { FileRecord } from "@/types/files";

export type PdfPacket = {
  id: number;
  packet_id: string;
  original_name: string;
  stored_name: string;
  file_ext: string | null;
  mime_type: string;
  file_size: number;
  file_hash: string;
  storage_path: string;
  storage_type: string;
  project_id: number;
  center_id: number;
  subject_id: number;
  screening_no: string;
  filename_screening_no: string | null;
  page_count: number;
  status: string;
  error_message: string | null;
  analysis_summary: string | null;
  uploaded_by: number | null;
  uploaded_at: string;
  updated_at: string;
  segment_count: number | null;
};

export type PdfPacketSegment = {
  id: number;
  packet_id: number;
  page_start: number;
  page_end: number;
  detected_name: string | null;
  detected_code: string | null;
  confidence: number;
  suggested_subject_item_id: number | null;
  subject_item_id: number | null;
  file_asset_id: number | null;
  status: string;
  ocr_text: string | null;
  created_at: string;
  updated_at: string;
};

export type PdfPacketSegmentPayload = {
  page_start?: number;
  page_end?: number;
  detected_name?: string | null;
  detected_code?: string | null;
  confidence?: number;
  suggested_subject_item_id?: number | null;
  subject_item_id?: number | null;
  status?: string;
  ocr_text?: string | null;
};

export type PdfPacketSegmentUploadResult = {
  segment: PdfPacketSegment;
  file: FileRecord;
};
