# ============================================================
# prepare_oil_tokenized_dataset.py
# تجهيز Oil Spill Dataset من PostgreSQL ورفعها على Hugging Face
# مع Tokenizer
# بدون prompts
# بدون messages
# بدون fine-tuning model
# بدون GeoJSON
# ============================================================

# الفكرة:
# 1) نسحب جدول spill_analysis_results من PostgreSQL
# 2) نجهز عمود text عادي من بيانات الصف
# 3) نحول risk_level إلى labels رقمية
# 4) نقسم الداتا train / validation / test
# 5) نستخدم Tokenizer لإنتاج:
#    input_ids
#    token_type_ids
#    attention_mask
# 6) نرفع الداتا على Hugging Face


# ============================================================
# 1) Import libraries
# ============================================================

import os
import json
from datetime import datetime
from urllib.parse import quote_plus
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split

from datasets import Dataset, DatasetDict, ClassLabel
from transformers import AutoTokenizer
from huggingface_hub import login, create_repo, upload_file


# ============================================================
# 2) إعدادات PostgreSQL
# ============================================================

DB_NAME = "oil_spills"
DB_USER = "postgres"

# اكتبي باسورد PostgreSQL هنا
DB_PASSWORD = "1234"

DB_HOST = "localhost"
DB_PORT = "5432"
TABLE_NAME = "spill_analysis_results"


# ============================================================
# 3) إعدادات Hugging Face
# ============================================================

HF_TOKEN = "PUT_YOUR_HF_TOKEN_HERE"

# اسم الريبو في Hugging Face
HF_REPO_ID = "ra-hk1/oil-spill-tokenized-dataset"

# False يعني Public
PRIVATE_DATASET = False

OUTPUT_DIR = Path("PUT_YOUR_HF_TOKEN_HERE")

SEED = 42


# ============================================================
# 4) إعدادات Tokenizer
# ============================================================

# اخترت BERT tokenizer لأنه يعطي:
# input_ids
# token_type_ids
# attention_mask
#
# هذا يشبه كثير داتا الأفلام الجاهزة للتصنيف.
# هنا ما نحمل مودل، فقط tokenizer.
TOKENIZER_ID = "bert-base-uncased"

MAX_LENGTH = 256


# ============================================================
# 5) إنشاء مجلد الإخراج
# ============================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("Oil Spill Tokenized Dataset Preparation")
print("=" * 70)


# ============================================================
# 6) الاتصال بقاعدة البيانات
# ============================================================

safe_password = quote_plus(DB_PASSWORD)

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{safe_password}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)

print("تم تجهيز الاتصال بقاعدة البيانات.")


# ============================================================
# 7) قراءة البيانات من PostgreSQL
# ============================================================

# اخترنا الأعمدة الآمنة للنشر فقط.
# ما أخذنا source_image_path أو predicted_mask_path عشان لا تظهر مسارات جهازك.
query = f"""
SELECT
    filename,
    area_m2,
    coverage_pct,
    distance_to_land_km,
    land_proximity_class,
    distance_to_coral_km,
    coral_proximity_class,
    risk_score,
    risk_level,
    risk_factors,
    date,
    time
FROM {TABLE_NAME}
WHERE filename IS NOT NULL
  AND risk_level IS NOT NULL;
"""

df = pd.read_sql(query, engine)

print("\nتم تحميل البيانات من PostgreSQL.")
print("عدد الصفوف:", len(df))
print("الأعمدة:")
print(df.columns.tolist())
print("\nأول 5 صفوف:")
print(df.head())


# ============================================================
# 8) فحص البيانات
# ============================================================

if len(df) == 0:
    raise ValueError("الداتا فاضية. تأكدي من اسم قاعدة البيانات والجدول.")

# حذف التكرار
before = len(df)
df = df.drop_duplicates().reset_index(drop=True)
after = len(df)

print("\nفحص التكرار:")
print("قبل:", before)
print("بعد:", after)

print("\nالقيم الناقصة:")
print(df.isna().sum())

print("\nتوزيع risk_level:")
print(df["risk_level"].value_counts(dropna=False))


# ============================================================
# 9) تجهيز label names
# ============================================================

# هنا نحول risk_level إلى labels رقمية مثل:
# HIGH -> 0
# LOW -> 1
# MEDIUM -> 2
#
# الترتيب يكون ثابت لأننا استخدمنا sorted.
label_names = sorted(df["risk_level"].dropna().unique().tolist())

label2id = {label: idx for idx, label in enumerate(label_names)}
id2label = {idx: label for label, idx in label2id.items()}

print("\nLabel names:")
print(label_names)

print("\nlabel2id:")
print(label2id)


# ============================================================
# 10) تحويل صف البيانات إلى نص عادي
# ==========================================================

def row_to_text(row):
    """
    هذه الدالة لا تكتب prompt.
    فقط تحول الصف إلى نص منظم حتى يستطيع tokenizer تحويله إلى tokens.
    """

    text = (
        f"filename: {row['filename']} "
        f"area_m2: {row['area_m2']} "
        f"coverage_pct: {row['coverage_pct']} "
        f"distance_to_land_km: {row['distance_to_land_km']} "
        f"land_proximity_class: {row['land_proximity_class']} "
        f"distance_to_coral_km: {row['distance_to_coral_km']} "
        f"coral_proximity_class: {row['coral_proximity_class']} "
        f"risk_score: {row['risk_score']} "
        f"risk_factors: {row['risk_factors']} "
        f"date: {row['date']} "
        f"time: {row['time']}"
    )

    return text


df["text"] = df.apply(row_to_text, axis=1)

# labels هي نسخة رقمية من risk_level
df["labels"] = df["risk_level"].map(label2id)


# text + labels
prepared_df = df[["text", "labels"]].copy()

print("\nمثال text:")
print(prepared_df.iloc[0]["text"])

print("\nمثال labels:")
print(prepared_df.iloc[0]["labels"])


# ============================================================
# 11) تقسيم البيانات إلى train / validation / test
# ============================================================

# نحافظ على توزيع labels داخل الأقسام إذا ممكن.
label_counts = prepared_df["labels"].value_counts()

can_stratify = len(label_counts) > 1 and label_counts.min() >= 2
stratify_col = prepared_df["labels"] if can_stratify else None

train_df, temp_df = train_test_split(
    prepared_df,
    test_size=0.2,
    random_state=SEED,
    shuffle=True,
    stratify=stratify_col
)

temp_stratify = None
if can_stratify:
    temp_counts = temp_df["labels"].value_counts()
    if len(temp_counts) > 1 and temp_counts.min() >= 2:
        temp_stratify = temp_df["labels"]

validation_df, test_df = train_test_split(
    temp_df,
    test_size=0.5,
    random_state=SEED,
    shuffle=True,
    stratify=temp_stratify
)

print("\nتم تقسيم البيانات:")
print("Train:", len(train_df))
print("Validation:", len(validation_df))
print("Test:", len(test_df))


# ============================================================
# 12) تحويل DataFrame إلى Hugging Face DatasetDict
# ============================================================

raw_dataset = DatasetDict({
    "train": Dataset.from_pandas(train_df.reset_index(drop=True)),
    "validation": Dataset.from_pandas(validation_df.reset_index(drop=True)),
    "test": Dataset.from_pandas(test_df.reset_index(drop=True)),
})

# تحويل labels إلى ClassLabel حتى يظهر في Dataset info
raw_dataset = raw_dataset.cast_column(
    "labels",
    ClassLabel(names=label_names)
)

print("\nRaw Dataset:")
print(raw_dataset)

print("\nRaw features:")
print(raw_dataset["train"].features)


# ============================================================
# 13) تحميل Tokenizer
# ============================================================

# AutoTokenizer.from_pretrained يحمّل tokenizer المناسب من اسم checkpoint.
# هنا لا نحمّل أي مودل، فقط tokenizer.
tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_ID)

print("\nتم تحميل tokenizer:")
print(TOKENIZER_ID)


# ============================================================
# 14) Tokenization
# ============================================================

def tokenize_batch(batch):
    """
    هذه الدالة تطبق tokenizer على عمود text.
    الناتج:
    - input_ids
    - token_type_ids غالبًا مع BERT
    - attention_mask
    """

    return tokenizer(
        batch["text"],
        padding="max_length",
        truncation=True,
        max_length=MAX_LENGTH
    )


# Dataset.map تطبق الدالة على الداتا.
# batched=True أسرع مع tokenizer.
tokenized_dataset = raw_dataset.map(
    tokenize_batch,
    batched=True
)

print("\nTokenized Dataset:")
print(tokenized_dataset)

print("\nTokenized features:")
print(tokenized_dataset["train"].features)

print("\nأول مثال بعد التوكنة:")
print(tokenized_dataset["train"][0])


# ============================================================
# 15) حفظ نسخة محلية
# ============================================================

# حفظ النسخة الأصلية text + labels
raw_train_path = os.path.join(OUTPUT_DIR, "raw_train.jsonl")
raw_validation_path = os.path.join(OUTPUT_DIR, "raw_validation.jsonl")
raw_test_path = os.path.join(OUTPUT_DIR, "raw_test.jsonl")

train_df.to_json(raw_train_path, orient="records", lines=True, force_ascii=False)
validation_df.to_json(raw_validation_path, orient="records", lines=True, force_ascii=False)
test_df.to_json(raw_test_path, orient="records", lines=True, force_ascii=False)

# حفظ النسخة المتوكنة بصيغة JSONL
tokenized_train_path = os.path.join(OUTPUT_DIR, "train.jsonl")
tokenized_validation_path = os.path.join(OUTPUT_DIR, "validation.jsonl")
tokenized_test_path = os.path.join(OUTPUT_DIR, "test.jsonl")

tokenized_dataset["train"].to_json(tokenized_train_path, force_ascii=False)
tokenized_dataset["validation"].to_json(tokenized_validation_path, force_ascii=False)
tokenized_dataset["test"].to_json(tokenized_test_path, force_ascii=False)

# حفظ dataset كامل بصيغة Arrow محليًا
local_arrow_dir = os.path.join(OUTPUT_DIR, "arrow_dataset")
tokenized_dataset.save_to_disk(local_arrow_dir)

print("\nتم حفظ الملفات محليًا:")
print(raw_train_path)
print(raw_validation_path)
print(raw_test_path)
print(tokenized_train_path)
print(tokenized_validation_path)
print(tokenized_test_path)
print(local_arrow_dir)


# ============================================================
# 16) إنشاء dataset_summary.json
# ============================================================

dataset_summary = {
    "dataset_name": "oil-spill-tokenized-dataset",
    "source_database": DB_NAME,
    "source_table": TABLE_NAME,
    "tokenizer_id": TOKENIZER_ID,
    "max_length": MAX_LENGTH,
    "contains_prompts": False,
    "contains_chat_messages": False,
    "contains_model_weights": False,
    "contains_geojson": False,
    "task_type": "text_classification",
    "label_column": "risk_level",
    "label_names": label_names,
    "label2id": label2id,
    "id2label": id2label,
    "splits": {
        "train": len(train_df),
        "validation": len(validation_df),
        "test": len(test_df)
    },
    "features": [
        "text",
        "labels",
        "input_ids",
        "token_type_ids",
        "attention_mask"
    ],
    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

summary_path = os.path.join(OUTPUT_DIR, "dataset_summary.json")

with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(dataset_summary, f, ensure_ascii=False, indent=4)

print("\nتم إنشاء dataset_summary.json:")
print(summary_path)


# =========================
# Create README.md for Hugging Face Dataset
# =========================

readme_content = """---
license: mit
task_categories:
  - image-segmentation
language:
  - en
tags:
  - oil-spill-detection
  - satellite-imagery
  - remote-sensing
  - segmentation
  - computer-vision
  - geospatial-ai
pretty_name: Oil Spill Tokenized Dataset
size_categories:
  - 1K<n<10K
---

# Oil Spill Tokenized Dataset

This dataset is prepared for an oil spill detection project using satellite imagery and segmentation masks.

## Dataset Description

The dataset contains preprocessed satellite images and corresponding oil spill masks.  
It is intended for computer vision tasks such as semantic segmentation, oil spill detection, and geospatial AI experiments.

## Dataset Structure

The dataset is organized into three splits:

- train
- validation
- test

Each sample may include:

- image
- mask
- filename
- tokenized fields, if text/token preparation was applied

## Intended Use

This dataset can be used for:

- training image segmentation models
- testing oil spill detection models
- experimenting with satellite image analysis
- building AI-based environmental monitoring systems

## Project Goal

The main goal of this project is to detect oil spills from satellite imagery and support risk analysis using AI and geospatial data.

## Notes

This dataset was prepared as part of an educational AI and geospatial analysis project.
"""

readme_path = OUTPUT_DIR / "README.md"
readme_path.write_text(readme_content, encoding="utf-8")

print(f"README.md saved at: {readme_path}")