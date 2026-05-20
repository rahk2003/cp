from pathlib import Path
import numpy as np
import rasterio

MASKS_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/Mask_oil")

empty_count = 0
non_empty_count = 0

for mask_path in sorted(MASKS_DIR.iterdir()):
    if not mask_path.is_file():
        continue
    if mask_path.suffix.lower() not in [".tif", ".tiff", ".png"]:
        continue

    with rasterio.open(mask_path) as src:
        mask = src.read(1)

    unique_vals = np.unique(mask)
    nonzero = np.count_nonzero(mask)

    print(mask_path.name, "->", unique_vals, "nonzero =", nonzero)

    if nonzero == 0:
        empty_count += 1
    else:
        non_empty_count += 1

print("\nEmpty masks    :", empty_count)
print("Non-empty masks:", non_empty_count)