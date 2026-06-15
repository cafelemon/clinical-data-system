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

export type PdfPacketSegmentSplitItem = {
  page_start: number;
  page_end: number;
  subject_item_id?: number | null;
  detected_name?: string | null;
};

export type PdfPacketSegmentSplitPayload = {
  splits: PdfPacketSegmentSplitItem[];
};

export type PdfPacketSegmentMergePayload = {
  segment_ids: number[];
  subject_item_id?: number | null;
  detected_name?: string | null;
};

export type PdfPacketAnalysisPage = {
  page_no: number;
  doc_type: string | null;
  display_name: string | null;
  target_code: string | null;
  confidence: number;
  matched_title: string[];
  title_locations?: string[];
  matched_features: string[];
  negative_hits: string[];
  reason: string;
  raw_text?: string;
  normalized_text?: string;
  head_lines?: string[];
  tail_lines?: string[];
};

export type PdfPacketAnalysisSegment = {
  page_start: number;
  page_end: number;
  detected_name: string | null;
  detected_code: string | null;
  confidence: number;
  doc_type?: string | null;
  reason?: string;
  page_reasons?: string[];
};

export type PdfPacketAnalysisReport = {
  generated_at: string;
  packet: {
    id: number;
    packet_id: string;
    original_name: string;
    screening_no: string;
    page_count: number;
  };
  text_page_count: number;
  pages: PdfPacketAnalysisPage[];
  segments: PdfPacketAnalysisSegment[];
};

export type PdfPacketSegmentUploadResult = {
  segment: PdfPacketSegment;
  file: FileRecord;
};
