"""
=============================================================
RAG Step 2: Query interface (Groq edition)
=============================================================
هذا الملف يسترجع المعلومات من ChromaDB ثم يرسل السياق إلى Groq LLM
ويُرجع إجابة عربية مبنية على المستندات فقط.
"""

from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from groq import Groq
import os


# =========================
# الإعدادات
# =========================

# مسار هذا الملف: /Users/rana/Documents/tuwaiq/CP/external_rag/rag_query.py
BASE_DIR = Path(__file__).resolve().parent

# قاعدة بيانات Chroma داخل external_rag/rag_db
DB_DIR = BASE_DIR / "rag_db"

COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# Groq models:
# - llama-3.3-70b-versatile  الأقوى
# - llama-3.1-8b-instant     الأسرع
LLM_MODEL = "llama-3.3-70b-versatile"

TOP_K = 5


# =========================
# مفتاح Groq
# =========================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "Missing GROQ_API_KEY. شغلي هذا الأمر في التيرمنل قبل تشغيل الباك إند:\n"
        'export GROQ_API_KEY="your_groq_key_here"'
    )


# =========================
# Glossary للمصطلحات التقنية
# =========================

TECHNICAL_GLOSSARY = """
- Containment boom = حاجز احتواء عائم
- Dispersant = مشتت كيميائي
- In-situ burning = الحرق في الموقع
- Skimmer = جهاز كشط/جمع النفط
- Weathering = التجوية (تغير خصائص النفط بمرور الوقت)
- Emulsion = مستحلب (نفط ممزوج بالماء)
- Sorbent = مادة ماصة
- Slick = طبقة النفط الطافية
- Mousse = موس النفط (مستحلب لزج)
- Spill response = الاستجابة للتسرب
- Shoreline cleanup = تنظيف الشواطئ
- Fate of oil = مآل النفط (ما يحدث له بعد التسرب)
- Evaporation = التبخر
- Dissolution = الذوبان
- Dispersion = التشتت الطبيعي
- Sedimentation = الترسب
- Biodegradation = التحلل البيولوجي
- Photo-oxidation = الأكسدة الضوئية
"""


# =========================
# System Prompt
# =========================

SYSTEM_PROMPT = f"""
أنت مساعد متخصص في مجال تسرب النفط البحري والاستجابة له.

مهمتك:
1. الإجابة على أسئلة المستخدم بناءً على السياق المرفق فقط من المستندات التقنية.
2. أجب دائماً باللغة العربية بأسلوب علمي واضح.
3. استخدم المصطلحات التقنية العربية الصحيحة من القاموس أدناه.
4. إذا كان السؤال عن التنظيف أو الاستجابة أو الحلول، ركّز على مقاطع ملفات PDF التقنية وليس ملف CSV الخاص بالحالات.
5. إذا كان السؤال عن التأثير على الأسماك أو الحياة البحرية أو البيئة، استخدم أي معلومات في السياق عن المصايد، التسمم، الموائل، أو الشعاب.
6. إذا وُجد في السياق أي معلومات مفيدة (حتى جزئية) عن السؤال، استخدمها ولا تقل إن المعلومات غير كافية.
7. إذا كان السؤال «ما الفرق بين X و Y» ووجدت في السياق معلومات عن أحدهما أو كليهما، اشرح الفرق بوضوح في نقاط.
8. لا تقل «لا تتوفر معلومات» إذا ذُكرت في السياق كلمات مثل: dispersant, skimmer, مشتت, كشط, boom, تنظيف.
9. إذا كان السياق فارغاً تماماً فقط، قل:
   "لا تتوفر لدي معلومات كافية عن هذا في المستندات الحالية."
10. اذكر المصدر في نهاية الإجابة بالشكل:
   [المصدر: اسم_المستند، صفحة X]
11. لا تخترع معلومات غير موجودة في السياق.

قاموس المصطلحات التقنية:
{TECHNICAL_GLOSSARY}
"""

# =========================
# تحميل الموارد مرة واحدة
# =========================

print("Loading embedder...")
embedder = SentenceTransformer(EMBED_MODEL)

print("Connecting to ChromaDB...")
client = chromadb.PersistentClient(
    path=str(DB_DIR),
    settings=Settings(anonymized_telemetry=False),
)

try:
    collection = client.get_collection(COLLECTION)
    print(f"Loaded collection '{COLLECTION}' with {collection.count()} chunks.")
except Exception as e:
    print(f"❌ Collection '{COLLECTION}' not found.")
    print("تأكدي أن rag_db موجود داخل external_rag.")
    print("أو شغلي ملف بناء الفهرس أولاً مثل:")
    print("python build_rag_index_mac.py")
    raise SystemExit(1) from e

llm_client = Groq(api_key=GROQ_API_KEY)


# =========================
# دالة البحث
# =========================

def is_response_or_cleanup_question(query: str) -> bool:
    q = query.lower()

    keywords = [
        "تنظيف", "حل", "حلول", "استجابة", "معالجة", "احتواء", "إزالة",
        "الشاطئ", "الشواطئ", "قريب من الشاطئ", "قريب من اليابسة",
        "مشتت", "مشتتات", "كشط", "كاشط", "الفرق بين", "ما الفرق",
        "boom", "containment", "cleanup", "clean-up", "shoreline",
        "response", "skimmer", "dispersant", "sorbent", "bioremediation",
        "in-situ", "burning",
    ]

    return any(word in q for word in keywords)


def is_environmental_impact_question(query: str) -> bool:
    q = query.lower()
    oil_terms = ["تسرب", "نفط", "spill", "oil", "marine", "بحري"]
    env_terms = [
        "خطورة", "خطر", "مخاطر", "تأثير", "اثر", "أثر", "ضرر", "أضرار",
        "الاسماك", "الأسماك", "اسماك", "أسماك", "سمك", "مصايد", "مصائد",
        "الحياة البحرية", "بيئي", "البيئة", "شعاب", "مرجان", "سلسلة غذائية",
        "fish", "fisheries", "mariculture", "wildlife", "ecosystem", "habitat",
        "environment", "environmental", "impact", "damage", "toxicity", "coral", "reef",
    ]
    return any(t in q for t in oil_terms) and any(t in q for t in env_terms)


def _prefer_pdf_chunks(raw_chunks: list[dict], k: int, *, pdf_only: bool = False) -> list[dict]:
    pdf_chunks = [c for c in raw_chunks if not str(c.get("source", "")).lower().endswith(".csv")]
    if pdf_chunks:
        return pdf_chunks[:k]
    if pdf_only:
        return []
    ranked = sorted(
        raw_chunks,
        key=lambda c: (
            str(c.get("source", "")).lower().endswith(".csv"),
            -float(c.get("score") or 0),
        ),
    )
    return ranked[:k]


def is_insufficient_rag_answer(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return True
    markers = [
        "لا تتوفر",
        "لا توجد معلومات",
        "غير كافية",
        "لا أملك معلومات",
        "not enough information",
        "do not have enough",
        "cannot answer",
    ]
    return any(m in t for m in markers)


def _boost_response_method_chunks(chunks: list[dict], query: str) -> list[dict]:
    """يفضّل TIP 4 (مشتتات) و TIP 5 (كشط) عند أسئلة المقارنة."""
    q = (query or "").lower()
    want_disp = any(t in q for t in ["مشتت", "dispersant", "مشتتات"])
    want_skim = any(t in q for t in ["كشط", "كاشط", "skimmer", "skimming"])

    def rank_key(c: dict) -> tuple:
        src = str(c.get("source", "")).lower()
        bonus = 0.0
        if want_disp and ("tip_4" in src or "dispersant" in src):
            bonus += 3.0
        if want_skim and ("tip_5" in src or "skimmer" in src):
            bonus += 3.0
        if "tip_7" in src and (want_disp or want_skim):
            bonus -= 0.5
        return (-(bonus + float(c.get("score") or 0)),)

    return sorted(chunks, key=rank_key)


def _boost_fisheries_chunks(chunks: list[dict]) -> list[dict]:
    fisheries_tokens = (
        "fisheries", "mariculture", "marine_environment", "marine environment",
        "tip_11", "tip_13", "fish", "fishery",
    )
    return sorted(
        chunks,
        key=lambda c: (
            0
            if any(token in str(c.get("source", "")).lower() for token in fisheries_tokens)
            else 1,
            -float(c.get("score") or 0),
        ),
    )


def expand_query_for_cleanup(query: str) -> str:
    if is_response_or_cleanup_question(query):
        q = query.lower()
        extra = (
            " oil spill shoreline cleanup response methods containment boom "
            "skimmer sorbents dispersants bioremediation shoreline clean-up"
        )
        if "الفرق" in q or "difference" in q:
            extra += (
                " chemical dispersant vs surface skimming comparison "
                "TIP_4_Use_of_Dispersants TIP_5_Use_of_Skimmers difference between"
            )
        return query + extra

    if is_environmental_impact_question(query):
        return (
            query
            + " oil spill effects on fish fisheries mariculture marine environment "
              "marine life toxicity habitat coral reef food chain environmental impact"
        )

    return query


def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    """
    تبحث في ChromaDB وترجع أقرب المقاطع للسؤال.
    إذا السؤال عن التنظيف أو الحلول، تقلل الاعتماد على ملف CSV وتفضّل ملفات PDF.
    """

    if not query or not query.strip():
        return []

    search_query = expand_query_for_cleanup(query)

    query_emb = embedder.encode(
        [search_query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).tolist()

    # نجيب عدد أكبر ثم نفلتر
    results = collection.query(
        query_embeddings=query_emb,
        n_results=max(k * 4, 20),
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    raw_chunks = []

    for doc, meta, dist in zip(documents, metadatas, distances):
        meta = meta or {}

        source = meta.get("source", "unknown_source")
        page_or_chunk = meta.get("page", meta.get("chunk", "N/A"))

        raw_chunks.append(
            {
                "text": doc,
                "source": source,
                "page": page_or_chunk,
                "score": round(1 - dist, 4),
            }
        )

    # أسئلة الحلول/التنظيف: نفضّل PDFs (ITOPF) على CSV الحالات
    if is_response_or_cleanup_question(query):
        preferred = _prefer_pdf_chunks(raw_chunks, max(k * 2, 10))
        boosted = _boost_response_method_chunks(preferred, query)
        return boosted[:k]

    # أسئلة التأثير البيئي: PDFs فقط (لا نستخدم CSV الحالات أبداً)
    if is_environmental_impact_question(query):
        preferred = _prefer_pdf_chunks(raw_chunks, k, pdf_only=True)
        if preferred:
            return _boost_fisheries_chunks(preferred)[:k]
        return []

    return raw_chunks[:k]

# =========================
# بناء السياق
# =========================

def build_context(chunks: list[dict]) -> str:
    """
    يحول المقاطع المسترجعة إلى نص واضح للـ LLM.
    """

    if not chunks:
        return "لا توجد مقاطع مسترجعة من قاعدة المعرفة."

    parts = []

    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"[المصدر {i}: {c['source']}, صفحة/مقطع {c['page']}, score={c['score']}]\n"
            f"{c['text']}\n"
        )

    return "\n---\n".join(parts)


# =========================
# دالة الجواب
# =========================

def answer(query: str, k: int = TOP_K, verbose: bool = True) -> dict:
    """
    تستقبل سؤال المستخدم، تبحث في RAG، ثم ترجع إجابة عربية.
    """

    query = query.strip()

    if not query:
        return {
            "query": query,
            "answer": "اكتبي سؤالاً واضحاً أولاً.",
            "sources": [],
        }

    chunks = retrieve(query, k)
    context = build_context(chunks)

    if verbose:
        print(f"\n📚 المصادر المسترجعة ({len(chunks)}):")
        for c in chunks:
            print(f"   • {c['source']} (page/chunk: {c['page']}) — score: {c['score']}")

    if not chunks:
        return {
            "query": query,
            "answer": "لا تتوفر لدي معلومات كافية عن هذا في المستندات الحالية.",
            "sources": [],
        }

    user_msg = f"""
السياق المسترجع من المستندات:
═══════════════════════════════════════════
{context}
═══════════════════════════════════════════

السؤال:
{query}

أجب بالعربية بناءً على السياق أعلاه فقط، واذكر المصادر.
"""

    def _call_llm(user_content: str, force_answer: bool = False) -> str:
        system = SYSTEM_PROMPT
        if force_answer:
            system += (
                "\n\nتنبيه عاجل: السياق يحتوي معلومات ذات صلة. "
                "يجب الإجابة من السياق الآن. ممنوع قول أن المعلومات غير كافية."
            )
        response = llm_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=1200,
        )
        return str(response.choices[0].message.content or "").strip()

    answer_text = _call_llm(user_msg, force_answer=False)

    if chunks and is_insufficient_rag_answer(answer_text):
        retry_msg = f"""
السياق المسترجع (يجب استخدامه):
═══════════════════════════════════════════
{context}
═══════════════════════════════════════════

السؤال: {query}

اكتب إجابة عربية واضحة. إذا السؤال عن الفرق بين تقنيتين، استخدم هذا القالب:
- تعريف المشتت الكيميائي ومتى يُستخدم
- تعريف الكشط السطحي ومتى يُستخدم
- الفرق الرئيسي
- متى نفضّل كل خيار
- اذكر [المصدر: ...] من السياق
"""
        answer_text = _call_llm(retry_msg, force_answer=True)

    return {
        "query": query,
        "answer": answer_text,
        "sources": chunks,
    }


# =========================
# واجهة المحادثة من التيرمنل
# =========================

def chat_loop():
    print("\n" + "=" * 60)
    print("🛢️ Oil Spill RAG Assistant - Groq Powered")
    print("=" * 60)
    print("اكتبي سؤالك عربي أو إنجليزي.")
    print("للخروج اكتبي: exit أو خروج\n")

    while True:
        try:
            query = input("\n❓ أنت: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 مع السلامة")
            break

        if not query:
            continue

        if query.lower() in ["exit", "quit", "خروج", "q"]:
            print("👋 مع السلامة")
            break

        try:
            result = answer(query)
            print(f"\n🤖 المساعد:\n{result['answer']}")
        except Exception as e:
            print(f"\n❌ خطأ: {e}")


if __name__ == "__main__":
    chat_loop()