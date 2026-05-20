from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd
import rasterio
import tensorflow as tf

from pyproj import CRS
from rasterio.transform import from_origin
from rasterio.warp import transform
from rasterio.windows import Window
from shapely.geometry import box
from sqlalchemy import create_engine, text


# ============================================================
# الإعدادات
# ============================================================
@dataclass
class Config:
    BASE_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP")

    # مودل DeepLabV3+
    MODEL_PATH: Path = Path("/Users/rana/Documents/tuwaiq/CP/best_deeplab_finetuned.keras")

    # مجلد الصور
    TEST_IMG_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/Oil")

    # إذا ما عندك masks حقيقية خليه مثل ما هو
    TEST_MSK_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/Oil/__no_masks_available__")

    # ملفات اليابسة والشعب المرجانية
    LAND_SHP: Path = Path("/Users/rana/Documents/tuwaiq/CP/ne_10m_land")
    CORAL_SHP: Path = Path("/Users/rana/Documents/tuwaiq/CP/Global_Coral_Reef_Points/Global_Coral_Reef_Points.shp")

    # مجلد المخرجات
    OUTPUT_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output")
    PRED_MASK_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/predicted_masks/test")
    VIS_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/visual_reports")

    IMG_SIZE: int = 256
    THRESHOLD: float = 0.5
    PIXEL_SIZE_M: float = 0.5

    # None يعني يأخذ كل الصور
    MAX_SAMPLES: Optional[int] = None

    TARGET_CRS: str = "EPSG:3857"
    BUFFER_STEPS: Tuple[int, ...] = (500, 1000, 2000, 5000, 10000, 20000)

    # PostgreSQL / PostGIS
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "oil_spills"

    ENABLE_RASTER_UPLOAD: bool = True
    RASTER_TABLE: str = "predicted_rasters"
    RASTER_SRID: int = 4326
    TILE_SIZE: str = "512x512"

    @property
    def DB_URI(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


CFG = Config()


# ============================================================
# تجهيز المجلدات
# ============================================================
def make_dirs() -> None:
    CFG.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CFG.PRED_MASK_DIR.mkdir(parents=True, exist_ok=True)
    CFG.VIS_DIR.mkdir(parents=True, exist_ok=True)


def get_sorted_files(folder: Path) -> List[Path]:
    exts = [".tif", ".tiff", ".png", ".jpg", ".jpeg"]

    if not folder.exists():
        return []

    return sorted([
        p for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in exts
    ])


def find_matching_file(filename: str, folder: Path) -> Optional[Path]:
    stem = Path(filename).stem
    possible_exts = [".tif", ".tiff", ".png", ".jpg", ".jpeg"]

    direct_candidates = [folder / filename]
    direct_candidates += [folder / f"{stem}{ext}" for ext in possible_exts]

    for c in direct_candidates:
        if c.exists():
            return c

    for p in folder.rglob("*"):
        if p.is_file() and p.stem == stem and p.suffix.lower() in possible_exts:
            return p

    return None


# ============================================================
# Dice metric عشان تحميل المودل
# ============================================================
def dice_coef(y_true, y_pred, smooth=1e-6):
    y_true = tf.reshape(y_true, [-1])
    y_pred = tf.reshape(y_pred, [-1])
    y_pred = tf.cast(y_pred > 0.5, tf.float32)

    intersection = tf.reduce_sum(y_true * y_pred)

    return (2.0 * intersection + smooth) / (
        tf.reduce_sum(y_true) + tf.reduce_sum(y_pred) + smooth
    )


# ============================================================
# قراءة الصور
# ============================================================
def read_image_array_for_model(path: Path, img_size: int) -> np.ndarray:
    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        with rasterio.open(path) as src:
            img = src.read()
        img = np.transpose(img, (1, 2, 0))
    else:
        img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)

        if img is None:
            raise ValueError(f"ما قدرت أقرأ الصورة: {path}")

        if img.ndim == 3:
            if img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
            else:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img = np.expand_dims(img, axis=-1)

    if img.ndim == 2:
        img = np.expand_dims(img, axis=-1)

    if img.shape[2] == 1:
        img = np.repeat(img, 3, axis=2)
    elif img.shape[2] == 2:
        third = np.expand_dims(img[:, :, 0], axis=-1)
        img = np.concatenate([img, third], axis=2)
    elif img.shape[2] > 3:
        img = img[:, :, :3]

    img = img.astype(np.float32)

    img_min = float(np.min(img))
    img_max = float(np.max(img))

    img = (img - img_min) / (img_max - img_min + 1e-8)
    img = tf.image.resize(img, (img_size, img_size)).numpy()

    return img.astype(np.float32)


def read_mask_array_for_eval(path: Path, img_size: int) -> np.ndarray:
    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        with rasterio.open(path) as src:
            mask = src.read(1)
    else:
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)

        if mask is None:
            raise ValueError(f"ما قدرت أقرأ الماسك: {path}")

    mask = (mask > 0).astype(np.float32)
    mask = np.expand_dims(mask, axis=-1)
    mask = tf.image.resize(mask, (img_size, img_size), method="nearest").numpy()

    return mask.astype(np.float32)


def read_original_for_plot(img_path: Path, target_h: int, target_w: int) -> Optional[np.ndarray]:
    try:
        suffix = img_path.suffix.lower()

        if suffix in [".tif", ".tiff"]:
            with rasterio.open(img_path) as src:
                img = src.read()
            img = np.transpose(img, (1, 2, 0))
        else:
            img = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)

            if img is None:
                return None

            if img.ndim == 3:
                if img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                else:
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:
                img = np.expand_dims(img, axis=-1)

        if img.ndim == 2:
            img = np.expand_dims(img, axis=-1)

        if img.shape[2] == 1:
            img = np.repeat(img, 3, axis=2)
        elif img.shape[2] == 2:
            third = np.expand_dims(img[:, :, 0], axis=-1)
            img = np.concatenate([img, third], axis=2)
        elif img.shape[2] > 3:
            img = img[:, :, :3]

        img = img.astype(np.float32)
        img_min = float(np.min(img))
        img_max = float(np.max(img))
        img = (img - img_min) / (img_max - img_min + 1e-8)

        img = tf.image.resize(img, (target_h, target_w)).numpy()
        return img.astype(np.float32)

    except Exception as e:
        print(f"فشل قراءة الصورة للعرض: {img_path.name} | {e}")
        return None


# ============================================================
# اختبار المودل وحفظ predicted masks
# ============================================================
def run_model_test_and_predict() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("1) تحميل مودل DeepLab والتنبؤ على الصور")
    print("=" * 70)

    images = get_sorted_files(CFG.TEST_IMG_DIR)

    try:
        out_dir_resolved = CFG.OUTPUT_DIR.resolve()
        images = [p for p in images if out_dir_resolved not in p.resolve().parents]
    except Exception:
        pass

    if CFG.MAX_SAMPLES is not None:
        images = images[:CFG.MAX_SAMPLES]

    if not images:
        raise FileNotFoundError(f"ما لقيت صور في: {CFG.TEST_IMG_DIR}")

    masks_available = CFG.TEST_MSK_DIR.exists() and len(get_sorted_files(CFG.TEST_MSK_DIR)) > 0

    print(f"عدد الصور: {len(images)}")
    print(f"يوجد ground truth masks؟ {masks_available}")
    print(f"مسار المودل: {CFG.MODEL_PATH}")

    model = tf.keras.models.load_model(
        CFG.MODEL_PATH,
        custom_objects={"dice_coef": dice_coef}
    )

    print("تم تحميل المودل")

    cm_total = np.zeros((2, 2), dtype=np.int64)
    dice_scores = []
    pred_records = []
    no_crs_count = 0

    for idx, img_path in enumerate(images, start=1):
        print(f"[{idx}/{len(images)}] Predict: {img_path.name}")

        img_model = read_image_array_for_model(img_path, CFG.IMG_SIZE)
        pred = model.predict(np.expand_dims(img_model, axis=0), verbose=0)[0]

        pred_prob = np.squeeze(pred).astype(np.float32)
        pred_bin_small = (pred_prob > CFG.THRESHOLD).astype(np.uint8)

        suffix = img_path.suffix.lower()

        if suffix in [".tif", ".tiff"]:
            with rasterio.open(img_path) as src:
                profile = src.profile.copy()
                out_h, out_w = src.height, src.width
                transform_src = src.transform
                crs_src = src.crs
        else:
            original = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)

            if original is None:
                print(f"تخطي الصورة لأنها غير قابلة للقراءة: {img_path}")
                continue

            out_h, out_w = original.shape[:2]
            transform_src = from_origin(0, 0, 1, 1)
            crs_src = None

            profile = {
                "driver": "GTiff",
                "height": out_h,
                "width": out_w,
                "count": 1,
                "dtype": "uint8",
                "transform": transform_src,
                "crs": crs_src,
            }

        if crs_src is None:
            no_crs_count += 1

        pred_bin = cv2.resize(
            pred_bin_small,
            (out_w, out_h),
            interpolation=cv2.INTER_NEAREST,
        ).astype(np.uint8)

        out_path = CFG.PRED_MASK_DIR / f"{img_path.stem}.tif"

        profile.update(
            driver="GTiff",
            count=1,
            dtype="uint8",
            height=out_h,
            width=out_w,
            nodata=0,
            compress="lzw",
        )

        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(pred_bin, 1)

        pred_records.append({
            "filename": out_path.name,
            "source_image": img_path.name,
            "source_image_path": str(img_path),
            "predicted_mask_path": str(out_path),
            "has_crs": crs_src is not None,
            "crs": str(crs_src) if crs_src else None,
            "transform": str(transform_src),
        })

        if masks_available:
            mask_path = find_matching_file(img_path.name, CFG.TEST_MSK_DIR)

            if mask_path is not None:
                true_small = read_mask_array_for_eval(mask_path, CFG.IMG_SIZE).squeeze().astype(np.uint8)
                pred_small = pred_bin_small.astype(np.uint8)

                y_true = true_small.ravel()
                y_pred = pred_small.ravel()

                cm = pd.crosstab(
                    pd.Series(y_true, name="true"),
                    pd.Series(y_pred, name="pred"),
                    dropna=False,
                ).reindex(index=[0, 1], columns=[0, 1], fill_value=0).values

                cm_total += cm

                intersection = np.sum(true_small * pred_small)
                dice = (2 * intersection + 1e-6) / (
                    np.sum(true_small) + np.sum(pred_small) + 1e-6
                )
                dice_scores.append(float(dice))

    metrics = {
        "num_images": len(images),
        "num_predicted_masks": len(pred_records),
        "num_images_without_crs": no_crs_count,
        "threshold": CFG.THRESHOLD,
        "mean_dice": round(float(np.mean(dice_scores)), 6) if dice_scores else None,
        "confusion_matrix": cm_total.tolist() if masks_available else None,
        "source_dir": str(CFG.TEST_IMG_DIR),
    }

    with open(CFG.OUTPUT_DIR / "model_test_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    pd.DataFrame(pred_records).to_csv(
        CFG.OUTPUT_DIR / "prediction_files.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if masks_available:
        fig, ax = plt.subplots(figsize=(5, 4))
        im = ax.imshow(cm_total)
        ax.set_title("Pixel-wise Confusion Matrix")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("True")
        ax.set_xticks([0, 1], ["Background", "Oil Spill"])
        ax.set_yticks([0, 1], ["Background", "Oil Spill"])

        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(cm_total[i, j]), ha="center", va="center")

        fig.colorbar(im, ax=ax)
        plt.tight_layout()
        plt.savefig(CFG.OUTPUT_DIR / "confusion_matrix.png", dpi=150)
        plt.close()

    print(f"تم حفظ predicted masks في: {CFG.PRED_MASK_DIR}")
    print(f"Metrics: {metrics}")

    return metrics


# ============================================================
# معلومات GeoTIFF
# ============================================================
def get_file_datetime(path: Path) -> Tuple[str, str]:
    stat = os.stat(path)
    dt = datetime.fromtimestamp(stat.st_mtime)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")


def get_corner_coords(src) -> Optional[Dict[str, Tuple[float, float]]]:
    if src.crs is None:
        return None

    left, bottom, right, top = src.bounds

    xs = [left, right, right, left, (left + right) / 2]
    ys = [top, top, bottom, bottom, (top + bottom) / 2]

    lon, lat = transform(src.crs, CRS.from_epsg(4326), xs, ys)

    return {
        "upper_left": (lon[0], lat[0]),
        "upper_right": (lon[1], lat[1]),
        "lower_right": (lon[2], lat[2]),
        "lower_left": (lon[3], lat[3]),
        "center": (lon[4], lat[4]),
    }


def extract_tiff_info(path: Path) -> Dict[str, Any]:
    info = {
        "file": path.name,
        "source_path": str(path),
        "date": None,
        "time": None,
        "crs": None,
        "width": None,
        "height": None,
        "pixel_size_x": None,
        "pixel_size_y": None,
        "bbox_left": None,
        "bbox_bottom": None,
        "bbox_right": None,
        "bbox_top": None,
        "center_lon": None,
        "center_lat": None,
        "upper_left_lon": None,
        "upper_left_lat": None,
        "upper_right_lon": None,
        "upper_right_lat": None,
        "lower_right_lon": None,
        "lower_right_lat": None,
        "lower_left_lon": None,
        "lower_left_lat": None,
        "error": None,
    }

    try:
        info["date"], info["time"] = get_file_datetime(path)
    except Exception as e:
        info["error"] = f"datetime error: {e}"

    try:
        suffix = path.suffix.lower()

        if suffix not in [".tif", ".tiff"]:
            info["error"] = "not geotiff"
            return info

        with rasterio.open(path) as src:
            info["crs"] = str(src.crs) if src.crs else None
            info["width"] = src.width
            info["height"] = src.height

            try:
                info["pixel_size_x"] = float(abs(src.transform.a))
                info["pixel_size_y"] = float(abs(src.transform.e))
            except Exception:
                pass

            try:
                b = src.bounds
                info["bbox_left"] = float(b.left)
                info["bbox_bottom"] = float(b.bottom)
                info["bbox_right"] = float(b.right)
                info["bbox_top"] = float(b.top)
            except Exception:
                pass

            corners = get_corner_coords(src)

            if corners:
                info["center_lon"], info["center_lat"] = corners["center"]
                info["upper_left_lon"], info["upper_left_lat"] = corners["upper_left"]
                info["upper_right_lon"], info["upper_right_lat"] = corners["upper_right"]
                info["lower_right_lon"], info["lower_right_lat"] = corners["lower_right"]
                info["lower_left_lon"], info["lower_left_lat"] = corners["lower_left"]

    except Exception as e:
        info["error"] = (str(info["error"]) + " | " if info["error"] else "") + str(e)

    return info


# ============================================================
# القرب من اليابسة والشعب المرجانية
# ============================================================
def load_union_layer(
    path: Path,
    target_crs: str,
    default_crs: Optional[str] = None,
    name: str = "layer",
):
    if not path.exists():
        raise FileNotFoundError(f"ما لقيت ملف {name}: {path}")

    gdf = gpd.read_file(path)

    if gdf.empty:
        raise ValueError(f"ملف {name} فارغ: {path}")

    if gdf.crs is None:
        if default_crs is None:
            raise ValueError(f"ملف {name} لا يحتوي على CRS")
        gdf = gdf.set_crs(default_crs)

    gdf = gdf.to_crs(target_crs)

    union = gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union

    return union


def get_spill_bbox_geometry(mask_path: Path, target_crs: str):
    with rasterio.open(mask_path) as src:
        if src.crs is None:
            return None, "no_crs"

        mask = src.read(1)
        rows, cols = np.where(mask > 0)

        if len(rows) > 0:
            row_min, row_max = int(rows.min()), int(rows.max())
            col_min, col_max = int(cols.min()), int(cols.max())

            window = Window(
                col_off=col_min,
                row_off=row_min,
                width=(col_max - col_min + 1),
                height=(row_max - row_min + 1),
            )

            left, bottom, right, top = src.window_bounds(window)
            geom_type = "spill_bbox"
        else:
            b = src.bounds
            left, bottom, right, top = b.left, b.bottom, b.right, b.top
            geom_type = "image_bbox_no_spill"

        img_poly = box(left, bottom, right, top)

        gdf = gpd.GeoDataFrame(
            {"filename": [mask_path.name]},
            geometry=[img_poly],
            crs=src.crs,
        )

        gdf = gdf.to_crs(target_crs)

        return gdf.geometry.iloc[0], geom_type


def proximity_to_union(mask_path: Path, union_geom, mode: str) -> Dict[str, Any]:
    geom, geom_type = get_spill_bbox_geometry(mask_path, CFG.TARGET_CRS)

    if geom is None:
        if mode == "land":
            return {
                "distance_to_land_m": None,
                "distance_to_land_km": None,
                "land_proximity_class": "no_crs",
                "proximity_geom_type": geom_type,
            }

        return {
            "distance_to_coral_m": None,
            "distance_to_coral_km": None,
            "coral_proximity_class": "no_crs",
            "proximity_geom_type": geom_type,
        }

    if geom.intersects(union_geom):
        hit = 0
    else:
        hit = None

        for d in CFG.BUFFER_STEPS:
            if geom.buffer(d).intersects(union_geom):
                hit = d
                break

        if hit is None:
            hit = max(CFG.BUFFER_STEPS)

    km = hit / 1000 if hit is not None else None

    if mode == "land":
        if hit == 0:
            cls = "Touches land"
        elif hit <= 1000:
            cls = "Very close"
        elif hit <= 5000:
            cls = "Close"
        elif hit < max(CFG.BUFFER_STEPS):
            cls = "Far"
        else:
            cls = "Very far (>20 km)"

        return {
            "distance_to_land_m": hit,
            "distance_to_land_km": km,
            "land_proximity_class": cls,
            "proximity_geom_type": geom_type,
        }

    if hit == 0:
        cls = "Touches coral reef"
    elif hit <= 1000:
        cls = "Very close to coral"
    elif hit <= 5000:
        cls = "Close to coral"
    elif hit < max(CFG.BUFFER_STEPS):
        cls = "Far from coral"
    else:
        cls = "Very far from coral (>20 km)"

    return {
        "distance_to_coral_m": hit,
        "distance_to_coral_km": km,
        "coral_proximity_class": cls,
        "proximity_geom_type": geom_type,
    }


# ============================================================
# تحليل خصائص التسرب
# ============================================================
def read_mask(mask_path: Path) -> np.ndarray:
    with rasterio.open(mask_path) as src:
        mask = src.read(1)

    return (mask > 0).astype(np.float32)


def analyze_spill(mask_2d: np.ndarray, pixel_size_m: float) -> Dict[str, Any]:
    mask = (mask_2d > 0.5).astype(np.uint8)

    area_px = int(np.sum(mask))
    area_m2 = round(area_px * (pixel_size_m ** 2), 4)

    total_px = mask.shape[0] * mask.shape[1]
    coverage_pct = round(100.0 * area_px / total_px, 2) if total_px > 0 else 0.0

    M = cv2.moments(mask)

    if M["m00"] > 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        cx, cy = 0, 0

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    perimeter_px = sum(cv2.arcLength(c, closed=True) for c in contours)
    perimeter_m = round(perimeter_px * pixel_size_m, 4)

    ys, xs = np.where(mask > 0)

    orientation_deg = None
    spread_ratio = 0.0

    if len(xs) > 1:
        coords = np.stack([xs - xs.mean(), ys - ys.mean()], axis=1)
        cov = np.cov(coords.T)
        eigvals, eigvecs = np.linalg.eigh(cov)

        major_vec = eigvecs[:, np.argmax(eigvals)]

        orientation_deg = round(
            float(np.degrees(np.arctan2(major_vec[1], major_vec[0]))),
            2,
        )

        spread_ratio = round(
            float(np.sqrt(eigvals.max() / (eigvals.min() + 1e-8))),
            3,
        )

    num_labels, labels_map, stats, centroids = cv2.connectedComponentsWithStats(
        mask,
        connectivity=8,
    )

    components = []

    for lbl in range(1, num_labels):
        x, y, w, h, comp_area = stats[lbl]

        comp_mask = (labels_map == lbl).astype(np.uint8)
        comp_contours, _ = cv2.findContours(comp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        comp_perim = sum(cv2.arcLength(c, True) for c in comp_contours)

        components.append({
            "id": int(lbl),
            "area_px": int(comp_area),
            "area_m2": round(float(comp_area) * pixel_size_m ** 2, 4),
            "centroid": (
                round(float(centroids[lbl][0]), 1),
                round(float(centroids[lbl][1]), 1),
            ),
            "bbox_xywh": (int(x), int(y), int(w), int(h)),
            "perimeter_px": round(float(comp_perim), 2),
        })

    components.sort(key=lambda c: c["area_px"], reverse=True)

    compactness = round(area_px / (perimeter_px ** 2 + 1e-8), 6) if perimeter_px > 0 else 0.0

    spill_pixels = mask_2d[mask_2d > 0.5]

    if len(spill_pixels) > 0:
        mean_intensity = round(float(np.mean(spill_pixels)), 4)
        max_intensity = round(float(np.max(spill_pixels)), 4)
        std_intensity = round(float(np.std(spill_pixels)), 4)
        density_score = round(float(np.sum(spill_pixels) / (area_px + 1e-8)), 4)
    else:
        mean_intensity = 0.0
        max_intensity = 0.0
        std_intensity = 0.0
        density_score = 0.0

    return {
        "area_px": area_px,
        "area_m2": area_m2,
        "coverage_pct": coverage_pct,
        "centroid_x": cx,
        "centroid_y": cy,
        "perimeter_px": round(float(perimeter_px), 2),
        "perimeter_m": perimeter_m,
        "orientation_deg": orientation_deg,
        "spread_ratio": spread_ratio,
        "num_components": int(num_labels - 1),
        "components_json": json.dumps(components, ensure_ascii=False),
        "compactness": compactness,
        "mean_intensity": mean_intensity,
        "max_intensity": max_intensity,
        "std_intensity": std_intensity,
        "density_score": density_score,
        "contours_count": len(contours),
        "components": components,
        "contours": contours,
    }


def pixel_centroid_to_lonlat(mask_path: Path, cx: int, cy: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        with rasterio.open(mask_path) as src:
            if src.crs is None:
                return None, None

            x_world, y_world = src.transform * (cx, cy)

            lon, lat = transform(
                src.crs,
                CRS.from_epsg(4326),
                [x_world],
                [y_world],
            )

            return float(lon[0]), float(lat[0])

    except Exception:
        return None, None


# ============================================================
# Risk Engine
# ============================================================
def compute_risk(
    features: Dict[str, Any],
    land_info: Dict[str, Any],
    coral_info: Dict[str, Any],
) -> Dict[str, Any]:
    score = 0.0
    factors = []

    cov = features["coverage_pct"]

    if cov >= 50:
        score += 40
        factors.append(f"coverage {cov}% → CRITICAL")
    elif cov >= 25:
        score += 30
        factors.append(f"coverage {cov}% → HIGH")
    elif cov >= 10:
        score += 20
        factors.append(f"coverage {cov}% → MEDIUM")
    elif cov >= 2:
        score += 10
        factors.append(f"coverage {cov}% → LOW")
    else:
        factors.append(f"coverage {cov}% → MINIMAL")

    sr = features["spread_ratio"]

    if sr >= 10:
        score += 25
        factors.append(f"spread_ratio {sr} → CRITICAL")
    elif sr >= 5:
        score += 18
        factors.append(f"spread_ratio {sr} → HIGH")
    elif sr >= 2:
        score += 10
        factors.append(f"spread_ratio {sr} → MEDIUM")
    else:
        score += 4
        factors.append(f"spread_ratio {sr} → LOW")

    nc = features["num_components"]

    if nc >= 5:
        score += 20
        factors.append(f"components {nc} → CRITICAL")
    elif nc >= 3:
        score += 14
        factors.append(f"components {nc} → HIGH")
    elif nc == 2:
        score += 8
        factors.append(f"components {nc} → MEDIUM")
    elif nc == 1:
        score += 3
        factors.append(f"components {nc} → LOW")
    else:
        factors.append(f"components {nc} → NONE")

    ds = features["density_score"]

    if ds >= 0.95:
        score += 15
        factors.append(f"density {ds} → CRITICAL")
    elif ds >= 0.85:
        score += 10
        factors.append(f"density {ds} → HIGH")
    elif ds >= 0.70:
        score += 6
        factors.append(f"density {ds} → MEDIUM")
    else:
        score += 2
        factors.append(f"density {ds} → LOW")

    d_land = land_info.get("distance_to_land_km")

    if d_land is not None:
        if d_land == 0:
            score += 20
            factors.append("land 0 km → CRITICAL")
        elif d_land <= 1:
            score += 15
            factors.append(f"land {d_land} km → HIGH")
        elif d_land <= 5:
            score += 10
            factors.append(f"land {d_land} km → MEDIUM")
        elif d_land <= 20:
            score += 5
            factors.append(f"land {d_land} km → LOW")
        else:
            factors.append(f"land {d_land} km → VERY FAR")
    else:
        factors.append("land distance unknown")

    d_coral = coral_info.get("distance_to_coral_km")

    if d_coral is not None:
        if d_coral == 0:
            score += 25
            factors.append("coral 0 km → CRITICAL")
        elif d_coral <= 1:
            score += 22
            factors.append(f"coral {d_coral} km → CRITICAL")
        elif d_coral <= 5:
            score += 16
            factors.append(f"coral {d_coral} km → HIGH")
        elif d_coral <= 10:
            score += 10
            factors.append(f"coral {d_coral} km → MEDIUM")
        elif d_coral <= 20:
            score += 5
            factors.append(f"coral {d_coral} km → LOW")
        else:
            factors.append(f"coral {d_coral} km → VERY FAR")
    else:
        factors.append("coral distance unknown")

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
        "risk_score": score,
        "risk_level": level,
        "risk_factors": " | ".join(factors),
    }


# ============================================================
# Visualization
# ============================================================
RISK_COLORS = {
    "CRITICAL": "#e24b4a",
    "HIGH": "#ef9f27",
    "MEDIUM": "#378add",
    "LOW": "#1d9e75",
    "NONE": "#888780",
}


def visualize_sample(
    mask_path: Path,
    original_path: Optional[Path],
    row: Dict[str, Any],
) -> Optional[Path]:
    try:
        mask = read_mask(mask_path)
        H, W = mask.shape

        original_image = None

        if original_path is not None:
            original_image = read_original_for_plot(original_path, target_h=H, target_w=W)

        fig, axes = plt.subplots(1, 4, figsize=(20, 5))

        risk_level = row.get("risk_level", "NONE")
        risk_color = RISK_COLORS.get(risk_level, "#888780")

        fig.suptitle(
            f"Spill Analysis - {mask_path.name} | Risk: {risk_level} ({row.get('risk_score')}/100)",
            fontsize=13,
            fontweight="bold",
            color=risk_color,
        )

        if original_image is None:
            axes[0].text(0.5, 0.5, "Original image\nnot found", ha="center", va="center")
        else:
            axes[0].imshow(original_image)

        axes[0].set_title("Original image")
        axes[0].axis("off")

        axes[1].imshow(mask, cmap="gray")
        axes[1].set_title("Predicted mask")
        axes[1].axis("off")

        if original_image is None:
            overlay_bg = np.stack([mask, mask, mask], axis=-1)
            axes[2].imshow(overlay_bg)
        else:
            axes[2].imshow(original_image)
            spill_overlay = np.zeros((H, W, 4), dtype=np.float32)
            spill_overlay[mask > 0.5] = [1.0, 0.25, 0.1, 0.55]
            axes[2].imshow(spill_overlay)

        axes[2].plot(
            row["centroid_x"],
            row["centroid_y"],
            "y+",
            markersize=14,
            markeredgewidth=2,
        )

        try:
            components = json.loads(row["components_json"])

            for comp in components:
                x, y, w, h = comp["bbox_xywh"]
                axes[2].add_patch(
                    patches.Rectangle(
                        (x, y),
                        w,
                        h,
                        linewidth=1.2,
                        edgecolor="cyan",
                        facecolor="none",
                    )
                )
        except Exception:
            pass

        axes[2].set_title("Overlay + components")
        axes[2].axis("off")

        axes[3].axis("off")

        lines = [
            f"Area:           {row['area_px']:,} px ({row['area_m2']} m²)",
            f"Coverage:       {row['coverage_pct']}%",
            f"Centroid px:    ({row['centroid_x']}, {row['centroid_y']})",
            f"Centroid lonlat:({row.get('spill_centroid_lon')}, {row.get('spill_centroid_lat')})",
            f"Perimeter:      {row['perimeter_px']} px ({row['perimeter_m']} m)",
            f"Orientation:    {row['orientation_deg']}°",
            f"Spread ratio:   {row['spread_ratio']}",
            f"Components:     {row['num_components']}",
            f"Compactness:    {row['compactness']}",
            f"Density score:  {row['density_score']}",
            f"CRS:            {row.get('crs')}",
            f"Image center:   ({row.get('center_lon')}, {row.get('center_lat')})",
            f"Land distance:  {row['distance_to_land_km']} km",
            f"Land class:     {row['land_proximity_class']}",
            f"Coral distance: {row['distance_to_coral_km']} km",
            f"Coral class:    {row['coral_proximity_class']}",
            "--------------------",
            f"Risk score:     {row['risk_score']} / 100",
            f"Risk level:     {row['risk_level']}",
        ]

        for i, line in enumerate(lines):
            color = risk_color if i >= len(lines) - 2 else "black"

            axes[3].text(
                0.02,
                0.98 - i * 0.052,
                line,
                transform=axes[3].transAxes,
                fontsize=8,
                fontfamily="monospace",
                va="top",
                color=color,
            )

        axes[3].set_title("Extracted features + risk")

        plt.tight_layout()

        out_path = CFG.VIS_DIR / f"{mask_path.stem}_report.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()

        return out_path

    except Exception as e:
        print(f"فشل إنشاء visual report للصورة {mask_path.name}: {e}")
        return None


# ============================================================
# التحليل الكامل
# ============================================================
def analyze_predictions() -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("\n" + "=" * 70)
    print("2) تحليل التسرب + القرب من اليابسة والشعب المرجانية")
    print("=" * 70)

    mask_files = get_sorted_files(CFG.PRED_MASK_DIR)

    if CFG.MAX_SAMPLES is not None:
        mask_files = mask_files[:CFG.MAX_SAMPLES]

    if not mask_files:
        raise FileNotFoundError(f"ما لقيت predicted masks في: {CFG.PRED_MASK_DIR}")

    print("تحميل طبقة اليابسة...")
    land_union = load_union_layer(
        CFG.LAND_SHP,
        CFG.TARGET_CRS,
        default_crs=None,
        name="land",
    )

    print("تحميل طبقة الشعب المرجانية...")
    coral_union = load_union_layer(
        CFG.CORAL_SHP,
        CFG.TARGET_CRS,
        default_crs="EPSG:4326",
        name="coral",
    )

    analysis_rows = []
    info_rows = []

    for idx, mask_path in enumerate(mask_files, start=1):
        print(f"[{idx}/{len(mask_files)}] Analyze: {mask_path.name}")

        mask = read_mask(mask_path)
        features = analyze_spill(mask, CFG.PIXEL_SIZE_M)

        land_info = proximity_to_union(mask_path, land_union, mode="land")
        coral_info = proximity_to_union(mask_path, coral_union, mode="coral")

        risk = compute_risk(features, land_info, coral_info)

        original_path = find_matching_file(mask_path.name, CFG.TEST_IMG_DIR)

        if original_path is not None:
            tiff_info = extract_tiff_info(original_path)
        else:
            tiff_info = extract_tiff_info(mask_path)
            old_error = tiff_info.get("error") or ""
            tiff_info["error"] = old_error + " | original not found"

        spill_lon, spill_lat = pixel_centroid_to_lonlat(
            mask_path,
            features["centroid_x"],
            features["centroid_y"],
        )

        row = {
            "filename": mask_path.name,
            "source_image": original_path.name if original_path else mask_path.name,
            "source_image_path": str(original_path) if original_path else None,
            "predicted_mask_path": str(mask_path),

            **{k: v for k, v in features.items() if k not in ["components", "contours"]},

            "spill_centroid_lon": spill_lon,
            "spill_centroid_lat": spill_lat,

            "distance_to_land_m": land_info.get("distance_to_land_m"),
            "distance_to_land_km": land_info.get("distance_to_land_km"),
            "land_proximity_class": land_info.get("land_proximity_class"),

            "distance_to_coral_m": coral_info.get("distance_to_coral_m"),
            "distance_to_coral_km": coral_info.get("distance_to_coral_km"),
            "coral_proximity_class": coral_info.get("coral_proximity_class"),

            "proximity_geom_type": land_info.get("proximity_geom_type"),

            **risk,

            "date": tiff_info.get("date"),
            "time": tiff_info.get("time"),
            "crs": tiff_info.get("crs"),
            "width": tiff_info.get("width"),
            "height": tiff_info.get("height"),
            "pixel_size_x": tiff_info.get("pixel_size_x"),
            "pixel_size_y": tiff_info.get("pixel_size_y"),
            "bbox_left": tiff_info.get("bbox_left"),
            "bbox_bottom": tiff_info.get("bbox_bottom"),
            "bbox_right": tiff_info.get("bbox_right"),
            "bbox_top": tiff_info.get("bbox_top"),
            "center_lon": tiff_info.get("center_lon"),
            "center_lat": tiff_info.get("center_lat"),
            "upper_left_lon": tiff_info.get("upper_left_lon"),
            "upper_left_lat": tiff_info.get("upper_left_lat"),
            "upper_right_lon": tiff_info.get("upper_right_lon"),
            "upper_right_lat": tiff_info.get("upper_right_lat"),
            "lower_right_lon": tiff_info.get("lower_right_lon"),
            "lower_right_lat": tiff_info.get("lower_right_lat"),
            "lower_left_lon": tiff_info.get("lower_left_lon"),
            "lower_left_lat": tiff_info.get("lower_left_lat"),

            "analysis_created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        vis_path = visualize_sample(mask_path, original_path, row)
        row["visual_report_path"] = str(vis_path) if vis_path else None

        analysis_rows.append(row)
        info_rows.append(tiff_info)

    analysis_df = pd.DataFrame(analysis_rows)
    info_df = pd.DataFrame(info_rows)

    analysis_df.to_csv(
        CFG.OUTPUT_DIR / "spill_analysis_results_full.csv",
        index=False,
        encoding="utf-8-sig",
    )

    info_df.to_csv(
        CFG.OUTPUT_DIR / "spill_info.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"تم حفظ التحليل: {CFG.OUTPUT_DIR / 'spill_analysis_results_full.csv'}")
    print(f"تم حفظ الإحداثيات: {CFG.OUTPUT_DIR / 'spill_info.csv'}")

    return analysis_df, info_df


# ============================================================
# حفظ النتائج في قاعدة البيانات
# ============================================================
def save_to_database(
    analysis_df: pd.DataFrame,
    info_df: pd.DataFrame,
    metrics: Dict[str, Any],
) -> None:
    print("\n" + "=" * 70)
    print("3) حفظ النتائج في PostgreSQL/PostGIS")
    print("=" * 70)

    engine = create_engine(CFG.DB_URI)

    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            print("PostGIS extension جاهز")
        except Exception as e:
            print(f"PostGIS extension warning: {e}")

    info_df.to_sql(
        "spill_info",
        engine,
        if_exists="replace",
        index=False,
    )

    analysis_df.to_sql(
        "spill_analysis_results",
        engine,
        if_exists="replace",
        index=False,
    )

    metrics_df = pd.DataFrame([{
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_json": json.dumps(metrics, ensure_ascii=False),
    }])

    metrics_df.to_sql(
        "model_test_metrics",
        engine,
        if_exists="replace",
        index=False,
    )

    print("تم حفظ الجداول:")
    print("- spill_info")
    print("- spill_analysis_results")
    print("- model_test_metrics")

    if CFG.ENABLE_RASTER_UPLOAD:
        upload_predicted_masks_to_postgis()


# ============================================================
# رفع predicted masks إلى PostGIS Raster
# ============================================================
def run_psql(sql: str, env: Dict[str, str], quiet: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        "psql",
        "-h", CFG.DB_HOST,
        "-p", str(CFG.DB_PORT),
        "-U", CFG.DB_USER,
        "-d", CFG.DB_NAME,
        "-c", sql,
    ]

    if quiet:
        cmd.append("-q")

    return subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
    )


def upload_predicted_masks_to_postgis() -> None:
    print("\n" + "=" * 70)
    print("4) رفع predicted masks إلى PostGIS Raster")
    print("=" * 70)

    if shutil.which("raster2pgsql") is None or shutil.which("psql") is None:
        print("raster2pgsql أو psql غير موجود. سيتم تخطي رفع الراستر.")
        return

    files = []

    for pattern in ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]:
        files.extend(glob.glob(str(CFG.PRED_MASK_DIR / pattern)))

    files = sorted(set(files))

    if not files:
        print(f"ما لقيت masks في: {CFG.PRED_MASK_DIR}")
        return

    env = os.environ.copy()
    env["PGPASSWORD"] = CFG.DB_PASSWORD

    print("حذف جدول predicted_rasters القديم...")
    run_psql(f"DROP TABLE IF EXISTS {CFG.RASTER_TABLE} CASCADE;", env)

    success = 0
    failed = []

    for i, tiff_path in enumerate(files, start=1):
        fname = os.path.basename(tiff_path)
        flag = "-c" if i == 1 else "-a"

        raster_cmd = [
            "raster2pgsql",
            "-s", str(CFG.RASTER_SRID),
            flag,
            "-I",
            "-F",
            "-t", CFG.TILE_SIZE,
            tiff_path,
            CFG.RASTER_TABLE,
        ]

        psql_cmd = [
            "psql",
            "-h", CFG.DB_HOST,
            "-p", str(CFG.DB_PORT),
            "-U", CFG.DB_USER,
            "-d", CFG.DB_NAME,
            "-q",
        ]

        if i == 1 or i % 50 == 0 or i == len(files):
            print(f"[{i}/{len(files)}] {fname} ...", end=" ", flush=True)

        try:
            r2p = subprocess.Popen(
                raster_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            result = subprocess.run(
                psql_cmd,
                stdin=r2p.stdout,
                capture_output=True,
                env=env,
                text=True,
                timeout=180,
            )

            if r2p.stdout:
                r2p.stdout.close()

            r2p.wait()

            if result.returncode == 0:
                success += 1

                if i == 1 or i % 50 == 0 or i == len(files):
                    print("نجح")
            else:
                failed.append((fname, result.stderr[:300]))

                if i == 1 or i % 50 == 0 or i == len(files):
                    print("فشل")

        except Exception as e:
            failed.append((fname, str(e)))

    if success > 0:
        result = run_psql(
            f"SELECT AddRasterConstraints('{CFG.RASTER_TABLE}'::name, 'rast'::name);",
            env,
            quiet=False,
        )

        if result.returncode != 0:
            print(f"AddRasterConstraints warning: {result.stderr[:200]}")

        run_psql(f"VACUUM ANALYZE {CFG.RASTER_TABLE};", env)

    print(f"rasters نجحت: {success} | فشلت: {len(failed)}")

    if failed[:5]:
        print("أول الأخطاء:")
        for fname, err in failed[:5]:
            print(f"- {fname}: {err}")


# ============================================================
# تشغيل البايبلاين
# ============================================================
def run_pipeline() -> None:
    make_dirs()

    metrics = run_model_test_and_predict()

    analysis_df, info_df = analyze_predictions()

    save_to_database(analysis_df, info_df, metrics)

    print("\n" + "=" * 70)
    print("انتهى البايبلاين كامل بدون LLM")
    print("=" * 70)
    print(f"النتائج النهائية: {CFG.OUTPUT_DIR / 'spill_analysis_results_full.csv'}")
    print(f"Predicted masks: {CFG.PRED_MASK_DIR}")
    print(f"Visual reports: {CFG.VIS_DIR}")
    print("الجداول في قاعدة البيانات:")
    print("- spill_info")
    print("- spill_analysis_results")
    print("- model_test_metrics")
    print(f"- {CFG.RASTER_TABLE} إذا تم رفع الراستر بنجاح")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Oil Spill Full Pipeline without Large Language Model"
    )

    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="عدد محدد من الصور للتجربة فقط",
    )

    parser.add_argument(
        "--no-raster-upload",
        action="store_true",
        help="عدم رفع predicted masks إلى PostGIS Raster",
    )

    parser.add_argument(
        "--no-db",
        action="store_true",
        help="تشغيل التحليل فقط بدون حفظ في قاعدة البيانات",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.max_samples is not None:
        CFG.MAX_SAMPLES = args.max_samples

    if args.no_raster_upload:
        CFG.ENABLE_RASTER_UPLOAD = False

    if args.no_db:
        make_dirs()
        metrics = run_model_test_and_predict()
        analysis_df, info_df = analyze_predictions()

        print("\n" + "=" * 70)
        print("انتهى التشغيل بدون قاعدة البيانات")
        print("=" * 70)
        print(f"Metrics: {metrics}")
        print(f"Results: {CFG.OUTPUT_DIR / 'spill_analysis_results_full.csv'}")
        return

    run_pipeline()


if __name__ == "__main__":
    main()