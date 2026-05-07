from pathlib import Path

path = Path("Unified assistant.py")
text = path.read_text(encoding="utf-8")

# حذف كلمة عامة تسبب تحويل أسئلة معرفية إلى SQL
text = text.replace(
    '"list", "show me", "كم تسرب", "كم سبيل", "تسربات",',
    '"list", "show me", "كم تسرب", "كم سبيل",'
)

# إضافة كلمات معرفية/بيئية إلى RAG
old = '"protocol", "بروتوكول", "guidelines", "إرشادات",'
new = '''"protocol", "بروتوكول", "guidelines", "إرشادات",

    # تأثيرات بيئية ومعرفية لازم تروح RAG
    "تأثير", "اثر", "أثر", "آثار", "اضرار", "أضرار", "ضرر",
    "الأسماك", "الاسماك", "اسماك", "سمك", "مصايد", "مصائد",
    "الحياة البحرية", "البيئة البحرية", "الكائنات البحرية",
    "تلوث", "التلوث", "pollution", "impact", "effect", "effects",
    "fish", "fisheries", "mariculture", "marine environment",'''
text = text.replace(old, new)

# تحسين Prompt الراوتر
text = text.replace(
    'ما خطوات الاحتواء؟ best practices؟ تعريفات؟',
    'ما خطوات الاحتواء؟ best practices؟ تعريفات؟ تأثير النفط على الأسماك؟ البيئة البحرية؟ pollution effects؟'
)

path.write_text(text, encoding="utf-8")
print("Router updated successfully.")
