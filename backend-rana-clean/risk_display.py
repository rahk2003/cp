"""تحويل مستويات الخطورة المخزّنة إلى مستويات العرض دون تعديل قاعدة البيانات."""

from __future__ import annotations

from typing import Any, Dict

STORED_RISKS = ("Critical", "High", "Medium", "Low")
DISPLAY_RISKS = ("NoSpill", "Low", "Medium", "High")

DISPLAY_RISK_SCORE_MAP = {
    "NoSpill": 0,
    "Low": 25,
    "Medium": 50,
    "High": 75,
}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ""))
    except Exception:
        return default


def has_detected_spill(row: Dict[str, Any]) -> bool:
    return to_float(row.get("area_m2")) > 0 or to_float(row.get("coverage_pct")) > 0


def normalize_stored_risk(value: Any) -> str:
    raw = str(value or "").strip().lower()
    for risk in STORED_RISKS:
        if raw == risk.lower():
            return risk
    if raw in {"حرج", "critical risk"}:
        return "Critical"
    if raw in {"عالي", "عالٍ", "عاجل", "high risk"}:
        return "High"
    if raw in {"متوسط", "medium risk"}:
        return "Medium"
    if raw in {"منخفض", "low risk"}:
        return "Low"
    if raw in {"nospill", "no_spill", "none", "لا يوجد تسرب"}:
        return "Low"
    return "Low"


def normalize_display_risk_param(value: Any) -> str:
    """معامل فلتر API: يقبل التسميات الجديدة والقديمة."""
    raw = str(value or "").strip().lower()
    if raw in {"nospill", "no_spill", "none", "لا يوجد تسرب"}:
        return "NoSpill"
    if raw in {"low", "منخفض"}:
        return "Low"
    if raw in {"medium", "متوسط"}:
        return "Medium"
    if raw in {"high", "عالي", "عالٍ", "عاجل"}:
        return "High"
    if raw == "critical" or raw == "حرج":
        return "High"
    return normalize_stored_risk(value) if raw else "Low"


def to_display_risk_level(row: Dict[str, Any]) -> str:
    if not has_detected_spill(row):
        return "NoSpill"
    stored = normalize_stored_risk(
        row.get("stored_risk_level")
        or row.get("final_risk_level")
        or row.get("risk_level")
    )
    if stored == "Critical":
        return "High"
    if stored == "High":
        return "Medium"
    if stored == "Medium":
        return "Low"
    return "Low"


def _stored_tier_to_display(stored: str) -> str:
    if stored == "Critical":
        return "High"
    if stored == "High":
        return "Medium"
    if stored == "Medium":
        return "Low"
    return "Low"


def apply_display_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    stored = normalize_stored_risk(out.get("final_risk_level") or out.get("risk_level"))
    out["stored_risk_level"] = stored
    display = to_display_risk_level(out)
    out["final_risk_level"] = display
    out["risk_level"] = display
    return out


def enrich_report_row_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
    """استخراج المساحة/التغطية من payload أو من جدول التسربات."""
    out = dict(row)
    payload = out.get("payload")
    if isinstance(payload, dict):
        if to_float(out.get("area_m2")) <= 0:
            out["area_m2"] = to_float(payload.get("area_m2"))
        if to_float(out.get("coverage_pct")) <= 0:
            out["coverage_pct"] = to_float(payload.get("coverage_pct"))
        if not out.get("risk_level") and payload.get("risk_level"):
            out["risk_level"] = payload.get("risk_level")
    return out


def apply_report_display_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    """تقارير: خطورة العرض من المستوى المخزّن + مساحة payload/DB."""
    out = enrich_report_row_metrics(row)
    stored = normalize_stored_risk(out.get("risk_level") or out.get("final_risk_level"))
    out["stored_risk_level"] = stored
    if has_detected_spill(out):
        display = to_display_risk_level(out)
    else:
        display = _stored_tier_to_display(stored)
    out["final_risk_level"] = display
    out["risk_level"] = display
    return out


def infer_display_risk_score(row: Dict[str, Any]) -> float:
    explicit = to_float(row.get("risk_score"), -1)
    if explicit >= 0 and row.get("stored_risk_level"):
        display = to_display_risk_level(row)
        base = DISPLAY_RISK_SCORE_MAP.get(display, 0)
        area_bonus = min(to_float(row.get("area_m2"), 0) / 1000, 20)
        coverage_bonus = min(to_float(row.get("coverage_pct"), 0) * 2, 20)
        return float(base + area_bonus + coverage_bonus)
    display = to_display_risk_level(row)
    base = DISPLAY_RISK_SCORE_MAP.get(display, 0)
    area_bonus = min(to_float(row.get("area_m2"), 0) / 1000, 20)
    coverage_bonus = min(to_float(row.get("coverage_pct"), 0) * 2, 20)
    return float(base + area_bonus + coverage_bonus)
