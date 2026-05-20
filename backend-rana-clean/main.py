from __future__ import annotations

import html
import json
import math
import os
import re
import sys
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, unquote, urlparse

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ============================================================
# Environment
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

from risk_display import (  # noqa: E402
    apply_display_risk,
    apply_report_display_risk,
    infer_display_risk_score,
    normalize_display_risk_param,
    normalize_stored_risk,
)


def _normalize_env_value(name: str) -> None:
    value = os.getenv(name)
    if not value:
        return
    cleaned = value.strip()
    if name == "TAVILY_API_KEY":
        cleaned = re.sub(r"^tvly\s+", "tvly-", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", "", cleaned)
    os.environ[name] = cleaned


for _env_name in ("GROQ_API_KEY", "TAVILY_API_KEY", "GEMINI_API_KEY"):
    _normalize_env_value(_env_name)

SPILLS_TABLE = os.getenv("SPILLS_TABLE", "spill_analysis_results").strip()
REPORTS_TABLE = os.getenv("REPORTS_TABLE", "spill_reports").strip()

_engine: Optional[Engine] = None

VALID_RISKS = ["Critical", "High", "Medium", "Low"]
RISK_SCORE_MAP = {"Critical": 100, "High": 75, "Medium": 50, "Low": 25}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def get_db_url(mask_password: bool = False) -> str:
    """Build PostgreSQL SQLAlchemy URL from .env.

    You may also set DATABASE_URL directly, for example:
    postgresql+psycopg2://postgres:password@localhost:5432/oil_spills
    """
    direct = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if direct:
        if mask_password:
            return re.sub(r":([^:@/]+)@", ":***@", direct)
        return direct

    user = os.getenv("DB_USER", "postgres").strip()
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost").strip()
    port = os.getenv("DB_PORT", "5432").strip()
    name = os.getenv("DB_NAME", "oil_spills").strip()

    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    if password:
        real = f"postgresql+psycopg2://{safe_user}:{safe_password}@{host}:{port}/{name}"
        masked = f"postgresql+psycopg2://{safe_user}:***@{host}:{port}/{name}"
        return masked if mask_password else real
    return f"postgresql+psycopg2://{safe_user}@{host}:{port}/{name}"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_db_url(), pool_pre_ping=True, future=True)
    return _engine


def db_ping() -> Tuple[bool, Optional[str]]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def split_table_name(table_name: str) -> Tuple[str, str]:
    if "." in table_name:
        schema, name = table_name.split(".", 1)
        return schema.strip('" '), name.strip('" ')
    return "public", table_name.strip('" ')


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_ref(table_name: str) -> str:
    schema, name = split_table_name(table_name)
    return f"{q(schema)}.{q(name)}"


def table_exists(table_name: str) -> bool:
    schema, name = split_table_name(table_name)
    with get_engine().connect() as conn:
        return bool(conn.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
            )
        """), {"schema_name": schema, "table_name": name}).scalar())


def get_columns(table_name: str) -> List[str]:
    if not table_exists(table_name):
        return []
    schema, name = split_table_name(table_name)
    with get_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = :table_name
            ORDER BY ordinal_position
        """), {"schema_name": schema, "table_name": name}).all()
    return [r[0] for r in rows]


def first_existing(cols: set[str], *names: str) -> Optional[str]:
    for name in names:
        if name in cols:
            return name
    return None


def select_alias(cols: set[str], alias: str, *candidates: str, default_sql: str = "NULL") -> str:
    col = first_existing(cols, *candidates)
    if col:
        return f"{q(col)} AS {q(alias)}"
    return f"{default_sql} AS {q(alias)}"


def risk_sql(cols: set[str]) -> str:
    if "final_risk_level" in cols:
        return f"{q('final_risk_level')} AS final_risk_level"
    if "risk_level" in cols:
        return f"{q('risk_level')} AS final_risk_level"

    land = q("distance_to_land_km") if "distance_to_land_km" in cols else "999999"
    coral = q("distance_to_coral_km") if "distance_to_coral_km" in cols else "999999"
    area = q("area_m2") if "area_m2" in cols else "0"
    coverage = q("coverage_pct") if "coverage_pct" in cols else "0"

    return f"""
        CASE
            WHEN COALESCE({land}, 999999) <= 1
              OR COALESCE({coral}, 999999) <= 1
              OR COALESCE({area}, 0) >= 50000
              OR COALESCE({coverage}, 0) >= 35 THEN 'Critical'
            WHEN COALESCE({land}, 999999) <= 5
              OR COALESCE({coral}, 999999) <= 5
              OR COALESCE({area}, 0) >= 20000
              OR COALESCE({coverage}, 0) >= 20 THEN 'High'
            WHEN COALESCE({land}, 999999) <= 20
              OR COALESCE({coral}, 999999) <= 20
              OR COALESCE({area}, 0) >= 5000
              OR COALESCE({coverage}, 0) >= 8 THEN 'Medium'
            ELSE 'Low'
        END AS final_risk_level
    """


def risk_score_sql(cols: set[str]) -> str:
    if "risk_score" in cols:
        return f"{q('risk_score')} AS risk_score"

    risk_col = first_existing(cols, "final_risk_level", "risk_level")
    if risk_col:
        return f"""
            CASE UPPER(COALESCE({q(risk_col)}::text, ''))
                WHEN 'CRITICAL' THEN 100
                WHEN 'HIGH' THEN 75
                WHEN 'MEDIUM' THEN 50
                WHEN 'LOW' THEN 25
                ELSE 0
            END AS risk_score
        """
    return "0 AS risk_score"


def base_select(cols: set[str]) -> str:
    return ",\n".join([
        select_alias(cols, "id", "id", "spill_id", "filename", default_sql="ROW_NUMBER() OVER ()"),
        select_alias(cols, "spill_id", "spill_id", "id", "filename", default_sql="NULL"),
        select_alias(cols, "filename", "filename", "source_image", "image", default_sql="''"),
        select_alias(cols, "latitude", "latitude", "spill_centroid_lat", "centroid_lat", "center_lat", default_sql="NULL"),
        select_alias(cols, "longitude", "longitude", "spill_centroid_lon", "centroid_lon", "center_lon", default_sql="NULL"),
        select_alias(cols, "area_m2", "area_m2", "spill_area_m2", default_sql="0"),
        select_alias(cols, "coverage_pct", "coverage_pct", "coverage", "coverage_percent", default_sql="0"),
        select_alias(cols, "distance_to_land_km", "distance_to_land_km", "land_distance_km", default_sql="NULL"),
        select_alias(cols, "distance_to_coral_km", "distance_to_coral_km", "nearest_coral_distance_km", "coral_distance_km", default_sql="NULL"),
        select_alias(cols, "land_proximity_class", "land_proximity_class", default_sql="'Unknown'"),
        select_alias(cols, "coral_risk_class", "coral_risk_class", "coral_proximity_class", default_sql="'Unknown'"),
        risk_sql(cols),
        risk_score_sql(cols),
        select_alias(cols, "created_at", "created_at", "analysis_created_at", "detected_at", "processed_at", default_sql="CURRENT_TIMESTAMP"),
        select_alias(cols, "source_image_path", "source_image_path", "source_image", default_sql="NULL"),
        select_alias(cols, "predicted_mask_path", "predicted_mask_path", "mask_path", default_sql="NULL"),
        select_alias(cols, "area_px", "area_px", default_sql="NULL"),
        select_alias(cols, "perimeter_m", "perimeter_m", default_sql="NULL"),
        select_alias(cols, "orientation_deg", "orientation_deg", default_sql="NULL"),
        select_alias(cols, "spread_ratio", "spread_ratio", default_sql="NULL"),
        select_alias(cols, "num_components", "num_components", default_sql="NULL"),
        select_alias(cols, "compactness", "compactness", default_sql="NULL"),
        select_alias(cols, "density_score", "density_score", default_sql="NULL"),
        select_alias(cols, "contours_count", "contours_count", default_sql="NULL"),
    ])


def clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def normalize_risk(value: Any) -> str:
    raw = str(value or "").strip().lower()
    for risk in VALID_RISKS:
        if raw == risk.lower():
            return risk
    if raw in {"حرج", "critical risk"}:
        return "Critical"
    if raw in {"عالي", "high risk"}:
        return "High"
    if raw in {"متوسط", "medium risk"}:
        return "Medium"
    if raw in {"منخفض", "low risk"}:
        return "Low"
    return "Low"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", ""))
    except Exception:
        return default


def infer_risk_score(row: Dict[str, Any]) -> float:
    explicit = to_float(row.get("risk_score"), -1)
    if explicit >= 0:
        return explicit
    risk = normalize_risk(row.get("final_risk_level"))
    base = RISK_SCORE_MAP.get(risk, 0)
    area_bonus = min(to_float(row.get("area_m2"), 0) / 1000, 20)
    coverage_bonus = min(to_float(row.get("coverage_pct"), 0) * 2, 20)
    return float(base + area_bonus + coverage_bonus)


def clean_row(row: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {k: clean_value(v) for k, v in row.items()}
    cleaned = apply_display_risk(cleaned)
    cleaned["risk_score"] = infer_display_risk_score(cleaned)
    return cleaned


def uploaded_spills_file() -> Path:
    out = BASE_DIR / "generated_upload_spills"
    out.mkdir(exist_ok=True)
    return out / "spills.jsonl"


def _uploaded_spill_key(row: Dict[str, Any]) -> str:
    return str(row.get("filename") or row.get("spill_id") or row.get("id") or "").strip()


def _store_uploaded_spill(row: Dict[str, Any]) -> Dict[str, Any]:
    stored = clean_row({
        "id": row.get("id") or row.get("filename") or f"UPLOAD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "spill_id": row.get("filename") or row.get("id") or "",
        "filename": row.get("filename") or row.get("spill_id") or row.get("id") or "",
        "latitude": row.get("latitude", 0.0),
        "longitude": row.get("longitude", 0.0),
        "area_m2": row.get("area_m2", 0.0),
        "coverage_pct": row.get("coverage_pct", 0.0),
        "distance_to_land_km": row.get("distance_to_land_km", 0.0),
        "distance_to_coral_km": row.get("distance_to_coral_km", 0.0),
        "final_risk_level": row.get("final_risk_level") or row.get("risk_level") or "Low",
        "risk_level": row.get("final_risk_level") or row.get("risk_level") or "Low",
        "created_at": row.get("processed_at") or datetime.utcnow().isoformat(),
        "source_image_path": row.get("saved_path"),
        "predicted_mask_path": None,
        "upload_source": row.get("source") or "uploaded_analysis",
        "upload_message": row.get("message") or "",
    })
    with uploaded_spills_file().open("a", encoding="utf-8") as f:
        f.write(json.dumps(stored, ensure_ascii=False) + "\n")
    return stored


def _load_uploaded_spills() -> List[Dict[str, Any]]:
    path = uploaded_spills_file()
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for line in reversed(path.read_text(encoding="utf-8", errors="ignore").splitlines()):
        if not line.strip():
            continue
        try:
            row = clean_row(json.loads(line))
        except Exception:
            continue
        key = _uploaded_spill_key(row)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(row)
    return rows


def _merged_spill_records(risk: Optional[str] = "all") -> List[Dict[str, Any]]:
    """مصدر التسربات: PostgreSQL فقط (جدول SPILLS_TABLE)."""
    try:
        return get_spill_records(limit=None, risk=risk or "all")
    except Exception:
        return []


def _total_spill_count() -> int:
    return len(_merged_spill_records(risk="all"))


def _lookup_spill_row(filename: str) -> Optional[Dict[str, Any]]:
    """بحث حالة في PostgreSQL بالاسم أو المعرّف."""
    name = str(filename or "").strip()
    if not name:
        return None
    for key in (name, name if name.lower().endswith(".tif") else f"{name}.tif"):
        spill = get_spill_by_id(key)
        if spill:
            return spill
    return None


def _spill_record_matches_id(spill: Dict[str, Any], spill_id: str) -> bool:
    sid = unquote(str(spill_id or "")).strip()
    if not sid:
        return False
    sid_no_tif = sid[:-4] if sid.lower().endswith(".tif") else sid
    sid_tif = sid if sid.lower().endswith(".tif") else sid + ".tif"
    norm_key = _normalize_spill_key(sid)
    candidates = [
        str(spill.get("id") or ""),
        str(spill.get("spill_id") or ""),
        str(spill.get("filename") or ""),
    ]
    if sid in candidates or sid_no_tif in candidates or sid_tif in candidates:
        return True
    return bool(norm_key and norm_key in {_normalize_spill_key(c) for c in candidates if c})


def _find_uploaded_spill(spill_id: str) -> Optional[Dict[str, Any]]:
    """بحث في spills.jsonl فقط — بدون استدعاء get_spill_by_id (تجنّب تكرار لا نهائي)."""
    for spill in _load_uploaded_spills():
        if _spill_record_matches_id(spill, spill_id):
            return spill
    return None


# ============================================================
# Database helpers
# ============================================================


def ensure_reports_table() -> None:
    with get_engine().begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {table_ref(REPORTS_TABLE)} (
                id SERIAL PRIMARY KEY,
                report_id VARCHAR(120) UNIQUE,
                spill_id TEXT,
                filename TEXT,
                risk_level TEXT,
                language VARCHAR(10) DEFAULT 'ar',
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


def ensure_spills_table() -> None:
    with get_engine().begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {table_ref(SPILLS_TABLE)} (
                spill_id TEXT PRIMARY KEY,
                filename TEXT UNIQUE,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                area_m2 DOUBLE PRECISION,
                coverage_pct DOUBLE PRECISION,
                distance_to_land_km DOUBLE PRECISION,
                distance_to_coral_km DOUBLE PRECISION,
                land_proximity_class TEXT,
                coral_risk_class TEXT,
                final_risk_level TEXT,
                risk_level TEXT,
                risk_score DOUBLE PRECISION,
                analysis_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source_image_path TEXT,
                predicted_mask_path TEXT,
                area_px INTEGER
            )
        """))


def _save_spill_to_db(spill: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    ensure_spills_table()
    cols = set(get_columns(SPILLS_TABLE))

    lat = to_float(spill.get("latitude"), 0.0)
    lon = to_float(spill.get("longitude"), 0.0)
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        raise HTTPException(
            status_code=400,
            detail="This image does not contain usable coordinates, so no map point can be created yet.",
        )

    logical_values: Dict[str, Any] = {
        "spill_id": str(spill.get("spill_id") or spill.get("filename") or spill.get("id") or "").strip(),
        "filename": str(spill.get("filename") or spill.get("spill_id") or spill.get("id") or "").strip(),
        "latitude": lat,
        "longitude": lon,
        "area_m2": to_float(spill.get("area_m2"), 0.0),
        "coverage_pct": to_float(spill.get("coverage_pct"), 0.0),
        "distance_to_land_km": to_float(spill.get("distance_to_land_km"), 0.0),
        "distance_to_coral_km": to_float(spill.get("distance_to_coral_km"), 0.0),
        "land_proximity_class": spill.get("land_proximity_class") or "Unknown",
        "coral_risk_class": spill.get("coral_risk_class") or "Unknown",
        "final_risk_level": normalize_risk(spill.get("final_risk_level") or spill.get("risk_level")),
        "risk_level": normalize_risk(spill.get("final_risk_level") or spill.get("risk_level")),
        "risk_score": infer_risk_score(spill),
        "created_at": spill.get("processed_at") or spill.get("created_at") or datetime.utcnow().isoformat(),
        "source_image_path": spill.get("saved_path") or spill.get("source_image_path"),
        "predicted_mask_path": spill.get("predicted_mask_path"),
        "area_px": int(to_float(spill.get("area_px"), 0.0)),
    }

    if (
        logical_values["distance_to_land_km"] <= 0
        and logical_values["distance_to_coral_km"] <= 0
        and not (abs(lat) < 1e-9 and abs(lon) < 1e-9)
    ):
        proximity = compute_proximity_metrics(lat, lon)
        if proximity.get("distance_to_land_km") is not None:
            logical_values["distance_to_land_km"] = float(proximity["distance_to_land_km"])
        if proximity.get("distance_to_coral_km") is not None:
            logical_values["distance_to_coral_km"] = float(proximity["distance_to_coral_km"])
        logical_values["land_proximity_class"] = str(
            proximity.get("land_proximity_class") or logical_values["land_proximity_class"]
        )
        logical_values["coral_risk_class"] = str(
            proximity.get("coral_risk_class") or logical_values["coral_risk_class"]
        )

    column_candidates = {
        "spill_id": ["spill_id"],
        "filename": ["filename", "source_image", "image"],
        "latitude": ["latitude", "spill_centroid_lat", "centroid_lat", "center_lat"],
        "longitude": ["longitude", "spill_centroid_lon", "centroid_lon", "center_lon"],
        "area_m2": ["area_m2", "spill_area_m2"],
        "coverage_pct": ["coverage_pct", "coverage", "coverage_percent"],
        "distance_to_land_km": ["distance_to_land_km", "land_distance_km"],
        "distance_to_coral_km": ["distance_to_coral_km", "nearest_coral_distance_km", "coral_distance_km"],
        "land_proximity_class": ["land_proximity_class"],
        "coral_risk_class": ["coral_risk_class", "coral_proximity_class"],
        "final_risk_level": ["final_risk_level"],
        "risk_level": ["risk_level"],
        "risk_score": ["risk_score"],
        "created_at": ["created_at", "analysis_created_at", "detected_at", "processed_at"],
        "source_image_path": ["source_image_path", "source_image"],
        "predicted_mask_path": ["predicted_mask_path", "mask_path"],
        "area_px": ["area_px"],
    }

    db_values: Dict[str, Any] = {}
    for logical, candidates in column_candidates.items():
        col = first_existing(cols, *candidates)
        if col:
            db_values[col] = logical_values[logical]

    if not db_values:
        raise HTTPException(status_code=500, detail="Spill table is missing expected columns.")

    lookup_options: List[Tuple[Optional[str], Any]] = [
        (first_existing(cols, "spill_id"), logical_values["spill_id"]),
        (first_existing(cols, "filename"), logical_values["filename"]),
        (first_existing(cols, "source_image"), logical_values["filename"]),
        (first_existing(cols, "source_image_path"), logical_values["source_image_path"]),
    ]

    action = "created"
    with get_engine().begin() as conn:
        lookup_col: Optional[str] = None
        lookup_value: Any = None
        for candidate_col, candidate_value in lookup_options:
            if not candidate_col or candidate_value in (None, ""):
                continue
            exists = conn.execute(
                text(f"SELECT 1 FROM {table_ref(SPILLS_TABLE)} WHERE {q(candidate_col)} = :value LIMIT 1"),
                {"value": candidate_value},
            ).first()
            if exists:
                lookup_col = candidate_col
                lookup_value = candidate_value
                break

        if lookup_col:
            action = "updated"
            set_sql = ", ".join(f"{q(col)} = :{col}" for col in db_values.keys())
            params = {**db_values, "__lookup": lookup_value}
            conn.execute(
                text(f"""
                    UPDATE {table_ref(SPILLS_TABLE)}
                    SET {set_sql}
                    WHERE {q(lookup_col)} = :__lookup
                """),
                params,
            )
        else:
            columns_sql = ", ".join(q(col) for col in db_values.keys())
            values_sql = ", ".join(f":{col}" for col in db_values.keys())
            conn.execute(
                text(f"""
                    INSERT INTO {table_ref(SPILLS_TABLE)} ({columns_sql})
                    VALUES ({values_sql})
                """),
                db_values,
            )

    saved = get_spill_by_id(logical_values["spill_id"]) or get_spill_by_id(logical_values["filename"]) or clean_row(spill)
    return action, saved


def import_csv_to_db(csv_path: Path) -> int:
    if not csv_path.exists():
        raise FileNotFoundError(str(csv_path))

    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    if "spill_id" not in df.columns:
        if "filename" in df.columns:
            df.insert(0, "spill_id", df["filename"].astype(str))
        else:
            df.insert(0, "spill_id", [f"SP-{i + 1:05d}" for i in range(len(df))])

    if "latitude" not in df.columns and "spill_centroid_lat" in df.columns:
        df["latitude"] = df["spill_centroid_lat"]
    if "longitude" not in df.columns and "spill_centroid_lon" in df.columns:
        df["longitude"] = df["spill_centroid_lon"]

    schema, name = split_table_name(SPILLS_TABLE)
    df.to_sql(name=name, con=get_engine(), schema=schema, if_exists="replace", index=False)
    return int(len(df))


def merge_uploaded_spills_into_db() -> Dict[str, int]:
    """إعادة دمج التحليلات المحفوظة في JSONL إلى PostgreSQL بعد استيراد CSV."""
    created = 0
    updated = 0
    skipped = 0
    for row in _load_uploaded_spills():
        lat = to_float(row.get("latitude"), 0.0)
        lon = to_float(row.get("longitude"), 0.0)
        if abs(lat) < 1e-9 and abs(lon) < 1e-9:
            skipped += 1
            continue
        try:
            action, _saved = _save_spill_to_db(row)
            if action == "updated":
                updated += 1
            else:
                created += 1
        except Exception:
            skipped += 1
    return {"created": created, "updated": updated, "skipped": skipped}


def restore_spills_from_csv() -> Dict[str, Any]:
    csv_path = Path(os.getenv("CSV_PATH", "")).expanduser()
    if not str(csv_path) or not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    imported = import_csv_to_db(csv_path)
    merged = merge_uploaded_spills_into_db()
    total = count_spills()
    return {
        "status": "ok",
        "csv_path": str(csv_path),
        "rows_imported": imported,
        "uploads_merged": merged,
        "db_count": total,
        "api_count": _total_spill_count(),
    }


def _persist_analysis_to_db(spill: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    lat = to_float(spill.get("latitude"), 0.0)
    lon = to_float(spill.get("longitude"), 0.0)
    if abs(lat) < 1e-9 and abs(lon) < 1e-9:
        return None
    action, saved = _save_spill_to_db(spill)
    return {"action": action, "spill": saved}


def count_spills() -> int:
    if not table_exists(SPILLS_TABLE):
        return 0
    with get_engine().connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_ref(SPILLS_TABLE)}")).scalar() or 0)


def get_spill_records(
    limit: Optional[int] = 1200,
    offset: int = 0,
    risk: Optional[str] = "all",
) -> List[Dict[str, Any]]:
    if not table_exists(SPILLS_TABLE):
        return []

    cols = set(get_columns(SPILLS_TABLE))
    sql = f"SELECT {base_select(cols)} FROM {table_ref(SPILLS_TABLE)}"

    # Keep filtering in Python because some projects have risk_level, others have final_risk_level,
    # and others only infer risk from distance/area fields.
    sql += " ORDER BY risk_score DESC NULLS LAST, coverage_pct DESC NULLS LAST"

    params: Dict[str, Any] = {}
    if limit is not None:
        sql += " LIMIT :limit OFFSET :offset"
        params["limit"] = int(limit)
        params["offset"] = int(offset or 0)

    with get_engine().connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()

    records = [clean_row(dict(r)) for r in rows]
    if risk and str(risk).lower() != "all":
        target = normalize_display_risk_param(risk)
        records = [r for r in records if r.get("final_risk_level") == target]
    return records


def _normalize_spill_key(value: str) -> str:
    key = unquote(str(value or "")).strip().lower()
    if key.endswith(".tif") or key.endswith(".tiff"):
        key = Path(key).stem
    return key


def get_spill_by_id(spill_id: str) -> Optional[Dict[str, Any]]:
    if not spill_id:
        return None

    for spill in get_spill_records(limit=None):
        if _spill_record_matches_id(spill, spill_id):
            return spill
    uploaded = _find_uploaded_spill(spill_id)
    if uploaded:
        return uploaded
    return None


# ============================================================
# Report helpers
# ============================================================


def create_simple_report(spill: Dict[str, Any], language: str = "ar") -> str:
    risk = spill.get("final_risk_level") or "Low"
    filename = spill.get("filename") or spill.get("spill_id") or "Unknown"
    area = spill.get("area_m2")
    coverage = spill.get("coverage_pct")
    land = spill.get("distance_to_land_km")
    coral = spill.get("distance_to_coral_km")
    lat = spill.get("latitude")
    lon = spill.get("longitude")

    if (language or "ar").lower() == "ar":
        return f"""
# تقرير تسرب نفطي

## معلومات الحالة
- الملف: {filename}
- مستوى الخطورة: {risk}
- المساحة التقريبية: {area} م²
- نسبة التغطية: {coverage}%
- مركز التسرب: {lat}, {lon}
- المسافة عن اليابسة: {land} كم
- المسافة عن الشعاب المرجانية: {coral} كم

## قراءة أولية
هذه الحالة تحتاج تقييم حسب القرب من اليابسة والشعاب المرجانية وحجم البقعة. كلما قلت المسافة وارتفعت المساحة أو نسبة التغطية زادت أولوية الاستجابة.

## توصية مختصرة
ابدئي بتحديد اتجاه انتشار البقعة، ثم فعّلي الاحتواء الميكانيكي بالحواجز والكاشطات إذا كانت ظروف البحر مناسبة. إذا كانت الحالة قريبة من الشعاب المرجانية، تجنبي استخدام المشتتات الكيميائية إلا بعد موافقة جهة بيئية مختصة.
""".strip()

    return f"""
# Oil Spill Report

## Case Information
- File: {filename}
- Risk level: {risk}
- Approximate area: {area} m²
- Coverage: {coverage}%
- Spill centroid: {lat}, {lon}
- Distance to land: {land} km
- Distance to coral reefs: {coral} km

## Initial Reading
This case should be prioritized based on its proximity to land and coral reefs, plus the spill area and coverage percentage. Lower distance and higher coverage usually increase response priority.

## Quick Recommendation
Start by confirming drift direction, then deploy mechanical containment such as booms and skimmers when sea conditions allow. If the spill is near coral reefs, avoid chemical dispersants unless an environmental authority approves their use.
""".strip()


def _stored_risk_tier_for_reports_db(spill: Optional[Dict[str, Any]]) -> str:
    """يحفظ مستوى مخزّن (Critical/High/Medium/Low) وليس مستوى العرض — لتجنّب ظهور كل R- كمنخفض."""
    if not spill:
        return "Low"
    st = spill.get("stored_risk_level")
    if st and str(st).strip():
        return str(st).strip()
    return normalize_stored_risk(spill.get("risk_level") or spill.get("final_risk_level"))


def _merge_spill_metrics_into_report_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """مساحة الحالة + خطورة مخزّنة صحيحة لتقارير R- التي أُحفظ بها final_risk المعروض خطأً."""
    out = dict(row)
    key = str(out.get("spill_id") or out.get("filename") or "").strip()
    if not key:
        return out
    try:
        spill = get_spill_by_id(key)
    except Exception:
        spill = None
    if not spill:
        return out
    if to_float(out.get("area_m2")) <= 0:
        out["area_m2"] = to_float(spill.get("area_m2"))
    if to_float(out.get("coverage_pct")) <= 0:
        out["coverage_pct"] = to_float(spill.get("coverage_pct"))
    rid = str(out.get("report_id") or out.get("id") or "")
    if rid.startswith("R-"):
        st = spill.get("stored_risk_level") or normalize_stored_risk(
            spill.get("risk_level") or spill.get("final_risk_level")
        )
        if st:
            out["risk_level"] = st
    return out


def save_report(spill: Dict[str, Any], content: str, language: str) -> Dict[str, Any]:
    """إدراج تقرير مختصر في PostgreSQL.

    لم يعد يُستدعى من مسار التقرير الموحّد (LLM): المعروض للمستخدم هو LLM-* في JSONL فقط.
    """
    ensure_reports_table()
    report_id = f"R-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    created_at = datetime.utcnow().isoformat()

    with get_engine().begin() as conn:
        conn.execute(text(f"""
            INSERT INTO {table_ref(REPORTS_TABLE)}
            (report_id, spill_id, filename, risk_level, language, content)
            VALUES (:report_id, :spill_id, :filename, :risk_level, :language, :content)
        """), {
            "report_id": report_id,
            "spill_id": str(spill.get("spill_id") or spill.get("id") or spill.get("filename") or ""),
            "filename": spill.get("filename"),
            "risk_level": _stored_risk_tier_for_reports_db(spill),
            "language": language,
            "content": content,
        })

    return {
        "id": report_id,
        "report_id": report_id,
        "spill_id": str(spill.get("spill_id") or spill.get("id") or spill.get("filename") or ""),
        "filename": spill.get("filename"),
        "risk_level": _stored_risk_tier_for_reports_db(spill),
        "language": language,
        "created_at": created_at,
        "summary": content[:240],
        "content": content,
    }


# ============================================================
# App setup
# ============================================================

app = FastAPI(title="NaftScan / Rana Oil Spill Backend", version="1.1.0")

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "null",
]
origins = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(",") if o.strip()]
for origin in DEFAULT_ORIGINS:
    if origin not in origins:
        origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def refresh_rag_paths() -> None:
    cp_dir = Path(os.getenv("CP_PATH", str(BASE_DIR.parent))).expanduser()
    external_rag_dir = Path(os.getenv("EXTERNAL_RAG_PATH", str(cp_dir / "external_rag"))).expanduser()
    for path in [cp_dir, external_rag_dir]:
        if str(path) not in sys.path:
            sys.path.append(str(path))


refresh_rag_paths()

_SEARCH_AGENT_MODULE = None
_SEARCH_AGENT_FN = None
_SEARCH_AGENT_IMPORT_ERROR: Optional[str] = None
_DB_AGENT_MODULE = None
_DB_AGENT_IMPORT_ERROR: Optional[str] = None

TRUSTED_SEARCH_DOMAINS = {
    "imo.org",
    "itopf.org",
    "osrl.com",
    "noaa.gov",
    "epa.gov",
    "response.restoration.noaa.gov",
    "ncsc.gov.sa",
    "mewa.gov.sa",
    "meteo.gov.sa",
}


def _load_search_response_agent_module():
    global _SEARCH_AGENT_MODULE, _SEARCH_AGENT_FN, _SEARCH_AGENT_IMPORT_ERROR
    if _SEARCH_AGENT_MODULE is not None:
        return _SEARCH_AGENT_MODULE
    refresh_rag_paths()
    try:
        try:
            import external_rag.search_response_agent as search_response_agent  # type: ignore
        except Exception:
            import search_response_agent as search_response_agent  # type: ignore
        _SEARCH_AGENT_MODULE = search_response_agent
        _SEARCH_AGENT_FN = getattr(search_response_agent, "generate_response_plan_from_report", None)
        _SEARCH_AGENT_IMPORT_ERROR = None
        return _SEARCH_AGENT_MODULE
    except Exception as exc:
        _SEARCH_AGENT_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def _load_search_response_agent():
    mod = _load_search_response_agent_module()
    if mod is None:
        return None
    fn = getattr(mod, "generate_response_plan_from_report", None)
    if callable(fn):
        return fn
    return _SEARCH_AGENT_FN


def _load_database_agent_module():
    global _DB_AGENT_MODULE, _DB_AGENT_IMPORT_ERROR
    if _DB_AGENT_MODULE is not None:
        return _DB_AGENT_MODULE
    refresh_rag_paths()
    try:
        try:
            import external_rag.agent_module as agent_module  # type: ignore
        except Exception:
            import agent_module  # type: ignore
        _DB_AGENT_MODULE = agent_module
        _DB_AGENT_IMPORT_ERROR = None
        return _DB_AGENT_MODULE
    except Exception as exc:
        _DB_AGENT_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def _search_agent_status() -> Tuple[bool, str]:
    if not os.getenv("GROQ_API_KEY"):
        return False, "missing_groq_api_key"
    if not os.getenv("TAVILY_API_KEY"):
        return False, "missing_tavily_api_key"
    fn = _load_search_response_agent()
    if not callable(fn):
        return False, _SEARCH_AGENT_IMPORT_ERROR or "search_agent_unavailable"
    return True, "ready"


def _search_response_agent_cached(report_text: str) -> Dict[str, Any]:
    enabled, status = _search_agent_status()
    if not enabled:
        return {"status": status, "plan": None}

    fn = _load_search_response_agent()
    if not callable(fn):
        return {"status": _SEARCH_AGENT_IMPORT_ERROR or "search_agent_unavailable", "plan": None}

    try:
        plan = fn(report_text)
        cleaned = str(plan or "").strip()
        if not cleaned:
            return {"status": "empty_search_plan", "plan": None}
        return {"status": "ready", "plan": cleaned}
    except Exception as exc:
        return {"status": f"{type(exc).__name__}: {exc}", "plan": None}


@app.on_event("startup")
def startup() -> None:
    print("\n=== NaftScan / Rana Oil Spill Backend starting ===")
    print("DB:", get_db_url(mask_password=True))
    print("SPILLS_TABLE:", SPILLS_TABLE)
    print("REPORTS_TABLE:", REPORTS_TABLE)
    print("CSV_PATH:", os.getenv("CSV_PATH"))
    print("CP_PATH:", os.getenv("CP_PATH"))

    ok, error = db_ping()
    if not ok:
        print("Database connection failed:", error)
        return

    ensure_reports_table()

    csv_env = os.getenv("CSV_PATH")
    csv_path = Path(csv_env).expanduser() if csv_env else None
    # مصدر البيانات: PostgreSQL فقط. استيراد CSV يدوي عبر POST /api/import-csv عند الحاجة.
    if env_bool("AUTO_IMPORT_CSV", False):
        current_count = count_spills()
        if current_count == 0 and csv_path and csv_path.exists():
            try:
                rows = import_csv_to_db(csv_path)
                merge_uploaded_spills_into_db()
                print(f"Imported CSV into empty DB: {rows} rows")
            except Exception as exc:
                print(f"CSV import failed: {exc}")
    print(f"Spill rows in database ({SPILLS_TABLE}): {count_spills()}")


# ============================================================
# Request models
# ============================================================

class ChatRequest(BaseModel):
    message: Optional[str] = None
    question: Optional[str] = None
    text: Optional[str] = None
    spill_id: Optional[str] = None
    language: Optional[str] = "ar"
    top_k: Optional[int] = 5


class ReportRequest(BaseModel):
    spill_id: str
    language: Optional[str] = "ar"


class SolutionsRequest(BaseModel):
    spill_id: str
    language: Optional[str] = "ar"


class SaveAnalysisRequest(BaseModel):
    id: Optional[str] = None
    filename: str
    source: Optional[str] = None
    message: Optional[str] = None
    saved_path: Optional[str] = None
    latitude: float
    longitude: float
    area_m2: float
    coverage_pct: float
    distance_to_land_km: float
    distance_to_coral_km: float
    final_risk_level: str
    processed_at: Optional[str] = None
    area_px: Optional[int] = None


def _gps_ratio_to_float(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (tuple, list)) and len(value) == 2:
            num, den = value
            den = float(den or 0)
            if den == 0:
                return None
            return float(num) / den
        return float(value)
    except Exception:
        return None


def _gps_dms_to_decimal(parts: Any, ref: str) -> Optional[float]:
    if not parts or len(parts) < 3:
        return None
    deg = _gps_ratio_to_float(parts[0])
    minute = _gps_ratio_to_float(parts[1])
    second = _gps_ratio_to_float(parts[2])
    if deg is None or minute is None or second is None:
        return None
    value = deg + (minute / 60.0) + (second / 3600.0)
    if str(ref or "").upper() in {"S", "W"}:
        value *= -1
    return value


def extract_image_coordinates(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()

    if suffix in {".tif", ".tiff"}:
        try:
            import rasterio
            from rasterio.transform import xy
            from rasterio.warp import transform as warp_transform

            with rasterio.open(path) as src:
                if not src.crs:
                    return {"latitude": None, "longitude": None, "coordinate_source": "missing_crs"}

                row = max((src.height - 1) / 2.0, 0)
                col = max((src.width - 1) / 2.0, 0)
                x, y = xy(src.transform, row, col, offset="center")

                if src.crs.is_geographic:
                    lon, lat = float(x), float(y)
                else:
                    xs, ys = warp_transform(src.crs, "EPSG:4326", [float(x)], [float(y)])
                    lon, lat = float(xs[0]), float(ys[0])

                if not math.isfinite(lat) or not math.isfinite(lon):
                    return {"latitude": None, "longitude": None, "coordinate_source": "invalid_transform"}
                if abs(lat) > 90 or abs(lon) > 180:
                    return {"latitude": None, "longitude": None, "coordinate_source": "out_of_range"}

                return {
                    "latitude": lat,
                    "longitude": lon,
                    "coordinate_source": "geotiff_metadata",
                    "coordinate_crs": str(src.crs),
                }
        except Exception as exc:
            return {
                "latitude": None,
                "longitude": None,
                "coordinate_source": "geotiff_read_failed",
                "coordinate_error": str(exc),
            }

    try:
        from PIL import Image, ExifTags

        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return {"latitude": None, "longitude": None, "coordinate_source": "no_embedded_coordinates"}

            gps_tag = next((tag for tag, name in ExifTags.TAGS.items() if name == "GPSInfo"), None)
            if gps_tag is None or gps_tag not in exif:
                return {"latitude": None, "longitude": None, "coordinate_source": "no_gps_exif"}

            raw_gps = exif.get(gps_tag)
            gps: Dict[str, Any] = {}
            for key, value in dict(raw_gps).items():
                gps_name = ExifTags.GPSTAGS.get(key, key)
                gps[gps_name] = value

            lat = _gps_dms_to_decimal(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef", "N"))
            lon = _gps_dms_to_decimal(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef", "E"))
            if lat is None or lon is None:
                return {"latitude": None, "longitude": None, "coordinate_source": "gps_exif_incomplete"}

            return {
                "latitude": lat,
                "longitude": lon,
                "coordinate_source": "image_exif_gps",
            }
    except Exception as exc:
        return {
            "latitude": None,
            "longitude": None,
            "coordinate_source": "image_metadata_unavailable",
            "coordinate_error": str(exc),
        }


def _classify_land_distance_m(distance_m: Optional[float]) -> str:
    if distance_m is None:
        return "Unknown"
    if distance_m <= 0:
        return "Touches land"
    if distance_m <= 1000:
        return "Very close"
    if distance_m <= 5000:
        return "Close"
    if distance_m < 20000:
        return "Far"
    return "Very far (>20 km)"


def _classify_coral_distance_m(distance_m: Optional[float]) -> str:
    if distance_m is None:
        return "Unknown"
    if distance_m <= 0:
        return "Touches coral reef"
    if distance_m <= 1000:
        return "Very close to coral"
    if distance_m <= 5000:
        return "Close to coral"
    if distance_m < 20000:
        return "Far from coral"
    return "Very far from coral (>20 km)"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _cp_root() -> Path:
    return Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP")).expanduser()


@lru_cache(maxsize=1)
def _reference_distance_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        for spill in get_spill_records(limit=None):
            lat = to_float(spill.get("latitude"), 0.0)
            lon = to_float(spill.get("longitude"), 0.0)
            if abs(lat) < 1e-9 and abs(lon) < 1e-9:
                continue
            rows.append(spill)
        if rows:
            return rows
    except Exception:
        pass

    # احتياطي قديم فقط إذا الجدول فارغ (لن يُستخدم عادةً)
    csv_path = os.getenv("CSV_PATH")
    candidate_paths: List[Path] = []
    if csv_path:
        p = Path(csv_path).expanduser()
        if p.exists():
            candidate_paths.append(p)

    cp = _cp_root()
    candidate_paths.extend(cp.rglob("spill_analysis_results_full.csv"))
    candidate_paths.extend(cp.rglob("*spill*analysis*results*.csv"))

    seen: set[Path] = set()
    for path in candidate_paths:
        if path in seen or not path.exists():
            continue
        seen.add(path)
        try:
            df = pd.read_csv(path)
        except Exception:
            continue

        for _, row in df.iterrows():
            data = row.to_dict()
            lat = None
            lon = None
            for key in ["latitude", "spill_centroid_lat", "center_lat", "centroid_lat"]:
                if key in data and data[key] == data[key]:
                    try:
                        lat = float(data[key])
                        break
                    except Exception:
                        pass
            for key in ["longitude", "spill_centroid_lon", "center_lon", "centroid_lon"]:
                if key in data and data[key] == data[key]:
                    try:
                        lon = float(data[key])
                        break
                    except Exception:
                        pass
            if lat is None or lon is None:
                continue
            rows.append(data)

        if rows:
            break
    return rows


def _estimate_proximity_from_reference(lat: float, lon: float) -> Dict[str, Any]:
    rows = _reference_distance_rows()
    if not rows:
        return {
            "distance_to_land_m": None,
            "distance_to_land_km": None,
            "land_proximity_class": "Unknown",
            "distance_to_coral_m": None,
            "distance_to_coral_km": None,
            "coral_risk_class": "Unknown",
            "proximity_source": "reference_unavailable",
        }

    nearest = None
    nearest_km = None
    for row in rows:
        row_lat = pick_number(row, ["latitude", "spill_centroid_lat", "center_lat", "centroid_lat"], None)
        row_lon = pick_number(row, ["longitude", "spill_centroid_lon", "center_lon", "centroid_lon"], None)
        if row_lat is None or row_lon is None:
            continue
        d = _haversine_km(lat, lon, float(row_lat), float(row_lon))
        if nearest_km is None or d < nearest_km:
            nearest_km = d
            nearest = row

    if not nearest:
        return {
            "distance_to_land_m": None,
            "distance_to_land_km": None,
            "land_proximity_class": "Unknown",
            "distance_to_coral_m": None,
            "distance_to_coral_km": None,
            "coral_risk_class": "Unknown",
            "proximity_source": "reference_not_found",
        }

    land_m = pick_number(nearest, ["distance_to_land_m"], None)
    land_km = pick_number(nearest, ["distance_to_land_km"], None if land_m is None else land_m / 1000)
    coral_m = pick_number(nearest, ["distance_to_coral_m", "nearest_coral_distance_m"], None)
    coral_km = pick_number(nearest, ["distance_to_coral_km"], None if coral_m is None else coral_m / 1000)

    return {
        "distance_to_land_m": land_m,
        "distance_to_land_km": land_km,
        "land_proximity_class": pick_text(nearest, ["land_proximity_class"], _classify_land_distance_m(land_m)),
        "distance_to_coral_m": coral_m,
        "distance_to_coral_km": coral_km,
        "coral_risk_class": pick_text(nearest, ["coral_risk_class", "coral_proximity_class"], _classify_coral_distance_m(coral_m)),
        "proximity_source": "nearest_reference_spill",
        "reference_distance_km": nearest_km,
    }


@lru_cache(maxsize=1)
def _load_union_layer_backend(kind: str):
    cp = _cp_root()
    target_crs = "EPSG:3857"
    if kind == "land":
        path = cp / "ne_10m_land" / "ne_10m_land.shp"
        default_crs = None
    else:
        path = cp / "Global_Coral_Reef_Points" / "Global_Coral_Reef_Points.shp"
        default_crs = None

    if not path.exists():
        return None

    import geopandas as gpd

    gdf = gpd.read_file(path)
    if gdf.empty:
        return None
    if gdf.crs is None and default_crs is not None:
        gdf = gdf.set_crs(default_crs)
    if gdf.crs is None:
        return None
    gdf = gdf.to_crs(target_crs)
    return gdf.union_all() if hasattr(gdf, "union_all") else gdf.unary_union


def compute_proximity_metrics(lat: float, lon: float) -> Dict[str, Any]:
    if not math.isfinite(lat) or not math.isfinite(lon) or (abs(lat) < 1e-9 and abs(lon) < 1e-9):
        return {
            "distance_to_land_m": None,
            "distance_to_land_km": None,
            "land_proximity_class": "Unknown",
            "distance_to_coral_m": None,
            "distance_to_coral_km": None,
            "coral_risk_class": "Unknown",
            "proximity_source": "no_coordinates",
        }

    try:
        from pyproj import Transformer
        from shapely.geometry import Point

        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        x, y = transformer.transform(lon, lat)
        point = Point(x, y)

        land_union = _load_union_layer_backend("land")
        coral_union = _load_union_layer_backend("coral")

        if land_union is not None and coral_union is not None:
            land_m = float(point.distance(land_union))
            coral_m = float(point.distance(coral_union))
            return {
                "distance_to_land_m": round(land_m, 2),
                "distance_to_land_km": round(land_m / 1000, 3),
                "land_proximity_class": _classify_land_distance_m(land_m),
                "distance_to_coral_m": round(coral_m, 2),
                "distance_to_coral_km": round(coral_m / 1000, 3),
                "coral_risk_class": _classify_coral_distance_m(coral_m),
                "proximity_source": "vector_layers",
            }
    except Exception:
        pass

    return _estimate_proximity_from_reference(lat, lon)


class RagChatRequest(BaseModel):
    message: Optional[str] = None
    question: Optional[str] = None
    query: Optional[str] = None
    top_k: int = 5


# ============================================================
# API endpoints
# ============================================================

@app.get("/")
def root() -> Dict[str, Any]:
    db_ok, error = db_ping()
    spill_count = 0
    if db_ok:
        try:
            spill_count = count_spills()
        except Exception as exc:
            error = str(exc)
            db_ok = False

    return {
        "name": "NaftScan / Rana Oil Spill Backend",
        "state": "live" if db_ok else "db_error",
        "status": {
            "database": db_ok,
            "model": False,
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "qwen": False,
        },
        "database": db_ok,
        "error": error,
        "spills_count": spill_count,
        "docs": "/docs",
        "endpoints": [
            "/api/spills",
            "/api/spills/{spill_id}",
            "/api/analyze-image",
            "/api/save-analysis",
            "/api/chat",
            "/api/generate-report",
            "/api/reports",
            "/api/rag/health",
            "/api/rag/ask",
        ],
    }


@app.get("/api/debug/db")
def debug_db() -> Dict[str, Any]:
    ok, error = db_ping()
    csv_path = os.getenv("CSV_PATH", "")
    info: Dict[str, Any] = {
        "db_url": get_db_url(mask_password=True),
        "database_ok": ok,
        "error": error,
        "csv_path": csv_path,
        "csv_exists": Path(csv_path).expanduser().exists() if csv_path else False,
        "spill_table": SPILLS_TABLE,
        "reports_table": REPORTS_TABLE,
    }

    if ok:
        try:
            info.update({
                "table_exists": table_exists(SPILLS_TABLE),
                "columns": get_columns(SPILLS_TABLE),
                "count": count_spills(),
                "sample": get_spill_records(limit=3),
            })
        except Exception as exc:
            info["table_error"] = str(exc)
    return info


@app.post("/api/import-csv")
def import_csv_endpoint() -> Dict[str, Any]:
    try:
        return restore_spills_from_csv()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/restore-spills")
def restore_spills_endpoint() -> Dict[str, Any]:
    """استعادة ~1200 حالة من CSV ودمج الرفوعات المحفوظة في قاعدة البيانات."""
    try:
        return restore_spills_from_csv()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/spills")
def api_spills(risk: str = "all", limit: int = 1200, offset: int = 0) -> Dict[str, Any]:
    try:
        rows = _merged_spill_records(risk=risk)
        total = len(rows)
        if limit is not None:
            rows = rows[offset: offset + limit]
        elif offset:
            rows = rows[offset:]
        return {"count": int(total), "spills": rows}
    except Exception as exc:
        return {"count": 0, "spills": [], "error": str(exc)}


@app.get("/api/spills/{spill_id}")
def read_spill(spill_id: str) -> Dict[str, Any]:
    try:
        spill = get_spill_by_id(spill_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not spill:
        raise HTTPException(status_code=404, detail="Spill not found")
    return spill



_DEEPLAB_MODEL = None


def get_deeplab_model():
    global _DEEPLAB_MODEL
    if _DEEPLAB_MODEL is not None:
        return _DEEPLAB_MODEL

    from tensorflow.keras.models import load_model

    model_path = os.getenv("DEEPLAB_MODEL_PATH")
    if not model_path:
        raise HTTPException(status_code=500, detail="DEEPLAB_MODEL_PATH is missing in .env")

    model_path = Path(model_path).expanduser()
    if not model_path.exists():
        raise HTTPException(status_code=500, detail=f"DeepLab model not found: {model_path}")

    _DEEPLAB_MODEL = load_model(str(model_path), compile=False)
    return _DEEPLAB_MODEL


def read_image_for_deeplab(path: Path, target_h: int, target_w: int, channels: int):
    import numpy as np
    from PIL import Image

    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        try:
            import rasterio
            with rasterio.open(path) as src:
                arr = src.read(1).astype("float32")
        except Exception:
            arr = np.array(Image.open(path).convert("L")).astype("float32")
    else:
        mode = "RGB" if channels == 3 else "L"
        img = Image.open(path).convert(mode).resize((target_w, target_h))
        arr = np.array(img).astype("float32")

    if arr.max() > 1:
        arr = arr / 255.0

    if arr.shape[0] != target_h or arr.shape[1] != target_w:
        arr = np.array(
            Image.fromarray((arr * 255).astype("uint8")).resize((target_w, target_h))
        ).astype("float32") / 255.0

    if channels == 3:
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        elif arr.shape[-1] != 3:
            arr = arr[..., :3]
    else:
        if arr.ndim == 2:
            arr = arr[..., None]
        else:
            arr = arr[..., :1]

    return arr[None, ...]



from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import os

_DEEPLAB_MODEL = None


def get_deeplab_model():
    global _DEEPLAB_MODEL
    if _DEEPLAB_MODEL is not None:
        return _DEEPLAB_MODEL

    from tensorflow.keras.models import load_model

    model_path = os.getenv("DEEPLAB_MODEL_PATH")
    if not model_path:
        raise HTTPException(status_code=500, detail="DEEPLAB_MODEL_PATH is missing in .env")

    model_path = Path(model_path).expanduser()
    if not model_path.exists():
        raise HTTPException(status_code=500, detail=f"DeepLab model not found: {model_path}")

    _DEEPLAB_MODEL = load_model(str(model_path), compile=False)
    return _DEEPLAB_MODEL


def _norm01(arr):
    import numpy as np
    arr = arr.astype("float32")
    mn = float(np.nanmin(arr))
    mx = float(np.nanmax(arr))
    if mx > mn:
        arr = (arr - mn) / (mx - mn)
    else:
        arr = arr * 0
    return arr


def read_image_for_deeplab(path: Path, target_h: int, target_w: int, channels: int):
    import numpy as np
    from PIL import Image

    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        try:
            import rasterio
            with rasterio.open(path) as src:
                arr = src.read(1).astype("float32")
        except Exception:
            arr = np.array(Image.open(path).convert("L")).astype("float32")
    else:
        mode = "RGB" if channels == 3 else "L"
        img = Image.open(path).convert(mode)
        arr = np.array(img).astype("float32")
        if arr.ndim == 3:
            arr = arr[..., 0]

    arr = _norm01(arr)

    if arr.shape[0] != target_h or arr.shape[1] != target_w:
        arr = np.array(
            Image.fromarray((arr * 255).astype("uint8")).resize((target_w, target_h))
        ).astype("float32") / 255.0

    base_preview = arr.copy()

    if channels == 3:
        x = np.stack([arr, arr, arr], axis=-1)
    else:
        x = arr[..., None]

    return x[None, ...], base_preview


def lookup_csv_row(filename: str):
    import pandas as pd

    csv_path = os.getenv("CSV_PATH")
    if not csv_path or not Path(csv_path).exists():
        return None

    df = pd.read_csv(csv_path)
    name = Path(filename).name

    for col in ["filename", "spill_id", "id", "source_image"]:
        if col in df.columns:
            hit = df[df[col].astype(str).str.strip() == name]
            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def pick_number(row, keys, default=0.0):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def pick_text(row, keys, default="Medium"):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            return str(row[k])
    return default


@app.get("/api/analyze-preview/{name:path}")
async def analyze_preview(name: str):
    from fastapi.responses import FileResponse

    upload_dir = Path(os.getenv("UPLOAD_DIR", str(Path(os.getenv("CP_PATH", ".")) / "backend_uploads")))
    file_path = (upload_dir / name).resolve()
    base = upload_dir.resolve()

    if not str(file_path).startswith(str(base)) or not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")

    return FileResponse(str(file_path))



from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import os

_DEEPLAB_MODEL = None


def get_deeplab_model():
    global _DEEPLAB_MODEL
    if _DEEPLAB_MODEL is not None:
        return _DEEPLAB_MODEL

    from tensorflow.keras.models import load_model

    model_path = os.getenv("DEEPLAB_MODEL_PATH")
    if not model_path:
        raise HTTPException(status_code=500, detail="DEEPLAB_MODEL_PATH is missing in .env")

    model_path = Path(model_path).expanduser()
    if not model_path.exists():
        raise HTTPException(status_code=500, detail=f"DeepLab model not found: {model_path}")

    _DEEPLAB_MODEL = load_model(str(model_path), compile=False)
    return _DEEPLAB_MODEL


def _norm01(arr):
    import numpy as np
    arr = arr.astype("float32")
    mn = float(np.nanmin(arr))
    mx = float(np.nanmax(arr))
    if mx > mn:
        arr = (arr - mn) / (mx - mn)
    else:
        arr = arr * 0
    return arr


def read_image_for_deeplab(path: Path, target_h: int, target_w: int, channels: int):
    import numpy as np
    from PIL import Image

    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        try:
            import rasterio
            with rasterio.open(path) as src:
                arr = src.read(1).astype("float32")
        except Exception:
            arr = np.array(Image.open(path).convert("L")).astype("float32")
    else:
        mode = "RGB" if channels == 3 else "L"
        img = Image.open(path).convert(mode)
        arr = np.array(img).astype("float32")
        if arr.ndim == 3:
            arr = arr[..., 0]

    arr = _norm01(arr)

    if arr.shape[0] != target_h or arr.shape[1] != target_w:
        arr = np.array(
            Image.fromarray((arr * 255).astype("uint8")).resize((target_w, target_h))
        ).astype("float32") / 255.0

    base_preview = arr.copy()

    if channels == 3:
        x = np.stack([arr, arr, arr], axis=-1)
    else:
        x = arr[..., None]

    return x[None, ...], base_preview


def lookup_csv_row(filename: str):
    import pandas as pd

    csv_path = os.getenv("CSV_PATH")
    if not csv_path or not Path(csv_path).exists():
        return None

    df = pd.read_csv(csv_path)
    name = Path(filename).name

    for col in ["filename", "spill_id", "id", "source_image"]:
        if col in df.columns:
            hit = df[df[col].astype(str).str.strip() == name]
            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def pick_number(row, keys, default=0.0):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def pick_text(row, keys, default="Medium"):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            return str(row[k])
    return default


@app.get("/api/analyze-preview/{name:path}")
async def analyze_preview(name: str):
    from fastapi.responses import FileResponse

    upload_dir = Path(os.getenv("UPLOAD_DIR", str(Path(os.getenv("CP_PATH", ".")) / "backend_uploads")))
    file_path = (upload_dir / name).resolve()
    base = upload_dir.resolve()

    if not str(file_path).startswith(str(base)) or not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")

    return FileResponse(
        str(file_path),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


_DEEPLAB_MODEL = None


def get_deeplab_model():
    global _DEEPLAB_MODEL
    if _DEEPLAB_MODEL is not None:
        return _DEEPLAB_MODEL

    from tensorflow.keras.models import load_model

    model_path = os.getenv("DEEPLAB_MODEL_PATH")
    if not model_path:
        raise HTTPException(status_code=500, detail="DEEPLAB_MODEL_PATH is missing in .env")

    model_path = Path(model_path).expanduser()
    if not model_path.exists():
        raise HTTPException(status_code=500, detail=f"DeepLab model not found: {model_path}")

    _DEEPLAB_MODEL = load_model(str(model_path), compile=False)
    return _DEEPLAB_MODEL


def _norm01(arr):
    import numpy as np
    arr = arr.astype("float32")
    mn = float(np.nanmin(arr))
    mx = float(np.nanmax(arr))
    if mx > mn:
        arr = (arr - mn) / (mx - mn)
    else:
        arr = arr * 0
    return arr


def lookup_csv_row(filename: str):
    import pandas as pd

    csv_path = os.getenv("CSV_PATH")
    if not csv_path or not Path(csv_path).exists():
        cp = Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP"))
        hits = list(cp.rglob("spill_analysis_results_full.csv")) + list(cp.rglob("*spill*analysis*results*.csv"))
        if not hits:
            return None
        csv_path = str(hits[0])

    df = pd.read_csv(csv_path)

    name = Path(filename).name.strip()
    stem = Path(filename).stem.strip()

    for col in ["filename", "spill_id", "id", "source_image", "source_image_path"]:
        if col in df.columns:
            series = df[col].astype(str).str.strip()
            basename = series.apply(lambda x: Path(x).name.strip())
            basestem = series.apply(lambda x: Path(x).stem.strip())

            hit = df[
                (series == name) |
                (series == stem) |
                (basename == name) |
                (basename == stem) |
                (basestem == stem)
            ]

            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def pick_number(row, keys, default=0.0):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def pick_text(row, keys, default=""):
    if not row:
        return default
    for k in keys:
        if k in row and row[k] == row[k]:
            value = str(row[k])
            if value.lower() != "nan":
                return value
    return default


def _max_analyze_side() -> int:
    return max(256, int(os.getenv("MAX_ANALYZE_SIDE", "2048")))


def read_any_tif_or_image(path: Path):
    """قراءة صورة للمعاينة/النموذج مع تصغير تلقائي لتجنّب نفاد الذاكرة."""
    import numpy as np
    from PIL import Image

    if not path.is_file():
        raise FileNotFoundError(f"الملف غير موجود: {path}")

    max_side = _max_analyze_side()
    suffix = path.suffix.lower()

    if suffix in [".tif", ".tiff"]:
        try:
            import rasterio
            from rasterio.enums import Resampling

            with rasterio.open(path) as src:
                h, w = int(src.height), int(src.width)
                if h < 1 or w < 1:
                    raise ValueError("أبعاد الصورة غير صالحة")
                scale = max(h / max_side, w / max_side, 1.0)
                if scale > 1.0:
                    out_h = max(1, int(round(h / scale)))
                    out_w = max(1, int(round(w / scale)))
                    arr = src.read(
                        1,
                        out_shape=(out_h, out_w),
                        resampling=Resampling.bilinear,
                    ).astype("float32")
                else:
                    arr = src.read(1).astype("float32")
                # أقنعة ثنائية (0/1): لا نحوّل الصفر إلى nodata وإلا يختفي التسرب
                unique = np.unique(arr[~np.isnan(arr)]) if arr.size else arr
                is_binary_mask = (
                    unique.size <= 2
                    and float(np.nanmax(arr)) <= 1.0
                    and float(np.nanmin(arr)) >= 0.0
                )
                if src.nodata is not None and not is_binary_mask:
                    arr = np.where(arr == src.nodata, np.nan, arr)
        except Exception:
            img = Image.open(path)
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            arr = np.array(img.convert("L")).astype("float32")
    else:
        img = Image.open(path)
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        arr = np.array(img.convert("L")).astype("float32")

    return _norm01(arr)


def resize_2d(arr, h, w):
    import numpy as np
    from PIL import Image

    if arr.shape[0] == h and arr.shape[1] == w:
        return arr

    return np.array(
        Image.fromarray((arr * 255).clip(0, 255).astype("uint8")).resize((w, h))
    ).astype("float32") / 255.0


def save_preview_images(upload_path: Path, base_preview, mask, upload_dir: Path):
    """معاينات مرئية: قناع تركوازي + تداخل واضح على الصورة الأصلية."""
    import numpy as np
    from PIL import Image

    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    prefix = f"{upload_path.stem}_{stamp}"

    original_name = f"{prefix}_original.png"
    mask_name = f"{prefix}_mask.png"
    overlay_name = f"{prefix}_overlay.png"

    base_preview = _norm01(base_preview)
    mask_arr = np.squeeze(np.asarray(mask, dtype=np.float32))
    if mask_arr.ndim == 3:
        mask_arr = mask_arr[..., -1]
    if float(mask_arr.max()) > 1.0 or float(mask_arr.min()) < 0.0:
        mask_arr = 1.0 / (1.0 + np.exp(-mask_arr))
    mask_arr = np.clip(mask_arr.astype("float32"), 0.0, 1.0)

    if mask_arr.shape != base_preview.shape:
        mask_arr = resize_2d(mask_arr, base_preview.shape[0], base_preview.shape[1])

    peak = float(mask_arr.max())
    if peak > 1e-6:
        strength = np.clip(mask_arr / peak, 0.0, 1.0)
        strength = np.power(strength, 0.55)
    else:
        strength = mask_arr * 0.0

    base_u8 = (base_preview * 255).clip(0, 255).astype("uint8")
    base_rgb = np.stack([base_u8, base_u8, base_u8], axis=-1)

    # SpillVision teal #0FA4A4
    teal = np.array([15, 164, 164], dtype=np.float32)
    navy = np.array([10, 24, 50], dtype=np.float32)

    vis_u8 = (strength * 255.0).clip(0, 255).astype("uint8")
    mask_rgb = np.zeros((*vis_u8.shape, 3), dtype=np.uint8)
    mask_rgb[..., 0] = navy[0]
    mask_rgb[..., 1] = navy[1]
    mask_rgb[..., 2] = navy[2]
    mask_rgb[..., 0] = np.clip(navy[0] + vis_u8 * (teal[0] - navy[0]) / 255.0, 0, 255).astype("uint8")
    mask_rgb[..., 1] = np.clip(navy[1] + vis_u8 * (teal[1] - navy[1]) / 255.0, 0, 255).astype("uint8")
    mask_rgb[..., 2] = np.clip(navy[2] + vis_u8 * (teal[2] - navy[2]) / 255.0, 0, 255).astype("uint8")

    alpha = (strength[..., None] * 0.68).clip(0.0, 0.68)
    teal_layer = np.zeros_like(base_rgb, dtype=np.float32)
    teal_layer[..., 0] = teal[0]
    teal_layer[..., 1] = teal[1]
    teal_layer[..., 2] = teal[2]
    overlay = base_rgb.astype(np.float32) * (1.0 - alpha) + teal_layer * alpha
    overlay = overlay.clip(0, 255).astype("uint8")

    Image.fromarray(base_rgb).save(upload_dir / original_name)
    Image.fromarray(mask_rgb).save(upload_dir / mask_name)
    Image.fromarray(overlay).save(upload_dir / overlay_name)

    return {
        "original_preview_url": f"/api/analyze-preview/{original_name}",
        "mask_preview_url": f"/api/analyze-preview/{mask_name}",
        "overlay_preview_url": f"/api/analyze-preview/{overlay_name}",
    }


def _run_deeplab_on_upload(upload_path: Path):
    """تشغيل DeepLab على الملف المرفوع — يُرجع المعاينة والقناع والثنائي."""
    import numpy as np

    model = get_deeplab_model()
    input_shape = model.input_shape
    target_h = int(input_shape[1]) if input_shape[1] else 512
    target_w = int(input_shape[2]) if input_shape[2] else 512
    channels = int(input_shape[3]) if len(input_shape) > 3 and input_shape[3] else 1

    x, base_preview = read_image_for_deeplab(upload_path, target_h, target_w, channels)
    pred = model.predict(x, verbose=0)

    mask = np.squeeze(pred).astype("float32")
    if mask.ndim == 3:
        mask = mask[..., -1]

    if float(mask.max()) > 1 or float(mask.min()) < 0:
        mask_for_calc = 1 / (1 + np.exp(-mask))
    else:
        mask_for_calc = mask

    threshold = float(os.getenv("PREDICTION_THRESHOLD", "0.01"))
    binary = mask_for_calc > threshold
    return base_preview, mask_for_calc, binary


def read_image_for_deeplab(path: Path, target_h: int, target_w: int, channels: int):
    import numpy as np

    arr = read_any_tif_or_image(path)
    arr = resize_2d(arr, target_h, target_w)

    if channels == 3:
        x = np.stack([arr, arr, arr], axis=-1)
    else:
        x = arr[..., None]

    return x[None, ...], arr


def _analysis_upload_dir() -> Path:
    upload_dir = Path(os.getenv("UPLOAD_DIR", str(Path(os.getenv("CP_PATH", ".")) / "backend_uploads")))
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _cp_root() -> Path:
    return Path(os.getenv("CP_PATH", str(Path(__file__).resolve().parent.parent)))


def _read_binary_mask_tif(path: Path):
    """قراءة قناع 0/1 بدون إتلاف خلفية الصفر."""
    import numpy as np
    import rasterio

    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
    if float(np.nanmax(arr)) > 1.5:
        return (arr >= 127).astype("float32")
    return (arr >= 0.5).astype("float32")


def _resolve_pipeline_mask_path(filename: str, row: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    name = Path(filename).name
    if row:
        mask_raw = pick_text(row, ["predicted_mask_path"], "")
        if mask_raw and Path(mask_raw).exists():
            return Path(mask_raw)
    for rel in (
        f"full_pipeline_output/predicted_masks/test/{name}",
        f"full_pipeline_output/predicted_masks/{name}",
    ):
        cand = _cp_root() / rel
        if cand.exists():
            return cand
    return None


def _resolve_pipeline_source_path(
    filename: str, row: Optional[Dict[str, Any]], upload_path: Path
) -> Path:
    name = Path(filename).name
    if row:
        src_raw = pick_text(row, ["source_image_path"], "")
        if src_raw and Path(src_raw).exists():
            return Path(src_raw)
    for cand in (_cp_root() / "Oil" / name, upload_path):
        if cand.exists():
            return cand
    return upload_path


def _normalize_lat_lon(lat: float, lon: float) -> Tuple[float, float]:
    """تصحيح lat/lon المقلوبة في بعض صفوف CSV (مثل 55° في عمود latitude)."""
    if abs(lat) > 90 and abs(lon) <= 90:
        lat, lon = lon, lat
    elif abs(lat) > 20 and abs(lon) < 20:
        lat, lon = lon, lat
    return lat, lon


def _risk_from_metrics(coverage_pct: float, area_m2: float) -> str:
    if coverage_pct >= 10 or area_m2 >= 100000:
        return "Critical"
    if coverage_pct >= 5 or area_m2 >= 50000:
        return "High"
    if coverage_pct > 0 or area_m2 > 0:
        return "Medium"
    return "NoSpill"


def _try_analyze_with_pipeline_mask(
    upload_path: Path, original_name: str, upload_dir: Path
) -> Optional[Dict[str, Any]]:
    """استخدام قناع المسار الكامل (2048px) إن وُجد — نفس نتيجة المشروع الأصلية."""
    import numpy as np

    csv_row = lookup_csv_row(original_name)
    db_row = _lookup_spill_row(original_name)
    row = csv_row or db_row
    mask_path = _resolve_pipeline_mask_path(original_name, row)
    if not mask_path:
        return None

    src_path = _resolve_pipeline_source_path(original_name, row, upload_path)
    base_preview = read_any_tif_or_image(src_path)
    mask_for_calc = _read_binary_mask_tif(mask_path)

    if mask_for_calc.shape != base_preview.shape:
        mask_for_calc = resize_2d(mask_for_calc, base_preview.shape[0], base_preview.shape[1])

    binary = mask_for_calc > 0.5
    previews = save_preview_images(upload_path, base_preview, mask_for_calc, upload_dir)

    area_px = int(binary.sum())
    pixel_area_m2 = float(os.getenv("PIXEL_AREA_M2", "0.25"))
    area_m2 = round(area_px * pixel_area_m2, 2)
    denom = max(int(binary.size), 1)
    coverage_pct = round((area_px / denom) * 100, 4)

    risk = pick_text(row, ["final_risk_level", "risk_level"], "") if row else ""
    if not risk:
        risk = _risk_from_metrics(float(coverage_pct), float(area_m2))

    latitude = longitude = 0.0
    coordinate_source = "pipeline_csv"
    if row:
        latitude = pick_number(row, ["latitude", "spill_centroid_lat"], 0.0)
        longitude = pick_number(row, ["longitude", "spill_centroid_lon"], 0.0)
    if abs(latitude) < 1e-9 and abs(longitude) < 1e-9:
        extracted = extract_image_coordinates(src_path)
        latitude = float(extracted.get("latitude") or 0.0)
        longitude = float(extracted.get("longitude") or 0.0)
        coordinate_source = str(extracted.get("coordinate_source") or "geotiff_metadata")
    latitude, longitude = _normalize_lat_lon(latitude, longitude)

    proximity = compute_proximity_metrics(latitude, longitude)
    spill_id = (
        pick_text(row, ["spill_id", "filename", "id"], Path(original_name).name)
        if row
        else Path(original_name).name
    )

    return {
        "id": spill_id,
        "filename": original_name,
        "source": "pipeline_mask",
        "message": "تم عرض قناع الكشف من المسار الكامل للمشروع (دقة 2048px) — نفس التسرب الواضح في المنتصف.",
        "saved_path": str(upload_path),
        "area_px": area_px,
        "area_m2": area_m2,
        "coverage_pct": coverage_pct,
        "final_risk_level": risk,
        "risk_level": risk,
        "latitude": latitude,
        "longitude": longitude,
        "distance_to_land_km": pick_number(
            row, ["distance_to_land_km"], float(proximity.get("distance_to_land_km") or 0.0)
        )
        if row
        else float(proximity.get("distance_to_land_km") or 0.0),
        "distance_to_coral_km": pick_number(
            row, ["distance_to_coral_km"], float(proximity.get("distance_to_coral_km") or 0.0)
        )
        if row
        else float(proximity.get("distance_to_coral_km") or 0.0),
        "land_proximity_class": pick_text(
            row, ["land_proximity_class"], str(proximity.get("land_proximity_class") or "Unknown")
        )
        if row
        else str(proximity.get("land_proximity_class") or "Unknown"),
        "coral_risk_class": pick_text(
            row,
            ["coral_risk_class", "coral_proximity_class"],
            str(proximity.get("coral_risk_class") or "Unknown"),
        )
        if row
        else str(proximity.get("coral_risk_class") or "Unknown"),
        "processed_at": datetime.utcnow().isoformat(),
        "coordinate_source": coordinate_source,
        "coordinate_crs": "EPSG:4326" if row else None,
        "coordinate_error": None,
        "proximity_source": proximity.get("proximity_source"),
        "predicted_mask_path": str(mask_path),
        "source_image_path": str(src_path),
        "debug_mask_min": float(mask_for_calc.min()),
        "debug_mask_max": float(mask_for_calc.max()),
        "debug_mask_mean": float(mask_for_calc.mean()),
        **previews,
    }


def _analyze_saved_upload(upload_path: Path, original_name: str) -> Dict[str, Any]:
    import numpy as np
    upload_dir = upload_path.parent

    pipeline_result = _try_analyze_with_pipeline_mask(upload_path, original_name, upload_dir)
    if pipeline_result:
        result = pipeline_result
    else:
        row = _lookup_spill_row(original_name)
        base_preview, mask_for_calc, binary = _run_deeplab_on_upload(upload_path)
        previews = save_preview_images(upload_path, base_preview, mask_for_calc, upload_dir)

        area_px = int(binary.sum())
        pixel_area_m2 = float(os.getenv("PIXEL_AREA_M2", "0.25"))
        area_m2 = round(area_px * pixel_area_m2, 2)
        denom = max(int(binary.size), 1)
        coverage_pct = round((area_px / denom) * 100, 2)
        risk = _risk_from_metrics(float(coverage_pct), float(area_m2))

        extracted_coords = extract_image_coordinates(upload_path)
        latitude = float(extracted_coords.get("latitude") or 0.0)
        longitude = float(extracted_coords.get("longitude") or 0.0)
        if row:
            lat_row = pick_number(row, ["latitude", "spill_centroid_lat"], 0.0)
            lon_row = pick_number(row, ["longitude", "spill_centroid_lon"], 0.0)
            if abs(latitude) < 1e-9 and abs(longitude) < 1e-9:
                latitude, longitude = lat_row, lon_row
        latitude, longitude = _normalize_lat_lon(latitude, longitude)
        proximity = compute_proximity_metrics(latitude, longitude)

        spill_id = f"UPLOAD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        source = "deeplab_model_live"
        message = "تم تحليل الصورة المرفوعة باستخدام DeepLab (صورة جديدة بدون قناع محفوظ)."
        if row:
            spill_id = pick_text(row, ["spill_id", "filename", "id"], spill_id)
            source = "deeplab_with_db"
            message = "تم تحليل الصورة بالنموذج المباشر مع بيانات إضافية من قاعدة البيانات."

        result = {
            "id": spill_id,
            "filename": original_name,
            "source": source,
            "message": message,
            "saved_path": str(upload_path),
            "area_px": area_px,
            "area_m2": area_m2,
            "coverage_pct": coverage_pct,
            "final_risk_level": risk,
            "risk_level": risk,
            "latitude": latitude,
            "longitude": longitude,
            "distance_to_land_km": float(proximity.get("distance_to_land_km") or 0.0),
            "distance_to_coral_km": float(proximity.get("distance_to_coral_km") or 0.0),
            "land_proximity_class": str(proximity.get("land_proximity_class") or "Unknown"),
            "coral_risk_class": str(proximity.get("coral_risk_class") or "Unknown"),
            "processed_at": datetime.utcnow().isoformat(),
            "coordinate_source": extracted_coords.get("coordinate_source"),
            "coordinate_crs": extracted_coords.get("coordinate_crs"),
            "coordinate_error": extracted_coords.get("coordinate_error"),
            "proximity_source": proximity.get("proximity_source"),
            "debug_mask_min": float(mask_for_calc.min()),
            "debug_mask_max": float(mask_for_calc.max()),
            "debug_mask_mean": float(mask_for_calc.mean()),
            **previews,
        }
    _store_uploaded_spill(result)
    db_save = _persist_analysis_to_db(result)
    if db_save:
        result["db_saved"] = True
        result["db_action"] = db_save.get("action")
        saved_row = db_save.get("spill") or {}
        if saved_row.get("final_risk_level"):
            result["final_risk_level"] = saved_row["final_risk_level"]
            result["risk_level"] = saved_row["final_risk_level"]
    else:
        result["db_saved"] = False
    return result


@app.post("/api/analyze-image")
async def analyze_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="لم يُرفع أي ملف.")
    suffix = Path(file.filename).suffix.lower()
    allowed = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملف غير مدعوم ({suffix}). المدعوم: {', '.join(sorted(allowed))}",
        )

    max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", str(80 * 1024 * 1024)))
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"حجم الصورة كبير جداً ({len(content) // (1024 * 1024)} MB). الحد الأقصى {max_bytes // (1024 * 1024)} MB.",
        )

    upload_dir = _analysis_upload_dir()
    upload_path = upload_dir / Path(file.filename).name
    upload_path.write_bytes(content)

    try:
        return _analyze_saved_upload(upload_path, file.filename)
    except HTTPException:
        raise
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception("analyze-image failed for %s", file.filename)
        raise HTTPException(
            status_code=400,
            detail=f"تعذّر تحليل الصورة «{file.filename}»: {exc}",
        ) from exc


@app.post("/api/save-analysis")
def save_analysis(req: SaveAnalysisRequest) -> Dict[str, Any]:
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    action, saved = _save_spill_to_db(payload)
    return {
        "ok": True,
        "action": action,
        "spill": saved,
    }


class SafeChatRequest(BaseModel):
    message: str
    spill_id: Optional[str] = None
    language: Optional[str] = "ar"
    top_k: Optional[int] = 5


def _safe_load_spills_df():
    import pandas as pd
    from pathlib import Path
    import os

    csv_path = os.getenv("CSV_PATH")
    if csv_path and Path(csv_path).exists():
        return pd.read_csv(csv_path)

    cp = Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP"))
    hits = list(cp.rglob("spill_analysis_results_full.csv")) + list(cp.rglob("*spill*analysis*results*.csv"))

    if hits:
        return pd.read_csv(hits[0])

    return pd.DataFrame()


def _safe_num(row, keys, default=0.0):
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def _safe_txt(row, keys, default="غير متوفر"):
    for k in keys:
        if k in row and row[k] == row[k]:
            v = str(row[k])
            if v.lower() != "nan":
                return v
    return default


def _row_to_ar_summary(row):
    filename = _safe_txt(row, ["filename", "spill_id", "id"], "غير معروف")
    risk = _safe_txt(row, ["final_risk_level", "risk_level"], "غير متوفر")
    area = _safe_num(row, ["area_m2"], 0.0)
    coverage = _safe_num(row, ["coverage_pct"], 0.0)
    land = _safe_num(row, ["distance_to_land_km"], 0.0)
    coral = _safe_num(row, ["distance_to_coral_km"], 0.0)
    lat = _safe_num(row, ["latitude", "spill_centroid_lat"], 0.0)
    lon = _safe_num(row, ["longitude", "spill_centroid_lon"], 0.0)

    return (
        f"الحالة {filename}: مستوى الخطورة {risk}، "
        f"مساحة التسرب {area:,.2f} م²، نسبة التغطية {coverage:.2f}%، "
        f"الموقع التقريبي {lat:.4f}°,{lon:.4f}°، "
        f"المسافة من اليابسة {land:.2f} كم، والمسافة من الشعاب {coral:.2f} كم."
    )



try:
    SafeChatRequest
except NameError:
    class SafeChatRequest(BaseModel):
        message: str
        spill_id: Optional[str] = None
        language: Optional[str] = "ar"
        top_k: Optional[int] = 5


def _hybrid_load_spills_df():
    import pandas as pd
    from pathlib import Path
    import os

    csv_path = os.getenv("CSV_PATH")
    if csv_path and Path(csv_path).exists():
        return pd.read_csv(csv_path)

    cp = Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP"))
    hits = list(cp.rglob("spill_analysis_results_full.csv")) + list(cp.rglob("*spill*analysis*results*.csv"))

    if hits:
        return pd.read_csv(hits[0])

    return pd.DataFrame()


def _hybrid_num(row, keys, default=0.0):
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def _hybrid_txt(row, keys, default="غير متوفر"):
    for k in keys:
        if k in row and row[k] == row[k]:
            v = str(row[k])
            if v.lower() != "nan":
                return v
    return default


def _hybrid_find_row(df, spill_id):
    from pathlib import Path

    if df.empty or not spill_id:
        return None

    target = Path(str(spill_id)).name
    target_stem = Path(str(spill_id)).stem

    for col in ["filename", "spill_id", "id", "source_image", "source_image_path"]:
        if col in df.columns:
            series = df[col].astype(str)
            hit = df[
                (series == target) |
                (series == target_stem) |
                (series.apply(lambda x: Path(x).name) == target) |
                (series.apply(lambda x: Path(x).stem) == target_stem)
            ]
            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def _hybrid_row_summary(row):
    filename = _hybrid_txt(row, ["filename", "spill_id", "id"], "غير معروف")
    risk = _hybrid_txt(row, ["final_risk_level", "risk_level"], "غير متوفر")
    area = _hybrid_num(row, ["area_m2"], 0.0)
    coverage = _hybrid_num(row, ["coverage_pct"], 0.0)
    land = _hybrid_num(row, ["distance_to_land_km"], 0.0)
    coral = _hybrid_num(row, ["distance_to_coral_km"], 0.0)
    lat = _hybrid_num(row, ["latitude", "spill_centroid_lat"], 0.0)
    lon = _hybrid_num(row, ["longitude", "spill_centroid_lon"], 0.0)

    return (
        f"الحالة {filename}: مستوى الخطورة {risk}، "
        f"مساحة التسرب {area:,.2f} م²، نسبة التغطية {coverage:.2f}%، "
        f"الموقع التقريبي {lat:.4f}°,{lon:.4f}°، "
        f"المسافة من اليابسة {land:.2f} كم، والمسافة من الشعاب {coral:.2f} كم."
    )


def _hybrid_compare_spills(df, top_k=5):
    import pandas as pd

    work = df.copy()

    for col in ["risk_score", "area_m2", "coverage_pct", "distance_to_land_km", "distance_to_coral_km"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)

    # نعطي أفضلية للحالات الأخطر، ثم الأقرب لليابسة/الشعاب، ثم الأكبر مساحة
    work["proximity_priority"] = (20 - work["distance_to_land_km"]).clip(lower=0) + (20 - work["distance_to_coral_km"]).clip(lower=0)

    top = work.sort_values(
        by=["risk_score", "proximity_priority", "area_m2", "coverage_pct"],
        ascending=[False, False, False, False]
    ).head(int(top_k or 5))

    lines = []
    for _, row in top.iterrows():
        lines.append("- " + _hybrid_row_summary(row.to_dict()))

    return (
        "قارنت الحالات حسب درجة الخطورة، والقرب من اليابسة/الشعاب، ثم مساحة التسرب:\n\n"
        + "\n".join(lines)
        + "\n\nالتوصية من الداتا: الأولوية للحالات الأعلى خطورة والأقرب للمناطق الحساسة، خصوصًا إذا كانت قريبة من اليابسة أو الشعاب."
    )


def _hybrid_simple_rag(message: str, max_chunks: int = 3):
    import os
    import re
    from pathlib import Path

    cp = Path(os.getenv("CP_PATH", "/Users/rana/Documents/tuwaiq/CP"))
    rag_env = os.getenv("EXTERNAL_RAG_PATH", "")

    search_dirs = []
    if rag_env:
        search_dirs.append(Path(rag_env))
    search_dirs += [
        cp / "external_rag",
        cp / "final_html_reports",
        cp / "spill_reports_test",
    ]

    files = []
    for d in search_dirs:
        if d.exists():
            files += list(d.rglob("*.txt"))
            files += list(d.rglob("*.md"))
            files += list(d.rglob("*.html"))

    if not files:
        return ""

    q = message.lower()
    q_tokens = set(re.findall(r"[\w\u0600-\u06FF]+", q))
    chunks = []

    for f in files[:200]:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue

        text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        if len(text) < 80:
            continue

        parts = re.split(r"(?<=[.!؟])\s+|\n+", text)
        for part in parts:
            part = part.strip()
            if len(part) < 120:
                continue
            part_tokens = set(re.findall(r"[\w\u0600-\u06FF]+", part.lower()))
            score = len(q_tokens & part_tokens)

            boost_words = ["تنظيف", "احتواء", "استجابة", "الشعاب", "اليابسة", "حواجز", "تسرب", "نفطي", "خطة", "مخاطر"]
            score += sum(2 for w in boost_words if w in part)

            if score > 0:
                chunks.append((score, f.name, part[:900]))

    chunks.sort(reverse=True, key=lambda x: x[0])

    if not chunks:
        return ""

    selected = chunks[:max_chunks]
    out = []
    for score, name, text in selected:
        out.append(f"- من {name}: {text}")

    return "\n".join(out)


def _hybrid_response_guide():
    return (
        "خطة الاستجابة المقترحة:\n"
        "1. تحديد اتجاه انتشار التسرب باستخدام الرياح والتيارات البحرية.\n"
        "2. وضع حواجز احتواء عائمة إذا كانت ظروف البحر تسمح.\n"
        "3. إعطاء أولوية عالية إذا كان التسرب قريبًا من اليابسة أو الشعاب المرجانية.\n"
        "4. استخدام الكشط السطحي أو مواد الامتصاص حسب نوع النفط وحالة البحر.\n"
        "5. تجنب المشتتات الكيميائية قرب الشعاب إلا بعد تقييم بيئي واضح.\n"
        "6. متابعة الحالة بالصور والقياسات وتحديث مستوى الخطورة باستمرار."
    )


def _hybrid_route(message: str, has_spill_id: bool = False):
    msg = (message or "").lower()

    # كلمات تدل أن السؤال يحتاج أرقام من CSV/DB
    data_words = [
        "قارن", "مقارنة", "اخطر", "أخطر", "اعلى", "أعلى",
        "مساحة", "نسبة", "تغطية", "المسافة", "كم", "قرب",
        "احداثيات", "إحداثيات", "مركز", "risk", "area", "distance", "compare"
    ]

    # كلمات تدل أن السؤال يحتاج تفسير/حلول من RAG أو دليل الاستجابة
    rag_words = [
        "كيف", "حل", "حلول", "تنظيف", "استجابة", "خطة", "توصية", "تعامل",
        "ماذا", "اجراء", "إجراء", "احتواء", "مخاطر", "اشرح", "شرح",
        "recommend", "solution", "clean", "explain"
    ]

    wants_data = any(w.lower() in msg for w in data_words)
    wants_rag = any(w.lower() in msg for w in rag_words)

    # إذا فيه حالة مختارة والسؤال يطلب شرح/خطة/مخاطر، نحتاج الاثنين:
    # الداتا لأرقام الحالة + RAG للحلول والتفسير
    if has_spill_id and wants_rag:
        return "hybrid"

    if wants_data and wants_rag:
        return "hybrid"
    if wants_data:
        return "data"
    if wants_rag:
        return "rag"
    return "general"



class ChatHistoryItem(BaseModel):
    role: str
    content: str
    context_spill_id: Optional[str] = None
    intent: Optional[str] = None
    source_used: Optional[str] = None
    resolved_spill_id: Optional[str] = None


class SmartChatRequest(BaseModel):
    message: str
    spill_id: Optional[str] = None
    compare_spill_ids: Optional[List[str]] = None
    language: Optional[str] = "ar"
    top_k: Optional[int] = 5
    history: Optional[List[ChatHistoryItem]] = None


ChatHistoryItem.model_rebuild()
SmartChatRequest.model_rebuild()


def _chat_load_df():
    import pandas as pd

    # نفس مصدر /api/spills — PostgreSQL فقط
    try:
        rows = _merged_spill_records(risk="all")
        if rows:
            return pd.DataFrame(rows)
    except Exception:
        pass

    return pd.DataFrame()


def _n(row, keys, default=0.0):
    for k in keys:
        if k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def _t(row, keys, default="غير متوفر"):
    for k in keys:
        if k in row and row[k] == row[k]:
            v = str(row[k])
            if v.lower() != "nan":
                return v
    return default


def _find_spill(df, spill_id):
    from pathlib import Path

    if df.empty or not spill_id:
        return None

    def _candidates(value: Any) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        items = {
            raw,
            Path(raw).name,
            Path(raw).stem,
            raw.replace("\\", "/").split("/")[-1],
        }
        lower = raw.lower()
        if lower.startswith("tif.") and len(raw) > 4:
            items.add(f"{raw[4:]}.tif")
        if lower.endswith(".tif"):
            items.add(lower)
            items.add(Path(lower).stem)
        digits = "".join(re.findall(r"\d+", raw))
        if digits:
            items.add(digits)
            items.add(f"{digits}.tif")
            items.add(digits.lstrip("0") or "0")
        return [item for item in items if item]

    wanted = {str(item).lower() for item in _candidates(spill_id)}

    for col in ["filename", "spill_id", "id", "source_image", "source_image_path"]:
        if col in df.columns:
            series = df[col].astype(str)
            hit = df[series.apply(lambda x: bool(wanted.intersection({c.lower() for c in _candidates(x)})))]
            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def _selected_summary(row, lang="ar"):
    is_ar = (lang or "ar").lower() == "ar"
    filename = _t(row, ["filename", "spill_id", "id"], "غير معروف" if is_ar else "unknown")
    risk = _t(row, ["final_risk_level", "risk_level"], "غير متوفر" if is_ar else "N/A")
    area = _n(row, ["area_m2"])
    coverage = _n(row, ["coverage_pct"])
    land = _n(row, ["distance_to_land_km"])
    coral = _n(row, ["distance_to_coral_km"])
    lat = _n(row, ["latitude", "spill_centroid_lat"])
    lon = _n(row, ["longitude", "spill_centroid_lon"])

    if is_ar:
        return (
            f"الحالة {filename} خطورتها {risk}. "
            f"مساحة التسرب {area:,.2f} م²، ونسبة التغطية {coverage:.2f}%. "
            f"الموقع التقريبي {lat:.4f}°,{lon:.4f}°. "
            f"المسافة من اليابسة {land:.2f} كم، ومن الشعاب {coral:.2f} كم."
        )

    return (
        f"Case {filename} — risk level: {risk}. "
        f"Spill area {area:,.2f} m², coverage {coverage:.2f}%. "
        f"Approximate location {lat:.4f}°,{lon:.4f}°. "
        f"Distance to land {land:.2f} km, distance to coral {coral:.2f} km."
    )


def _environment_answer(row, question, lang="ar"):
    is_ar = (lang or "ar").lower() == "ar"
    risk = _t(row, ["final_risk_level", "risk_level"], "غير متوفر" if is_ar else "N/A")
    area = _n(row, ["area_m2"])
    coverage = _n(row, ["coverage_pct"])
    land = _n(row, ["distance_to_land_km"])
    coral = _n(row, ["distance_to_coral_km"])

    high_risk = risk.upper() in ["CRITICAL", "HIGH"] or coral <= 2 or land <= 2

    if is_ar:
        severity = "مرتفعة جدًا" if high_risk else "متوسطة"
        return (
            f"تحليل التأثير البيئي للحالة المختارة:\n\n"
            f"- مستوى الخطورة على الكائنات البحرية: {severity}.\n"
            f"- السبب: التسرب يغطي {coverage:.2f}% بمساحة تقريبية {area:,.2f} م².\n"
            f"- المسافة من اليابسة {land:.2f} كم، والمسافة من الشعاب {coral:.2f} كم.\n\n"
            f"الأثر المتوقع على الأسماك والحياة البحرية:\n"
            f"1. قد يقل الأكسجين المتاح قرب سطح الماء إذا انتشر النفط على مساحة واسعة.\n"
            f"2. الأسماك الصغيرة واليرقات أكثر حساسية لأنها تبقى قرب السطح أو المناطق الساحلية.\n"
            f"3. إذا كان التسرب قريبًا من الشعاب، فالخطر أعلى لأن الشعاب بيئة حضانة وتغذية لكثير من الكائنات.\n"
            f"4. قد تتأثر السلسلة الغذائية إذا وصل النفط إلى العوالق أو الكائنات الصغيرة.\n\n"
            f"التوصية:\n"
            f"- ابدئي باحتواء التسرب بالحواجز العائمة إذا كانت حالة البحر تسمح.\n"
            f"- امنعي وصول النفط للشعاب أو الساحل أولًا.\n"
            f"- استخدمي الكشط السطحي أو مواد الامتصاص، وتجنبي المشتتات الكيميائية قرب الشعاب إلا بتقييم بيئي.\n"
            f"- راقبي اتجاه الانتشار بالرياح والتيارات."
        )

    severity = "very high" if high_risk else "moderate"
    return (
        f"Environmental impact analysis for the selected case:\n\n"
        f"- Risk to marine life: {severity}.\n"
        f"- Reason: the spill covers {coverage:.2f}% with an approximate area of {area:,.2f} m².\n"
        f"- Distance to land: {land:.2f} km. Distance to coral: {coral:.2f} km.\n\n"
        f"Expected impact on fish and marine life:\n"
        f"1. Surface oxygen may drop if the slick spreads over a wide area.\n"
        f"2. Juvenile fish and larvae are most sensitive — they stay near the surface and shoreline.\n"
        f"3. If the spill is near reefs, risk is higher — reefs are nurseries and feeding grounds.\n"
        f"4. The food chain can be disrupted if oil reaches plankton or smaller organisms.\n\n"
        f"Recommendation:\n"
        f"- Begin containment with floating booms if sea state allows.\n"
        f"- Prioritize protecting reefs and the shoreline first.\n"
        f"- Use surface skimming or sorbents; avoid chemical dispersants near reefs without environmental assessment.\n"
        f"- Track drift using wind and current data."
    )


def _risk_rank_series(df):
    import pandas as pd

    if "final_risk_level" in df.columns:
        series = df["final_risk_level"]
    elif "risk_level" in df.columns:
        series = df["risk_level"]
    else:
        return pd.Series([99] * len(df), index=df.index)
    rank_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    return series.astype(str).str.upper().map(rank_map).fillna(99)


def _lowest_risk_answer(df, top_k=5, lang="ar"):
    import pandas as pd

    is_ar = (lang or "ar").lower() == "ar"
    work = _prepare_aggregate_df(df)
    work["_risk_rank"] = _risk_rank_series(work)
    bottom = work.sort_values(
        by=["_risk_rank", "risk_score", "area_m2"],
        ascending=[True, True, True],
    ).head(int(top_k or 5))

    lines = []
    for _, r in bottom.iterrows():
        lines.append("- " + _selected_summary(r.to_dict(), lang))

    if is_ar:
        return (
            f"أقل {len(lines)} حالات خطورة في البيانات المتاحة:\n\n"
            + "\n".join(lines)
            + "\n\nملاحظة: الترتيب يعتمد على مستوى الخطورة (Low → Critical) ثم درجة المخاطر والمساحة."
        )
    return (
        f"The {len(lines)} lowest-risk spill cases in the available data:\n\n"
        + "\n".join(lines)
        + "\n\nNote: ranked by risk level (Low → Critical), then risk score and area."
    )


def _compare_answer(df, top_k=5, lang="ar"):
    import pandas as pd
    is_ar = (lang or "ar").lower() == "ar"

    work = df.copy()
    for col in ["risk_score", "area_m2", "coverage_pct", "distance_to_land_km", "distance_to_coral_km"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)

    work["sensitive_priority"] = (20 - work["distance_to_land_km"]).clip(lower=0) + (20 - work["distance_to_coral_km"]).clip(lower=0)

    top = work.sort_values(
        by=["risk_score", "sensitive_priority", "area_m2"],
        ascending=[False, False, False]
    ).head(int(top_k or 5))

    lines = []
    for _, r in top.iterrows():
        lines.append("- " + _selected_summary(r.to_dict(), lang))

    if is_ar:
        return (
            "قارنت الحالات حسب الخطورة، والقرب من اليابسة والشعاب، وحجم التسرب:\n\n"
            + "\n".join(lines)
            + "\n\nالتوصية: الأولوية للحالات الأقرب للمناطق الحساسة، خصوصًا الشعاب والسواحل، ثم الأكبر مساحة."
        )

    return (
        "Cases ranked by risk, proximity to land/coral, and spill size:\n\n"
        + "\n".join(lines)
        + "\n\nRecommendation: prioritize cases closest to sensitive areas (reefs and shoreline), then by area."
    )


def _is_rag_knowledge_question(message: str) -> bool:
    """أسئلة مفاهيمية/تقنية من PDFs — لا تحتاج SQL."""
    msg = message or ""
    if _is_database_ranking_question(msg):
        return False
    if _is_environmental_knowledge_question(msg):
        return False
    return _contains_any(msg, [
        "ما الفرق", "الفرق بين", "ما هو", "ماهو", "ما هي", "ماهي", "تعريف", "اشرح", "اشرحي",
        "لماذا", "ليش", "متى نستخدم", "what is", "difference between", "define", "explain",
        "مشتت", "dispersant", "كشط", "skimmer", "boom", "حاجز", "احتواء", "containment",
        "sorbent", "ماصة", "weathering", "تجوية", "emulsion", "مستحلب", "mousse",
        "bioremediation", "in-situ", "burning", "حرق", "shoreline", "شاطئ", "شواطئ",
        "fate of oil", "مآل النفط", "best practice", "إرشادات", "guidelines", "protocol",
    ])


def _is_database_ranking_question(message: str) -> bool:
    msg = message or ""
    return _contains_any(msg, [
        "قاعدة", "قاعده", "database", "db", "جدول", "السجلات", "سجلات",
        "أقل", "اقل", "أكثر", "اكثر", "أخطر", "اخطر", "اعلى", "أعلى",
        "أصغر", "اصغر", "أكبر", "اكبر", "top", "rank", "lowest", "highest", "least",
        "اعرض", "عرض", "list", "show", "وش هي", "ما هي", "ماهي", "which",
        "كم عدد", "عدد", "count", "متوسط", "average",
    ])


def _is_environmental_knowledge_question(message: str) -> bool:
    msg = message or ""
    if _is_database_ranking_question(msg):
        return False
    oil_scope = _contains_any(msg, [
        "تسرب", "نفط", "بحري", "بحر", "spill", "oil", "marine", "offshore",
    ])
    if not oil_scope:
        return False
    return _contains_any(msg, [
        "خطورة", "خطوره", "مخاطر", "تأثير", "اثر", "أثر", "آثار", "ضرر", "أضرار", "اضرار",
        "الاسماك", "الأسماك", "اسماك", "أسماك", "سمك", "مصايد", "مصائد", "مزارع سمك",
        "الحياة البحرية", "الكائنات", "بيئي", "البيئة", "شعاب", "مرجان", "سلسلة غذائية",
        "fish", "fisheries", "mariculture", "wildlife", "ecosystem", "habitat",
        "environment", "environmental", "impact", "damage", "toxicity", "سمية", "تسمم",
        "coral", "reef", "pollution", "تلوث",
    ])


def _answer_rag_concept_fallback(question: str, lang: str = "ar") -> Optional[str]:
    is_ar = (lang or "ar").lower() == "ar"
    q = (question or "").lower()
    if (
        _contains_any(q, ["مشتت", "dispersant", "مشتتات"])
        and _contains_any(q, ["كشط", "كاشط", "skimmer", "skimming", "الفرق", "difference", "ما الفرق"])
    ) or (
        _contains_any(q, ["ما الفرق", "الفرق بين"])
        and _contains_any(q, ["مشتت", "كشط", "dispersant", "skimmer"])
    ):
        if is_ar:
            return (
                "**الفرق بين المشتت الكيميائي والكشط السطحي:**\n\n"
                "| | **المشتت الكيميائي (Dispersant)** | **الكشط السطحي (Skimming)** |\n"
                "|---|---|---|\n"
                "| **الفكرة** | يُكسَر النفط لقطرات صغيرة تنتشر في الماء لتسريع التحلل الطبيعي | يُجمَع النفط من السطح ميكانيكيًا |\n"
                "| **متى يُستخدم** | تسرب في **عرض البحر** بعيدًا عن الشواطئ والشعاب | تسرب بسُمك واضح على السطح وحالة بحر هادئة نسبيًا |\n"
                "| **الميزة** | يقلل تراكم النفط على السطح بسرعة | يُزيل النفط فعليًا من البيئة |\n"
                "| **المخاطر** | قد يؤثر على الكائنات المائية إذا استُخدم قرب الشعاب/السواحل | أبطأ وقد لا يلتقط النفط الرقيق جدًا |\n\n"
                "**التوصية العملية:** قرب الشعاب والسواحل → الأفضل **الاحتواء + الكشط**؛ "
                "في البحر المفتوح وبعيدًا عن المناطق الحساسة → قد يُناقش المشتت بعد تقييم بيئي.\n\n"
                "_المصدر: دليل تقني مدمج (ITOPF TIP 4 / TIP 5)_"
            )
        return (
            "**Chemical dispersant vs surface skimming:**\n\n"
            "- **Dispersant:** breaks oil into droplets for natural dispersion — used offshore, away from sensitive coasts/reefs.\n"
            "- **Skimming:** mechanically removes surface oil — best with visible slick and calmer seas.\n\n"
            "Near reefs/shorelines: prefer containment + skimming. Open sea: dispersants may be considered with environmental assessment.\n\n"
            "_Source: embedded technical guide (ITOPF TIP 4 / TIP 5)_"
        )
    return None


def _answer_general_environmental_knowledge(question: str, lang: str = "ar") -> str:
    is_ar = (lang or "ar").lower() == "ar"
    if is_ar:
        return (
            "خطورة التسربات النفطية على الأسماك والحياة البحرية:\n\n"
            "1) **التسمم المباشر**: تعرّض الأسماك للنفط عبر الخياشيم والجلد يسبب تهيجًا، ضعف التنفس، وقد يؤدي لنفوق جماعي قرب منطقة التسرب.\n"
            "2) **تلوث الغذاء والسلسلة الغذائية**: النفط والمشتقات تنتقل عبر العوالق والكائنات الصغيرة إلى الأسماك الكبيرة، ما يزيد تراكم المواد الضارة.\n"
            "3) **تأثير اليرقات والصغار**: يرقات الأسماك أكثر حساسية لأنها تبقى قرب السطح حيث يتركز النفط.\n"
            "4) **تلف الموائل**: إذا اقترب التسرب من الشعاب أو السواحل، تتأثر مناطق التكاثر والتغذية، فينخفض الإنتاج السمكي محليًا.\n"
            "5) **تأثيرات غير مباشرة**: قد يقل الأكسجاء قرب السطح، وتتأثر رؤية المياه وسلوك الأسماك (هروب/تغيير مسارات هجرة).\n\n"
            "**عوامل ترفع الخطورة**: مساحة التسرب الكبيرة، القرب من الساحل/الشعاب، نوع النفط الثقيل أو المستحلب، واستمرار التسرب بدون احتواء.\n\n"
            "**إجراءات تقليل الأثر**:\n"
            "- احتواء التسرب مبكرًا (حواجز عائمة + كشط سطحي).\n"
            "- حماية المناطق الحساسة (شعاب/مصائد) أولًا.\n"
            "- تجنب المشتتات الكيميائية قرب الشعاب إلا بعد تقييم بيئي.\n"
            "- مراقبة المصايد والمزارع السمكية وإيقاف الصيد مؤقتًا عند الحاجة.\n\n"
            "_ملاحظة: لتحليل حالة محددة من بيانات المشروع، اختاري تسربًا من قائمة السياق ثم اسألي عن تأثيره._"
        )
    return (
        "Oil spills threaten fish and marine life through:\n\n"
        "1) Direct toxicity via gills and skin exposure.\n"
        "2) Food-chain transfer through plankton and small organisms.\n"
        "3) High sensitivity of larvae near the surface slick.\n"
        "4) Habitat damage near reefs and shorelines (spawning/feeding areas).\n"
        "5) Indirect effects such as reduced surface oxygen and altered fish behavior.\n\n"
        "Risk increases with spill size, proximity to reefs/shorelines, heavy/emulsified oil, and delayed containment.\n\n"
        "Mitigation: early boom/skimmer deployment, protect sensitive habitats first, avoid dispersants near reefs without assessment, and monitor fisheries closures.\n\n"
        "_Note: select a specific spill in context for a case-based impact analysis from project data._"
    )


def _response_plan(lang="ar"):
    is_ar = (lang or "ar").lower() == "ar"
    if is_ar:
        return (
            "خطة الاستجابة المقترحة:\n"
            "1. تحديد اتجاه انتشار النفط بالرياح والتيارات.\n"
            "2. وضع حواجز احتواء عائمة حول التسرب أو أمام المناطق الحساسة.\n"
            "3. حماية الشعاب والسواحل أولًا لأنها أكثر حساسية بيئيًا.\n"
            "4. استخدام الكشط السطحي ومواد الامتصاص عند الإمكان.\n"
            "5. تجنب المشتتات الكيميائية قرب الشعاب إلا بعد تقييم بيئي.\n"
            "6. تحديث التقييم كل فترة حسب تغير الانتشار."
        )
    return (
        "Suggested response plan:\n"
        "1. Determine the spill drift direction using wind and current data.\n"
        "2. Deploy floating containment booms around the spill or in front of sensitive areas.\n"
        "3. Protect reefs and shoreline first — they are the most ecologically sensitive.\n"
        "4. Use surface skimming and sorbent materials when possible.\n"
        "5. Avoid chemical dispersants near reefs without environmental assessment.\n"
        "6. Re-assess regularly as spread changes."
    )


def _route_question(message, has_spill):
    msg = (message or "").lower()

    data_words = [
        "قارن", "مقارنة", "أخطر", "اخطر", "مساحة", "نسبة", "تغطية",
        "المسافة", "إحداثيات", "احداثيات", "قرب", "كم",
        "risk", "area", "compare", "coverage", "distance", "highest",
        "top", "list", "show me", "أعلى", "اعلى", "اعرض",
        "report", "explain", "summarize", "describe", "تقرير", "اشرح", "لخّص", "لخص",
    ]

    env_words = [
        "خطورة", "خطر", "مخاطر", "تأثير", "اثر", "أثر", "الاسماك", "الأسماك",
        "سمك", "الحياة البحرية", "الكائنات", "الشعاب", "بيئي", "البيئة", "ضرر",
        "fish", "marine", "coral", "reef", "environment", "environmental",
        "impact", "damage", "wildlife", "ecosystem",
    ]

    solution_words = [
        "كيف", "حل", "حلول", "تنظيف", "استجابة", "خطة", "توصية", "تعامل",
        "احتواء", "ماذا", "إجراء", "اجراء",
        "how", "solution", "solutions", "clean", "cleanup", "response",
        "plan", "recommend", "recommendation", "contain", "containment",
        "action", "what should",
    ]

    wants_data = any(w in msg for w in data_words)
    wants_env = any(w in msg for w in env_words)
    wants_solution = any(w in msg for w in solution_words)

    # When a spill is in context, treat almost anything as a question about IT
    if has_spill and (wants_env or wants_solution or wants_data):
        return "selected_environment"

    if wants_data:
        return "data"

    if wants_env or wants_solution:
        return "guide"

    if has_spill:
        return "selected_environment"  # was "selected" — give a real answer not a one-liner

    return "general"


def _normalize_ar_ui_terms(text: str) -> str:
    """توحيد المصطلحات العربية في ردود الوكيل."""
    if not text:
        return text
    out = str(text)
    out = re.sub(r"المساعد الذكي", "الوكيل الذكي", out)
    out = re.sub(r"مساعدك الذكي", "وكيلك الذكي", out)
    out = re.sub(r"المساعد", "الوكيل", out)
    out = re.sub(r"من الشعاب(?! المرجانية)", "من الشعاب المرجانية", out)
    out = re.sub(r"والشعاب(?! المرجانية)", "والشعاب المرجانية", out)
    out = re.sub(r"قرب الشعاب(?! المرجانية)", "قرب الشعاب المرجانية", out)
    out = re.sub(r"إلى الشعاب(?! المرجانية)", "إلى الشعاب المرجانية", out)
    out = re.sub(r"عن الشعاب(?! المرجانية)", "عن الشعاب المرجانية", out)
    out = re.sub(r"\bالشعب\b", "الشعاب المرجانية", out)
    out = re.sub(r"\bالشعاب\b(?! المرجانية)", "الشعاب المرجانية", out)
    out = re.sub(r"(?<!جيو )مكانية", "جيو المكانية", out)
    out = re.sub(r"(?<!جيو )مكاني(?!ة)", "جيو مكاني", out)
    out = re.sub(r"القناع المتوقّع", "منطقة التسرب المكتشفة", out)
    out = re.sub(r"القناع المتوقع", "منطقة التسرب المكتشفة", out)
    out = re.sub(r"قناع متوقّع", "منطقة التسرب المكتشفة", out)
    out = re.sub(r"قناع متوقع", "منطقة التسرب المكتشفة", out)
    out = re.sub(r"التراكب", "التداخل", out)
    out = re.sub(r"فضائية", "أقمار صناعية", out)
    out = re.sub(r"فضائي", "أقمار صناعية", out)
    out = re.sub(r"زيت", "نفط", out)
    out = re.sub(r"المنصة", "النظام", out)
    out = re.sub(r"منصة", "نظام", out)
    out = re.sub(r"السمات", "الخصائص", out)
    out = re.sub(r"السمة", "الخاصية", out)
    out = re.sub(r"سمات", "خصائص", out)
    out = re.sub(r"سمة", "خاصية", out)
    out = re.sub(r"\bحرج\b", "عالي", out)
    out = re.sub(r"\bCritical\b", "High", out, flags=re.IGNORECASE)
    # إحداثيات بدون مسافة: 26.0774°,49.8764°
    out = re.sub(
        r"(-?\d+(?:\.\d+)?)°\s*,\s*(-?\d+(?:\.\d+)?)°",
        r"\1°,\2°",
        out,
    )
    return out


_CHAT_REPLY_LANG = "ar"


def _chat_reply(
    reply: str,
    *,
    ok: bool = True,
    source_used: str = "none",
    intent: str = "general",
    route: Optional[str] = None,
    needs_clarification: bool = False,
    clarification_options: Optional[List[Dict[str, str]]] = None,
    used_search: bool = False,
    sources: Optional[List[Dict[str, Any]]] = None,
    resolved_spill_id: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_reply = (
        _normalize_ar_ui_terms(reply) if (_CHAT_REPLY_LANG or "ar").lower() == "ar" else reply
    )
    return {
        "ok": ok,
        "reply": normalized_reply,
        "source_used": source_used,
        "intent": intent,
        "route": route or intent,
        "needs_clarification": needs_clarification,
        "clarification_options": clarification_options or [],
        "used_search": used_search,
        "sources": sources or [],
        "resolved_spill_id": resolved_spill_id,
    }


def _contains_any(text: str, keywords: List[str]) -> bool:
    lowered = (text or "").lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _chat_history_context(history: Optional[List[Dict[str, Any]]], lang: str, max_turns: int = 6) -> str:
    if not history:
        return ""
    is_ar = (lang or "ar").lower() == "ar"
    lines: List[str] = []
    for item in history[-max_turns:]:
        role = str(item.get("role") or "").lower()
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        speaker = "المستخدم" if is_ar and role == "user" else "المساعد" if is_ar else "User" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")
    if not lines:
        return ""
    title = "سياق المحادثة الأخيرة" if is_ar else "Recent conversation context"
    return f"[{title}]\n" + "\n".join(lines)


def _last_history_item(history: Optional[List[Dict[str, Any]]], role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not history:
        return None
    for item in reversed(history):
        item_role = str(item.get("role") or "").lower()
        if role is None or item_role == role:
            return item
    return None


def _last_history_pair(history: Optional[List[Dict[str, Any]]]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    last_assistant = _last_history_item(history, "assistant")
    if not history:
        return None, last_assistant
    last_user = None
    if last_assistant and last_assistant in history:
        idx = history.index(last_assistant)
        for item in reversed(history[:idx]):
            if str(item.get("role") or "").lower() == "user":
                last_user = item
                break
    if last_user is None:
        last_user = _last_history_item(history, "user")
    return last_user, last_assistant


def _history_resolved_spill_id(history: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    if not history:
        return None
    for item in reversed(history):
        for key in ("resolved_spill_id", "context_spill_id"):
            value = str(item.get(key) or "").strip()
            if value:
                return value
    return None


def _is_followup_question(message: str) -> bool:
    q = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not q:
        return False

    exact_phrases = {
        "كيف ذلك", "كيف كذا", "كيف يعني", "وش تقصد", "ماذا تقصد", "وش يعني",
        "ليش", "لماذا", "وضح", "وضح أكثر", "اشرح أكثر", "كيف؟", "ليش؟",
        "why", "how so", "what do you mean", "explain more", "why is that",
    }
    if q in exact_phrases:
        return True

    if len(q.split()) <= 4 and _contains_any(q, [
        "كيف", "ليش", "لماذا", "وضح", "اشرح", "more", "why", "how",
    ]):
        return True
    return False


def _explain_previous_answer(question: str, history: Optional[List[Dict[str, Any]]], spill, lang: str = "ar") -> str:
    is_ar = (lang or "ar").lower() == "ar"
    last_user, last_assistant = _last_history_pair(history)
    prev_question = str((last_user or {}).get("content") or "").strip()
    prev_answer = str((last_assistant or {}).get("content") or "").strip()
    prev_intent = str((last_assistant or {}).get("intent") or "").strip().lower()

    if prev_intent == "aggregate_data":
        q_lower = prev_question.lower()
        if _contains_any(q_lower, ["متوسط", "average", "avg", "mean"]):
            return (
                f"المقصود أنني اعتمدت على السؤال السابق `{prev_question}` ثم أخذت جميع السجلات المطابقة من البيانات الحالية وحسبت المتوسط المطلوب منها. "
                "إذا تريد، أقدر أفصل لك هل المتوسط كان للمساحة أو التغطية أو المسافة إلى اليابسة والشعاب."
                if is_ar
                else f"What I mean is that I used your previous question `{prev_question}` and selected the matching records from the current dataset, then computed the requested average. If you want, I can break down whether that average refers to area, coverage, or distance to land/coral."
            )
        if _contains_any(q_lower, ["عدد", "كم", "count", "how many"]):
            return (
                f"المقصود أنني حسبت عدد السجلات المطابقة للسؤال السابق `{prev_question}` داخل البيانات الحالية، ولم أقدّم تقديرًا عامًّا من خارج القاعدة."
                if is_ar
                else f"What I mean is that I counted the records matching your previous question `{prev_question}` from the current data, rather than giving a general estimate."
            )
        if _contains_any(q_lower, ["أخطر", "اخطر", "top", "highest", "rank"]):
            return (
                f"المقصود أنني رتبت الحالات المطابقة للسؤال السابق `{prev_question}` حسب مؤشرات الخطورة المتاحة في البيانات، ثم عرضت الأعلى ترتيبًا."
                if is_ar
                else f"What I mean is that I ranked the records matching your previous question `{prev_question}` using the available risk indicators in the data, then showed the top-ranked results."
            )

    if prev_intent in {"spill_specific", "selected_spill_local"} and spill:
        summary = _selected_summary(spill, lang)
        return (
            f"المقصود في الرد السابق أن الشرح كان مبنيًا على بيانات الحالة نفسها، وليس على قاعدة البيانات كلها. {summary}"
            if is_ar
            else f"The previous answer was based on the selected spill itself, not on the whole dataset. {summary}"
        )

    if prev_intent == "solution_search":
        return (
            "المقصود أن الخطة السابقة كانت خطة استجابة تشغيلية: نبدأ بتقييم الانتشار، ثم الاحتواء، ثم حماية المناطق الحساسة، ثم المتابعة. إذا أردت، أقدر أحولها الآن إلى خطوات تنفيذية أكثر تفصيلًا."
            if is_ar
            else "What I mean is that the previous answer was an operational response plan: first assess spread, then contain it, protect sensitive areas, and continue monitoring. If you want, I can now turn it into a more detailed execution plan."
        )

    if prev_intent == "general_solution":
        return (
            "إذا كنت تقصد حالة تسرب محددة، فحدد الحالة أولًا حتى أشرح لك الخطة المناسبة لها بدقة. وإذا كنت تقصد شرح الخطة العامة نفسها، فاسأل بصياغة أوضح مثل: `اشرح لي الخطة العامة خطوة خطوة`."
            if is_ar
            else "If you mean a specific spill, select the spill first so I can explain the suitable plan for it accurately. If you mean the general response plan itself, ask more explicitly, for example: `Explain the general response plan step by step`."
        )

    if prev_answer:
        return (
            f"المقصود في الرد السابق هو: {prev_answer[:500]}"
            if is_ar
            else f"What I meant in the previous answer is: {prev_answer[:500]}"
        )

    return (
        "أحتاج سياقًا أوضح حتى أشرح المقصود. اكتب سؤالك بشكل أكثر تحديدًا أو أعد ذكر الحالة أو المعلومة التي تريد توضيحها."
        if is_ar
        else "I need clearer context to explain what I meant. Please ask a more specific follow-up or restate the spill or detail you want clarified."
    )


def _recent_history_in_scope(history: Optional[List[Dict[str, Any]]]) -> bool:
    if not history:
        return False
    scope_words = [
        "تسرب", "نفط", "spill", "oil", "reef", "coral", "shoreline", "risk",
        "شعاب", "يابسة", "استجابة", "تنظيف", "حل", "coverage", "area",
    ]
    for item in history[-6:]:
        text = str(item.get("content") or "")
        if item.get("context_spill_id"):
            return True
        if _contains_any(text, scope_words):
            return True
    return False


def _extract_named_spill_reference(df, message: str):
    from pathlib import Path

    if df.empty or not message:
        return None

    msg = (message or "").lower()
    best_row = None
    best_score = 0

    for col in ["spill_id", "id", "filename", "source_image", "source_image_path"]:
        if col not in df.columns:
            continue
        for _, row in df.iterrows():
            raw = str(row.get(col) or "").strip()
            if not raw or raw.lower() == "nan":
                continue
            candidates = {
                raw,
                Path(raw).name,
                Path(raw).stem,
            }
            for candidate in candidates:
                cand = candidate.strip().lower()
                if len(cand) < 4:
                    continue
                if cand in msg and len(cand) > best_score:
                    best_score = len(cand)
                    best_row = row.to_dict()

    return best_row


def _question_references_specific_case(message: str) -> bool:
    msg = (message or "").lower()
    has_case_word = _contains_any(msg, [
        "حالة", "التسرب", "spill", "case", "incident",
    ])
    has_pointer = _contains_any(msg, [
        "هذا", "هذه", "هذي", "ذا", "ذي", "المحددة", "المقصودة",
        "this", "that", "selected",
    ])
    if has_case_word and has_pointer:
        return True
    return _contains_any(message, [
        "هذا التسرب", "هذي الحالة", "هذه الحالة", "الحالة هذه", "الحالة هذي",
        "التسرب ذا", "التسرب هذا", "للتسرب هذا", "للتسرب ذا", "لهذه الحالة", "لهذي الحالة", "حدد الحالة",
        "this spill", "this case", "that spill", "that case", "selected spill",
        "الحالة المحددة", "الحالة المقصودة",
    ])


def is_out_of_scope_question(message: str, has_spill: bool = False, history: Optional[List[Dict[str, Any]]] = None) -> bool:
    if has_spill or _recent_history_in_scope(history):
        return False
    if _is_rag_knowledge_question(message) or _is_database_ranking_question(message):
        return False
    if _contains_any(message, ["مرحبا", "هلا", "السلام", "hello", "hi", "hey"]):
        return False

    out_of_scope_words = [
        "قصيدة", "شعر", "برمجة", "رياضيات", "طبخ", "مباراة", "كرة", "سياسة",
        "joke", "poem", "recipe", "football", "movie", "politics", "programming",
    ]
    if _contains_any(message, out_of_scope_words):
        return True

    in_scope_words = [
        "تسرب", "نفط", "بحري", "شعاب", "يابسة", "ساحل", "بيئة", "استجابة",
        "تنظيف", "خطر", "خطورة", "تقرير", "حالة", "spill", "oil", "marine",
        "coral", "shoreline", "risk", "response", "cleanup", "report", "case",
        "open sea", "open-sea", "offshore", "البحر المفتوح", "عرض البحر",
        "مشتت", "dispersant", "كشط", "skimmer", "boom", "حاجز", "احتواء",
        "sorbent", "ماصة", "الفرق", "تعريف", "weathering", "تجوية",
    ]
    return not _contains_any(message, in_scope_words)


def needs_spill_clarification(message: str, selected, named_spill) -> bool:
    if selected or named_spill:
        return False
    if not _question_references_specific_case(message):
        return False
    # أي سؤال يشير لـ «هذا التسرب» بدون تحديد حالة يحتاج توضيح أولاً
    return True


def needs_metric_clarification(message: str) -> bool:
    q = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not q:
        return False

    scope_terms = [
        "open sea", "open-sea", "البحر المفتوح", "عرض البحر",
        "near shore", "offshore", "coastal", "الشعاب", "اليابسة",
    ]
    if q in scope_terms:
        return True

    has_scope = _contains_any(q, scope_terms)
    has_metric = _contains_any(q, [
        "متوسط", "معدل", "عدد", "كم", "أخطر", "اخطر", "top", "count",
        "average", "avg", "mean", "highest", "lowest", "مساحة", "تغطية",
        "distance", "risk", "قرب", "المسافة",
    ])
    return has_scope and not has_metric and len(q.split()) <= 4


def needs_region_case_clarification(message: str, selected, named_spill) -> bool:
    if selected or named_spill:
        return False
    q = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not q:
        return False

    region_terms = [
        "arabian gulf", "gulf", "red sea", "gulf of oman", "strait of hormuz",
        "gulf of aqaba", "الخليج العربي", "الخليج", "البحر الأحمر",
        "خليج عمان", "مضيق هرمز", "خليج العقبة",
    ]
    has_region = _contains_any(q, region_terms)
    has_metric = _contains_any(q, [
        "متوسط", "معدل", "عدد", "كم", "أخطر", "اخطر", "top", "count",
        "average", "avg", "mean", "highest", "lowest", "مساحة", "تغطية",
        "distance", "risk", "قرب", "المسافة", "حل", "خطة", "استجابة", "اشرح",
    ])
    return has_region and not has_metric and len(q.split()) <= 5


def _agent_meta_topic(message: str) -> Optional[str]:
    q = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not q:
        return None

    if _contains_any(q, [
        "مموري", "memory", "ذاكرة", "localstorage", "local storage",
        "وش نوعها", "وش حجمها", "نوع الميموري", "حجم الميموري",
    ]):
        return "memory"

    if _contains_any(q, [
        "قارد", "guard", "guardrail", "guardrails", "الأسئلة الممنوعة",
        "الاسئلة الممنوعة", "الممنوع عنها", "خارج النطاق", "out of scope",
        "وش المسموح", "وش الممنوع", "وش كتبت في القاردس",
    ]):
        return "guardrails"

    if _contains_any(q, [
        "من وين يجيب", "من اين يجيب", "المصدر", "source", "sources",
        "كيف يقرر", "كيف يحدد المصدر", "كيف يختار المصدر", "routing", "route",
    ]):
        return "sources"

    if _contains_any(q, [
        "كيف يشتغل", "كيف يعمل", "كيف يشتغل الوكيل", "كيف يعمل الوكيل",
        "كيف يشتغل الشات", "كيف يعمل الشات", "كيف يرد", "وش يسوي",
        "وكيل", "الوكيل الذكي", "الشات الذكي",
    ]):
        return "behavior"

    return None


def _answer_agent_meta_question(question: str, lang: str = "ar") -> str:
    is_ar = (lang or "ar").lower() == "ar"
    topic = _agent_meta_topic(question)

    if topic == "memory":
        return (
            "الميموري الحالية من نوع localStorage داخل المتصفح. نحفظ فيها سجل المحادثة والحالة المثبتة، ثم نرسل آخر جزء من history إلى الباكند حتى يفهم أسئلة المتابعة مثل: `كيف ذلك`. هذه الميموري محلية على نفس الجهاز والمتصفح وليست مشتركة بين المستخدمين."
            if is_ar
            else "The current memory is browser localStorage. It stores the chat history and pinned spill, then sends the latest history slice to the backend so it can understand follow-up questions like `how so?`. This memory is local to the same device/browser and is not shared across users."
        )

    if topic == "guardrails":
        return (
            "القاردريلز الحالية تمنع الشات من الخروج عن نطاق التسرّبات النفطية، وتمنع تخمين حالة غير محددة، وتطلب توضيحًا عند الغموض، وتسمح بالبحث الخارجي فقط لأسئلة الحلول، كما أن استعلامات قاعدة البيانات محمية بحيث يُسمح فقط باستعلامات SELECT الآمنة."
            if is_ar
            else "The current guardrails keep the chat within oil-spill scope, prevent it from guessing an unspecified spill, force clarification when the request is ambiguous, allow external search only for solution questions, and protect database access by allowing only safe SELECT queries."
        )

    if topic == "sources":
        return (
            "الشات يجيب من أكثر من مصدر بحسب السؤال: من قاعدة البيانات للأسئلة الرقمية والتجميعية، ومن تحليل الحالة إذا كانت هناك حالة محددة، ومن بحث موثوق لأسئلة الحلول فقط، ومن شرح محلي للمتابعة أو التوضيح. وإذا كان السؤال خارج النطاق فإنه يرفضه بدل التخمين."
            if is_ar
            else "The chat uses multiple sources depending on the question: the database for numeric and aggregate questions, local spill analysis when a spill is selected, trusted web search only for solution questions, and local follow-up/clarification logic for conversational explanation. If the question is out of scope, it refuses instead of guessing."
        )

    if topic == "behavior":
        return (
            "الوكيل الذكي يعمل على مراحل: أولًا يحدد نوع السؤال، ثم يقرر هل يحتاج توضيحًا، أو إجابة من قاعدة البيانات، أو تحليل حالة محددة، أو بحثًا موثوقًا للحلول، أو رفضًا بسبب الخروج عن النطاق. بعد ذلك يعيد الرد بالمصدر المناسب بدل استخدام مسار واحد لكل الأسئلة."
            if is_ar
            else "The smart agent works in stages: first it classifies the question, then it decides whether the user needs clarification, a database answer, a selected-spill analysis, a trusted solution search, or an out-of-scope refusal. It then replies using the appropriate source instead of using one single path for all questions."
        )

    return (
        "أستطيع شرح الميموري الحالية، القاردريلز، مصادر الإجابة، أو آلية عمل الوكيل الذكي. اسألني مثلًا: `وش نوع الميموري؟` أو `وش كتبت في القاردريلز؟`."
        if is_ar
        else "I can explain the current memory, guardrails, answer sources, or how the smart agent works. For example, ask: `what memory does it use?` or `what guardrails are enabled?`."
    )


def detect_question_intent(
    message: str,
    has_spill: bool = False,
    named_spill=None,
    history: Optional[List[Dict[str, Any]]] = None,
    compare_count: int = 0,
) -> str:
    msg = message or ""

    if _is_followup_question(msg) and _last_history_item(history, "assistant"):
        return "followup_explanation"
    if _agent_meta_topic(msg):
        return "agent_meta"
    if _detect_sea_scope(msg) and _contains_any(msg, ["كم", "عدد", "count", "how many", "نقطة", "نقاط"]):
        return "aggregate_data"
    if needs_region_case_clarification(msg, has_spill, named_spill):
        return "clarification"
    if needs_metric_clarification(msg):
        return "metric_clarification"
    if is_out_of_scope_question(msg, has_spill=bool(has_spill or named_spill), history=history):
        return "guardrail"
    if compare_count >= 2:
        return "spill_compare"

    wants_data = _contains_any(msg, [
        "قارن", "مقارنة", "أخطر", "اخطر", "أقل", "اقل", "أعلى", "اعلى",
        "أصغر", "اصغر", "أكبر", "اكبر", "مساحة", "نسبة", "تغطية",
        "المسافة", "إحداثيات", "احداثيات", "قرب", "كم", "متوسط", "معدل",
        "عدد", "احص", "إحص", "top", "count", "average", "avg", "mean", "rank",
        "highest", "lowest", "least", "compare", "coverage", "distance",
        "قاعدة", "قاعده", "database", "اعرض", "عرض", "list", "وش", "ما هي", "ماهي",
        "نقطة", "نقاط", "حالة", "حالات",
    ]) or _is_database_ranking_question(msg) or (
        _detect_sea_scope(msg) is not None
        and _contains_any(msg, ["كم", "عدد", "count", "how many", "نقطة", "نقاط", "حالة", "حالات", "متوسط", "average", "أخطر", "top"])
    )
    wants_solution = _contains_any(msg, [
        "كيف", "حل", "حلول", "تنظيف", "استجابة", "خطة", "توصية", "تعامل",
        "احتواء", "إجراء", "اجراء", "how", "solution", "cleanup", "response",
        "plan", "recommend", "containment", "mitigation",
    ])

    if needs_spill_clarification(msg, has_spill, named_spill):
        return "clarification"
    if wants_solution and (has_spill or named_spill):
        return "solution_search"
    if (has_spill or named_spill) and (wants_data or _question_references_specific_case(msg)):
        return "spill_specific"
    # أسئلة «هذا التسرب» بدون حالة محددة لا تذهب للتجميع العام
    if _question_references_specific_case(msg) and not has_spill and not named_spill:
        return "clarification"
    if wants_data:
        return "aggregate_data"
    if has_spill or named_spill:
        return "spill_specific"
    if wants_solution:
        return "general_solution"
    if _is_environmental_knowledge_question(msg) and not wants_data:
        return "environmental_knowledge"
    if _is_rag_knowledge_question(msg):
        return "rag_knowledge"
    return "general"


def _clarification_options(df, lang: str, limit: int = 5) -> List[Dict[str, str]]:
    if df.empty:
        return []
    work = df.copy()
    for col in ["risk_score", "area_m2"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    work = work.sort_values(by=["risk_score", "area_m2"], ascending=[False, False]).head(limit)
    options: List[Dict[str, str]] = []
    for _, row in work.iterrows():
        row_dict = row.to_dict()
        spill_id = _t(row_dict, ["spill_id", "id", "filename"], "")
        if not spill_id:
            continue
        region = _t(row_dict, ["region"], "غير معروف" if lang == "ar" else "Unknown")
        risk = _t(row_dict, ["final_risk_level", "risk_level"], "Unknown")
        label = f"{spill_id} · {region} · {risk}"
        options.append({"id": spill_id, "label": label})
    return options


def _prepare_aggregate_df(df):
    work = df.copy()
    for col in ["risk_score", "area_m2", "coverage_pct", "distance_to_land_km", "distance_to_coral_km"]:
        if col not in work.columns:
            work[col] = 0
        work[col] = pd.to_numeric(work[col], errors="coerce").fillna(0)
    return work


def _infer_sea_region(lat: float, lon: float) -> Optional[str]:
    """نفس تصنيف الواجهة: Red Sea | Arabian Gulf | Open Sea."""
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    if abs(lat_f) < 1e-9 and abs(lon_f) < 1e-9:
        return None
    if 12 <= lat_f <= 28 and 33 <= lon_f <= 44:
        return "Red Sea"
    if 20 <= lat_f <= 30 and 47 <= lon_f <= 60:
        return "Arabian Gulf"
    return "Open Sea"


def _sea_region_label(sea: str, lang: str = "ar") -> str:
    labels = {
        "Red Sea": ("البحر الأحمر", "Red Sea"),
        "Arabian Gulf": ("الخليج العربي", "Arabian Gulf"),
        "Open Sea": ("البحر المفتوح", "Open Sea"),
    }
    pair = labels.get(str(sea or ""), (sea, sea))
    return pair[0] if (lang or "ar").lower() == "ar" else pair[1]


def _detect_sea_scope(message: str) -> Optional[str]:
    q = re.sub(r"\s+", " ", (message or "").strip().lower())
    if not q:
        return None
    if _contains_any(q, [
        "red sea", "البحر الأحمر", "بحر أحمر", "بحر احمر", "البحر الاحمر",
    ]):
        return "Red Sea"
    if _contains_any(q, [
        "arabian gulf", "persian gulf", "الخليج العربي", "الخليج",
        "خليج عمان", "gulf of oman", "مضيق هرمز", "strait of hormuz",
        "خليج العقبة", "gulf of aqaba",
    ]):
        return "Arabian Gulf"
    if _contains_any(q, [
        "open sea", "open-sea", "البحر المفتوح", "عرض البحر", "البحر المفتوحه",
        "offshore", "deep sea",
    ]):
        return "Open Sea"
    return None


def _ensure_sea_region_column(df):
    if df.empty:
        return df
    if "sea_region" in df.columns:
        return df
    work = df.copy()
    lat_col = "latitude" if "latitude" in work.columns else "spill_centroid_lat"
    lon_col = "longitude" if "longitude" in work.columns else "spill_centroid_lon"
    if lat_col not in work.columns or lon_col not in work.columns:
        work["sea_region"] = "Open Sea"
        return work
    lats = pd.to_numeric(work[lat_col], errors="coerce").fillna(0)
    lons = pd.to_numeric(work[lon_col], errors="coerce").fillna(0)
    work["sea_region"] = [
        _infer_sea_region(la, lo) or "Open Sea" for la, lo in zip(lats, lons)
    ]
    return work


def _apply_sea_region_filter(df, message: str, lang: str = "ar"):
    sea = _detect_sea_scope(message)
    if not sea or df.empty:
        return df, None
    work = _ensure_sea_region_column(df)
    filtered = work[work["sea_region"].astype(str) == sea]
    return filtered, _sea_region_label(sea, lang)


def _apply_open_sea_filter(df, message: str):
    """Legacy: يفوّض إلى فلتر البحر الموحّد."""
    filtered, label = _apply_sea_region_filter(df, message)
    if label:
        return filtered, label
    if df.empty:
        return df, None
    q = (message or "").lower()
    if not _contains_any(q, ["open sea", "open-sea", "البحر المفتوح", "عرض البحر", "البحر المفتوحه"]):
        return df, None

    mask = pd.Series([False] * len(df), index=df.index)
    if "land_proximity_class" in df.columns:
        series = df["land_proximity_class"].astype(str).str.lower()
        mask = mask | series.str.contains("open sea|offshore|deep sea", regex=True, na=False)
    if "distance_to_land_km" in df.columns:
        distance = pd.to_numeric(df["distance_to_land_km"], errors="coerce").fillna(0)
        mask = mask | (distance >= 20)

    filtered = df[mask]
    return filtered, "البحر المفتوح" if _contains_any(q, ["البحر", "عرض"]) else "open sea"


def _apply_risk_filter(df, message: str):
    if df.empty:
        return df, None
    q = (message or "").lower()
    risk_map = [
        ("Critical", ["حرج", "حرجة", "critical"]),
        ("High", ["عالية", "مرتفع", "high"]),
        ("Medium", ["متوسطة", "medium"]),
        ("Low", ["منخفض", "low"]),
    ]
    for risk_name, keywords in risk_map:
        if _contains_any(q, keywords):
            risk_series = (
                df["final_risk_level"] if "final_risk_level" in df.columns
                else df["risk_level"] if "risk_level" in df.columns
                else pd.Series([""] * len(df), index=df.index)
            )
            filtered = df[risk_series.astype(str).str.upper() == risk_name.upper()]
            return filtered, risk_name
    return df, None


def _answer_aggregate_question(df, question: str, top_k: int = 5, lang: str = "ar") -> str:
    is_ar = (lang or "ar").lower() == "ar"
    if df.empty:
        return "لا توجد بيانات كافية للإجابة حالياً." if is_ar else "There is not enough data to answer right now."

    work = _prepare_aggregate_df(df)
    scoped, scope_label = _apply_sea_region_filter(work, question, lang=lang)
    if scope_label is None:
        scoped, scope_label = _apply_open_sea_filter(work, question)
    scoped, risk_label = _apply_risk_filter(scoped, question)
    if scoped.empty:
        target = scope_label or ("الفئة المطلوبة" if is_ar else "the requested subset")
        return (
            f"لا توجد بيانات مطابقة داخل {target}."
            if is_ar
            else f"No matching records were found within {target}."
        )

    q = (question or "").lower()
    wants_lowest = _contains_any(q, [
        "أقل", "اقل", "أصغر", "اصغر", "lowest", "least", "أقل خطورة", "اقل خطوره", "اقل خطورة",
        "الأقل خطورة", "الاقل خطوره", "less dangerous", "low risk", "منخفضة الخطورة", "منخفض",
    ])
    wants_top = _contains_any(q, ["أخطر", "اخطر", "top", "highest", "اعلى", "أعلى", "قارن", "مقارنة", "list"])
    wants_count = _contains_any(q, ["كم", "عدد", "count", "how many"])
    wants_average = _contains_any(q, ["متوسط", "معدل", "average", "avg", "mean"])

    if wants_lowest and not wants_top:
        prefix = ""
        if scope_label or risk_label:
            if is_ar:
                parts = [part for part in [scope_label, risk_label] if part]
                prefix = f"ضمن {' / '.join(parts)}:\n\n"
            else:
                parts = [part for part in [scope_label, risk_label] if part]
                prefix = f"Within {' / '.join(parts)}:\n\n"
        return prefix + _lowest_risk_answer(scoped, top_k=top_k, lang=lang)

    if wants_top:
        prefix = ""
        if scope_label or risk_label:
            if is_ar:
                parts = [part for part in [scope_label, risk_label] if part]
                prefix = f"ضمن {' / '.join(parts)}:\n\n"
            else:
                parts = [part for part in [scope_label, risk_label] if part]
                prefix = f"Within {' / '.join(parts)}:\n\n"
        return prefix + _compare_answer(scoped, top_k=top_k, lang=lang)

    if wants_count and not wants_average:
        if not scope_label and not risk_label:
            count = _total_spill_count()
            target = "قاعدة البيانات (نفس مصدر لوحة التحكم)" if is_ar else "the database (same source as the dashboard)"
        else:
            count = int(len(scoped))
            parts = []
            if scope_label:
                parts.append(scope_label)
            if risk_label:
                parts.append(risk_label)
            target = " / ".join(parts) if parts else ("جميع الحالات" if is_ar else "all matching spills")
        if is_ar and not scope_label and not risk_label:
            return f"عدد حالات التسرب المسجلة في {target}: {count} حالة."
        if not is_ar and not scope_label and not risk_label:
            return f"Total registered spill cases in {target}: {count}."
        return (
            f"عدد حالات التسرب في {target}: {count} حالة."
            if is_ar
            else f"The number of spill cases in {target}: {count} cases."
        )

    if wants_average:
        count = int(len(scoped))
        avg_area = float(scoped["area_m2"].mean())
        avg_coverage = float(scoped["coverage_pct"].mean())
        avg_land = float(scoped["distance_to_land_km"].mean())
        avg_coral = float(scoped["distance_to_coral_km"].mean())

        if _contains_any(q, ["مساحة", "area"]):
            return (
                f"متوسط مساحة التسرب {'في ' + scope_label if scope_label and is_ar else 'in ' + scope_label if scope_label else ''}: {avg_area:,.2f} م²."
                if is_ar
                else f"The average spill area {'in ' + scope_label if scope_label else ''}: {avg_area:,.2f} m²."
            )
        if _contains_any(q, ["تغطية", "coverage"]):
            return (
                f"متوسط نسبة التغطية {'في ' + scope_label if scope_label and is_ar else 'in ' + scope_label if scope_label else ''}: {avg_coverage:.2f}%."
                if is_ar
                else f"The average coverage {'in ' + scope_label if scope_label else ''}: {avg_coverage:.2f}%."
            )

        if is_ar:
            scope_text = f" في {scope_label}" if scope_label else ""
            return (
                f"بالنسبة لحالات التسرب{scope_text}، وجدت {count} حالة مطابقة. "
                f"المتوسطات هي: مساحة التسرب {avg_area:,.2f} م²، "
                f"نسبة التغطية {avg_coverage:.2f}%، "
                f"المسافة إلى اليابسة {avg_land:.2f} كم، "
                f"والمسافة إلى الشعاب المرجانية {avg_coral:.2f} كم."
            )
        scope_text = f" in {scope_label}" if scope_label else ""
        return (
            f"For spill cases{scope_text}, I found {count} matching cases. "
            f"The averages are: area {avg_area:,.2f} m², coverage {avg_coverage:.2f}%, "
            f"distance to land {avg_land:.2f} km, and distance to coral reefs {avg_coral:.2f} km."
        )

    db_answer = _call_database_agent(question)
    if db_answer:
        return db_answer
    return _compare_answer(scoped, top_k=top_k, lang=lang)


def _answer_selected_spill_question(spill, question: str, lang: str = "ar") -> Optional[str]:
    q = (question or "").lower()
    if _contains_any(q, [
        "مساحة", "تغطية", "إحداثيات", "احداثيات", "المسافة", "الشعاب", "اليابسة",
        "risk", "area", "coverage", "coordinate", "distance", "coral", "shoreline",
        "تقرير", "اشرح", "لخص", "تفاصيل", "summary", "describe", "details",
    ]):
        summary = _selected_summary(spill, lang)
        if _contains_any(q, ["تأثير", "اثر", "أثر", "بيئي", "مخاطر", "impact", "environment", "risk"]):
            return summary + "\n\n" + _environment_answer(spill, question, lang)
        return summary

    if _contains_any(q, [
        "تأثير", "اثر", "أثر", "بيئي", "مخاطر", "الأسماك", "الاسماك", "الشعاب",
        "impact", "environment", "risk", "fish", "reef",
    ]):
        return _environment_answer(spill, question, lang)

    return None


def _chat_distance_value(row, distance_keys, class_keys) -> Optional[float]:
    distance = _n(row, distance_keys, None)
    if distance is None:
        return None
    proximity_class = _t(row, class_keys, "")
    proximity_text = str(proximity_class or "").strip().lower()
    invalid = {"", "unknown", "nan", "none", "null", "غير معروف", "غير متوفر"}
    if distance == 0 and proximity_text in invalid:
        return None
    return float(distance)


def _chat_risk_rank(row) -> int:
    risk = normalize_risk(_t(row, ["final_risk_level", "risk_level"], "Low"))
    return {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}.get(risk, 1)


def _chat_urgency_score(row) -> float:
    risk_rank = _chat_risk_rank(row)
    area = _n(row, ["area_m2"])
    coverage = _n(row, ["coverage_pct"])
    land = _chat_distance_value(row, ["distance_to_land_km"], ["land_proximity_class"])
    coral = _chat_distance_value(row, ["distance_to_coral_km"], ["coral_risk_class", "coral_proximity_class"])

    score = float(risk_rank * 1000)
    score += min(area / 1000.0, 250.0)
    score += min(coverage * 10.0, 250.0)
    if land is not None and land <= 5:
        score += max(0.0, 120.0 - (land * 20.0))
    if coral is not None and coral <= 5:
        score += max(0.0, 140.0 - (coral * 20.0))
    return score


def _answer_spill_comparison(spills: List[Dict[str, Any]], question: str, lang: str = "ar") -> str:
    is_ar = (lang or "ar").lower() == "ar"
    if len(spills) < 2:
        return "أحتاج حالتين على الأقل لإجراء المقارنة." if is_ar else "I need at least two cases to compare."

    profiles: List[Dict[str, Any]] = []
    for spill in spills:
        label = _t(spill, ["spill_id", "id", "filename"], "Unknown")
        risk = normalize_risk(_t(spill, ["final_risk_level", "risk_level"], "Low"))
        area = _n(spill, ["area_m2"])
        coverage = _n(spill, ["coverage_pct"])
        land = _chat_distance_value(spill, ["distance_to_land_km"], ["land_proximity_class"])
        coral = _chat_distance_value(spill, ["distance_to_coral_km"], ["coral_risk_class", "coral_proximity_class"])
        urgency = _chat_urgency_score(spill)
        profiles.append({
            "label": label,
            "risk": risk,
            "area": area,
            "coverage": coverage,
            "land": land,
            "coral": coral,
            "urgency": urgency,
            "risk_rank": _chat_risk_rank(spill),
        })

    def _equal_metric(a: Optional[float], b: Optional[float], tolerance: float = 1e-9) -> bool:
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tolerance

    most_dangerous = max(profiles, key=lambda item: (item["risk_rank"], item["area"], item["coverage"], item["urgency"]))
    fastest = max(profiles, key=lambda item: item["urgency"])
    land_candidates = [item for item in profiles if item["land"] is not None]
    closest_land = min(land_candidates, key=lambda item: item["land"]) if land_candidates else None

    if len(profiles) == 2:
        left, right = profiles[0], profiles[1]
        left_land_text = f"{left['land']:.2f} كم" if left["land"] is not None else "غير متاح"
        right_land_text = f"{right['land']:.2f} كم" if right["land"] is not None else "غير متاح"
        left_coral_text = f"{left['coral']:.2f} كم" if left["coral"] is not None else "غير متاح"
        right_coral_text = f"{right['coral']:.2f} كم" if right["coral"] is not None else "غير متاح"

        if is_ar:
            risk_line = (
                f"{most_dangerous['label']} أعلى خطورة لأنها مصنفة {most_dangerous['risk']}، "
                f"مقابل {right['risk'] if most_dangerous['label'] == left['label'] else left['risk']} للحالة الأخرى."
            )
            area_winner = left if (left["area"], left["coverage"]) >= (right["area"], right["coverage"]) else right
            area_other = right if area_winner is left else left
            area_line = (
                f"{area_winner['label']} تُظهر أثرًا أكبر في الصورة؛ "
                f"المساحة {area_winner['area']:,.2f} م² مقابل {area_other['area']:,.2f} م²، "
                f"ونسبة التغطية {area_winner['coverage']:.2f}% مقابل {area_other['coverage']:.2f}%."
            )
            if _equal_metric(left["land"], right["land"]):
                land_line = f"لا يوجد فرق في القرب من اليابسة؛ كلتا الحالتين تبعدان {left_land_text}."
            elif left["land"] is None and right["land"] is None:
                land_line = "لا توجد قراءة موثوقة للمسافة إلى اليابسة في الحالتين."
            else:
                nearer_land = left if (left["land"] or 10**9) < (right["land"] or 10**9) else right
                land_line = (
                    f"{nearer_land['label']} أقرب إلى اليابسة؛ "
                    f"تبعد {left_land_text if nearer_land is left else right_land_text} "
                    f"مقابل {right_land_text if nearer_land is left else left_land_text} للحالة الأخرى."
                )

            if _equal_metric(left["coral"], right["coral"]):
                coral_line = f"لا يوجد فرق في القرب من الشعاب؛ كلتا الحالتين تبعدان {left_coral_text}."
            elif left["coral"] is None and right["coral"] is None:
                coral_line = "لا توجد قراءة موثوقة للمسافة إلى الشعاب في الحالتين."
            else:
                nearer_coral = left if (left["coral"] or 10**9) < (right["coral"] or 10**9) else right
                coral_line = (
                    f"{nearer_coral['label']} أقرب إلى الشعاب المرجانية، "
                    f"وهذا يرفع حساسية القرار البيئي لها."
                )

            if _equal_metric(left["urgency"], right["urgency"]):
                urgency_line = "أولوية التدخل متقاربة بين الحالتين وفق القراءات الحالية."
            else:
                urgency_other = right if fastest is left else left
                urgency_line = (
                    f"{fastest['label']} تحتاج تدخلاً أسرع؛ "
                    f"لأنها تجمع بين خطورة أعلى وحجم أثر أكبر من {urgency_other['label']}."
                )

            return (
                f"مقارنة بين {left['label']} و{right['label']}:\n\n"
                f"1. من حيث الخطورة:\n- {risk_line}\n\n"
                f"2. من حيث حجم الأثر في الصورة:\n- {area_line}\n\n"
                f"3. من حيث القرب من اليابسة:\n- {land_line}\n\n"
                f"4. من حيث القرب من الشعاب:\n- {coral_line}\n\n"
                f"5. من حيث أولوية التدخل:\n- {urgency_line}"
            )

        risk_line = (
            f"{most_dangerous['label']} is riskier because it is classified as {most_dangerous['risk']}, "
            f"while the other case is lower in severity."
        )
        area_winner = left if (left["area"], left["coverage"]) >= (right["area"], right["coverage"]) else right
        area_other = right if area_winner is left else left
        area_line = (
            f"{area_winner['label']} shows the larger footprint in the image: "
            f"{area_winner['area']:,.2f} m² versus {area_other['area']:,.2f} m², "
            f"with {area_winner['coverage']:.2f}% coverage versus {area_other['coverage']:.2f}%."
        )
        if _equal_metric(left["land"], right["land"]):
            land_line = (
                f"There is no difference in distance to land; both cases are {left['land']:.2f} km away."
                if left["land"] is not None
                else "No reliable shoreline distance reading is available for either case."
            )
        elif left["land"] is None and right["land"] is None:
            land_line = "No reliable shoreline distance reading is available for either case."
        elif left["land"] is None or right["land"] is None:
            known_land = right if left["land"] is None else left
            land_line = f"{known_land['label']} is the only case with a reliable shoreline distance reading ({known_land['land']:.2f} km)."
        else:
            nearer_land = left if (left["land"] or 10**9) < (right["land"] or 10**9) else right
            farther_land = right if nearer_land is left else left
            land_line = (
                f"{nearer_land['label']} is closer to land "
                f"({nearer_land['land']:.2f} km versus {farther_land['land']:.2f} km)."
            )
        if _equal_metric(left["coral"], right["coral"]):
            coral_line = (
                f"There is no difference in distance to coral; both cases are {left['coral']:.2f} km away."
                if left["coral"] is not None
                else "No reliable coral-distance reading is available for either case."
            )
        elif left["coral"] is None and right["coral"] is None:
            coral_line = "No reliable coral-distance reading is available for either case."
        elif left["coral"] is None or right["coral"] is None:
            known_coral = right if left["coral"] is None else left
            coral_line = f"{known_coral['label']} is the only case with a reliable coral-distance reading."
        else:
            nearer_coral = left if (left["coral"] or 10**9) < (right["coral"] or 10**9) else right
            coral_line = f"{nearer_coral['label']} is closer to coral receptors."
        urgency_line = (
            "The intervention priority is similar between the two cases."
            if _equal_metric(left["urgency"], right["urgency"])
            else f"{fastest['label']} needs faster intervention because it combines higher severity and a larger footprint."
        )
        return (
            f"Comparison between {left['label']} and {right['label']}:\n\n"
            f"1. Risk:\n- {risk_line}\n\n"
            f"2. Image footprint:\n- {area_line}\n\n"
            f"3. Distance to land:\n- {land_line}\n\n"
            f"4. Distance to coral:\n- {coral_line}\n\n"
            f"5. Intervention priority:\n- {urgency_line}"
        )

    if is_ar:
        lines = []
        for item in profiles:
            land_text = f"{item['land']:.2f} كم" if item["land"] is not None else "غير متاح"
            coral_text = f"{item['coral']:.2f} كم" if item["coral"] is not None else "غير متاح"
            lines.append(
                f"- {item['label']}: الخطورة {item['risk']}، المساحة {item['area']:,.2f} م²، "
                f"نسبة التغطية {item['coverage']:.2f}%، البعد عن اليابسة {land_text}، والبعد عن الشعاب {coral_text}."
            )

        summary = [
            f"الأخطر حاليًا: {most_dangerous['label']}. السبب: مستوى الخطورة {most_dangerous['risk']} مع مساحة/تغطية أعلى نسبيًا.",
            (
                f"الأقرب إلى اليابسة: {closest_land['label']} ({closest_land['land']:.2f} كم)."
                if closest_land
                else "الأقرب إلى اليابسة: غير ممكن تحديده من القراءات الحالية."
            ),
            f"الأسرع حاجةً للتدخل: {fastest['label']}. السبب: يجمع بين الخطورة والحجم والقرب من المناطق الحساسة.",
        ]
        return (
            "مقارنة مباشرة بين الحالات المختارة:\n\n"
            + "\n".join(lines)
            + "\n\nالخلاصة التنفيذية:\n- "
            + "\n- ".join(summary)
        )

    lines = []
    for item in profiles:
        land_text = f"{item['land']:.2f} km" if item["land"] is not None else "unavailable"
        coral_text = f"{item['coral']:.2f} km" if item["coral"] is not None else "unavailable"
        lines.append(
            f"- {item['label']}: risk {item['risk']}, area {item['area']:,.2f} m², "
            f"coverage {item['coverage']:.2f}%, distance to land {land_text}, distance to coral {coral_text}."
        )
    summary = [
        f"Highest risk right now: {most_dangerous['label']}. Reason: higher severity plus stronger size/coverage indicators.",
        (
            f"Closest to land: {closest_land['label']} ({closest_land['land']:.2f} km)."
            if closest_land
            else "Closest to land: could not be determined from the current readings."
        ),
        f"Needs the fastest intervention: {fastest['label']}. Reason: it combines severity, size, and sensitivity proximity.",
    ]
    return (
        "Direct comparison between the selected cases:\n\n"
        + "\n".join(lines)
        + "\n\nExecutive summary:\n- "
        + "\n- ".join(summary)
    )


def _trusted_domain_for_url(url: str) -> Optional[str]:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return None
    host = host.split("@")[-1].split(":")[0]
    for domain in TRUSTED_SEARCH_DOMAINS:
        normalized = domain.lower()
        if host == normalized or host.endswith("." + normalized):
            return normalized
    return None


def _collect_trusted_sources_for_spill(spill) -> List[Dict[str, Any]]:
    mod = _load_search_response_agent_module()
    if mod is None:
        return []

    collect = getattr(mod, "collect_search_evidence", None)
    if not callable(collect):
        return []

    spill_data = {
        "spill_id": _t(spill, ["spill_id", "id", "filename"], ""),
        "risk_level": _t(spill, ["final_risk_level", "risk_level"], "unknown"),
        "area": f"{_n(spill, ['area_m2']):.2f} m2",
        "distance_to_coral": f"{_n(spill, ['distance_to_coral_km']):.2f} km",
        "distance_to_shoreline": f"{_n(spill, ['distance_to_land_km']):.2f} km",
        "wind_direction": "unknown",
        "sea_conditions": "unknown",
        "environmental_sensitivity": (
            "coral reefs and shoreline"
            if _n(spill, ["distance_to_coral_km"], 999) <= 5 or _n(spill, ["distance_to_land_km"], 999) <= 5
            else "open marine area"
        ),
    }

    try:
        raw_results = collect(spill_data)
    except Exception:
        return []

    trusted: List[Dict[str, Any]] = []
    seen_urls = set()
    for item in raw_results or []:
        url = str(item.get("url") or "").strip()
        domain = _trusted_domain_for_url(url)
        if not url or not domain or url in seen_urls:
            continue
        seen_urls.add(url)
        trusted.append({
            "title": str(item.get("title") or domain),
            "url": url,
            "domain": domain,
            "content": str(item.get("content") or "").strip(),
            "query": str(item.get("query") or "").strip(),
        })
    return trusted


def _synthesize_solution_with_sources(spill, question: str, sources: List[Dict[str, Any]], lang: str) -> str:
    from groq import Groq

    is_ar = (lang or "ar").lower() == "ar"
    groq_key = os.getenv("GROQ_API_KEY")
    if not groq_key:
        raise ValueError("Missing GROQ_API_KEY")

    groq_client = Groq(api_key=groq_key)
    summary = _selected_summary(spill, lang)
    sources_text = "\n\n".join(
        f"Source {i}\nTitle: {src.get('title')}\nDomain: {src.get('domain')}\nURL: {src.get('url')}\nContent: {src.get('content')}"
        for i, src in enumerate(sources[:4], start=1)
    )

    if is_ar:
        prompt = f"""
أنت مستشار استجابة لتسرّب نفطي.

المطلوب:
- أجب بالعربية المهنية فقط.
- اعتمد على ملخص الحالة وعلى المصادر الموثوقة التالية فقط.
- لا تخترع معلومات غير موجودة في البيانات أو المصادر.
- إذا كانت الحالة قريبة من الشعاب المرجانية أو الساحل فاذكر أن الأولوية للحماية والاحتواء الميكانيكي.
- اجعل الإجابة عملية ومقسمة إلى: ملخص سريع، إجراءات فورية، إجراءات خلال 24 ساعة، ولماذا هذه الخطة مناسبة.

سؤال المستخدم:
{question}

ملخص الحالة:
{summary}

المصادر الموثوقة:
{sources_text}
"""
    else:
        prompt = f"""
You are an oil spill response advisor.

Requirements:
- Answer in professional English.
- Use only the spill summary and the trusted sources below.
- Do not invent facts outside the data and sources.
- Prioritize mechanical containment and shoreline/reef protection when relevant.
- Structure the answer into: quick summary, immediate actions, next 24 hours, and why this plan fits.

User question:
{question}

Spill summary:
{summary}

Trusted sources:
{sources_text}
"""

    response = groq_client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        messages=[
            {"role": "system", "content": "Be concise, operational, and evidence-based."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=900,
    )
    return str(response.choices[0].message.content or "").strip()


def answer_solution_question_with_search(spill, question: str, lang: str = "ar") -> Dict[str, Any]:
    is_ar = (lang or "ar").lower() == "ar"
    trusted_sources = _collect_trusted_sources_for_spill(spill)
    if not trusted_sources:
        fallback = _response_plan(lang)
        note = (
            "\n\nلم أجد مصادر موثوقة كافية من الويب لهذه الحالة، لذلك أعرض لك الخطة التشغيلية المحلية المتاحة."
            if is_ar
            else "\n\nI could not find enough trusted web sources for this case, so I am giving you the local operational response plan."
        )
        return {
            "reply": fallback + note,
            "sources": [],
            "used_search": False,
            "source_used": "local_response_guide",
        }

    try:
        reply = _synthesize_solution_with_sources(spill, question, trusted_sources, lang)
    except Exception:
        source_lines = "\n".join(
            f"- {src['title']} ({src['domain']})"
            for src in trusted_sources[:4]
        )
        if is_ar:
            reply = (
                _response_plan(lang)
                + "\n\nاستندت الخطة إلى مصادر موثوقة مشابهة، من بينها:\n"
                + source_lines
            )
        else:
            reply = (
                _response_plan(lang)
                + "\n\nThis plan is aligned with trusted sources such as:\n"
                + source_lines
            )

    return {
        "reply": reply,
        "sources": trusted_sources,
        "used_search": True,
        "source_used": "trusted_solution_search",
    }


def _call_database_agent(question: str) -> Optional[str]:
    mod = _load_database_agent_module()
    if mod is None:
        return None
    fn = getattr(mod, "answer_question", None)
    if not callable(fn):
        return None
    try:
        result = fn(question)
        text = str(result or "").strip()
        return text or None
    except Exception:
        return None


# ============================================================
# Bridge: Unified_assistant.py (external RAG agent)
# ============================================================
#
# /api/chat forwards every question to the external assistant at
#   /Users/rana/Documents/tuwaiq/CP/external_rag/Unified_assistant.py
# (override path via env var: UNIFIED_ASSISTANT_PATH)
#
# Target function: answer_unified(question: str, verbose: bool = False) -> dict
#   returns {"final_answer": ..., "route": ..., "sql_answer": ..., "rag_answer": ..., ...}
#
# The function takes ONE question string — it does not accept spill_id or
# language as parameters. So when a spill is selected in the UI, we prepend
# its data summary to the question itself, so the assistant has grounding.

_UNIFIED_MODULE = None  # cached imported module
_UNIFIED_IMPORT_ERROR: Optional[str] = None


def _unified_path() -> Path:
    env = os.getenv("UNIFIED_ASSISTANT_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    base = ROOT_DIR / "external_rag"
    for name in ("Unified assistant.py", "Unified_assistant.py"):
        candidate = base / name
        if candidate.exists():
            return candidate
    return base / "Unified assistant.py"


def _format_rag_sources(chunks: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        source_name = str(chunk.get("source") or chunk.get("title") or "مستند").strip()
        page = chunk.get("page")
        title = f"{source_name} (ص {page})" if page not in (None, "", "N/A") else source_name
        formatted.append({
            "title": title,
            "domain": "local_rag",
            "url": str(chunk.get("url") or ""),
            "content": str(chunk.get("text") or chunk.get("content") or "")[:500],
        })
    return formatted


_WEAK_RAG_PHRASES = (
    "لا تتوفر",
    "لا توجد معلومات",
    "لا توجد مقاطع",
    "غير كافية",
    "لا أستطيع الإجابة",
    "i do not have enough information",
    "no relevant information",
    "cannot answer",
)


def _is_weak_rag_reply(reply: str, sources: Optional[List[Dict[str, Any]]] = None) -> bool:
    text = (reply or "").strip().lower()
    if not text:
        return True
    if any(phrase in text for phrase in _WEAK_RAG_PHRASES):
        return True
  # إذا وُجدت مصادر PDF لكن الإجابة تقول «لا معلومات» → رد ضعيف
    if sources and len(sources) > 0:
        if any(phrase in text for phrase in ("لا تتوفر", "غير كافية", "لا توجد معلومات")):
            return True
        titles = [str(s.get("title") or s.get("domain") or "").lower() for s in sources]
        if titles and all(".csv" in title for title in titles):
            return True
    return False


def run_rag_query(message: str, top_k: int = 5) -> Dict[str, Any]:
    refresh_rag_paths()
    try:
        try:
            from external_rag.rag_query import answer as rag_answer  # type: ignore
        except Exception:
            from rag_query import answer as rag_answer  # type: ignore
        result = rag_answer(message, k=int(top_k or 5), verbose=False)
        reply = str(result.get("answer") or "").strip()
        sources = _format_rag_sources(result.get("sources") or [])
        if reply and not _is_weak_rag_reply(reply, sources):
            return {"ok": True, "reply": reply, "sources": sources, "error": None}
        return {
            "ok": False,
            "reply": reply,
            "sources": sources,
            "error": "weak_or_empty_rag_answer",
        }
    except Exception as exc:
        return {"ok": False, "reply": "", "sources": [], "error": f"{type(exc).__name__}: {exc}"}


def _try_import_unified():
    """Import the external assistant once and cache it. Returns the module or None."""
    global _UNIFIED_MODULE, _UNIFIED_IMPORT_ERROR
    if _UNIFIED_MODULE is not None:
        return _UNIFIED_MODULE

    p = _unified_path()
    if not p.exists():
        _UNIFIED_IMPORT_ERROR = f"file not found: {p}"
        return None

    try:
        import importlib.util
        # The assistant imports `agent_module` and `rag_query` from its own folder,
        # so its directory MUST be on sys.path before exec_module runs.
        parent = str(p.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        spec = importlib.util.spec_from_file_location("unified_assistant", str(p))
        if spec is None or spec.loader is None:
            _UNIFIED_IMPORT_ERROR = "could not create import spec"
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _UNIFIED_MODULE = mod
        _UNIFIED_IMPORT_ERROR = None
        print(f"[unified] imported from {p}")
        return mod
    except Exception as e:
        _UNIFIED_IMPORT_ERROR = f"{type(e).__name__}: {e}"
        print(f"[unified] import failed: {_UNIFIED_IMPORT_ERROR}")
        return None


def _call_unified(question: str) -> Optional[str]:
    """Call answer_unified(question) and pull out final_answer."""
    mod = _try_import_unified()
    if mod is None:
        return None

    fn = getattr(mod, "answer_unified", None)
    if not callable(fn):
        # very defensive fallback — try alternative names if anyone renames it
        for alt in ("ask", "answer", "chat", "run", "query"):
            fn = getattr(mod, alt, None)
            if callable(fn):
                break

    if not callable(fn):
        print("[unified] module has no answer_unified/ask/answer function")
        return None

    try:
        result = fn(question)
    except TypeError:
        # signature might differ — try with verbose=False
        try:
            result = fn(question, False)
        except Exception as e:
            print(f"[unified] call failed: {type(e).__name__}: {e}")
            return None
    except Exception as e:
        print(f"[unified] call failed: {type(e).__name__}: {e}")
        return None

    if isinstance(result, dict):
        for key in ("final_answer", "answer", "reply", "text"):
            val = result.get(key)
            if val:
                return str(val).strip()
        # nothing matched — return the whole dict serialised
        return None
    if isinstance(result, str):
        return result.strip()
    if result is not None:
        return str(result).strip()
    return None


@app.post("/api/chat")
async def chat_endpoint(req: SmartChatRequest) -> Dict[str, Any]:
    global _CHAT_REPLY_LANG
    lang = (req.language or "ar").lower()
    _CHAT_REPLY_LANG = lang
    is_ar = lang == "ar"
    df = _chat_load_df()
    history_items = [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in (req.history or [])
    ]
    explicit_selected = _find_spill(df, req.spill_id) if req.spill_id and not df.empty else None
    compare_selected: List[Dict[str, Any]] = []
    compare_seen: set[str] = set()
    for compare_id in (req.compare_spill_ids or []):
        compare_spill = _find_spill(df, compare_id) if compare_id and not df.empty else None
        if not compare_spill:
            continue
        compare_key = _t(compare_spill, ["spill_id", "id", "filename"], str(compare_id))
        if compare_key in compare_seen:
            continue
        compare_seen.add(compare_key)
        compare_selected.append(compare_spill)
    named_spill = _extract_named_spill_reference(df, req.message) if not df.empty else None
    followup_spill_id = _history_resolved_spill_id(history_items) if _is_followup_question(req.message) else None
    followup_spill = _find_spill(df, followup_spill_id) if followup_spill_id and not df.empty else None
    selected = explicit_selected or named_spill or followup_spill
    resolved_spill_id = _t(selected, ["spill_id", "id", "filename"], "") if selected else None
    intent = detect_question_intent(
        req.message,
        bool(explicit_selected),
        named_spill=named_spill,
        history=history_items,
        compare_count=len(compare_selected),
    )

    if intent == "guardrail":
        reply = (
            "أستطيع المساعدة فقط في أسئلة التسرّبات النفطية، التحليل، الخطورة، الخرائط، التقارير، التأثير البيئي، وخطط الاستجابة."
            if is_ar
            else "I can only help with oil-spill questions, analysis, risk, maps, reports, environmental impact, and response plans."
        )
        return _chat_reply(reply, source_used="guardrail", intent=intent)

    if intent == "clarification":
        reply = (
            "أحتاج تحدد الحالة المقصودة أولاً حتى أعطيك تحليلاً أو حلاً دقيقاً. اختر الحالة من القائمة أو من الخيارات التالية."
            if is_ar
            else "I need you to specify which spill you mean first, so I can give you an accurate analysis or response plan. Select a spill from the list or from the options below."
        )
        return _chat_reply(
            reply,
            source_used="clarification",
            intent=intent,
            needs_clarification=True,
            clarification_options=_clarification_options(df, lang),
        )

    if intent == "metric_clarification":
        reply = (
            "هل تقصد في open sea: المتوسط، العدد، أم أخطر الحالات؟ اكتب سؤالك بشكل أوضح مثل: `متوسط حالات التسرب في open sea`."
            if is_ar
            else "Do you mean the average, the count, or the highest-risk cases in open sea? Please phrase it more clearly, for example: `average spill area in open sea`."
        )
        return _chat_reply(
            reply,
            source_used="clarification",
            intent=intent,
        )

    if intent == "followup_explanation":
        reply = _explain_previous_answer(req.message, history_items, selected, lang)
        return _chat_reply(
            reply,
            source_used="followup_explanation",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    if intent == "agent_meta":
        reply = _answer_agent_meta_question(req.message, lang)
        return _chat_reply(
            reply,
            source_used="agent_meta",
            intent=intent,
        )

    if intent == "aggregate_data":
        reply = _answer_aggregate_question(df, req.message, top_k=req.top_k or 5, lang=lang)
        return _chat_reply(
            reply,
            source_used="database",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    if intent == "spill_compare" and len(compare_selected) >= 2:
        reply = _answer_spill_comparison(compare_selected, req.message, lang)
        return _chat_reply(
            reply,
            source_used="spill_compare",
            intent=intent,
        )

    if intent == "solution_search" and selected:
        result = answer_solution_question_with_search(selected, req.message, lang)
        return _chat_reply(
            result["reply"],
            source_used=result["source_used"],
            intent=intent,
            used_search=bool(result.get("used_search")),
            sources=result.get("sources") or [],
            resolved_spill_id=resolved_spill_id,
        )

    if intent == "general_solution" and not selected:
        reply = (
            "أستطيع إعطاء خطة عامة للاستجابة، لكن إذا أردت حلاً مبنياً على حالة محددة ومصادر موثوقة فحدد الحالة أولاً."
            "\n\n" + _response_plan(lang)
            if is_ar
            else "I can provide a general response guide, but if you want a case-specific plan grounded in trusted sources, please select the spill first."
            + "\n\n" + _response_plan(lang)
        )
        return _chat_reply(reply, source_used="response_guide", intent=intent)

    if intent == "rag_knowledge":
        concept_fallback = _answer_rag_concept_fallback(req.message, lang)
        rag_result = run_rag_query(req.message, top_k=req.top_k or 5)
        rag_sources = rag_result.get("sources") or []
        if rag_result.get("ok") and rag_result.get("reply"):
            return _chat_reply(
                str(rag_result["reply"]),
                source_used="rag_knowledge",
                intent=intent,
                sources=rag_sources,
                resolved_spill_id=resolved_spill_id,
            )
        if concept_fallback:
            return _chat_reply(
                concept_fallback,
                source_used="rag_concept_guide",
                intent=intent,
                sources=rag_sources,
                resolved_spill_id=resolved_spill_id,
            )
        return _chat_reply(
            (
                "لم أجد مقطعًا كافيًا في المستندات التقنية لهذا السؤال. "
                "تأكدي من فهرس RAG (external_rag/rag_db) ثم أعيدي السؤال."
            )
            if is_ar
            else "I could not find enough technical-document context for this question. Please verify the RAG index and try again.",
            ok=False,
            source_used="rag_knowledge",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    if intent == "environmental_knowledge":
        if selected:
            local_env = _answer_selected_spill_question(selected, req.message, lang)
            if local_env:
                return _chat_reply(
                    local_env,
                    source_used="selected_spill_environment",
                    intent=intent,
                    resolved_spill_id=resolved_spill_id,
                )
        rag_result = run_rag_query(req.message, top_k=req.top_k or 5)
        if rag_result.get("ok") and rag_result.get("reply"):
            return _chat_reply(
                str(rag_result["reply"]),
                source_used="rag_knowledge",
                intent=intent,
                sources=rag_result.get("sources") or [],
                resolved_spill_id=resolved_spill_id,
            )
        return _chat_reply(
            _answer_general_environmental_knowledge(req.message, lang),
            source_used="environmental_guide",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    if intent == "spill_specific" and selected:
        local_selected_reply = _answer_selected_spill_question(selected, req.message, lang)
        if local_selected_reply:
            return _chat_reply(
                local_selected_reply,
                source_used="selected_spill_local",
                intent=intent,
                resolved_spill_id=resolved_spill_id,
            )

    question = req.message or ""
    history_context = _chat_history_context(history_items, lang)
    if selected:
        summary = _selected_summary(selected, lang)
        if is_ar:
            question = (
                f"{history_context}\n\n"
                f"[سياق: الحالة المحددة هي {resolved_spill_id}]\n"
                f"{summary}\n\n"
                f"[سؤال المستخدم]\n{req.message}"
            ).strip()
        else:
            question = (
                f"{history_context}\n\n"
                f"[Context: selected spill is {resolved_spill_id}]\n"
                f"{summary}\n\n"
                f"[User question]\n{req.message}"
            ).strip()
    elif is_ar:
        question = (
            f"{history_context}\n\n"
            "[تعليمات: لا تفترض حالة بعينها إلا إذا ذكرها المستخدم صراحة. "
            "التزم فقط بمجال التسرّبات النفطية والتحليل البيئي والاستجابة.]"
            f"\n[سؤال المستخدم]\n{req.message}"
        ).strip()
    else:
        question = (
            f"{history_context}\n\n"
            "[Instructions: do not assume a specific spill unless the user names one explicitly. "
            "Stay within oil-spill detection, environmental analysis, and response planning.]"
            f"\n[User question]\n{req.message}"
        ).strip()

    try:
        external_reply = _call_unified(question)
    except Exception as exc:
        external_reply = None
        print(f"[unified] top-level error: {type(exc).__name__}: {exc}")

    if external_reply and external_reply.strip():
        return _chat_reply(
            external_reply.strip(),
            source_used="unified_assistant",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    if selected:
        return _chat_reply(
            _environment_answer(selected, req.message, lang),
            source_used="fallback_csv_environment",
            intent=intent,
            resolved_spill_id=resolved_spill_id,
        )

    db_answer = _call_database_agent(req.message)
    if db_answer:
        return _chat_reply(
            db_answer,
            source_used="database_agent",
            intent="aggregate_data" if intent == "general" else intent,
            resolved_spill_id=resolved_spill_id,
        )

    if _is_environmental_knowledge_question(req.message):
        return _chat_reply(
            _answer_general_environmental_knowledge(req.message, lang),
            source_used="environmental_guide",
            intent="environmental_knowledge",
            resolved_spill_id=resolved_spill_id,
        )

    fallback = (
        "لم أتمكن من تحديد إجابة موثوقة من البيانات الحالية. أعد صياغة السؤال بشكل أوضح أو حدد حالة تسرب بعينها."
        if is_ar
        else "I could not determine a reliable answer from the current data. Please rephrase the question or select a specific spill."
    )
    return _chat_reply(fallback, ok=False, source_used="chat_fallback", intent=intent)


@app.get("/api/chat/status")
def chat_status() -> Dict[str, Any]:
    """Lightweight diagnostic: shows whether Unified_assistant is reachable."""
    p = _unified_path()
    mod = _try_import_unified()
    fn = getattr(mod, "answer_unified", None) if mod else None
    return {
        "unified_path": str(p),
        "path_exists": p.exists(),
        "module_imported": mod is not None,
        "answer_unified_present": callable(fn),
        "import_error": _UNIFIED_IMPORT_ERROR,
    }





# ============================================================
# Restored Solutions + Solution Reports helpers
# ============================================================

class FrontendReportRequest(BaseModel):
    spill_id: str
    language: Optional[str] = "ar"


class FrontendSolutionsRequest(BaseModel):
    spill_id: str
    language: Optional[str] = "ar"


def _fr_load_df():
    import os
    import pandas as pd
    from pathlib import Path

    csv_path = os.getenv("CSV_PATH")
    if csv_path and Path(csv_path).exists():
        return pd.read_csv(csv_path)

    cp = Path("/Users/rana/Documents/tuwaiq/CP")
    hits = list(cp.rglob("spill_analysis_results_full.csv")) + list(cp.rglob("*spill*analysis*results*.csv"))
    if hits:
        return pd.read_csv(hits[0])

    return pd.DataFrame()


def _fr_text(row, keys, default="غير متوفر"):
    for k in keys:
        if isinstance(row, dict) and k in row and row[k] == row[k]:
            v = str(row[k])
            if v.lower() != "nan":
                return v
    return default


def _fr_num(row, keys, default=0.0):
    for k in keys:
        if isinstance(row, dict) and k in row and row[k] == row[k]:
            try:
                return float(row[k])
            except Exception:
                pass
    return default


def _fr_find_spill(spill_id: str):
    from pathlib import Path

    def _candidates(value: Any) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        items = {
            raw,
            Path(raw).name,
            Path(raw).stem,
            raw.replace("\\", "/").split("/")[-1],
        }
        lower = raw.lower()
        if lower.startswith("tif.") and len(raw) > 4:
            items.add(f"{raw[4:]}.tif")
        if lower.endswith(".tif"):
            items.add(lower)
            items.add(Path(lower).stem)
        digits = "".join(re.findall(r"\d+", raw))
        if digits:
            items.add(digits)
            items.add(f"{digits}.tif")
            items.add(digits.lstrip("0") or "0")
        return [item for item in items if item]

    try:
        old = get_spill_by_id(spill_id)
        if old:
            return old
    except Exception:
        pass

    df = _fr_load_df()
    if df.empty:
        return None

    wanted = {str(item).lower() for item in _candidates(spill_id)}

    for col in ["filename", "spill_id", "id", "source_image", "source_image_path"]:
        if col in df.columns:
            series = df[col].astype(str)
            hit = df[series.apply(lambda x: bool(wanted.intersection({c.lower() for c in _candidates(x)})))]
            if not hit.empty:
                return hit.iloc[0].to_dict()

    return None


def _fr_unique(items: List[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _fr_bullets(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in _fr_unique(items))


def _fr_fmt_num(value: float, decimals: int = 2) -> str:
    return f"{value:,.{decimals}f}"


def _fr_is_missing_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return not text or text in {"nan", "none", "null", "unknown", "غير معروف", "غير متوفر"}


def safe_value(value: Any, language: str = "ar") -> str:
    if value is None:
        return "غير متاح / يحتاج تحقق" if language == "ar" else "Unavailable / needs verification"
    if isinstance(value, float):
        try:
            if math.isnan(value):
                return "غير متاح / يحتاج تحقق" if language == "ar" else "Unavailable / needs verification"
        except Exception:
            pass
    text = str(value).strip()
    if _fr_is_missing_text(text):
        return "غير متاح / يحتاج تحقق" if language == "ar" else "Unavailable / needs verification"
    return text


def format_number_ar(value: Any, unit: str = "", decimals: int = 2, language: str = "ar") -> str:
    try:
        number = float(value)
        if math.isnan(number):
            raise ValueError("NaN")
    except Exception:
        return safe_value(None, language)

    formatted = _fr_fmt_num(number, decimals)
    return f"{formatted} {unit}".strip()


def _valid_proximity_class(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    invalid = {"unknown", "none", "null", "nan", "غير معروف", "غير متوفر", "unavailable"}
    return text not in invalid


def _safe_distance(value: Any, proximity_class: Any, language: str = "ar") -> str:
    try:
        distance = float(value)
        if math.isnan(distance):
            raise ValueError("NaN")
    except Exception:
        return safe_value(None, language)

    if distance < 0:
        return safe_value(None, language)
    if distance == 0 and not _valid_proximity_class(proximity_class):
        return safe_value(None, language)
    return format_number_ar(distance, "كم" if language == "ar" else "km", 2, language)


def _is_confirmed_proximity(value: Any, proximity_class: Any, threshold_km: float = 5.0) -> bool:
    try:
        distance = float(value)
        if math.isnan(distance):
            return False
    except Exception:
        return False
    if distance == 0:
        return _valid_proximity_class(proximity_class)
    return 0 < distance <= threshold_km


def _has_confirmed_spill(area: float, coverage: float) -> bool:
    return area > 0 and coverage > 0


def build_data_quality_note(spill, language: str = "ar") -> Optional[str]:
    area = _fr_num(spill, ["area_m2"])
    coverage = _fr_num(spill, ["coverage_pct"])
    if area <= 0 or coverage <= 0:
        return (
            "تنبيه بيانات: لم يتم رصد مساحة تسرب مؤكدة في هذه القراءة، لذلك تُعامل التوصيات كخطة مراقبة احترازية."
            if language == "ar"
            else "Data note: no confirmed spill area was detected in this reading, so recommendations are treated as a precautionary monitoring plan."
        )
    return None


def classify_operational_decision(spill, language: str = "ar") -> Dict[str, Any]:
    risk = normalize_risk(_fr_text(spill, ["final_risk_level", "risk_level"], "Low"))
    area = _fr_num(spill, ["area_m2"])
    coverage = _fr_num(spill, ["coverage_pct"])
    land = _fr_num(spill, ["distance_to_land_km"])
    coral = _fr_num(spill, ["distance_to_coral_km"])
    land_class = _fr_text(spill, ["land_proximity_class"], "")
    coral_class = _fr_text(spill, ["coral_risk_class", "coral_proximity_class"], "")
    confirmed = _has_confirmed_spill(area, coverage)
    near_land = _is_confirmed_proximity(land, land_class, threshold_km=5.0)
    near_coral = _is_confirmed_proximity(coral, coral_class, threshold_km=5.0)
    large_spill = area >= 50000 or coverage >= 5
    very_large = area >= 100000 or coverage >= 10

    if not confirmed:
        if risk in {"High", "Critical"} or near_land or near_coral:
            badge = "استعداد محدود" if language == "ar" else "Limited readiness"
            decision = (
                "القرار الحالي هو التحقق السريع مع رفع الجاهزية المحدودة، دون اعتماد استجابة ميدانية كاملة قبل تأكيد القراءة."
                if language == "ar"
                else "The current decision is rapid verification with limited readiness, without full field deployment until the reading is confirmed."
            )
            reason = (
                "السبب: القراءة لا تُظهر مساحة تسرب مؤكدة، لكن مستوى الخطورة أو القرب من عنصر حساس يبرر الاستعداد المحدود."
                if language == "ar"
                else "Reason: the reading does not confirm spill area, but the severity level or proximity to a sensitive receptor justifies limited readiness."
            )
        else:
            badge = "مراقبة فقط" if language == "ar" else "Monitoring only"
            decision = (
                "الأولوية الحالية هي المراقبة والتحقق البصري، وليس التدخل الميداني الكامل."
                if language == "ar"
                else "The current priority is monitoring and visual verification, not full field intervention."
            )
            reason = (
                "السبب: المساحة أو التغطية غير مؤكدة في هذه القراءة، ولا توجد مؤشرات تشغيلية كافية لتصعيد فوري."
                if language == "ar"
                else "Reason: area or coverage is unconfirmed in this reading, and there is not enough operational evidence for immediate escalation."
            )
    elif risk in {"High", "Critical"} or very_large or (near_land and near_coral):
        badge = "استجابة عاجلة" if language == "ar" else "Urgent response"
        decision = (
            "القرار الموصى به هو تفعيل تخطيط الاستجابة العاجلة وبدء تجهيز الاحتواء والحماية البيئية فورًا."
            if language == "ar"
            else "The recommended decision is to activate urgent response planning and prepare containment and environmental protection immediately."
        )
        reason = (
            "السبب: مستوى الخطورة مرتفع أو أن حجم القراءة/حساسيتها يبرر تصعيدًا تشغيليًا عاجلًا."
            if language == "ar"
            else "Reason: the risk level is elevated or the spill magnitude/sensitivity justifies urgent operational escalation."
        )
    elif risk == "Medium" or large_spill or near_land or near_coral:
        badge = "استعداد محدود" if language == "ar" else "Limited readiness"
        decision = (
            "القرار الموصى به هو رفع الجاهزية التشغيلية مع التحقق الميداني وتخطيط احتواء محدود إذا لزم الأمر."
            if language == "ar"
            else "The recommended decision is limited operational readiness with field verification and constrained containment planning if needed."
        )
        reason = (
            "السبب: القراءة تؤكد وجود حالة متوسطة أو قريبة من عنصر حساس، لكنها لا تستدعي نشرًا واسعًا منذ البداية."
            if language == "ar"
            else "Reason: the reading confirms a moderate or sensitive case, but not one that requires full-scale deployment at the outset."
        )
    else:
        badge = "مراقبة فقط" if language == "ar" else "Monitoring only"
        decision = (
            "القرار الموصى به هو المراقبة المنتظمة والتحقق الدوري دون نشر استجابة ميدانية واسعة."
            if language == "ar"
            else "The recommended decision is routine monitoring and periodic verification without broad field deployment."
        )
        reason = (
            "السبب: مستوى الخطورة منخفض والمساحة أو التغطية لا تشير إلى حالة تشغيلية كبيرة."
            if language == "ar"
            else "Reason: the risk level is low and the area/coverage does not indicate a significant operational case."
        )

    return {
        "risk": risk,
        "area": area,
        "coverage": coverage,
        "land": land,
        "coral": coral,
        "land_class": land_class,
        "coral_class": coral_class,
        "confirmed": confirmed,
        "near_land": near_land,
        "near_coral": near_coral,
        "large_spill": large_spill,
        "very_large": very_large,
        "decision_badge": badge,
        "operational_decision": decision,
        "decision_reason": reason,
        "data_quality_note": build_data_quality_note(spill, language),
        "land_display": _safe_distance(land, land_class, language),
        "coral_display": _safe_distance(coral, coral_class, language),
    }


def build_executive_summary(spill, decision: Dict[str, Any], language: str = "ar") -> str:
    spill_id = _fr_text(spill, ["spill_id", "id", "filename"], "")
    filename = _fr_text(spill, ["filename", "spill_id", "id"], spill_id)
    risk = decision["risk"]
    area = decision["area"]
    coverage = decision["coverage"]
    near_land = decision["near_land"]
    near_coral = decision["near_coral"]

    if language == "ar":
        if not decision["confirmed"]:
            return (
                f"تُظهر قراءة الحالة {filename} مستوى خطورة مصنفًا عند {risk}، إلا أن المساحة المؤكدة غير متاحة "
                f"حيث بلغت المساحة {_fr_fmt_num(area)} م² ونسبة التغطية {_fr_fmt_num(coverage)}%. "
                f"بناءً على ذلك تُعامل الحالة حاليًا كقراءة تحتاج إلى تحقق بصري أو صورة لاحقة قبل اعتماد تدخل ميداني كامل."
            )
        summary = (
            f"تشير قراءة الحالة {filename} إلى حالة تشغيلية بمستوى خطورة {risk}، "
            f"ومساحة مؤكدة تبلغ {_fr_fmt_num(area)} م² ونسبة تغطية {_fr_fmt_num(coverage)}%. "
        )
        if near_land:
            summary += "القرب من اليابسة يرفع احتمال التأثر الساحلي المباشر. "
        if near_coral:
            summary += "القرب من الشعاب المرجانية يرفع أولوية الحماية البيئية المبكرة. "
        summary += decision["operational_decision"]
        return summary.strip()

    if not decision["confirmed"]:
        return (
            f"Case {filename} is currently classified at {risk}, but the reading does not confirm a spill footprint "
            f"(area {_fr_fmt_num(area)} m², coverage {_fr_fmt_num(coverage)}%). "
            f"The case is therefore treated as a verification-driven monitoring situation rather than a confirmed active spill."
        )
    summary = (
        f"Case {filename} reflects a {risk} operational reading with a confirmed area of {_fr_fmt_num(area)} m² "
        f"and coverage of {_fr_fmt_num(coverage)}%. "
    )
    if near_land:
        summary += "Its proximity to land raises shoreline exposure risk. "
    if near_coral:
        summary += "Its proximity to coral reefs elevates environmental protection priority. "
    summary += decision["operational_decision"]
    return summary.strip()


def _fr_confirmed_data_rows(spill, decision: Dict[str, Any], language: str = "ar") -> List[Tuple[str, str]]:
    created_at = _fr_text(spill, ["created_at", "processed_at", "generated_at"], "")
    lat = _fr_num(spill, ["latitude", "spill_centroid_lat"], None)
    lon = _fr_num(spill, ["longitude", "spill_centroid_lon"], None)
    coordinates = (
        f"{lat:.6f}, {lon:.6f}" if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and not (lat == 0 and lon == 0)
        else safe_value(None, language)
    )
    if language == "ar":
        return [
            ("معرف الحالة", _fr_text(spill, ["spill_id", "id", "filename"], "")),
            ("اسم الملف", _fr_text(spill, ["filename", "spill_id", "id"], "")),
            ("مستوى الخطورة", decision["risk"]),
            ("المساحة المؤكدة", format_number_ar(decision["area"], "م²", 2, language)),
            ("نسبة التغطية في الصورة", format_number_ar(decision["coverage"], "%", 2, language)),
            ("المسافة إلى اليابسة", decision["land_display"]),
            ("تصنيف قرب اليابسة", safe_value(decision["land_class"], language)),
            ("المسافة إلى الشعاب", decision["coral_display"]),
            ("تصنيف الشعاب", safe_value(decision["coral_class"], language)),
            ("الإحداثيات", coordinates),
            ("تاريخ القراءة/التقرير", safe_value(created_at, language)),
        ]
    return [
        ("Spill ID", _fr_text(spill, ["spill_id", "id", "filename"], "")),
        ("File", _fr_text(spill, ["filename", "spill_id", "id"], "")),
        ("Risk level", decision["risk"]),
        ("Confirmed area", format_number_ar(decision["area"], "m²", 2, language)),
        ("Image coverage", format_number_ar(decision["coverage"], "%", 2, language)),
        ("Distance to land", decision["land_display"]),
        ("Land proximity class", safe_value(decision["land_class"], language)),
        ("Distance to coral", decision["coral_display"]),
        ("Coral class", safe_value(decision["coral_class"], language)),
        ("Coordinates", coordinates),
        ("Reading/report time", safe_value(created_at, language)),
    ]


def _fr_build_risk_factors(spill, decision: Dict[str, Any], language: str = "ar") -> List[str]:
    risk = decision["risk"]
    area = decision["area"]
    coverage = decision["coverage"]
    factors: List[str] = []
    if language == "ar":
        factors.append(f"مستوى الخطورة الحالي: {risk}. السبب: هذا هو التصنيف المسجل في بيانات الحالة.")
        if decision["confirmed"]:
            factors.append(f"المساحة المؤكدة {_fr_fmt_num(area)} م² ونسبة التغطية {_fr_fmt_num(coverage)}%. السبب: القراءة الحالية تثبت وجود أثر مرصود يمكن التعامل معه تشغيليًا.")
        else:
            factors.append(f"لا توجد مساحة تسرب مؤكدة في هذه القراءة. السبب: المساحة {_fr_fmt_num(area)} م² أو التغطية {_fr_fmt_num(coverage)}% لا تدعم تأكيد بقعة نشطة.")
        if decision["near_land"]:
            factors.append("القرب من اليابسة يرفع أولوية الحماية الساحلية. السبب: قرب الحالة من الساحل يزيد احتمال التأثر المباشر إذا استمر الانتشار.")
        else:
            factors.append(f"القرب من اليابسة: {decision['land_display']}. السبب: لا توجد دلالة تشغيلية مؤكدة على تماس ساحلي مباشر في القراءة الحالية.")
        if decision["near_coral"]:
            factors.append("القرب من الشعاب المرجانية يرفع أولوية المراقبة البيئية. السبب: المناطق المرجانية أكثر حساسية لأي انتشار إضافي.")
        else:
            factors.append(f"القرب من الشعاب: {decision['coral_display']}. السبب: لا توجد قراءة مؤكدة تستدعي افتراض تماس مباشر مع الشعاب.")
        return _fr_unique(factors)

    factors.append(f"Current risk level: {risk}. Reason: this is the recorded severity classification for the case.")
    if decision["confirmed"]:
        factors.append(f"Confirmed area {_fr_fmt_num(area)} m² and coverage {_fr_fmt_num(coverage)}%. Reason: the current reading supports a detectable operational footprint.")
    else:
        factors.append(f"No confirmed spill area is present in this reading. Reason: area {_fr_fmt_num(area)} m² or coverage {_fr_fmt_num(coverage)}% does not support confirmation of an active slick.")
    if decision["near_land"]:
        factors.append("Proximity to land raises shoreline protection priority. Reason: a nearby coastline is more exposed if spread continues.")
    if decision["near_coral"]:
        factors.append("Proximity to coral reefs raises environmental monitoring priority. Reason: reef systems are highly sensitive receptors.")
    return _fr_unique(factors)


def build_action_plan(spill, decision: Dict[str, Any], language: str = "ar") -> Dict[str, List[str]]:
    confirmed = decision["confirmed"]
    risk = decision["risk"]
    near_land = decision["near_land"]
    near_coral = decision["near_coral"]
    large_spill = decision["large_spill"]

    if language == "ar":
        if not confirmed:
            return {
                "next_24h": _fr_unique([
                    "مراجعة القراءة بصريًا ومقارنتها بلقطة زمنية لاحقة. السبب: لا توجد مساحة تسرب مؤكدة في القراءة الحالية.",
                    "إبقاء فرق الاستجابة في وضع المتابعة دون نشر ميداني كامل. السبب: القرار الحالي احترازي ويعتمد على التحقق.",
                    "طلب تحقق ميداني محدود إذا كانت المنطقة قريبة من عنصر حساس. السبب: الحساسية البيئية قد ترفع الحاجة إلى تأكيد أسرع." if (near_land or near_coral) else "الاكتفاء بالمراقبة الدورية وتحديث السجل التشغيلي. السبب: لا توجد مؤشرات تشغيلية كافية على بقعة مؤكدة.",
                ]),
                "monitoring": _fr_unique([
                    "متابعة الصورة التالية أو طبقة الرصد التالية خلال نافذة زمنية قصيرة.",
                    "مقارنة نتائج المساحة والتغطية مع أي قراءة لاحقة قبل اعتماد التصعيد.",
                    "توثيق أي تغير في القرب من الساحل أو الشعاب على أنه يحتاج تحقق إضافي.",
                ]),
                "equipment": _fr_unique([
                    "أدوات متابعة وتوثيق",
                    "وصول إلى صور لاحقة أو طبقات رصد بديلة",
                    "معدات تحقق ميداني محدودة إذا تطلب الموقع ذلك",
                ]),
            }

        next_24h = [
            "تأكيد حدود البقعة واتجاه الانتشار قبل تثبيت الانتشار الميداني. السبب: القرار التشغيلي يجب أن يستند إلى حدود مؤكدة للقراءة الحالية.",
            "مراجعة جاهزية فرق الاستجابة وتوزيع الأدوار التشغيلية. السبب: منع التأخر عند الحاجة إلى التصعيد.",
        ]
        if risk in {"High", "Critical"} or large_spill:
            next_24h.extend([
                "تجهيز الحواجز العائمة ووسائل الاحتواء حول المحاور الأكثر تعرضًا للانتشار. السبب: الحجم أو مستوى الخطورة يبرران تقليل الامتداد مبكرًا.",
                "تكليف فرق ميدانية ومعاينة بيئية بالتحرك خلال نافذة سريعة. السبب: القراءة المؤكدة تستلزم قرارًا ميدانيًا مبكرًا.",
            ])
        elif near_land or near_coral:
            next_24h.append("وضع خطة احتواء محدودة قرب المناطق الحساسة دون نشر كامل. السبب: القرب من الساحل أو الشعاب يرفع أولوية الجاهزية.")
        else:
            next_24h.append("الإبقاء على جاهزية محدودة مع متابعة دورية. السبب: الحالة مؤكدة ولكنها لا تشير حاليًا إلى انتشار واسع.")

        monitoring = [
            "تحديث الرصد كل 3 إلى 6 ساعات عند توافر صور أو بيانات لاحقة.",
            "تسجيل أي زيادة في المساحة أو التغطية على أنها مؤشر تصعيد مباشر.",
            "مراجعة القرب من الساحل أو الشعاب عند كل تحديث جديد.",
        ]

        equipment: List[str] = []
        if risk in {"High", "Critical"} or large_spill:
            equipment.extend(["حواجز عائمة", "كاشطات سطحية", "مواد ماصة", "معدات حماية شخصية", "قوارب دعم", "أدوات أخذ عينات"])
        elif near_land or near_coral:
            equipment.extend(["أدوات مراقبة ميدانية", "معدات احتواء محدودة", "وسائل توثيق واتصال"])
        else:
            equipment.extend(["وسائل متابعة ورصد", "معدات تحقق ميداني عند الحاجة"])
        return {
            "next_24h": _fr_unique(next_24h),
            "monitoring": _fr_unique(monitoring),
            "equipment": _fr_unique(equipment),
        }

    # English fallback
    if not confirmed:
        return {
            "next_24h": _fr_unique([
                "Review the reading visually and compare it with a later image. Reason: no confirmed spill area is present in the current reading.",
                "Keep response teams in monitoring posture without full deployment. Reason: the current decision is precautionary and verification-driven.",
            ]),
            "monitoring": _fr_unique([
                "Check the next image or monitoring layer in a short time window.",
                "Compare area and coverage values against any subsequent reading before escalation.",
            ]),
            "equipment": _fr_unique([
                "Monitoring/documentation tools",
                "Access to later imagery or alternate observation layers",
            ]),
        }
    return {
        "next_24h": _fr_unique([
            "Confirm spill boundaries and drift direction before locking operational deployment.",
            "Review response readiness and role allocation.",
        ]),
        "monitoring": _fr_unique([
            "Refresh monitoring every 3 to 6 hours when new data is available.",
            "Treat any rise in area or coverage as an escalation trigger.",
        ]),
        "equipment": _fr_unique(["Containment booms", "Monitoring tools", "Field sampling kits"] if risk in {"High", "Critical"} else ["Monitoring tools"]),
    }


def _fr_build_escalation_triggers(spill, decision: Dict[str, Any], language: str = "ar") -> List[str]:
    if language == "ar":
        triggers = [
            "زيادة المساحة أو نسبة التغطية في قراءة لاحقة.",
            "تأكيد ميداني بوجود بقعة مرئية أو امتداد فعلي.",
            "تحول القرب من اليابسة أو الشعاب إلى قراءة مؤكدة.",
        ]
        if decision["near_land"] or decision["near_coral"]:
            triggers.append("أي مؤشرات على انتقال البقعة باتجاه الساحل أو الشعاب تتطلب رفع مستوى الاستجابة فورًا.")
        return _fr_unique([f"{item} السبب: هذا التغير ينقل الحالة إلى مستوى تشغيلي أعلى." for item in triggers])
    return _fr_unique([
        "A later reading shows an increase in area or coverage. Reason: this indicates operational growth.",
        "Field confirmation detects a visible slick or active spread. Reason: this upgrades the reading from precautionary to confirmed response.",
    ])


def render_sources(sources: List[Dict[str, Any]], language: str = "ar") -> str:
    if not sources:
        fallback = (
            "لم يتم إرفاق مصادر خارجية موثوقة لهذا التقرير، وتم الاعتماد على بيانات النموذج وقاعدة البيانات وخطة التشغيل المحلية."
            if language == "ar"
            else "No trusted external sources were attached to this report; the report is based on model output, database records, and the local operational plan."
        )
        return f"<p>{html.escape(fallback)}</p>"

    rows = []
    for source in sources:
        title = html.escape(str(source.get("title") or source.get("domain") or ""))
        domain = html.escape(str(source.get("domain") or ""))
        url = html.escape(str(source.get("url") or ""))
        if not url:
            continue
        rows.append(
            f"<div class='source-item'><div class='source-title'>{title}</div><div class='source-domain'>{domain}</div><a href='{url}' target='_blank' rel='noreferrer'>{url}</a></div>"
        )
    if not rows:
        return render_sources([], language)
    return "".join(rows)


def _spill_report_text_for_search(spill, language="ar") -> str:
    risk = normalize_risk(_fr_text(spill, ["final_risk_level", "risk_level"], "Low"))
    spill_id = _fr_text(spill, ["spill_id", "id", "filename"], "")
    filename = _fr_text(spill, ["filename", "spill_id", "id"], spill_id)
    area = _fr_num(spill, ["area_m2"])
    coverage = _fr_num(spill, ["coverage_pct"])
    land = _fr_num(spill, ["distance_to_land_km"])
    coral = _fr_num(spill, ["distance_to_coral_km"])
    latitude = _fr_num(spill, ["latitude", "spill_centroid_lat"], 0.0)
    longitude = _fr_num(spill, ["longitude", "spill_centroid_lon"], 0.0)
    is_ar = (language or "ar").lower() == "ar"

    if is_ar:
        return (
            "تقرير تحليل تسرب نفطي\n"
            f"- المعرف: {spill_id}\n"
            f"- الملف: {filename}\n"
            f"- مستوى الخطورة: {risk}\n"
            f"- المساحة: {_fr_fmt_num(area)} م²\n"
            f"- نسبة التغطية: {_fr_fmt_num(coverage)}%\n"
            f"- الإحداثيات: {latitude:.6f}, {longitude:.6f}\n"
            f"- المسافة من الساحل: {_fr_fmt_num(land)} كم\n"
            f"- المسافة من الشعاب المرجانية: {_fr_fmt_num(coral)} كم\n"
        )

    return (
        "Oil spill analysis report\n"
        f"- Spill ID: {spill_id}\n"
        f"- File: {filename}\n"
        f"- Risk level: {risk}\n"
        f"- Area: {_fr_fmt_num(area)} m²\n"
        f"- Coverage: {_fr_fmt_num(coverage)}%\n"
        f"- Coordinates: {latitude:.6f}, {longitude:.6f}\n"
        f"- Distance to shoreline: {_fr_fmt_num(land)} km\n"
        f"- Distance to coral reefs: {_fr_fmt_num(coral)} km\n"
    )


def _fr_with_web_plan(payload: Dict[str, Any], spill, language="ar") -> Dict[str, Any]:
    report_text = _spill_report_text_for_search(spill, language)
    search_result = _search_response_agent_cached(report_text)
    trusted_sources: List[Dict[str, Any]] = []

    status = str(search_result.get("status") or "unavailable")
    plan = search_result.get("plan")
    payload["web_plan_status"] = status
    payload["web_plan"] = plan
    if status == "ready":
        try:
            trusted_sources = _collect_trusted_sources_for_spill(spill)
        except Exception:
            trusted_sources = []
    payload["trusted_sources"] = trusted_sources

    if plan:
        payload["source"] = "response_report_builder+search_response_agent"
    return payload


def _fr_priority_window(risk: str, language: str) -> str:
    is_ar = (language or "ar").lower() == "ar"
    if risk == "Critical":
        return "خلال ساعتين" if is_ar else "within 2 hours"
    if risk == "High":
        return "خلال 6 ساعات" if is_ar else "within 6 hours"
    if risk == "Medium":
        return "خلال 12 ساعة" if is_ar else "within 12 hours"
    return "خلال 24 ساعة" if is_ar else "within 24 hours"


def _fr_solution_payload(spill, language="ar"):
    is_ar = (language or "ar").lower() == "ar"
    decision = classify_operational_decision(spill, language)
    spill_id = _fr_text(spill, ["spill_id", "id", "filename"], "")
    filename = _fr_text(spill, ["filename", "spill_id", "id"], spill_id)
    area = decision["area"]
    coverage = decision["coverage"]
    latitude = _fr_num(spill, ["latitude", "spill_centroid_lat"], 0.0)
    longitude = _fr_num(spill, ["longitude", "spill_centroid_lon"], 0.0)
    action_plan = build_action_plan(spill, decision, language)
    confirmed_rows = _fr_confirmed_data_rows(spill, decision, language)
    risk_drivers = _fr_build_risk_factors(spill, decision, language)
    escalation_triggers = _fr_build_escalation_triggers(spill, decision, language)

    if is_ar:
        priority_map = {
            "مراقبة فقط": "مراقبة فقط",
            "استعداد محدود": "استعداد محدود",
            "استجابة عاجلة": "استجابة عاجلة",
        }
        priority = priority_map.get(decision["decision_badge"], "مراقبة فقط")
        objectives = _fr_unique([
            decision["operational_decision"],
            decision["decision_reason"],
            "ربط القرار التشغيلي بالقيم المؤكدة فقط دون افتراضات غير مدعومة.",
            "تحديث القرار بعد أي قراءة أو تحقق بصري لاحق.",
        ])
        immediate = _fr_unique(action_plan["next_24h"][:2] or action_plan["next_24h"])
        short_term = _fr_unique(action_plan["next_24h"][2:] or [
            "مراجعة الحاجة إلى تصعيد إضافي بعد التحقق الميداني أو القراءة اللاحقة."
        ])
        long_term = _fr_unique([
            "مراجعة تغير السلوك الجيو مكاني للحالة عبر قراءات لاحقة قبل تثبيت أي تدخل ممتد.",
            "توثيق أسباب القرار التشغيلي والنتائج المترتبة عليه لدعم القراءات اللاحقة.",
            "مراجعة فعالية إجراءات المراقبة أو الاحتواء بعد انتهاء نافذة الأربع والعشرين ساعة الأولى.",
        ])
        agencies = _fr_unique([
            "الجهة البيئية المختصة" if decision["decision_badge"] != "مراقبة فقط" else "فريق الرصد والتحقق",
            "فرق الاستجابة البحرية" if decision["decision_badge"] == "استجابة عاجلة" else "جهة المتابعة التشغيلية",
            "خفر السواحل أو الجهة الملاحية" if decision["near_land"] else "الجهة المحلية ذات العلاقة",
            "فريق حماية الشعاب أو الموائل الحساسة" if decision["near_coral"] else "لا يتطلب تنسيقًا بيئيًا خاصًا حاليًا",
        ])
        summary = build_executive_summary(spill, decision, language)
    else:
        priority = decision["decision_badge"]
        objectives = _fr_unique([
            decision["operational_decision"],
            decision["decision_reason"],
            "Tie the operating decision to confirmed values only, without unsupported assumptions.",
            "Refresh the decision whenever a later reading or visual verification becomes available.",
        ])
        immediate = _fr_unique(action_plan["next_24h"][:2] or action_plan["next_24h"])
        short_term = _fr_unique(action_plan["next_24h"][2:] or ["Reassess whether escalation is justified after verification or a later reading."])
        long_term = _fr_unique([
            "Review subsequent spatial readings before locking in any extended field intervention.",
            "Document the reasons behind the operating decision and any resulting action.",
            "Assess the effectiveness of monitoring or containment after the first 24-hour window.",
        ])
        agencies = _fr_unique([
            "Environmental authority" if decision["decision_badge"] != "Monitoring only" else "Monitoring and verification team",
            "Marine response teams" if decision["decision_badge"] == "Urgent response" else "Operational follow-up authority",
            "Coast guard or navigation authority" if decision["near_land"] else "Relevant local authority",
            "Sensitive habitat protection team" if decision["near_coral"] else "No dedicated environmental escalation currently required",
        ])
        summary = build_executive_summary(spill, decision, language)

    payload = {
            "spill_id": spill_id,
        "filename": filename,
        "risk_level": decision["risk"],
        "priority": priority,
        "priority_window": _fr_priority_window(decision["risk"], language),
        "source": "response_report_builder",
        "summary": summary,
        "confirmed_data": [f"{label}: {value}" for label, value in confirmed_rows],
        "confirmed_data_rows": confirmed_rows,
        "operational_decision": decision["operational_decision"],
        "decision_badge": decision["decision_badge"],
        "decision_reason": decision["decision_reason"],
        "data_quality_note": decision["data_quality_note"],
        "risk_drivers": risk_drivers,
        "objectives": objectives,
            "immediate": immediate,
            "short_term": short_term,
            "long_term": long_term,
        "monitoring": _fr_unique(action_plan["monitoring"]),
        "equipment": _fr_unique(action_plan["equipment"]),
        "agencies": agencies,
        "escalation_triggers": escalation_triggers,
        "area_m2": area,
        "coverage_pct": coverage,
        "distance_to_land_km": decision["land"],
        "distance_to_coral_km": decision["coral"],
        "distance_to_land_display": decision["land_display"],
        "distance_to_coral_display": decision["coral_display"],
        "land_proximity_class": decision["land_class"],
        "coral_risk_class": decision["coral_class"],
        "latitude": latitude,
        "longitude": longitude,
        "confirmed_spill": decision["confirmed"],
    }
    return _fr_with_web_plan(payload, spill, language)


def _fr_solution_report_content(spill, language="ar"):
    sol = _fr_solution_payload(spill, language)
    is_ar = (language or "ar").lower() == "ar"

    if is_ar:
        sections = [
            "تقرير الحلول والاستجابة للتسرّب النفطي",
            f"ملخص تنفيذي\n{sol['summary']}",
            f"البيانات المؤكدة من النموذج/قاعدة البيانات\n{_fr_bullets(sol['confirmed_data'])}",
            f"القرار التشغيلي\n- {sol['decision_badge']}\n- {sol['operational_decision']}\n- {sol['decision_reason']}",
            f"عوامل الخطورة الرئيسية\n{_fr_bullets(sol['risk_drivers'])}",
            f"الإجراء الموصى به خلال 24 ساعة\n{_fr_bullets(sol['immediate'] + sol['short_term'])}",
            f"مؤشرات التصعيد\n{_fr_bullets(sol.get('escalation_triggers') or [])}",
            f"خطة المراقبة\n{_fr_bullets(sol['monitoring'])}",
            f"المعدات المطلوبة عند الحاجة\n{_fr_bullets(sol['equipment'])}",
        ]
        if sol.get("data_quality_note"):
            sections.insert(2, f"ملاحظة جودة البيانات\n- {sol['data_quality_note']}")
        if sol.get("web_plan"):
            sections.append(f"خطة مدعومة بالبحث الشبكي\n{sol['web_plan']}")
        if sol.get("trusted_sources"):
            source_lines = [
                f"- {src.get('title') or src.get('domain')}\n  {src.get('domain')} | {src.get('url')}"
                for src in (sol.get("trusted_sources") or [])
                if src.get("url")
            ]
            if source_lines:
                sections.append("المصادر المعتمدة\n" + "\n".join(source_lines))
            else:
                sections.append("المصادر المعتمدة\n- لم يتم إرفاق مصادر خارجية موثوقة لهذا التقرير، وتم الاعتماد على بيانات النموذج وقاعدة البيانات وخطة التشغيل المحلية.")
        else:
            sections.append("المصادر المعتمدة\n- لم يتم إرفاق مصادر خارجية موثوقة لهذا التقرير، وتم الاعتماد على بيانات النموذج وقاعدة البيانات وخطة التشغيل المحلية.")
        return "\n\n".join(sections).strip()

    sections = [
        "Oil Spill Response and Solutions Report",
        f"Executive Summary\n{sol['summary']}",
        f"Confirmed Data\n{_fr_bullets(sol['confirmed_data'])}",
        f"Operational Decision\n- {sol['decision_badge']}\n- {sol['operational_decision']}\n- {sol['decision_reason']}",
        f"Primary Risk Drivers\n{_fr_bullets(sol['risk_drivers'])}",
        f"Recommended Action in 24 Hours\n{_fr_bullets(sol['immediate'] + sol['short_term'])}",
        f"Escalation Triggers\n{_fr_bullets(sol.get('escalation_triggers') or [])}",
        f"Monitoring Plan\n{_fr_bullets(sol['monitoring'])}",
        f"Equipment When Justified\n{_fr_bullets(sol['equipment'])}",
    ]
    if sol.get("data_quality_note"):
        sections.insert(2, f"Data Quality Note\n- {sol['data_quality_note']}")
    if sol.get("web_plan"):
        sections.append(f"Web-backed Response Plan\n{sol['web_plan']}")
    if sol.get("trusted_sources"):
        source_lines = [
            f"- {src.get('title') or src.get('domain')}\n  {src.get('domain')} | {src.get('url')}"
            for src in (sol.get("trusted_sources") or [])
            if src.get("url")
        ]
        if source_lines:
            sections.append("Trusted Sources\n" + "\n".join(source_lines))
        else:
            sections.append("Trusted Sources\n- No trusted external sources were attached to this report; the report is based on model output, database records, and the local operational plan.")
    else:
        sections.append("Trusted Sources\n- No trusted external sources were attached to this report; the report is based on model output, database records, and the local operational plan.")
    return "\n\n".join(sections).strip()


def _fr_html_list(items: List[str]) -> str:
    return "".join(f"<li>{html.escape(str(item))}</li>" for item in _fr_unique(items))


def _fr_html_rows(rows: List[Tuple[str, str]]) -> str:
    return "".join(
        f"<tr><th>{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>"
        for label, value in rows
    )


def _fr_payload_is_complete(payload: Any) -> bool:
    return isinstance(payload, dict) and bool(
        payload.get("operational_decision") and payload.get("decision_badge") and payload.get("confirmed_data_rows")
    )


def _fr_prepare_report_for_html(report: Dict[str, Any]) -> Dict[str, Any]:
    prepared = dict(report or {})
    payload = prepared.get("payload")

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
            prepared["payload"] = payload
        except Exception:
            payload = None

    if _fr_payload_is_complete(payload):
        return prepared

    language = str(prepared.get("language") or "ar").lower()
    lookup_keys = [
        prepared.get("spill_id"),
        prepared.get("filename"),
        prepared.get("id"),
        prepared.get("report_id"),
    ]
    spill = None
    for key in lookup_keys:
        if not key:
            continue
        spill = _fr_find_spill(str(key))
        if spill:
            break

    if not spill:
        return prepared

    fresh_payload = _fr_solution_payload(spill, language)
    prepared["payload"] = fresh_payload
    prepared["spill_id"] = prepared.get("spill_id") or fresh_payload.get("spill_id") or spill.get("spill_id")
    prepared["filename"] = prepared.get("filename") or fresh_payload.get("filename") or spill.get("filename")
    prepared["risk_level"] = fresh_payload.get("risk_level") or prepared.get("risk_level")
    prepared["final_risk_level"] = prepared.get("final_risk_level") or prepared.get("risk_level")
    prepared["summary"] = fresh_payload.get("summary") or prepared.get("summary") or str(prepared.get("content") or "")[:240]
    return prepared


def _fr_html(report):
    report = _fr_prepare_report_for_html(report)
    language = str(report.get("language") or "ar").lower()
    is_ar = language == "ar"
    payload = report.get("payload") or _fr_solution_payload(report, language)

    title = "تقرير الحلول والاستجابة للتسرّب النفطي" if is_ar else "Oil Spill Response Report"
    subtitle = (
        "ملف تشغيلي مختصر مبني على قراءة الحالة وقيم قاعدة البيانات، مع ربط التوصيات بأسبابها المباشرة."
        if is_ar
        else "A concise operational brief built from the case reading and database values, with every recommendation tied to explicit evidence."
    )
    confirmed_rows = payload.get("confirmed_data_rows") or []
    if not confirmed_rows:
        confirmed_rows = _fr_confirmed_data_rows(report, classify_operational_decision(report, language), language)
    sources_html = render_sources(payload.get("trusted_sources") or [], language)
    data_quality_note = payload.get("data_quality_note")
    decision_badge = str(payload.get("decision_badge") or payload.get("priority") or "")

    return f"""
<!doctype html>
<html lang="{ 'ar' if is_ar else 'en' }" dir="{ 'rtl' if is_ar else 'ltr' }">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #edf3f8;
      --ink: #12304b;
      --muted: #63788c;
      --card: #ffffff;
      --line: #d8e3ee;
      --teal: #0e7c86;
      --navy: #12324b;
      --soft: #f6fafc;
      --warn: #9a6700;
      --warn-bg: #fff6db;
      --shadow: 0 14px 38px rgba(18,48,75,.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #f9fbfd 0%, var(--bg) 100%);
      color: var(--ink);
      font-family: Arial, sans-serif;
      line-height: 1.75;
      padding: 24px 16px 36px;
    }}
    .sheet {{
      max-width: 1120px;
      margin: 0 auto;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      overflow: hidden;
      box-shadow: var(--shadow);
    }}
    .hero {{
      padding: 28px 30px 24px;
      background: linear-gradient(135deg, #10324d 0%, #0e6471 100%);
      color: #fff;
    }}
    .eyebrow {{
      font-size: 12px;
      letter-spacing: .12em;
      text-transform: uppercase;
      opacity: .78;
      margin-bottom: 8px;
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      line-height: 1.25;
    }}
    .hero p {{
      margin: 0;
      max-width: 860px;
      color: rgba(255,255,255,.88);
    }}
    .hero-top {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 132px;
      padding: 10px 16px;
      border-radius: 999px;
      background: rgba(255,255,255,.16);
      border: 1px solid rgba(255,255,255,.18);
      font-weight: 700;
      white-space: nowrap;
    }}
    .report-meta {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      padding: 18px 30px 0;
    }}
    .meta-card, .summary-card, .panel {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 16px;
    }}
    .meta-card {{
      padding: 14px 16px;
      background: #f9fcff;
    }}
    .label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: var(--muted);
      margin-bottom: 6px;
    }}
    .value {{
      font-size: 16px;
      font-weight: 700;
      color: var(--navy);
      word-break: break-word;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 10px;
      padding: 18px 30px 0;
    }}
    .summary-card {{
      padding: 14px 16px;
      background: var(--soft);
    }}
    .note {{
      margin: 18px 30px 0;
      padding: 14px 16px;
      border-radius: 14px;
      background: var(--warn-bg);
      border: 1px solid #f1d78d;
      color: #5e4504;
      font-size: 14px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1.2fr .9fr;
      gap: 14px;
      padding: 18px 30px 28px;
    }}
    .stack {{
      display: grid;
      gap: 14px;
    }}
    .panel {{
      padding: 18px 18px 16px;
    }}
    .panel h2 {{
      margin: 0 0 12px;
      font-size: 18px;
      color: var(--navy);
    }}
    .summary {{
      background: linear-gradient(180deg, #ffffff 0%, #f9fcff 100%);
    }}
    ul {{
      margin: 0;
      padding-{ 'right' if is_ar else 'left' }: 18px;
    }}
    li + li {{ margin-top: 8px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      text-align: { 'right' if is_ar else 'left' };
      vertical-align: top;
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
    }}
    th {{
      width: 36%;
      color: var(--muted);
      font-weight: 600;
      background: #fbfdff;
    }}
    .source-item + .source-item {{
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px dashed var(--line);
    }}
    .source-title {{
      font-weight: 700;
      margin-bottom: 4px;
      color: var(--navy);
    }}
    .source-domain {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 4px;
    }}
    .source-item a {{
      color: var(--teal);
      text-decoration: none;
      word-break: break-all;
    }}
    .footer {{
      padding: 0 30px 26px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media print {{
      body {{ padding: 0; background: #fff; }}
      .sheet {{ box-shadow: none; border: none; }}
    }}
    @media (max-width: 900px) {{
      .report-meta, .summary-grid, .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main class="sheet">
    <section class="hero">
      <div class="hero-top">
        <div>
          <div class="eyebrow">{'Response Plan' if not is_ar else 'خطة الاستجابة'}</div>
          <h1>{html.escape(title)}</h1>
          <p>{html.escape(subtitle)}</p>
    </div>
        <div class="status-badge">{html.escape(decision_badge)}</div>
  </div>
    </section>

    <section class="report-meta">
      <div class="meta-card">
        <div class="label">{'رقم التقرير' if is_ar else 'Report ID'}</div>
        <div class="value">{html.escape(str(report.get('report_id') or report.get('id') or ''))}</div>
      </div>
      <div class="meta-card">
        <div class="label">{'الحالة' if is_ar else 'Case'}</div>
        <div class="value">{html.escape(str(payload.get('spill_id') or report.get('spill_id') or ''))}</div>
      </div>
      <div class="meta-card">
        <div class="label">{'تاريخ الإنشاء' if is_ar else 'Created at'}</div>
        <div class="value">{html.escape(str(report.get('created_at') or ''))}</div>
      </div>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <div class="label">{'مستوى الخطورة' if is_ar else 'Risk level'}</div>
        <div class="value">{html.escape(str(payload.get('risk_level') or report.get('risk_level') or ''))}</div>
      </div>
      <div class="summary-card">
        <div class="label">{'المساحة' if is_ar else 'Area'}</div>
        <div class="value">{html.escape(format_number_ar(payload.get('area_m2'), 'م²' if is_ar else 'm²', 2, language))}</div>
      </div>
      <div class="summary-card">
        <div class="label">{'نسبة التغطية في الصورة' if is_ar else 'Image coverage'}</div>
        <div class="value">{html.escape(format_number_ar(payload.get('coverage_pct'), '%', 2, language))}</div>
      </div>
      <div class="summary-card">
        <div class="label">{'المسافة إلى اليابسة' if is_ar else 'Distance to land'}</div>
        <div class="value">{html.escape(str(payload.get('distance_to_land_display') or safe_value(None, language)))}</div>
      </div>
      <div class="summary-card">
        <div class="label">{'المسافة إلى الشعاب' if is_ar else 'Distance to coral'}</div>
        <div class="value">{html.escape(str(payload.get('distance_to_coral_display') or safe_value(None, language)))}</div>
      </div>
      <div class="summary-card">
        <div class="label">{'القرار الموصى به' if is_ar else 'Recommended decision'}</div>
        <div class="value">{html.escape(str(payload.get('operational_decision') or ''))}</div>
      </div>
    </section>

    {f'<section class="note">{html.escape(str(data_quality_note))}</section>' if data_quality_note else ''}

    <section class="grid">
      <div class="stack">
        <article class="panel summary">
          <h2>{'الملخص التنفيذي' if is_ar else 'Executive Summary'}</h2>
          <p>{html.escape(str(payload.get('summary') or ''))}</p>
        </article>

        <article class="panel">
          <h2>{'البيانات المؤكدة من النموذج/قاعدة البيانات' if is_ar else 'Confirmed Data from Model/Database'}</h2>
          <table>
            <tbody>{_fr_html_rows(confirmed_rows)}</tbody>
          </table>
        </article>

        <article class="panel">
          <h2>{'القرار التشغيلي' if is_ar else 'Operational Decision'}</h2>
          <p><strong>{html.escape(str(payload.get('decision_badge') or ''))}</strong></p>
          <p>{html.escape(str(payload.get('operational_decision') or ''))}</p>
          <p>{html.escape(str(payload.get('decision_reason') or ''))}</p>
        </article>

        <article class="panel">
          <h2>{'عوامل الخطورة الرئيسية' if is_ar else 'Main Risk Factors'}</h2>
          <ul>{_fr_html_list(payload.get('risk_drivers') or [])}</ul>
        </article>

        <article class="panel">
          <h2>{'الإجراء الموصى به خلال 24 ساعة' if is_ar else 'Recommended Action in the Next 24 Hours'}</h2>
          <ul>{_fr_html_list((payload.get('immediate') or []) + (payload.get('short_term') or []))}</ul>
        </article>
      </div>

      <div class="stack">
        <article class="panel">
          <h2>{'مؤشرات التصعيد' if is_ar else 'Escalation Triggers'}</h2>
          <ul>{_fr_html_list(payload.get('escalation_triggers') or [])}</ul>
        </article>
        <article class="panel">
          <h2>{'خطة المراقبة' if is_ar else 'Monitoring Plan'}</h2>
          <ul>{_fr_html_list(payload.get('monitoring') or [])}</ul>
        </article>
        <article class="panel">
          <h2>{'المعدات المطلوبة عند التبرير' if is_ar else 'Equipment Needed When Justified'}</h2>
          <ul>{_fr_html_list(payload.get('equipment') or [])}</ul>
        </article>
        <article class="panel">
          <h2>{'الجهات المقترحة' if is_ar else 'Suggested Agencies'}</h2>
          <ul>{_fr_html_list(payload.get('agencies') or [])}</ul>
        </article>
        <article class="panel">
          <h2>{'المصادر المعتمدة' if is_ar else 'Trusted Sources'}</h2>
          {sources_html}
        </article>
      </div>
    </section>

    <footer class="footer">
      {html.escape(str(report.get('filename') or payload.get('filename') or ''))}
    </footer>
  </main>
</body>
</html>
"""


def _llm_reports_dir() -> Path:
    return Path(
        os.getenv(
            "LLM_REPORTS_OUTPUT_DIR",
            str(BASE_DIR / "generated_llm_reports"),
        )
    ).expanduser()


def _use_llm_reports() -> bool:
    return os.getenv("USE_LLM_REPORTS", "1").strip().lower() not in ("0", "false", "no")


def _llm_python_executable() -> str:
    return (os.getenv("LLM_PYTHON") or "").strip() or sys.executable


def _generate_llm_report_via_subprocess(spill: Dict[str, Any], language: str) -> Dict[str, Any]:
    import json
    import subprocess

    cp_dir = Path(os.getenv("CP_PATH", str(BASE_DIR.parent))).expanduser()
    script = Path(
        os.getenv(
            "LLM_REPORT_SCRIPT",
            str(cp_dir / "oil_llm_reporter" / "run_local_oil_llm.py"),
        )
    ).expanduser()
    if not script.exists():
        raise FileNotFoundError(f"LLM script not found: {script}")

    spill_id = _fr_text(spill, ["filename", "spill_id", "id", "source_image"], "")
    if not spill_id:
        raise ValueError("Could not resolve spill id for LLM report")

    out_dir = _llm_reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CP_PATH"] = str(cp_dir)
    upload_dir = os.getenv("UPLOAD_DIR", str(cp_dir / "backend_uploads"))
    env["UPLOAD_DIR"] = upload_dir
    env.setdefault("DB_HOST", os.getenv("DB_HOST", "localhost"))
    env.setdefault("DB_NAME", os.getenv("DB_NAME", "oil_spills"))
    env.setdefault("DB_USER", os.getenv("DB_USER", "postgres"))
    env.setdefault("DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
    if os.getenv("SPILLS_TABLE"):
        env["SPILLS_TABLE"] = os.getenv("SPILLS_TABLE", "")
    if os.getenv("DB_TABLE"):
        env["DB_TABLE"] = os.getenv("DB_TABLE", "")
    if os.getenv("LLM_TRANSLATION_METHOD"):
        env["LLM_TRANSLATION_METHOD"] = os.getenv("LLM_TRANSLATION_METHOD", "")

    cmd = [
        _llm_python_executable(),
        str(script),
        "--spill-id",
        str(spill_id),
        "--output-dir",
        str(out_dir),
        "--language",
        language,
        "--api-assets",
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("LLM_REPORT_TIMEOUT_SEC", "900")),
        env=env,
        cwd=str(script.parent),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "unknown error").strip()
        raise RuntimeError(
            "فشل تشغيل run_local_oil_llm.py. عيّني LLM_PYTHON لنفس بايثون التدريب (مع torch/peft). "
            f"Details: {err[:2000]}"
        )

    line = ""
    for candidate in reversed((proc.stdout or "").splitlines()):
        if candidate.strip().startswith("{"):
            line = candidate.strip()
            break
    if not line:
        raise RuntimeError(f"LLM subprocess returned no JSON: {(proc.stdout or '')[:500]}")

    return json.loads(line)


def _generate_llm_report_for_spill(spill: Dict[str, Any], language: str) -> Dict[str, Any]:
    """التقارير تُولَّد فقط من oil_llm_reporter/run_local_oil_llm.py ( subprocess + LLM_PYTHON )."""
    return _generate_llm_report_via_subprocess(spill, language)


def _solutions_html_section(payload: Dict[str, Any], language: str) -> str:
    """قسم الحلول والاستجابة — يُدمج في تقرير LLM الموحّد."""
    import html as html_mod

    is_ar = (language or "ar").lower() == "ar"

    def esc(v: Any) -> str:
        return html_mod.escape("" if v is None else str(v))

    def list_block(title: str, items: List[str]) -> str:
        rows = [str(x).strip() for x in (items or []) if str(x).strip()]
        if not rows:
            return ""
        lis = "".join(f"<li>{esc(x)}</li>" for x in rows)
        return f"<div class=\"sol-block\"><h3>{esc(title)}</h3><ul>{lis}</ul></div>"

    blocks = [
        list_block("الإجراءات الفورية" if is_ar else "Immediate actions", payload.get("immediate") or []),
        list_block("إجراءات قصيرة المدى" if is_ar else "Short-term actions", payload.get("short_term") or []),
        list_block("إجراءات طويلة المدى" if is_ar else "Long-term actions", payload.get("long_term") or []),
        list_block("المراقبة والمتابعة" if is_ar else "Monitoring", payload.get("monitoring") or []),
        list_block("المعدات المطلوبة" if is_ar else "Equipment", payload.get("equipment") or []),
        list_block("الجهات المقترحة" if is_ar else "Agencies", payload.get("agencies") or []),
        list_block("عوامل الخطورة" if is_ar else "Risk drivers", payload.get("risk_drivers") or []),
        list_block("مؤشرات التصعيد" if is_ar else "Escalation triggers", payload.get("escalation_triggers") or []),
    ]
    blocks_html = "".join(blocks)

    title = "خطة الاستجابة والحلول" if is_ar else "Response plan & solutions"
    decision = esc(payload.get("decision_badge") or payload.get("priority") or "")
    op = esc(payload.get("operational_decision") or "")
    reason = esc(payload.get("decision_reason") or "")

    return f"""
    <section class="card solutions-unified" style="margin-top:28px">
        <h2 style="color:#2f7fd6;margin-top:0">{esc(title)}</h2>
        <p><strong>{'الأولوية' if is_ar else 'Priority'}:</strong> {decision}
        {' · ' + esc(payload.get('priority_window') or '') if payload.get('priority_window') else ''}</p>
        <p>{esc(payload.get('summary') or '')}</p>
        {f'<p><strong>{"القرار التشغيلي" if is_ar else "Operational decision"}:</strong> {op}</p>' if op else ''}
        {f'<p>{reason}</p>' if reason else ''}
        <div class="solutions-grid">{blocks_html}</div>
    </section>
    <style>
    .solutions-unified .sol-block {{ margin:14px 0; padding:12px; background:#f8fafc; border-radius:10px; border:1px solid #e2e8f0; }}
    .solutions-unified h3 {{ margin:0 0 8px; font-size:15px; color:#1d4ed8; }}
    .solutions-unified ul {{ margin:0; padding-inline-start:22px; line-height:1.75; }}
    </style>
    """


def _append_solutions_to_llm_html(html_path: Path, payload: Dict[str, Any], language: str) -> None:
    path = Path(html_path)
    if not path.exists():
        return
    section = _solutions_html_section(payload, language)
    text = path.read_text(encoding="utf-8")
    if "solutions-unified" in text:
        return
    if "</body>" in text:
        text = text.replace("</body>", section + "\n</body>", 1)
    else:
        text += section
    path.write_text(text, encoding="utf-8")


def _store_llm_report_record(result: Dict[str, Any], payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    import json

    out = _llm_reports_dir()
    out.mkdir(parents=True, exist_ok=True)

    lang = str(result.get("language") or "ar").lower()
    record = {
        "id": result.get("report_id"),
        "report_id": result.get("report_id"),
        "spill_id": result.get("spill_id"),
        "filename": result.get("filename"),
        "risk_level": result.get("risk_level"),
        "final_risk_level": result.get("final_risk_level") or result.get("risk_level"),
        "language": lang,
        "created_at": result.get("created_at"),
        "summary": result.get("summary"),
        "content": result.get("content"),
        "generator": result.get("generator", "run_local_oil_llm.py"),
        "model": result.get("model", "Qwen2.5-0.5B-Instruct+LoRA"),
        "html_path": result.get("html_path"),
        "html_filename": result.get("html_filename"),
        "source": "unified_llm",
        "report_type": "unified",
    }
    if payload:
        record["payload"] = payload
    assets = result.get("image_assets")
    if isinstance(assets, dict):
        record["image_assets"] = assets
    if result.get("image_asset"):
        record["image_asset"] = result.get("image_asset")

    jsonl = out / "reports.jsonl"
    with jsonl.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def _llm_file_reports() -> List[Dict[str, Any]]:
    import json

    jsonl = _llm_reports_dir() / "reports.jsonl"
    if not jsonl.exists():
        return []

    rows: List[Dict[str, Any]] = []
    for line in jsonl.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows[::-1]


def _fr_store_report(spill, content, language):
    import json
    from pathlib import Path
    from datetime import datetime

    out = Path(__file__).parent / "generated_solution_reports"
    out.mkdir(exist_ok=True)

    payload = _fr_solution_payload(spill, language)
    report_id = f"SOL-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
    report = {
        "id": report_id,
        "report_id": report_id,
        "spill_id": _fr_text(spill, ["spill_id", "id", "filename"], ""),
        "filename": _fr_text(spill, ["filename"], ""),
        "risk_level": _fr_text(spill, ["final_risk_level", "risk_level"], "Unknown"),
        "language": language,
        "created_at": datetime.utcnow().isoformat(),
        "summary": payload.get("summary") or content[:240],
        "content": content,
        "payload": payload,
    }

    with (out / "reports.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")

    return report


def _fr_file_reports():
    import json
    from pathlib import Path

    path = Path(__file__).parent / "generated_solution_reports" / "reports.jsonl"
    if not path.exists():
        return []

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            pass

    return rows[::-1]



@app.post("/api/generate-report")
def generate_report(req: FrontendReportRequest) -> Dict[str, Any]:
    spill = _fr_find_spill(req.spill_id)
    if not spill:
        raise HTTPException(status_code=404, detail="Spill not found")

    language = (req.language or "ar").lower()

    if not _use_llm_reports():
        raise HTTPException(
            status_code=503,
            detail="توليد التقارير الموحّدة معطّل. فعّلي USE_LLM_REPORTS=1 في .env",
        )

    try:
        llm_result = _generate_llm_report_for_spill(spill, language)
        payload = _fr_solution_payload(spill, language)
        html_path = llm_result.get("html_path")
        if html_path:
            _append_solutions_to_llm_html(Path(str(html_path)), payload, language)

        combined_summary = str(llm_result.get("summary") or "")
        sol_summary = str(payload.get("summary") or "")
        if sol_summary and sol_summary not in combined_summary:
            combined_summary = f"{combined_summary}\n\n{sol_summary}".strip()

        llm_result["summary"] = combined_summary[:500]
        llm_result["content"] = combined_summary
        llm_result["payload"] = payload

        report = _store_llm_report_record(llm_result, payload)
        report["source"] = "unified_llm"
        report["model"] = llm_result.get("model")
        report["payload"] = payload
        return report
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "تعذّر توليد التقرير الموحّد (تحليل Qwen + خطة الحلول). "
                "تأكدي من LLM_PYTHON في .env (نفس بايثون run_local_oil_llm.py). "
                f"التفاصيل: {exc}"
            ),
        ) from exc


@app.get("/api/reports")
def list_reports() -> Dict[str, Any]:
    reports = []

    try:
        ensure_reports_table()
        with get_engine().connect() as conn:
            rows = conn.execute(text(f"""
                SELECT report_id AS id, report_id, spill_id, filename, risk_level, language, created_at, content
                FROM {REPORTS_TABLE}
                ORDER BY created_at DESC
            """)).mappings().all()

        for r in rows:
            rid = str(r.get("report_id") or r.get("id") or "").strip()
            # تقارير R- = نسخ DB قديمة؛ المصدر الرسمي الآن LLM- في JSONL فقط
            if rid.upper().startswith("R-"):
                continue
            d = apply_report_display_risk(clean_value_dict(_merge_spill_metrics_into_report_row(dict(r))))
            d["summary"] = str(d.get("content") or "")[:240]
            reports.append(d)
    except Exception:
        pass

    reports.extend(_llm_file_reports())

    seen = set()
    unique = []
    for r in reports:
        rid = str(r.get("report_id") or r.get("id"))
        if rid not in seen:
            seen.add(rid)
            unique.append(apply_report_display_risk(r))

    return {"count": len(unique), "reports": unique}


def clean_value_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: clean_value(v) for k, v in row.items()}


def _report_id_matches(report: Dict[str, Any], rid: str) -> bool:
    rid = str(rid or "").strip()
    if not rid:
        return False
    for key in ("report_id", "id"):
        if str(report.get(key) or "").strip() == rid:
            return True
    return False


def _delete_report_html_files(records: List[Dict[str, Any]], llm_root: Path) -> None:
    for report in records:
        html_path = report.get("html_path")
        if html_path:
            p = Path(str(html_path))
            if p.is_file():
                try:
                    p.unlink()
                except OSError:
                    pass
        fname = report.get("html_filename")
        if fname:
            p = (llm_root / "html" / str(fname)).resolve()
            if p.is_file() and str(p).startswith(str((llm_root / "html").resolve())):
                try:
                    p.unlink()
                except OSError:
                    pass
        rid = str(report.get("report_id") or report.get("id") or "").strip()
        if rid:
            direct = llm_root / "html" / f"{rid}.html"
            if direct.is_file():
                try:
                    direct.unlink()
                except OSError:
                    pass


def _remove_report_from_jsonl(jsonl_path: Path, rid: str) -> Tuple[bool, List[Dict[str, Any]]]:
    import json

    if not jsonl_path.is_file():
        return False, []

    removed: List[Dict[str, Any]] = []
    kept: List[Dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            report = json.loads(line)
        except Exception:
            continue
        if _report_id_matches(report, rid):
            removed.append(report)
        else:
            kept.append(report)

    if not removed:
        return False, []

    with jsonl_path.open("w", encoding="utf-8") as f:
        for report in kept:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")
    return True, removed


def _delete_report_record(rid: str) -> bool:
    import json

    rid = str(rid or "").strip()
    if not rid:
        return False

    deleted = False
    llm_root = _llm_reports_dir()

    try:
        ensure_reports_table()
        with get_engine().begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM {REPORTS_TABLE} WHERE report_id = :rid"),
                {"rid": rid},
            )
            if result.rowcount and int(result.rowcount) > 0:
                deleted = True
    except Exception:
        pass

    jsonl_paths = [
        llm_root / "reports.jsonl",
        Path(__file__).parent / "generated_solution_reports" / "reports.jsonl",
        Path(os.getenv("SOLUTION_OUTPUT_DIR", str(BASE_DIR.parent / "solution_reports_output")))
        / "reports.jsonl",
    ]

    for jsonl_path in jsonl_paths:
        found, removed = _remove_report_from_jsonl(jsonl_path, rid)
        if found:
            deleted = True
            if jsonl_path.parent.resolve() == llm_root.resolve() or (
                llm_root / "reports.jsonl"
            ).resolve() == jsonl_path.resolve():
                _delete_report_html_files(removed, llm_root)
            else:
                _delete_report_html_files(removed, jsonl_path.parent)

    return deleted


@app.delete("/api/reports/{report_id}")
def delete_report(report_id: str) -> Dict[str, Any]:
    from urllib.parse import unquote

    rid = unquote(str(report_id)).strip()
    if not rid:
        raise HTTPException(status_code=400, detail="Report id is required.")
    if not _delete_report_record(rid):
        raise HTTPException(status_code=404, detail="Report not found.")
    return {"ok": True, "deleted": True, "report_id": rid}


# NOTE: the active /api/reports/{report_id} route lives further below; it reads
# from the JSONL file + DB + saved HTML files. The old DB-only handler was
# removed because reports generated through /api/generate-report are stored as
# JSONL, which the DB-only handler could not see (always 404).


@app.get("/api/rag/health")
def rag_health() -> Dict[str, Any]:
    refresh_rag_paths()
    try:
        try:
            from external_rag.rag_query import collection  # type: ignore
        except Exception:
            from rag_query import collection  # type: ignore
        return {"ok": True, "message": "RAG is connected to backend", "collection_count": collection.count()}
    except Exception as exc:
        return {"ok": False, "message": "RAG is not connected", "error": str(exc)}


@app.post("/api/rag/ask")
def ask_rag(request: RagChatRequest) -> Dict[str, Any]:
    message = (request.message or request.question or request.query or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is empty.")
    result = run_rag_query(message, top_k=request.top_k)
    return {
        "ok": bool(result.get("ok")),
        "reply": result.get("reply", ""),
        "sources": result.get("sources", []),
        "error": result.get("error"),
    }




class RunSolutionScriptRequest(BaseModel):
    spill_id: Optional[str] = None
    limit: Optional[int] = 150
    language: Optional[str] = "ar"


@app.post("/api/run-solution-script")
def run_solution_script(req: RunSolutionScriptRequest) -> Dict[str, Any]:
    import os
    import sys
    import subprocess
    from pathlib import Path
    from urllib.parse import quote

    script_path = Path(os.getenv(
        "SOLUTION_SCRIPT_PATH",
        "/Users/rana/Documents/tuwaiq/CP/oil_solution_reports_same_template_no_images.py"
    ))

    output_dir = Path(os.getenv(
        "SOLUTION_OUTPUT_DIR",
        "/Users/rana/Documents/tuwaiq/CP/solution_reports_output"
    ))

    if not script_path.exists():
        return {
            "ok": False,
            "error": f"Solution script not found: {script_path}"
        }

    output_dir.mkdir(parents=True, exist_ok=True)

    limit = int(req.limit or 150)

    cmd = [
        sys.executable,
        str(script_path),
        "--table",
        os.getenv("SPILLS_TABLE", os.getenv("DB_TABLE", "spill_analysis_results")),
        "--limit",
        str(limit),
        "--output-dir",
        str(output_dir),
    ]

    env = os.environ.copy()
    env["DB_NAME"] = os.getenv("DB_NAME", "oil_spills")
    env["DB_USER"] = os.getenv("DB_USER", "postgres")
    env["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "")
    env["DB_HOST"] = os.getenv("DB_HOST", "localhost")
    env["DB_PORT"] = os.getenv("DB_PORT", "5432")
    env["DB_TABLE"] = os.getenv("SPILLS_TABLE", os.getenv("DB_TABLE", "spill_analysis_results"))

    try:
        completed = subprocess.run(
            cmd,
            cwd=str(script_path.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }

    html_files = sorted(
        list(output_dir.rglob("*.html")),
        key=lambda x: x.stat().st_mtime,
        reverse=True,
    )

    selected = None
    index_file = output_dir / "index.html"

    if req.spill_id:
        target = str(req.spill_id)
        stem = Path(target).stem

        for f in html_files:
            if f.name.lower() == "index.html":
                continue
            name = f.name
            if target in name or stem in name:
                selected = f
                break

        if selected is None:
            for f in html_files[:300]:
                if f.name.lower() == "index.html":
                    continue
                try:
                    txt = f.read_text(encoding="utf-8", errors="ignore")[:30000]
                    if target in txt or stem in txt:
                        selected = f
                        break
                except Exception:
                    pass

    if selected is None and index_file.exists():
        selected = index_file

    if selected is None and html_files:
        selected = html_files[0]

    html_url = None
    report_id = None

    if selected:
        rel = selected.relative_to(output_dir).as_posix()
        html_url = "/api/solution-script-report/" + quote(rel, safe="/")
        report_id = selected.stem

    return {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "spill_id": req.spill_id,
        "report_id": report_id,
        "html_url": html_url,
        "index_url": "/api/solution-script-report/index.html" if index_file.exists() else html_url,
        "output_dir": str(output_dir),
        "stdout": completed.stdout[-3000:],
        "stderr": completed.stderr[-3000:],
    }


@app.get("/api/solution-script-report/{report_path:path}")
def get_solution_script_report(report_path: str):
    from pathlib import Path
    from fastapi.responses import FileResponse

    output_dir = Path(os.getenv(
        "SOLUTION_OUTPUT_DIR",
        "/Users/rana/Documents/tuwaiq/CP/solution_reports_output"
    )).resolve()

    file_path = (output_dir / report_path).resolve()

    if not str(file_path).startswith(str(output_dir)):
        raise HTTPException(status_code=400, detail="Invalid report path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    return FileResponse(str(file_path), media_type="text/html")



@app.get("/api/llm-report-assets/{asset_name}")
def llm_report_asset(asset_name: str):
    from fastapi.responses import FileResponse

    images_dir = (_llm_reports_dir() / "images").resolve()
    safe = Path(str(asset_name)).name
    file_path = (images_dir / safe).resolve()
    if not str(file_path).startswith(str(images_dir)):
        raise HTTPException(status_code=400, detail="Invalid asset path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(str(file_path))


@app.get("/api/reports/{report_id}")
def get_report_html(report_id: str):
    import os
    import json
    import html
    from pathlib import Path
    from urllib.parse import unquote
    from fastapi.responses import HTMLResponse, FileResponse

    rid = unquote(str(report_id)).strip()

    def build_html(report: dict) -> str:
        return _fr_html(report)

    # 0) تقارير Qwen المحلية (HTML جاهز)
    llm_root = _llm_reports_dir()
    llm_jsonl = llm_root / "reports.jsonl"
    if llm_jsonl.exists():
        for line in llm_jsonl.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                report = json.loads(line)
            except Exception:
                continue
            ids = [
                str(report.get("id") or ""),
                str(report.get("report_id") or ""),
            ]
            if rid in ids:
                html_path = report.get("html_path")
                if html_path:
                    p = Path(str(html_path))
                    if p.exists():
                        return FileResponse(str(p), media_type="text/html")
                fname = report.get("html_filename")
                if fname:
                    p = llm_root / "html" / str(fname)
                    if p.exists():
                        return FileResponse(str(p), media_type="text/html")

    direct_html = llm_root / "html" / f"{rid}.html"
    if direct_html.exists():
        return FileResponse(str(direct_html), media_type="text/html")

    # 1) تقارير الحلول المحفوظة كـ JSONL
    jsonl_paths = [
        Path(__file__).parent / "generated_solution_reports" / "reports.jsonl",
        Path(os.getenv("SOLUTION_OUTPUT_DIR", "/Users/rana/Documents/tuwaiq/CP/solution_reports_output")) / "reports.jsonl",
    ]

    for jsonl in jsonl_paths:
        if jsonl.exists():
            for line in jsonl.read_text(encoding="utf-8", errors="ignore").splitlines():
                try:
                    report = json.loads(line)
                except Exception:
                    continue

                ids = [
                    str(report.get("id") or ""),
                    str(report.get("report_id") or ""),
                    str(report.get("spill_id") or ""),
                    str(report.get("filename") or ""),
                ]

                if rid in ids:
                    return HTMLResponse(build_html(report))

    # 2) تقارير قاعدة البيانات القديمة
    try:
        ensure_reports_table()
        with get_engine().connect() as conn:
            row = conn.execute(text(f"""
                SELECT *
                FROM {REPORTS_TABLE}
                WHERE report_id = :rid
                   OR spill_id = :rid
                   OR filename = :rid
                LIMIT 1
            """), {"rid": rid}).mappings().first()

        if row:
            report = clean_row(dict(row))
            return HTMLResponse(build_html(report))
    except Exception:
        pass

    # 3) ملفات HTML الناتجة من سكربت الحلول
    output_dir = Path(os.getenv("SOLUTION_OUTPUT_DIR", "/Users/rana/Documents/tuwaiq/CP/solution_reports_output"))
    if output_dir.exists():
        html_files = list(output_dir.rglob("*.html"))

        for f in html_files:
            if f.stem == rid or f.name == rid:
                return FileResponse(str(f), media_type="text/html")

        for f in html_files[:500]:
            try:
                txt = f.read_text(encoding="utf-8", errors="ignore")
                if rid in txt:
                    return FileResponse(str(f), media_type="text/html")
            except Exception:
                pass

    raise HTTPException(status_code=404, detail=f"Report not found: {rid}")

