/** مستوى الخطورة المعروض (بعد إعادة التصنيف). Critical القديم → High. */
export type RiskLevel = "NoSpill" | "Low" | "Medium" | "High";

export interface SpillRecord {
  id: string;
  filename: string;
  latitude: number;
  longitude: number;
  area_m2: number;
  coverage_pct: number;
  distance_to_land_km: number;
  distance_to_coral_km: number;
  land_proximity_class: string;
  coral_risk_class: string;
  final_risk_level: RiskLevel;
  detected_at: string;
  centroid: [number, number];
  region: string;
  // Optional backend extras
  risk_score?: number;
  spill_id?: string;
  created_at?: string;
  source_image_path?: string | null;
  predicted_mask_path?: string | null;
}

export interface ReportSolutionPayload {
  summary?: string;
  objectives?: string[];
  immediate?: string[];
  short_term?: string[];
  long_term?: string[];
  monitoring?: string[];
  equipment?: string[];
  agencies?: string[];
  operational_decision?: string;
  decision_badge?: string;
}

export interface ReportRecord {
  id: string;
  spill_id: string;
  filename: string;
  risk_level: RiskLevel;
  language: "EN" | "AR";
  generated_at: string;
  summary: string;
  content?: string;
  payload?: ReportSolutionPayload;
  report_type?: string;
  source?: string;
  image_asset?: string;
  image_assets?: { primary?: string; secondary?: string };
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  context_spill_id?: string;
  source_used?: string;
  intent?: string;
  used_search?: boolean;
  needs_clarification?: boolean;
  clarification_options?: ChatClarificationOption[];
  sources?: ChatSource[];
  resolved_spill_id?: string;
}

export type Lang = "en" | "ar";

export interface ChatSource {
  title?: string;
  url?: string;
  domain?: string;
  query?: string;
  note?: string;
  [k: string]: unknown;
}

export interface ChatClarificationOption {
  id: string;
  label: string;
}
