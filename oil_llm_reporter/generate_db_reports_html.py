import html
import shutil
from pathlib import Path
from datetime import datetime

import torch
import psycopg
from psycopg.rows import dict_row
from psycopg import sql

from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


# =========================================================
# SETTINGS - عدلي هنا فقط
# =========================================================

BASE_MODEL_DIR = "./models/Qwen2.5-0.5B-Instruct"
ADAPTER_DIR = "./oil_qwen_lora_adapter"

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

# للتجربة خليها 5، بعدين خليها None عشان كل البيانات
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
        self.method = method
        self.model = None
        self.tokenizer = None
        self.google_translator = None

        if method == "nllb":
            self._load_nllb()
        elif method == "google":
            self._load_google()
        elif method == "none":
            print("Translation disabled. Reports will be in English only.")
        else:
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
    risk_level = get_value(row, ["risk_level"])

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

def make_html_card(row, report_ar, report_en, image_relative_path):
    filename = get_value(row, ["filename", "source_image", "image_name"])
    area_m2 = get_value(row, ["area_m2"])
    coverage_pct = get_value(row, ["coverage_pct"])
    land_class = get_value(row, ["land_proximity_class"])
    coral_class = get_value(row, ["coral_risk_class", "coral_proximity_class", "nearest_coral_risk_class"])
    risk_score = get_value(row, ["risk_score"])
    risk_level = get_value(row, ["risk_level"])

    if image_relative_path:
        image_html = f"""
        <img class="visual-report" src="{html.escape(str(image_relative_path))}" alt="تقرير بصري لـ {html.escape(str(filename))}">
        """
    else:
        image_html = """
        <div class="missing-image">لم يتم العثور على صورة بصرية مطابقة.</div>
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
<title>تقارير حوادث التسربات النفطية</title>
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
    print("=" * 70)
    print("Connecting to database...")
    print("=" * 70)

    conn = connect_db()
    rows = fetch_rows(conn)
    conn.close()

    print(f"Rows loaded: {len(rows)}")

    tokenizer, model, device = load_llm()

    # تحميل المترجم
    translator = Translator(method=TRANSLATION_METHOD)

    cards = []

    for idx, row in enumerate(rows, start=1):
        filename = get_value(row, ["filename", "source_image", "image_name"])
        print(f"Processing {idx}/{len(rows)}: {filename}")

        # 1) توليد التقرير بالإنجليزي (نفس اللي تدرب عليه)
        report_en = generate_report(tokenizer, model, device, row)

        # 2) ترجمة التقرير للعربي
        print(f"   → Translating to Arabic...")
        report_ar = translator.translate(report_en)

        # 3) معالجة الصورة
        image_path = find_visual_report_image(row)
        image_relative_path = copy_image_to_html_folder(image_path, filename)

        cards.append(make_html_card(row, report_ar, report_en, image_relative_path))

    output_html = save_final_html(cards)

    print("=" * 70)
    print("DONE")
    print(f"HTML saved at: {output_html.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    main()