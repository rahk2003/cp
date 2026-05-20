"""
=======================================================================
  RAG Evaluation v2 — مع تحسينات للـ multi-source
=======================================================================

  التحسينات عن النسخة الأولى:
    1. TOP_K_RETRIEVE = 15 (نسحب أكثر)
    2. TOP_K_CONTEXT  = 8  (نستخدم أكثر في الـ prompt)
    3. Source diversification: نضمن إن النتائج تجي من ملفات مختلفة
       (مفيد جداً لأسئلة multi_source)
    4. مع المحافظة على نفس مكونات الراق الأصلي (Chroma + Groq + multilingual-mpnet)

=======================================================================
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# CONFIG
# =====================================================================
DB_DIR     = Path(r"C:\Users\jojoo\Desktop\RAG2\rag_db")
COLLECTION = "oil_spill_knowledge"
EMBED_MODEL = "paraphrase-multilingual-mpnet-base-v2"

EVAL_QUESTIONS_PATH = "eval_questions.json"
RESULTS_DIR = Path("eval_results_v2")
RESULTS_DIR.mkdir(exist_ok=True)

# 🔥 التحسين: نسحب أكثر ثم ننوّع
TOP_K_RETRIEVE = 15     # نسحب 15 من Chroma
TOP_K_CONTEXT  = 8      # نمرّر 8 للـ LLM بعد التنويع
MAX_PER_SOURCE = 3      # حد أقصى 3 chunks من نفس الملف (يجبر التنويع)

# Groq
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# =====================================================================
# Init
# =====================================================================
print("[init] Loading embedding model…")
from sentence_transformers import SentenceTransformer
embedder = SentenceTransformer(EMBED_MODEL)

print("[init] Connecting to ChromaDB…")
import chromadb
from chromadb.config import Settings
client = chromadb.PersistentClient(
    path=str(DB_DIR),
    settings=Settings(anonymized_telemetry=False),
)
collection = client.get_collection(COLLECTION)
print(f"[init] Collection has {collection.count()} chunks.")

print("[init] Initialising Groq…")
from groq import Groq
if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY غير موجود في .env")
groq_client = Groq(api_key=GROQ_API_KEY)
print(f"[init] Groq ready. Model: {GROQ_MODEL}\n")


# =====================================================================
# 🔥 Source-aware diversification
# =====================================================================
def diversify_by_source(docs, metadatas, distances,
                        max_per_source=MAX_PER_SOURCE,
                        final_k=TOP_K_CONTEXT):
    """
    يأخذ نتائج Chroma المرتبة بالـ similarity،
    ويعيد ترتيبها بحيث:
      1. ما يطلع أكثر من max_per_source من نفس الملف
      2. النتيجة النهائية فيها تنويع بين الملفات
      3. كل ملف يأخذ أفضل chunk منه أولاً، ثم الثاني، إلخ.

    هذا يحل مشكلة multi_source: لو سؤال يحتاج 3 ملفات،
    قبل كنا نجيب 5 chunks كلها من نفس الملف؛ الحين نضمن التنويع.
    """
    # نجمّع النتائج حسب source ونحافظ على الترتيب الأصلي
    by_source = defaultdict(list)
    for doc, meta, dist in zip(docs, metadatas, distances):
        src = meta.get("source", "unknown")
        by_source[src].append((doc, meta, dist))

    # نأخذ أفضل واحد من كل مصدر، ثم ثاني، إلخ (round-robin)
    diversified = []
    iters = {src: iter(items) for src, items in by_source.items()}
    counts = defaultdict(int)

    # ندور لين نوصل final_k أو نخلّص كل المصادر
    keep_going = True
    while keep_going and len(diversified) < final_k:
        keep_going = False
        for src in list(iters.keys()):
            if counts[src] >= max_per_source:
                continue
            try:
                item = next(iters[src])
                diversified.append((src, item))
                counts[src] += 1
                keep_going = True
                if len(diversified) >= final_k:
                    break
            except StopIteration:
                pass

    new_docs      = [item[1][0] for item in diversified]
    new_metadatas = [item[1][1] for item in diversified]
    new_distances = [item[1][2] for item in diversified]
    return new_docs, new_metadatas, new_distances


# =====================================================================
# RAG query function (محسّنة)
# =====================================================================
SYSTEM_PROMPT = """You are an expert assistant on marine oil spill response and analysis.
Answer the user's question using ONLY the information in the provided context.

IMPORTANT:
- The context may include both technical document excerpts AND statistical records from an oil spill dataset.
- If the question requires combining information from MULTIPLE sources, integrate them properly.
- Answer in the SAME language as the question (Arabic ↔ Arabic, English ↔ English).
- If the answer is not in the context, say so honestly. Do not make up facts.
- Be concise but complete. Cite specific values, numbers, or sources when relevant."""


def your_rag_query(question: str) -> Dict[str, Any]:
    # 1. embed
    q_emb = embedder.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).tolist()

    # 2. retrieve أكثر من الأول
    results = collection.query(
        query_embeddings=q_emb,
        n_results=TOP_K_RETRIEVE,
        include=["documents", "metadatas", "distances"],
    )
    docs      = results["documents"][0]      if results["documents"]      else []
    metadatas = results["metadatas"][0]      if results["metadatas"]      else []
    distances = results["distances"][0]      if results["distances"]      else []

    # 3. 🔥 diversify
    docs_div, metas_div, _ = diversify_by_source(docs, metadatas, distances)

    # 4. normalize source names (add .pdf for matching)
    retrieved_sources = []
    for m in metas_div:
        src = m.get("source", "")
        ftype = m.get("file_type", "")
        if src and ftype in ("pdf",) and not src.lower().endswith(".pdf"):
            src = src + ".pdf"
        retrieved_sources.append(src)

    # 5. build context
    context_blocks = []
    for i, (doc, meta) in enumerate(zip(docs_div, metas_div), 1):
        src   = meta.get("source", "unknown")
        page  = meta.get("page", "?")
        ftype = meta.get("file_type", "pdf")
        if ftype == "csv_summary":
            label = f"[Source {i}: {src} — statistical summary]"
        elif ftype == "csv_row":
            label = f"[Source {i}: {src} — record #{page}]"
        else:
            label = f"[Source {i}: {src} — page {page}]"
        context_blocks.append(f"{label}\n{doc}")
    context_str = "\n\n---\n\n".join(context_blocks)

    user_prompt = f"""Context:
{context_str}

Question: {question}

Answer:"""

    # 6. call Groq
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=1024,
        )
        answer = completion.choices[0].message.content
    except Exception as e:
        answer = f"[ERROR calling Groq: {e}]"

    return {
        "answer":            answer,
        "contexts":          docs_div,
        "retrieved_sources": retrieved_sources,
    }


# =====================================================================
# Retrieval metrics
# =====================================================================
def normalize_source(s):
    name = os.path.basename(str(s)).strip().lower()
    if name.endswith(".pdf"):
        name = name[:-4]
    return name


def hit_rate_at_k(expected, retrieved, k=TOP_K_CONTEXT):
    exp_set = {normalize_source(s) for s in expected}
    top_k   = [normalize_source(s) for s in retrieved[:k]]
    return 1.0 if any(r in exp_set for r in top_k) else 0.0


def reciprocal_rank(expected, retrieved):
    exp_set = {normalize_source(s) for s in expected}
    for i, r in enumerate(retrieved, start=1):
        if normalize_source(r) in exp_set:
            return 1.0 / i
    return 0.0


def source_recall_at_k(expected, retrieved, k=TOP_K_CONTEXT):
    exp_set = {normalize_source(s) for s in expected}
    top_k   = {normalize_source(s) for s in retrieved[:k]}
    if not exp_set:
        return 0.0
    return len(exp_set & top_k) / len(exp_set)


# =====================================================================
# Pipeline
# =====================================================================
def run_rag(questions):
    records = []
    for q in tqdm(questions, desc="Running RAG"):
        try:
            out = your_rag_query(q["question"])
            records.append({
                **q,
                "predicted_answer":   out["answer"],
                "retrieved_contexts": out["contexts"],
                "retrieved_sources":  out["retrieved_sources"],
                "error": None,
            })
        except Exception as e:
            records.append({
                **q,
                "predicted_answer":   "",
                "retrieved_contexts": [],
                "retrieved_sources":  [],
                "error": str(e),
            })
    return records


def add_metrics(records):
    for r in records:
        exp = r.get("expected_sources", []) or []
        ret = r.get("retrieved_sources", []) or []
        r["hit_rate@k"]      = hit_rate_at_k(exp, ret)
        r["reciprocal_rank"] = reciprocal_rank(exp, ret)
        r["source_recall@k"] = source_recall_at_k(exp, ret)
    return records


def summarize(records):
    df = pd.DataFrame(records)
    metric_cols = ["hit_rate@k", "reciprocal_rank", "source_recall@k"]
    summary = {
        "overall":       {m: float(df[m].mean()) for m in metric_cols},
        "by_language":   df.groupby("language")[metric_cols].mean().round(4).to_dict(orient="index"),
        "by_type":       df.groupby("type")[metric_cols].mean().round(4).to_dict(orient="index"),
        "by_difficulty": df.groupby("difficulty")[metric_cols].mean().round(4).to_dict(orient="index"),
        "n_questions":   len(df),
        "n_errors":      int(df["error"].notna().sum()),
    }
    return summary, df


# =====================================================================
# Main
# =====================================================================
def main():
    print("=" * 70)
    print(f"  RAG EVALUATION v2  (top_k_retrieve={TOP_K_RETRIEVE}, "
          f"top_k_context={TOP_K_CONTEXT}, max_per_source={MAX_PER_SOURCE})")
    print("=" * 70)

    with open(EVAL_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)
    print(f"\nLoaded {len(questions)} questions.\n")

    records = run_rag(questions)
    records = add_metrics(records)

    with open(RESULTS_DIR / "raw_rag_outputs.json", "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    summary, df = summarize(records)
    df.to_csv(RESULTS_DIR / "per_question_results.csv",
              index=False, encoding="utf-8-sig")
    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"\nTotal questions: {summary['n_questions']} | Errors: {summary['n_errors']}\n")

    print("OVERALL SCORES:")
    for m, v in summary["overall"].items():
        bar = "█" * int(v * 30)
        print(f"  {m:>22s}: {v:.4f}  {bar}")

    print("\nBY LANGUAGE:")
    print(pd.DataFrame(summary["by_language"]).T.round(4).to_string())
    print("\nBY TYPE:")
    print(pd.DataFrame(summary["by_type"]).T.round(4).to_string())
    print("\nBY DIFFICULTY:")
    print(pd.DataFrame(summary["by_difficulty"]).T.round(4).to_string())

    print(f"\n✓ Results in: {RESULTS_DIR}/")
    print("=" * 70)


if __name__ == "__main__":
    main()