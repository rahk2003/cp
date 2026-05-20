import argparse
import html
import json
import os
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

import torch
import psycopg
from psycopg.rows import dict_row
from psycopg import sql

from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


# =========================================================
# SETTINGS - عدلي هنا فقط
# =========================================================

# =========================================================
# SETTINGS - عدلي هنا فقط
# =========================================================

BASE_MODEL_DIR = "/Users/rana/Documents/tuwaiq/CP/oil_llm_reporter/models/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "/Users/rana/Documents/tuwaiq/CP/oil_llm_reporter/oil_qwen_lora_adapter"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "oil_spills",
    "user": "postgres",
    "password": "1234"
}

TABLE_NAME = "spill_analysis_results"

VISUAL_REPORTS_DIR = Path(
    "/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/visual_reports"
)

OUTPUT_DIR = Path("./final_html_reports")
OUTPUT_IMAGES_DIR = OUTPUT_DIR / "images"

LIMIT_ROWS = 150

# =========================================================
# الترجمة - اختاري طريقة واحدة:
#   "nllb"   = ترجمة محلية بنموذج NLLB-200 (يحمل ~600MB أول مرة، يشتغل offline)
#   "google" = ترجمة سريعة عبر googletrans (يحتاج إنترنت، خفيف)
#   "none"   = بدون ترجمة (يطبع إنجليزي فقط)
# =========================================================
TRANSLATION_METHOD = "nllb"


# =========================================================
# MODEL
# =========================================================

def get_device():
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_llm():
    device = get_device()
    dtype = torch.float16 if device in ["mps", "cuda"] else torch.float32

    print("=" * 70)
    print("Loading local Qwen2.5 + Oil Spill LoRA")
    print(f"Device: {device}")
    print("=" * 70)

    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_DIR,
        local_files_only=True,
        trust_remote_code=True
    )

    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_DIR,
        local_files_only=True,
        dtype=dtype,
        trust_remote_code=True
    )

    model = PeftModel.from_pretrained(
        base_model,
        ADAPTER_DIR,
        local_files_only=True
    )

    model.to(device)
    model.eval()

    return tokenizer, model, device


# =========================================================
# TRANSLATION
# =========================================================

class Translator:
    """مترجم إنجليزي → عربي. يدعم 3 طرق."""

    def __init__(self, method="nllb"):
        self.method = (method or "nllb").strip().lower()
        self.model = None
        self.tokenizer = None
        self.google_translator = None

        if self.method == "none":
            print("Translation disabled. Reports will be in English only.", flush=True)
            return

        if self.method == "google":
            try:
                self._load_google()
                return
            except Exception as exc:
                print(
                    f"Google translator unavailable ({exc}). Falling back to NLLB.",
                    flush=True,
                )
                self.method = "nllb"

        if self.method == "nllb":
            try:
                self._load_nllb()
                return
            except Exception as exc:
                print(
                    f"NLLB translator unavailable ({exc}). Reports will stay in English.",
                    flush=True,
                )
                self.method = "none"
                return

        raise ValueError(f"Unknown translation method: {method}")

    def _load_nllb(self):
        """تحميل NLLB-200 distilled (محلي، offline بعد أول تحميل)."""
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

        print("Loading NLLB-200 translator (English → Arabic)...")
        model_id = "facebook/nllb-200-distilled-600M"

        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id)

        device = get_device()
        self.model.to(device)
        self.model.eval()
        self.device = device
        print("NLLB translator loaded.")

    def _load_google(self):
        """ترجمة Google عبر googletrans (يحتاج إنترنت)."""
        try:
            from googletrans import Translator as GTranslator
        except ImportError:
            raise ImportError(
                "googletrans not installed. Run: pip install googletrans==4.0.0rc1"
            )
        self.google_translator = GTranslator()
        print("Google translator ready.")

    def translate(self, text):
        if self.method == "none":
            return text
        if self.method == "nllb":
            return self._translate_nllb(text)
        if self.method == "google":
            return self._translate_google(text)

    def _translate_nllb(self, text):
        """ترجمة فقرة فقرة عشان نحافظ على بنية التقرير."""
        if not text.strip():
            return text

        # نقسم النص حسب الأسطر الفارغة (الفقرات/العناوين)
        paragraphs = text.split("\n")
        translated_parts = []

        for para in paragraphs:
            if not para.strip():
                translated_parts.append("")
                continue

            inputs = self.tokenizer(
                para,
                return_tensors="pt",
                truncation=True,
                max_length=512
            ).to(self.device)

            with torch.no_grad():
                output = self.model.generate(
                    **inputs,
                    forced_bos_token_id=self.tokenizer.convert_tokens_to_ids("arb_Arab"),
                    max_length=512,
                    num_beams=4,
                    early_stopping=True
                )

            translated = self.tokenizer.batch_decode(
                output, skip_special_tokens=True
            )[0]
            translated_parts.append(translated)

        return "\n".join(translated_parts)

    def _translate_google(self, text):
        try:
            result = self.google_translator.translate(text, src="en", dest="ar")
            return result.text
        except Exception as e:
            print(f"Translation error: {e}. Returning English.")
            return text


# =========================================================
# DATABASE
# =========================================================

def connect_db():
    return psycopg.connect(**DB_CONFIG, row_factory=dict_row)


def apply_env_overrides():
    """يقرأ CP_PATH و DB_* من البيئة (للتشغيل من الباك إند أو سطر الأوامر)."""
    global DB_CONFIG, TABLE_NAME, VISUAL_REPORTS_DIR, BASE_MODEL_DIR, ADAPTER_DIR, TRANSLATION_METHOD

    root = Path(os.getenv("CP_PATH", Path(__file__).resolve().parents[1])).expanduser()
    reporter = Path(__file__).resolve().parent

    DB_CONFIG = {
        "host": os.getenv("DB_HOST", DB_CONFIG["host"]),
        "port": int(os.getenv("DB_PORT", str(DB_CONFIG["port"]))),
        "dbname": os.getenv("DB_NAME", DB_CONFIG["dbname"]),
        "user": os.getenv("DB_USER", DB_CONFIG["user"]),
        "password": os.getenv("DB_PASSWORD", os.getenv("PGPASSWORD", DB_CONFIG["password"])),
    }
    TABLE_NAME = os.getenv("SPILLS_TABLE", os.getenv("DB_TABLE", TABLE_NAME))
    VISUAL_REPORTS_DIR = Path(
        os.getenv(
            "VISUAL_REPORTS_DIR",
            str(root / "full_pipeline_output" / "visual_reports"),
        )
    )
    BASE_MODEL_DIR = os.getenv(
        "LLM_BASE_MODEL_DIR",
        str(reporter / "models" / "Qwen2.5-0.5B-Instruct"),
    )
    ADAPTER_DIR = os.getenv(
        "LLM_ADAPTER_DIR",
        str(reporter / "oil_qwen_lora_adapter"),
    )
    if os.getenv("LLM_TRANSLATION_METHOD"):
        TRANSLATION_METHOD = os.getenv("LLM_TRANSLATION_METHOD", TRANSLATION_METHOD).strip().lower()


def _safe_sql_table(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(name or "")):
        raise ValueError(f"Unsafe table name: {name!r}")
    return str(name)


def _table_column_names(conn, table: str) -> set:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        rows = cur.fetchall()
        names = set()
        for r in rows:
            if isinstance(r, dict):
                names.add(str(r.get("column_name") or next(iter(r.values()), "")))
            else:
                names.add(str(r[0]))
        return {n for n in names if n}


def fetch_one_spill_row(spill_id: str) -> dict:
    apply_env_overrides()
    table = _safe_sql_table(TABLE_NAME)
    key = str(spill_id or "").strip()
    if not key:
        raise ValueError("Spill id is empty")

    conn = connect_db()
    try:
        cols = _table_column_names(conn, table)
        with conn.cursor() as cur:
            # مطابقة مباشرة — الجدول الحالي يستخدم filename / source_image (بدون spill_id)
            match_cols = [c for c in ("filename", "source_image", "spill_id", "id") if c in cols]
            if match_cols:
                parts = [sql.SQL("{} = %s").format(sql.Identifier(c)) for c in match_cols]
                q = sql.SQL("SELECT * FROM {} WHERE {} LIMIT 1").format(
                    sql.Identifier(table),
                    sql.SQL(" OR ").join(parts),
                )
                params = tuple(key for _ in match_cols)
                cur.execute(q, params)
                row = cur.fetchone()
                if row:
                    return dict(row)

            stem = Path(key).stem
            fuzzy_cols = [c for c in ("filename", "source_image", "source_image_path") if c in cols]
            if fuzzy_cols and stem:
                parts = [
                    sql.SQL("{} ILIKE %s").format(sql.Identifier(c)) for c in fuzzy_cols
                ]
                q2 = sql.SQL("SELECT * FROM {} WHERE {} LIMIT 1").format(
                    sql.Identifier(table),
                    sql.SQL(" OR ").join(parts),
                )
                params = tuple(f"%{stem}%" for _ in fuzzy_cols)
                cur.execute(q2, params)
                row = cur.fetchone()
                if row:
                    return dict(row)
    finally:
        conn.close()
    raise ValueError(f"Spill not found: {spill_id}")


def _path_if_file(value: Any) -> Optional[Path]:
    if value is None:
        return None
    p = Path(str(value)).expanduser()
    return p if p.is_file() else None


def _uploads_dir() -> Path:
    root = Path(os.getenv("CP_PATH", Path(__file__).resolve().parents[1])).expanduser()
    return Path(os.getenv("UPLOAD_DIR", str(root / "backend_uploads"))).expanduser()


def prepare_web_png(source: Path, target: Path) -> bool:
    """نسخ أو تحويل الصورة إلى PNG يعرض في المتصفح."""
    target = target.with_suffix(".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        shutil.copy2(source, target)
        return True
    try:
        from PIL import Image
        import numpy as np

        arr = np.array(Image.open(source))
        if arr.ndim == 2:
            u8 = arr.astype("float32")
            if u8.max() > 1.0:
                u8 = u8 / 255.0
            mask = np.clip(u8, 0, 1)
            base = np.full((*mask.shape, 3), 40, dtype=np.uint8)
            color = np.zeros_like(base)
            color[..., 1] = 200
            color[..., 2] = 120
            alpha = (mask[..., None] * 0.72).clip(0, 0.72)
            rgb = (base * (1 - alpha) + color * alpha).clip(0, 255).astype(np.uint8)
            Image.fromarray(rgb).save(target)
            return True
        if arr.ndim == 3 and arr.shape[2] >= 3:
            rgb = arr[..., :3]
            if rgb.dtype != np.uint8:
                rgb = (np.clip(rgb, 0, 1) * 255).astype(np.uint8) if rgb.max() <= 1 else np.clip(rgb, 0, 255).astype(np.uint8)
            Image.fromarray(rgb).save(target)
            return True
        Image.fromarray(arr).convert("RGB").save(target)
        return True
    except Exception:
        return False


def find_spill_display_images(row: dict) -> dict:
    """
    يحدد أفضل صورة/صورتين للتقرير:
    - overlay أو التقرير البصري أو القناع
    - الصورة الأصلية إن وُجدت
    """
    out: dict = {"primary": None, "secondary": None}
    filename = get_value(row, ["filename", "source_image", "image_name"], default=None)
    if filename is None:
        return out

    stem = Path(str(filename)).stem

    for col in ["visual_report_path", "visual_report"]:
        p = _path_if_file(get_value(row, [col], default=None))
        if p:
            out["primary"] = p
            break

    if out["primary"] is None:
        upload_dir = _uploads_dir()
        if upload_dir.is_dir():
            overlays = sorted(
                upload_dir.glob(f"*{stem}*overlay*.png"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            if overlays:
                out["primary"] = overlays[0]

    if out["primary"] is None:
        out["primary"] = find_visual_report_image(row)

    src = _path_if_file(
        get_value(row, ["source_image_path", "saved_path", "source_image"], default=None)
    )
    mask = _path_if_file(get_value(row, ["predicted_mask_path", "mask_path"], default=None))

    if out["primary"] is None and mask is not None:
        out["primary"] = mask
    if out["secondary"] is None and src is not None and src != out["primary"]:
        out["secondary"] = src

    return out


def copy_image_to_report_dir(image_path, filename, images_dir: Path, *, slot: str = "visual") -> Optional[str]:
    if image_path is None:
        return None
    images_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(str(filename)).stem.replace(" ", "_")
    target = images_dir / f"{safe_name}_{slot}.png"
    src = Path(image_path)
    if not prepare_web_png(src, target):
        return None
    return target.name


def copy_spill_images_for_report(
    row: dict,
    images_dir: Path,
    *,
    use_api_assets: bool = False,
) -> dict:
    """ينسخ صور الحالة إلى مجلد التقرير ويعيد روابط العرض."""
    filename = get_value(row, ["filename", "source_image", "image_name"])
    found = find_spill_display_images(row)
    urls: dict = {}

    def asset_url(name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        if use_api_assets:
            return f"/api/llm-report-assets/{name}"
        return f"images/{name}"

    primary = found.get("primary")
    secondary = found.get("secondary")

    if primary is not None:
        asset = copy_image_to_report_dir(primary, filename, images_dir, slot="spill")
        urls["primary"] = asset_url(asset)

    if secondary is not None:
        asset = copy_image_to_report_dir(secondary, filename, images_dir, slot="satellite")
        urls["secondary"] = asset_url(asset)

    return urls


def _report_page_shell(card_html: str, subtitle: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تقرير تقييم واستجابة التسرب النفطي</title>
<style>
    body {{
        font-family: "Segoe UI", "Tahoma", Arial, sans-serif;
        background: #f4f6f8;
        margin: 0;
        padding: 28px;
        color: #222;
        direction: rtl;
    }}
    h1 {{ margin-bottom: 4px; color: #1f5f9f; }}
    .subtitle {{ margin-bottom: 28px; color: #666; }}
    .card {{
        background: white;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 26px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.08);
    }}
    .card h2 {{ margin-top: 0; color: #2f7fd6; }}
    .grid {{
        display: grid;
        grid-template-columns: 58% 42%;
        gap: 22px;
        align-items: start;
    }}
    .visual-report {{
        width: 100%;
        border-radius: 12px;
        border: 1px solid #ddd;
        background: #fafafa;
    }}
    .image-stack {{ display: flex; flex-direction: column; gap: 14px; }}
    .figure {{ margin: 0; }}
    .figure figcaption {{
        margin-top: 6px;
        font-size: 12px;
        color: #64748b;
        text-align: center;
    }}
    .missing-image {{
        height: 300px;
        border: 1px dashed #999;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #777;
        background: #fafafa;
    }}
    .badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;
    }}
    .badges span {{
        background: #eef4fb;
        border: 1px solid #d7e6f7;
        border-radius: 18px;
        padding: 7px 12px;
        font-size: 13px;
    }}
    .llm-report {{
        line-height: 1.85;
        font-size: 15px;
        background: #fbfbfb;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 16px;
    }}
    .llm-report h3 {{ margin-top: 0; color: #2f7fd6; }}
    .english-original {{ margin-top: 12px; }}
    .english-original summary {{
        cursor: pointer;
        color: #1f5f9f;
        font-size: 13px;
        padding: 6px 0;
    }}
    .llm-report-en {{
        margin-top: 8px;
        line-height: 1.6;
        font-size: 13px;
        background: #fafafa;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 12px;
        color: #555;
    }}
    @media (max-width: 900px) {{
        .grid {{ grid-template-columns: 1fr; }}
    }}
</style>
</head>
<body>
    <h1>تقارير حوادث التسربات النفطية</h1>
    <div class="subtitle">{html.escape(subtitle)}</div>
    {card_html}
</body>
</html>
"""


def generate_one_spill_report_json(
    spill_id: str,
    output_dir: Path,
    language: str = "ar",
    *,
    use_api_assets: bool = False,
) -> dict:
    """
    نفس مسار main() لكن لحالة واحدة — للباك إند.
    يطبع JSON على stdout عند التشغيل بـ --spill-id.
    """
    apply_env_overrides()
    row = fetch_one_spill_row(spill_id)

    out_root = Path(output_dir).expanduser()
    html_dir = out_root / "html"
    images_dir = out_root / "images"
    html_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    report_id = f"LLM-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    tokenizer, model, device = load_llm()
    translator = Translator(method=TRANSLATION_METHOD)

    report_en = generate_report(tokenizer, model, device, row)
    print("   → Translating to Arabic...", flush=True)
    report_ar = translator.translate(report_en)

    lang = (language or "ar").lower()
    primary = report_ar if lang == "ar" else report_en

    filename = get_value(row, ["filename", "source_image", "image_name"])
    image_urls = copy_spill_images_for_report(row, images_dir, use_api_assets=use_api_assets)

    card = make_html_card(row, report_ar, report_en, image_urls)
    subtitle = (
        f"تقرير تقييم واستجابة التسرب · Qwen2.5 + LoRA · {report_id} · {generated_at}"
    )
    page = _report_page_shell(card, subtitle)
    html_path = html_dir / f"{report_id}.html"
    html_path.write_text(page, encoding="utf-8")

    risk_level = str(get_value(row, ["risk_level", "final_risk_level"], "Unknown"))
    spill_key = str(get_value(row, ["spill_id", "filename", "id"], filename))

    return {
        "id": report_id,
        "report_id": report_id,
        "spill_id": spill_key,
        "filename": str(filename),
        "risk_level": risk_level,
        "final_risk_level": risk_level,
        "language": "ar" if lang == "ar" else "en",
        "created_at": datetime.utcnow().isoformat(),
        "generated_at": generated_at,
        "summary": str(primary)[:280],
        "content": str(primary),
        "report_en": report_en,
        "report_ar": report_ar,
        "generator": "run_local_oil_llm.py",
        "model": "Qwen2.5-0.5B-Instruct+LoRA",
        "html_path": str(html_path.resolve()),
        "html_filename": html_path.name,
        "image_asset": image_urls.get("primary"),
        "image_assets": image_urls,
    }


def fetch_rows(conn):
    with conn.cursor() as cur:
        if LIMIT_ROWS is None:
            query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(TABLE_NAME))
            cur.execute(query)
        else:
            query = sql.SQL("SELECT * FROM {} LIMIT %s").format(sql.Identifier(TABLE_NAME))
            cur.execute(query, (LIMIT_ROWS,))

        return cur.fetchall()


# =========================================================
# HELPERS
# =========================================================

def get_value(row, possible_columns, default="Not available"):
    for col in possible_columns:
        if col in row and row[col] is not None:
            value = str(row[col]).strip()
            if value != "":
                return row[col]
    return default


def find_visual_report_image(row):
    filename = get_value(row, ["filename", "source_image", "image_name"], default=None)

    if filename is None:
        return None

    filename = str(filename)
    stem = Path(filename).stem

    candidates = [
        VISUAL_REPORTS_DIR / filename,
        VISUAL_REPORTS_DIR / f"{stem}.png",
        VISUAL_REPORTS_DIR / f"{stem}.jpg",
        VISUAL_REPORTS_DIR / f"{stem}.jpeg",
        VISUAL_REPORTS_DIR / f"{stem}.tif",
        VISUAL_REPORTS_DIR / f"{stem}.tiff",
        VISUAL_REPORTS_DIR / f"{stem}_report.png",
        VISUAL_REPORTS_DIR / f"{stem}_visual_report.png",
        VISUAL_REPORTS_DIR / f"{stem}_analysis.png",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = list(VISUAL_REPORTS_DIR.glob(f"*{stem}*.png"))
    matches += list(VISUAL_REPORTS_DIR.glob(f"*{stem}*.jpg"))
    matches += list(VISUAL_REPORTS_DIR.glob(f"*{stem}*.jpeg"))

    if matches:
        return matches[0]

    return None


def copy_image_to_html_folder(image_path, filename):
    if image_path is None:
        return None

    OUTPUT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    safe_name = Path(str(filename)).stem.replace(" ", "_")
    target = OUTPUT_IMAGES_DIR / f"{safe_name}_visual_report{image_path.suffix.lower()}"

    shutil.copy2(image_path, target)

    return target.relative_to(OUTPUT_DIR)


# =========================================================
# LLM PROMPT (English - matches training)
# =========================================================

def build_messages(row):
    filename = get_value(row, ["filename", "source_image", "image_name"])

    area_px = get_value(row, ["area_px"])
    area_m2 = get_value(row, ["area_m2"])
    coverage_pct = get_value(row, ["coverage_pct"])

    centroid_x = get_value(row, ["centroid_x"])
    centroid_y = get_value(row, ["centroid_y"])
    spill_lon = get_value(row, ["spill_centroid_lon"])
    spill_lat = get_value(row, ["spill_centroid_lat"])

    perimeter_m = get_value(row, ["perimeter_m"])
    orientation_deg = get_value(row, ["orientation_deg"])
    spread_ratio = get_value(row, ["spread_ratio"])
    compactness = get_value(row, ["compactness"])
    density_score = get_value(row, ["density_score"])
    num_components = get_value(row, ["num_components"])

    distance_to_land_km = get_value(row, ["distance_to_land_km"])
    land_class = get_value(row, ["land_proximity_class"])

    coral_distance_km = get_value(
        row,
        ["distance_to_coral_km", "nearest_coral_distance_km", "coral_distance_km"]
    )
    coral_class = get_value(
        row,
        ["coral_risk_class", "coral_proximity_class", "nearest_coral_risk_class"]
    )

    risk_score = get_value(row, ["risk_score"])
    risk_level = get_value(row, ["risk_level", "final_risk_level"])

    prompt = f"""
Generate a professional oil spill incident report using only these database values.

Database values:
- Filename: {filename}
- Area pixels: {area_px}
- Area square meters: {area_m2}
- Coverage percentage: {coverage_pct}%
- Centroid pixel: ({centroid_x}, {centroid_y})
- Centroid lon/lat: ({spill_lon}, {spill_lat})
- Perimeter meters: {perimeter_m}
- Orientation degrees: {orientation_deg}
- Spread ratio: {spread_ratio}
- Components: {num_components}
- Compactness: {compactness}
- Density score: {density_score}
- Land distance km: {distance_to_land_km}
- Land class: {land_class}
- Coral distance km: {coral_distance_km}
- Coral class: {coral_class}
- Risk score: {risk_score}
- Risk level: {risk_level}

Rules:
- Do not analyze the image.
- Do not invent values.
- Do not invent emergency protocols.
- Use only the database values.
- Write the report in English.
- Structure it as: Event Summary, Spatial/Risk Interpretation, Monitoring Recommendation, Conclusion.
"""

    messages = [
        {
            "role": "system",
            "content": """
You are an AI assistant specialized in oil spill monitoring reports.
You generate reports only from structured database values.
You do not analyze images.
You do not invent emergency levels, protocols, agencies, or legal decisions.
"""
        },
        {
            "role": "user",
            "content": prompt
        }
    ]

    return messages


def generate_report(tokenizer, model, device, row):
    messages = build_messages(row)

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=1024
    ).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=320,
            do_sample=False,
            repetition_penalty=1.05,
            eos_token_id=tokenizer.eos_token_id
        )

    generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    report = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    return report.strip()


# =========================================================
# HTML (Arabic-aware with RTL)
# =========================================================

def make_html_card(row, report_ar, report_en, image_urls):
    filename = get_value(row, ["filename", "source_image", "image_name"])
    area_m2 = get_value(row, ["area_m2"])
    coverage_pct = get_value(row, ["coverage_pct"])
    land_class = get_value(row, ["land_proximity_class"])
    coral_class = get_value(row, ["coral_risk_class", "coral_proximity_class", "nearest_coral_risk_class"])
    risk_score = get_value(row, ["risk_score"])
    risk_level = get_value(row, ["risk_level", "final_risk_level"])

    urls = image_urls if isinstance(image_urls, dict) else {}
    if not urls and image_urls:
        urls = {"primary": image_urls}

    blocks = []
    primary = urls.get("primary")
    secondary = urls.get("secondary")
    if primary:
        blocks.append(
            f'<figure class="figure"><img class="visual-report" src="{html.escape(str(primary))}" '
            f'alt="كشف التسرب — {html.escape(str(filename))}">'
            f'<figcaption>صورة الكشف والتسرب</figcaption></figure>'
        )
    if secondary:
        blocks.append(
            f'<figure class="figure"><img class="visual-report" src="{html.escape(str(secondary))}" '
            f'alt="صورة الأقمار الصناعية — {html.escape(str(filename))}">'
            f'<figcaption>صورة الأقمار الصناعية الأصلية</figcaption></figure>'
        )
    if blocks:
        image_html = '<div class="image-stack">' + "".join(blocks) + "</div>"
    else:
        image_html = """
        <div class="missing-image">لم تُعثر على صورة لهذا التسرب. احفظي التحليل أو تأكدي من مسار الصورة في قاعدة البيانات.</div>
        """

    report_ar_html = html.escape(report_ar).replace("\n", "<br>")
    report_en_html = html.escape(report_en).replace("\n", "<br>")

    return f"""
    <section class="card">
        <h2>{html.escape(str(filename))}</h2>

        <div class="grid">
            <div class="image-box">
                {image_html}
            </div>

            <div class="report-box">
                <div class="badges">
                    <span><b>المساحة:</b> {html.escape(str(area_m2))} م²</span>
                    <span><b>التغطية:</b> {html.escape(str(coverage_pct))}%</span>
                    <span><b>القرب من اليابسة:</b> {html.escape(str(land_class))}</span>
                    <span><b>القرب من المرجان:</b> {html.escape(str(coral_class))}</span>
                    <span><b>المخاطر:</b> {html.escape(str(risk_level))} ({html.escape(str(risk_score))})</span>
                </div>

                <div class="llm-report" dir="rtl" lang="ar">
                    <h3>التقرير</h3>
                    {report_ar_html}
                </div>

                <details class="english-original">
                    <summary>عرض النص الأصلي بالإنجليزية</summary>
                    <div class="llm-report-en" dir="ltr" lang="en">
                        {report_en_html}
                    </div>
                </details>
            </div>
        </div>
    </section>
    """


def save_final_html(cards):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    page = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تقرير تقييم واستجابة التسرب النفطي</title>
<style>
    body {{
        font-family: "Segoe UI", "Tahoma", Arial, sans-serif;
        background: #f4f6f8;
        margin: 0;
        padding: 28px;
        color: #222;
        direction: rtl;
    }}

    h1 {{
        margin-bottom: 4px;
        color: #1f5f9f;
    }}

    .subtitle {{
        margin-bottom: 28px;
        color: #666;
    }}

    .card {{
        background: white;
        border-radius: 16px;
        padding: 22px;
        margin-bottom: 26px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.08);
    }}

    .card h2 {{
        margin-top: 0;
        color: #2f7fd6;
    }}

    .grid {{
        display: grid;
        grid-template-columns: 58% 42%;
        gap: 22px;
        align-items: start;
    }}

    .visual-report {{
        width: 100%;
        border-radius: 12px;
        border: 1px solid #ddd;
        background: #fafafa;
    }}
    .image-stack {{ display: flex; flex-direction: column; gap: 14px; }}
    .figure {{ margin: 0; }}
    .figure figcaption {{
        margin-top: 6px;
        font-size: 12px;
        color: #64748b;
        text-align: center;
    }}

    .missing-image {{
        height: 300px;
        border: 1px dashed #999;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #777;
        background: #fafafa;
    }}

    .badges {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;
    }}

    .badges span {{
        background: #eef4fb;
        border: 1px solid #d7e6f7;
        border-radius: 18px;
        padding: 7px 12px;
        font-size: 13px;
    }}

    .llm-report {{
        line-height: 1.85;
        font-size: 15px;
        background: #fbfbfb;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 16px;
    }}

    .llm-report h3 {{
        margin-top: 0;
        color: #2f7fd6;
    }}

    .english-original {{
        margin-top: 12px;
    }}

    .english-original summary {{
        cursor: pointer;
        color: #1f5f9f;
        font-size: 13px;
        padding: 6px 0;
    }}

    .llm-report-en {{
        margin-top: 8px;
        line-height: 1.6;
        font-size: 13px;
        background: #fafafa;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 12px;
        color: #555;
    }}

    @media (max-width: 900px) {{
        .grid {{
            grid-template-columns: 1fr;
        }}
    }}
</style>
</head>

<body>
    <h1>تقارير حوادث التسربات النفطية</h1>
    <div class="subtitle">
        تقارير مولّدة من قيم قاعدة بيانات PostgreSQL. الصور البصرية مطابقة بالاسم ولا يحلّلها النموذج اللغوي.
    </div>

    {''.join(cards)}
</body>
</html>
"""

    output_path = OUTPUT_DIR / "oil_spill_llm_final_report.html"
    output_path.write_text(page, encoding="utf-8")

    return output_path


# =========================================================
# MAIN
# =========================================================

def main():
    apply_env_overrides()
    print("=" * 70)
    print("Connecting to database...")
    print("=" * 70)

    conn = connect_db()
    rows = fetch_rows(conn)
    conn.close()

    print(f"Rows loaded: {len(rows)}")

    tokenizer, model, device = load_llm()
    translator = Translator(method=TRANSLATION_METHOD)
    cards = []

    for idx, row in enumerate(rows, start=1):
        filename = get_value(row, ["filename", "source_image", "image_name"])
        print(f"Processing {idx}/{len(rows)}: {filename}")
        report_en = generate_report(tokenizer, model, device, row)
        print("   → Translating to Arabic...")
        report_ar = translator.translate(report_en)
        image_urls = copy_spill_images_for_report(row, OUTPUT_IMAGES_DIR, use_api_assets=False)
        cards.append(make_html_card(row, report_ar, report_en, image_urls))

    output_html = save_final_html(cards)

    print("=" * 70)
    print("DONE")
    print(f"HTML saved at: {output_html.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Oil spill LLM reports — نفس المنطق للدفعة أو لحالة واحدة."
    )
    parser.add_argument(
        "--spill-id",
        default="",
        help="توليد تقرير واحد لهذه الحالة (اسم الملف أو spill_id). يُستخدم مع الباك إند.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="مجلد الإخراج (يُنشأ html/ و images/). الافتراضي: final_html_reports تحت المجلد الحالي.",
    )
    parser.add_argument("--language", default="ar", help="ar أو en")
    parser.add_argument(
        "--api-assets",
        action="store_true",
        help="روابط الصور عبر /api/llm-report-assets/ (للعرض من الواجهة عبر الباك إند).",
    )
    args = parser.parse_args()

    if (args.spill_id or "").strip():
        out = (
            Path(args.output_dir).expanduser()
            if (args.output_dir or "").strip()
            else Path.cwd() / "final_html_reports"
        )
        result = generate_one_spill_report_json(
            args.spill_id.strip(),
            out,
            args.language,
            use_api_assets=bool(args.api_assets),
        )
        print(json.dumps(result, ensure_ascii=False))
    else:
        main()