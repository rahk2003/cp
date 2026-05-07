"""
=============================================================
RAG Streamlit Interface
=============================================================
واجهة ويب جميلة للمساعد الذكي.

كيفية التشغيل:
    streamlit run rag_streamlit.py

تتفتح في المتصفح تلقائياً على http://localhost:8501
"""

import streamlit as st
from pathlib import Path
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from groq import Groq
import os
import time

# =========================
# الإعدادات
# =========================
DB_DIR = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_db")
COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"
LLM_MODEL   = "llama-3.3-70b-versatile"
DEFAULT_TOP_K = 5

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "PUT_YOUR_GROQ_API_KEY_HERE")


# =========================
# Glossary
# =========================
TECHNICAL_GLOSSARY = """
- Containment boom = حاجز احتواء عائم
- Dispersant = مشتت كيميائي
- In-situ burning = الحرق في الموقع
- Skimmer = جهاز كشط/جمع النفط
- Weathering = التجوية
- Emulsion = مستحلب
- Sorbent = مادة ماصة
- Slick = طبقة النفط الطافية
- Mousse = موس النفط (مستحلب لزج)
- Spill response = الاستجابة للتسرب
- Shoreline cleanup = تنظيف الشواطئ
- Fate of oil = مآل النفط
- Evaporation = التبخر
- Dissolution = الذوبان
- Dispersion = التشتت الطبيعي
- Sedimentation = الترسب
- Biodegradation = التحلل البيولوجي
- Photo-oxidation = الأكسدة الضوئية
"""

SYSTEM_PROMPT = f"""أنت مساعد متخصص في مجال تسرب النفط البحري والاستجابة له.

مهمتك:
1. الإجابة على أسئلة المستخدم بناءً على السياق المرفق فقط (من مستندات تقنية إنجليزية).
2. أجب دائماً باللغة العربية بأسلوب علمي واضح، حتى لو كان السياق بالإنجليزية.
3. استخدم المصطلحات التقنية العربية الصحيحة من القاموس أدناه.
4. إذا كان السياق لا يحتوي على إجابة، قل بصراحة: "لا تتوفر لدي معلومات كافية عن هذا في المستندات الحالية."
5. اذكر المصدر في نهاية الإجابة.
6. لا تخترع معلومات غير موجودة في السياق.

قاموس المصطلحات التقنية:
{TECHNICAL_GLOSSARY}
"""


# =========================
# إعداد الصفحة
# =========================
st.set_page_config(
    page_title="مساعد تسرب النفط",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS مخصص للعربي
st.markdown("""
<style>
    /* اتجاه RTL للنص العربي */
    .stChatMessage {
        text-align: right;
        direction: rtl;
    }

    /* تنسيق الـ chat input */
    .stChatInput textarea {
        text-align: right;
        direction: rtl;
        font-size: 16px;
    }

    /* لون الخلفية الجانبية */
    section[data-testid="stSidebar"] {
        background-color: #f0f4f8;
    }

    /* تنسيق الـ source cards */
    .source-card {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        border-right: 4px solid #1d9e75;
    }

    /* العناوين */
    h1, h2, h3 {
        color: #1e3a5f;
    }

    /* الـ metrics */
    [data-testid="stMetricValue"] {
        font-size: 24px;
        color: #1d9e75;
    }
</style>
""", unsafe_allow_html=True)


# =========================
# تحميل الموارد (cached)
# =========================
@st.cache_resource(show_spinner="جاري تحميل النموذج...")
def load_embedder():
    return SentenceTransformer(EMBED_MODEL)


@st.cache_resource(show_spinner="الاتصال بقاعدة البيانات...")
def load_collection():
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(COLLECTION)


@st.cache_resource
def load_llm_client():
    if not GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)


# =========================
# دوال البحث والإجابة
# =========================
def retrieve(query: str, k: int):
    embedder = load_embedder()
    collection = load_collection()

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


def build_context(chunks):
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(
            f"[المصدر {i}: {c['source']}, صفحة {c['page']}, score={c['score']}]\n"
            f"{c['text']}\n"
        )
    return "\n---\n".join(parts)


def stream_answer(query: str, chunks: list, model: str):
    """يطبع الجواب streaming من الـ LLM."""
    llm = load_llm_client()
    if llm is None:
        yield "❌ مفتاح Groq API غير موجود. أضيفيه في environment variable: GROQ_API_KEY"
        return

    context = build_context(chunks)

    user_msg = f"""السياق المسترجع من المستندات:
═══════════════════════════════════════════
{context}
═══════════════════════════════════════════

السؤال: {query}

أجب بالعربية بناءً على السياق أعلاه فقط، واذكر المصادر."""

    stream = llm.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


# =========================
# الشريط الجانبي
# =========================
with st.sidebar:
    st.markdown("## ⚙️ الإعدادات")

    # عدد المصادر
    top_k = st.slider(
        "عدد المصادر المسترجعة",
        min_value=2,
        max_value=10,
        value=DEFAULT_TOP_K,
        help="كم مصدر يبحث عنه قبل ما يجاوب"
    )

    # اختيار الموديل
    model_choice = st.selectbox(
        "نموذج اللغة",
        options=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ],
        index=0,
        help="70B أقوى، 8B أسرع"
    )

    st.markdown("---")

    # إحصائيات قاعدة البيانات
    st.markdown("## 📊 إحصائيات القاعدة")
    try:
        coll = load_collection()
        total_chunks = coll.count()

        # عدّ المصادر
        all_meta = coll.get(include=["metadatas"])
        sources = set(m["source"] for m in all_meta["metadatas"])

        col1, col2 = st.columns(2)
        with col1:
            st.metric("📄 المستندات", len(sources))
        with col2:
            st.metric("🔖 القطع", total_chunks)

        # قائمة المصادر
        with st.expander("📚 قائمة المستندات"):
            for s in sorted(sources):
                st.markdown(f"- {s}")
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال بقاعدة البيانات\n{e}")

    st.markdown("---")

    # زر مسح المحادثة
    if st.button("🗑️ مسح المحادثة", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.caption("🤖 مدعوم بـ Groq + ChromaDB")


# =========================
# الواجهة الرئيسية
# =========================
st.markdown("# 🛢️ مساعد تسرب النفط الذكي")
st.markdown("اسأل أي سؤال عن تسرب النفط البحري والاستجابة له. الأسئلة تُقبل بالعربية والإنجليزية.")

# تهيئة الجلسة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض المحادثة السابقة
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🤖" if msg["role"] == "assistant" else "👤"):
        st.markdown(msg["content"])

        # عرض المصادر إذا موجودة
        if msg["role"] == "assistant" and "sources" in msg:
            with st.expander(f"📚 المصادر ({len(msg['sources'])})"):
                for i, src in enumerate(msg["sources"], start=1):
                    st.markdown(f"""
                    <div class="source-card">
                        <b>المصدر {i}:</b> {src['source']}<br>
                        <b>الصفحة:</b> {src['page']} | <b>الدقة:</b> {src['score']}<br>
                        <small>{src['text'][:200]}...</small>
                    </div>
                    """, unsafe_allow_html=True)

# أمثلة سريعة (تظهر فقط في البداية)
if not st.session_state.messages:
    st.markdown("### 💡 أمثلة على الأسئلة:")
    cols = st.columns(3)
    examples = [
        "كيف يتحول النفط بعد التسرب؟",
        "ما هي طرق احتواء التسرب؟",
        "وش تأثير النفط على الأسماك؟",
    ]
    for col, example in zip(cols, examples):
        with col:
            if st.button(example, use_container_width=True):
                st.session_state.pending_query = example
                st.rerun()

# معالجة السؤال (سواء من الـ chat input أو من الأمثلة)
query = st.chat_input("اكتبي سؤالك هنا...")

if "pending_query" in st.session_state:
    query = st.session_state.pop("pending_query")

if query:
    # عرض سؤال المستخدم
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user", avatar="👤"):
        st.markdown(query)

    # البحث + الإجابة
    with st.chat_message("assistant", avatar="🤖"):
        # خطوة البحث
        with st.spinner("🔍 جاري البحث في المستندات..."):
            chunks = retrieve(query, k=top_k)

        # عرض الجواب streaming
        placeholder = st.empty()
        full_response = ""

        try:
            for delta in stream_answer(query, chunks, model_choice):
                full_response += delta
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"❌ خطأ: {e}"
            placeholder.markdown(full_response)

        # عرض المصادر
        with st.expander(f"📚 المصادر ({len(chunks)})"):
            for i, src in enumerate(chunks, start=1):
                st.markdown(f"""
                <div class="source-card">
                    <b>المصدر {i}:</b> {src['source']}<br>
                    <b>الصفحة:</b> {src['page']} | <b>الدقة:</b> {src['score']}<br>
                    <small>{src['text'][:200]}...</small>
                </div>
                """, unsafe_allow_html=True)

    # حفظ في الجلسة
    st.session_state.messages.append({
        "role":    "assistant",
        "content": full_response,
        "sources": chunks,
    })
