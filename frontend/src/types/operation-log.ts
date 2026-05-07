export type OperationLog = {
  id: number;
  user_id: number | null;
  username: string | null;
  action: string;
  target_type: string | null;
  target_id: number | null;
  project_id: number | null;
  center_id: number | null;
  ip_address: string | null;
  user_agent: string | null;
  detail_json: Record<string, unknown> | null;
  created_at: string;
};

export type OperationLogList = {
  items: OperationLog[];
  total: number;
  limit: number;
  offset: number;
};

export type OperationLogFilters = {
  user_id?: number;
  username?: string;
  action?: string;
  target_type?: string;
  target_id?: number;
  project_id?: number;
  center_id?: number;
  created_from?: string;
  created_to?: string;
  limit?: number;
  offset?: number;
};
