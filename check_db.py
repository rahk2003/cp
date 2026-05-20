import chromadb
from pathlib import Path

# جربي المسارين عشان نشوف وين القاعدة فعلياً
paths_to_check = [
    r"C:\Users\jojoo\Desktop\RAG\rag_db",
    r"C:\Users\jojoo\Desktop\RAG2\rag_db",
]

for p in paths_to_check:
    print(f"\n--- Checking: {p} ---")
    if not Path(p).exists():
        print("  ❌ المسار غير موجود")
        continue
    try:
        client = chromadb.PersistentClient(path=p)
        cols = client.list_collections()
        if not cols:
            print("  ⚠️  المسار موجود بس ما فيه أي collections")
        else:
            print(f"  ✅ Collections found ({len(cols)}):")
            for c in cols:
                print(f"     - name: '{c.name}'  |  count: {c.count()} chunks")
    except Exception as e:
        print(f"  ❌ Error: {e}")