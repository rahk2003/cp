#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
oil_solution_reports_same_template_no_images.py

ملف واحد يولد تقارير HTML عربية عن الاستجابة للتسرب النفطي بنفس شكل قالب
arabic_response_plan.html، لكن بدون صور وبدون نسخ أو ربط أي ملفات مرئية.

الفكرة:
1) الاتصال بقاعدة PostgreSQL/PostGIS.
2) قراءة حالات التسرب من جدول spill_analysis_results أو أي جدول تحددينه.
3) ترتيب الحالات حسب أولوية الاستجابة.
4) توليد تقرير HTML لكل حالة بنفس قالب تقرير الاستجابة.
5) توليد ملف index.html يجمع كل التقارير + ملفات JSON + summary.csv.

تشغيل سريع:
python oil_solution_reports_same_template_no_images.py --limit 150 --output-dir final_response_reports_150

تشغيل مع اسم جدول مختلف:
python oil_solution_reports_same_template_no_images.py --table spill_analysis_results --limit 150

مهم:
- هذا السكربت لا يعرض صور ولا يبحث في visual_reports ولا ينسخ أي صورة.
- خيار --visual-dir موجود فقط حتى لا يتعطل الأمر القديم لو كتبتيه، لكنه مهمل.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# ============================================================
# Defaults
# ============================================================

DEFAULT_DB_NAME = os.getenv("DB_NAME", "oil_spills")
DEFAULT_DB_USER = os.getenv("DB_USER", "postgres")
DEFAULT_DB_PASSWORD = os.getenv("DB_PASSWORD", os.getenv("PGPASSWORD", ""))
DEFAULT_DB_HOST = os.getenv("DB_HOST", "localhost")
DEFAULT_DB_PORT = os.getenv("DB_PORT", "5432")
DEFAULT_DB_TABLE = os.getenv("DB_TABLE", "spill_analysis_results")

HTML_REPORT_TITLE = "تقرير الاستجابة للتسرب النفطي"

TRUSTED_RESPONSE_SOURCES = [
    {
        "title": "NOAA - Spill Containment Methods",
        "desc": "مرجع للحواجز العائمة والكاشطات وطرق احتواء النفط.",
        "url": "https://response.restoration.noaa.gov/oil-and-chemical-spills/oil-spills/spill-containment-methods.html",
    },
    {
        "title": "ITOPF - Containment & Recovery",
        "desc": "مرجع للاستجابة البحرية باستخدام الحواجز والكاشطات.",
        "url": "https://www.itopf.org/knowledge-resources/documents-guides/response-techniques/containment-recovery/",
    },
    {
        "title": "ITOPF - Shoreline Clean-Up and Response",
        "desc": "مرجع لمراحل تنظيف السواحل بعد التسربات النفطية.",
        "url": "https://www.itopf.org/knowledge-resources/documents-guides/response-techniques/shoreline-clean-up-and-response/",
    },
]


# ============================================================
# Small utilities
# ============================================================

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_identifier(name: str) -> str:
    """Allow only simple table names or schema.table to avoid SQL injection."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", name):
        raise ValueError(f"اسم الجدول غير آمن: {name}")
    return name


def safe_slug(name: str) -> str:
    stem = Path(str(name)).stem
    stem = re.sub(r"[^A-Za-z0-9_\-.]+", "_", stem)
    return stem or "incident"


def to_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", "")
            if value == "" or value.lower() in {"nan", "none", "null", "unknown"}:
                return default
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    number = to_float(value, None)
    if number is None:
        return default
    return int(number)


def get_any(row: Dict[str, Any], keys: Iterable[str], default: Any = None) -> Any:
    """Get first available value from possible column names, case-insensitive."""
    if not row:
        return default
    lowered = {str(k).lower(): k for k in row.keys()}
    for key in keys:
        original = lowered.get(key.lower())
        if original is not None and row.get(original) is not None:
            return row.get(original)
    return default


def fmt_num(value: Any, decimals: int = 2, empty: str = "غير متوفر") -> str:
    number = to_float(value, None)
    if number is None:
        return empty
    if abs(number) >= 1000:
        return f"{number:,.{decimals}f}"
    return f"{number:.{decimals}f}"


def fmt_raw(value: Any, decimals: int = 2, empty: str = "غير متوفر") -> str:
    """Numbers without thousands comma, to look closer to the sample report."""
    number = to_float(value, None)
    if number is None:
        return empty
    text = f"{number:.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def fmt_pct(value: Any) -> str:
    number = to_float(value, None)
    if number is None:
        return "غير متوفر"
    return f"{number:.2f}"


def fmt_distance_m(value: Any) -> str:
    number = to_float(value, None)
    if number is None:
        return "غير متوفر"
    if number < 1000:
        return f"{number:.0f} م"
    return f"{number / 1000:.2f} كم"


def fmt_distance_for_card(value_m: Any, value_km: Any = None) -> str:
    if value_km is not None and to_float(value_km, None) is not None:
        return f"{fmt_raw(value_km)} كم"
    return fmt_distance_m(value_m)


def filename_from_row(row: Dict[str, Any], index: int) -> str:
    name = get_any(row, ["filename", "source_image", "image_name", "name"], None)
    if not name:
        name = f"incident_{index:04d}.tif"
    return Path(str(name)).name


# ============================================================
# Database
# ============================================================

def connect_db(args: argparse.Namespace):
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise SystemExit(
            "مكتبة psycopg2 غير مثبتة. ثبتيها داخل البيئة الحالية:\n"
            "pip install psycopg2-binary"
        ) from exc

    if args.database_url:
        return psycopg2.connect(args.database_url, cursor_factory=psycopg2.extras.RealDictCursor)

    return psycopg2.connect(
        dbname=args.db_name,
        user=args.db_user,
        password=args.db_password,
        host=args.db_host,
        port=args.db_port,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def fetch_db_rows(args: argparse.Namespace) -> List[Dict[str, Any]]:
    table = safe_identifier(args.table)
    scan_limit = max(args.limit * 4, args.limit, 300)
    query = f"SELECT * FROM {table} LIMIT %s"

    conn = connect_db(args)
    try:
        with conn.cursor() as cur:
            cur.execute(query, (scan_limit,))
            rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()
    return rows


# ============================================================
# Risk and priority logic
# ============================================================

def classify_distance_to_land(row: Dict[str, Any]) -> str:
    existing = get_any(row, ["land_proximity_class", "land_risk_class", "land_risk"], None)
    if existing:
        return str(existing)

    d = to_float(get_any(row, ["distance_to_land_m", "nearest_land_distance_m"], None), None)
    if d is None:
        return "غير متوفر"
    if d <= 0:
        return "ملامسة اليابسة"
    if d <= 500:
        return "قريب جدًا"
    if d <= 1000:
        return "قريب"
    if d <= 5000:
        return "متوسط القرب"
    if d <= 20000:
        return "بعيد نسبيًا"
    return "بعيد جدًا"


def classify_coral_risk(row: Dict[str, Any]) -> str:
    existing = get_any(row, ["coral_risk_class", "nearest_coral_risk", "coral_risk"], None)
    if existing:
        return str(existing)

    d = to_float(get_any(row, ["nearest_coral_distance_m", "distance_to_coral_m", "coral_distance_m"], None), None)
    if d is None:
        return "غير متوفر"
    if d <= 500:
        return "قريب جدًا"
    if d <= 1000:
        return "قريب"
    if d <= 5000:
        return "متوسط القرب"
    if d <= 20000:
        return "بعيد نسبيًا"
    return "بعيد"


def is_land_sensitive(summary: Dict[str, Any]) -> bool:
    d = to_float(summary.get("distance_to_land_m"), None)
    cls = str(summary.get("land_class", ""))
    return (d is not None and d <= 1000) or any(word in cls for word in ["ملامسة", "يلامس", "قريب", "Touches", "touch"])


def is_coral_sensitive(summary: Dict[str, Any]) -> bool:
    d = to_float(summary.get("nearest_coral_distance_m"), None)
    cls = str(summary.get("coral_class", ""))
    return (d is not None and d <= 5000) or any(word in cls for word in ["قريب", "مرتفع", "عال", "high", "High"])


def compute_priority_score(row: Dict[str, Any]) -> float:
    area_m2 = to_float(get_any(row, ["area_m2", "spill_area_m2"], 0), 0) or 0
    coverage_pct = to_float(get_any(row, ["coverage_pct", "coverage_percent"], 0), 0) or 0
    density_score = to_float(get_any(row, ["density_score", "density"], 0), 0) or 0
    components = to_int(get_any(row, ["num_components", "components_count"], 0), 0)
    distance_land_m = to_float(get_any(row, ["distance_to_land_m", "nearest_land_distance_m"], None), None)
    distance_coral_m = to_float(get_any(row, ["nearest_coral_distance_m", "distance_to_coral_m", "coral_distance_m"], None), None)

    score = 0.0
    score += min(area_m2 / 10000.0, 30.0)
    score += min(coverage_pct * 1.5, 25.0)
    score += min(density_score * 10.0, 12.0)
    score += min(components * 1.2, 10.0)

    if distance_land_m is not None:
        if distance_land_m <= 0:
            score += 35
        elif distance_land_m <= 500:
            score += 30
        elif distance_land_m <= 1000:
            score += 24
        elif distance_land_m <= 5000:
            score += 15
        elif distance_land_m <= 20000:
            score += 6

    if distance_coral_m is not None:
        if distance_coral_m <= 500:
            score += 25
        elif distance_coral_m <= 1000:
            score += 20
        elif distance_coral_m <= 5000:
            score += 12
        elif distance_coral_m <= 20000:
            score += 5

    return round(score, 2)


def priority_label(score: float) -> str:
    if score >= 85:
        return "حرجة جدًا"
    if score >= 60:
        return "عالية"
    if score >= 35:
        return "متوسطة"
    return "منخفضة"


# ============================================================
# Report data
# ============================================================

def row_summary(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    filename = filename_from_row(row, index)
    score = compute_priority_score(row)
    return {
        "index": index,
        "filename": filename,
        "priority_score": score,
        "priority_label": priority_label(score),
        "area_m2": get_any(row, ["area_m2", "spill_area_m2"], None),
        "area_px": get_any(row, ["area_px", "spill_area_px"], None),
        "coverage_pct": get_any(row, ["coverage_pct", "coverage_percent"], None),
        "spill_centroid_lon": get_any(row, ["spill_centroid_lon", "longitude", "lon"], None),
        "spill_centroid_lat": get_any(row, ["spill_centroid_lat", "latitude", "lat"], None),
        "distance_to_land_m": get_any(row, ["distance_to_land_m", "nearest_land_distance_m"], None),
        "distance_to_land_km": get_any(row, ["distance_to_land_km", "nearest_land_distance_km"], None),
        "land_class": classify_distance_to_land(row),
        "nearest_coral_distance_m": get_any(row, ["nearest_coral_distance_m", "distance_to_coral_m", "coral_distance_m"], None),
        "nearest_coral_distance_km": get_any(row, ["nearest_coral_distance_km", "distance_to_coral_km", "coral_distance_km"], None),
        "coral_class": classify_coral_risk(row),
        "density_score": get_any(row, ["density_score", "density"], None),
        "compactness": get_any(row, ["compactness"], None),
        "spread_ratio": get_any(row, ["spread_ratio"], None),
        "orientation_deg": get_any(row, ["orientation_deg"], None),
        "num_components": get_any(row, ["num_components", "components_count"], None),
        "contours_count": get_any(row, ["contours_count", "predicted_contours", "num_contours"], None),
    }


def affected_ecosystems(summary: Dict[str, Any]) -> str:
    land = is_land_sensitive(summary)
    coral = is_coral_sensitive(summary)
    if land and coral:
        return "سواحل وشعاب مرجانية"
    if coral:
        return "شعاب مرجانية"
    if land:
        return "مناطق ساحلية"
    return "مياه بحرية مفتوحة"


def risk_basis(summary: Dict[str, Any]) -> str:
    land = is_land_sensitive(summary)
    coral = is_coral_sensitive(summary)
    if land and coral:
        return "مخاطر الساحل والشعاب"
    if land:
        return "مخاطر الساحل"
    if coral:
        return "مخاطر الشعاب"
    return "حجم البقعة ونسبة التغطية"


def coordinates_text(summary: Dict[str, Any]) -> str:
    lon = summary.get("spill_centroid_lon")
    lat = summary.get("spill_centroid_lat")
    if lon is None or lat is None:
        return "غير متوفر"
    return f"{fmt_raw(lon, 12)}، {fmt_raw(lat, 12)}"


def evidence_text(summary: Dict[str, Any]) -> str:
    return (
        f"المساحة المقدّرة: {fmt_raw(summary.get('area_m2'))} | "
        f"نسبة التغطية: {fmt_pct(summary.get('coverage_pct'))} | "
        f"المسافة إلى اليابسة: {fmt_raw(summary.get('distance_to_land_m'), 0)} | "
        f"خطر الساحل: {summary.get('land_class', 'غير متوفر')} | "
        f"المسافة إلى الشعاب المرجانية: {fmt_distance_for_card(summary.get('nearest_coral_distance_m'), summary.get('nearest_coral_distance_km'))} | "
        f"خطر الشعاب المرجانية: {summary.get('coral_class', 'غير متوفر')}"
    )


def missing_info_list(summary: Dict[str, Any]) -> List[str]:
    # نفس القائمة الظاهرة في القالب، لأنها فعلاً غير مستنتجة من بيانات المودل/القناع فقط.
    return [
        "نوع النفط",
        "مصدر التسرب",
        "حجم النفط",
        "الطقس",
        "التيارات",
        "زمن الحادث",
        "الحجم الحقيقي بالبراميل أو اللترات",
        "حالة الطقس والتيارات البحرية",
        "زمن بداية الحادث",
    ]


def build_report(row: Dict[str, Any], index: int) -> Dict[str, Any]:
    summary = row_summary(row, index)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    coords = coordinates_text(summary)

    executive_summary = (
        f"تم تحليل حالة تسرب نفطي في موقع {coords}، وتم تحديد أولوية الاستجابة بناءً على قرب المسافة من اليابسة "
        f"والشعاب المرجانية وحجم البقعة ونسبة التغطية. تم وضع خطة استجابة شاملة لاحتواء التسرب وتنظيف السواحل "
        f"وتقليل التأثير البيئي. الحالة مرتبطة بالملف: {summary['filename']}."
    )

    return {
        "metadata": {
            "generated_at": generated_at,
            "generator": "oil_solution_reports_same_template_no_images.py",
            "mode": "same_template_no_images",
        },
        "incident": summary,
        "executive_summary": executive_summary,
        "missing_info": missing_info_list(summary),
        "evidence": evidence_text(summary),
        "affected_ecosystems": affected_ecosystems(summary),
        "risk_basis": risk_basis(summary),
    }


# ============================================================
# HTML rendering helpers
# ============================================================

def list_items(items: Iterable[str]) -> str:
    return "".join(f"<li>{esc(item)}</li>" for item in items)


def card(label: str, value: Any) -> str:
    return f"<div class='card'><div class='label'>{esc(label)}</div><div>{esc(value)}</div></div>"


def action_card(title: str, reason: str, evidence: str) -> str:
    return f"""
        <div class="action">
            <div class="action-title">{esc(title)}</div>
            <div class="action-text"><strong>المبرر:</strong> {esc(reason)}</div>
            <div class="tag">الدليل: {esc(evidence)}</div>
        </div>
    """


def risk_card(title: str, evidence: str, mitigation: str) -> str:
    return f"""
        <div class="risk">
            <strong>{esc(title)}</strong><br>
            <span>الدليل: {esc(evidence)}</span><br>
            <span>التخفيف: {esc(mitigation)}</span>
        </div>
    """


def source_card(source: Dict[str, str]) -> str:
    return f"""
        <div class="ref">
            <strong>{esc(source['title'])}</strong><br>
            <span>{esc(source['desc'])}</span><br>
            <a href="{esc(source['url'])}" target="_blank" rel="noopener">{esc(source['url'])}</a>
        </div>
    """


def phase_sections(report: Dict[str, Any]) -> str:
    s = report["incident"]
    ev = report["evidence"]

    return f"""
        <section>
            <h2>المرحلة 1 - استجابة فورية</h2>
            <div class="time">0-24 ساعة</div>
            {action_card('تأكيد القناع والإحداثيات ومراجعة الصورة الأصلية قبل اتخاذ قرار ميداني', 'التحقق يقلل احتمال التعامل مع إنذار خاطئ أو قناع غير دقيق.', ev)}
            {action_card('تصعيد البلاغ للجهات البحرية والبيئية وإعطاء أولوية لحماية الساحل والشعاب المرجانية', 'قرب التسرب من اليابسة أو الشعاب يرفع خطورة الأثر البيئي.', ev)}
            {action_card('تنفيذ مراقبة جوية أو فضائية قصيرة المدى لتقدير اتجاه الانتشار', 'المراقبة المتكررة تساعد على معرفة هل البقعة ثابتة أو تتحرك نحو مناطق حساسة.', 'مركز التسرب + مساحة البقعة + نسبة التغطية')}
        </section>

        <section>
            <h2>المرحلة 2 - استجابة نشطة</h2>
            <div class="time">1-14 يوم</div>
            {action_card('تجهيز حواجز احتواء عائمة حول اتجاه انتشار البقعة متى ما سمحت حالة البحر', 'الحواجز تساعد على تقليل انتشار النفط وحماية السواحل والمناطق الحساسة.', ev)}
            {action_card('استخدام سفن مزودة بكاشطات أو معدات استرجاع لجمع النفط من سطح الماء', 'الاسترجاع الميكانيكي مناسب عندما يكون النفط عائمًا ومركزًا بما يكفي للجمع.', 'امتداد البقعة ومؤشرات التغطية من قاعدة البيانات')}
            {action_card('تحديد مناطق حماية ساحلية وشعابية ذات أولوية على الخريطة', 'توجيه الموارد للأماكن الحساسة أولًا يقلل الضرر البيئي.', 'المسافة إلى اليابسة + المسافة إلى الشعاب المرجانية')}
        </section>

        <section>
            <h2>المرحلة 3 - معالجة وتنظيف</h2>
            <div class="time">أسابيع إلى أشهر</div>
            {action_card('تنفيذ تنظيف ساحلي مرحلي حسب شدة التلوث وحساسية الموقع', 'التنظيف المرحلي يبدأ بإزالة النفط الكثيف ثم المواد الملوثة ثم التنظيف النهائي عند الحاجة.', 'تصنيف خطر الساحل وقرب التسرب من اليابسة')}
            {action_card('جمع وتوثيق مخلفات النفط والمواد الماصة ونقلها لمسار معالجة معتمد', 'إدارة المخلفات تمنع إعادة التلوث وتحافظ على سلامة الموقع.', 'نتائج الاستجابة الميدانية وربطها بسجل الحالة في قاعدة البيانات')}
            {action_card('إجراء تقييم بيئي للشعاب والمناطق الساحلية المتأثرة', 'الشعاب والمواطن الساحلية قد تتأثر حتى لو كان النفط محدود الامتداد.', 'coral_risk + land_risk')}
        </section>

        <section>
            <h2>المرحلة 4 - متابعة طويلة المدى</h2>
            <div class="time">أشهر إلى سنوات</div>
            {action_card('إنشاء متابعة زمنية بالصور الفضائية لمقارنة مساحة التسرب قبل وبعد المعالجة', 'الصور الزمنية تعطي قياسًا موضوعيًا لانخفاض المساحة والتغطية.', 'area_m2 + coverage_pct + predicted masks')}
            {action_card('تحديث قاعدة البيانات بنتائج الاستجابة والملاحظات الميدانية لتحسين التقارير القادمة', 'دمج بيانات الميدان مع مخرجات المودل يرفع جودة التحليل والتوصيات مستقبلًا.', 'PostgreSQL/PostGIS records')}
        </section>
    """


def risks_html(report: Dict[str, Any]) -> str:
    s = report["incident"]
    risks: List[str] = []

    if is_coral_sensitive(s):
        risks.append(risk_card("تأثير على الشعاب المرجانية", "قرب المسافة من الشعاب", "استخدام أساليب منخفضة التأثير وتجنب أي إجراء يزيد ترسيب النفط فوق الشعاب"))
    if is_land_sensitive(s):
        risks.append(risk_card("تأثير على السواحل", str(s.get("land_class", "قرب التسرب من اليابسة")), "تنظيف ساحلي مرحلي وحماية خط الساحل بالحواجز عند الإمكان"))

    area = to_float(s.get("area_m2"), 0) or 0
    coverage = to_float(s.get("coverage_pct"), 0) or 0
    if area >= 100000 or coverage >= 10:
        risks.append(risk_card("اتساع نطاق البقعة", "ارتفاع المساحة أو نسبة التغطية", "تقسيم منطقة العمل وتحديث الخطة بعد كل رصد جديد"))

    if not risks:
        risks.append(risk_card("احتمال تغير اتجاه الانتشار", "عدم توفر بيانات التيارات والطقس داخل السجل", "تكرار الرصد ومقارنة النتائج مع صور أحدث"))

    return "".join(risks)


def render_html_report(report: Dict[str, Any]) -> str:
    s = report["incident"]
    sources = "".join(source_card(src) for src in TRUSTED_RESPONSE_SOURCES)
    coords = coordinates_text(s)

    analysis_cards = "".join([
        card("امتداد التسرب", f"{fmt_raw(s.get('area_m2'))} متر مربع"),
        card("الموقع التقريبي", coords),
        card("الأنظمة البيئية المتأثرة", report["affected_ecosystems"]),
        card("أساس تقييم الخطورة", report["risk_basis"]),
    ])

    evidence_cards = "".join([
        card("المساحة المقدّرة", fmt_raw(s.get("area_m2"))),
        card("نسبة التغطية", fmt_pct(s.get("coverage_pct"))),
        card("المسافة إلى اليابسة", fmt_raw(s.get("distance_to_land_m"), 0)),
        card("خطر الساحل", s.get("land_class", "غير متوفر")),
        card("المسافة إلى الشعاب المرجانية", fmt_distance_for_card(s.get("nearest_coral_distance_m"), s.get("nearest_coral_distance_km"))),
        card("خطر الشعاب المرجانية", s.get("coral_class", "غير متوفر")),
        card("مؤشرات شكل البقعة", f"compactness: {fmt_raw(s.get('compactness'), 6)}، spread_ratio: {fmt_raw(s.get('spread_ratio'), 3)}"),
    ])

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>{esc(HTML_REPORT_TITLE)}</title>
<style>
body {{ font-family: 'Cairo', 'Segoe UI', Tahoma, sans-serif; background:#eef4f8; margin:0; color:#1f2937; line-height:1.8; }}
.container {{ max-width:1100px; margin:30px auto; background:white; border-radius:18px; overflow:hidden; box-shadow:0 10px 35px rgba(0,0,0,.08); }}
.header {{ background:linear-gradient(135deg,#0f766e,#1d4ed8); color:white; padding:35px; text-align:center; }}
.header h1 {{ margin:0; font-size:32px; }}
.header p {{ margin:8px 0 0; opacity:.9; }}
.content {{ padding:30px; }}
section {{ margin-bottom:28px; padding-bottom:22px; border-bottom:1px solid #e5e7eb; }}
h2 {{ color:#1d4ed8; margin-bottom:12px; }}
.summary {{ background:#dbeafe; border-right:5px solid #1d4ed8; padding:18px; border-radius:12px; font-size:17px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:12px; }}
.card {{ background:#f9fafb; border-right:4px solid #0f766e; padding:14px; border-radius:10px; min-height:92px; }}
.label {{ color:#6b7280; font-size:13px; font-weight:bold; margin-bottom:4px; }}
.muted {{ color:#6b7280; background:#f9fafb; padding:12px; border-radius:10px; }}
a {{ color:#0369a1; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.action {{ background:#f8fafc; border-right:4px solid #0284c7; padding:14px; border-radius:10px; margin:10px 0; }}
.action-title {{ font-weight:bold; color:#0f172a; }}
.action-text {{ color:#374151; }}
.tag {{ display:inline-block; margin-top:8px; background:#e0e7ff; color:#3730a3; padding:4px 9px; border-radius:8px; font-size:13px; }}
.risk {{ background:#fef2f2; border-right:4px solid #dc2626; padding:14px; border-radius:10px; margin:10px 0; }}
.case {{ background:#fffbeb; border-right:4px solid #f59e0b; padding:14px; border-radius:10px; margin:10px 0; }}
.ref {{ background:#f0fdf4; border-right:4px solid #16a34a; padding:14px; border-radius:10px; margin:10px 0; }}
.source {{ color:#0369a1; direction:ltr; text-align:left; margin-top:8px; word-break:break-all; }}
.time {{ display:inline-block; background:#0f766e; color:white; padding:5px 12px; border-radius:999px; margin-bottom:10px; }}
.footer {{ background:#f9fafb; padding:18px; color:#6b7280; text-align:center; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{esc(HTML_REPORT_TITLE)}</h1>
    <p>تحليل عربي مبني على تقرير HTML + قاعدة بيانات PostgreSQL/PostGIS</p>
    <p>الحالة: {esc(s.get('filename'))}</p>
    <p>تم التوليد: {esc(report['metadata']['generated_at'])}</p>
  </div>
  <div class="content">
    <section>
      <h2>الملخص التنفيذي</h2>
      <div class="summary">{esc(report['executive_summary'])}</div>
    </section>

    <section>
      <h2>تحليل الحادثة</h2>
      <div class="grid">{analysis_cards}</div>
    </section>

    <section>
      <h2>الأدلة من قاعدة البيانات</h2>
      <div class="grid">{evidence_cards}</div>
    </section>

    <section>
      <h2>المعلومات غير المتوفرة في البيانات</h2>
      <ul>{list_items(report['missing_info'])}</ul>
    </section>

    <section>
      <h2>مراجع أو حالات مشابهة</h2>
      <p class='muted'>لم يتم استخدام حالات تاريخية غير موثقة. التقرير اعتمد على قاعدة البيانات ومخرجات المودل، مع مراجع إرشادية عامة بالأسفل.</p>
    </section>

    <section>
      <h2>مصادر إرشادية موثوقة للاستجابة</h2>
      {sources}
    </section>

    {phase_sections(report)}

    <section>
      <h2>مخاطر يجب الانتباه لها</h2>
      {risks_html(report)}
    </section>

    <section>
      <h2>الجهات المعنية</h2>
      <ul>
        <li><strong>السلطات الساحلية</strong>: تنفيذ خطة الاستجابة وحماية خط الساحل.</li>
        <li><strong>الجهات البيئية</strong>: تقييم الأثر البيئي ومتابعة الشعاب والمناطق الحساسة.</li>
        <li><strong>فرق التشغيل البحري</strong>: نشر الحواجز والكاشطات وتنظيم جمع المخلفات.</li>
      </ul>
    </section>

    <section>
      <h2>فجوات المعرفة</h2>
      <ul>{list_items(report['missing_info'])}</ul>
    </section>
  </div>
  <div class="footer">Oil Spill Arabic Response Agent · للأغراض التحليلية والاستشارية · بدون صور</div>
</div>
</body>
</html>"""


# ============================================================
# Index and pipeline
# ============================================================

def render_index_html(items: List[Dict[str, Any]]) -> str:
    rows = ""
    for item in items:
        rows += f"""
        <tr>
            <td>{esc(item['index'])}</td>
            <td>{esc(item['filename'])}</td>
            <td>{esc(item['priority_label'])}</td>
            <td>{esc(item['priority_score'])}</td>
            <td>{esc(item['area_m2'])}</td>
            <td>{esc(item['coverage_pct'])}</td>
            <td><a href="{esc(item['html_rel'])}">فتح التقرير</a></td>
            <td><a href="{esc(item['json_rel'])}">JSON</a></td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>فهرس تقارير الاستجابة للتسرب النفطي</title>
<style>
body {{ font-family:'Cairo','Segoe UI',Tahoma,Arial,sans-serif; background:#eef4f8; margin:0; color:#1f2937; line-height:1.8; }}
.container {{ max-width:1180px; margin:30px auto; background:white; border-radius:18px; overflow:hidden; box-shadow:0 10px 35px rgba(0,0,0,.08); }}
.header {{ background:linear-gradient(135deg,#0f766e,#1d4ed8); color:white; padding:35px; text-align:center; }}
.content {{ padding:28px; overflow-x:auto; }}
.summary {{ background:#dbeafe; border-right:5px solid #1d4ed8; padding:18px; border-radius:12px; margin-bottom:20px; }}
table {{ width:100%; border-collapse:collapse; min-width:900px; }}
th,td {{ padding:12px; border-bottom:1px solid #e5e7eb; text-align:right; }}
th {{ background:#f8fafc; }}
a {{ color:#0369a1; font-weight:700; text-decoration:none; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>فهرس تقارير الاستجابة للتسرب النفطي</h1>
        <p>عدد التقارير المولدة: {len(items)}</p>
        <p>تم التوليد: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    <div class="content">
        <div class="summary">هذه الصفحة تجمع كل التقارير بنفس قالب الاستجابة، وبدون صور.</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>الصورة/الحالة</th>
                    <th>الأولوية</th>
                    <th>الدرجة</th>
                    <th>المساحة</th>
                    <th>التغطية</th>
                    <th>HTML</th>
                    <th>JSON</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
</div>
</body>
</html>"""


def save_summary_csv(items: List[Dict[str, Any]], output_dir: Path) -> None:
    if not items:
        return
    csv_path = output_dir / "summary.csv"
    fieldnames = [
        "index", "filename", "priority_label", "priority_score", "area_m2", "coverage_pct",
        "distance_to_land", "distance_to_coral", "html_rel", "json_rel",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow({key: item.get(key, "") for key in fieldnames})


def run(args: argparse.Namespace) -> Path:
    print("🛢️  Oil Spill Arabic Response Reports - Same Template / No Images")
    print("=" * 76)
    print(f"DB: {args.db_name} | table: {args.table}")
    print(f"Limit: {args.limit}")
    if args.visual_dir:
        print("ℹ️ تم تجاهل --visual-dir لأن هذا الإصدار لا يعرض ولا ينسخ الصور.")

    output_dir = Path(args.output_dir or f"response_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}").expanduser()
    reports_dir = output_dir / "reports"
    json_dir = output_dir / "json"
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    print("\n🗄️ قراءة البيانات من قاعدة البيانات...")
    rows = fetch_db_rows(args)
    if not rows:
        raise SystemExit("ما فيه صفوف راجعة من قاعدة البيانات. تأكدي من اسم الجدول والاتصال.")

    rows = sorted(rows, key=compute_priority_score, reverse=True)[: args.limit]
    print(f"✅ عدد الصفوف المختارة للتقارير: {len(rows)}")

    index_items: List[Dict[str, Any]] = []

    print("\n🧾 توليد التقارير بنفس القالب وبدون صور...")
    for i, row in enumerate(rows, start=1):
        filename = filename_from_row(row, i)
        slug = safe_slug(filename)
        html_path = reports_dir / f"{i:03d}_{slug}_response.html"
        json_path = json_dir / f"{i:03d}_{slug}_response.json"

        if args.resume and html_path.exists() and json_path.exists():
            print(f"⏭️ موجود مسبقًا: {i}/{len(rows)} - {filename}")
            report = json.loads(json_path.read_text(encoding="utf-8"))
        else:
            print(f"[{i}/{len(rows)}] {filename}")
            report = build_report(row, i)
            html_text = render_html_report(report)
            json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            html_path.write_text(html_text, encoding="utf-8")

        incident = report.get("incident", {})
        index_items.append({
            "index": i,
            "filename": filename,
            "priority_label": incident.get("priority_label", "غير متوفر"),
            "priority_score": incident.get("priority_score", ""),
            "area_m2": f"{fmt_raw(incident.get('area_m2'))} م²",
            "coverage_pct": fmt_pct(incident.get("coverage_pct")),
            "distance_to_land": fmt_distance_m(incident.get("distance_to_land_m")),
            "distance_to_coral": fmt_distance_for_card(incident.get("nearest_coral_distance_m"), incident.get("nearest_coral_distance_km")),
            "html_rel": f"reports/{html_path.name}",
            "json_rel": f"json/{json_path.name}",
        })

    (output_dir / "index.html").write_text(render_index_html(index_items), encoding="utf-8")
    save_summary_csv(index_items, output_dir)

    print("\n✅ تم الانتهاء")
    print(f"INDEX: {output_dir / 'index.html'}")
    print(f"REPORTS: {reports_dir}")
    print(f"JSON: {json_dir}")
    print(f"SUMMARY CSV: {output_dir / 'summary.csv'}")
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate Arabic oil-spill response reports using the same HTML template, with no images."
    )
    parser.add_argument("--limit", type=int, default=150, help="عدد التقارير المطلوب توليدها")
    parser.add_argument("--output-dir", default="final_response_reports_150", help="مجلد الإخراج")
    parser.add_argument("--table", default=DEFAULT_DB_TABLE, help="اسم جدول قاعدة البيانات")

    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"), help="DATABASE_URL اختياري بدل إعدادات الاتصال المفصلة")
    parser.add_argument("--db-name", default=DEFAULT_DB_NAME, help="اسم قاعدة البيانات")
    parser.add_argument("--db-user", default=DEFAULT_DB_USER, help="مستخدم PostgreSQL")
    parser.add_argument("--db-password", default=DEFAULT_DB_PASSWORD, help="كلمة مرور PostgreSQL أو استخدمي PGPASSWORD")
    parser.add_argument("--db-host", default=DEFAULT_DB_HOST, help="المضيف")
    parser.add_argument("--db-port", default=DEFAULT_DB_PORT, help="المنفذ")

    # موجود فقط حتى الأوامر القديمة التي فيها --visual-dir ما تتعطل.
    parser.add_argument("--visual-dir", default=None, help="مهمل في هذا الإصدار: لا يتم استخدام الصور")
    parser.add_argument("--no-resume", action="store_true", help="إعادة توليد التقارير حتى لو كانت موجودة")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.resume = not args.no_resume
    run(args)


if __name__ == "__main__":
    main()
