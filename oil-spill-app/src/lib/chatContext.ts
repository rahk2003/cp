/** مفتاح الحالة المستخدم في API الشات والوكيل (يفضّل اسم الملف). */
export function spillContextKey(spill: {
  id?: string;
  filename?: string;
  spill_id?: string;
}): string {
  return String(spill.filename || spill.spill_id || spill.id || "").trim();
}

/** حالة تحليل حديثة قبل ظهورها في قائمة الخريطة (جلسة المتصفح فقط). */
export const PENDING_SPILL_SESSION_KEY = "naftscan_pending_spill_v1";

export interface PendingSpillContext {
  spill_id: string;
  filename: string;
  area_m2?: number;
  coverage_pct?: number;
  final_risk_level?: string;
  latitude?: number;
  longitude?: number;
  distance_to_land_km?: number;
  distance_to_coral_km?: number;
}

export function stashPendingSpillForChat(spill: PendingSpillContext): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(PENDING_SPILL_SESSION_KEY, JSON.stringify(spill));
}

export function readPendingSpillForChat(): PendingSpillContext | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PENDING_SPILL_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingSpillContext;
    if (!parsed?.spill_id && !parsed?.filename) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearPendingSpillForChat(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(PENDING_SPILL_SESSION_KEY);
}

export function reportSpillKey(report: {
  spill_id?: string;
  filename?: string;
  id?: string;
}): string {
  return String(report.spill_id || report.filename || report.id || "").trim();
}

export function chatbotPath(opts?: { spillId?: string; reportId?: string }): string {
  const params = new URLSearchParams();
  const spillId = opts?.spillId?.trim();
  const reportId = opts?.reportId?.trim();
  if (spillId) params.set("spill_id", spillId);
  if (reportId) params.set("report_id", reportId);
  const qs = params.toString();
  return qs ? `/chatbot?${qs}` : "/chatbot";
}
