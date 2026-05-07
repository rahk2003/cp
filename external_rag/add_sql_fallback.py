from pathlib import Path

p = Path("agent_module.py")
t = p.read_text(encoding="utf-8")

insert = r'''
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

'''

if "def rule_based_sql(question: str):" not in t:
    t = t.replace("def answer_question(", insert + "\n\ndef answer_question(")

old = '''    sql_plan = generate_sql(question, schema_context, allowed_tables)
    sql = sql_plan["sql"]
'''

new = '''    sql_plan = rule_based_sql(question)
    if sql_plan is None:
        sql_plan = generate_sql(question, schema_context, allowed_tables)

    sql = sql_plan["sql"]
'''

if old in t:
    t = t.replace(old, new)
elif "sql_plan = rule_based_sql(question)" in t:
    print("Already patched.")
else:
    print("Could not find the target block. Check answer_question manually.")

p.write_text(t, encoding="utf-8")
print("SQL fallback added successfully.")
