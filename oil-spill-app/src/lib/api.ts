/**
 * NaftScan API Client
 * Connects the frontend to Rana's FastAPI backend on http://localhost:8000
 *
 * All endpoints are documented in the backend's main.py:
 *   GET  /                           - root / health
 *   GET  /api/debug/db                - db diagnostic
 *   GET  /api/spills?risk=&limit=...  - list spills
 *   GET  /api/spills/{spill_id}       - single spill
 *   POST /api/analyze-image           - multipart upload
 *   POST /api/chat                    - smart router (DB/RAG/guide)
 *   POST /api/generate-report         - create report
 *   GET  /api/reports                 - list reports
 *   GET  /api/reports/{id}            - report HTML
 *   DELETE /api/reports/{id}          - delete report
 *   POST /api/restore-spills          - restore spills from CSV
 *   (response plan is embedded in unified /api/generate-report HTML)
 *   GET  /api/rag/health
 *   POST /api/rag/ask
 */
import { inferSeaRegion } from "@/lib/seas";
import { normalizeDisplayRisk, normalizeReportRisk } from "@/lib/riskLevels";
import type {
  ChatClarificationOption,
  ChatSource,
  RiskLevel,
  SpillRecord,
  ReportRecord,
} from "@/types";

export type { ReportRecord } from "@/types";

// Vite proxies /api → http://localhost:8000 in dev (see vite.config.ts).
// In production, set VITE_API_BASE_URL in your .env.
const API_BASE: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ||
  "";

function url(path: string): string {
  if (!path.startsWith("/")) path = "/" + path;
  return `${API_BASE}${path}`;
}

async function readApiError(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  try {
    const body = JSON.parse(text) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string" && body.detail.trim()) {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail.length > 0) {
      return body.detail
        .map((d) => (typeof d === "object" && d?.msg ? d.msg : String(d)))
        .join("; ");
    }
  } catch {
    /* not JSON */
  }
  return `${res.status} ${res.statusText} ${text}`.trim();
}

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(await readApiError(res));
  }
  return res.json();
}

// ============================================================
// Spills
// ============================================================

interface ApiSpill {
  id: string | number;
  spill_id?: string;
  filename: string;
  latitude: number | null;
  longitude: number | null;
  area_m2: number | null;
  coverage_pct: number | null;
  distance_to_land_km: number | null;
  distance_to_coral_km: number | null;
  land_proximity_class?: string;
  coral_risk_class?: string;
  final_risk_level: string;
  risk_level?: string;
  risk_score?: number;
  created_at?: string;
  source_image_path?: string | null;
  predicted_mask_path?: string | null;
}

function normalizeRisk(
  v: unknown,
  areaM2 = 0,
  coveragePct = 0
): RiskLevel {
  return normalizeDisplayRisk(v, areaM2, coveragePct);
}

function inferRegion(lat: number, lon: number): string {
  return inferSeaRegion(lat, lon) ?? "Open Sea";
}

function toSpillRecord(s: ApiSpill): SpillRecord {
  const lat = typeof s.latitude === "number" ? s.latitude : 0;
  const lon = typeof s.longitude === "number" ? s.longitude : 0;
  const id = String(s.spill_id || s.id || s.filename);
  return {
    id,
    filename: s.filename || id,
    latitude: lat,
    longitude: lon,
    area_m2: Number(s.area_m2) || 0,
    coverage_pct: Number(s.coverage_pct) || 0,
    distance_to_land_km: Number(s.distance_to_land_km) || 0,
    distance_to_coral_km: Number(s.distance_to_coral_km) || 0,
    land_proximity_class: s.land_proximity_class || "Unknown",
    coral_risk_class: s.coral_risk_class || "Unknown",
    final_risk_level: normalizeRisk(
      s.final_risk_level || s.risk_level,
      Number(s.area_m2) || 0,
      Number(s.coverage_pct) || 0
    ),
    detected_at: s.created_at || new Date().toISOString(),
    centroid: [lat, lon],
    region: inferRegion(lat, lon),
    risk_score: s.risk_score,
    spill_id: s.spill_id,
    created_at: s.created_at,
    source_image_path: s.source_image_path,
    predicted_mask_path: s.predicted_mask_path,
  };
}

export async function fetchSpills(opts?: {
  risk?: "all" | RiskLevel;
  limit?: number;
  offset?: number;
}): Promise<{ count: number; spills: SpillRecord[] }> {
  const params = new URLSearchParams();
  params.set("risk", opts?.risk ?? "all");
  // اجلب كل السجلات — القاعدة ~1200+ نقطة والحد القديم 1200 كان يقطع 12+ تسرب
  params.set("limit", String(opts?.limit ?? 10000));
  params.set("offset", String(opts?.offset ?? 0));
  const data = await jsonFetch<{ count: number; spills: ApiSpill[]; error?: string }>(
    `/api/spills?${params}`
  );
  if (data.error) {
    console.warn("[api] /api/spills returned error:", data.error);
  }
  return {
    count: data.count || 0,
    spills: (data.spills || []).map(toSpillRecord),
  };
}

export async function fetchSpill(spillId: string): Promise<SpillRecord> {
  const data = await jsonFetch<ApiSpill>(`/api/spills/${encodeURIComponent(spillId)}`);
  return toSpillRecord(data);
}

// ============================================================
// Analyze image
// ============================================================

export interface AnalyzeResult {
  id: string;
  filename: string;
  source?: string;
  message?: string;
  saved_path?: string;
  original_preview_url?: string;
  mask_preview_url?: string;
  overlay_preview_url?: string;
  latitude: number;
  longitude: number;
  area_m2: number;
  coverage_pct: number;
  distance_to_land_km: number;
  distance_to_coral_km: number;
  final_risk_level: RiskLevel;
  processed_at: string;
  coordinate_source?: string;
  coordinate_crs?: string;
  coordinate_error?: string;
  db_saved?: boolean;
  db_action?: "created" | "updated";
}

export interface SaveAnalysisResponse {
  ok: boolean;
  action: "created" | "updated";
  spill: SpillRecord;
}

export async function analyzeImage(file: File): Promise<AnalyzeResult> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(url("/api/analyze-image"), {
    method: "POST",
    body: fd,
  });
  if (!res.ok) {
    throw new Error(await readApiError(res));
  }
  const data = await res.json();
  const areaM2 = Number(data.area_m2) || 0;
  const coveragePct = Number(data.coverage_pct) || 0;
  return {
    ...data,
    final_risk_level: normalizeRisk(
      data.final_risk_level,
      areaM2,
      coveragePct
    ),
  };
}

export async function saveAnalyzedSpill(
  payload: AnalyzeResult
): Promise<SaveAnalysisResponse> {
  const data = await jsonFetch<SaveAnalysisResponse>("/api/save-analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return {
    ...data,
    spill: toSpillRecord(data.spill as unknown as ApiSpill),
  };
}

// ============================================================
// Chat (Smart Router)
// ============================================================

export interface ChatApiRequest {
  message: string;
  spill_id?: string;
  compare_spill_ids?: string[];
  language?: "ar" | "en";
  top_k?: number;
  history?: Array<{
    role: "user" | "assistant" | "system";
    content: string;
    context_spill_id?: string;
    intent?: string;
    source_used?: string;
    resolved_spill_id?: string;
  }>;
}

export interface ChatApiResponse {
  ok: boolean;
  source_used: string;
  reply: string;
  intent?: string;
  route?: string;
  needs_clarification?: boolean;
  clarification_options?: ChatClarificationOption[];
  used_search?: boolean;
  resolved_spill_id?: string;
  sources?: ChatSource[];
}

export async function sendChat(payload: ChatApiRequest): Promise<ChatApiResponse> {
  return jsonFetch<ChatApiResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ============================================================
// Reports
// ============================================================

interface ApiReport {
  id?: string | number;
  report_id: string;
  spill_id: string;
  filename: string;
  risk_level: string;
  language: string;
  created_at: string;
  content?: string;
  summary?: string;
  payload?: ReportRecord["payload"];
  image_asset?: string;
  image_assets?: ReportRecord["image_assets"];
}

function toReportRecord(r: ApiReport): ReportRecord {
  const langRaw = String(r.language || "ar").toLowerCase();
  const language: "AR" | "EN" = langRaw === "ar" ? "AR" : "EN";
  return {
    id: String(r.report_id || r.id || ""),
    spill_id: String(r.spill_id || ""),
    filename: r.filename || "",
    risk_level: normalizeReportRisk(
      r.risk_level,
      (r.payload as Record<string, unknown> | undefined) ?? undefined
    ),
    language,
    generated_at: r.created_at || new Date().toISOString(),
    summary: r.summary || (r.content ? r.content.slice(0, 240) : ""),
    content: r.content,
    payload: r.payload,
    image_asset: r.image_asset,
    image_assets: r.image_assets,
  };
}

export async function fetchReports(): Promise<{ count: number; reports: ReportRecord[] }> {
  const data = await jsonFetch<{ count: number; reports: ApiReport[] }>("/api/reports");
  return {
    count: data.count || 0,
    reports: (data.reports || []).map(toReportRecord),
  };
}

export function reportHtmlUrl(reportId: string): string {
  return url(`/api/reports/${encodeURIComponent(reportId)}`);
}

export async function restoreSpillsFromCsv(): Promise<{
  status: string;
  rows_imported: number;
  db_count: number;
  api_count: number;
}> {
  return jsonFetch("/api/restore-spills", { method: "POST" });
}

export async function deleteReport(
  reportId: string
): Promise<{ ok: boolean; deleted: boolean; report_id: string }> {
  return jsonFetch(`/api/reports/${encodeURIComponent(reportId)}`, {
    method: "DELETE",
  });
}

export function reportAssetUrl(assetOrPath: string): string {
  const s = assetOrPath.trim();
  if (s.startsWith("http://") || s.startsWith("https://")) return s;
  if (s.startsWith("/api/")) return url(s);
  return url(`/api/llm-report-assets/${encodeURIComponent(s)}`);
}

export async function generateReport(
  spill_id: string,
  language: "ar" | "en" = "ar"
): Promise<ReportRecord> {
  const data = await jsonFetch<ApiReport>("/api/generate-report", {
    method: "POST",
    body: JSON.stringify({ spill_id, language }),
  });
  return toReportRecord(data);
}

// ============================================================
// Unified report payload (embedded in generate-report response)
// ============================================================

export interface SolutionsResponse {
  spill_id: string;
  filename?: string;
  risk_level: string;
  priority?: string;
  priority_window?: string;
  source: string;
  summary?: string;
  risk_drivers?: string[];
  objectives?: string[];
  immediate: string[];
  short_term: string[];
  long_term: string[];
  monitoring?: string[];
  equipment: string[];
  agencies: string[];
  web_plan?: string | null;
  web_plan_status?: string;
  web_plan_note?: string;
  area_m2?: number;
  coverage_pct?: number;
  distance_to_land_km?: number;
  distance_to_coral_km?: number;
  latitude?: number;
  longitude?: number;
}

// ============================================================
// Health
// ============================================================

export interface RootHealth {
  name: string;
  state: string;
  status: Record<string, boolean>;
  database: boolean;
  error?: string | null;
  spills_count: number;
}

export async function fetchHealth(): Promise<RootHealth> {
  return jsonFetch<RootHealth>("/");
}
