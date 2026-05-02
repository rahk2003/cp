"""
🛢️ Oil Spill Pipeline (Pipeline-only, no Agent)
================================================

نسخة نظيفة بدون الإيجنت — استخدمي oil_rag_agent.py للـ RAG/SQL.

ما يفعله السكربت:
1) يقرأ صور Oil GeoTIFF الأصلية
2) ينبّأ بـ predicted masks (يحفظها بنفس CRS + transform الأصليين)
3) يحلل خصائص التسرب (مساحة، شكل، انتشار...)
4) يحسب القرب من اليابسة والشعب المرجانية
5) يولّد تقارير LLM محلية لكل تسرب
6) يحفظ النتائج في PostgreSQL/PostGIS
7) يرفع predicted masks إلى PostGIS Raster

العرض البصري:
- الصورة الأصلية تُعرض RAW من الملف بدون أي معالجة (cmap='gray', vmin/vmax الأصليين)
- Predicted mask + Overlay + جدول الميزات

قبل التشغيل:
    pip install tensorflow rasterio geopandas shapely pyproj opencv-python matplotlib pandas sqlalchemy psycopg2-binary langchain-ollama langchain-core

شغلي Ollama:
    ollama serve
    ollama pull llama3.1

طريقة التشغيل:
    python oil_full_pipeline.py
    python oil_full_pipeline.py --max-samples 50
    python oil_full_pipeline.py --no-raster-upload
"""

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
from rasterio.warp import transform
from rasterio.windows import Window
from shapely.geometry import box
from sqlalchemy import create_engine, text

try:
    from langchain_ollama import ChatOllama
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    OLLAMA_AVAILABLE = True
except Exception:
    ChatOllama = None
    StrOutputParser = None
    ChatPromptTemplate = None
    OLLAMA_AVAILABLE = False


# ============================================================
# الإعدادات
# ============================================================
@dataclass
class Config:
    BASE_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP")

    MODEL_PATH: Path = Path("/Users/rana/Documents/tuwaiq/CP/best_deeplab_finetuned.keras")

    # Oil فيه صور .tif مباشرة بدون تقسيم وبدون masks
    OIL_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/Oil")
    TEST_IMG_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/Oil")
    TEST_MSK_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/Oil/__no_masks_available__")

    LAND_SHP: Path = Path("/Users/rana/Documents/tuwaiq/CP/ne_10m_land")
    CORAL_SHP: Path = Path("/Users/rana/Documents/tuwaiq/CP/Global_Coral_Reef_Points/Global_Coral_Reef_Points.shp")

    OUTPUT_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output")
    PRED_MASK_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/predicted_masks/test")
    VIS_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/visual_reports")
    LLM_REPORT_DIR: Path = Path("/Users/rana/Documents/tuwaiq/CP/full_pipeline_output/llm_reports")

    IMG_SIZE: int = 256
    BATCH_SIZE: int = 4
    THRESHOLD: float = 0.5
    PIXEL_SIZE_M: float = 0.5
    MAX_SAMPLES: Optional[int] = None

    TARGET_CRS: str = "EPSG:3857"
    BUFFER_STEPS: Tuple[int, ...] = (500, 1000, 2000, 5000, 10000, 20000)

    DB_USER: str = "postgres"
    DB_PASSWORD: str = "1234"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "oil_spills"

    ENABLE_RASTER_UPLOAD: bool = True
    RASTER_TABLE: str = "predicted_rasters"
    RASTER_SRID: int = 4326
    TILE_SIZE: str = "512x512"

    OLLAMA_MODEL: str = "llama3.1"
    MAX_LLM_REPORTS: Optional[int] = 10

    @property
    def DB_URI(self) -> str:
        return (
            f"postgresql+psycopg2://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


CFG = Config()


# ============================================================
# أدوات عامة
# ============================================================
def make_dirs() -> None:
    CFG.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CFG.PRED_MASK_DIR.mkdir(parents=True, exist_ok=True)
    CFG.VIS_DIR.mkdir(parents=True, exist_ok=True)
    CFG.LLM_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def get_sorted_files(folder: Path) -> List[Path]:
    exts = [".tif", ".tiff", ".png", ".jpg", ".jpeg"]
    if not folder.exists():
        return []
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts])


def find_matching_file(filename: str, folder: Path) -> Optional[Path]:
    stem = Path(filename).stem
    candidates = [
        folder / filename,
        folder / f"{stem}.tif",
        folder / f"{stem}.tiff",
        folder / f"{stem}.png",
        folder / f"{stem}.jpg",
        folder / f"{stem}.jpeg",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


# ============================================================
# Dice metric لتوافق تحميل المودل
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
# قراءة الصور للمودل
# ============================================================
def read_image_array_for_model(path: Path, img_size: int) -> np.ndarray:
    """قراءة Oil GeoTIFF + تحضيرها للمودل (resize + normalize)."""
    with rasterio.open(path) as src:
        img = src.read()

    img = np.transpose(img, (1, 2, 0))

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
    with rasterio.open(path) as src:
        mask = src.read(1)
    mask = (mask > 0).astype(np.float32)
    mask = np.expand_dims(mask, axis=-1)
    mask = tf.image.resize(mask, (img_size, img_size), method="nearest").numpy()
    return mask.astype(np.float32)


# ============================================================
# ✅ قراءة الصورة الأصلية للعرض (نفس منطق read_image_for_model + resize للماسك)
# ============================================================
def read_original_for_plot(
    img_path: Path,
    img_size: Optional[int] = None,
    target_h: Optional[int] = None,
    target_w: Optional[int] = None,
) -> Optional[np.ndarray]:
    """يقرأ الصورة الأصلية ويعدّها للعرض:
    - يحوّل القنوات إلى 3
    - normalize 0-1 (نفس طريقة التدريب)
    - resize إلى نفس حجم الماسك (target_h, target_w) أو img_size

    هكذا الصورة تطابق الـ predicted mask تماماً، وأيضاً تطابق ما رآه المودل.
    """
    try:
        suffix = img_path.suffix.lower()

        if suffix in [".tif", ".tiff"]:
            with rasterio.open(img_path) as src:
                img = src.read()
            img = np.transpose(img, (1, 2, 0))  # (bands, H, W) → (H, W, bands)
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

        # توحيد القنوات إلى 3
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

        # Normalize 0-1 لتوضيح التباين
        img_min = img.min()
        img_max = img.max()
        img = (img - img_min) / (img_max - img_min + 1e-8)

        # Resize: حجم الماسك له الأولوية
        if target_h is not None and target_w is not None:
            img = tf.image.resize(img, (target_h, target_w)).numpy()
        elif img_size is not None:
            img = tf.image.resize(img, (img_size, img_size)).numpy()
        # وإلا نتركها بحجمها الأصلي

        return img.astype(np.float32)

    except Exception as e:
        print(f"⚠️ failed to read {img_path.name}: {e}")
        return None


# ============================================================
# اختبار المودل + حفظ predicted masks (مع CRS من Oil)
# ============================================================
def run_model_test_and_predict() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print("1) تحميل المودل واختباره ثم حفظ predicted masks (مصدر: Oil GeoTIFF)")
    print("=" * 70)

    images = get_sorted_files(CFG.TEST_IMG_DIR)

    # استبعاد ملفات داخل مجلد المخرجات إن وجدت
    try:
        out_dir_resolved = CFG.OUTPUT_DIR.resolve()
        images = [p for p in images if out_dir_resolved not in p.resolve().parents]
    except Exception:
        pass

    if CFG.MAX_SAMPLES is not None:
        images = images[: CFG.MAX_SAMPLES]

    if not images:
        msg = (
            f"ما لقيت صور test في: {CFG.TEST_IMG_DIR}\n"
            f"تأكدي من المسار وامتدادات الملفات (.tif/.tiff)."
        )
        raise FileNotFoundError(msg)

    masks_available = CFG.TEST_MSK_DIR.exists() and len(get_sorted_files(CFG.TEST_MSK_DIR)) > 0

    print(f"صور الاختبار من Oil: {len(images)}")
    print(f"مجلد الماسكات موجود: {masks_available}")
    if not masks_available:
        print("ℹ️ لا توجد ground truth masks → سيتم تخطي حساب Dice و Confusion Matrix")
    print(f"المودل: {CFG.MODEL_PATH}")

    model = tf.keras.models.load_model(CFG.MODEL_PATH, custom_objects={"dice_coef": dice_coef})
    print("✅ تم تحميل المودل")

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

        # ✅ نحتفظ بـ CRS و transform الأصليين من Oil
        with rasterio.open(img_path) as src:
            profile = src.profile.copy()
            out_h, out_w = src.height, src.width
            transform_src = src.transform
            crs_src = src.crs

        if crs_src is None:
            no_crs_count += 1

        pred_bin = cv2.resize(
            pred_bin_small, (out_w, out_h), interpolation=cv2.INTER_NEAREST
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
                dice = (2 * intersection + 1e-6) / (np.sum(true_small) + np.sum(pred_small) + 1e-6)
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

    if no_crs_count > 0:
        print(f"⚠️ {no_crs_count} صورة بدون CRS")

    with open(CFG.OUTPUT_DIR / "model_test_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

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

    pd.DataFrame(pred_records).to_csv(CFG.OUTPUT_DIR / "prediction_files.csv", index=False, encoding="utf-8-sig")
    print(f"✅ predicted masks: {CFG.PRED_MASK_DIR}")
    print(f"✅ metrics: {metrics}")
    return metrics


# ============================================================
# الإحداثيات والتاريخ من Oil الأصلي
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
        "file": path.name, "source_path": str(path),
        "date": None, "time": None, "crs": None,
        "width": None, "height": None,
        "pixel_size_x": None, "pixel_size_y": None,
        "bbox_left": None, "bbox_bottom": None, "bbox_right": None, "bbox_top": None,
        "center_lon": None, "center_lat": None,
        "upper_left_lon": None, "upper_left_lat": None,
        "upper_right_lon": None, "upper_right_lat": None,
        "lower_right_lon": None, "lower_right_lat": None,
        "lower_left_lon": None, "lower_left_lat": None,
        "error": None,
    }

    try:
        info["date"], info["time"] = get_file_datetime(path)
    except Exception as e:
        info["error"] = f"datetime error: {e}"

    try:
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
# القرب من اليابسة والشعب
# ============================================================
def load_union_layer(path: Path, target_crs: str, default_crs: Optional[str] = None, name: str = "layer"):
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
                col_off=col_min, row_off=row_min,
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
        gdf = gpd.GeoDataFrame({"filename": [mask_path.name]}, geometry=[img_poly], crs=src.crs)
        gdf = gdf.to_crs(target_crs)
        return gdf.geometry.iloc[0], geom_type


def proximity_to_union(mask_path: Path, union_geom, mode: str) -> Dict[str, Any]:
    geom, geom_type = get_spill_bbox_geometry(mask_path, CFG.TARGET_CRS)

    if geom is None:
        if mode == "land":
            return {"distance_to_land_m": None, "distance_to_land_km": None,
                    "land_proximity_class": "no_crs", "proximity_geom_type": geom_type}
        return {"distance_to_coral_m": None, "distance_to_coral_km": None,
                "coral_proximity_class": "no_crs", "proximity_geom_type": geom_type}

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
            "distance_to_land_m": hit, "distance_to_land_km": km,
            "land_proximity_class": cls, "proximity_geom_type": geom_type,
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
        "distance_to_coral_m": hit, "distance_to_coral_km": km,
        "coral_proximity_class": cls, "proximity_geom_type": geom_type,
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
        orientation_deg = round(float(np.degrees(np.arctan2(major_vec[1], major_vec[0]))), 2)
        spread_ratio = round(float(np.sqrt(eigvals.max() / (eigvals.min() + 1e-8))), 3)

    num_labels, labels_map, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
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
            "centroid": (round(float(centroids[lbl][0]), 1), round(float(centroids[lbl][1]), 1)),
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
        mean_intensity = max_intensity = std_intensity = density_score = 0.0

    return {
        "area_px": area_px, "area_m2": area_m2, "coverage_pct": coverage_pct,
        "centroid_x": cx, "centroid_y": cy,
        "perimeter_px": round(float(perimeter_px), 2), "perimeter_m": perimeter_m,
        "orientation_deg": orientation_deg, "spread_ratio": spread_ratio,
        "num_components": int(num_labels - 1),
        "components_json": json.dumps(components, ensure_ascii=False),
        "compactness": compactness,
        "mean_intensity": mean_intensity, "max_intensity": max_intensity,
        "std_intensity": std_intensity, "density_score": density_score,
        "contours_count": len(contours),
        "components": components, "contours": contours,
    }


def pixel_centroid_to_lonlat(mask_path: Path, cx: int, cy: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        with rasterio.open(mask_path) as src:
            if src.crs is None:
                return None, None
            x_world, y_world = src.transform * (cx, cy)
            lon, lat = transform(src.crs, CRS.from_epsg(4326), [x_world], [y_world])
            return float(lon[0]), float(lat[0])
    except Exception:
        return None, None


# ============================================================
# Risk Engine
# ============================================================
def compute_risk(features: Dict[str, Any], land_info: Dict[str, Any], coral_info: Dict[str, Any]) -> Dict[str, Any]:
    score = 0.0
    factors = []

    cov = features["coverage_pct"]
    if cov >= 50:
        score += 40; factors.append(f"coverage {cov}% → CRITICAL (>=50%)")
    elif cov >= 25:
        score += 30; factors.append(f"coverage {cov}% → HIGH (25-50%)")
    elif cov >= 10:
        score += 20; factors.append(f"coverage {cov}% → MEDIUM (10-25%)")
    elif cov >= 2:
        score += 10; factors.append(f"coverage {cov}% → LOW (2-10%)")
    else:
        factors.append(f"coverage {cov}% → MINIMAL (<2%)")

    sr = features["spread_ratio"]
    if sr >= 10:
        score += 25; factors.append(f"spread_ratio {sr} → CRITICAL (>=10)")
    elif sr >= 5:
        score += 18; factors.append(f"spread_ratio {sr} → HIGH (5-10)")
    elif sr >= 2:
        score += 10; factors.append(f"spread_ratio {sr} → MEDIUM (2-5)")
    else:
        score += 4; factors.append(f"spread_ratio {sr} → LOW (<2)")

    nc = features["num_components"]
    if nc >= 5:
        score += 20; factors.append(f"components {nc} → CRITICAL")
    elif nc >= 3:
        score += 14; factors.append(f"components {nc} → HIGH")
    elif nc == 2:
        score += 8; factors.append(f"components {nc} → MEDIUM")
    elif nc == 1:
        score += 3; factors.append(f"components {nc} → LOW")
    else:
        factors.append(f"components {nc} → NONE")

    ds = features["density_score"]
    if ds >= 0.95:
        score += 15; factors.append(f"density {ds} → CRITICAL")
    elif ds >= 0.85:
        score += 10; factors.append(f"density {ds} → HIGH")
    elif ds >= 0.70:
        score += 6; factors.append(f"density {ds} → MEDIUM")
    else:
        score += 2; factors.append(f"density {ds} → LOW")

    d_land = land_info.get("distance_to_land_km")
    if d_land is not None:
        if d_land == 0:
            score += 20; factors.append("land 0 km → CRITICAL")
        elif d_land <= 1:
            score += 15; factors.append(f"land {d_land} km → HIGH")
        elif d_land <= 5:
            score += 10; factors.append(f"land {d_land} km → MEDIUM")
        elif d_land <= 20:
            score += 5; factors.append(f"land {d_land} km → LOW")
        else:
            factors.append(f"land {d_land} km → VERY FAR")
    else:
        factors.append("land distance unknown")

    d_coral = coral_info.get("distance_to_coral_km")
    if d_coral is not None:
        if d_coral == 0:
            score += 25; factors.append("coral 0 km → CRITICAL")
        elif d_coral <= 1:
            score += 22; factors.append(f"coral {d_coral} km → CRITICAL")
        elif d_coral <= 5:
            score += 16; factors.append(f"coral {d_coral} km → HIGH")
        elif d_coral <= 10:
            score += 10; factors.append(f"coral {d_coral} km → MEDIUM")
        elif d_coral <= 20:
            score += 5; factors.append(f"coral {d_coral} km → LOW")
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

    return {"risk_score": score, "risk_level": level, "risk_factors": " | ".join(factors)}


# ============================================================
# Visualization (RAW image display)
# ============================================================
RISK_COLORS = {
    "CRITICAL": "#e24b4a",
    "HIGH": "#ef9f27",
    "MEDIUM": "#378add",
    "LOW": "#1d9e75",
    "NONE": "#888780",
}


def visualize_sample(mask_path: Path, original_path: Optional[Path], row: Dict[str, Any]) -> Optional[Path]:
    """يعرض:
    1) الصورة الأصلية بحجمها الكامل (مع normalize 0-1 لتوضيح التباين)
    2) Predicted mask بحجمها الكامل
    3) Overlay فوق الصورة الأصلية
    4) جدول الميزات
    الإحداثيات (centroid, bbox) محسوبة على نفس الحجم الكامل، فالعرض يتطابق.
    """
    try:
        mask = read_mask(mask_path)
        H, W = mask.shape

        # ✅ نقرأ الصورة الأصلية بحجمها الكامل (نفس حجم الماسك)
        original_image = None
        if original_path is not None:
            original_image = read_original_for_plot(original_path, img_size=None,
                                                   target_h=H, target_w=W)

        fig, axes = plt.subplots(1, 4, figsize=(20, 5))
        risk_level = row.get("risk_level", "NONE")
        risk_color = RISK_COLORS.get(risk_level, "#888780")

        fig.suptitle(
            f"Spill Analysis - {mask_path.name} | Risk: {risk_level} ({row.get('risk_score')}/100)",
            fontsize=13, fontweight="bold", color=risk_color,
        )

        # ───────── 1) الصورة الأصلية ─────────
        if original_image is None:
            axes[0].text(0.5, 0.5, "Original image\nnot found", ha="center", va="center")
        else:
            if original_image.ndim == 3:
                axes[0].imshow(original_image)
            else:
                axes[0].imshow(original_image, cmap="gray")
        axes[0].set_title("Original image")
        axes[0].axis("off")

        # ───────── 2) Predicted mask ─────────
        axes[1].imshow(mask, cmap="gray")
        axes[1].set_title("Predicted mask")
        axes[1].axis("off")

        # ───────── 3) Overlay ─────────
        if original_image is None:
            overlay_bg = np.stack([mask, mask, mask], axis=-1)
            axes[2].imshow(overlay_bg)
        else:
            if original_image.ndim == 3:
                axes[2].imshow(original_image)
            else:
                axes[2].imshow(original_image, cmap="gray")
            # طبقة شفافة فوق الصورة لتوضيح التسرب باللون الأحمر-البرتقالي
            spill_overlay = np.zeros((H, W, 4), dtype=np.float32)
            spill_overlay[mask > 0.5] = [1.0, 0.25, 0.1, 0.55]  # RGBA
            axes[2].imshow(spill_overlay)

        axes[2].plot(row["centroid_x"], row["centroid_y"], "y+", markersize=14, markeredgewidth=2)

        try:
            components = json.loads(row["components_json"])
            for comp in components:
                x, y, w, h = comp["bbox_xywh"]
                axes[2].add_patch(
                    patches.Rectangle((x, y), w, h, linewidth=1.2, edgecolor="cyan", facecolor="none")
                )
        except Exception:
            pass

        axes[2].set_title("Overlay + components")
        axes[2].axis("off")

        # ───────── 4) جدول الميزات ─────────
        axes[3].axis("off")
        lines = [
            f"Area:           {row['area_px']:,} px ({row['area_m2']} m²)",
            f"Coverage:       {row['coverage_pct']}%",
            f"Centroid (px):  ({row['centroid_x']}, {row['centroid_y']})",
            f"Centroid (lon,lat): ({row.get('spill_centroid_lon')}, {row.get('spill_centroid_lat')})",
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
            "────────────────────",
            f"Risk score:     {row['risk_score']} / 100",
            f"Risk level:     {row['risk_level']}",
        ]
        for i, line in enumerate(lines):
            color = risk_color if i >= len(lines) - 2 else "black"
            axes[3].text(0.02, 0.98 - i * 0.052, line, transform=axes[3].transAxes,
                         fontsize=8, fontfamily="monospace", va="top", color=color)
        axes[3].set_title("Extracted features + risk")

        plt.tight_layout()
        out_path = CFG.VIS_DIR / f"{mask_path.stem}_report.png"
        plt.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close()
        return out_path
    except Exception as e:
        print(f"⚠️ visualization failed for {mask_path.name}: {e}")
        return None


# ============================================================
# Local LLM Report
# ============================================================
def row_to_prompt_text(row: Dict[str, Any]) -> str:
    return f"""معرّف العينة: {row['filename']}
الصورة الأصلية: {row.get('source_image')}

الموقع الجغرافي:
- نظام الإحداثيات: {row.get('crs')}
- مركز الصورة: lon={row.get('center_lon')}, lat={row.get('center_lat')}
- مركز التسرب: lon={row.get('spill_centroid_lon')}, lat={row.get('spill_centroid_lat')}
- التاريخ: {row.get('date')} {row.get('time')}

المقاييس الهندسية:
- المساحة: {row['area_px']:,} بكسل ({row['area_m2']} م²)
- نسبة التغطية: {row['coverage_pct']}%
- المحيط: {row['perimeter_px']} بكسل ({row['perimeter_m']} م)
- مركز البقعة (بكسل): ({row['centroid_x']}, {row['centroid_y']})
- زاوية التوجّه: {row['orientation_deg']}°
- نسبة الامتداد: {row['spread_ratio']}
- معامل الانضغاط: {row['compactness']}
- عدد البقع المنفصلة: {row['num_components']}

مقاييس الشدة:
- متوسط الشدة: {row['mean_intensity']}
- أقصى شدة: {row['max_intensity']}
- الانحراف المعياري: {row['std_intensity']}
- درجة الكثافة: {row['density_score']}

القرب من اليابسة:
- المسافة: {row['distance_to_land_km']} كم
- التصنيف: {row['land_proximity_class']}

القرب من الشعب المرجانية:
- المسافة: {row['distance_to_coral_km']} كم
- التصنيف: {row['coral_proximity_class']}

تقييم الخطورة:
- Risk Score: {row['risk_score']} / 100
- Risk Level: {row['risk_level']}
- العوامل:
{row['risk_factors']}
""".strip()


def get_local_llm():
    if not OLLAMA_AVAILABLE:
        raise ImportError("langchain_ollama غير مثبت")
    return ChatOllama(model=CFG.OLLAMA_MODEL, temperature=0.2)


def generate_local_report(row: Dict[str, Any]) -> str:
    llm = get_local_llm()
    prompt_text = row_to_prompt_text(row)
    system = """أنت خبير بيئي متخصص في تحليل صور الأقمار الاصطناعية SAR لرصد التسربات النفطية.
اكتب تقريراً تقنياً عربياً فصيحاً ومختصراً. استخدم فقط الأرقام المقدمة ولا تخترع.
استخدم HTML بسيط: <h3> <p> <ul><li>."""

    user_prompt = f"""لدي نتائج تحليل تسرب نفطي:

{prompt_text}

اكتب تقريراً يحتوي:
<h3>١. الملخص التنفيذي</h3>
<h3>٢. الموقع الجغرافي والتاريخ</h3>
<h3>٣. الوصف الهندسي للتسرب</h3>
<h3>٤. القرب من اليابسة والشعب المرجانية والأثر البيئي</h3>
<h3>٥. تقييم الخطورة</h3>
<h3>٦. التوصيات</h3>
<ul><li>3 توصيات عملية فقط.</li></ul>
<h3>٧. الملاحظات</h3>"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("user", user_prompt),
    ])
    return (prompt | llm | StrOutputParser()).invoke({})


def build_html_report(row: Dict[str, Any], report_html: str, image_path: Optional[Path]) -> str:
    risk_color = RISK_COLORS.get(row["risk_level"], "#888")
    img_html = (
        f'<img src="../visual_reports/{image_path.name}" style="max-width:100%;border-radius:10px;">'
        if image_path and image_path.exists()
        else "<p>صورة التحليل غير موجودة.</p>"
    )

    geo_block = f"""
    <p><b>CRS:</b> {row.get('crs')}</p>
    <p><b>مركز الصورة:</b> lon={row.get('center_lon')}, lat={row.get('center_lat')}</p>
    <p><b>مركز التسرب:</b> lon={row.get('spill_centroid_lon')}, lat={row.get('spill_centroid_lat')}</p>
    <p><b>التاريخ:</b> {row.get('date')} {row.get('time')}</p>
    """

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تقرير - {row['filename']}</title>
<style>
body {{font-family: Arial; background:#f4f6f8; color:#263238; padding:20px; line-height:1.8;}}
.container {{max-width:1100px; margin:auto; background:white; border-radius:14px; overflow:hidden; box-shadow:0 4px 18px rgba(0,0,0,.08);}}
.header {{background:#1a4a8a; color:white; padding:28px;}}
.badge {{display:inline-block; background:{risk_color}; color:white; padding:8px 18px; border-radius:18px; font-weight:bold;}}
.section {{padding:26px;}}
.geo {{background:#eaf2fb; padding:16px; border-radius:10px; margin-bottom:18px;}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🛰️ تقرير تحليل التسرب النفطي</h1>
    <p>{row['filename']}</p>
    <span class="badge">{row['risk_level']} — {row['risk_score']}/100</span>
  </div>
  <div class="section">
    <div class="geo">{geo_block}</div>
    <h2>التحليل البصري</h2>
    {img_html}
  </div>
  <div class="section">
    <h2>التقرير</h2>
    {report_html}
  </div>
</div>
</body>
</html>"""


# ============================================================
# التحليل الكامل
# ============================================================
def analyze_predictions() -> Tuple[pd.DataFrame, pd.DataFrame]:
    print("\n" + "=" * 70)
    print("2) تحليل + قرب اليابسة/الشعب + إحداثيات من Oil")
    print("=" * 70)

    mask_files = get_sorted_files(CFG.PRED_MASK_DIR)
    if CFG.MAX_SAMPLES is not None:
        mask_files = mask_files[: CFG.MAX_SAMPLES]
    if not mask_files:
        raise FileNotFoundError(f"ما لقيت predicted masks في: {CFG.PRED_MASK_DIR}")

    print("تحميل طبقة اليابسة...")
    land_union = load_union_layer(CFG.LAND_SHP, CFG.TARGET_CRS, default_crs=None, name="land")
    print("تحميل طبقة الشعب المرجانية...")
    coral_union = load_union_layer(CFG.CORAL_SHP, CFG.TARGET_CRS, default_crs="EPSG:4326", name="coral")

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
            tiff_info["error"] = (tiff_info.get("error") or "") + " | original not found"

        spill_lon, spill_lat = pixel_centroid_to_lonlat(
            mask_path, features["centroid_x"], features["centroid_y"]
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

    analysis_df.to_csv(CFG.OUTPUT_DIR / "spill_analysis_results_full.csv", index=False, encoding="utf-8-sig")
    info_df.to_csv(CFG.OUTPUT_DIR / "spill_info.csv", index=False, encoding="utf-8-sig")

    print(f"✅ التحليل: {CFG.OUTPUT_DIR / 'spill_analysis_results_full.csv'}")
    print(f"✅ الإحداثيات: {CFG.OUTPUT_DIR / 'spill_info.csv'}")
    return analysis_df, info_df


# ============================================================
# تقارير LLM
# ============================================================
def generate_llm_reports(analysis_df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("3) تقارير LLM محلية (Ollama)")
    print("=" * 70)

    if not OLLAMA_AVAILABLE:
        print("⚠️ langchain_ollama غير مثبت. تخطي تقارير LLM.")
        analysis_df["llm_report_html"] = None
        analysis_df["llm_report_path"] = None
        return analysis_df

    rows = analysis_df.to_dict("records")
    rows_to_generate = rows[: CFG.MAX_LLM_REPORTS] if CFG.MAX_LLM_REPORTS is not None else rows

    report_map = {}
    path_map = {}

    for idx, row in enumerate(rows_to_generate, start=1):
        print(f"[{idx}/{len(rows_to_generate)}] LLM: {row['filename']}")
        if int(row.get("area_px", 0)) == 0:
            report_html = "<p>لم يتم اكتشاف تسرب في هذه العينة.</p>"
        else:
            try:
                report_html = generate_local_report(row)
            except Exception as e:
                report_html = f"<p>تعذر التقرير: {e}</p>"

        vis_path = Path(row["visual_report_path"]) if row.get("visual_report_path") else None
        html = build_html_report(row, report_html, vis_path)
        out_path = CFG.LLM_REPORT_DIR / f"{Path(row['filename']).stem}_llm_report.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        report_map[row["filename"]] = report_html
        path_map[row["filename"]] = str(out_path)

    analysis_df["llm_report_html"] = analysis_df["filename"].map(report_map)
    analysis_df["llm_report_path"] = analysis_df["filename"].map(path_map)

    analysis_df.to_csv(CFG.OUTPUT_DIR / "spill_analysis_results_full_with_llm.csv", index=False, encoding="utf-8-sig")
    print(f"✅ تقارير LLM: {CFG.LLM_REPORT_DIR}")
    return analysis_df


# ============================================================
# قاعدة البيانات
# ============================================================
def save_to_database(analysis_df: pd.DataFrame, info_df: pd.DataFrame, metrics: Dict[str, Any]) -> None:
    print("\n" + "=" * 70)
    print("4) حفظ في PostgreSQL/PostGIS")
    print("=" * 70)

    engine = create_engine(CFG.DB_URI)
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            print("✅ PostGIS extension جاهز")
        except Exception as e:
            print(f"⚠️ PostGIS: {e}")

    info_df.to_sql("spill_info", engine, if_exists="replace", index=False)
    analysis_df.to_sql("spill_analysis_results", engine, if_exists="replace", index=False)

    metrics_df = pd.DataFrame([{
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics_json": json.dumps(metrics, ensure_ascii=False),
    }])
    metrics_df.to_sql("model_test_metrics", engine, if_exists="replace", index=False)

    print("✅ الجداول: spill_info, spill_analysis_results, model_test_metrics")

    if CFG.ENABLE_RASTER_UPLOAD:
        upload_predicted_masks_to_postgis()


# ============================================================
# رفع masks إلى PostGIS Raster
# ============================================================
def run_psql(sql: str, env: Dict[str, str], quiet: bool = True) -> subprocess.CompletedProcess:
    cmd = [
        "psql",
        "-h", CFG.DB_HOST, "-p", str(CFG.DB_PORT),
        "-U", CFG.DB_USER, "-d", CFG.DB_NAME,
        "-c", sql,
    ]
    if quiet:
        cmd.append("-q")
    return subprocess.run(cmd, env=env, capture_output=True, text=True)


def upload_predicted_masks_to_postgis() -> None:
    print("\n" + "=" * 70)
    print("5) رفع predicted masks إلى predicted_rasters")
    print("=" * 70)

    if shutil.which("raster2pgsql") is None or shutil.which("psql") is None:
        print("⚠️ raster2pgsql أو psql غير موجود. تخطي.")
        return

    files = []
    for pattern in ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]:
        files.extend(glob.glob(str(CFG.PRED_MASK_DIR / pattern)))
    files = sorted(set(files))

    if not files:
        print(f"⚠️ ما لقيت masks في: {CFG.PRED_MASK_DIR}")
        return

    env = os.environ.copy()
    env["PGPASSWORD"] = CFG.DB_PASSWORD

    print("🗑️ حذف predicted_rasters القديم...")
    run_psql(f"DROP TABLE IF EXISTS {CFG.RASTER_TABLE} CASCADE;", env)

    success = 0
    failed = []

    for i, tiff_path in enumerate(files, start=1):
        fname = os.path.basename(tiff_path)
        flag = "-c" if i == 1 else "-a"

        raster_cmd = [
            "raster2pgsql",
            "-s", str(CFG.RASTER_SRID),
            flag, "-I", "-F",
            "-t", CFG.TILE_SIZE,
            tiff_path, CFG.RASTER_TABLE,
        ]
        psql_cmd = [
            "psql",
            "-h", CFG.DB_HOST, "-p", str(CFG.DB_PORT),
            "-U", CFG.DB_USER, "-d", CFG.DB_NAME, "-q",
        ]

        if i == 1 or i % 50 == 0 or i == len(files):
            print(f"[{i}/{len(files)}] {fname} ...", end=" ", flush=True)

        try:
            r2p = subprocess.Popen(raster_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            result = subprocess.run(psql_cmd, stdin=r2p.stdout, capture_output=True, env=env, text=True, timeout=180)
            if r2p.stdout:
                r2p.stdout.close()
            r2p.wait()

            if result.returncode == 0:
                success += 1
                if i == 1 or i % 50 == 0 or i == len(files):
                    print("✅")
            else:
                failed.append((fname, result.stderr[:300]))
                if i == 1 or i % 50 == 0 or i == len(files):
                    print("❌")
        except Exception as e:
            failed.append((fname, str(e)))

    if success > 0:
        result = run_psql(f"SELECT AddRasterConstraints('{CFG.RASTER_TABLE}'::name, 'rast'::name);", env, quiet=False)
        if result.returncode != 0:
            print(f"⚠️ AddRasterConstraints: {result.stderr[:200]}")
        run_psql(f"VACUUM ANALYZE {CFG.RASTER_TABLE};", env)

    print(f"✅ rasters نجحت: {success} | فشلت: {len(failed)}")
    if failed[:5]:
        for fname, err in failed[:5]:
            print(f"- {fname}: {err}")


# ============================================================
# Pipeline main
# ============================================================
def run_pipeline() -> None:
    make_dirs()
    metrics = run_model_test_and_predict()
    analysis_df, info_df = analyze_predictions()
    analysis_df = generate_llm_reports(analysis_df)
    save_to_database(analysis_df, info_df, metrics)
    print("\n" + "=" * 70)
    print("✅ انتهى البايبلاين")
    print("=" * 70)
    print(f"المصدر: {CFG.OIL_DIR}")
    print(f"النتائج النهائية: {CFG.OUTPUT_DIR / 'spill_analysis_results_full_with_llm.csv'}")
    print(f"Predicted masks: {CFG.PRED_MASK_DIR}")
    print(f"Visual reports: {CFG.VIS_DIR}")
    print(f"LLM reports: {CFG.LLM_REPORT_DIR}")
    print("\n💡 للسؤال عن النتائج: شغّلي oil_rag_agent.py")


def parse_args():
    parser = argparse.ArgumentParser(description="Oil Spill Pipeline (no agent)")
    parser.add_argument("--max-samples", type=int, default=None, help="عدد محدد من الصور")
    parser.add_argument("--max-llm-reports", type=int, default=None, help="عدد تقارير LLM")
    parser.add_argument("--no-raster-upload", action="store_true", help="عدم رفع rasters لـ PostGIS")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.max_samples is not None:
        CFG.MAX_SAMPLES = args.max_samples
    if args.max_llm_reports is not None:
        CFG.MAX_LLM_REPORTS = args.max_llm_reports
    if args.no_raster_upload:
        CFG.ENABLE_RASTER_UPLOAD = False

    run_pipeline()


if __name__ == "__main__":
    main()