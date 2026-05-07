export type Project = {
  id: number;
  name: string;
  code: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ProjectPayload = {
  name: string;
  code: string;
  description?: string | null;
  status: string;
};

export type Center = {
  id: number;
  project_id: number;
  name: string;
  code: string;
  contact_person: string | null;
  status: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type CenterPayload = {
  project_id: number;
  name: string;
  code: string;
  contact_person?: string | null;
  status: string;
  description?: string | null;
};

export type Stage = {
  id: number;
  project_id: number;
  name: string;
  code: string;
  parent_id: number | null;
  phase_code: string | null;
  option_code: string | null;
  is_system: boolean;
  enabled: boolean;
  sort_order: number;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type StagePayload = {
  project_id: number;
  phase_code?: string | null;
  parent_id?: number | null;
  option_code?: string | null;
  name?: string | null;
  code?: string | null;
  sort_order?: number | null;
  enabled?: boolean;
  description?: string | null;
};

export type StageOption = {
  phase_code: string;
  option_code: string;
  name: string;
  sort_order: number;
  default_enabled: boolean;
  description: string | null;
};

export type StageOptionGroup = {
  phase_code: string;
  phase_name: string;
  sort_order: number;
  options: StageOption[];
};

export type StageTemplate = {
  id: number;
  project_id: number;
  stage_id: number;
  item_name: string;
  item_code: string;
  template_scope: "center_file" | "subject_item";
  required: boolean;
  sort_order: number;
  recognition_keywords: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type StageTemplatePayload = {
  project_id: number;
  stage_id: number;
  item_name: string;
  item_code: string;
  template_scope: "center_file" | "subject_item";
  required: boolean;
  sort_order: number;
  recognition_keywords?: string | null;
  description?: string | null;
};

export type DictionaryItem = {
  id: number;
  dict_type: string;
  value: string;
  label: string;
  color: string | null;
  sort_order: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type DictionaryPayload = {
  dict_type: string;
  value: string;
  label: string;
  color?: string | null;
  sort_order: number;
  enabled: boolean;
};
