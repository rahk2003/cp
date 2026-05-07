from pathlib import Path
import sys
import html as html_escape
from bs4 import BeautifulSoup

sys.path.append(str(Path(__file__).resolve().parent))

from search_response_agent import generate_response_plan_from_report


HTML_PATH = Path("oil_spill_llm_final_report.html")
OUTPUT_DIR = Path("external_rag/final_first_image_report")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FINAL_HTML = OUTPUT_DIR / "first_image_final_report.html"
FINAL_TXT = OUTPUT_DIR / "first_image_final_response.txt"


def clean_text(text):
    return " ".join(text.split())


def text_to_html(text):
    return html_escape.escape(text).replace("\n", "<br>")


def extract_first_report(html_path):
    html_content = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html_content, "html.parser")

    card = soup.select_one("section.card")
    if card is None:
        raise ValueError("No report card found in the HTML file.")

    title = clean_text(card.select_one("h2").get_text(" ", strip=True))

    image_src = ""
    img = card.select_one("img.visual-report")
    if img:
        image_src = img.get("src", "")

    badges = []
    for span in card.select(".badges span"):
        badges.append(clean_text(span.get_text(" ", strip=True)))

    ar_box = card.select_one(".llm-report")
    arabic_report = clean_text(ar_box.get_text(" ", strip=True)) if ar_box else ""

    en_box = card.select_one(".llm-report-en")
    english_report = clean_text(en_box.get_text(" ", strip=True)) if en_box else ""

    full_report = f"""
Oil Spill LLM Final Report

Image/File: {title}

Extracted Badges:
{chr(10).join("- " + b for b in badges)}

Arabic LLM Report:
{arabic_report}

English Original Report:
{english_report}
"""

    return {
        "title": title,
        "image_src": image_src,
        "badges": badges,
        "arabic_report": arabic_report,
        "english_report": english_report,
        "full_report": full_report
    }


def build_final_html(report, response):
    badges_html = "".join(
        f"<span>{html_escape.escape(b)}</span>"
        for b in report["badges"]
    )

    image_html = ""
    if report["image_src"]:
        image_html = f'''
        <img class="visual-report" src="../../{html_escape.escape(report["image_src"])}" alt="visual report">
        '''
    else:
        image_html = '<div class="missing-image">No visual image found</div>'

    page = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>التقرير النهائي لأول صورة</title>
<style>
body {{
    font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    background: #f4f6f8;
    padding: 28px;
    color: #222;
}}
h1 {{
    color: #1f5f9f;
}}
.card {{
    background: white;
    border-radius: 16px;
    padding: 22px;
    margin-bottom: 24px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.08);
}}
.grid {{
    display: grid;
    grid-template-columns: 45% 55%;
    gap: 22px;
    align-items: start;
}}
.visual-report {{
    width: 100%;
    border-radius: 12px;
    border: 1px solid #ddd;
}}
.badges {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
}}
.badges span {{
    background: #eef4fb;
    border: 1px solid #d7e6f7;
    border-radius: 18px;
    padding: 8px 12px;
    font-size: 14px;
}}
.box {{
    background: #fbfbfb;
    border: 1px solid #eee;
    border-radius: 12px;
    padding: 16px;
    line-height: 1.9;
    margin-top: 10px;
}}
.final {{
    background: #fffdf7;
    border: 1px solid #eadca8;
}}
summary {{
    cursor: pointer;
    color: #1f5f9f;
}}
@media (max-width: 900px) {{
    .grid {{
        grid-template-columns: 1fr;
    }}
}}
</style>
</head>
<body>

<h1>التقرير النهائي لأول صورة</h1>

<section class="card">
    <h2>{html_escape.escape(report["title"])}</h2>

    <div class="grid">
        <div>
            <h3>الصورة / التقرير البصري</h3>
            {image_html}
        </div>

        <div>
            <h3>1) البيانات التي أخذها من تقرير LLM الأول</h3>
            <div class="badges">{badges_html}</div>

            <h3>2) تقرير LLM الأول</h3>
            <details>
                <summary>عرض التقرير المستخدم كمدخل للـ Agent</summary>
                <div class="box">{text_to_html(report["full_report"])}</div>
            </details>
        </div>
    </div>
</section>

<section class="card">
    <h2>3) التقرير النهائي من Search Response Agent</h2>
    <div class="box final">{text_to_html(response)}</div>
</section>

</body>
</html>
"""
    FINAL_HTML.write_text(page, encoding="utf-8")


def main():
    if not HTML_PATH.exists():
        raise FileNotFoundError(
            "oil_spill_llm_final_report.html غير موجود داخل مجلد cp."
        )

    print("Extracting first image report from HTML...")
    report = extract_first_report(HTML_PATH)

    print(f"Running full pipeline for: {report['title']}")
    response = generate_response_plan_from_report(report["full_report"])

    FINAL_TXT.write_text(response, encoding="utf-8")
    build_final_html(report, response)

    print("Done.")
    print(f"Final TXT saved to: {FINAL_TXT}")
    print(f"Final HTML saved to: {FINAL_HTML}")


if __name__ == "__main__":
    main()
