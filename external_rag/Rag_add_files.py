"""
=============================================================
RAG: Add LLM reports from CSV to existing index
=============================================================
يستخرج عمود llm_report_html من ملف CSV ويضيفه لقاعدة الـ ChromaDB.

كل تقرير يصير له metadata غني:
- filename, date, time
- risk_level, risk_score
- coordinates (lat, lon)
- distance_to_land, distance_to_coral
- area_m2, coverage_pct

كذا لما المستخدم يسأل، الـ RAG يقدر يرجع التقرير + كل البيانات المرتبطة.

كيفية الاستخدام:
    python rag_add_csv_reports.py
"""

from pathlib import Path
import pandas as pd
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import hashlib

# =========================
# الإعدادات
# =========================
CSV_PATH = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_documents\spill_analysis_results_full_with_llm.csv")
DB_DIR   = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_db")
COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# عمود التقرير في الـ CSV
REPORT_COLUMN = "llm_report_html"

# تقسيم النص
CHUNK_SIZE    = 600   # أكبر شوي لأن التقارير منظمة
CHUNK_OVERLAP = 100

# اسم المصدر (ظاهر في النتائج)
SOURCE_PREFIX = "spill_report"


# =========================
# دالة تنظيف HTML
# =========================
def clean_html(text: str) -> str:
    """يزيل tags HTML البسيطة ويبقي النص قابل للقراءة."""
    if not isinstance(text, str):
        return ""

    # استبدال headings بـ markdown
    text = re.sub(r'<h\d>', '\n## ', text)
    text = re.sub(r'</h\d>', '\n', text)

    # استبدال <ul> و <li>
    text = re.sub(r'<ul>', '', text)
    text = re.sub(r'</ul>', '\n', text)
    text = re.sub(r'<li>', '- ', text)
    text = re.sub(r'</li>', '\n', text)

    # حذف بقية الـ tags
    text = re.sub(r'<[^>]+>', '', text)

    # تنظيف الأسطر المتعددة
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[\t ]+', ' ', text)

    return text.strip()


# =========================
# دالة بناء metadata
# =========================
def build_metadata(row: pd.Series, chunk_idx: int) -> dict:
    """يبني metadata لكل chunk من بيانات الصف."""
    def safe_get(col, default=""):
        val = row.get(col, default)
        if pd.isna(val):
            return default
        return val

    def safe_float(col, default=0.0):
        try:
            val = row.get(col, default)
            return float(val) if not pd.isna(val) else default
        except (ValueError, TypeError):
            return default

    return {
        "source":             f"{SOURCE_PREFIX}_{safe_get('filename', 'unknown')}",
        "type":               "spill_report",
        "filename":           str(safe_get("filename")),
        "date":               str(safe_get("date")),
        "time":               str(safe_get("time")),
        "risk_level":         str(safe_get("risk_level")),
        "risk_score":         safe_float("risk_score"),
        "area_m2":            safe_float("area_m2"),
        "coverage_pct":       safe_float("coverage_pct"),
        "centroid_lon":       safe_float("spill_centroid_lon"),
        "centroid_lat":       safe_float("spill_centroid_lat"),
        "distance_to_land_km":   safe_float("distance_to_land_km"),
        "distance_to_coral_km":  safe_float("distance_to_coral_km"),
        "land_proximity":     str(safe_get("land_proximity_class")),
        "coral_proximity":    str(safe_get("coral_proximity_class")),
        "num_components":     int(safe_float("num_components", 0)),
        "page":               1,    # توافق مع نفس البنية
        "chunk":              chunk_idx,
    }


def make_id(filename: str, chunk_idx: int, text: str) -> str:
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    safe_name = filename.replace(".", "_")
    return f"spill_{safe_name}_c{chunk_idx}_{h}"


# =========================
# المعالجة الرئيسية
# =========================
def add_csv_reports():
    print("=" * 60)
    print("Adding LLM reports from CSV to RAG index")
    print("=" * 60)

    # 1. التحقق من الملف
    if not CSV_PATH.exists():
        print(f"❌ الملف غير موجود: {CSV_PATH}")
        return

    # 2. الاتصال بقاعدة البيانات
    print(f"\n[1/5] Connecting to ChromaDB at: {DB_DIR}")
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        collection = client.get_collection(COLLECTION)
        existing_count = collection.count()
        print(f"      Found '{COLLECTION}' with {existing_count} existing chunks.")
    except Exception:
        print(f"❌ ما لقيت collection '{COLLECTION}'.")
        print(f"   شغّلي rag_build_index.py أولاً.")
        return

    # 3. قراءة الـ CSV
    print(f"\n[2/5] Reading CSV: {CSV_PATH.name}")
    df = pd.read_csv(CSV_PATH)
    print(f"      Total rows: {len(df)}")
    print(f"      Columns: {len(df.columns)}")

    if REPORT_COLUMN not in df.columns:
        print(f"❌ العمود '{REPORT_COLUMN}' غير موجود في الـ CSV.")
        print(f"   الأعمدة المتاحة: {list(df.columns)[:5]}...")
        return

    # تصفية الصفوف اللي فيها تقرير فعلي
    df_valid = df[df[REPORT_COLUMN].notna()].copy()
    df_valid = df_valid[df_valid[REPORT_COLUMN].str.strip() != ""]
    print(f"      Rows with reports: {len(df_valid)}")

    if len(df_valid) == 0:
        print("❌ ما فيه تقارير LLM في الملف.")
        return

    # 4. اكتشاف الـ reports المضافة سابقاً
    print(f"\n[3/5] Checking for already-indexed reports...")
    all_existing = collection.get(include=["metadatas"])
    indexed_filenames = set()
    for meta in all_existing["metadatas"]:
        if meta.get("type") == "spill_report":
            indexed_filenames.add(meta.get("filename"))

    print(f"      Already indexed reports: {len(indexed_filenames)}")

    # تصفية اللي مو موجودين
    df_new = df_valid[~df_valid["filename"].isin(indexed_filenames)]
    print(f"      🆕 New reports to add: {len(df_new)}")

    if len(df_new) == 0:
        print("\n✅ كل التقارير موجودة في القاعدة. ما فيه جديد.")
        return

    # 5. تحميل embedding model
    print(f"\n[4/5] Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL)

    # 6. معالجة التقارير وإضافتها
    print(f"\n[5/5] Processing and indexing reports...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n\n", "\n", ". ", " ", ""],
    )

    all_texts     = []
    all_metas     = []
    all_ids       = []

    for idx, row in df_new.iterrows():
        raw_html = row[REPORT_COLUMN]
        clean    = clean_html(raw_html)

        if not clean or len(clean) < 50:
            continue

        # تقسيم
        chunks = splitter.split_text(clean)

        for chunk_idx, chunk_text in enumerate(chunks):
            meta = build_metadata(row, chunk_idx)
            all_texts.append(chunk_text)
            all_metas.append(meta)
            all_ids.append(make_id(row.get("filename", f"row{idx}"), chunk_idx, chunk_text))

    print(f"      Total chunks generated: {len(all_texts)}")

    if not all_texts:
        print("❌ ما تم استخراج نصوص.")
        return

    # حساب embeddings وإضافة
    BATCH = 64
    for i in range(0, len(all_texts), BATCH):
        batch_texts = all_texts[i:i + BATCH]
        batch_embs  = embedder.encode(
            batch_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()

        collection.add(
            ids=all_ids[i:i + BATCH],
            embeddings=batch_embs,
            documents=batch_texts,
            metadatas=all_metas[i:i + BATCH],
        )
        print(f"      Indexed {min(i + BATCH, len(all_texts))}/{len(all_texts)}")

    final_count = collection.count()

    print("\n" + "=" * 60)
    print(f"✅ Done.")
    print(f"   Reports added : {len(df_new)}")
    print(f"   Chunks added  : {len(all_texts)}")
    print(f"   Total chunks  : {existing_count} → {final_count}")
    print("=" * 60)


if __name__ == "__main__":
    add_csv_reports()
    