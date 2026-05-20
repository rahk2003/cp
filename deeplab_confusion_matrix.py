from pathlib import Path
import numpy as np
import tensorflow as tf
import rasterio
import matplotlib.pyplot as plt
import pandas as pd

# ============================================================
# PATHS
# ============================================================
BASE_DIR = Path("/Users/rana/Documents/tuwaiq/CP/preprocessed_dataset")
PROJECT_DIR = Path("/Users/rana/Documents/tuwaiq/CP")

TEST_IMG_DIR = BASE_DIR / "images" / "test"
TEST_MSK_DIR = BASE_DIR / "masks" / "test"

MODEL_PATH = PROJECT_DIR / "best_deeplab_finetuned.keras"

IMG_SIZE = 256
BATCH_SIZE = 4

# غيري الثريشولد هنا لو تبين
THRESHOLD = 0.5

# ============================================================
# GET FILES
# ============================================================
def get_sorted_files(folder):
    return sorted([
        str(p) for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])

test_images = get_sorted_files(TEST_IMG_DIR)
test_masks = get_sorted_files(TEST_MSK_DIR)

print("Test images:", len(test_images))
print("Test masks :", len(test_masks))

if len(test_images) == 0 or len(test_masks) == 0:
    raise ValueError("ما لقيت صور أو ماسكات في test. تأكدي من المسارات.")

if len(test_images) != len(test_masks):
    raise ValueError("عدد صور test لا يساوي عدد ماسكات test.")

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"ما لقيت المودل هنا: {MODEL_PATH}")

# ============================================================
# READ IMAGE AND MASK
# نفس طريقة كود التدريب حقك
# ============================================================
def read_tif_image(path):
    path = path.numpy().decode("utf-8")

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

def read_tif_mask(path):
    path = path.numpy().decode("utf-8")

    with rasterio.open(path) as src:
        mask = src.read(1)

    mask = (mask > 0).astype(np.float32)
    mask = np.expand_dims(mask, axis=-1)

    mask = tf.image.resize(
        mask,
        (IMG_SIZE, IMG_SIZE),
        method="nearest"
    ).numpy()

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

test_ds = make_dataset(test_images, test_masks)

# ============================================================
# CUSTOM METRIC FROM TRAINING
# عشان لو المودل يحتاج dice_coef وقت التحميل
# ============================================================
def dice_coef(y_true, y_pred, smooth=1e-6):
    y_true = tf.reshape(y_true, [-1])
    y_pred = tf.reshape(y_pred, [-1])
    y_pred_bin = tf.cast(y_pred > 0.5, tf.float32)

    intersection = tf.reduce_sum(y_true * y_pred_bin)
    return (2.0 * intersection + smooth) / (
        tf.reduce_sum(y_true) + tf.reduce_sum(y_pred_bin) + smooth
    )

# ============================================================
# LOAD MODEL
# ============================================================
print("\nLoading model...")
model = tf.keras.models.load_model(
    MODEL_PATH,
    custom_objects={"dice_coef": dice_coef},
    compile=False
)

print("Model loaded successfully.")

# ============================================================
# PIXEL-LEVEL CONFUSION MATRIX
# ============================================================
TN = 0
FP = 0
FN = 0
TP = 0

print("\nCalculating confusion matrix...")

for batch_images, batch_masks in test_ds:
    preds = model.predict(batch_images, verbose=0)

    y_true = batch_masks.numpy().astype(np.uint8)
    y_pred = (preds > THRESHOLD).astype(np.uint8)

    y_true = y_true.reshape(-1)
    y_pred = y_pred.reshape(-1)

    TN += np.sum((y_true == 0) & (y_pred == 0))
    FP += np.sum((y_true == 0) & (y_pred == 1))
    FN += np.sum((y_true == 1) & (y_pred == 0))
    TP += np.sum((y_true == 1) & (y_pred == 1))

conf_matrix = np.array([
    [TN, FP],
    [FN, TP]
])

# ============================================================
# METRICS FROM CONFUSION MATRIX
# ============================================================
accuracy = (TP + TN) / (TP + TN + FP + FN + 1e-8)
precision = TP / (TP + FP + 1e-8)
recall = TP / (TP + FN + 1e-8)
specificity = TN / (TN + FP + 1e-8)
f1_score = (2 * precision * recall) / (precision + recall + 1e-8)
iou = TP / (TP + FP + FN + 1e-8)
dice = (2 * TP) / ((2 * TP) + FP + FN + 1e-8)

print("\n==============================")
print("DeepLabV3+ Confusion Matrix")
print("==============================")
print(f"Threshold: {THRESHOLD}")
print()
print("Rows    = Actual")
print("Columns = Predicted")
print()
print("                 Pred 0 Background     Pred 1 Oil")
print(f"Actual 0 Background   {TN:15d}     {FP:10d}")
print(f"Actual 1 Oil          {FN:15d}     {TP:10d}")

print("\n==============================")
print("Metrics")
print("==============================")
print(f"Accuracy    : {accuracy:.4f}")
print(f"Precision   : {precision:.4f}")
print(f"Recall      : {recall:.4f}")
print(f"Specificity : {specificity:.4f}")
print(f"F1-score    : {f1_score:.4f}")
print(f"IoU         : {iou:.4f}")
print(f"Dice        : {dice:.4f}")

# ============================================================
# SAVE CSV
# ============================================================
df_cm = pd.DataFrame(
    conf_matrix,
    index=["Actual Background", "Actual Oil"],
    columns=["Pred Background", "Pred Oil"]
)

csv_path = PROJECT_DIR / "deeplab_confusion_matrix.csv"
df_cm.to_csv(csv_path)

metrics_df = pd.DataFrame({
    "metric": [
        "accuracy",
        "precision",
        "recall",
        "specificity",
        "f1_score",
        "iou",
        "dice",
        "threshold"
    ],
    "value": [
        accuracy,
        precision,
        recall,
        specificity,
        f1_score,
        iou,
        dice,
        THRESHOLD
    ]
})

metrics_csv_path = PROJECT_DIR / "deeplab_confusion_metrics.csv"
metrics_df.to_csv(metrics_csv_path, index=False)

print("\nSaved:")
print(csv_path)
print(metrics_csv_path)

# ============================================================
# PLOT CONFUSION MATRIX
# ============================================================
plt.figure(figsize=(6, 5))
plt.imshow(conf_matrix)
plt.title(f"DeepLabV3+ Confusion Matrix - Threshold {THRESHOLD}")
plt.xlabel("Predicted")
plt.ylabel("Actual")

plt.xticks([0, 1], ["Background", "Oil"])
plt.yticks([0, 1], ["Background", "Oil"])

for i in range(2):
    for j in range(2):
        plt.text(j, i, str(conf_matrix[i, j]), ha="center", va="center")

plt.colorbar()
plt.tight_layout()

fig_path = PROJECT_DIR / "deeplab_confusion_matrix.png"
plt.savefig(fig_path, dpi=300)
plt.show()

print("Saved figure:")
print(fig_path)