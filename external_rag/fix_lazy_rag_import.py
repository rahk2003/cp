from pathlib import Path

path = Path("Unified assistant.py")
text = path.read_text(encoding="utf-8")

old_import = "import rag_query as rag_module  # = الكود الثاني (RAG / Groq)"
new_import = '''# RAG يتم تحميله فقط عند الحاجة حتى لا يبطئ أسئلة SQL
rag_module = None

def get_rag_module():
    global rag_module
    if rag_module is None:
        import rag_query as _rag_module
        rag_module = _rag_module
    return rag_module
'''

if old_import not in text:
    print("Could not find the exact rag import line. Check the file manually.")
else:
    text = text.replace(old_import, new_import)

text = text.replace(
    "rag_result = rag_module.answer(question, verbose=verbose)",
    "rag_result = get_rag_module().answer(question, verbose=verbose)"
)

path.write_text(text, encoding="utf-8")
print("Lazy RAG import applied successfully.")
