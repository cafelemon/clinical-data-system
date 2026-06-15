export type DocumentFieldStatus = "extracted" | "needs_input" | "confirmed";

export type DocumentExtractedField = {
  id: number;
  file_version_id: number | null;
  pdf_packet_segment_id: number | null;
  document_type: string;
  field_key: string;
  field_label: string;
  value_type: string;
  raw_value: string | null;
  normalized_value: string | null;
  source_page_no: number | null;
  source_text: string | null;
  confidence: number;
  status: DocumentFieldStatus;
  manually_edited: boolean;
  confirmed_by: number | null;
  confirmed_at: string | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
};

export type DocumentExtractedFieldUpdate = {
  raw_value?: string | null;
  normalized_value?: string | null;
  status?: DocumentFieldStatus | null;
};
