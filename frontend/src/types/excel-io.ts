export type ImportKind = "projects" | "centers" | "subjects" | "stage-templates";

export type ImportError = {
  row: number;
  field: string;
  message: string;
};

export type ImportResult = {
  total_rows: number;
  created_count: number;
  updated_count: number;
  skipped_count: number;
  errors: ImportError[];
};

export type ExportKind =
  | "project-progress"
  | "center-status"
  | "subject-completeness"
  | "missing-items";
