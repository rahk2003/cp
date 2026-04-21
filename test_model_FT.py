from pathlib import Path
import numpy as np
import tensorflow as tf
import rasterio
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay, classification_report


BASE_DIR = Path("/Users/rana/Documents/tuwaiq/CP/preprocessed_dataset")

# هذا مودل الفاين تيونق
MODEL_PATH = Path("/Users/rana/Documents/tuwaiq/CP/best_deeplab_finetuned.keras")

IMG_SIZE = 256
BATCH_SIZE = 4


SPLIT = "test"

IMG_DIR = BASE_DIR / "images" / SPLIT
MSK_DIR = BASE_DIR / "masks" / SPLIT

# =========================
# Dice metric
# =========================
def dice_coef(y_true, y_pred, smooth=1e-6):
    y_true = tf.reshape(y_true, [-1])
    y_pred = tf.reshape(y_pred, [-1])
    y_pred = tf.cast(y_pred > 0.5, tf.float32)

    intersection = tf.reduce_sum(y_true * y_pred)
    return (2. * intersection + smooth) / (
        tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) + smooth
    )

# =========================
# قراءة الملفات
# =========================
def get_sorted_files(folder):
    return sorted([
        str(p) for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])

images_list = get_sorted_files(IMG_DIR)
masks_list  = get_sorted_files(MSK_DIR)

print(f"{SPLIT.capitalize()} images:", len(images_list))
print(f"{SPLIT.capitalize()} masks :", len(masks_list))

print("\nFirst 5 pairs:")
for img_path, mask_path in list(zip(images_list, masks_list))[:5]:
    print("IMG :", Path(img_path).name)
    print("MASK:", Path(mask_path).name)
    print("---")

# =========================
# قراءة الصورة
# =========================
def read_tif_image(path):
    path = path.numpy().decode()

    with rasterio.open(path) as src:
        img = src.read()

    img = np.transpose(img, (1, 2, 0))

    if img.shape[2] == 1:
        img = np.repeat(img, 3, axis=2)
    elif img.shape[2] == 2:
        third = np.expand_dims(img[:, :, 0], axis=-1)
        img = np.concatenate([img, third], axis=2)
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    img = img.astype(np.float32)
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min + 1e-8)

    img = tf.image.resize(img, (IMG_SIZE, IMG_SIZE)).numpy()
    return img.astype(np.float32)

# =========================
# قراءة الماسك
# =========================
def read_tif_mask(path):
    path = path.numpy().decode()

    with rasterio.open(path) as src:
        mask = src.read(1)

    mask = (mask > 0).astype(np.float32)
    mask = np.expand_dims(mask, axis=-1)
    mask = tf.image.resize(mask, (IMG_SIZE, IMG_SIZE), method="nearest").numpy()
    return mask.astype(np.float32)

def load_sample(img_path, mask_path):
    img = tf.py_function(read_tif_image, [img_path], tf.float32)
    mask = tf.py_function(read_tif_mask, [mask_path], tf.float32)

    img.set_shape([IMG_SIZE, IMG_SIZE, 3])
    mask.set_shape([IMG_SIZE, IMG_SIZE, 1])

    return img, mask

def make_dataset(image_paths, mask_paths):
    ds = tf.data.Dataset.from_tensor_slices((image_paths, mask_paths))
    ds = ds.map(load_sample, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    return ds

ds = make_dataset(images_list, masks_list)

# =========================
# تحميل مودل الفاين تيونق
# =========================
print("\nLoading fine-tuned model...")
model = tf.keras.models.load_model(
    MODEL_PATH,
    custom_objects={"dice_coef": dice_coef}
)
print("Fine-tuned model loaded successfully.")

# =========================
# تقييم المودل على الـ split المختار
# =========================
print(f"\nEvaluating on {SPLIT} set...")
results = model.evaluate(ds, verbose=1)
print("Results:", results)

# إذا تبين أسماء المقاييس مع القيم
print("\nMetrics:")
for name, value in zip(model.metrics_names, results):
    print(f"{name}: {value:.6f}")

# =========================
# عرض 3 نتائج
# =========================
print("\nShowing sample predictions...")
for images, masks in ds.take(1):
    preds = model.predict(images, verbose=0)
    preds_bin = (preds > 0.5).astype(np.float32)

    n = min(3, len(images))

    for i in range(n):
        img = images[i].numpy()
        true_mask = masks[i].numpy().squeeze()
        pred_mask = preds_bin[i].squeeze()

        plt.figure(figsize=(12, 4))

        plt.subplot(1, 3, 1)
        plt.imshow(img)
        plt.title("Image")
        plt.axis("off")

        plt.subplot(1, 3, 2)
        plt.imshow(true_mask, cmap="gray")
        plt.title("True Mask")
        plt.axis("off")

        plt.subplot(1, 3, 3)
        plt.imshow(pred_mask, cmap="gray")
        plt.title("Predicted Mask")
        plt.axis("off")

        plt.tight_layout()
        plt.show()

# =========================
# Confusion Matrix
# =========================
print(f"\nComputing confusion matrix on {SPLIT} set...")
y_true_all = []
y_pred_all = []

for images, masks in ds:
    preds = model.predict(images, verbose=0)
    preds_bin = (preds > 0.5).astype(np.uint8)

    y_true_all.append(masks.numpy().astype(np.uint8).ravel())
    y_pred_all.append(preds_bin.ravel())

y_true_all = np.concatenate(y_true_all)
y_pred_all = np.concatenate(y_pred_all)

cm = confusion_matrix(y_true_all, y_pred_all)

print("\nConfusion Matrix:")
print(cm)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=["Background", "Oil Spill"]
)
disp.plot(cmap="Blues")
plt.title(f"Pixel-wise Confusion Matrix ({SPLIT})")
plt.show()

print("\nClassification Report:")
print(classification_report(
    y_true_all,
    y_pred_all,
    target_names=["Background", "Oil Spill"]
))