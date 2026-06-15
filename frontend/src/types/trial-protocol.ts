export type TrialProtocolItemDraft = {
  ordinal: number;
  name: string;
  required: boolean;
  enabled: boolean;
};

export type TrialProtocolVisitDraft = {
  ordinal: number;
  source_visit_code: string | null;
  name: string;
  window: string | null;
  enabled: boolean;
  items: TrialProtocolItemDraft[];
};

export type TrialProtocolCenterDraft = {
  code: string;
  name: string;
  filing_no: string | null;
  principal_investigator: string | null;
  enabled: boolean;
  confidence?: number | null;
  requires_confirmation?: boolean;
  confirmed?: boolean;
  evidence?: {
    page_no?: number;
    source?: string;
    risk_reasons?: string[];
    lines?: {
      page_no: number;
      text: string;
      source?: string;
      confidence?: number | null;
    }[];
  } | null;
};

export type TrialProtocolDraft = {
  visits: TrialProtocolVisitDraft[];
  centers: TrialProtocolCenterDraft[];
  deactivate_missing: {
    visits: boolean;
    items: boolean;
    centers: boolean;
  };
  parse_meta?: {
    text_source?: string;
    page_count?: number;
    center_count?: number;
    center_risk_count?: number;
    evidence_mode?: string;
  } | null;
};

export type TrialProtocolVersion = {
  id: number;
  project_id: number;
  version_number: number;
  original_name: string;
  file_hash: string;
  file_size: number;
  page_count: number;
  parsing_status: string;
  protocol_no: string | null;
  protocol_version: string | null;
  protocol_date: string | null;
  draft_json: TrialProtocolDraft;
  apply_result_json: Record<string, number> | null;
  uploaded_by: number | null;
  applied_by: number | null;
  uploaded_at: string;
  applied_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TrialProtocolVersionSummary = Omit<
  TrialProtocolVersion,
  "draft_json" | "uploaded_by" | "applied_by" | "created_at" | "updated_at"
>;

export type TrialProtocolApplyResult = {
  version: TrialProtocolVersion;
  result: Record<string, number>;
};
