from pathlib import Path
import sys
from bs4 import BeautifulSoup

# import search_response_agent from same folder
sys.path.append(str(Path(__file__).resolve().parent))

from search_response_agent import generate_response_plan_from_report


HTML_PATH = Path("oil_spill_llm_final_report.html")
OUTPUT_DIR = Path("external_rag/search_test_outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(text):
    return " ".join(text.split())


def extract_first_reports_from_html(html_path, limit=2):
    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    cards = soup.select("section.card")
    reports = []

    for card in cards[:limit]:
        title_tag = card.select_one("h2")
        title = clean_text(title_tag.get_text(" ", strip=True)) if title_tag else "unknown"

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

        reports.append({
            "title": title,
            "text": full_report
        })

    return reports


def main():
    if not HTML_PATH.exists():
        raise FileNotFoundError(
            f"HTML file not found: {HTML_PATH}\n"
            "Make sure oil_spill_llm_final_report.html is inside the cp folder."
        )

    reports = extract_first_reports_from_html(HTML_PATH, limit=2)

    for report in reports:
        safe_name = report["title"].replace(".tif", "").replace("/", "_").replace("\\", "_")

        input_path = OUTPUT_DIR / f"{safe_name}_input_report.txt"
        output_path = OUTPUT_DIR / f"{safe_name}_search_response.txt"

        input_path.write_text(report["text"], encoding="utf-8")

        print("=" * 80)
        print(f"Running Search Response Agent for: {report['title']}")
        print(f"Input saved to: {input_path}")

        response = generate_response_plan_from_report(report["text"])
        output_path.write_text(response, encoding="utf-8")

        print(response)
        print(f"Saved response to: {output_path}")
        print("=" * 80)


if __name__ == "__main__":
    main()
