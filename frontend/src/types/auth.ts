export type CurrentUser = {
  id: number;
  username: string;
  full_name: string | null;
  email: string | null;
  is_active: boolean;
  role_ids: number[];
  roles: string[];
  permissions: string[];
  project_ids: number[];
  center_ids: number[];
  is_admin: boolean;
  created_at: string;
  updated_at: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
};

export type Permission = {
  id: number;
  code: string;
  label: string;
  module: string;
  description: string | null;
};

export type Role = {
  id: number;
  name: string;
  label: string;
  description: string | null;
  system: boolean;
  permission_ids: number[];
  permissions: string[];
  created_at: string;
  updated_at: string;
};

export type RolePayload = {
  name: string;
  label: string;
  description?: string | null;
  permission_ids: number[];
};

export type User = {
  id: number;
  username: string;
  full_name: string | null;
  email: string | null;
  is_active: boolean;
  role_ids: number[];
  roles: string[];
  permissions: string[];
  project_ids: number[];
  center_ids: number[];
  created_at: string;
  updated_at: string;
};

export type UserPayload = {
  username: string;
  password?: string;
  full_name?: string | null;
  email?: string | null;
  is_active: boolean;
  role_ids: number[];
  project_ids: number[];
  center_ids: number[];
};

