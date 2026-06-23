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

export type ImageEvidenceType =
  | "raw_package"
  | "enhanced_package"
  | "report_package"
  | "report_image"
  | "marked_image"
  | "landmark_image";

export type LandmarkCandidate = {
  candidate_key: string;
  score: number;
  enhanced_relative_path: string;
  raw_relative_path: string;
  filename: string;
  camera: string;
  frame_no: number;
  clock_seconds: number;
};

export type ImageEvidence = {
  id: number;
  project_id: number;
  center_id: number;
  subject_id: number;
  subject_image_record_id: number;
  evidence_type: ImageEvidenceType;
  evidence_source: string | null;
  relative_path: string | null;
  match_status: "resolved" | "approx_matched" | "unresolved" | "not_supported" | null;
  file_hash: string | null;
  file_size: number | null;
  gastrointestinal_location: string | null;
  payload_json: {
    elapsed_time?: string;
    marked?: boolean;
    manually_confirmed?: boolean;
    selected_candidate_key?: string | null;
    selected_candidate?: LandmarkCandidate | null;
    candidates?: LandmarkCandidate[];
    [key: string]: unknown;
  } | null;
  indexed_by: number | null;
  indexed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LandmarkIndexResponse = {
  report_record_id: number;
  raw_record_id: number | null;
  enhanced_record_id: number | null;
  index_status:
    | "waiting_for_assets"
    | "indexed"
    | "partial"
    | "unresolved"
    | "not_supported"
    | "failed";
  counts: {
    resolved: number;
    approx_matched: number;
    unresolved: number;
    marked: number;
  };
  warning: string | null;
  evidence: ImageEvidence[];
};
