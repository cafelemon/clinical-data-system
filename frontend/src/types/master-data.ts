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
  sort_order: number;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type StagePayload = {
  project_id: number;
  name: string;
  code: string;
  sort_order: number;
  description?: string | null;
};

export type StageTemplate = {
  id: number;
  project_id: number;
  stage_id: number;
  item_name: string;
  item_code: string;
  required: boolean;
  sort_order: number;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type StageTemplatePayload = {
  project_id: number;
  stage_id: number;
  item_name: string;
  item_code: string;
  required: boolean;
  sort_order: number;
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

