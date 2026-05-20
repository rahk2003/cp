import type { RiskLevel } from "@/types";

/** مستويات الخطورة المعروضة في الواجهة (بعد إعادة التصنيف). */
export const DISPLAY_RISK_LEVELS: RiskLevel[] = [
  "NoSpill",
  "Low",
  "Medium",
  "High",
];

const STORED_LEVELS = ["Critical", "High", "Medium", "Low"] as const;
type StoredRisk = (typeof STORED_LEVELS)[number];

export function hasDetectedSpill(areaM2: number, coveragePct: number): boolean {
  return (Number(areaM2) || 0) > 0 || (Number(coveragePct) || 0) > 0;
}

function normalizeStoredRisk(value: unknown): StoredRisk {
  const raw = String(value ?? "").trim().toLowerCase();
  for (const risk of STORED_LEVELS) {
    if (raw === risk.toLowerCase()) return risk;
  }
  if (raw === "حرج") return "Critical";
  if (raw === "عالي" || raw === "عالٍ" || raw === "عاجل") return "High";
  if (raw === "متوسط") return "Medium";
  if (raw === "منخفض") return "Low";
  return "Low";
}

/** تحويل مستوى مخزّن + مقاييس الكشف → مستوى العرض. */
export function toDisplayRiskLevel(
  storedOrDisplay: unknown,
  areaM2 = 0,
  coveragePct = 0
): RiskLevel {
  const raw = String(storedOrDisplay ?? "").trim();
  if (
    raw === "NoSpill" ||
    raw.toLowerCase() === "nospill" ||
    raw === "لا يوجد تسرب"
  ) {
    return "NoSpill";
  }
  const stored = normalizeStoredRisk(storedOrDisplay);
  if (!hasDetectedSpill(areaM2, coveragePct)) {
    if (stored === "Low") return "NoSpill";
    return storedTierToDisplay(stored);
  }
  return storedTierToDisplay(stored);
}

function storedTierToDisplay(stored: StoredRisk): RiskLevel {
  switch (stored) {
    case "Critical":
      return "High";
    case "High":
      return "Medium";
    case "Medium":
      return "Low";
    case "Low":
      return "Low";
    default:
      return "Low";
  }
}

export function normalizeDisplayRisk(
  value: unknown,
  areaM2 = 0,
  coveragePct = 0
): RiskLevel {
  const raw = String(value ?? "").trim();
  const direct = DISPLAY_RISK_LEVELS.find(
    (r) => r.toLowerCase() === raw.toLowerCase()
  );
  if (direct) {
    if (direct === "NoSpill") return "NoSpill";
    // مستوى عرض جاهز من الخادم (تقارير/خريطة) — لا نُعيده «لا يوجد تسرب» لغياب area في JSON
    return direct;
  }
  return toDisplayRiskLevel(value, areaM2, coveragePct);
}

/** خطورة التقرير: تستخدم مساحة الـ payload إن وُجدت. */
export function normalizeReportRisk(
  value: unknown,
  payload?: Record<string, unknown> | null
): RiskLevel {
  const areaM2 = Number(payload?.area_m2) || 0;
  const coveragePct = Number(payload?.coverage_pct) || 0;
  return normalizeDisplayRisk(value, areaM2, coveragePct);
}

export function riskLabel(level: RiskLevel, lang: "ar" | "en"): string {
  if (lang === "ar") {
    return {
      NoSpill: "لا يوجد تسرب",
      Low: "منخفض",
      Medium: "متوسط",
      High: "عالي",
    }[level];
  }
  return {
    NoSpill: "No spill",
    Low: "Low",
    Medium: "Medium",
    High: "High",
  }[level];
}
