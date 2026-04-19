from pathlib import Path
import numpy as np
import rasterio

MASKS_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/masks_fixed_v2")

for i, mask_path in enumerate(sorted(MASKS_DIR.iterdir())):
    if i == 10:
        break
    if mask_path.suffix.lower() not in [".tif", ".tiff"]:
        continue

    with rasterio.open(mask_path) as src:
        mask = src.read(1)

    print(mask_path.name, "->", np.unique(mask), "nonzero =", np.count_nonzero(mask))