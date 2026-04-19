from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling


BASE_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/dataset_split")
OUT_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/preprocessed_dataset")

IMG_SIZE = 256

splits = ["train", "val", "test"]

for split in splits:
    (OUT_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "masks" / split).mkdir(parents=True, exist_ok=True)

def preprocess_image(src_path, dst_path, img_size=256):
    with rasterio.open(src_path) as src:
        img = src.read(
            out_shape=(src.count, img_size, img_size),
            resampling=Resampling.bilinear
        )

    # img shape = (bands, H, W)
    img = np.transpose(img, (1, 2, 0))

    # 1 قناة -> 3
    if img.shape[2] == 1:
        img = np.repeat(img, 3, axis=2)

    # 2 قنوات -> نخليها 3
    elif img.shape[2] == 2:
        third = np.expand_dims(img[:, :, 0], axis=-1)
        img = np.concatenate([img, third], axis=2)

    # أكثر من 3 -> ناخذ أول 3
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    img = img.astype(np.float32)

    # Normalize 0-255
    img_min = img.min()
    img_max = img.max()
    img = (img - img_min) / (img_max - img_min + 1e-8)
    img = (img * 255).astype(np.uint8)

    # حفظ كـ 3 bands tif
    profile = {
        "driver": "GTiff",
        "height": img_size,
        "width": img_size,
        "count": 3,
        "dtype": rasterio.uint8
    }

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(np.transpose(img, (2, 0, 1)))

def preprocess_mask(src_path, dst_path, img_size=256):
    with rasterio.open(src_path) as src:
        mask = src.read(
            1,
            out_shape=(img_size, img_size),
            resampling=Resampling.nearest
        )

    mask = (mask > 0).astype(np.uint8)

    profile = {
        "driver": "GTiff",
        "height": img_size,
        "width": img_size,
        "count": 1,
        "dtype": rasterio.uint8,
        "nodata": 0
    }

    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(mask, 1)

for split in splits:
    img_dir = BASE_DIR / "images" / split
    msk_dir = BASE_DIR / "masks" / split

    out_img_dir = OUT_DIR / "images" / split
    out_msk_dir = OUT_DIR / "masks" / split

    image_files = sorted([
        p for p in img_dir.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])

    for img_path in image_files:
        mask_path = msk_dir / img_path.name

        if not mask_path.exists():
            print(f"[SKIP] No matching mask for {img_path.name}")
            continue

        try:
            preprocess_image(img_path, out_img_dir / img_path.name, IMG_SIZE)
            preprocess_mask(mask_path, out_msk_dir / mask_path.name, IMG_SIZE)
            print(f"[OK] {split} -> {img_path.name}")
        except Exception as e:
            print(f"[FAIL] {split} -> {img_path.name}: {e}")

print("Done preprocessing dataset.")