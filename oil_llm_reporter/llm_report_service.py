"""
خدمة توليد تقارير Qwen2.5 + LoRA لحالة تسرب واحدة (للباك إند أو السكربت الدفعي).
"""

from __future__ import annotations

import html
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

_CP = Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP")).expanduser()
_REPORTER = _CP / "oil_llm_reporter"

BASE_MODEL_DIR = Path(
    os.getenv("LLM_BASE_MODEL_DIR", str(_REPORTER / "models" / "Qwen2.5-0.5B-Instruct"))
)
ADAPTER_DIR = Path(os.getenv("LLM_ADAPTER_DIR", str(_REPORTER / "oil_qwen_lora_adapter")))
VISUAL_REPORTS_DIR = Path(
    os.getenv("VISUAL_REPORTS_DIR", str(_CP / "full_pipeline_output" / "visual_reports"))
)
DEFAULT_OUTPUT_DIR = Path(
    os.getenv("LLM_REPORTS_OUTPUT_DIR", str(_CP / "backend-rana-clean" / "generated_llm_reports"))
)

TRANSLATION_METHOD = os.getenv("LLM_TRANSLATION_METHOD", "google").strip().lower()

_LLM_LOCK = threading.Lock()
_LLM_CACHE: Dict[str, Any] = {}


def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def load_llm():
    with _LLM_LOCK:
        if _LLM_CACHE.get("ready"):
            return _LLM_CACHE["tokenizer"], _LLM_CACHE["model"], _LLM_CACHE["device"]

        device = get_device()
        dtype = torch.float16 if device in ("mps", "cuda") else torch.float32

        tokenizer = AutoTokenizer.from_pretrained(
            str(BASE_MODEL_DIR), local_files_only=True, trust_remote_code=True
        )
        base_model = AutoModelForCausalLM.from_pretrained(
            str(BASE_MODEL_DIR), local_files_only=True, dtype=dtype, trust_remote_code=True
        )
        model = PeftModel.from_pretrained(
            base_model, str(ADAPTER_DIR), local_files_only=True
        )
        model.to(device)
        model.eval()

        _LLM_CACHE["tokenizer"] = tokenizer
        _LLM_CACHE["model"] = model
        _LLM_CACHE["device"] = device
        _LLM_CACHE["ready"] = True
        return tokenizer, model, device


class Translator:
    def __init__(self, method: str = "google"):
        self.method = (method or "google").lower()
        self.model = None
        self.tokenizer = None
        self.google_translator = None
        self.device = None

        if self.method == "nllb":
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer as AT

            model_id = "facebook/nllb-200-distilled-600M"
            self.tokenizer = AT.from_pretrained(model_id)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
            self.device = get_device()
            self.model.to(self.device)
            self.model.eval()
        elif self.method == "google":
            from googletrans import Translator as GTranslator

            self.google_translator = GTranslator()
        elif self.method != "none":
            raise ValueError(f"Unknown translation method: {method}")

    def translate(self, text: str) -> str:
        if self.method == "none" or not text.strip():
            return text
        if self.method == "nllb":
            return self._translate_nllb(text)
        if self.method == "google":
            try:
                return self.google_translator.translate(text, src="en", dest="ar").text
            except Exception:
                return text
        return text

    def _translate_nllb(self, text: str) -> str:
        paragraphs = text.split("\n")
        out = []
        for para in paragraphs:
            if not para.strip():
                out.append("")
                continue
            inputs = self.tokenizer(
                para, return_tensors="pt", truncation=True, max_length=512
            ).to(self.device)
            with torch.no_grad():
                output = self.model.generate(
                    **inputs,
                    forced_bos_token_id=self.tokenizer.convert_tokens_to_ids("arb_Arab"),
                    max_length=512,
                    num_beams=4,
                    early_stopping=True,
                )
            out.append(self.tokenizer.batch_decode(output, skip_special_tokens=True)[0])
        return "\n".join(out)


def get_translator() -> Translator:
    with _LLM_LOCK:
        if "translator" not in _LLM_CACHE:
            _LLM_CACHE["translator"] = Translator(method=TRANSLATION_METHOD)
        return _LLM_CACHE["translator"]


def get_value(row: Dict[str, Any], possible_columns, default: Any = "Not available"):
    for col in possible_columns:
        if col in row and row[col] is not None:
            value = str(row[col]).strip()
            if value:
                return row[col]
    return default


def find_visual_report_image(row: Dict[str, Any]) -> Optional[Path]:
    filename = get_value(row, ["filename", "source_image", "image_name"], default=None)
    if filename is None:
        return None

    stem = Path(str(filename)).stem
    for candidate in [
        VISUAL_REPORTS_DIR / str(filename),
        VISUAL_REPORTS_DIR / f"{stem}.png",
        VISUAL_REPORTS_DIR / f"{stem}_report.png",
        VISUAL_REPORTS_DIR / f"{stem}_visual_report.png",
    ]:
        if candidate.exists():
            return candidate

    matches = list(VISUAL_REPORTS_DIR.glob(f"*{stem}*.png"))
    return matches[0] if matches else None


def copy_image_for_report(
    image_path: Optional[Path], filename: Any, images_dir: Path
) -> Optional[str]:
    if image_path is None or not image_path.exists():
        return None
    images_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(str(filename)).stem.replace(" ", "_")
    target = images_dir / f"{safe_name}_visual{image_path.suffix.lower()}"
    shutil.copy2(image_path, target)
    return target.name


def build_messages(row: Dict[str, Any]):
    filename = get_value(row, ["filename", "source_image", "image_name"])
    prompt = f"""
Generate a professional oil spill incident report using only these database values.

Database values:
- Filename: {filename}
- Area pixels: {get_value(row, ["area_px"])}
- Area square meters: {get_value(row, ["area_m2"])}
- Coverage percentage: {get_value(row, ["coverage_pct"])}%
- Centroid lon/lat: ({get_value(row, ["spill_centroid_lon"])}, {get_value(row, ["spill_centroid_lat"])})
- Perimeter meters: {get_value(row, ["perimeter_m"])}
- Orientation degrees: {get_value(row, ["orientation_deg"])}
- Spread ratio: {get_value(row, ["spread_ratio"])}
- Components: {get_value(row, ["num_components"])}
- Compactness: {get_value(row, ["compactness"])}
- Density score: {get_value(row, ["density_score"])}
- Land distance km: {get_value(row, ["distance_to_land_km"])}
- Land class: {get_value(row, ["land_proximity_class"])}
- Coral distance km: {get_value(row, ["distance_to_coral_km", "nearest_coral_distance_km"])}
- Coral class: {get_value(row, ["coral_risk_class", "coral_proximity_class"])}
- Risk score: {get_value(row, ["risk_score"])}
- Risk level: {get_value(row, ["risk_level", "final_risk_level"])}

Rules:
- Do not analyze the image.
- Do not invent values or emergency protocols.
- Write in English.
- Structure: Event Summary, Spatial/Risk Interpretation, Monitoring Recommendation, Conclusion.
"""
    return [
        {
            "role": "system",
            "content": (
                "You are an AI assistant specialized in oil spill monitoring reports. "
                "Generate reports only from structured database values. "
                "Do not analyze images or invent protocols."
            ),
        },
        {"role": "user", "content": prompt},
    ]


def generate_report_en(tokenizer, model, device, row: Dict[str, Any]) -> str:
    messages = build_messages(row)
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=320,
            do_sample=False,
            repetition_penalty=1.05,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated_tokens = outputs[0][inputs["input_ids"].shape[-1] :]
    return tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()



def make_html_card(
    row: Dict[str, Any],
    report_ar: str,
    report_en: str,
    image_src: Optional[str],
) -> str:
    filename = get_value(row, ["filename", "source_image", "image_name"])
    area_m2 = get_value(row, ["area_m2"])
    coverage_pct = get_value(row, ["coverage_pct"])
    land_class = get_value(row, ["land_proximity_class"])
    coral_class = get_value(
        row, ["coral_risk_class", "coral_proximity_class", "nearest_coral_risk_class"]
    )
    risk_score = get_value(row, ["risk_score"])
    risk_level = get_value(row, ["risk_level", "final_risk_level"])

    if image_src:
        image_html = (
            f'<img class="visual-report" src="{html.escape(str(image_src))}" '
            f'alt="تقرير بصري لـ {html.escape(str(filename))}">'
        )
    else:
        image_html = '<div class="missing-image">لم يتم العثور على صورة بصرية مطابقة.</div>'

    report_ar_html = html.escape(report_ar).replace("\n", "<br>")
    report_en_html = html.escape(report_en).replace("\n", "<br>")

    return f"""
    <section class="card">
        <h2>{html.escape(str(filename))}</h2>
        <div class="grid">
            <div class="image-box">{image_html}</div>
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
                    <div class="llm-report-en" dir="ltr" lang="en">{report_en_html}</div>
                </details>
            </div>
        </div>
    </section>
    """


def make_html_page(
    row: Dict[str, Any],
    report_ar: str,
    report_en: str,
    image_asset_name: Optional[str],
    *,
    report_id: str,
    generated_at: str,
) -> str:
    image_src = f"/api/llm-report-assets/{image_asset_name}" if image_asset_name else None
    card = make_html_card(row, report_ar, report_en, image_src)
    return f"""<!DOCTYPE html>
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
    <div class="subtitle">
        تقرير Qwen2.5 + LoRA · {html.escape(report_id)} · {html.escape(generated_at)}
    </div>
    {card}
</body>
</html>"""


def generate_spill_llm_report(
    row: Dict[str, Any],
    *,
    language: str = "ar",
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    يولّد تقرير LLM لصف واحد (dict من قاعدة البيانات).
    يرجع metadata + مسارات HTML.
    """
    out_root = Path(output_dir or DEFAULT_OUTPUT_DIR)
    html_dir = out_root / "html"
    images_dir = out_root / "images"
    html_dir.mkdir(parents=True, exist_ok=True)

    lang = (language or "ar").lower()
    report_id = f"LLM-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    tokenizer, model, device = load_llm()
    report_en = generate_report_en(tokenizer, model, device, row)

    if lang == "ar":
        report_ar = get_translator().translate(report_en)
        primary_content = report_ar
    else:
        report_ar = get_translator().translate(report_en) if TRANSLATION_METHOD != "none" else report_en
        primary_content = report_en

    filename = str(get_value(row, ["filename", "source_image", "image_name"], ""))
    image_asset = copy_image_for_report(
        find_visual_report_image(row),
        filename,
        images_dir,
    )

    html_body = make_html_page(
        row,
        report_ar,
        report_en,
        image_asset,
        report_id=report_id,
        generated_at=generated_at,
    )

    html_path = html_dir / f"{report_id}.html"
    html_path.write_text(html_body, encoding="utf-8")

    risk_level = str(get_value(row, ["final_risk_level", "risk_level"], "Unknown"))

    return {
        "id": report_id,
        "report_id": report_id,
        "spill_id": str(get_value(row, ["spill_id", "id", "filename"], filename)),
        "filename": filename,
        "risk_level": risk_level,
        "final_risk_level": risk_level,
        "language": "ar" if lang == "ar" else "en",
        "created_at": datetime.utcnow().isoformat(),
        "generated_at": generated_at,
        "summary": primary_content[:280],
        "content": primary_content,
        "report_en": report_en,
        "report_ar": report_ar,
        "generator": "run_local_oil_llm.py",
        "model": "Qwen2.5-0.5B-Instruct+LoRA",
        "html_path": str(html_path),
        "html_filename": html_path.name,
        "image_asset": image_asset,
    }
