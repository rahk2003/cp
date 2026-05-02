from pathlib import Path
import cv2
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import rasterio
import csv
import pandas as pd

# =========================
# الإعدادات
# =========================
PRED_MASK_DIR = Path("/Users/rana/Desktop/tuwaiq/CP/predicted_masks/test")
OUTPUT_DIR    = Path("/Users/rana/Desktop/tuwaiq/CP/spill_reports_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ملف نتائج قرب الصور من اليابسة 
LAND_PROX_CSV = Path("/Users/rana/Documents/tuwaiq/CP/tif_land_buffer_results.csv")

PIXEL_SIZE_M = 0.5
MAX_SAMPLES  = None


# =========================
# تحميل نتائج القرب من اليابسة
# =========================
def load_land_proximity(csv_path: Path):
    if not csv_path.exists():
        print(f"Warning: land proximity CSV not found: {csv_path}")
        return {}

    df = pd.read_csv(csv_path)

    # نتأكد من الأعمدة
    required_cols = {"filename", "nearest_buffer_m", "nearest_buffer_km", "class"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in land proximity CSV: {missing}")

    proximity_map = {}
    for _, row in df.iterrows():
        proximity_map[str(row["filename"])] = {
            "distance_to_land_m": None if pd.isna(row["nearest_buffer_m"]) else float(row["nearest_buffer_m"]),
            "distance_to_land_km": None if pd.isna(row["nearest_buffer_km"]) else float(row["nearest_buffer_km"]),
            "land_proximity_class": str(row["class"]),
        }
    return proximity_map


LAND_PROXIMITY_MAP = load_land_proximity(LAND_PROX_CSV)


# =========================
# دالة قراءة الماسك
# =========================
def get_sorted_files(folder):
    return sorted([
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    ])


def read_mask(mask_path: Path):
    with rasterio.open(mask_path) as src:
        mask = src.read(1)
    mask = (mask > 0).astype(np.float32)
    return mask


# =========================
# Spill Analysis Module
# =========================
def analyze_spill(mask_2d: np.ndarray, pixel_size_m: float = 1.0):
    mask = (mask_2d > 0.5).astype(np.uint8)

    # Area
    area_px  = int(np.sum(mask))
    area_m2  = round(area_px * (pixel_size_m ** 2), 4)

    # Coverage
    total_px     = mask.shape[0] * mask.shape[1]
    coverage_pct = round(100.0 * area_px / total_px, 2) if total_px > 0 else 0.0

    # Centroid
    M = cv2.moments(mask)
    if M["m00"] > 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx, cy = 0, 0

    # Contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Perimeter
    perimeter_px = sum(cv2.arcLength(c, closed=True) for c in contours)
    perimeter_m  = round(perimeter_px * pixel_size_m, 4)

    # Orientation & Spread
    ys, xs = np.where(mask > 0)
    orientation_deg = None
    spread_ratio    = 0.0

    if len(xs) > 1:
        coords           = np.stack([xs - xs.mean(), ys - ys.mean()], axis=1)
        cov              = np.cov(coords.T)
        eigvals, eigvecs = np.linalg.eigh(cov)
        major_vec        = eigvecs[:, np.argmax(eigvals)]
        orientation_deg  = round(float(np.degrees(np.arctan2(major_vec[1], major_vec[0]))), 2)
        spread_ratio     = round(float(np.sqrt(eigvals.max() / (eigvals.min() + 1e-8))), 3)

    # Connected Components
    num_labels, labels_map, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    components = []
    for lbl in range(1, num_labels):
        x, y, w, h, comp_area = stats[lbl]
        comp_mask = (labels_map == lbl).astype(np.uint8)
        comp_contours, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        comp_perim = sum(cv2.arcLength(c, True) for c in comp_contours)
        components.append({
            "id":           lbl,
            "area_px":      int(comp_area),
            "area_m2":      round(comp_area * pixel_size_m ** 2, 4),
            "centroid":     (round(centroids[lbl][0], 1), round(centroids[lbl][1], 1)),
            "bbox_xywh":    (int(x), int(y), int(w), int(h)),
            "perimeter_px": round(comp_perim, 2),
        })
    components.sort(key=lambda c: c["area_px"], reverse=True)

    # Compactness
    compactness = round(area_px / (perimeter_px ** 2 + 1e-8), 6) if perimeter_px > 0 else 0.0

    # Intensity
    spill_pixels = mask_2d[mask_2d > 0.5]
    if len(spill_pixels) > 0:
        mean_intensity = round(float(np.mean(spill_pixels)), 4)
        max_intensity  = round(float(np.max(spill_pixels)), 4)
        std_intensity  = round(float(np.std(spill_pixels)), 4)
        density_score  = round(float(np.sum(spill_pixels) / (area_px + 1e-8)), 4)
    else:
        mean_intensity = max_intensity = std_intensity = density_score = 0.0

    return {
        "area_px":         area_px,
        "area_m2":         area_m2,
        "coverage_pct":    coverage_pct,
        "centroid":        (cx, cy),
        "perimeter_px":    round(perimeter_px, 2),
        "perimeter_m":     perimeter_m,
        "orientation_deg": orientation_deg,
        "spread_ratio":    spread_ratio,
        "num_components":  num_labels - 1,
        "components":      components,
        "compactness":     compactness,
        "mean_intensity":  mean_intensity,
        "max_intensity":   max_intensity,
        "std_intensity":   std_intensity,
        "density_score":   density_score,
        "contours":        contours,
    }


# =========================
# Land Proximity Helper
# =========================
def get_land_proximity(filename: str):
    return LAND_PROXIMITY_MAP.get(filename, {
        "distance_to_land_m": None,
        "distance_to_land_km": None,
        "land_proximity_class": "unknown"
    })


# =========================
# Risk Engine
# =========================
def compute_risk(features: dict) -> dict:
    score = 0.0
    factors = []

    cov = features["coverage_pct"]
    if cov >= 50:
        score += 40
        factors.append(f"coverage {cov}% → CRITICAL (>=50%)")
    elif cov >= 25:
        score += 30
        factors.append(f"coverage {cov}% → HIGH (25-50%)")
    elif cov >= 10:
        score += 20
        factors.append(f"coverage {cov}% → MEDIUM (10-25%)")
    elif cov >= 2:
        score += 10
        factors.append(f"coverage {cov}% → LOW (2-10%)")
    else:
        factors.append(f"coverage {cov}% → MINIMAL (<2%)")

    sr = features["spread_ratio"]
    if sr >= 10:
        score += 25
        factors.append(f"spread_ratio {sr} → CRITICAL (>=10, highly elongated)")
    elif sr >= 5:
        score += 18
        factors.append(f"spread_ratio {sr} → HIGH (5-10)")
    elif sr >= 2:
        score += 10
        factors.append(f"spread_ratio {sr} → MEDIUM (2-5)")
    else:
        score += 4
        factors.append(f"spread_ratio {sr} → LOW (<2, compact shape)")

    nc = features["num_components"]
    if nc >= 5:
        score += 20
        factors.append(f"components {nc} → CRITICAL (>=5, fragmented spill)")
    elif nc >= 3:
        score += 14
        factors.append(f"components {nc} → HIGH (3-4)")
    elif nc == 2:
        score += 8
        factors.append(f"components {nc} → MEDIUM (2)")
    elif nc == 1:
        score += 3
        factors.append(f"components {nc} → LOW (1, single blob)")
    else:
        factors.append(f"components {nc} → NONE (no spill detected)")

    ds = features["density_score"]
    if ds >= 0.95:
        score += 15
        factors.append(f"density {ds} → CRITICAL (>=0.95)")
    elif ds >= 0.85:
        score += 10
        factors.append(f"density {ds} → HIGH (0.85-0.95)")
    elif ds >= 0.70:
        score += 6
        factors.append(f"density {ds} → MEDIUM (0.70-0.85)")
    else:
        score += 2
        factors.append(f"density {ds} → LOW (<0.70)")

    score = round(min(score, 100), 1)

    if score >= 75:
        level = "CRITICAL"
    elif score >= 50:
        level = "HIGH"
    elif score >= 25:
        level = "MEDIUM"
    elif score > 0:
        level = "LOW"
    else:
        level = "NONE"

    return {
        "risk_score":   score,
        "risk_level":   level,
        "risk_factors": factors,
    }


# =========================
# CSV Export
# =========================
CSV_PATH = OUTPUT_DIR / "spill_analysis_results.csv"

CSV_FIELDS = [
    "filename",
    "area_px", "area_m2",
    "coverage_pct",
    "centroid_x", "centroid_y",
    "perimeter_px", "perimeter_m",
    "orientation_deg", "spread_ratio",
    "num_components",
    "compactness",
    "mean_intensity", "max_intensity", "std_intensity", "density_score",
    "distance_to_land_m", "distance_to_land_km", "land_proximity_class",
    "risk_score", "risk_level",
    "risk_factors",
]

def write_csv_row(writer, filename, features, land_info, risk):
    cx, cy = features["centroid"]
    writer.writerow({
        "filename":             filename,
        "area_px":              features["area_px"],
        "area_m2":              features["area_m2"],
        "coverage_pct":         features["coverage_pct"],
        "centroid_x":           cx,
        "centroid_y":           cy,
        "perimeter_px":         features["perimeter_px"],
        "perimeter_m":          features["perimeter_m"],
        "orientation_deg":      features["orientation_deg"],
        "spread_ratio":         features["spread_ratio"],
        "num_components":       features["num_components"],
        "compactness":          features["compactness"],
        "mean_intensity":       features["mean_intensity"],
        "max_intensity":        features["max_intensity"],
        "std_intensity":        features["std_intensity"],
        "density_score":        features["density_score"],
        "distance_to_land_m":   land_info["distance_to_land_m"],
        "distance_to_land_km":  land_info["distance_to_land_km"],
        "land_proximity_class": land_info["land_proximity_class"],
        "risk_score":           risk["risk_score"],
        "risk_level":           risk["risk_level"],
        "risk_factors":         " | ".join(risk["risk_factors"]),
    })


# =========================
# Visualization
# =========================
RISK_COLORS = {
    "CRITICAL": "#e24b4a",
    "HIGH":     "#ef9f27",
    "MEDIUM":   "#378add",
    "LOW":      "#1d9e75",
    "NONE":     "#888780",
}

def visualize_spill_analysis(mask_2d, features, land_info, risk, title="Predicted Spill Mask", save_path=None):
    base      = (mask_2d > 0.5).astype(np.uint8) * 255
    image_rgb = np.stack([base, base, base], axis=-1)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    risk_color = RISK_COLORS.get(risk["risk_level"], "#888780")
    fig.suptitle(
        f"{title}    |    Risk: {risk['risk_level']} ({risk['risk_score']}/100)",
        fontsize=13, fontweight="bold", color=risk_color
    )

    axes[0].imshow(mask_2d, cmap="gray")
    axes[0].set_title("Predicted mask")
    axes[0].axis("off")

    overlay = image_rgb.copy()
    overlay[mask_2d > 0.5] = [255, 80, 40]
    axes[1].imshow(overlay)

    cx, cy = features["centroid"]
    axes[1].plot(cx, cy, "y+", markersize=14, markeredgewidth=2)

    for comp in features["components"]:
        x, y, w, h = comp["bbox_xywh"]
        axes[1].add_patch(patches.Rectangle(
            (x, y), w, h,
            linewidth=1.2, edgecolor="cyan", facecolor="none"
        ))

    axes[1].set_title(f"Overlay | {features['num_components']} component(s)")
    axes[1].axis("off")

    axes[2].axis("off")
    lines = [
        f"Area:           {features['area_px']:,} px ({features['area_m2']} m²)",
        f"Coverage:       {features['coverage_pct']}%",
        f"Centroid:       ({cx}, {cy})",
        f"Perimeter:      {features['perimeter_px']:.1f} px",
        f"Orientation:    {features['orientation_deg']}°",
        f"Spread ratio:   {features['spread_ratio']}",
        f"Components:     {features['num_components']}",
        f"Compactness:    {features['compactness']:.6f}",
        f"Mean intensity: {features['mean_intensity']}",
        f"Max intensity:  {features['max_intensity']}",
        f"Std intensity:  {features['std_intensity']}",
        f"Density score:  {features['density_score']}",
        f"Distance land:  {land_info['distance_to_land_km']} km",
        f"Land class:     {land_info['land_proximity_class']}",
        f"──────────────────────────",
        f"Risk score:     {risk['risk_score']} / 100",
        f"Risk level:     {risk['risk_level']}",
    ]

    for i, line in enumerate(lines):
        color = risk_color if i >= 15 else "black"
        axes[2].text(
            0.05, 0.97 - i * 0.058, line,
            transform=axes[2].transAxes,
            fontsize=9.5, fontfamily="monospace",
            verticalalignment="top", color=color
        )

    axes[2].set_title("Extracted features + Land proximity + Risk")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {save_path.name}")
    plt.show()


# =========================
# تشغيل التحليل
# =========================
print("Reading predicted test masks...")
mask_files = get_sorted_files(PRED_MASK_DIR)

if MAX_SAMPLES is not None:
    mask_files = mask_files[:MAX_SAMPLES]

print(f"Total masks found: {len(mask_files)}")
print(f"CSV will be saved to: {CSV_PATH}\n")

with open(CSV_PATH, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDS)
    writer.writeheader()

    for idx, mask_path in enumerate(mask_files, start=1):
        print(f"{'='*60}")
        print(f"Sample {idx}: {mask_path.name}")
        print(f"{'='*60}")

        mask      = read_mask(mask_path)
        features  = analyze_spill(mask, pixel_size_m=PIXEL_SIZE_M)
        land_info = get_land_proximity(mask_path.name)
        risk      = compute_risk(features)

        for k, v in features.items():
            if k == "contours":
                print(f"  {'contours':<20}: {len(v)} contour(s)")
            elif k == "components":
                print(f"  {'components':<20}: {len(v)} total")
                for comp in v:
                    print(f"    {comp}")
            else:
                print(f"  {k:<20}: {v}")

        print(f"  {'distance_to_land_m':<20}: {land_info['distance_to_land_m']}")
        print(f"  {'distance_to_land_km':<20}: {land_info['distance_to_land_km']}")
        print(f"  {'land_proximity_class':<20}: {land_info['land_proximity_class']}")

        print(f"\n  Risk Score : {risk['risk_score']} / 100")
        print(f"  Risk Level : {risk['risk_level']}")
        print(f"  Risk Factors:")
        for factor in risk["risk_factors"]:
            print(f"    • {factor}")

        write_csv_row(writer, mask_path.name, features, land_info, risk)

        out_file = OUTPUT_DIR / f"{mask_path.stem}_report.png"
        visualize_spill_analysis(
            mask, features, land_info, risk,
            title=f"Spill Analysis - {mask_path.name}",
            save_path=out_file
        )

print(f"\nDone. CSV saved: {CSV_PATH}")