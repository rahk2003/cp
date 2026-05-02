"""
🛢️ Oil Spill Hybrid Agent (RAG + SQL)
======================================

Agent محلي 100% يدمج:
- SQL Tool: للأسئلة الرقمية والإحصائية (كم/عدد/أكبر/متى)
- RAG Tool: للأسئلة التفسيرية والوصفية (وش يقول التقرير عن.../اشرح/كيف)
- Hybrid: يدمج الاثنين في الأسئلة المركبة

المكونات:
- Ollama llama3.1     → LLM (router + synthesizer)
- nomic-embed-text   → Embeddings (محلي عبر Ollama)
- ChromaDB           → Vector store محلي (بدون server)
- PostgreSQL         → مصدر البيانات الرقمية والميتاداتا

قبل التشغيل:
    pip install langchain-ollama langchain-core chromadb sqlalchemy psycopg2-binary pandas

شغّلي Ollama واسحبي الموديلين:
    ollama serve
    ollama pull llama3.1
    ollama pull nomic-embed-text

طريقة التشغيل:
    # أول مرة (يبني الفهرس من قاعدة البيانات)
    python oil_rag_agent.py --index

    # تشغيل الإيجنت التفاعلي
    python oil_rag_agent.py --chat

    # إعادة الفهرسة + تشغيل الإيجنت
    python oil_rag_agent.py --reindex --chat

    # سؤال واحد سريع
    python oil_rag_agent.py --ask "وش أخطر تسرب وين موقعه؟"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from sqlalchemy import create_engine, text

try:
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    OLLAMA_AVAILABLE = True
except Exception as e:
    print(f"⚠️ langchain_ollama غير مثبت: {e}")
    print("   pip install langchain-ollama langchain-core")
    OLLAMA_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except Exception as e:
    print(f"⚠️ chromadb غير مثبت: {e}")
    print("   pip install chromadb")
    CHROMA_AVAILABLE = False


# ============================================================
# الإعدادات
# ============================================================
@dataclass
class Config:
    # قاعدة البيانات (نفس إعدادات pipeline)
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "oil_spills"

    # Ollama
    OLLAMA_LLM_MODEL: str = "llama3.1"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TEMPERATURE: float = 0.2

    # ChromaDB
    CHROMA_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/chroma_db")
    COLLECTION_NAME: str = "oil_spill_reports"

    # RAG settings
    TOP_K: int = 5                  # كم تقرير نجيب من البحث
    MAX_DOC_CHARS: int = 4000       # نقص التقرير لو طويل جداً
    MIN_AREA_PX: int = 1            # تجاهل التسربات الفاضية في الفهرسة
    INDEX_BATCH: int = 32           # حجم batch للفهرسة

    @property
    def DB_URI(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


CFG = Config()


# ============================================================
# أدوات عامة
# ============================================================
def get_engine():
    return create_engine(CFG.DB_URI)


def run_query(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def clean_llm_sql(text_value: str) -> str:
    text_value = re.sub(r"```sql\s*", "", text_value, flags=re.IGNORECASE)
    text_value = re.sub(r"```\s*", "", text_value)
    return text_value.strip("` \n;") + ";"


def is_select_only(sql: str) -> bool:
    s = sql.strip().lower()
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke"]
    return s.startswith("select") and not any(re.search(rf"\b{x}\b", s) for x in forbidden)


def get_llm():
    if not OLLAMA_AVAILABLE:
        raise ImportError("langchain_ollama غير مثبت")
    return ChatOllama(model=CFG.OLLAMA_LLM_MODEL, temperature=CFG.OLLAMA_TEMPERATURE)


def get_embeddings():
    if not OLLAMA_AVAILABLE:
        raise ImportError("langchain_ollama غير مثبت")
    return OllamaEmbeddings(model=CFG.OLLAMA_EMBED_MODEL)


def strip_html(html) -> str:
    """يشيل HTML tags بشكل بسيط للفهرسة ويتعامل مع القيم الفاضية NaN."""
    if html is None:
        return ""

    try:
        if pd.isna(html):
            return ""
    except Exception:
        pass

    html = str(html)

    if not html.strip():
        return ""

    text_only = re.sub(r"<[^>]+>", " ", html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    return text_only

# ============================================================
# Vector Store (ChromaDB محلي)
# ============================================================
class VectorStore:
    """واجهة بسيطة لـ ChromaDB."""

    def __init__(self):
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb غير مثبت")
        CFG.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(CFG.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self.embeddings = get_embeddings()
        self.collection = self.client.get_or_create_collection(
            name=CFG.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self):
        try:
            self.client.delete_collection(CFG.COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=CFG.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return self.collection.count()

    def add_batch(self, ids: List[str], texts: List[str], metadatas: List[Dict[str, Any]]):
        if not texts:
            return
        vectors = self.embeddings.embed_documents(texts)
        # Chroma metadata قيوده: scalars فقط (str, int, float, bool)
        clean_meta = [_sanitize_metadata(m) for m in metadatas]
        self.collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=clean_meta,
        )

    def query(self, query_text: str, k: int = 5,
              where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        q_vec = self.embeddings.embed_query(query_text)
        res = self.collection.query(
            query_embeddings=[q_vec],
            n_results=k,
            where=where,
        )
        results = []
        if not res["ids"] or not res["ids"][0]:
            return results
        for i in range(len(res["ids"][0])):
            results.append({
                "id": res["ids"][0][i],
                "document": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i] if res.get("distances") else None,
            })
        return results


def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """ChromaDB يقبل scalars فقط. نحول None → '' و الأنواع المعقدة → str."""
    clean = {}
    for k, v in meta.items():
        if v is None:
            clean[k] = ""
        elif isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean


# ============================================================
# بناء الـ Index من قاعدة البيانات
# ============================================================
def build_document(row: Dict[str, Any]) -> str:
    """يبني نص قابل للفهرسة من صف التحليل."""
    parts = []

    parts.append(f"التسرب: {row.get('filename')}")
    parts.append(f"الصورة الأصلية: {row.get('source_image')}")

    # الموقع
    if row.get("spill_centroid_lat") and row.get("spill_centroid_lon"):
        parts.append(
            f"موقع التسرب: lat={row.get('spill_centroid_lat')}, lon={row.get('spill_centroid_lon')}"
        )
    if row.get("date"):
        parts.append(f"التاريخ: {row.get('date')} {row.get('time') or ''}")
    if row.get("crs"):
        parts.append(f"نظام الإحداثيات: {row.get('crs')}")

    # الأرقام
    parts.append(f"المساحة: {row.get('area_m2')} م² ({row.get('area_px')} بكسل)")
    parts.append(f"نسبة التغطية: {row.get('coverage_pct')}%")
    parts.append(f"عدد البقع: {row.get('num_components')}")
    parts.append(f"نسبة الامتداد: {row.get('spread_ratio')}")

    # القرب من اليابسة والشعب
    parts.append(
        f"المسافة إلى اليابسة: {row.get('distance_to_land_km')} كم "
        f"({row.get('land_proximity_class')})"
    )
    parts.append(
        f"المسافة إلى الشعب المرجانية: {row.get('distance_to_coral_km')} كم "
        f"({row.get('coral_proximity_class')})"
    )

    # الخطورة
    parts.append(f"تقييم الخطورة: {row.get('risk_level')} ({row.get('risk_score')}/100)")
    if row.get("risk_factors"):
        parts.append(f"عوامل الخطورة: {row.get('risk_factors')}")

    # تقرير LLM (إذا موجود)
    llm_report = strip_html(row.get("llm_report_html") or "")
    if llm_report:
        if len(llm_report) > CFG.MAX_DOC_CHARS:
            llm_report = llm_report[: CFG.MAX_DOC_CHARS] + "..."
        parts.append("\nالتقرير التفصيلي:")
        parts.append(llm_report)

    return "\n".join(parts)


def build_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    """ميتاداتا للفلترة في البحث (مثلاً where={'risk_level': 'CRITICAL'})."""
    return {
        "filename": row.get("filename"),
        "risk_level": row.get("risk_level") or "NONE",
        "risk_score": float(row.get("risk_score") or 0),
        "area_m2": float(row.get("area_m2") or 0),
        "coverage_pct": float(row.get("coverage_pct") or 0),
        "num_components": int(row.get("num_components") or 0),
        "distance_to_land_km": float(row.get("distance_to_land_km") or 0)
            if row.get("distance_to_land_km") is not None else 0,
        "distance_to_coral_km": float(row.get("distance_to_coral_km") or 0)
            if row.get("distance_to_coral_km") is not None else 0,
        "land_proximity_class": row.get("land_proximity_class") or "",
        "coral_proximity_class": row.get("coral_proximity_class") or "",
        "spill_centroid_lon": float(row.get("spill_centroid_lon"))
            if row.get("spill_centroid_lon") is not None else 0,
        "spill_centroid_lat": float(row.get("spill_centroid_lat"))
            if row.get("spill_centroid_lat") is not None else 0,
        "date": str(row.get("date") or ""),
        "has_llm_report": bool(row.get("llm_report_html")),
    }


def build_index(reset: bool = False) -> int:
    """يبني (أو يعيد بناء) الفهرس من جدول spill_analysis_results."""
    print("=" * 70)
    print("بناء فهرس RAG من قاعدة البيانات")
    print("=" * 70)

    store = VectorStore()
    if reset:
        print("🗑️ حذف الفهرس القديم...")
        store.reset()

    existing = store.count()
    print(f"عدد المستندات الحالية في الفهرس: {existing}")

    # نجيب البيانات من قاعدة البيانات
    sql = """
    SELECT * FROM spill_analysis_results
    WHERE area_px > 0
    ORDER BY filename;
    """
    try:
        df = run_query(sql)
    except Exception as e:
        print(f"❌ خطأ في قراءة قاعدة البيانات: {e}")
        return 0

    if df.empty:
        print("⚠️ ما لقيت تسربات في الجدول (area_px > 0)")
        return 0

    print(f"عدد التسربات للفهرسة: {len(df)}")

    # نتجنب إعادة فهرسة اللي موجود (إلا لو reset)
    existing_ids = set()
    if not reset:
        try:
            res = store.collection.get()
            existing_ids = set(res.get("ids", []))
        except Exception:
            pass

    rows = df.to_dict("records")
    to_index = [r for r in rows if r["filename"] not in existing_ids]
    print(f"الجديد للفهرسة: {len(to_index)} (موجود مسبقاً: {len(rows) - len(to_index)})")

    if not to_index:
        print("✅ الفهرس محدّث، ما فيه شيء جديد للإضافة")
        return store.count()

    # batched indexing
    indexed = 0
    for i in range(0, len(to_index), CFG.INDEX_BATCH):
        batch = to_index[i: i + CFG.INDEX_BATCH]
        ids = [r["filename"] for r in batch]
        texts = [build_document(r) for r in batch]
        metas = [build_metadata(r) for r in batch]
        try:
            store.add_batch(ids, texts, metas)
            indexed += len(batch)
            print(f"  [{indexed}/{len(to_index)}] فُهرس...")
        except Exception as e:
            print(f"  ⚠️ فشلت دفعة عند {i}: {e}")

    final_count = store.count()
    print(f"✅ انتهى الفهرس. الإجمالي الآن: {final_count}")
    return final_count


# ============================================================
# Router: يقرر أي tool يستخدم
# ============================================================
ROUTER_PROMPT = """صنّف سؤال المستخدم إلى واحد فقط:

- sql: السؤال يحتاج عدّ/إحصاء/قائمة دقيقة من قاعدة البيانات.
  أمثلة: "كم تسرب عندي؟"، "أكبر 5 تسربات حسب المساحة"، "وش التواريخ المتاحة؟"

- rag: السؤال يحتاج فهم/تفسير/شرح من تقارير التحليل النصية.
  أمثلة: "وش يقول التقرير عن أخطر تسرب؟"، "اشرح لي الأثر البيئي للتسرب 00004.tif"

- hybrid: السؤال يحتاج الاثنين معاً (أرقام + شرح).
  أمثلة: "وش التسربات اللي تهدد الشعب المرجانية وكم عددها؟"، "اعطني تقرير شامل عن أخطر 3 تسربات"

- chat: محادثة عامة لا تحتاج قاعدة بيانات.
  أمثلة: "مرحبا"، "وش تسوي؟"

أرجع كلمة واحدة فقط من: sql, rag, hybrid, chat

السؤال: {question}
التصنيف:"""


def route_question(question: str) -> str:
    # كلمات مفتاحية سريعة قبل ما نسأل LLM
    q = question.lower().strip()

    # محادثة عامة
    if len(q) < 6 and any(w in q for w in ["مرحبا", "اهلا", "hi", "hello", "السلام"]):
        return "chat"

    # كلمات تشير للأرقام والإحصاء فقط
    pure_sql_signals = ["كم عدد", "كم تسرب", "كم صورة", "أكبر", "اكبر", "أصغر", "اصغر",
                        "أعلى", "اعلى", "أدنى", "ادنى", "متوسط", "average", "count"]
    has_sql = any(w in q for w in pure_sql_signals)

    # كلمات تشير لتفسير/شرح
    rag_signals = ["اشرح", "وضح", "تقرير", "وش يقول", "ليش", "كيف",
                   "explain", "describe", "report", "تفصيل", "تفسير", "أثر", "اثر"]
    has_rag = any(w in q for w in rag_signals)

    if has_sql and has_rag:
        return "hybrid"
    if has_sql and not has_rag:
        return "sql"
    if has_rag and not has_sql:
        return "rag"

    # غامض → نسأل LLM
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(ROUTER_PROMPT)
        out = (prompt | llm | StrOutputParser()).invoke({"question": question}).strip().lower()
        m = re.search(r"(sql|rag|hybrid|chat)", out)
        return m.group(1) if m else "rag"
    except Exception:
        return "rag"


# ============================================================
# SQL Tool
# ============================================================
SQL_PROMPT = """أنت خبير PostgreSQL. حول سؤال المستخدم إلى SQL للقراءة فقط.

الجداول:
- spill_info(file, source_path, date, time, crs, width, height,
            pixel_size_x, pixel_size_y,
            bbox_left, bbox_bottom, bbox_right, bbox_top,
            center_lon, center_lat,
            upper_left_lon, upper_left_lat, upper_right_lon, upper_right_lat,
            lower_right_lon, lower_right_lat, lower_left_lon, lower_left_lat)

- spill_analysis_results(filename, source_image, area_px, area_m2, coverage_pct,
            centroid_x, centroid_y,
            spill_centroid_lon, spill_centroid_lat,
            perimeter_m, spread_ratio, num_components, compactness,
            mean_intensity, max_intensity, std_intensity, density_score,
            distance_to_land_km, land_proximity_class,
            distance_to_coral_km, coral_proximity_class,
            risk_score, risk_level, risk_factors,
            crs, center_lon, center_lat, date, time,
            llm_report_html)

قواعد صارمة:
- SELECT فقط، لا تستخدم INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE
- استخدم LIMIT 50 إلا لو طُلب رقم محدد
- لا تختار llm_report_html إلا لو طُلب صراحة (طويل)
- استخدم ILIKE للبحث النصي بدل =

السؤال: {question}
SQL:"""


def tool_sql(question: str) -> Dict[str, Any]:
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SQL_PROMPT)
        sql = (prompt | llm | StrOutputParser()).invoke({"question": question})
        sql = clean_llm_sql(sql)
        if not is_select_only(sql):
            return {"ok": False, "sql": sql, "error": "SQL غير آمن"}
        df = run_query(sql)
        return {
            "ok": True,
            "sql": sql,
            "rowcount": len(df),
            "data": df.head(20).to_string(index=False),
            "df": df,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# RAG Tool
# ============================================================
def parse_rag_filters(question: str) -> Optional[Dict[str, Any]]:
    """يستخرج فلاتر بسيطة من السؤال (مثلاً risk_level=CRITICAL)."""
    q = question.lower()
    where = {}

    if "حرج" in q or "critical" in q or "أخطر" in q or "اخطر" in q:
        where["risk_level"] = "CRITICAL"
    elif "عالي" in q or "high" in q or "خطير" in q:
        where["risk_level"] = {"$in": ["CRITICAL", "HIGH"]}

    if "شعب" in q or "coral" in q:
        where["distance_to_coral_km"] = {"$lte": 5.0}
    if "يابسة" in q or "سواحل" in q or "ساحل" in q or "land" in q:
        where["distance_to_land_km"] = {"$lte": 5.0}

    return where if where else None


def tool_rag(question: str, k: Optional[int] = None) -> Dict[str, Any]:
    try:
        store = VectorStore()
        if store.count() == 0:
            return {
                "ok": False,
                "error": "الفهرس فارغ. شغّلي: python oil_rag_agent.py --index",
            }

        where = parse_rag_filters(question)
        results = store.query(question, k=k or CFG.TOP_K, where=where)

        if not results:
            # لو الفلتر صارم وما رجّع نتائج، نحاول بدون فلتر
            if where:
                results = store.query(question, k=k or CFG.TOP_K, where=None)

        if not results:
            return {"ok": False, "error": "ما لقيت تقارير ذات صلة"}

        context_parts = []
        for i, r in enumerate(results, 1):
            meta = r["metadata"]
            context_parts.append(
                f"--- تقرير {i} ({meta.get('filename')}) "
                f"[{meta.get('risk_level')} - {meta.get('risk_score')}/100] ---\n"
                f"{r['document']}"
            )

        return {
            "ok": True,
            "context": "\n\n".join(context_parts),
            "filenames": [r["metadata"].get("filename") for r in results],
            "count": len(results),
            "filters_applied": where,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================
# Synthesizer: يدمج النتائج بإجابة عربية
# ============================================================
SYNTH_PROMPT_SQL = """أجب باللغة العربية اعتماداً على نتائج SQL التالية فقط.
لا تخترع أي رقم أو تسرب غير موجود.

السؤال: {question}

استعلام SQL المستخدم:
{sql}

النتائج (عدد الصفوف: {rowcount}):
{data}

أجب بإيجاز وبدقة:"""

SYNTH_PROMPT_RAG = """أجب باللغة العربية اعتماداً على التقارير التالية فقط.
لا تخترع معلومات غير موجودة. لو السؤال يطلب رقماً معيناً وما هو موجود، قولي بصراحة.

السؤال: {question}

التقارير المسترجعة:
{context}

اكتب إجابة منظمة وواضحة. اذكر اسم التسرب (filename) عند الإشارة لأي حالة:"""

SYNTH_PROMPT_HYBRID = """أجب باللغة العربية معتمداً على المصدرين معاً:
1. نتائج SQL (الأرقام والإحصاء)
2. التقارير المسترجعة (الشرح والتفسير)

لا تخترع أي معلومة.

السؤال: {question}

نتائج SQL:
{sql_result}

التقارير المسترجعة:
{rag_context}

اكتب إجابة شاملة تجمع الأرقام مع الشرح. اذكر أسماء التسربات (filename) عند الإشارة لحالات محددة:"""


def synthesize_sql(question: str, sql_result: Dict[str, Any]) -> str:
    if not sql_result.get("ok"):
        return f"تعذّر تنفيذ الاستعلام: {sql_result.get('error')}"
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_SQL)
        return (prompt | llm | StrOutputParser()).invoke({
            "question": question,
            "sql": sql_result.get("sql", ""),
            "rowcount": sql_result.get("rowcount", 0),
            "data": sql_result.get("data", ""),
        })
    except Exception:
        return sql_result.get("data", "")


def synthesize_rag(question: str, rag_result: Dict[str, Any]) -> str:
    if not rag_result.get("ok"):
        return f"تعذّر البحث الدلالي: {rag_result.get('error')}"
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_RAG)
        return (prompt | llm | StrOutputParser()).invoke({
            "question": question,
            "context": rag_result.get("context", ""),
        })
    except Exception:
        return rag_result.get("context", "")


def synthesize_hybrid(question: str, sql_result: Dict[str, Any], rag_result: Dict[str, Any]) -> str:
    sql_text = sql_result.get("data", "لم يُنفذ استعلام SQL.") if sql_result.get("ok") else f"SQL تعذّر: {sql_result.get('error')}"
    rag_text = rag_result.get("context", "لم تُسترجع تقارير.") if rag_result.get("ok") else f"RAG تعذّر: {rag_result.get('error')}"
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_HYBRID)
        return (prompt | llm | StrOutputParser()).invoke({
            "question": question,
            "sql_result": sql_text,
            "rag_context": rag_text,
        })
    except Exception:
        return f"SQL:\n{sql_text}\n\nRAG:\n{rag_text}"


def chat_response(question: str) -> str:
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(
            "أنت مساعد متخصص في تحليل التسربات النفطية البحرية. "
            "أجب باللغة العربية وباختصار.\n\nالسؤال: {question}\n\nالجواب:"
        )
        return (prompt | llm | StrOutputParser()).invoke({"question": question})
    except Exception as e:
        return f"تعذّر الرد: {e}"


# ============================================================
# الواجهة الرئيسية للإيجنت
# ============================================================
def answer_question(question: str, verbose: bool = True) -> str:
    route = route_question(question)
    if verbose:
        print(f"🧭 المسار: {route}")

    if route == "sql":
        sql_res = tool_sql(question)
        if verbose and sql_res.get("ok"):
            print(f"📊 SQL: {sql_res['sql']}")
            print(f"   صفوف: {sql_res['rowcount']}")
        return synthesize_sql(question, sql_res)

    if route == "rag":
        rag_res = tool_rag(question)
        if verbose and rag_res.get("ok"):
            print(f"📚 استُرجع: {rag_res['count']} تقرير")
            print(f"   الملفات: {rag_res['filenames']}")
            if rag_res.get("filters_applied"):
                print(f"   فلاتر: {rag_res['filters_applied']}")
        return synthesize_rag(question, rag_res)

    if route == "hybrid":
        sql_res = tool_sql(question)
        rag_res = tool_rag(question)
        if verbose:
            if sql_res.get("ok"):
                print(f"📊 SQL: {sql_res.get('rowcount')} صفوف")
            if rag_res.get("ok"):
                print(f"📚 RAG: {rag_res.get('count')} تقرير")
        return synthesize_hybrid(question, sql_res, rag_res)

    # chat
    return chat_response(question)


def run_chat():
    print("\n" + "=" * 70)
    print("🛢️ Oil Spill Hybrid Agent (RAG + SQL)")
    print("=" * 70)
    print(f"LLM: {CFG.OLLAMA_LLM_MODEL}")
    print(f"Embeddings: {CFG.OLLAMA_EMBED_MODEL}")

    try:
        store = VectorStore()
        idx_count = store.count()
        print(f"الفهرس: {idx_count} تقرير")
        if idx_count == 0:
            print("⚠️ الفهرس فارغ. شغّلي --index أولاً.")
    except Exception as e:
        print(f"⚠️ تعذّر فتح الفهرس: {e}")

    print("\nاكتبي 'خروج' للإنهاء\n")
    print("أمثلة:")
    print("- كم عدد التسربات الحرجة؟              [SQL]")
    print("- اشرح لي أخطر تسرب وموقعه           [RAG]")
    print("- وش التسربات قرب الشعب وكم عددها     [Hybrid]")
    print("- ما هي العوامل المؤثرة في الخطورة؟    [Chat]")
    print("─" * 70 + "\n")

    while True:
        try:
            q = input("❓ سؤالك: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nمع السلامة")
            break
        if not q:
            continue
        if q.lower() in ["خروج", "exit", "quit", "q"]:
            print("مع السلامة")
            break

        try:
            answer = answer_question(q, verbose=True)
        except Exception as e:
            answer = f"حدث خطأ: {e}"

        print("\n🤖 الجواب:")
        print(answer)
        print("\n" + "─" * 70 + "\n")


# ============================================================
# Main
# ============================================================
def parse_args():
    p = argparse.ArgumentParser(description="Oil Spill Hybrid Agent (RAG + SQL)")
    p.add_argument("--index", action="store_true", help="بناء الفهرس من قاعدة البيانات")
    p.add_argument("--reindex", action="store_true", help="حذف الفهرس وإعادة بنائه")
    p.add_argument("--chat", action="store_true", help="تشغيل الإيجنت التفاعلي")
    p.add_argument("--ask", type=str, default=None, help="سؤال واحد سريع")
    p.add_argument("--top-k", type=int, default=None, help="كم تقرير نسترجع في RAG")
    return p.parse_args()


def main():
    args = parse_args()

    if not OLLAMA_AVAILABLE or not CHROMA_AVAILABLE:
        print("❌ مكتبات ناقصة. نفّذي:")
        print("   pip install langchain-ollama langchain-core chromadb sqlalchemy psycopg2-binary pandas")
        sys.exit(1)

    if args.top_k is not None:
        CFG.TOP_K = args.top_k

    did_something = False

    if args.reindex:
        build_index(reset=True)
        did_something = True
    elif args.index:
        build_index(reset=False)
        did_something = True

    if args.ask:
        answer = answer_question(args.ask, verbose=True)
        print("\n🤖 الجواب:")
        print(answer)
        did_something = True

    if args.chat:
        run_chat()
        did_something = True

    if not did_something:
        # default: تفاعلي
        run_chat()


if __name__ == "__main__":
    main()