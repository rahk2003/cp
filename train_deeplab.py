from pathlib import Path
import numpy as np
import tensorflow as tf
import rasterio

# =========================
# المسارات
# =========================
BASE_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/preprocessed_dataset")

TRAIN_IMG_DIR = BASE_DIR / "images" / "train"
TRAIN_MSK_DIR = BASE_DIR / "masks" / "train"

VAL_IMG_DIR = BASE_DIR / "images" / "val"
VAL_MSK_DIR = BASE_DIR / "masks" / "val"

TEST_IMG_DIR = BASE_DIR / "images" / "test"
TEST_MSK_DIR = BASE_DIR / "masks" / "test"

IMG_SIZE = 256
BATCH_SIZE = 8
EPOCHS = 20

# =========================
# قراءة الملفات
# =========================
def get_sorted_files(folder):
    return sorted([
        str(p) for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])

train_images = get_sorted_files(TRAIN_IMG_DIR)
train_masks  = get_sorted_files(TRAIN_MSK_DIR)

val_images = get_sorted_files(VAL_IMG_DIR)
val_masks  = get_sorted_files(VAL_MSK_DIR)

test_images = get_sorted_files(TEST_IMG_DIR)
test_masks  = get_sorted_files(TEST_MSK_DIR)

print("Train:", len(train_images), len(train_masks))
print("Val  :", len(val_images), len(val_masks))
print("Test :", len(test_images), len(test_masks))

# =========================
# قراءة صورة tiff
# =========================
def read_tif_image(path):
    path = path.numpy().decode()

    with rasterio.open(path) as src:
        img = src.read()

    # img shape: (bands, H, W)
    img = np.transpose(img, (1, 2, 0))

    # إذا الصورة band وحدة نخليها 3 قنوات
    if img.shape[2] == 1:
        img = np.repeat(img, 3, axis=2)

    # إذا الصورة فيها قناتين، نضيف قناة ثالثة
    elif img.shape[2] == 2:
        third = np.expand_dims(img[:, :, 0], axis=-1)
        img = np.concatenate([img, third], axis=2)

    # إذا أكثر من 3 bands، ناخذ أول 3
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    img = img.astype(np.float32)

    # Normalize to 0-1
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min + 1e-8)

    img = tf.image.resize(img, (IMG_SIZE, IMG_SIZE)).numpy()
    return img.astype(np.float32)


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

def make_dataset(image_paths, mask_paths, training=False):
    ds = tf.data.Dataset.from_tensor_slices((image_paths, mask_paths))
    ds = ds.map(load_sample, num_parallel_calls=tf.data.AUTOTUNE)

    if training:
        ds = ds.shuffle(200)

    ds = ds.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    return ds

train_ds = make_dataset(train_images, train_masks, training=True)
val_ds = make_dataset(val_images, val_masks, training=False)
test_ds = make_dataset(test_images, test_masks, training=False)

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
# DeepLabV3 مبسط
# =========================
base_model = tf.keras.applications.MobileNetV2(
    input_shape=(IMG_SIZE, IMG_SIZE, 3),
    include_top=False,
    weights="imagenet"
)

layer_names = [
    "block_1_expand_relu",   # 128x128
    "block_3_expand_relu",   # 64x64
    "block_6_expand_relu",   # 32x32
    "block_13_expand_relu",  # 16x16
    "out_relu",              # 8x8
]

layers_out = [base_model.get_layer(name).output for name in layer_names]
encoder = tf.keras.Model(inputs=base_model.input, outputs=layers_out)

encoder.trainable = False

inputs = tf.keras.Input(shape=(IMG_SIZE, IMG_SIZE, 3))
x1, x2, x3, x4, x5 = encoder(inputs)

# ASPP بسيط
b0 = tf.keras.layers.Conv2D(256, 1, padding="same", activation="relu")(x5)

b1 = tf.keras.layers.Conv2D(256, 3, padding="same", dilation_rate=6, activation="relu")(x5)
b2 = tf.keras.layers.Conv2D(256, 3, padding="same", dilation_rate=12, activation="relu")(x5)
b3 = tf.keras.layers.Conv2D(256, 3, padding="same", dilation_rate=18, activation="relu")(x5)

x = tf.keras.layers.Concatenate()([b0, b1, b2, b3])
x = tf.keras.layers.Conv2D(256, 1, padding="same", activation="relu")(x)


# Decoder
x = tf.keras.layers.UpSampling2D(size=(4, 4), interpolation="bilinear")(x)

# استخدمي x3 بدل x2 عشان المقاس يطابق
skip = tf.keras.layers.Conv2D(48, 1, padding="same", activation="relu")(x3)

x = tf.keras.layers.Concatenate()([x, skip])
x = tf.keras.layers.Conv2D(256, 3, padding="same", activation="relu")(x)
x = tf.keras.layers.Conv2D(256, 3, padding="same", activation="relu")(x)

x = tf.keras.layers.UpSampling2D(size=(8, 8), interpolation="bilinear")(x)
outputs = tf.keras.layers.Conv2D(1, 1, activation="sigmoid")(x)
model = tf.keras.Model(inputs, outputs)

model.compile(
    optimizer=tf.keras.optimizers.Adam(1e-4),
    loss="binary_crossentropy",
    metrics=["accuracy", dice_coef]
)

model.summary()

callbacks = [
    tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=5,
        restore_best_weights=True
    ),
    tf.keras.callbacks.ModelCheckpoint(
        "best_deeplab.keras",
        monitor="val_loss",
        save_best_only=True
    )
]

history = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=EPOCHS,
    callbacks=callbacks
)

print("\nEvaluating on test set...")
results = model.evaluate(test_ds)
print("Test results:", results)