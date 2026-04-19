from pathlib import Path
import numpy as np
import rasterio
from rasterio.enums import Resampling

IMAGES_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/Oil")
MASKS_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/Mask_oil")
OUTPUT_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/masks_fixed_v2")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

fixed_count = 0
skipped_count = 0
failed_count = 0

for image_path in sorted(IMAGES_DIR.iterdir()):
    if not image_path.is_file() or image_path.suffix.lower() not in [".tif", ".tiff"]:
        continue

    mask_path = MASKS_DIR / image_path.name
    if not mask_path.exists():
        print(f"[SKIP] No matching mask for: {image_path.name}")
        skipped_count += 1
        continue

    try:
        with rasterio.open(image_path) as img:
            img_profile = img.profile.copy()
            img_height = img.height
            img_width = img.width

        with rasterio.open(mask_path) as msk:
            # إذا نفس الأبعاد، خذ الماسك كما هو
            if msk.height == img_height and msk.width == img_width:
                mask = msk.read(1)
            else:
                # إذا الأبعاد مختلفة، سوي resize فقط بدون reproject
                mask = msk.read(
                    1,
                    out_shape=(img_height, img_width),
                    resampling=Resampling.nearest
                )

        # تحويل إلى ماسك ثنائي
        mask = (mask > 0).astype(np.uint8)

        out_profile = img_profile.copy()
        out_profile.update(
            driver="GTiff",
            dtype=rasterio.uint8,
            count=1,
            nodata=0
        )

        out_path = OUTPUT_DIR / image_path.name
        with rasterio.open(out_path, "w", **out_profile) as dst:
            dst.write(mask, 1)

        print(f"[OK] {image_path.name}")
        fixed_count += 1

    except Exception as e:
        print(f"[FAIL] {image_path.name}: {e}")
        failed_count += 1

print("\nDone.")
print(f"Fixed   : {fixed_count}")
print(f"Skipped : {skipped_count}")
print(f"Failed  : {failed_count}")