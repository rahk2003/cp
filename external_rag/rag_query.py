"""
=============================================================
RAG Step 2: Query interface (Groq edition - مجاني)
=============================================================
نفس الكود السابق، لكن يستخدم Groq API بدل OpenAI.
Groq مجاني وسريع جداً (Llama 3.3 70B).

سجلي مفتاح مجاني: https://console.groq.com
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
DB_DIR = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_db")
COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# نماذج Groq المتاحة (الأقوى أولاً):
# - "llama-3.3-70b-versatile"     ← الأقوى (موصى به)
# - "llama-3.1-8b-instant"        ← الأسرع
# - "mixtral-8x7b-32768"          ← context طويل
LLM_MODEL = "llama-3.3-70b-versatile"
TOP_K     = 5

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "PUT_YOUR_GROQ_API_KEY_HERE")


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
SYSTEM_PROMPT = f"""أنت مساعد متخصص في مجال تسرب النفط البحري والاستجابة له.

مهمتك:
1. الإجابة على أسئلة المستخدم بناءً على السياق المرفق فقط (من مستندات تقنية إنجليزية).
2. أجب دائماً باللغة العربية بأسلوب علمي واضح، حتى لو كان السياق بالإنجليزية.
3. استخدم المصطلحات التقنية العربية الصحيحة من القاموس أدناه.
4. إذا كان السياق لا يحتوي على إجابة، قل بصراحة: "لا تتوفر لدي معلومات كافية عن هذا في المستندات الحالية."
5. اذكر المصدر في نهاية الإجابة بالشكل: [المصدر: اسم_المستند، صفحة X]
6. لا تخترع معلومات غير موجودة في السياق.

قاموس المصطلحات التقنية:
{TECHNICAL_GLOSSARY}
"""


# =========================
# تحميل الموارد
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
except Exception:
    print(f"❌ Collection '{COLLECTION}' not found.")
    print(f"   شغّلي rag_build_index.py أولاً.")
    raise SystemExit(1)

llm_client = Groq(api_key=GROQ_API_KEY)


# =========================
# دالة البحث
# =========================
def retrieve(query: str, k: int = TOP_K) -> list[dict]:
    query_emb = embedder.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).tolist()

    results = collection.query(
        query_embeddings=query_emb,
        n_results=k,
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text":   doc,
            "source": meta["source"],
            "page":   meta["page"],
            "score":  round(1 - dist, 4),
        })
    return chunks


# =========================
# دالة الجواب
# =========================
def build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"[المصدر {i}: {c['source']}, صفحة {c['page']}, score={c['score']}]\n"
            f"{c['text']}\n"
        )
    return "\n---\n".join(parts)


def answer(query: str, k: int = TOP_K, verbose: bool = True) -> dict:
    chunks  = retrieve(query, k)
    context = build_context(chunks)

    if verbose:
        print(f"\n📚 المصادر المسترجعة ({len(chunks)}):")
        for c in chunks:
            print(f"   • {c['source']} (p.{c['page']}) — score: {c['score']}")

    user_msg = f"""السياق المسترجع من المستندات:
═══════════════════════════════════════════
{context}
═══════════════════════════════════════════

السؤال: {query}

أجب بالعربية بناءً على السياق أعلاه فقط، واذكر المصادر."""

    response = llm_client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    answer_text = response.choices[0].message.content

    return {
        "query":   query,
        "answer":  answer_text,
        "sources": chunks,
    }


# =========================
# واجهة المحادثة
# =========================
def chat_loop():
    print("\n" + "=" * 60)
    print("🛢️  Oil Spill RAG Assistant (Groq powered)")
    print("=" * 60)
    print("اكتبي سؤالك (عربي أو إنجليزي). للخروج اكتبي 'exit' أو 'خروج'.\n")

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

    
