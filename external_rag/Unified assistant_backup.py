"""
=============================================================
Unified Oil Spill Assistant
=============================================================
يوحّد:
  1) SQL Agent (Gemini + Postgres)   -> أسئلة البيانات (إحصائيات/تسربات معينة)
  2) RAG       (Groq  + ChromaDB)    -> أسئلة المعرفة (PDFs)

طريقة العمل:
  السؤال يدخل -> Router (rules أولاً ثم LLM لو ما حسم) ->
    - sql      => agent_module.answer_question(...)
    - rag      => rag_module.answer(...)
    - hybrid   => الاثنين، ثم Gemini يدمج الإجابتين بالعربي
=============================================================
"""

from __future__ import annotations

import os
import re
import json
from typing import Dict, Any, Tuple

from dotenv import load_dotenv
from google import genai

# نستورد الكودين الموجودين عندك (نفس أسماء الملفات اللي ترسلين)
# عدّلي الأسماء هنا لو عندك ملفات بأسماء ثانية
import agent_module          # = الكود الأول (SQL agent)
import rag_query as rag_module  # = الكود الثاني (RAG / Groq)


load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


# =====================================================================
# 1) Router rules  -- بالعربي والإنجليزي
# =====================================================================
# كلمات تدل على أن السؤال عن البيانات (الـ DB)
SQL_KEYWORDS = [
    # عربي
    "كم", "عدد", "أعلى", "اعلى", "أقل", "اقل", "أكبر", "اكبر", "أصغر", "اصغر",
    "أخطر", "اخطر", "أحدث", "احدث", "آخر", "اخر",
    "اقرب", "أقرب", "اقرب للشعب", "اقرب للساحل", "اقرب لليابسة",
    "متوسط", "مجموع", "إجمالي", "اجمالي",
    "risk score", "risk_score", "risk level", "risk_level",
    "spill_id", "filename", "اسم الملف", "نسبة التغطية", "coverage",
    "area_m2", "area_px", "spread_ratio",
    "distance_to_land", "distance_to_coral",
    "spill_centroid", "lat", "lon", "إحداثيات", "احداثيات",
    "في قاعدة البيانات", "من القاعدة", "في الجدول",
    "list", "show me", "كم تسرب", "كم سبيل", "تسربات",
]

# كلمات تدل على أن السؤال معرفي (RAG)
RAG_KEYWORDS = [
    # عربي
    "كيف", "ماهو", "ما هو", "ما هي", "ماهي", "تعريف", "اشرح", "اشرحي",
    "ما الفرق", "الفرق بين", "لماذا", "ليش", "متى نستخدم",
    "الاستجابة", "استجابة", "تنظيف", "احتواء", "حاجز", "boom",
    "dispersant", "مشتت", "skimmer", "كاشط",
    "weathering", "تجوية", "emulsion", "مستحلب",
    "biodegradation", "تحلل", "evaporation", "تبخر",
    "shoreline", "شاطئ", "in-situ burning", "حرق في الموقع",
    "fate of oil", "مآل النفط", "sorbent", "ماصة",
    "best practice", "افضل الممارسات", "أفضل الممارسات",
    "protocol", "بروتوكول", "guidelines", "إرشادات",
]

# كلمات تدل على سؤال هجين (يحتاج البيانات + التوصية)
HYBRID_HINTS = [
    "ماذا أفعل", "ما الذي يجب", "كيف أتعامل", "كيف نتعامل",
    "وش اسوي", "وش نسوي", "التوصية", "أوصي", "اوصي",
    "خطة الاستجابة", "ما هي الخطوات",
    "what should i do", "how to respond", "recommendation",
]


def _contains_any(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(k.lower() in low for k in keywords)


def route_with_rules(question: str) -> str | None:
    """
    يرجّع:
        "sql"    | "rag" | "hybrid"  -> إذا rules حسمت
        None                          -> إذا ما قدرت تحسم (نسأل LLM)
    """
    has_sql    = _contains_any(question, SQL_KEYWORDS)
    has_rag    = _contains_any(question, RAG_KEYWORDS)
    has_hybrid = _contains_any(question, HYBRID_HINTS)

    # إشارة هجينة قوية
    if has_hybrid and has_sql:
        return "hybrid"
    if has_hybrid and has_rag:
        return "hybrid"

    # إشارة واحدة واضحة
    if has_sql and not has_rag:
        return "sql"
    if has_rag and not has_sql:
        return "rag"

    # الاثنين موجودين → هجين
    if has_sql and has_rag:
        return "hybrid"

    # ما حسم
    return None


# =====================================================================
# 2) Router LLM fallback (Gemini)
# =====================================================================
_gemini_client = None

def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "PUT_YOUR_GEMINI_API_KEY_HERE":
            raise ValueError("Missing GEMINI_API_KEY in .env")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


ROUTER_PROMPT = """أنت موجِّه أسئلة (Router) لنظام تحليل تسربات النفط.

عندك مصدران:
  1) "sql"    : قاعدة بيانات Postgres فيها نتائج تحليل التسربات
                (risk_score, area_m2, distance_to_land_km, distance_to_coral_km,
                 spill_centroid_lat/lon, filename, coverage_pct, ...).
                استخدمه لأي سؤال عن أرقام، إحصائيات، تسرّب معيّن، أعلى/أقل،
                عدد، متوسط، أخطر، أقرب، إلخ.

  2) "rag"    : مستندات PDF تقنية عن تسرب النفط البحري والاستجابة له.
                استخدمه لأي سؤال معرفي/مفاهيمي:
                كيف نتعامل مع تسرب؟ ما هو الـ dispersant؟
                ما خطوات الاحتواء؟ best practices؟ تعريفات؟

  3) "hybrid" : إذا السؤال يحتاج بيانات من القاعدة + معلومات/توصية من المستندات
                مثل: "هذا التسرب الفلاني، وش التوصية بالاستجابة له؟"

أرجع JSON فقط بهذا الشكل (بدون أي شرح إضافي):
{
  "route": "sql" | "rag" | "hybrid",
  "reason": "سبب قصير جداً"
}

السؤال:
"""


def route_with_llm(question: str) -> Dict[str, str]:
    client = _get_gemini()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=ROUTER_PROMPT + question,
    )
    raw = (response.text or "").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            # fallback آمن: hybrid (الأقل ضرراً)
            return {"route": "hybrid", "reason": "router parse failed"}
        data = json.loads(match.group(0))

    route = data.get("route", "hybrid").lower().strip()
    if route not in {"sql", "rag", "hybrid"}:
        route = "hybrid"
    return {"route": route, "reason": data.get("reason", "")}


def decide_route(question: str, verbose: bool = False) -> Dict[str, str]:
    """Hybrid routing: rules أولاً، ثم LLM إذا ما حسم."""
    rule_decision = route_with_rules(question)
    if rule_decision is not None:
        if verbose:
            print(f"[Router] rules → {rule_decision}")
        return {"route": rule_decision, "reason": "matched by rules"}

    if verbose:
        print("[Router] rules لم تحسم، نسأل Gemini...")
    decision = route_with_llm(question)
    if verbose:
        print(f"[Router] LLM → {decision['route']}  ({decision.get('reason','')})")
    return decision


# =====================================================================
# 3) Hybrid merger -- يدمج إجابتي SQL و RAG في إجابة عربية واحدة
# =====================================================================
MERGE_PROMPT = """أنت مساعد عربي لنظام تحليل تسربات النفط.

عندك إجابتان:

[إجابة من قاعدة البيانات (بيانات حقيقية للتسرب)]
{sql_answer}

[إجابة من المستندات التقنية (معرفة عامة وتوصيات)]
{rag_answer}

اكتب إجابة عربية واحدة موحّدة:
- ابدأ بالحقائق من قاعدة البيانات (أرقام، أسماء ملفات، إحداثيات...).
- ثم اربطها بالمعرفة من المستندات (كيف نتعامل، توصيات، تفسير).
- لا تخترع أرقاماً غير موجودة في إجابة قاعدة البيانات.
- اذكر مصادر المستندات إذا كانت موجودة في إجابة RAG.
- إذا أحد المصدرين فاضي/ما لقى شيء، اعتمد على الآخر فقط.

السؤال الأصلي:
{question}

الإجابة العربية الموحّدة:
"""


def merge_answers(question: str, sql_answer: str, rag_answer: str) -> str:
    client = _get_gemini()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=MERGE_PROMPT.format(
            question=question,
            sql_answer=sql_answer or "(لا توجد إجابة من قاعدة البيانات)",
            rag_answer=rag_answer or "(لا توجد إجابة من المستندات)",
        ),
    )
    return response.text or ""


# =====================================================================
# 4) الواجهة الموحدة
# =====================================================================
def answer_unified(question: str, verbose: bool = False) -> Dict[str, Any]:
    """
    يرجّع dict فيه:
      route, sql_answer (لو وجد), rag_answer (لو وجد), final_answer
    """
    decision = decide_route(question, verbose=verbose)
    route = decision["route"]

    out: Dict[str, Any] = {
        "question": question,
        "route": route,
        "route_reason": decision.get("reason", ""),
        "sql_answer": None,
        "rag_answer": None,
        "rag_sources": None,
        "final_answer": None,
    }

    if route == "sql":
        if verbose:
            print("\n[Pipeline] تشغيل SQL Agent ...")
        sql_answer = agent_module.answer_question(question, show_sql=verbose)
        out["sql_answer"] = sql_answer
        out["final_answer"] = sql_answer
        return out

    if route == "rag":
        if verbose:
            print("\n[Pipeline] تشغيل RAG ...")
        rag_result = rag_module.answer(question, verbose=verbose)
        out["rag_answer"] = rag_result["answer"]
        out["rag_sources"] = rag_result.get("sources")
        out["final_answer"] = rag_result["answer"]
        return out

    # hybrid
    if verbose:
        print("\n[Pipeline] هجين: تشغيل SQL + RAG بالتوازي المنطقي ...")

    sql_answer = ""
    rag_answer = ""
    rag_sources = None

    # SQL part — لو فشلت ما توقف العملية كلها
    try:
        sql_answer = agent_module.answer_question(question, show_sql=verbose)
    except Exception as e:
        sql_answer = f"(تعذّر الحصول على بيانات من القاعدة: {e})"
        if verbose:
            print(f"[Pipeline] SQL فشل: {e}")

    # RAG part
    try:
        rag_result = rag_module.answer(question, verbose=verbose)
        rag_answer = rag_result["answer"]
        rag_sources = rag_result.get("sources")
    except Exception as e:
        rag_answer = f"(تعذّر الحصول على معلومات من المستندات: {e})"
        if verbose:
            print(f"[Pipeline] RAG فشل: {e}")

    if verbose:
        print("\n[Pipeline] دمج الإجابتين ...")

    final = merge_answers(question, sql_answer, rag_answer)

    out["sql_answer"] = sql_answer
    out["rag_answer"] = rag_answer
    out["rag_sources"] = rag_sources
    out["final_answer"] = final
    return out


# =====================================================================
# 5) Chat loop
# =====================================================================
def run_chat(verbose: bool = False):
    print("\n" + "=" * 72)
    print("🛢️  Unified Oil Spill Assistant  (SQL Agent + RAG)")
    print("=" * 72)
    print("اكتبي سؤالك بالعربي أو الإنجليزي. اكتبي 'exit' للخروج.")
    print("الراوتر يقرر تلقائياً: قاعدة البيانات | المستندات | الاثنين معاً.")
    print("=" * 72 + "\n")

    while True:
        try:
            q = input("سؤالك: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nتم الإنهاء.")
            break

        if not q:
            continue
        if q.lower() in {"exit", "quit", "q", "خروج"}:
            print("تم الإنهاء.")
            break

        try:
            result = answer_unified(q, verbose=verbose)

            print(f"\n[المسار المختار: {result['route']}]")
            if verbose and result.get("route_reason"):
                print(f"[سبب: {result['route_reason']}]")

            if result["route"] == "hybrid" and verbose:
                print("\n--- إجابة قاعدة البيانات ---")
                print(result["sql_answer"])
                print("\n--- إجابة المستندات ---")
                print(result["rag_answer"])
                if result.get("rag_sources"):
                    print("\nمصادر RAG:")
                    for s in result["rag_sources"]:
                        print(f"  • {s['source']} (p.{s['page']}) score={s['score']}")
                print("\n--- الإجابة الموحدة ---")

            print("\nالجواب:")
            print(result["final_answer"])
            print("\n" + "-" * 72 + "\n")

        except Exception as e:
            print(f"\nخطأ: {e}\n" + "-" * 72 + "\n")


# =====================================================================
# 6) CLI
# =====================================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unified Oil Spill Assistant")
    parser.add_argument("--ask", type=str, default=None, help="سؤال واحد")
    parser.add_argument("--verbose", action="store_true", help="إظهار تفاصيل التوجيه والـ SQL")
    args = parser.parse_args()

    if args.ask:
        result = answer_unified(args.ask, verbose=args.verbose)
        print(f"\n[المسار: {result['route']}]")
        print("\nالجواب:")
        print(result["final_answer"])
    else:
        run_chat(verbose=args.verbose)