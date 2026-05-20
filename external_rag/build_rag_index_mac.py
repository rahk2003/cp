"""
=======================================================================
  RAG Index Builder v2 — يفهرس PDFs + CSV سوا
=======================================================================

  التحسينات عن النسخة الأولى:
    1. يفهرس ملف CSV كمان (مو بس PDFs) -> يحل مشكلة الـ 0.00 في أسئلة CSV
    2. CSV chunking ذكي: كل صف يصير "وثيقة نصية" منفصلة بصيغة قابلة للاسترجاع
    3. Metadata غني (file_type يفرّق بين pdf و csv)

  شغّليه مرة وحدة، بعدها استخدمي rag_evaluation_v2.py.
"""

from pathlib import Path
import hashlib
import csv as csv_module

from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

# =========================
# الإعدادات
# =========================
from pathlib import Path

BASE_DIR   = Path("/Users/rana/Documents/tuwaiq/CP")

PDF_DIR    = BASE_DIR / "rag_documents"
CSV_PATH   = PDF_DIR / "spill_analysis_results_full_with_llm.csv"
DB_DIR     = BASE_DIR / "rag_db"
COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

CHUNK_SIZE    = 500
CHUNK_OVERLAP = 80

PDF_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 1. قراءة PDFs (كما السابق)
# =========================
def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page": i, "text": text})
        except Exception as e:
            print(f"  [WARN] page {i} failed: {e}")
    return pages


def chunk_pages(pages, source):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    all_chunks = []
    for p in pages:
        chunks = splitter.split_text(p["text"])
        for j, c in enumerate(chunks):
            all_chunks.append({
                "text":      c,
                "source":    source,
                "page":      p["page"],
                "chunk":     j,
                "file_type": "pdf",
            })
    return all_chunks


# =========================
# 2. قراءة CSV — تحويل كل صف لـ chunk نصي
# =========================
# الفكرة: نحوّل كل صف من 1200 سجل إلى وصف نصي طبيعي
# عشان embedding model يقدر يفهمه ويبحث فيه.

def csv_row_to_text(row: dict, row_idx: int) -> str:
    """يحوّل صف CSV إلى نص قابل للبحث."""
    # نختار الأعمدة المهمة للأسئلة المتوقعة
    return (
        f"Spill record number {row_idx} (filename: {row.get('filename', 'unknown')}). "
        f"Oil-covered area: {row.get('area_m2', '?')} square meters "
        f"({row.get('area_px', '?')} pixels). "
        f"Coverage percentage of image: {row.get('coverage_pct', '?')}%. "
        f"Perimeter: {row.get('perimeter_m', '?')} meters. "
        f"Spread ratio: {row.get('spread_ratio', '?')}. "
        f"Number of components: {row.get('num_components', '?')}. "
        f"Compactness: {row.get('compactness', '?')}. "
        f"Distance to nearest land: {row.get('distance_to_land_km', '?')} km "
        f"({row.get('distance_to_land_m', '?')} m). "
        f"Land proximity class: {row.get('land_proximity_class', '?')}. "
        f"Distance to nearest coral reef: {row.get('distance_to_coral_km', '?')} km. "
        f"Coral proximity class: {row.get('coral_proximity_class', '?')}. "
        f"Risk score: {row.get('risk_score', '?')}. "
        f"Risk level: {row.get('risk_level', '?')}. "
        f"Risk factors breakdown: {row.get('risk_factors', '?')}. "
        f"Geographic location: latitude {row.get('spill_centroid_lat', '?')}, "
        f"longitude {row.get('spill_centroid_lon', '?')}. "
        f"Image dimensions: {row.get('width', '?')}x{row.get('height', '?')} pixels."
    )


def build_csv_summary_chunks(csv_path: Path) -> list[dict]:
    """
    يبني نوعين من chunks للـ CSV:
      أ) chunks لكل صف (1200 chunk للسجلات الفردية)
      ب) chunks تلخيصية إحصائية (للأسئلة الإجمالية مثل 'كم HIGH؟')
    """
    chunks = []

    print(f"  → Reading CSV: {csv_path.name}")
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv_module.DictReader(f)
        all_rows = list(reader)

    print(f"    Total rows: {len(all_rows)}")
    print(f"    Total columns: {len(all_rows[0].keys()) if all_rows else 0}")

    # (أ) صف لكل سجل
    for i, row in enumerate(all_rows, start=1):
        text = csv_row_to_text(row, i)
        chunks.append({
            "text":      text,
            "source":    "spill_analysis_results_full_with_llm.csv",
            "page":      i,            # نستخدم page كرقم الصف
            "chunk":     0,
            "file_type": "csv_row",
        })

    # (ب) chunks تلخيصية إحصائية — مهمة جداً لأسئلة "كم عدد..."
    from collections import Counter
    risk_levels   = Counter(r["risk_level"] for r in all_rows if r.get("risk_level"))
    land_classes  = Counter(r["land_proximity_class"] for r in all_rows if r.get("land_proximity_class"))
    coral_classes = Counter(r["coral_proximity_class"] for r in all_rows if r.get("coral_proximity_class"))

    summaries = []

    summaries.append(
        f"Dataset summary: The spill analysis CSV file 'spill_analysis_results_full_with_llm.csv' "
        f"contains {len(all_rows)} oil spill records. "
        f"It has {len(all_rows[0].keys())} columns describing each spill: filename, area (in pixels "
        f"and m²), perimeter, coverage percentage, geographic coordinates (latitude/longitude, "
        f"bounding box, corner coordinates), shape metrics (compactness, spread_ratio, "
        f"orientation_deg, num_components, contours_count, centroid), pixel size, image dimensions, "
        f"distance to land (in meters and km) with proximity class, distance to coral reefs (km) with "
        f"proximity class, risk_score, risk_level, and risk_factors breakdown."
    )

    summaries.append(
        f"Risk level distribution in the spill dataset: "
        f"HIGH risk: {risk_levels.get('HIGH', 0)} records. "
        f"MEDIUM risk: {risk_levels.get('MEDIUM', 0)} records. "
        f"CRITICAL risk: {risk_levels.get('CRITICAL', 0)} records. "
        f"LOW risk: {risk_levels.get('LOW', 0)} records. "
        f"Risk levels are classified into four categories: LOW, MEDIUM, HIGH, and CRITICAL. "
        f"إحصاءات مستويات الخطر: عالي {risk_levels.get('HIGH', 0)}، متوسط {risk_levels.get('MEDIUM', 0)}، "
        f"حرج {risk_levels.get('CRITICAL', 0)}، منخفض {risk_levels.get('LOW', 0)}."
    )

    summaries.append(
        f"Land proximity distribution: "
        + ", ".join(f"'{cls}': {count} records" for cls, count in land_classes.most_common())
        + ". The most common land proximity class is "
        + (f"'{land_classes.most_common(1)[0][0]}' with {land_classes.most_common(1)[0][1]} records" if land_classes else "")
        + "."
    )

    summaries.append(
        f"Coral reef proximity distribution: "
        + ", ".join(f"'{cls}': {count} records" for cls, count in coral_classes.most_common())
        + ". Number of spills that directly touch coral reefs (Touches coral reef class): "
        + f"{coral_classes.get('Touches coral reef', 0)}. "
        + "Number of spills that touch land (Touches land class): "
        + f"{land_classes.get('Touches land', 0)}."
    )

    # إحصاءات المساحة
    areas = [float(r["area_m2"]) for r in all_rows if r.get("area_m2")]
    if areas:
        import statistics
        max_area_row = max(all_rows, key=lambda r: float(r.get("area_m2", 0) or 0))
        summaries.append(
            f"Spill area statistics: "
            f"average area = {statistics.mean(areas):.0f} m², "
            f"median area = {statistics.median(areas):.0f} m², "
            f"maximum area = {max(areas):.0f} m² "
            f"(record {max_area_row['filename']}, classified as {max_area_row.get('risk_level','?')}, "
            f"with coverage {max_area_row.get('coverage_pct','?')}%). "
            f"Minimum area = {min(areas):.0f} m²."
        )

    # risk_score القصوى
    scores = [(float(r.get("risk_score", 0) or 0), r) for r in all_rows]
    max_score = max(scores, key=lambda x: x[0])[0] if scores else 0
    n_at_max = sum(1 for s, _ in scores if s == max_score)
    summaries.append(
        f"Risk score statistics: maximum risk_score recorded in the dataset is {max_score}. "
        f"{n_at_max} records reach this maximum risk score and are all classified as CRITICAL."
    )

    for s_idx, summary_text in enumerate(summaries):
        chunks.append({
            "text":      summary_text,
            "source":    "spill_analysis_results_full_with_llm.csv",
            "page":      0,                       # 0 = summary chunk
            "chunk":     s_idx,
            "file_type": "csv_summary",
        })

    print(f"    Created {len(all_rows)} row-chunks + {len(summaries)} summary-chunks")
    return chunks


# =========================
# 3. ID فريد
# =========================
def make_id(source, page, chunk, text):
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}_p{page}_c{chunk}_{h}"


# =========================
# 4. بناء الفهرس
# =========================
def build_index():
    print("=" * 60)
    print("Building RAG index v2 (PDFs + CSV)")
    print("=" * 60)

    print(f"\n[1/4] Loading embedding model: {EMBED_MODEL}")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("      Model loaded.")

    print(f"\n[2/4] Setting up ChromaDB at: {DB_DIR}")
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection(COLLECTION)
        print(f"      Old collection deleted.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # ========== PDFs ==========
    print(f"\n[3/4] Reading PDFs from: {PDF_DIR}")
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    print(f"      Found {len(pdf_files)} PDF(s)")

    all_chunks = []
    for pdf in pdf_files:
        print(f"\n      → {pdf.name}")
        pages  = extract_text_from_pdf(pdf)
        chunks = chunk_pages(pages, source=pdf.stem)
        print(f"        pages: {len(pages)}, chunks: {len(chunks)}")
        all_chunks.extend(chunks)

    # ========== CSV ==========
    print(f"\n      → Reading CSV file")
    if CSV_PATH.exists():
        csv_chunks = build_csv_summary_chunks(CSV_PATH)
        all_chunks.extend(csv_chunks)
    else:
        print(f"      ⚠️  CSV not found at {CSV_PATH}")

    print(f"\n      Total chunks (PDF + CSV): {len(all_chunks)}")

    # ========== Embedding + insert ==========
    print(f"\n[4/4] Computing embeddings and saving to DB...")
    texts     = [c["text"] for c in all_chunks]
    metadatas = [
        {
            "source":    c["source"],
            "page":      c["page"],
            "chunk":     c["chunk"],
            "file_type": c["file_type"],
        }
        for c in all_chunks
    ]
    ids = [make_id(c["source"], c["page"], c["chunk"], c["text"]) for c in all_chunks]

    BATCH = 64
    for i in range(0, len(texts), BATCH):
        batch_texts = texts[i:i + BATCH]
        batch_embs  = embedder.encode(
            batch_texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            normalize_embeddings=True,
        ).tolist()
        collection.add(
            ids=ids[i:i + BATCH],
            embeddings=batch_embs,
            documents=batch_texts,
            metadatas=metadatas[i:i + BATCH],
        )
        print(f"      Indexed {min(i + BATCH, len(texts))}/{len(texts)}")

    print("\n" + "=" * 60)
    print(f"✅ Done. {len(all_chunks)} chunks indexed.")
    print(f"   DB path:    {DB_DIR}")
    print(f"   Collection: {COLLECTION}")
    print("=" * 60)


if __name__ == "__main__":
    build_index()