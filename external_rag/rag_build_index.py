"""
=============================================================
RAG Step 1: Build the vector database from PDFs
=============================================================
يقرأ كل PDF في rag_documents/، يقسّمها لـ chunks،
يحوّلها لـ embeddings (multilingual)، ويخزّنها في ChromaDB.

شغّليه مرة وحدة فقط (أو كل ما تضيفين/تحذفين PDFs).
"""

from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import hashlib

# =========================
# الإعدادات
# =========================
PDF_DIR = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_documents")
DB_DIR  = Path(r"C:\Users\hp\Desktop\PR_T\cp\external_rag\rag_db")
COLLECTION = "oil_spill_knowledge"

EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

CHUNK_SIZE    = 500     # عدد الأحرف في كل قطعة
CHUNK_OVERLAP = 80      # تداخل بين القطع للحفاظ على السياق

PDF_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# 1. قراءة PDFs
# =========================
def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """يستخرج النص من كل صفحة، مع رقم الصفحة."""
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({
                    "page": i,
                    "text": text
                })
        except Exception as e:
            print(f"  [WARN] page {i} failed: {e}")
    return pages


# =========================
# 2. تقسيم النصوص
# =========================
def chunk_pages(pages: list[dict], source: str) -> list[dict]:
    """يقسّم النصوص ويحتفظ بمعلومات المصدر والصفحة."""
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
                "text":   c,
                "source": source,
                "page":   p["page"],
                "chunk":  j,
            })
    return all_chunks


def make_id(source: str, page: int, chunk: int, text: str) -> str:
    """ID فريد لكل chunk."""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}_p{page}_c{chunk}_{h}"


# =========================
# 3. بناء قاعدة البيانات
# =========================
def build_index():
    print("=" * 60)
    print("Building RAG index")
    print("=" * 60)

    # تحميل embedding model
    print(f"\n[1/4] Loading embedding model: {EMBED_MODEL}")
    print("      (أول مرة راح يحمّل ~500MB — انتظري شوي)")
    embedder = SentenceTransformer(EMBED_MODEL)
    print("      Model loaded.")

    # ChromaDB
    print(f"\n[2/4] Setting up ChromaDB at: {DB_DIR}")
    client = chromadb.PersistentClient(
        path=str(DB_DIR),
        settings=Settings(anonymized_telemetry=False),
    )

    # احذفي المجموعة القديمة لو موجودة (rebuild نظيف)
    try:
        client.delete_collection(COLLECTION)
        print(f"      Old collection deleted.")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # قراءة الـ PDFs
    print(f"\n[3/4] Reading PDFs from: {PDF_DIR}")
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"      ⚠️  ما فيه PDFs في {PDF_DIR}")
        print(f"      حطّي الملفات وأعيدي تشغيل السكربت.")
        return

    print(f"      Found {len(pdf_files)} PDF(s)")

    all_chunks = []
    for pdf in pdf_files:
        print(f"\n      → {pdf.name}")
        pages  = extract_text_from_pdf(pdf)
        chunks = chunk_pages(pages, source=pdf.stem)
        print(f"        pages: {len(pages)}, chunks: {len(chunks)}")
        all_chunks.extend(chunks)

    print(f"\n      Total chunks: {len(all_chunks)}")

    # حساب embeddings وحفظها
    print(f"\n[4/4] Computing embeddings and saving to DB...")
    texts     = [c["text"] for c in all_chunks]
    metadatas = [
        {"source": c["source"], "page": c["page"], "chunk": c["chunk"]}
        for c in all_chunks
    ]
    ids = [
        make_id(c["source"], c["page"], c["chunk"], c["text"])
        for c in all_chunks
    ]

    # batch processing عشان نتفادى مشاكل الذاكرة
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
    print(f"   DB path: {DB_DIR}")
    print(f"   Collection: {COLLECTION}")
    print("=" * 60)


if __name__ == "__main__":
    build_index()