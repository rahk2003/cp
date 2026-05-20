from pathlib import Path
import numpy as np
import tensorflow as tf
import rasterio

# =========================
# عدلي هذي فقط
# =========================
BASE_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/preprocessed_dataset")
MODEL_PATH = Path("/Users/rana/Desktop/tuwaiq/CP/best_deeplab.keras")
OUTPUT_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/predicted_masks")

IMG_SIZE = 256
THRESHOLD = 0.5

TRAIN_IMG_DIR = BASE_DIR / "images" / "train"
TEST_IMG_DIR  = BASE_DIR / "images" / "test"

OUT_TRAIN_DIR = OUTPUT_DIR / "train"
OUT_TEST_DIR  = OUTPUT_DIR / "test"

OUT_TRAIN_DIR.mkdir(parents=True, exist_ok=True)
OUT_TEST_DIR.mkdir(parents=True, exist_ok=True)

# =========================
# Dice metric
# =========================
def dice_coef(y_true, y_pred, smooth=1e-6):
    y_true = tf.reshape(y_true, [-1])
    y_pred = tf.reshape(y_pred, [-1])
    y_pred = tf.cast(y_pred > 0.5, tf.float32)

    intersection = tf.reduce_sum(y_true * y_pred)
    return (2.0 * intersection + smooth) / (
        tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) + smooth
    )

# =========================
# قراءة الملفات
# =========================
def get_sorted_files(folder: Path):
    return sorted([
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])

# =========================
# قراءة الصورة وتجهيزها للمودل
# =========================
def read_tif_image(path: Path, img_size=256):
    with rasterio.open(path) as src:
        img = src.read()

    # (bands, H, W) -> (H, W, bands)
    img = np.transpose(img, (1, 2, 0))

    # توحيد القنوات إلى 3
    if img.shape[2] == 1:
        img = np.repeat(img, 3, axis=2)
    elif img.shape[2] == 2:
        third = np.expand_dims(img[:, :, 0], axis=-1)
        img = np.concatenate([img, third], axis=2)
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    img = img.astype(np.float32)

    # Normalize 0-1
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min + 1e-8)

    img = tf.image.resize(img, (img_size, img_size)).numpy()
    return img.astype(np.float32)

# =========================
# حفظ الماسك
# =========================
def save_mask(mask: np.ndarray, out_path: Path):
    with rasterio.open(
        out_path,
        "w",
        driver="GTiff",
        height=mask.shape[0],
        width=mask.shape[1],
        count=1,
        dtype=rasterio.uint8,
        nodata=0
    ) as dst:
        dst.write(mask.astype(np.uint8), 1)

# =========================
# تنفيذ التوقع وحفظ النتائج
# =========================
def predict_and_save(image_paths, output_folder: Path, model, split_name: str):
    print(f"\nProcessing {split_name}...")
    saved = 0
    failed = 0

    for img_path in image_paths:
        try:
            img = read_tif_image(img_path, IMG_SIZE)

            pred = model.predict(np.expand_dims(img, axis=0), verbose=0)[0]
            pred_mask = (pred > THRESHOLD).astype(np.uint8)

            # من (256,256,1) إلى (256,256)
            if pred_mask.ndim == 3:
                pred_mask = pred_mask[:, :, 0]

            out_path = output_folder / img_path.name
            save_mask(pred_mask, out_path)

            print(f"[SAVED] {split_name} -> {img_path.name}")
            saved += 1

        except Exception as e:
            print(f"[FAIL] {split_name} -> {img_path.name}: {e}")
            failed += 1

    print(f"\n{split_name} done.")
    print(f"Saved : {saved}")
    print(f"Failed: {failed}")

# =========================
# تحميل المودل
# =========================
print("Loading model...")
model = tf.keras.models.load_model(
    MODEL_PATH,
    custom_objects={"dice_coef": dice_coef}
)
print("Model loaded successfully.")

# =========================
# قراءة الصور
# =========================
train_images = get_sorted_files(TRAIN_IMG_DIR)
test_images  = get_sorted_files(TEST_IMG_DIR)

print(f"\nTrain images: {len(train_images)}")
print(f"Test images : {len(test_images)}")

# =========================
# حفظ ماسكات train و test
# =========================
predict_and_save(train_images, OUT_TRAIN_DIR, model, "train")
predict_and_save(test_images, OUT_TEST_DIR, model, "test")

print("\nDone.")
print(f"Train masks saved in: {OUT_TRAIN_DIR}")
print(f"Test masks saved in : {OUT_TEST_DIR}")