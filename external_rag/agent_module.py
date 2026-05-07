from __future__ import annotations

import argparse
import json
import os
import re
from typing import Dict, List, Tuple

import pandas as pd
from dotenv import load_dotenv
from google import genai
from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.engine import URL


load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "oil_spills")

PREFERRED_TABLES = [
    "spill_analysis_results",
    "spill_info",
    "prediction_files",
]


FORBIDDEN_SQL_WORDS = [
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "copy", "execute", "call"
]


def make_engine():
    db_url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )
    return create_engine(db_url)


def make_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "PUT_YOUR_GEMINI_API_KEY_HERE":
        raise ValueError("Missing GEMINI_API_KEY. Put your Gemini API key inside .env")
    return genai.Client(api_key=api_key)


def get_schema_context(engine) -> Tuple[str, List[str]]:
    inspector = sa_inspect(engine)
    all_tables = inspector.get_table_names()

    selected_tables = [t for t in PREFERRED_TABLES if t in all_tables]
    if not selected_tables:
        selected_tables = all_tables

    schema_lines = []
    for table_name in selected_tables:
        schema_lines.append(f"TABLE: {table_name}")
        columns = inspector.get_columns(table_name)
        for col in columns:
            schema_lines.append(f"  - {col['name']} ({col['type']})")
        schema_lines.append("")

    return "\n".join(schema_lines), selected_tables


def extract_json_object(raw_text: str) -> Dict:
    cleaned = raw_text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError(f"Gemini did not return JSON. Raw response:\n{raw_text}")

    return json.loads(match.group(0))


def clean_sql(sql: str) -> str:
    sql = sql.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    sql = sql.strip("`").strip()
    return sql


def normalize_table_name(name: str) -> str:
    name = name.replace('"', "").strip()
    return name.split(".")[-1].lower()


def validate_sql(sql: str, allowed_tables: List[str]) -> str:
    sql = clean_sql(sql)
    sql_no_semicolon = sql.rstrip().rstrip(";")
    lowered = sql_no_semicolon.lower()

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    if len(statements) > 1:
        raise ValueError("Blocked SQL: multiple statements are not allowed.")

    if not lowered.startswith("select"):
        raise ValueError("Blocked SQL: only SELECT queries are allowed.")

    for word in FORBIDDEN_SQL_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            raise ValueError(f"Blocked SQL: forbidden keyword found: {word}")

    referenced_tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_\.]*|\"[^\"]+\")", lowered)
    allowed_set = {t.lower() for t in allowed_tables}

    for table in referenced_tables:
        normalized = normalize_table_name(table)
        if normalized not in allowed_set:
            raise ValueError(f"Blocked SQL: table '{table}' is not in allowed tables: {allowed_tables}")

    if " limit " not in f" {lowered} ":
        is_aggregate = bool(re.search(r"\b(count|avg|sum|min|max)\s*\(", lowered))
        has_group_by = " group by " in f" {lowered} "
        if not is_aggregate and not has_group_by:
            sql_no_semicolon += "\nLIMIT 50"

    return sql_no_semicolon + ";"


def generate_sql(question: str, schema_context: str, allowed_tables: List[str]) -> Dict[str, str]:
    client = make_gemini_client()

    prompt = f"""
You are a PostgreSQL data analyst for an oil spill detection project.

Your task:
Convert the user's question into ONE safe PostgreSQL SELECT query.

Database schema:
{schema_context}

Allowed tables only:
{", ".join(allowed_tables)}

Strict rules:
1. Return ONLY valid JSON.
2. JSON format:
   {{
     "sql": "SELECT ...",
     "reason": "short reason"
   }}
3. Use SELECT only.
4. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, COPY, CALL.
5. Use LIMIT 50 unless the user asks for a specific number or the query is an aggregate.
6. For text search on filenames, use ILIKE.
7. Important database values:
   - risk_level values are uppercase: CRITICAL, HIGH, MEDIUM, LOW.
   - For Arabic الحرجة / حرج / critical use UPPER(risk_level) = CRITICAL.
   - For عالية / high use UPPER(risk_level) = HIGH.
   - For متوسطة / medium use UPPER(risk_level) = MEDIUM.
   - For منخفضة / low use UPPER(risk_level) = LOW.
   - For risk_level comparisons, always use UPPER(risk_level).
8. For Arabic questions:
   - "اخطر" or "أخطر" means order by risk_score DESC.
   - "اقرب للشعب" means order by distance_to_coral_km ASC.
   - "اقرب لليابسة" or "الساحل" means order by distance_to_land_km ASC.
   - "كم" often means COUNT.
   - "مساحة" means area_m2 or area_px.
8. If the user asks why a spill is risky, select risk_score, risk_level, risk_factors,
   area_m2, coverage_pct, spread_ratio, distance_to_land_km, distance_to_coral_km,
   spill_centroid_lat, spill_centroid_lon, filename.
9. Do not select llm_report_html unless the user explicitly asks for report text.

User question:
{question}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    parsed = extract_json_object(response.text or "")
    sql = validate_sql(parsed["sql"], allowed_tables)

    return {
        "sql": sql,
        "reason": parsed.get("reason", ""),
    }


def run_sql(engine, sql: str) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def truncate_value(value, max_chars: int = 700):
    if value is None:
        return ""
    text_value = str(value)
    if len(text_value) > max_chars:
        return text_value[:max_chars] + "..."
    return text_value


def dataframe_to_context(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "No rows returned."

    sample = df.head(max_rows).copy()

    for col in sample.columns:
        sample[col] = sample[col].apply(truncate_value)

    try:
        table_text = sample.to_markdown(index=False)
    except Exception:
        table_text = sample.to_string(index=False)

    return f"Total rows returned: {len(df)}\nShowing first {len(sample)} rows:\n\n{table_text}"


def generate_final_answer(question: str, sql: str, data_context: str) -> str:
    client = make_gemini_client()

    prompt = f"""
You are an AI assistant for an oil spill analysis system.

Answer the user in Arabic.

Use ONLY the SQL result below.
Do not invent any number, filename, location, risk score, or date.
If the result is empty, say clearly that no matching records were found.
Make the answer clear and useful for a technical graduation project.

User question:
{question}

SQL used:
{sql}

Database result:
{data_context}

Arabic answer:
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
    )

    return response.text or ""



def rule_based_sql(question: str):
    q = question.lower()

    # Arabic words as unicode escapes to avoid Windows encoding problems
    word_count = "\u0643\u0645"          # كم
    word_number = "\u0639\u062f\u062f"   # عدد
    word_spill = "\u062a\u0633\u0631\u0628"  # تسرب
    word_critical = "\u062d\u0631\u062c"     # حرج
    word_critical2 = "\u062d\u0631\u062c\u0629"  # حرجة
    word_dangerous = "\u0623\u062e\u0637\u0631"  # أخطر
    word_dangerous2 = "\u0627\u062e\u0637\u0631" # اخطر

    wants_count = (word_count in q) or (word_number in q) or ("count" in q)
    talks_spills = (word_spill in q) or ("spill" in q)
    talks_critical = (word_critical in q) or (word_critical2 in q) or ("critical" in q)

    if wants_count and talks_spills and talks_critical:
        return {
            "sql": "SELECT COUNT(*) AS critical_spills FROM spill_analysis_results WHERE UPPER(risk_level) = 'CRITICAL';",
            "reason": "rule-based SQL fallback: count critical spills"
        }

    if wants_count and talks_spills:
        return {
            "sql": "SELECT COUNT(*) AS total_spills FROM spill_analysis_results;",
            "reason": "rule-based SQL fallback: count total spills"
        }

    if ((word_dangerous in q) or (word_dangerous2 in q) or ("most dangerous" in q)) and talks_spills:
        return {
            "sql": "SELECT filename, risk_score, risk_level, area_m2, spill_centroid_lat, spill_centroid_lon, distance_to_land_km, distance_to_coral_km, risk_factors FROM spill_analysis_results ORDER BY risk_score DESC, area_m2 DESC LIMIT 1;",
            "reason": "rule-based SQL fallback: most dangerous spill"
        }

    return None



def answer_question(question: str, show_sql: bool = False) -> str:
    engine = make_engine()
    schema_context, allowed_tables = get_schema_context(engine)

    sql_plan = rule_based_sql(question)
    if sql_plan is None:
        sql_plan = generate_sql(question, schema_context, allowed_tables)

    sql = sql_plan["sql"]

    if show_sql:
        print("\nGenerated SQL:")
        print(sql)
        if sql_plan.get("reason"):
            print("\nReason:")
            print(sql_plan["reason"])

    df = run_sql(engine, sql)
    data_context = dataframe_to_context(df)

    if show_sql:
        print("\nDatabase result preview:")
        print(data_context)

    return generate_final_answer(question, sql, data_context)


def print_schema():
    engine = make_engine()
    schema_context, allowed_tables = get_schema_context(engine)

    print("=" * 80)
    print("Connected database:")
    print(f"{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("=" * 80)
    print("Allowed tables:")
    for table in allowed_tables:
        print(f"- {table}")
    print("=" * 80)
    print(schema_context)


def run_chat(show_sql: bool = False):
    print("\n" + "=" * 80)
    print("Gemini Oil Spill Database Agent")
    print("=" * 80)
    print(f"Model: {GEMINI_MODEL}")
    print(f"Database: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("Type 'exit' to stop.")
    print("=" * 80 + "\n")

    while True:
        question = input("سؤالك: ").strip()

        if not question:
            continue

        if question.lower() in ["exit", "quit", "q", "خروج"]:
            print("تم الإنهاء.")
            break

        try:
            answer = answer_question(question, show_sql=show_sql)
            print("\nالجواب:")
            print(answer)
            print("\n" + "-" * 80 + "\n")
        except Exception as e:
            print("\nError:")
            print(e)
            print("\n" + "-" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Gemini Oil Spill Database Agent")
    parser.add_argument("--ask", type=str, default=None, help="Ask one question")
    parser.add_argument("--chat", action="store_true", help="Run interactive chat")
    parser.add_argument("--schema", action="store_true", help="Show database schema")
    parser.add_argument("--show-sql", action="store_true", help="Show generated SQL and result preview")

    args = parser.parse_args()

    if args.schema:
        print_schema()
        return

    if args.ask:
        answer = answer_question(args.ask, show_sql=args.show_sql)
        print("\nالجواب:")
        print(answer)
        return

    run_chat(show_sql=args.show_sql)


if __name__ == "__main__":
    main()
