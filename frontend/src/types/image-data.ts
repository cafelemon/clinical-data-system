export type ImageDataType = "raw" | "enhanced" | "report";

export type SubjectImageRecord = {
  id: number;
  project_id: number;
  center_id: number;
  subject_id: number;
  image_type: ImageDataType;
  screening_no_snapshot: string;
  upload_status: "not_uploaded" | "uploaded" | string;
  original_name: string | null;
  stored_name: string | null;
  file_ext: string | null;
  mime_type: string | null;
  file_size: number;
  file_hash: string | null;
  storage_path: string | null;
  extracted_dir: string | null;
  version: number;
  image_count: number;
  image_total_size: number;
  image_extensions_json: Record<string, number> | null;
  parse_warning: string | null;
  source_raw_record_id: number | null;
  uploaded_by: number | null;
  uploaded_at: string | null;
  copied_by: number | null;
  copied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SubjectImageRow = {
  subject_id: number;
  project_id: number;
  center_id: number;
  screening_no: string;
  subject_arm: "experimental" | "control" | null;
  gender: string | null;
  age: number | null;
  record: SubjectImageRecord;
  raw_record: SubjectImageRecord | null;
};

export type SubjectImageUploadResult = {
  record: SubjectImageRecord;
};
