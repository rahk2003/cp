"""
🛢️ Oil Spill Hybrid Agent (RAG + SQL + Gradio)
==============================================

Agent محلي يدمج:
- SQL Tool: للأسئلة الرقمية والإحصائية
- RAG Tool: للأسئلة التفسيرية والوصفية
- Hybrid: يدمج SQL + RAG
- Gradio UI: واجهة متصفح محلية

قبل التشغيل:
    pip install langchain-ollama langchain-core chromadb sqlalchemy psycopg2-binary pandas gradio

موديلات Ollama:
    ollama pull qwen3:8b
    ollama pull nomic-embed-text

طريقة التشغيل:
    python oil_rag_agent_gradio.py --index
    python oil_rag_agent_gradio.py --gradio
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text


# ============================================================
# Optional Imports
# ============================================================
try:
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate

    OLLAMA_AVAILABLE = True
    OLLAMA_IMPORT_ERROR = None
except Exception as e:
    ChatOllama = None
    OllamaEmbeddings = None
    StrOutputParser = None
    ChatPromptTemplate = None
    OLLAMA_AVAILABLE = False
    OLLAMA_IMPORT_ERROR = e


try:
    import chromadb
    from chromadb.config import Settings

    CHROMA_AVAILABLE = True
    CHROMA_IMPORT_ERROR = None
except Exception as e:
    chromadb = None
    Settings = None
    CHROMA_AVAILABLE = False
    CHROMA_IMPORT_ERROR = e


try:
    import gradio as gr

    GRADIO_AVAILABLE = True
    GRADIO_IMPORT_ERROR = None
except Exception as e:
    gr = None
    GRADIO_AVAILABLE = False
    GRADIO_IMPORT_ERROR = e


# ============================================================
# Config
# ============================================================
@dataclass
class Config:
    # PostgreSQL
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "oil_spills"

    # Ollama
    OLLAMA_LLM_MODEL: str = "qwen3:8b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TEMPERATURE: float = 0.1
    OLLAMA_NUM_PREDICT: int = 300

    # ChromaDB
    CHROMA_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/chroma_db")
    COLLECTION_NAME: str = "oil_spill_reports"

    # RAG
    TOP_K: int = 3
    MAX_DOC_CHARS: int = 2000
    INDEX_BATCH: int = 32

    @property
    def DB_URI(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


CFG = Config()


# ============================================================
# Safe Helpers
# ============================================================
def is_empty_value(value: Any) -> bool:
    try:
        return value is None or pd.isna(value)
    except Exception:
        return value is None


def safe_str(value: Any, default: str = "") -> str:
    if is_empty_value(value):
        return default
    return str(value)


def safe_float(value: Any, default: float = 0.0) -> float:
    if is_empty_value(value):
        return default
    try:
        value = float(value)
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    if is_empty_value(value):
        return default
    try:
        value = int(float(value))
        return value
    except Exception:
        return default


def get_requested_limit(question: str, default: int = 5, maximum: int = 50) -> int:
    nums = re.findall(r"\d+", question)
    if nums:
        try:
            return min(max(int(nums[0]), 1), maximum)
        except Exception:
            return default
    return default


# ============================================================
# General Tools
# ============================================================
def get_engine():
    return create_engine(CFG.DB_URI)


def run_query(sql: str) -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def clean_llm_sql(text_value: str) -> str:
    """
    ينظف SQL الخارج من الموديل.
    مهم لأن بعض الموديلات مثل Qwen قد ترجع شرح أو <think> قبل SELECT.
    """
    if text_value is None:
        return ""

    text_value = str(text_value)

    # Remove Qwen thinking tags
    text_value = re.sub(
        r"<think>.*?</think>",
        "",
        text_value,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # Remove markdown sql blocks
    text_value = re.sub(r"```sql\s*", "", text_value, flags=re.IGNORECASE)
    text_value = re.sub(r"```\s*", "", text_value)

    # Extract first SELECT statement only
    match = re.search(r"(select\b.*)", text_value, flags=re.IGNORECASE | re.DOTALL)
    if match:
        text_value = match.group(1)

    # Stop at first semicolon
    if ";" in text_value:
        text_value = text_value.split(";")[0]

    return text_value.strip("` \n;") + ";"


def is_select_only(sql: str) -> bool:
    s = sql.strip().lower()

    forbidden = [
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "truncate",
        "grant",
        "revoke",
        "copy",
        "execute",
    ]

    return s.startswith("select") and not any(
        re.search(rf"\b{x}\b", s) for x in forbidden
    )


def get_llm():
    if not OLLAMA_AVAILABLE:
        raise ImportError(f"langchain_ollama غير مثبت: {OLLAMA_IMPORT_ERROR}")

    return ChatOllama(
        model=CFG.OLLAMA_LLM_MODEL,
        temperature=CFG.OLLAMA_TEMPERATURE,
        num_predict=CFG.OLLAMA_NUM_PREDICT,
    )


def get_embeddings():
    if not OLLAMA_AVAILABLE:
        raise ImportError(f"langchain_ollama غير مثبت: {OLLAMA_IMPORT_ERROR}")

    return OllamaEmbeddings(model=CFG.OLLAMA_EMBED_MODEL)


def strip_html(html) -> str:
    """
    يشيل HTML tags ويتعامل مع None و NaN.
    هذا يمنع خطأ: expected string or bytes-like object, got float
    """
    if is_empty_value(html):
        return ""

    html = str(html)

    if not html.strip():
        return ""

    text_only = re.sub(r"<[^>]+>", " ", html)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    return text_only


# ============================================================
# Vector Store
# ============================================================
class VectorStore:
    def __init__(self):
        if not CHROMA_AVAILABLE:
            raise ImportError(f"chromadb غير مثبت: {CHROMA_IMPORT_ERROR}")

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

    def add_batch(
        self,
        ids: List[str],
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ):
        if not texts:
            return

        vectors = self.embeddings.embed_documents(texts)
        clean_meta = [_sanitize_metadata(m) for m in metadatas]

        self.collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=clean_meta,
        )

    def query(
        self,
        query_text: str,
        k: int = 3,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        q_vec = self.embeddings.embed_query(query_text)

        kwargs = {
            "query_embeddings": [q_vec],
            "n_results": k,
        }

        if where:
            kwargs["where"] = where

        res = self.collection.query(**kwargs)

        results = []

        if not res.get("ids") or not res["ids"][0]:
            return results

        for i in range(len(res["ids"][0])):
            results.append(
                {
                    "id": res["ids"][0][i],
                    "document": res["documents"][0][i],
                    "metadata": res["metadatas"][0][i],
                    "distance": res["distances"][0][i]
                    if res.get("distances")
                    else None,
                }
            )

        return results


def _sanitize_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    ChromaDB metadata يقبل فقط:
    str, int, float, bool
    ولا يقبل None أو NaN.
    """
    clean = {}

    for k, v in meta.items():
        if is_empty_value(v):
            if k in [
                "risk_score",
                "area_m2",
                "coverage_pct",
                "num_components",
                "distance_to_land_km",
                "distance_to_coral_km",
                "spill_centroid_lon",
                "spill_centroid_lat",
            ]:
                clean[k] = 0.0
            else:
                clean[k] = ""
        elif isinstance(v, bool):
            clean[k] = v
        elif isinstance(v, int):
            clean[k] = v
        elif isinstance(v, float):
            if pd.isna(v):
                clean[k] = 0.0
            else:
                clean[k] = v
        elif isinstance(v, str):
            clean[k] = v
        else:
            clean[k] = str(v)

    return clean


# ============================================================
# Build Index
# ============================================================
def build_document(row: Dict[str, Any]) -> str:
    parts = []

    parts.append(f"التسرب: {safe_str(row.get('filename'))}")
    parts.append(f"الصورة الأصلية: {safe_str(row.get('source_image'))}")

    lat = safe_float(row.get("spill_centroid_lat"), None)
    lon = safe_float(row.get("spill_centroid_lon"), None)

    if lat is not None and lon is not None:
        parts.append(f"موقع التسرب: lat={lat}, lon={lon}")

    date = safe_str(row.get("date"))
    time_value = safe_str(row.get("time"))
    if date:
        parts.append(f"التاريخ: {date} {time_value}".strip())

    crs = safe_str(row.get("crs"))
    if crs:
        parts.append(f"نظام الإحداثيات: {crs}")

    parts.append(
        f"المساحة: {safe_float(row.get('area_m2'))} م² "
        f"({safe_int(row.get('area_px'))} بكسل)"
    )
    parts.append(f"نسبة التغطية: {safe_float(row.get('coverage_pct'))}%")
    parts.append(f"عدد البقع: {safe_int(row.get('num_components'))}")
    parts.append(f"نسبة الامتداد: {safe_float(row.get('spread_ratio'))}")

    parts.append(
        f"المسافة إلى اليابسة: {safe_float(row.get('distance_to_land_km'))} كم "
        f"({safe_str(row.get('land_proximity_class'))})"
    )

    parts.append(
        f"المسافة إلى الشعب المرجانية: {safe_float(row.get('distance_to_coral_km'))} كم "
        f"({safe_str(row.get('coral_proximity_class'))})"
    )

    parts.append(
        f"تقييم الخطورة: {safe_str(row.get('risk_level'), 'NONE')} "
        f"({safe_float(row.get('risk_score'))}/100)"
    )

    risk_factors = safe_str(row.get("risk_factors"))
    if risk_factors:
        parts.append(f"عوامل الخطورة: {risk_factors}")

    llm_report = strip_html(row.get("llm_report_html"))
    if llm_report:
        if len(llm_report) > CFG.MAX_DOC_CHARS:
            llm_report = llm_report[: CFG.MAX_DOC_CHARS] + "..."

        parts.append("\nالتقرير التفصيلي:")
        parts.append(llm_report)

    return "\n".join(parts)


def build_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
    llm_report = strip_html(row.get("llm_report_html"))

    return {
        "filename": safe_str(row.get("filename")),
        "risk_level": safe_str(row.get("risk_level"), "NONE"),
        "risk_score": safe_float(row.get("risk_score")),
        "area_m2": safe_float(row.get("area_m2")),
        "coverage_pct": safe_float(row.get("coverage_pct")),
        "num_components": safe_int(row.get("num_components")),
        "distance_to_land_km": safe_float(row.get("distance_to_land_km")),
        "distance_to_coral_km": safe_float(row.get("distance_to_coral_km")),
        "land_proximity_class": safe_str(row.get("land_proximity_class")),
        "coral_proximity_class": safe_str(row.get("coral_proximity_class")),
        "spill_centroid_lon": safe_float(row.get("spill_centroid_lon")),
        "spill_centroid_lat": safe_float(row.get("spill_centroid_lat")),
        "date": safe_str(row.get("date")),
        "has_llm_report": bool(llm_report),
    }


def build_index(reset: bool = False) -> int:
    print("=" * 70)
    print("بناء فهرس RAG من قاعدة البيانات")
    print("=" * 70)

    store = VectorStore()

    if reset:
        print("🗑️ حذف الفهرس القديم...")
        store.reset()

    existing = store.count()
    print(f"عدد المستندات الحالية في الفهرس: {existing}")

    sql = """
    SELECT *
    FROM spill_analysis_results
    WHERE area_px > 0
    ORDER BY filename;
    """

    try:
        df = run_query(sql)
    except Exception as e:
        print(f"❌ خطأ في قراءة قاعدة البيانات: {e}")
        return 0

    if df.empty:
        print("⚠️ ما لقيت تسربات في الجدول area_px > 0")
        return 0

    print(f"عدد التسربات للفهرسة: {len(df)}")

    existing_ids = set()

    if not reset:
        try:
            res = store.collection.get()
            existing_ids = set(res.get("ids", []))
        except Exception:
            pass

    rows = df.to_dict("records")

    to_index = [
        r
        for r in rows
        if safe_str(r.get("filename")) and safe_str(r.get("filename")) not in existing_ids
    ]

    print(
        f"الجديد للفهرسة: {len(to_index)} "
        f"(موجود مسبقاً: {len(rows) - len(to_index)})"
    )

    if not to_index:
        print("✅ الفهرس محدّث، ما فيه شيء جديد للإضافة")
        return store.count()

    indexed = 0

    for i in range(0, len(to_index), CFG.INDEX_BATCH):
        batch = to_index[i : i + CFG.INDEX_BATCH]

        ids = [safe_str(r.get("filename")) for r in batch]
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
# Router
# ============================================================
ROUTER_PROMPT = """
صنّف سؤال المستخدم إلى واحد فقط:

sql:
للأسئلة الرقمية أو القوائم أو العد أو أكبر/أصغر/متوسط.

rag:
للشرح أو التفسير أو قراءة التقارير.

hybrid:
إذا السؤال يحتاج أرقام من SQL وشرح من RAG.

chat:
محادثة عامة.

أرجع كلمة واحدة فقط:
sql, rag, hybrid, chat

السؤال:
{question}

التصنيف:
"""


def route_question(question: str) -> str:
    q = question.lower().strip()

    if not q:
        return "chat"

    if any(w in q for w in ["مرحبا", "اهلا", "السلام", "hi", "hello"]) and len(q) < 20:
        return "chat"

    sql_signals = [
        "كم",
        "عدد",
        "احسب",
        "count",
        "average",
        "متوسط",
        "أكبر",
        "اكبر",
        "أصغر",
        "اصغر",
        "أعلى",
        "اعلى",
        "أدنى",
        "ادنى",
        "قائمة",
        "وش التسربات",
        "ما التسربات",
    ]

    rag_signals = [
        "اشرح",
        "وضح",
        "فسر",
        "تقرير",
        "تحليل",
        "ليش",
        "لماذا",
        "كيف",
        "explain",
        "describe",
        "report",
        "تفصيل",
        "أثر",
        "اثر",
        "توصية",
    ]

    has_sql = any(w in q for w in sql_signals)
    has_rag = any(w in q for w in rag_signals)

    if has_sql and has_rag:
        return "hybrid"

    if has_sql:
        return "sql"

    if has_rag:
        return "rag"

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(ROUTER_PROMPT)
        out = (prompt | llm | StrOutputParser()).invoke({"question": question})
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL | re.IGNORECASE)
        out = out.strip().lower()
        m = re.search(r"(sql|rag|hybrid|chat)", out)
        return m.group(1) if m else "rag"
    except Exception:
        return "rag"


# ============================================================
# SQL Tool
# ============================================================
SQL_PROMPT = """
أنت خبير PostgreSQL.
حوّل سؤال المستخدم إلى SQL للقراءة فقط.

الجداول:

spill_info(
    file, source_path, date, time, crs, width, height,
    pixel_size_x, pixel_size_y,
    bbox_left, bbox_bottom, bbox_right, bbox_top,
    center_lon, center_lat,
    upper_left_lon, upper_left_lat,
    upper_right_lon, upper_right_lat,
    lower_right_lon, lower_right_lat,
    lower_left_lon, lower_left_lat
)

spill_analysis_results(
    filename, source_image, area_px, area_m2, coverage_pct,
    centroid_x, centroid_y,
    spill_centroid_lon, spill_centroid_lat,
    perimeter_m, spread_ratio, num_components, compactness,
    mean_intensity, max_intensity, std_intensity, density_score,
    distance_to_land_km, land_proximity_class,
    distance_to_coral_km, coral_proximity_class,
    risk_score, risk_level, risk_factors,
    crs, center_lon, center_lat, date, time,
    llm_report_html
)

قواعد صارمة:
- أرجع SQL فقط.
- لا تكتب شرح.
- لا تستخدم Markdown.
- SELECT فقط.
- لا تستخدم INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE.
- استخدم LIMIT 50 إذا السؤال قائمة.
- لا تختار llm_report_html إلا لو طُلب نص التقرير صراحة.
- استخدم ILIKE للبحث النصي.

السؤال:
{question}

SQL:
"""


def direct_sql_fallback(question: str) -> Optional[str]:
    """
    SQL جاهز للأسئلة المتكررة.
    هذا يحل مشكلة SQL غير آمن، لأننا لا نحتاج الموديل للأسئلة البسيطة.
    """
    q = question.lower().strip()
    limit = get_requested_limit(question, default=5, maximum=50)

    # عدد التسربات الحرجة
    if ("كم" in q or "عدد" in q or "count" in q) and (
        "حرج" in q or "critical" in q
    ):
        return """
        SELECT COUNT(*) AS critical_spills_count
        FROM spill_analysis_results
        WHERE risk_level ILIKE 'CRITICAL';
        """

    # عدد التسربات العالية أو الحرجة
    if ("كم" in q or "عدد" in q or "count" in q) and (
        "عالي" in q or "high" in q
    ):
        return """
        SELECT COUNT(*) AS high_or_critical_spills_count
        FROM spill_analysis_results
        WHERE risk_level ILIKE 'HIGH'
           OR risk_level ILIKE 'CRITICAL';
        """

    # عدد كل التسربات
    if ("كم" in q or "عدد" in q or "count" in q) and (
        "التسربات" in q or "تسرب" in q
    ):
        return """
        SELECT COUNT(*) AS total_spills_count
        FROM spill_analysis_results
        WHERE area_px > 0;
        """

    # أخطر التسربات
    if "أخطر" in q or "اخطر" in q or "أعلى خطورة" in q or "اعلى خطورة" in q:
        return f"""
        SELECT
            filename,
            risk_level,
            risk_score,
            area_m2,
            coverage_pct,
            distance_to_land_km,
            distance_to_coral_km,
            spill_centroid_lat,
            spill_centroid_lon,
            date,
            time
        FROM spill_analysis_results
        WHERE area_px > 0
        ORDER BY risk_score DESC NULLS LAST
        LIMIT {limit};
        """

    # أكبر التسربات حسب المساحة
    if "أكبر" in q or "اكبر" in q or "المساحة" in q:
        return f"""
        SELECT
            filename,
            risk_level,
            risk_score,
            area_m2,
            coverage_pct,
            distance_to_land_km,
            distance_to_coral_km,
            date,
            time
        FROM spill_analysis_results
        WHERE area_px > 0
        ORDER BY area_m2 DESC NULLS LAST
        LIMIT {limit};
        """

    # التسربات القريبة من الشعب المرجانية
    if ("شعب" in q or "coral" in q) and (
        "قريب" in q or "القريبة" in q or "تهدد" in q or "وش" in q or "ما" in q
    ):
        return f"""
        SELECT
            filename,
            risk_level,
            risk_score,
            distance_to_coral_km,
            area_m2,
            coverage_pct,
            date,
            time
        FROM spill_analysis_results
        WHERE area_px > 0
        ORDER BY distance_to_coral_km ASC NULLS LAST
        LIMIT {max(limit, 10)};
        """

    # التسربات القريبة من اليابسة أو الساحل
    if ("يابسة" in q or "ساحل" in q or "سواحل" in q or "land" in q) and (
        "قريب" in q or "القريبة" in q or "تهدد" in q or "وش" in q or "ما" in q
    ):
        return f"""
        SELECT
            filename,
            risk_level,
            risk_score,
            distance_to_land_km,
            area_m2,
            coverage_pct,
            date,
            time
        FROM spill_analysis_results
        WHERE area_px > 0
        ORDER BY distance_to_land_km ASC NULLS LAST
        LIMIT {max(limit, 10)};
        """

    # توزيع مستويات الخطورة
    if "مستويات الخطورة" in q or "توزيع الخطورة" in q or "risk levels" in q:
        return """
        SELECT
            risk_level,
            COUNT(*) AS spill_count
        FROM spill_analysis_results
        WHERE area_px > 0
        GROUP BY risk_level
        ORDER BY spill_count DESC;
        """

    # متوسط المسافة من اليابسة
    if "متوسط" in q and ("يابسة" in q or "ساحل" in q or "land" in q):
        return """
        SELECT
            AVG(distance_to_land_km) AS avg_distance_to_land_km,
            MIN(distance_to_land_km) AS min_distance_to_land_km,
            MAX(distance_to_land_km) AS max_distance_to_land_km
        FROM spill_analysis_results
        WHERE area_px > 0;
        """

    # متوسط المسافة من الشعب المرجانية
    if "متوسط" in q and ("شعب" in q or "coral" in q):
        return """
        SELECT
            AVG(distance_to_coral_km) AS avg_distance_to_coral_km,
            MIN(distance_to_coral_km) AS min_distance_to_coral_km,
            MAX(distance_to_coral_km) AS max_distance_to_coral_km
        FROM spill_analysis_results
        WHERE area_px > 0;
        """

    return None


def tool_sql(question: str) -> Dict[str, Any]:
    try:
        sql = direct_sql_fallback(question)

        if sql is None:
            llm = get_llm()
            prompt = ChatPromptTemplate.from_template(SQL_PROMPT)
            raw_sql = (prompt | llm | StrOutputParser()).invoke({"question": question})
            sql = clean_llm_sql(raw_sql)
        else:
            sql = clean_llm_sql(sql)

        if not is_select_only(sql):
            return {
                "ok": False,
                "sql": sql,
                "error": f"SQL غير آمن أو غير واضح. الاستعلام الناتج كان:\n{sql}",
            }

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
    q = question.lower()
    conditions = []

    if "حرج" in q or "critical" in q or "أخطر" in q or "اخطر" in q:
        conditions.append({"risk_level": "CRITICAL"})
    elif "عالي" in q or "high" in q or "خطير" in q:
        conditions.append({"risk_level": {"$in": ["CRITICAL", "HIGH"]}})

    if "شعب" in q or "coral" in q:
        conditions.append({"distance_to_coral_km": {"$lte": 5.0}})

    if "يابسة" in q or "سواحل" in q or "ساحل" in q or "land" in q:
        conditions.append({"distance_to_land_km": {"$lte": 5.0}})

    if not conditions:
        return None

    if len(conditions) == 1:
        return conditions[0]

    return {"$and": conditions}


def tool_rag(question: str, k: Optional[int] = None) -> Dict[str, Any]:
    try:
        store = VectorStore()

        if store.count() == 0:
            return {
                "ok": False,
                "error": "الفهرس فارغ. شغّلي أولاً: python oil_rag_agent_gradio.py --index",
            }

        where = parse_rag_filters(question)

        try:
            results = store.query(question, k=k or CFG.TOP_K, where=where)
        except Exception:
            results = store.query(question, k=k or CFG.TOP_K, where=None)

        if not results and where:
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
# Prompts
# ============================================================
SYNTH_PROMPT_SQL = """
أجب باللغة العربية اعتماداً على نتائج SQL فقط.

قواعد:
- لا تخترع أرقام.
- لا تضيف معلومات غير موجودة.
- إذا كانت النتيجة رقم واحد، اذكره مباشرة.
- إذا كانت النتيجة جدول، لخّص أهم الصفوف.
- اذكر filename إذا كان موجوداً.

السؤال:
{question}

استعلام SQL:
{sql}

النتائج:
{data}

الإجابة:
"""


SYNTH_PROMPT_RAG = """
أنت محلل ذكي متخصص في تحليل تسربات النفط البحرية.

مهمتك:
- أجب باللغة العربية الواضحة.
- اعتمد فقط على التقارير المسترجعة.
- لا تخترع أرقام أو مواقع أو أسماء غير موجودة.
- إذا كانت المعلومة غير موجودة، قل: "غير مذكور في البيانات".
- اذكر اسم الملف filename عند الحديث عن أي تسرب.
- اجعل الإجابة مرتبة وليست عامة.

السؤال:
{question}

التقارير المسترجعة:
{context}

اكتب الإجابة بهذا الشكل:

1. الخلاصة:
2. الحالات المرتبطة بالسؤال:
3. التفسير:
4. ملاحظات:
"""


SYNTH_PROMPT_HYBRID = """
أنت محلل ذكي متخصص في مخاطر التسربات النفطية البحرية.

اعتمد على مصدرين:
1. نتائج SQL للأرقام والجداول.
2. تقارير RAG للتفسير والوصف.

قواعد:
- لا تخترع أي معلومة.
- لا تذكر رقمًا غير موجود.
- اكتب بلغة عربية واضحة.
- اذكر filename عند الإشارة لأي تسرب.

السؤال:
{question}

نتائج SQL:
{sql_result}

التقارير المسترجعة:
{rag_context}

اكتب الإجابة بهذا الشكل:

1. الإجابة المختصرة:
2. النتائج الرقمية:
3. الحالات المهمة:
4. التحليل:
5. توصية:
"""


def synthesize_sql(question: str, sql_result: Dict[str, Any]) -> str:
    if not sql_result.get("ok"):
        return f"تعذّر تنفيذ الاستعلام:\n{sql_result.get('error')}"

    df = sql_result.get("df")

    # جواب سريع بدون LLM لو النتيجة رقم واحد
    if isinstance(df, pd.DataFrame) and df.shape == (1, 1):
        col = df.columns[0]
        val = df.iloc[0, 0]

        if "critical" in col.lower() or "حرج" in question:
            return f"عدد التسربات الحرجة هو: {val}"

        if "total" in col.lower() or "عدد" in question or "كم" in question:
            return f"العدد هو: {val}"

        return f"{col}: {val}"

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_SQL)

        return (prompt | llm | StrOutputParser()).invoke(
            {
                "question": question,
                "sql": sql_result.get("sql", ""),
                "data": sql_result.get("data", ""),
            }
        )

    except Exception:
        return sql_result.get("data", "")


def synthesize_rag(question: str, rag_result: Dict[str, Any]) -> str:
    if not rag_result.get("ok"):
        return f"تعذّر البحث الدلالي:\n{rag_result.get('error')}"

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_RAG)

        return (prompt | llm | StrOutputParser()).invoke(
            {
                "question": question,
                "context": rag_result.get("context", ""),
            }
        )

    except Exception:
        return rag_result.get("context", "")


def synthesize_hybrid(
    question: str,
    sql_result: Dict[str, Any],
    rag_result: Dict[str, Any],
) -> str:
    sql_text = (
        sql_result.get("data", "لم تُنفذ SQL.")
        if sql_result.get("ok")
        else f"SQL تعذّر: {sql_result.get('error')}"
    )

    rag_text = (
        rag_result.get("context", "لم تُسترجع تقارير.")
        if rag_result.get("ok")
        else f"RAG تعذّر: {rag_result.get('error')}"
    )

    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(SYNTH_PROMPT_HYBRID)

        return (prompt | llm | StrOutputParser()).invoke(
            {
                "question": question,
                "sql_result": sql_text,
                "rag_context": rag_text,
            }
        )

    except Exception:
        return f"SQL:\n{sql_text}\n\nRAG:\n{rag_text}"


def chat_response(question: str) -> str:
    try:
        llm = get_llm()
        prompt = ChatPromptTemplate.from_template(
            """
            أنت مساعد متخصص في تحليل التسربات النفطية البحرية.
            أجب بالعربية وباختصار.

            السؤال:
            {question}

            الجواب:
            """
        )

        return (prompt | llm | StrOutputParser()).invoke({"question": question})

    except Exception as e:
        return f"تعذّر الرد: {e}"


# ============================================================
# Main Agent Answer
# ============================================================
def answer_question(question: str, verbose: bool = True) -> str:
    route = route_question(question)

    if verbose:
        print(f"🧭 المسار: {route}")

    if route == "sql":
        sql_res = tool_sql(question)

        if verbose and sql_res.get("ok"):
            print(f"📊 SQL: {sql_res['sql']}")
            print(f"صفوف: {sql_res['rowcount']}")

        return synthesize_sql(question, sql_res)

    if route == "rag":
        rag_res = tool_rag(question)

        if verbose and rag_res.get("ok"):
            print(f"📚 استُرجع: {rag_res['count']} تقرير")
            print(f"الملفات: {rag_res['filenames']}")

        return synthesize_rag(question, rag_res)

    if route == "hybrid":
        sql_res = tool_sql(question)
        rag_res = tool_rag(question)

        if verbose:
            if sql_res.get("ok"):
                print(f"📊 SQL rows: {sql_res.get('rowcount')}")
            if rag_res.get("ok"):
                print(f"📚 RAG docs: {rag_res.get('count')}")

        return synthesize_hybrid(question, sql_res, rag_res)

    return chat_response(question)


# ============================================================
# Terminal Chat
# ============================================================
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
    print("- كم عدد التسربات الحرجة؟")
    print("- اشرح لي أخطر تسرب وموقعه")
    print("- وش التسربات القريبة من الشعب المرجانية؟")
    print("- اعطني تقرير شامل عن أخطر 3 تسربات")
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
# Gradio UI
# ============================================================
def get_index_status() -> str:
    try:
        store = VectorStore()
        idx_count = store.count()

        if idx_count == 0:
            return "⚠️ الفهرس فارغ. شغّلي أولاً: python oil_rag_agent_gradio.py --index"

        return f"✅ الفهرس جاهز: {idx_count} تقرير موجود في ChromaDB"

    except Exception as e:
        return f"⚠️ تعذّر قراءة الفهرس: {e}"


def gradio_answer(question: str, top_k: int = 3) -> str:
    question = (question or "").strip()

    if not question:
        return "اكتبي سؤال أولاً."

    try:
        CFG.TOP_K = int(top_k)
        answer = answer_question(question, verbose=False)
        return answer

    except Exception as e:
        return f"حدث خطأ أثناء تشغيل الإيجنت:\n{e}"


def run_gradio():
    if not GRADIO_AVAILABLE:
        print("❌ مكتبة gradio غير مثبتة.")
        print("نفّذي:")
        print("   pip install gradio")
        if GRADIO_IMPORT_ERROR:
            print(f"سبب الخطأ: {GRADIO_IMPORT_ERROR}")
        return

    with gr.Blocks(title="Oil Spill Hybrid Agent") as demo:
        gr.Markdown(
            """
            # 🛢️ Oil Spill Hybrid Agent

            واجهة محلية تسألين فيها الإيجنت عن نتائج تسربات النفط.

            - الأسئلة الرقمية تستخدم SQL.
            - الأسئلة التفسيرية تستخدم RAG.
            - الأسئلة المركبة تدمج SQL + RAG.
            """
        )

        status_box = gr.Markdown(value=get_index_status())

        with gr.Row():
            question_box = gr.Textbox(
                label="اكتبي سؤالك",
                placeholder="مثال: كم عدد التسربات الحرجة؟",
                lines=3,
                scale=4,
            )

            top_k_slider = gr.Slider(
                minimum=1,
                maximum=10,
                value=CFG.TOP_K,
                step=1,
                label="عدد التقارير المسترجعة RAG",
            )

        with gr.Row():
            ask_btn = gr.Button("اسألي الإيجنت", variant="primary")
            clear_btn = gr.Button("مسح")
            refresh_btn = gr.Button("تحديث حالة الفهرس")

        answer_box = gr.Textbox(
            label="جواب الإيجنت",
            lines=16,
        )

        gr.Examples(
            examples=[
                "كم عدد التسربات الحرجة؟",
                "اشرح لي أخطر تسرب وموقعه",
                "وش التسربات القريبة من الشعب المرجانية؟",
                "اعطني تقرير شامل عن أخطر 3 تسربات",
                "ما هي العوامل المؤثرة في الخطورة؟",
            ],
            inputs=question_box,
        )

        ask_btn.click(
            fn=gradio_answer,
            inputs=[question_box, top_k_slider],
            outputs=answer_box,
        )

        question_box.submit(
            fn=gradio_answer,
            inputs=[question_box, top_k_slider],
            outputs=answer_box,
        )

        clear_btn.click(
            fn=lambda: ("", ""),
            inputs=None,
            outputs=[question_box, answer_box],
        )

        refresh_btn.click(
            fn=get_index_status,
            inputs=None,
            outputs=status_box,
        )

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
    )


# ============================================================
# CLI
# ============================================================
def parse_args():
    p = argparse.ArgumentParser(description="Oil Spill Hybrid Agent (RAG + SQL + Gradio)")

    p.add_argument("--index", action="store_true", help="بناء الفهرس من قاعدة البيانات")
    p.add_argument("--reindex", action="store_true", help="حذف الفهرس وإعادة بنائه")
    p.add_argument("--chat", action="store_true", help="تشغيل الإيجنت داخل التيرمنال")
    p.add_argument("--gradio", action="store_true", help="تشغيل واجهة Gradio في المتصفح")
    p.add_argument("--ask", type=str, default=None, help="سؤال واحد سريع")
    p.add_argument("--top-k", type=int, default=None, help="عدد التقارير المسترجعة في RAG")

    return p.parse_args()


def main():
    args = parse_args()

    if not OLLAMA_AVAILABLE:
        print("❌ مكتبة langchain_ollama ناقصة.")
        print("نفّذي:")
        print("   pip install langchain-ollama langchain-core")
        print(f"الخطأ: {OLLAMA_IMPORT_ERROR}")
        sys.exit(1)

    if not CHROMA_AVAILABLE:
        print("❌ مكتبة chromadb ناقصة.")
        print("نفّذي:")
        print("   pip install chromadb")
        print(f"الخطأ: {CHROMA_IMPORT_ERROR}")
        sys.exit(1)

    if args.top_k is not None:
        CFG.TOP_K = int(args.top_k)

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

    if args.gradio:
        run_gradio()
        did_something = True

    if not did_something:
        run_chat()


if __name__ == "__main__":
    main()