from pathlib import Path
import random
import shutil

# عدلي المسارات
IMAGES_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/Oil")
MASKS_DIR = Path("//Users/rana/Desktop/tuwaiq/CP/masks_fixed_v2")
OUTPUT_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/dataset_split")

# النسب
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

random.seed(42)

# إنشاء الفولدرات
for split in ["train", "val", "test"]:
    (OUTPUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "masks" / split).mkdir(parents=True, exist_ok=True)

# جمع الملفات المطابقة
pairs = []

for img_path in sorted(IMAGES_DIR.iterdir()):
    if not img_path.is_file():
        continue
    if img_path.suffix.lower() not in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]:
        continue

    mask_path = MASKS_DIR / img_path.name
    if mask_path.exists():
        pairs.append((img_path, mask_path))

print(f"Total matched pairs: {len(pairs)}")

# خلط
random.shuffle(pairs)

n = len(pairs)
n_train = int(n * TRAIN_RATIO)
n_val = int(n * VAL_RATIO)
n_test = n - n_train - n_val

train_pairs = pairs[:n_train]
val_pairs = pairs[n_train:n_train + n_val]
test_pairs = pairs[n_train + n_val:]

print(f"Train: {len(train_pairs)}")
print(f"Val  : {len(val_pairs)}")
print(f"Test : {len(test_pairs)}")

def copy_pairs(pairs_list, split_name):
    for img_path, mask_path in pairs_list:
        shutil.copy2(img_path, OUTPUT_DIR / "images" / split_name / img_path.name)
        shutil.copy2(mask_path, OUTPUT_DIR / "masks" / split_name / mask_path.name)

copy_pairs(train_pairs, "train")
copy_pairs(val_pairs, "val")
copy_pairs(test_pairs, "test")

print("Done splitting dataset.")