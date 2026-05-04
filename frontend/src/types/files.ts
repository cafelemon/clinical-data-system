export type FileRecord = {
  id: number;
  file_id: string;
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
  subject_id: number | null;
  stage_id: number | null;
  stage_file_id: number | null;
  subject_item_id: number | null;
  file_category: string;
  version: number;
  uploaded_by: number | null;
  uploaded_at: string;
  status: string;
};

export type FileVersion = {
  id: number;
  file_id: number;
  version: number;
  storage_path: string;
  file_hash: string;
  file_size: number;
  mime_type: string;
  original_name: string;
  stored_name: string;
  uploaded_by: number | null;
  uploaded_at: string;
  change_note: string | null;
};

export type FileQuery = {
  project_id?: number;
  center_id?: number;
  subject_id?: number;
  stage_file_id?: number;
  subject_item_id?: number;
  file_category?: string;
  status?: string;
};
