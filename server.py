#!/usr/bin/env python3
"""
FastAPI Studio Server (server.py — v3.2)
MR Darkroom — Fine-Art Archival & Book Curation Studio
"""

import asyncio
import base64
import glob
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import open_clip
import torch
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config_paths import (
    APP_NAME,
    APP_VERSION,
    DATA_VAULT_DIR,
    DEFAULT_CROP_BOXES_PATH,
    DEFAULT_CROP_VECTORS_PATH,
    ensure_data_vault_migrated,
    get_version_info,
)
from db_schema import (
    DEFAULT_DB_PATH,
    DEFAULT_PREVIEWS_1600_DIR,
    DEFAULT_THUMBS_360_DIR,
    DEFAULT_VECTORS_PATH,
    PROJECT_ROOT,
    backup_catalog_to_das,
    get_db_connection,
    init_and_migrate_db,
)
from domain_gazetteer import (
    COUNTABLE_DISCRETE_SUBJECT_TAGS_LOWER,
    COUNTABLE_SEARCH_CONCEPTS,
    GLOBAL_LANDMARK_GAZETTEER,
    SINGULAR_PLURAL_PAIRS,
    US_STATE_NAMES,
    deduplicate_singular_plural_tags,
)
from harvester import (
    discover_catalog_files,
    find_active_lrcat_and_previews,
    resolve_offline_gps_location,
)
from pipeline import load_settings, run_pipeline
from stage1_engine import (
    DEFAULT_COLOR_SIGS_PATH,
    bridge_same_day_gps_locations,
    build_or_update_crop_vectors_mps,
    detect_hardware_profile,
    load_or_init_color_signatures,
    load_or_init_crop_vectors_matrix,
    load_or_init_vectors_matrix,
    run_stage1_pipeline,
    sync_external_edits,
)
from stage2_vlm import (
    STAGE2_PAUSE_EVENT,
    _GENERIC_VISUAL_NOUNS_KEEP,
    apply_clean_slate_wipe_to_record,
    cluster_and_propagate_entities,
    compute_clip_concept_probes_for_rows,
    discover_visual_subjects_for_records,
    parse_natural_language_teach,
    reassess_records_deep,
    reassess_records_fast,
    rename_entity_cluster,
    run_stage2_vlm,
)
from studio_jobs_undo import (
    JOB_MANAGER,
    OFFLINE_GAZETTEER,
    PIPELINE_STATUS,
    BackgroundJobManager,
    create_rolling_vault_backup,
    get_undo_status,
    list_vault_backups,
    pop_and_restore_undo,
    record_undo_snapshot,
)
from xmp_sync import sync_record_metadata_additive

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(
    title="MR Darkroom",
    version=APP_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS middleware for local Vite / frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# GLOBAL RUNTIME CACHES, BOILERPLATE FILTERS & OFFLINE GAZETTEER
# ==============================================================================
VECTORS_CACHE: Optional[np.ndarray] = None
VECTORS_MTIME: float = 0.0
VECTORS_NORM_CACHE: Optional[np.ndarray] = None

CROP_VECTORS_CACHE: Optional[np.ndarray] = None
CROP_VECTORS_MTIME: float = 0.0
CROP_VECTORS_NORM_CACHE: Optional[np.ndarray] = None

COLOR_SIGS_CACHE: Optional[np.ndarray] = None
COLOR_SIGS_MTIME: float = 0.0

SEARCH_INDEX_CACHE: Dict[str, Any] = {
    "db_mtime_sig": (0.0, 0.0),
    "by_key": {},
}


def invalidate_search_index_cache() -> None:
    SEARCH_INDEX_CACHE["db_mtime_sig"] = (0.0, 0.0)
    SEARCH_INDEX_CACHE["by_key"] = {}

CLIP_MODEL = None
CLIP_TOKENIZER = None
CLIP_DEVICE = "cpu"
CLIP_LOCK = threading.Lock()

BACKGROUND_BASELINE_PROMPTS = [
    "a general scenic landscape or aerial view",
    "empty water, sky, or natural terrain",
    "abstract texture or foliage",
]
BACKGROUND_BASELINE_VECS: Optional[np.ndarray] = None
TEXT_EMBED_CACHE: Dict[str, np.ndarray] = {}

BOILERPLATE_TAGS_LOWER = {
    "mitch rouse aerials",
    "mitch_rouse_aerials",
    "mitch rouse",
    "aerials",
    "msr",
    "keepers",
    "to print",
    "book",
    "phase",
    "hassy",
    "d",
    "west coast imaging",
    "west coast imaging*  alice",
    "alice",
    "staff",
    "panoframes",
    "vert pano",
    "location_review_needed",
    "location_burst_inherited",
    "needs_review",
    "unknown",
    "archival",
}

# Re-exported from studio_jobs_undo.py:
# OFFLINE_GAZETTEER, PIPELINE_STATUS, BackgroundJobManager, JOB_MANAGER



def get_vectors_matrix() -> np.ndarray:
    global VECTORS_CACHE, VECTORS_MTIME, VECTORS_NORM_CACHE
    v_path = DEFAULT_VECTORS_PATH
    if not v_path.exists():
        return np.zeros((0, 768), dtype=np.float16)
    mtime = v_path.stat().st_mtime
    if VECTORS_CACHE is None or mtime != VECTORS_MTIME:
        VECTORS_CACHE = load_or_init_vectors_matrix(v_path)
        VECTORS_MTIME = mtime
        mat_f32 = VECTORS_CACHE.astype(np.float32)
        norms = np.linalg.norm(mat_f32, axis=1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        VECTORS_NORM_CACHE = mat_f32 / norms
    return VECTORS_CACHE


def get_normalized_vectors_matrix() -> np.ndarray:
    get_vectors_matrix()
    if VECTORS_NORM_CACHE is None:
        return np.zeros((0, 768), dtype=np.float32)
    return VECTORS_NORM_CACHE


def get_crop_vectors_matrix() -> np.ndarray:
    global CROP_VECTORS_CACHE, CROP_VECTORS_MTIME, CROP_VECTORS_NORM_CACHE
    cv_path = DEFAULT_CROP_VECTORS_PATH
    if not cv_path.exists():
        return np.zeros((0, 4, 768), dtype=np.float16)
    mtime = cv_path.stat().st_mtime
    if CROP_VECTORS_CACHE is None or mtime != CROP_VECTORS_MTIME:
        CROP_VECTORS_CACHE, _ = load_or_init_crop_vectors_matrix(cv_path, DEFAULT_CROP_BOXES_PATH)
        CROP_VECTORS_MTIME = mtime
        mat_f32 = CROP_VECTORS_CACHE.astype(np.float32)
        norms = np.linalg.norm(mat_f32, axis=-1, keepdims=True)
        norms[norms < 1e-8] = 1.0
        CROP_VECTORS_NORM_CACHE = mat_f32 / norms
    return CROP_VECTORS_CACHE


def get_normalized_crop_vectors_matrix() -> np.ndarray:
    get_crop_vectors_matrix()
    if CROP_VECTORS_NORM_CACHE is None:
        return np.zeros((0, 4, 768), dtype=np.float32)
    return CROP_VECTORS_NORM_CACHE


def get_color_signatures_matrix() -> np.ndarray:
    global COLOR_SIGS_CACHE, COLOR_SIGS_MTIME
    c_path = DEFAULT_COLOR_SIGS_PATH
    if not c_path.exists():
        return np.zeros((0, 25), dtype=np.float32)
    mtime = c_path.stat().st_mtime
    if COLOR_SIGS_CACHE is None or mtime != COLOR_SIGS_MTIME:
        COLOR_SIGS_CACHE = load_or_init_color_signatures(c_path)
        COLOR_SIGS_MTIME = mtime
    return COLOR_SIGS_CACHE


def ensure_clip_loaded():
    global CLIP_MODEL, CLIP_TOKENIZER, CLIP_DEVICE, BACKGROUND_BASELINE_VECS
    if CLIP_MODEL is not None:
        return
    with CLIP_LOCK:
        if CLIP_MODEL is not None:
            return
        hw = detect_hardware_profile()
        device = hw["device"]
        logging.info(f"Loading OpenCLIP ViT-L-14 text encoder on {device}...")
        try:
            model, _, _ = open_clip.create_model_and_transforms(
                "ViT-L-14-quickgelu", pretrained="openai", device=device
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer("ViT-L-14-quickgelu")
            CLIP_MODEL = model
            CLIP_TOKENIZER = tokenizer
            CLIP_DEVICE = device
            logging.info(f"OpenCLIP ViT-L-14 text encoder ready on {device}.")
        except Exception as e:
            logging.error(f"Failed to load OpenCLIP model on {device}: {e}")
            CLIP_DEVICE = "cpu"
            model, _, _ = open_clip.create_model_and_transforms(
                "ViT-L-14-quickgelu", pretrained="openai", device="cpu"
            )
            model.eval()
            CLIP_MODEL = model
            CLIP_TOKENIZER = open_clip.get_tokenizer("ViT-L-14-quickgelu")

        try:
            tokens = CLIP_TOKENIZER(BACKGROUND_BASELINE_PROMPTS).to(CLIP_DEVICE)
            with torch.no_grad():
                bg_feat = CLIP_MODEL.encode_text(tokens)
                bg_feat = bg_feat / bg_feat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                BACKGROUND_BASELINE_VECS = bg_feat.cpu().numpy().astype(np.float32)
        except Exception as e:
            logging.error(f"Failed to encode background baseline vectors: {e}")


WATCHED_EDIT_TARGETS: Dict[str, Any] = {
    "files": {},  # file_path -> (last_mtime, last_size)
    "dirs": {},   # dir_path -> set_of_known_files
    "last_sync_event": None,
}
WATCHER_LOCK = threading.Lock()


def _register_file_for_edit_watcher(file_path: str) -> None:
    p = Path(file_path)
    if not p.exists():
        return
    try:
        st = p.stat()
        parent = p.parent
        with WATCHER_LOCK:
            WATCHED_EDIT_TARGETS["files"][str(p)] = (float(st.st_mtime), int(st.st_size))
            if parent.exists():
                WATCHED_EDIT_TARGETS["dirs"][str(parent)] = {
                    str(c) for c in parent.iterdir() if c.is_file()
                }
        conn = get_db_connection(DEFAULT_DB_PATH)
        conn.execute(
            "UPDATE photo_records SET file_mtime = ?, file_size = ? WHERE file_path = ? OR sibling_path = ?",
            (float(st.st_mtime), int(st.st_size), str(p), str(p)),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logging.debug(f"Could not register edit watcher for {file_path}: {exc}")


def _background_edit_watcher_loop() -> None:
    """
    Lightweight background thread polling files/folders recently opened in Photoshop
    every 5 seconds so saved edits or new sibling derivatives auto-sync into the studio.
    """
    while True:
        time.sleep(5.0)
        try:
            if PIPELINE_STATUS.get("running"):
                continue
            with WATCHER_LOCK:
                watched_files = dict(WATCHED_EDIT_TARGETS["files"])
                watched_dirs = {k: set(v) for k, v in WATCHED_EDIT_TARGETS["dirs"].items()}

            if not watched_files and not watched_dirs:
                continue

            triggered_paths: List[str] = []
            for fp_str, (prev_mtime, prev_size) in watched_files.items():
                p = Path(fp_str)
                if not p.exists():
                    continue
                try:
                    st = p.stat()
                    if abs(float(st.st_mtime) - prev_mtime) > 1.0 or int(st.st_size) != prev_size:
                        triggered_paths.append(fp_str)
                        with WATCHER_LOCK:
                            WATCHED_EDIT_TARGETS["files"][fp_str] = (float(st.st_mtime), int(st.st_size))
                except Exception:
                    pass

            for dir_str, known_set in watched_dirs.items():
                dp = Path(dir_str)
                if not dp.exists():
                    continue
                try:
                    current_files = {str(c) for c in dp.iterdir() if c.is_file()}
                    new_files = current_files - known_set
                    img_new = [
                        nf for nf in new_files
                        if Path(nf).suffix.lower() in {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".dng"}
                        and not Path(nf).name.startswith(".")
                    ]
                    if img_new:
                        # Trigger sync via any watched file in that directory
                        sample_fp = next((f for f in watched_files if str(Path(f).parent) == dir_str), img_new[0])
                        if sample_fp not in triggered_paths:
                            triggered_paths.append(sample_fp)
                        with WATCHER_LOCK:
                            WATCHED_EDIT_TARGETS["dirs"][dir_str] = current_files
                except Exception:
                    pass

            if triggered_paths:
                logging.info(f"[EditWatcher] Detected external edit/save on {triggered_paths}, syncing...")
                res = sync_external_edits(
                    db_path=DEFAULT_DB_PATH,
                    vectors_path=DEFAULT_VECTORS_PATH,
                    color_sigs_path=DEFAULT_COLOR_SIGS_PATH,
                    thumbs_360_dir=DEFAULT_THUMBS_360_DIR,
                    previews_1600_dir=DEFAULT_PREVIEWS_1600_DIR,
                    target_file_paths=triggered_paths,
                    scan_parent_dirs=True,
                )
                global VECTORS_MTIME, COLOR_SIGS_MTIME
                VECTORS_MTIME = 0.0
                COLOR_SIGS_MTIME = 0.0
                with WATCHER_LOCK:
                    WATCHED_EDIT_TARGETS["last_sync_event"] = {
                        "timestamp": datetime.now().isoformat(),
                        "result": res,
                    }
        except Exception as exc:
            logging.debug(f"[EditWatcher] loop warning: {exc}")


@app.on_event("startup")
async def startup_event():
    init_and_migrate_db(DEFAULT_DB_PATH)
    create_rolling_vault_backup(DEFAULT_DB_PATH, reason="startup")
    DEFAULT_THUMBS_360_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PREVIEWS_1600_DIR.mkdir(parents=True, exist_ok=True)
    # Warm up OpenCLIP in background thread
    threading.Thread(target=ensure_clip_loaded, daemon=True).start()
    # Start lightweight external edit watcher thread
    threading.Thread(target=_background_edit_watcher_loop, daemon=True).start()


def encode_text_batch(texts: List[str]) -> Dict[str, np.ndarray]:
    """Encodes a list of strings with caching for <2ms repeated lookups."""
    ensure_clip_loaded()
    if CLIP_MODEL is None or CLIP_TOKENIZER is None:
        return {}
    clean_texts = [t.strip() for t in texts if t and t.strip()]
    missing = [t for t in clean_texts if t not in TEXT_EMBED_CACHE]
    if missing:
        try:
            # Encode in batches of 64
            for i in range(0, len(missing), 64):
                chunk = missing[i : i + 64]
                tokens = CLIP_TOKENIZER(chunk).to(CLIP_DEVICE)
                with torch.no_grad():
                    feat = CLIP_MODEL.encode_text(tokens)
                    feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                    arr = feat.cpu().numpy().astype(np.float32)
                for txt, vec in zip(chunk, arr):
                    TEXT_EMBED_CACHE[txt] = vec
        except Exception as e:
            logging.error(f"Error batch-encoding texts: {e}")
    return {t: TEXT_EMBED_CACHE[t] for t in clean_texts if t in TEXT_EMBED_CACHE}


def encode_text_query(query: str) -> Optional[np.ndarray]:
    """
    Encodes a search query using a foreground-focused prompt ('a photo featuring {Q}')
    blended with the direct query for high precision on specific objects & landmarks.
    """
    q = (query or "").strip()
    if not q:
        return None
    prompt_feat = f"a photo featuring {q}"
    emb_map = encode_text_batch([q, prompt_feat])
    if prompt_feat in emb_map and q in emb_map:
        blended = 0.65 * emb_map[prompt_feat] + 0.35 * emb_map[q]
        norm = float(np.linalg.norm(blended))
        return (blended / norm).astype(np.float32) if norm > 1e-8 else emb_map[prompt_feat]
    return emb_map.get(prompt_feat) or emb_map.get(q)


def resolve_photo_record(photo_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    # Support lookup by file_hash or file_path or stem
    row = cursor.execute(
        "SELECT * FROM photo_records WHERE file_hash = ? LIMIT 1", (photo_id,)
    ).fetchone()
    if not row:
        row = cursor.execute(
            "SELECT * FROM photo_records WHERE file_path = ? LIMIT 1", (photo_id,)
        ).fetchone()
    if not row:
        row = cursor.execute(
            "SELECT * FROM photo_records WHERE file_path LIKE ? LIMIT 1", (f"%{photo_id}%",)
        ).fetchone()
    conn.close()
    return dict(row) if row else None


# ==============================================================================
# PREVIEW STATIC FILE ROUTES (AGGRESSIVE BROWSER CACHING)
# ==============================================================================
@app.get("/previews/thumbs_360/{filename}")
async def get_thumb_360(filename: str):
    p = DEFAULT_THUMBS_360_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(
        str(p),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/previews/previews_1600/{filename}")
async def get_preview_1600(filename: str):
    p = DEFAULT_PREVIEWS_1600_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(
        str(p),
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.api_route("/api/thumbnail/{photo_id:path}", methods=["GET", "HEAD"])
async def get_photo_thumbnail(photo_id: str):
    clean_id = (photo_id or "").strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="Missing photo_id")

    # 1. Direct WebP file check in thumbs_360
    stem_name = Path(clean_id).stem
    p_direct = DEFAULT_THUMBS_360_DIR / f"{stem_name}.webp"
    if p_direct.exists():
        return FileResponse(
            str(p_direct),
            media_type="image/webp",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # 2. Query photo_records for thumb_360_path / preview_1600_path
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    row = cursor.execute(
        """
        SELECT thumb_360_path, preview_1600_path
        FROM photo_records
        WHERE file_hash = ? OR file_path = ? OR rowid = ?
        LIMIT 1
        """,
        (clean_id, clean_id, int(clean_id) if clean_id.isdigit() else -1),
    ).fetchone()
    conn.close()

    if row:
        t_path = row["thumb_360_path"]
        if t_path:
            p_cand = Path(t_path)
            if not p_cand.is_absolute():
                p_cand = DEFAULT_THUMBS_360_DIR / p_cand.name
            if p_cand.exists():
                return FileResponse(
                    str(p_cand),
                    media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )
        p_path = row["preview_1600_path"]
        if p_path:
            p_cand = Path(p_path)
            if not p_cand.is_absolute():
                p_cand = DEFAULT_PREVIEWS_1600_DIR / p_cand.name
            if p_cand.exists():
                return FileResponse(
                    str(p_cand),
                    media_type="image/webp",
                    headers={"Cache-Control": "public, max-age=31536000, immutable"},
                )

    raise HTTPException(status_code=404, detail="Thumbnail not found")


# ==============================================================================
# 1. CATALOGS & SYSTEM SUMMARY
# ==============================================================================
@app.get("/api/catalogs")
async def list_catalogs():
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    db_catalogs = cursor.execute(
        "SELECT catalog_name, root_path, description, photo_count as total_photos, last_scanned_at FROM catalogs"
    ).fetchall()
    catalogs_by_name: Dict[str, Dict[str, Any]] = {}
    for r in db_catalogs:
        d = dict(r)
        cname = d.get("catalog_name")
        if cname:
            d["photo_count"] = int(d.get("total_photos") or 0)
            catalogs_by_name[cname] = d

    # Get distinct catalog names and live counts from photo_records
    counts_rows = cursor.execute(
        "SELECT catalog_name, COUNT(*) as cnt FROM photo_records WHERE status != 'failed' GROUP BY catalog_name"
    ).fetchall()
    counts_map = {r["catalog_name"]: int(r["cnt"]) for r in counts_rows if r["catalog_name"]}

    for cname, cnt in counts_map.items():
        if cname in catalogs_by_name:
            catalogs_by_name[cname]["photo_count"] = cnt
            catalogs_by_name[cname]["total_photos"] = cnt
        else:
            catalogs_by_name[cname] = {
                "catalog_name": cname,
                "root_path": "",
                "description": "",
                "photo_count": cnt,
                "total_photos": cnt,
                "last_scanned_at": None,
            }

    catalogs_list = [c for c in catalogs_by_name.values() if int(c.get("photo_count") or 0) > 0]

    total_photos = cursor.execute("SELECT COUNT(*) FROM photo_records WHERE status != 'failed'").fetchone()[0]
    keepers_count = cursor.execute(
        "SELECT COUNT(*) FROM photo_records WHERE catalog_name = 'Keepers' AND status != 'failed'"
    ).fetchone()[0]
    unsharp_count = cursor.execute(
        "SELECT COUNT(*) FROM photo_records WHERE is_unsharp = 1"
    ).fetchone()[0]

    conn.close()

    cfg = load_settings()
    configured_catalogs = cfg.get("catalogs", [])

    return {
        "total_photos": total_photos,
        "keepers_count": keepers_count,
        "unsharp_count": unsharp_count,
        "catalogs": catalogs_list,
        "catalog_counts": counts_map,
        "configured_catalogs": configured_catalogs,
    }


class AddCatalogRequest(BaseModel):
    name: str
    path: Optional[str] = None
    root_path: Optional[str] = None
    description: Optional[str] = None
    is_keepers: bool = False


@app.post("/api/catalogs/add")
async def add_catalog(payload: AddCatalogRequest):
    catalog_path = payload.path or payload.root_path
    if not catalog_path:
        raise HTTPException(status_code=400, detail="Missing catalog path or root_path")

    p = Path(catalog_path).expanduser().resolve()
    if not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            raise HTTPException(status_code=400, detail=f"Directory path does not exist and cannot be created: {catalog_path}")

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO catalogs (catalog_name, root_path, description, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(catalog_name) DO UPDATE SET
            root_path = excluded.root_path,
            description = excluded.description
    """, (payload.name, str(p), payload.description))
    conn.commit()
    conn.close()

    return {"status": "ok", "catalog_name": payload.name, "root_path": str(p)}


class PrescanFolderRequest(BaseModel):
    path: Optional[str] = None
    root_path: Optional[str] = None


def _run_folder_prescan(raw_path: str) -> Dict[str, Any]:
    clean_raw = (raw_path or "").strip()
    if not clean_raw:
        return {
            "status": "empty",
            "exists": False,
            "path": "",
            "folder_name": "",
            "suggested_catalog_name": "",
            "total_photos": 0,
            "extension_counts": {},
            "summary_text": "Select or browse to a folder to preview photo count.",
            "has_lrcat": False,
            "lrcat_files": [],
            "lrcat_found": False,
            "lrcat_name": "",
            "lrcat_path": "",
            "previews_found": False,
            "previews_name": "",
            "previews_path": "",
            "has_previews_ready": False,
            "subfolders": [],
            "can_split_subfolders": False,
        }

    p = Path(clean_raw).expanduser()
    if not p.exists() or not p.is_dir():
        return {
            "status": "not_found",
            "exists": False,
            "path": str(p),
            "folder_name": p.name,
            "suggested_catalog_name": p.name,
            "total_photos": 0,
            "extension_counts": {},
            "summary_text": f"Folder not found on disk: {clean_raw}",
            "has_lrcat": False,
            "lrcat_files": [],
            "lrcat_found": False,
            "lrcat_name": "",
            "lrcat_path": "",
            "previews_found": False,
            "previews_name": "",
            "previews_path": "",
            "has_previews_ready": False,
            "subfolders": [],
            "can_split_subfolders": False,
        }

    p_resolved = p.resolve()
    paired_items, lrcat_files = discover_catalog_files(p_resolved)

    # 1. Discover active Lightroom .lrcat and Previews.lrdata bundle
    sample_stems = [item["primary"].stem.lower() for item in paired_items[:25]] if paired_items else None
    active_lrcat, active_previews, ranked_cands = find_active_lrcat_and_previews(p_resolved, sample_stems=sample_stems)

    has_lrcat = bool(active_lrcat or lrcat_files)
    lrcat_name = active_lrcat.name if active_lrcat else (lrcat_files[0].name if lrcat_files else "")
    lrcat_path_str = str(active_lrcat) if active_lrcat else (str(lrcat_files[0]) if lrcat_files else "")
    previews_name = active_previews.name if active_previews else ""
    previews_path_str = str(active_previews) if active_previews else ""
    has_previews_ready = bool(active_previews and (active_previews / "previews.db").exists())

    # 2. Scan immediate child subfolders with photo counts
    subfolders: List[Dict[str, Any]] = []
    try:
        with os.scandir(p_resolved) as it:
            for entry in it:
                if entry.is_dir() and not entry.name.startswith(".") and not entry.name.lower().endswith(".lrdata"):
                    sub_low = entry.name.lower()
                    if sub_low in {"backups", "backup", "_temporary", ".trash", ".trashes", "old versions"}:
                        continue
                    sub_p = Path(entry.path)
                    sub_items, _ = discover_catalog_files(sub_p, auto_discover_external_lrcat=False)
                    if sub_items:
                        subfolders.append({
                            "name": entry.name,
                            "path": str(sub_p),
                            "photo_count": len(sub_items),
                        })
    except Exception:
        pass
    subfolders.sort(key=lambda x: x["name"].lower())

    ext_counter: Counter = Counter()
    for item in paired_items:
        prim = item.get("primary") or item.get("primary_path") or ""
        ext_label = str(item.get("ext") or Path(prim).suffix).upper().lstrip(".")
        if ext_label == "JPEG":
            ext_label = "JPG"
        elif ext_label == "TIFF":
            ext_label = "TIF"
        elif ext_label == "HEIF":
            ext_label = "HEIC"
        ext_counter[ext_label or "IMG"] += 1

    sorted_exts = dict(ext_counter.most_common())
    total_count = len(paired_items)
    if total_count > 0:
        breakdown_str = ", ".join(f"{cnt} {ext}" for ext, cnt in sorted_exts.items())
        summary_text = f"Found {total_count} photo{'s' if total_count != 1 else ''}: {breakdown_str}"
    else:
        summary_text = "Found 0 supported photos in this folder."

    return {
        "status": "ok",
        "exists": True,
        "path": str(p_resolved),
        "folder_name": p_resolved.name,
        "suggested_catalog_name": p_resolved.name,
        "total_photos": total_count,
        "extension_counts": sorted_exts,
        "summary_text": summary_text,
        "has_lrcat": has_lrcat,
        "lrcat_files": [str(x) for x in lrcat_files],
        "lrcat_found": has_lrcat,
        "lrcat_name": lrcat_name,
        "lrcat_path": lrcat_path_str,
        "previews_found": bool(active_previews),
        "previews_name": previews_name,
        "previews_path": previews_path_str,
        "has_previews_ready": has_previews_ready,
        "subfolders": subfolders,
        "can_split_subfolders": len(subfolders) >= 1,
    }


@app.get("/api/catalogs/prescan")
async def prescan_catalog_folder_get(path: str = Query(""), root_path: str = Query("")):
    target_path = path or root_path or ""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_folder_prescan, target_path)


@app.post("/api/catalogs/prescan")
async def prescan_catalog_folder_post(payload: PrescanFolderRequest):
    target_path = payload.path or payload.root_path or ""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_folder_prescan, target_path)


@app.post("/api/pipeline/inspect-folder")
async def inspect_folder_post(payload: PrescanFolderRequest):
    target_path = payload.path or payload.root_path or ""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _run_folder_prescan, target_path)


@app.get("/api/system/browse-folder")
@app.post("/api/system/browse-folder")
async def browse_macos_folder():
    """
    Opens a native macOS Finder folder selection dialog via osascript
    so the user can browse to any folder on Mac or external DAS without copy-pasting paths.
    Automatically runs a live pre-scan on the selected folder before returning.
    """
    script = 'POSIX path of (choose folder with prompt "Select Photo Folder to Import into MR Darkroom:")'
    loop = asyncio.get_running_loop()
    try:
        res = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["/usr/bin/osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=300.0,
            ),
        )
        if res.returncode != 0:
            return {"status": "cancelled", "cancelled": True, "path": None}
        folder_path = (res.stdout or "").strip()
        if not folder_path:
            return {"status": "cancelled", "cancelled": True, "path": None}
        prescan = await loop.run_in_executor(None, _run_folder_prescan, folder_path)
        return {
            "status": "ok",
            "cancelled": False,
            "path": prescan["path"],
            "folder_name": prescan["folder_name"],
            "suggested_catalog_name": prescan["suggested_catalog_name"],
            "prescan": prescan,
        }
    except Exception as exc:
        return {"status": "cancelled", "cancelled": True, "path": None, "error": str(exc)}


@app.delete("/api/catalogs/{catalog_name}")
async def delete_catalog_entry(catalog_name: str, remove_photos: bool = Query(True)):
    clean_name = (catalog_name or "").strip()
    if not clean_name or clean_name.lower() in ("all catalogs", "all", "keepers"):
        raise HTTPException(status_code=400, detail="Cannot delete built-in studio view")

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM catalogs WHERE catalog_name = ?", (clean_name,))
    removed_photos = 0
    if remove_photos:
        cursor.execute("DELETE FROM photo_records WHERE catalog_name = ?", (clean_name,))
        removed_photos = cursor.rowcount
    conn.commit()
    conn.close()
    return {"status": "ok", "catalog_name": clean_name, "removed_photos": removed_photos}


# ==============================================================================
# UNIVERSAL TAG, SHOOT TITLE, GAZETTEER & BIOME HELPERS
# ==============================================================================
import re
from collections import Counter


def _parse_json_list(val: Any) -> List[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            return [s.strip() for s in val.split(",") if s.strip()]
    return []


def _is_boilerplate_tag(tag: str) -> bool:
    tl = str(tag or "").strip().lower()
    if not tl or len(tl) <= 1:
        return True
    if tl in {"mitch rouse (subject)", "identity|mitch rouse", "mitch shooting"}:
        return False
    if tl in BOILERPLATE_TAGS_LOWER:
        return True
    if "mitch rouse aerials" in tl or "mitch_rouse_aerials" in tl or "west coast imaging" in tl:
        return True
    return False


def _parse_json_raw_list(val: Any) -> List[Any]:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
    return []


def _serialize_photo_item(item: Dict[str, Any], shoot_title: Optional[str] = None) -> Dict[str, Any]:
    t_path = item.get("thumb_360_path")
    p_path = item.get("preview_1600_path")
    cache_ver = ""
    if item.get("file_mtime"):
        cache_ver = f"?v={int(float(item['file_mtime']))}"
    elif item.get("updated_at"):
        cache_ver = f"?v={str(item['updated_at']).replace(' ', '_').replace(':', '')}"
    item["thumb_url"] = f"/previews/thumbs_360/{Path(t_path).name}{cache_ver}" if t_path else None
    item["preview_url"] = f"/previews/previews_1600/{Path(p_path).name}{cache_ver}" if p_path else None

    for k in ("lrcat_keywords", "existing_keywords", "key_subjects", "hierarchical_keywords", "user_taught_tags", "negated_tags"):
        item[k] = _parse_json_list(item.get(k))
    item["subject_boxes"] = _parse_json_raw_list(item.get("subject_boxes"))
    item["verified_subjects"] = _parse_json_raw_list(item.get("verified_subjects"))
    item["location_provenance"] = str(item.get("location_provenance") or "").strip()
    item["user_context_notes"] = str(item.get("user_context_notes") or "").strip()
    item["tag_authority_weight"] = float(item.get("tag_authority_weight") or 0.85)
    item["assessment_tier"] = str(item.get("assessment_tier") or "level1")
    item["macro_biome"] = str(item.get("macro_biome") or "")

    # Enforce strict Blank-by-Default location serialization (never "Unknown" or "None")
    for loc_f in ("country", "state_region", "city", "specific_location", "sub_location"):
        lv = str(item.get(loc_f) or "").strip()
        if lv.lower() in ("unknown", "none", "null"):
            lv = ""
        item[loc_f] = lv

    # Clean boilerplate leaves from hierarchical_keywords
    clean_hier: List[str] = []
    for h in item["hierarchical_keywords"]:
        parts = [p.strip() for p in str(h).split("|") if p.strip() and not _is_boilerplate_tag(p)]
        if len(parts) >= 2:
            cleaned_h = "|".join(parts)
            if cleaned_h not in clean_hier:
                clean_hier.append(cleaned_h)
    item["hierarchical_keywords"] = clean_hier

    negated_low = {n.lower().strip() for n in item["negated_tags"] if n.strip()}
    # Strip conversational filler or directive fragments if accidentally present in user_taught_tags
    _directive_junk_low = {
        "bro just look", "what's", "whats", "just look", "look at it",
        "tag what's", "tag whats", "in there", "tell me", "look closely",
        "reassess", "rescan", "re-scan",
    }
    item["user_taught_tags"] = [
        t for t in item["user_taught_tags"]
        if str(t).strip() and str(t).strip().lower() not in _directive_junk_low
    ]
    taught_low = {t.lower().strip() for t in item["user_taught_tags"] if t.strip()}

    # Build redundant location & internal classifier filter set so Location Metadata stays in the Location card
    # and technical/portfolio classifiers never clutter Keywords & Studio Tags
    _hidden_studio_tag_low = {
        "national parks & mountains",
        "pets & animals",
        "portraits & people",
        "automotive & urban",
        "architecture & interiors",
        "everyday & lifestyle",
        "eye-level terrestrial",
        "eye-level",
        "terrestrial",
        "unsharp",
        "sharp",
        "united states",
        "usa",
    } | _directive_junk_low
    _cty = item.get("city", "")
    _sub = item.get("sub_location", "")
    _st = item.get("state_region", "")
    _ctry = item.get("country", "")
    _spec = item.get("specific_location", "")
    for _loc_val in (_cty, _sub, _st, _ctry):
        if _loc_val:
            _hidden_studio_tag_low.add(_loc_val.lower())
    if _cty and _st:
        _hidden_studio_tag_low.add(f"{_cty}, {_st}".lower())
    if _spec and (int(item.get("gps_ground_truth") or 0) == 1 or item.get("location_provenance") in ("exif_gps", "same_day_gps") or "," in _spec):
        _hidden_studio_tag_low.add(_spec.lower())

    def _is_redundant_location_or_classifier_tag(tag_str: str) -> bool:
        tl = tag_str.strip().lower()
        if not tl:
            return True
        if tl in _hidden_studio_tag_low:
            return True
        if tl.endswith(" county"):
            return True
        return False

    primary_tags: List[str] = []
    boilerplate_tags: List[str] = []
    # Put photographer-taught tags first, then curated LrCat & existing non-boilerplate tags, then AI 5-facet key_subjects
    for src_list in (item["user_taught_tags"], item["lrcat_keywords"], item["existing_keywords"], item["key_subjects"]):
        for t in src_list:
            ts = str(t).strip()
            if not ts or ts == "[CLEARED_SLATE]" or ts.lower() in negated_low:
                continue
            if ts.lower() not in taught_low and _is_redundant_location_or_classifier_tag(ts):
                continue
            if ts.lower() not in taught_low and _is_boilerplate_tag(ts):
                if ts not in boilerplate_tags:
                    boilerplate_tags.append(ts)
            else:
                if ts not in primary_tags:
                    primary_tags.append(ts)

    item["key_subjects"] = [
        t for t in item["key_subjects"]
        if str(t).strip() and (str(t).strip().lower() in taught_low or not _is_redundant_location_or_classifier_tag(str(t)))
    ]

    subj_counts: Dict[str, int] = {}
    for sb in item["subject_boxes"]:
        if isinstance(sb, dict) and sb.get("label"):
            lbl_low = str(sb["label"]).lower().strip()
            subj_counts[lbl_low] = subj_counts.get(lbl_low, 0) + 1

    primary_tags = deduplicate_singular_plural_tags(primary_tags, subject_counts=subj_counts)
    item["key_subjects"] = deduplicate_singular_plural_tags(item["key_subjects"], subject_counts=subj_counts)

    item["tags"] = primary_tags
    item["all_tags"] = primary_tags + boilerplate_tags
    item["gps_ground_truth"] = int(item.get("gps_ground_truth") or 0)
    item["is_screenshot"] = int(item.get("is_screenshot") or 0)
    if shoot_title:
        item["shoot_title"] = shoot_title
    return item


def _extract_non_boilerplate_tags(r: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    negated_lower = {str(nt).strip().lower() for nt in _parse_json_list(r.get("negated_tags")) if str(nt).strip()}
    taught_lower = {str(ut).strip().lower() for ut in _parse_json_list(r.get("user_taught_tags")) if str(ut).strip()}
    for k in ("user_taught_tags", "lrcat_keywords", "existing_keywords", "key_subjects"):
        for t in _parse_json_list(r.get(k)):
            tl = t.strip()
            if tl and tl != "[CLEARED_SLATE]" and tl.lower() not in negated_lower and (tl.lower() in taught_lower or not _is_boilerplate_tag(tl)):
                tags.append(tl)
    for h in _parse_json_list(r.get("hierarchical_keywords")):
        for part in str(h).split("|"):
            pl = part.strip()
            if pl and pl.lower() not in negated_lower and pl.lower() not in ("places", "united states", "subject", "lighting") and not _is_boilerplate_tag(pl):
                tags.append(pl)
    for loc_field in ("specific_location", "sub_location", "city", "state_region", "country"):
        val = str(r.get(loc_field) or "").strip()
        if val and val.lower() not in negated_lower and val.lower() not in ("", "unknown", "united states") and not _is_boilerplate_tag(val):
            tags.append(val)
    # Deduplicate preserving order
    seen = set()
    unique_tags = []
    for t in tags:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            unique_tags.append(t)
    return unique_tags


def _extract_biome_tokens(r: Dict[str, Any]) -> set:
    """
    Extracts normalized biome, category, place, and lighting tokens for a photo
    to drive multi-modal Find Similar biome alignment.
    """
    tokens = set()
    for field in ("primary_category", "sub_category", "state_region", "specific_location"):
        val = str(r.get(field) or "").strip().lower()
        if val and not _is_boilerplate_tag(val):
            tokens.add(val)

    for h in _parse_json_list(r.get("hierarchical_keywords")):
        parts = [p.strip().lower() for p in str(h).split("|") if p.strip() and not _is_boilerplate_tag(p)]
        for p in parts:
            if p not in ("places", "united states", "subject"):
                tokens.add(p)

    for k in ("lrcat_keywords", "existing_keywords", "key_subjects"):
        for t in _parse_json_list(r.get(k)):
            tl = t.strip().lower().replace("_", " ")
            if tl and not _is_boilerplate_tag(tl):
                tokens.add(tl)
                for w in tl.split():
                    if len(w) >= 4 and w not in BOILERPLATE_TAGS_LOWER:
                        tokens.add(w)
    return tokens


def _resolve_photo_geo(r: Dict[str, Any]) -> Optional[Tuple[float, float, str, str]]:
    """
    Resolves (lat, lon, canonical_place, region_state) for a photo record using
    exact EXIF GPS coordinates if present, or specific_location, lrcat_keywords,
    hierarchical_keywords, state_region, or filename stem.
    """
    if r.get("gps_lat") is not None and r.get("gps_lon") is not None:
        try:
            g_lat = float(r["gps_lat"])
            g_lon = float(r["gps_lon"])
            if not (abs(g_lat) < 1e-6 and abs(g_lon) < 1e-6):
                place_lbl = (
                    str(r.get("specific_location") or "").strip()
                    or str(r.get("sub_location") or "").strip()
                    or str(r.get("city") or "").strip()
                    or str(r.get("state_region") or "").strip()
                    or str(r.get("country") or "").strip()
                    or "GPS Location"
                )
                region_lbl = (
                    str(r.get("state_region") or "").strip()
                    or str(r.get("country") or "").strip()
                    or ""
                )
                return (g_lat, g_lon, place_lbl, region_lbl)
        except Exception:
            pass

    candidates: List[str] = []
    for k in ("lrcat_keywords", "existing_keywords"):
        for t in _parse_json_list(r.get(k)):
            if not _is_boilerplate_tag(t):
                candidates.append(t.strip().lower())
    for f in ("specific_location", "sub_location", "city"):
        v = str(r.get(f) or "").strip().lower()
        if v and not _is_boilerplate_tag(v):
            candidates.append(v)
    for h in _parse_json_list(r.get("hierarchical_keywords")):
        parts = [p.strip().lower() for p in str(h).split("|") if p.strip() and not _is_boilerplate_tag(p)]
        candidates.extend(reversed(parts))
    for f_reg in ("state_region", "country"):
        st = str(r.get(f_reg) or "").strip().lower()
        if st and st not in ("unknown", "united states") and not _is_boilerplate_tag(st):
            candidates.append(st)

    stem = Path(r.get("file_path") or "").stem.lower().replace("_", " ").replace("-", " ")
    candidates.append(stem)

    # 1. Exact key match in OFFLINE_GAZETTEER
    for cand in candidates:
        if cand in OFFLINE_GAZETTEER:
            return OFFLINE_GAZETTEER[cand]

    # 2. Substring match (prefer longer/more specific landmark names first)
    sorted_gaz = sorted(OFFLINE_GAZETTEER.items(), key=lambda kv: len(kv[0]), reverse=True)
    for cand in candidates:
        for g_key, g_val in sorted_gaz:
            if len(g_key) >= 4 and g_key in cand:
                return g_val

    return None


def _synthesize_shoot_title(date_rows: List[Dict[str, Any]]) -> str:
    """
    Synthesizes a human-readable Shoot Title for a capture date or trip
    by extracting dominant non-boilerplate place & subject terms.
    """
    place_counts: Counter = Counter()
    subject_counts: Counter = Counter()

    for r in date_rows:
        geo = _resolve_photo_geo(r)
        if geo:
            place_counts[geo[2]] += 2

        spec = str(r.get("specific_location") or "").strip()
        if spec and not _is_boilerplate_tag(spec) and len(spec) > 2:
            place_counts[spec] += 2

        state = str(r.get("state_region") or "").strip()
        if state and not _is_boilerplate_tag(state):
            place_counts[state] += 1

        for k in ("lrcat_keywords", "existing_keywords"):
            for t in _parse_json_list(r.get(k)):
                if not _is_boilerplate_tag(t) and len(t) > 2:
                    place_counts[t.strip()] += 3

        for h in _parse_json_list(r.get("hierarchical_keywords")):
            parts = [p.strip().replace("_", " ") for p in str(h).split("|") if p.strip() and not _is_boilerplate_tag(p)]
            if len(parts) >= 2:
                root = parts[0].lower()
                leaf = parts[-1]
                if root == "places" and leaf.lower() != "united states":
                    place_counts[leaf] += 2
                elif root in ("landscape", "aerial", "water", "architecture", "agriculture"):
                    subject_counts[leaf.title()] += 2

        for s in _parse_json_list(r.get("key_subjects")):
            s_clean = s.strip().replace("_", " ")
            if not _is_boilerplate_tag(s_clean) and len(s_clean) > 2:
                subject_counts[s_clean.title()] += 1

    top_place = place_counts.most_common(1)[0][0] if place_counts else None
    top_subj = None
    for subj, _ in subject_counts.most_common(5):
        if not top_place or subj.lower() not in top_place.lower():
            top_subj = subj
            break

    if top_place and top_subj:
        return f"{top_place} · {top_subj}"
    if top_place:
        return top_place
    if top_subj:
        return f"Studio & Field Shoot · {top_subj}"
    return "Field & Aerial Session"


def _stem_word(w: str) -> str:
    w = w.lower().strip()
    if len(w) > 5 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("es"):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


_QUERY_HYPERNYM_MAP: Dict[str, Set[str]] = {
    "animal": {"animal", "animals", "wildlife", "fauna", "bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "elk", "deer", "bird", "birds", "pelican", "dog", "cat", "kitten", "scottish fold", "french bulldog", "sheep", "livestock", "mammal"},
    "animals": {"animal", "animals", "wildlife", "fauna", "bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "elk", "deer", "bird", "birds", "pelican", "dog", "cat", "kitten", "scottish fold", "french bulldog", "sheep", "livestock", "mammal"},
    "pet": {"cat", "kitten", "scottish fold", "tabby cat", "dog", "puppy", "french bulldog", "chihuahua", "terrier", "retriever", "domestic cat", "domestic dog"},
    "pets": {"cat", "kitten", "scottish fold", "tabby cat", "dog", "puppy", "french bulldog", "chihuahua", "terrier", "retriever", "domestic cat", "domestic dog"},
    "wildlife": {"animal", "animals", "wildlife", "fauna", "bison", "buffalo", "elk", "deer", "bird", "birds", "pelican"},
    "person": {"person", "people", "human", "man", "woman", "male", "female", "photographer", "mitch rouse (subject)", "mitch shooting", "cowboy", "rancher", "rider", "portrait", "family"},
    "people": {"person", "people", "human", "man", "woman", "male", "female", "photographer", "mitch rouse (subject)", "mitch shooting", "cowboy", "rancher", "rider", "portrait", "family"},
    "human": {"person", "people", "human", "man", "woman", "male", "female", "photographer", "mitch rouse (subject)", "mitch shooting", "cowboy", "rancher", "rider", "portrait", "family"},
    "man": {"man", "male", "photographer", "mitch rouse (subject)", "mitch shooting", "cowboy", "rancher"},
    "men": {"man", "male", "photographer", "mitch rouse (subject)", "mitch shooting", "cowboy", "rancher"},
    "woman": {"woman", "female"},
    "women": {"woman", "female"},
    "photographer": {"photographer", "mitch rouse (subject)", "mitch shooting"},
    "mitch": {"mitch rouse (subject)", "identity|mitch rouse", "mitch shooting", "photographer"},
    "flower": {"flower", "flowers", "wildflowers", "lupine", "poppies", "flora", "plants"},
    "flowers": {"flower", "flowers", "wildflowers", "lupine", "poppies", "flora", "plants"},
    "plant": {"plant", "plants", "flora", "wildflowers", "trees", "forest", "foliage", "vegetation", "houseplant", "pothos", "monstera"},
    "plants": {"plant", "plants", "flora", "wildflowers", "trees", "forest", "foliage", "vegetation", "houseplant", "pothos", "monstera"},
    "building": {"building", "buildings", "structure", "architecture", "barn", "farmstead", "ranch", "house", "cabin", "shed", "silo", "pier", "bridge", "door", "doors", "wooden door", "colonial door"},
    "buildings": {"building", "buildings", "structure", "architecture", "barn", "farmstead", "ranch", "house", "cabin", "shed", "silo", "pier", "bridge", "door", "doors", "wooden door", "colonial door"},
    "structure": {"structure", "architecture", "infrastructure", "barn", "farmstead", "ranch", "corral", "fence", "pier", "bridge", "train", "oil rig", "door", "doors", "wooden door", "colonial door", "archway"},
    "door": {"door", "doors", "wooden door", "colonial door", "archway"},
    "doors": {"door", "doors", "wooden door", "colonial door", "archway"},
    "butte": {"butte", "buttes", "mitten buttes", "valley of the gods", "monument valley", "castleton tower", "devils tower"},
    "buttes": {"butte", "buttes", "mitten buttes", "valley of the gods", "monument valley", "castleton tower", "devils tower"},
    "teton": {"tetons", "grand teton national park", "teton range"},
    "tetons": {"tetons", "grand teton national park", "teton range"},
    "iceland": {"iceland", "hallgrimskirkja", "kirkjufell", "jokulsarlon", "diamond beach", "reynisfjara", "gullfoss", "reykjavik"},
}

_STRICT_BIOLOGICAL_COUNTABLE_KEYS = {
    "cat", "cats", "kitten", "kittens", "feline", "scottish fold", "tabby cat",
    "dog", "dogs", "puppy", "puppies", "canine", "french bulldog",
    "frog", "frogs", "toad", "toads", "amphibian",
    "alligator", "alligators", "crocodile", "crocodiles",
    "bird", "birds", "pelican", "pelicans", "heron", "egret", "eagle", "hawk", "owl",
    "horse", "horses", "mustang", "mustangs", "foal",
    "bison", "buffalo", "cattle", "cow", "cows", "deer", "elk", "moose", "bear", "bears", "whale", "whales",
    "person", "people", "human", "man", "men", "woman", "women",
}


def _extract_countable_query_targets(query_str: str) -> List[Set[str]]:
    """
    If the search query asks for one or more countable discrete subjects (e.g. 'birds', 'frogs',
    'dogs', 'cats', 'scottish fold', 'boats', 'people', 'horses', 'bison'), returns the list of required target tag sets.
    For multi-word open-vocabulary scene phrases (3+ words like 'fence in front of overpass' or 'bohemian throw blanket on couch'),
    only biological animals/people enforce strict verified subject presence so open-vocabulary scene queries can score focal crops.
    """
    q_low = (query_str or "").strip().lower()
    if not q_low:
        return []
    # Do not treat compound structure/place queries like 'boathouse' or 'wildlife refuge' as countable subject queries
    if any(p in q_low for p in ("boathouse", "wildlife refuge", "birdseye", "bird's eye", "dogwood", "cathedral", "sawhorse", "catwalk")):
        return []
    if q_low in COUNTABLE_SEARCH_CONCEPTS:
        return [COUNTABLE_SEARCH_CONCEPTS[q_low]]
    q_words = [w for w in re.split(r"[^a-z0-9]+", q_low) if len(w) >= 2]
    is_long_open_vocab_phrase = len(q_words) >= 3
    groups: List[Set[str]] = []
    seen_roots: Set[str] = set()
    for w in q_words:
        if w in COUNTABLE_SEARCH_CONCEPTS:
            if is_long_open_vocab_phrase and w not in _STRICT_BIOLOGICAL_COUNTABLE_KEYS:
                continue
            target_set = COUNTABLE_SEARCH_CONCEPTS[w]
            sig = "|".join(sorted(target_set))
            if sig not in seen_roots:
                seen_roots.add(sig)
                groups.append(target_set)
    return groups


def _compute_row_verified_countable_set(r: Dict[str, Any]) -> Set[str]:
    neg_low = {str(n).strip().lower() for n in _parse_json_list(r.get("negated_tags")) if str(n).strip()}
    verified_tokens: Set[str] = set()
    verified_phrases: Set[str] = set()

    for vs in _parse_json_raw_list(r.get("verified_subjects")):
        lbl = str(vs.get("label") if isinstance(vs, dict) else vs).strip().lower()
        if lbl and lbl not in neg_low:
            verified_phrases.add(lbl)
            verified_tokens.update(re.findall(r"[a-z0-9]+", lbl))

    for col in ("user_taught_tags", "lrcat_keywords", "key_subjects"):
        for t in _parse_json_list(r.get(col)):
            tl = str(t or "").strip().lower().replace("_", " ")
            if not tl or tl in neg_low:
                continue
            if any(p in tl for p in ("wildlife refuge", "boathouse", "hawkeye", "deer creek", "bighorn", "eagle mountain", "pigeon point")):
                continue
            verified_phrases.add(tl)
            for w in re.findall(r"[a-z0-9]+", tl):
                if w not in neg_low:
                    verified_tokens.add(w)

    return verified_phrases | verified_tokens


def _passes_countable_subject_search_gate(r: Dict[str, Any], required_groups: List[Set[str]]) -> bool:
    """
    High-Trust Search Gate for Countable Discrete Subjects:
    Requires positive presence verification in verified_subjects, user_taught_tags,
    lrcat_keywords, or verified key_subjects (excluding negated_tags and compound place names).
    Never allows unverified OpenCLIP habitat similarity or substring collisions ('boathouse' != 'boat').
    """
    if not required_groups:
        return True
    all_verified = r.get("_all_verified_countable")
    if all_verified is None:
        all_verified = _compute_row_verified_countable_set(r)
    return all(bool(all_verified & grp) for grp in required_groups)


def _get_db_mtime_signature() -> Tuple[float, float, float]:
    db_m = DEFAULT_DB_PATH.stat().st_mtime if DEFAULT_DB_PATH.exists() else 0.0
    wal_p = Path(str(DEFAULT_DB_PATH) + "-wal")
    wal_m = wal_p.stat().st_mtime if wal_p.exists() else 0.0
    vec_m = DEFAULT_VECTORS_PATH.stat().st_mtime if DEFAULT_VECTORS_PATH.exists() else 0.0
    return (db_m, wal_m, vec_m)


def _get_cached_query_rows(where_sql: str, params_tuple: Tuple[Any, ...]) -> Tuple[List[Dict[str, Any]], Set[str]]:
    sig = _get_db_mtime_signature()
    if SEARCH_INDEX_CACHE.get("db_mtime_sig") != sig:
        SEARCH_INDEX_CACHE["db_mtime_sig"] = sig
        SEARCH_INDEX_CACHE["by_key"] = {}

    cache_key = (where_sql, params_tuple)
    cached = SEARCH_INDEX_CACHE["by_key"].get(cache_key)
    if cached is not None:
        return cached

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    sql = f"""
        SELECT file_path, file_hash, sibling_path, catalog_name,
               exif_time, shoot_date, status, camera_make, camera_model,
               focal_length, shutter_speed, aperture, iso,
               gps_lat, gps_lon, gps_alt, gps_ground_truth, is_screenshot,
               title, caption, sub_location, specific_location, city, state_region, country,
               star_rating, color_label, pick_flag,
               lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
               user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
               thumb_360_path, preview_1600_path,
               sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
               laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
               sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
               vector_index, in_keepers, file_mtime, updated_at,
               tag_authority_weight, assessment_tier, macro_biome
        FROM photo_records
        WHERE {where_sql}
    """
    raw_rows = [dict(r) for r in cursor.execute(sql, list(params_tuple)).fetchall()]

    # Also load entity names / breeds per file_hash from photo_entities + entity_clusters
    entity_tags_by_hash: Dict[str, List[str]] = {}
    try:
        ent_rows = cursor.execute(
            """
            SELECT pe.file_hash, ec.entity_name, ec.auto_breed, ec.entity_id
            FROM photo_entities pe
            JOIN entity_clusters ec ON pe.entity_id = ec.entity_id
            """
        ).fetchall()
        for er in ent_rows:
            fh = er["file_hash"]
            if not fh:
                continue
            lst = entity_tags_by_hash.setdefault(fh, [])
            if er["entity_name"]:
                lst.append(str(er["entity_name"]).strip())
            if er["auto_breed"]:
                lst.append(str(er["auto_breed"]).strip())
            if er["entity_id"]:
                lst.append(str(er["entity_id"]).strip())
    except Exception:
        pass
    conn.close()

    unique_catalog_tags: Set[str] = set()
    for r in raw_rows:
        ctags = _extract_non_boilerplate_tags(r)
        fh = r.get("file_hash")
        if fh and fh in entity_tags_by_hash:
            for et in entity_tags_by_hash[fh]:
                if et and et not in ctags:
                    ctags.append(et)
        r["_clean_tags"] = ctags
        ctags_low = {t.lower().replace("_", " ") for t in ctags}
        r["_clean_tags_lower_set"] = ctags_low
        unique_catalog_tags.update(ctags_low)
        stem_name = Path(r.get("file_path") or "").stem.lower()
        corpus_str = " ".join(ctags_low) + " " + stem_name.replace("_", " ")
        r["_corpus_tokens_str"] = corpus_str
        c_words = [w for w in re.split(r"[^a-z0-9]+", corpus_str) if len(w) >= 2]
        r["_corpus_words"] = c_words
        r["_corpus_stems"] = {_stem_word(w) for w in c_words}
        v_cnt = _compute_row_verified_countable_set(r)
        if fh and fh in entity_tags_by_hash:
            for et in entity_tags_by_hash[fh]:
                etl = et.lower().strip()
                v_cnt.add(etl)
                v_cnt.update(re.findall(r"[a-z0-9]+", etl))
        r["_all_verified_countable"] = v_cnt
        r["_entity_tokens"] = [et.lower() for et in entity_tags_by_hash.get(fh, [])] if fh else []

    if unique_catalog_tags:
        encode_text_batch(list(unique_catalog_tags))

    SEARCH_INDEX_CACHE["by_key"][cache_key] = (raw_rows, unique_catalog_tags)
    return raw_rows, unique_catalog_tags


def _apply_sort_by(
    rows_list: List[Dict[str, Any]],
    sort_by: str,
    has_active_query: bool = False,
) -> List[Dict[str, Any]]:
    norm_sort = (sort_by or "capture_desc").strip().lower()
    if norm_sort == "date_desc":
        norm_sort = "capture_desc"
    elif norm_sort == "date_asc":
        norm_sort = "capture_asc"

    if norm_sort == "capture_asc":
        dated = [r for r in rows_list if r.get("shoot_date") and r.get("shoot_date") != "Undated"]
        undated = [r for r in rows_list if not r.get("shoot_date") or r.get("shoot_date") == "Undated"]
        dated.sort(
            key=lambda x: (
                x.get("shoot_date") or "",
                x.get("exif_time") or "",
                x.get("file_path") or "",
            )
        )
        return dated + undated
    if norm_sort == "aesthetic_desc":
        return sorted(
            rows_list,
            key=lambda x: (
                float(x.get("aesthetic_score") or 0.0),
                float(x.get("sharpness_score") or 0.0),
            ),
            reverse=True,
        )
    if norm_sort == "stars_desc":
        return sorted(
            rows_list,
            key=lambda x: (
                int(x.get("star_rating") or 0),
                float(x.get("aesthetic_score") or 0.0),
            ),
            reverse=True,
        )
    if norm_sort == "sharpness_desc":
        return sorted(
            rows_list,
            key=lambda x: (
                float(x.get("sharpness_score") or 0.0),
                float(x.get("aesthetic_score") or 0.0),
            ),
            reverse=True,
        )
    if norm_sort == "filename_asc":
        return sorted(
            rows_list,
            key=lambda x: Path(x.get("file_path") or "").name.lower(),
        )
    # Default: capture_desc (when no active search query, sort newest first with Undated at bottom)
    if has_active_query:
        return rows_list
    return sorted(
        rows_list,
        key=lambda x: (
            0 if (not x.get("shoot_date") or x.get("shoot_date") == "Undated") else 1,
            x.get("shoot_date") or "",
            x.get("exif_time") or "",
            x.get("file_path") or "",
        ),
        reverse=True,
    )


# ==============================================================================
# 2. QUERY PHOTOS (CONTRASTIVE SEARCH, TAG-COHERENCE GATING, PERCENTILE FILTER)
# ==============================================================================
@app.get("/api/photos")
async def query_photos(
    catalog: str = Query("All Catalogs", description="Filter by catalog_name or 'All Catalogs'"),
    query: Optional[str] = Query(None, description="Semantic text query or keyword search"),
    q: Optional[str] = Query(None, description="Alias for query"),
    entity_id: Optional[str] = Query(None, description="Optional People & Pets entity_id filter"),
    trip_id: Optional[str] = Query(None, description="Optional trip_id filter from Trips & Map view"),
    portfolio_theme: Optional[str] = Query(None, description="Optional 10,000-foot Portfolio Category or Sub-Region filter"),
    year: Optional[str] = Query(None, description="Optional 4-digit shoot year filter (e.g. '2009')"),
    shoot_date: Optional[str] = Query(None, description="Optional single shoot_date filter"),
    shoot_dates: Optional[str] = Query(None, description="Optional comma-separated shoot_date filter"),
    collection_id: Optional[int] = Query(None, description="Optional collection_id filter"),
    aesthetic_percentile: Optional[str] = Query(None, pattern="^(all|top25|top10|top5)$"),
    aesthetic_tier: Optional[str] = Query(None, pattern="^(all|top25|top10|top5)$"),
    sort_by: str = Query("capture_desc", pattern="^(capture_desc|date_desc|capture_asc|date_asc|aesthetic_desc|stars_desc|sharpness_desc|filename_asc)$"),
    min_stars: Optional[int] = Query(None, ge=0, le=5),
    four_five_stars: Optional[bool] = Query(None),
    hide_unsharp: Optional[bool] = Query(None),
    sharp_only: Optional[bool] = Query(None),
    collapse_strafing: Optional[bool] = Query(None, description="Collapse strafing runs into hero cards"),
    collapse_sequences: Optional[bool] = Query(None, description="Alias for collapse_strafing"),
    ids_only: bool = Query(False, description="Return lightweight ID stubs for bulk selection"),
    offset: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=25000),
):
    active_query = (query if query is not None else q) or ""
    active_query = active_query.strip()

    norm_sort_by = (sort_by or "capture_desc").strip().lower()
    if norm_sort_by == "date_desc":
        norm_sort_by = "capture_desc"
    elif norm_sort_by == "date_asc":
        norm_sort_by = "capture_asc"

    effective_percentile = aesthetic_percentile or aesthetic_tier or "all"
    effective_hide_unsharp = bool(hide_unsharp) or bool(sharp_only)
    effective_min_stars = min_stars if min_stars is not None else (4 if four_five_stars else None)
    if collapse_sequences is not None:
        effective_collapse = collapse_sequences
    elif collapse_strafing is not None:
        effective_collapse = collapse_strafing
    else:
        effective_collapse = False

    where_clauses = ["status != 'failed'"]
    params: List[Any] = []

    cat_clean = (catalog or "").strip()
    if cat_clean and cat_clean.lower() not in ("all catalogs", "all", "all photos"):
        if cat_clean.lower() == "keepers":
            where_clauses.append("catalog_name = 'Keepers'")
        else:
            where_clauses.append("catalog_name = ?")
            params.append(cat_clean)

    if effective_hide_unsharp:
        where_clauses.append("(is_unsharp = 0 OR is_unsharp IS NULL)")

    if effective_min_stars is not None and effective_min_stars > 0:
        where_clauses.append("star_rating >= ?")
        params.append(effective_min_stars)

    combined_dates_str = shoot_dates or shoot_date
    if combined_dates_str and not trip_id:
        date_list = [d.strip() for d in combined_dates_str.split(",") if d.strip()]
        if date_list:
            placeholders = ",".join("?" for _ in date_list)
            where_clauses.append(f"shoot_date IN ({placeholders})")
            params.extend(date_list)

    if collection_id is not None:
        conn = get_db_connection(DEFAULT_DB_PATH)
        c_rows = conn.execute(
            "SELECT photo_id FROM collection_items WHERE collection_id = ? ORDER BY sort_order ASC, added_at ASC",
            (collection_id,),
        ).fetchall()
        conn.close()
        c_ids = [r["photo_id"] for r in c_rows if r["photo_id"]]
        if not c_ids:
            return {"total": 0, "page": page, "limit": limit, "aesthetic_cutoff": 0.0, "photos": []}
        ph_c = ",".join("?" for _ in c_ids)
        where_clauses.append(f"(file_hash IN ({ph_c}) OR file_path IN ({ph_c}))")
        params.extend(c_ids + c_ids)

    cached_rows, unique_catalog_tags = _get_cached_query_rows(" AND ".join(where_clauses), tuple(params))
    rows = list(cached_rows)

    if not rows:
        return {
            "total": 0,
            "page": page,
            "limit": limit,
            "aesthetic_cutoff": 0.0,
            "photos": [],
        }

    # Optional People & Pets entity_id filter
    if entity_id and entity_id.strip():
        eid_low = entity_id.strip().lower()
        rows = [
            r for r in rows
            if eid_low in r.get("_entity_tokens", []) or eid_low in r.get("_clean_tags_lower_set", set())
        ]

    # Optional trip_id filter
    if trip_id:
        if trip_id.startswith("portfolio_"):
            from stage2_vlm import PORTFOLIO_CATEGORIES_CONFIG
            slug_target = trip_id.replace("portfolio_", "").strip("_").lower()
            matched_cat_name = None
            for cfg in PORTFOLIO_CATEGORIES_CONFIG:
                c_name = cfg["category"]
                c_slug = re.sub(r"[^a-z0-9]+", "_", c_name.lower()).strip("_")
                if c_slug == slug_target or c_name.lower() == slug_target.replace("_", " "):
                    matched_cat_name = c_name
                    break
            if matched_cat_name:
                cat_hier = f"Portfolio|{matched_cat_name}"
                rows = [
                    r for r in rows
                    if cat_hier in _parse_json_list(r.get("hierarchical_keywords"))
                    or matched_cat_name in _parse_json_list(r.get("key_subjects"))
                ]
        else:
            trips_data = _build_trips_from_rows(rows)
            matching_trip = next((t for t in trips_data if t["trip_id"] == trip_id), None)
            if matching_trip:
                trip_hashes = set(matching_trip.get("file_hashes") or [])
                rows = [r for r in rows if r.get("file_hash") in trip_hashes]

    # Optional 4-digit year filter (applies across Portfolio Regions, Sub-Regions, Trips, and Grid)
    if year and str(year).strip() and str(year).strip().lower() not in ("all", "all years"):
        y_clean = str(year).strip()
        if y_clean.lower() == "undated":
            rows = [r for r in rows if not r.get("shoot_date") or r.get("shoot_date") == "Undated"]
        else:
            rows = [r for r in rows if str(r.get("shoot_date") or "").startswith(y_clean)]

    # Optional portfolio_theme filter (matches Portfolio|<theme> in hierarchical_keywords or exact/substring match in key_subjects / locations)
    if portfolio_theme and portfolio_theme.strip() and not (trip_id and trip_id.startswith("portfolio_")):
        pt_clean = portfolio_theme.strip()
        pt_low = pt_clean.lower()
        target_hier = f"portfolio|{pt_low}"
        exact_cat_rows = [
            r for r in rows
            if any(str(hk).lower() == target_hier for hk in _parse_json_list(r.get("hierarchical_keywords")))
            or any(str(k).lower() == pt_low for k in _parse_json_list(r.get("key_subjects")))
        ]
        if exact_cat_rows:
            rows = exact_cat_rows
        else:
            pt_rows = []
            for r in rows:
                hk_list = _parse_json_list(r.get("hierarchical_keywords"))
                ks_list = _parse_json_list(r.get("key_subjects"))
                loc_str = " ".join([
                    str(r.get("specific_location") or ""),
                    str(r.get("state_region") or ""),
                    str(r.get("country") or ""),
                ]).lower()
                if (
                    any(pt_low in str(hk).lower() for hk in hk_list)
                    or any(pt_low in str(k).lower() for k in ks_list)
                    or pt_low in loc_str
                ):
                    pt_rows.append(r)
            rows = pt_rows

    # 1. Systemic Search Engine: Sub-15ms Open-Vocabulary Multi-Crop + Verified Tag Hybrid Search
    if active_query:
        q_lower = active_query.lower()
        _QUERY_STOPWORDS = {"of", "the", "in", "at", "on", "to", "for", "and", "a", "an", "by", "from"}
        q_words = [w for w in re.split(r"[^a-z0-9]+", q_lower) if len(w) >= 2]
        q_words_meaningful = [w for w in q_words if w not in _QUERY_STOPWORDS]
        q_stems = [_stem_word(w) for w in q_words if len(w) >= 3]
        q_stems_meaningful = [_stem_word(w) for w in q_words_meaningful if len(w) >= 3]

        text_vec = encode_text_query(active_query)
        raw_q_vec = TEXT_EMBED_CACHE.get(active_query.strip())
        if raw_q_vec is None:
            raw_q_vec = TEXT_EMBED_CACHE.get(q_lower)
        if raw_q_vec is None:
            raw_q_vec = text_vec
        norm_vectors = get_normalized_vectors_matrix()
        norm_crop_vectors = get_normalized_crop_vectors_matrix()

        # Pre-compute image-vector cosine similarities across 1x global + 4 focal sub-crops in vectorized BLAS
        n_vecs = len(norm_vectors)
        if text_vec is not None and n_vecs > 0:
            global_sims = np.dot(norm_vectors, text_vec)
            if len(norm_crop_vectors) > 0:
                n_crops = min(n_vecs, len(norm_crop_vectors))
                crop_flat = norm_crop_vectors[:n_crops].reshape(-1, 768)
                max_crop_sims = np.max(np.dot(crop_flat, text_vec).reshape(n_crops, 4), axis=1)
                all_raw_sims = global_sims.copy()
                all_raw_sims[:n_crops] = np.maximum(global_sims[:n_crops], max_crop_sims * 0.985)
            else:
                all_raw_sims = global_sims
            global _BG_SIMS_ALL_CACHE, _BG_SIMS_ALL_LEN
            if BACKGROUND_BASELINE_VECS is not None and len(BACKGROUND_BASELINE_VECS) > 0:
                if globals().get("_BG_SIMS_ALL_CACHE") is None or globals().get("_BG_SIMS_ALL_LEN") != n_vecs:
                    _BG_SIMS_ALL_CACHE = np.max(np.dot(norm_vectors, BACKGROUND_BASELINE_VECS.T), axis=1)
                    _BG_SIMS_ALL_LEN = n_vecs
                bg_sims_all = _BG_SIMS_ALL_CACHE
            else:
                bg_sims_all = np.full(n_vecs, 0.22, dtype=np.float32)
        else:
            all_raw_sims = np.zeros(n_vecs, dtype=np.float32)
            bg_sims_all = np.zeros(n_vecs, dtype=np.float32)

        # Compute adaptive Z-score cosine floor across candidate rows to prevent low-confidence tail false positives
        cand_v_indices = [
            int(r["vector_index"])
            for r in rows
            if r.get("vector_index") is not None and 0 <= int(r["vector_index"]) < n_vecs
        ]
        if cand_v_indices and len(all_raw_sims) > 0:
            cand_sims = all_raw_sims[cand_v_indices]
            adaptive_z_cutoff = max(0.252, float(np.mean(cand_sims)) + 2.25 * float(np.std(cand_sims)))
        else:
            adaptive_z_cutoff = 0.255

        tag_sim_lookup: Dict[str, float] = {}
        if raw_q_vec is not None and unique_catalog_tags:
            for t_str in unique_catalog_tags:
                t_vec = TEXT_EMBED_CACHE.get(t_str)
                if t_vec is not None:
                    tag_sim_lookup[t_str] = float(np.dot(raw_q_vec, t_vec))

        scored_candidates: List[Tuple[int, float, Dict[str, Any]]] = []
        countable_query_groups = _extract_countable_query_targets(active_query)

        for r in rows:
            # High-Trust Search Gate: when searching for countable subjects (birds, frogs, dogs, boats, people, etc.),
            # strictly require positive verified subject presence and never pad with habitat/vector similarity matches.
            if countable_query_groups and not _passes_countable_subject_search_gate(r, countable_query_groups):
                continue

            ctags = r.get("_clean_tags") or []
            ctags_lower_set = r.get("_clean_tags_lower_set") or set()
            v_idx = r.get("vector_index")
            raw_clip_sim = 0.0
            bg_clip_sim = 0.22
            if v_idx is not None and 0 <= int(v_idx) < n_vecs:
                raw_clip_sim = float(all_raw_sims[int(v_idx)])
                bg_clip_sim = float(bg_sims_all[int(v_idx)])

            contrastive_margin = raw_clip_sim - bg_clip_sim

            corpus_tokens_str = r.get("_corpus_tokens_str") or ""
            corpus_words = r.get("_corpus_words") or []
            corpus_stems = r.get("_corpus_stems") or set()

            lexical_score = 0.0
            if q_lower in corpus_tokens_str:
                if len(q_words_meaningful) >= 2:
                    lexical_score = 1.0
                elif any(w == q_lower or w.startswith(q_lower) or _stem_word(w) in q_stems for w in corpus_words):
                    lexical_score = 1.0
                elif len(q_lower) >= 4:
                    lexical_score = 0.80
            elif q_stems_meaningful and all(qs in corpus_stems for qs in q_stems_meaningful):
                lexical_score = 0.85

            # Check parent-category / hypernym ontological expansion match (single-concept queries or full phrase)
            has_hypernym_match = False
            hyp_candidates = [q_lower] if len(q_words_meaningful) >= 2 else ([q_lower] + q_words_meaningful)
            for qw in hyp_candidates:
                hyp_targets = _QUERY_HYPERNYM_MAP.get(qw)
                if hyp_targets and (ctags_lower_set & hyp_targets):
                    has_hypernym_match = True
                    lexical_score = max(lexical_score, 0.92)
                    break

            # Semantic tag-to-query similarity across the photo's non-boilerplate tags
            max_tag_clip_sim = 0.0
            if ctags_lower_set and tag_sim_lookup:
                max_tag_clip_sim = max(
                    (tag_sim_lookup.get(tl, 0.0) for tl in ctags_lower_set),
                    default=0.0,
                )

            # Tag-Coherence Gating:
            # Never penalize when the query is a parent/hypernym concept or when max_tag_clip_sim >= 0.72.
            gated_clip_sim = raw_clip_sim
            if not has_hypernym_match and len(ctags) >= 3 and lexical_score == 0.0 and max_tag_clip_sim < 0.72 and raw_clip_sim < adaptive_z_cutoff + 0.025:
                gated_clip_sim = raw_clip_sim * 0.50

            # Tiered Ranking & Strict Cutoff (boost parent-concept & high tag-coherence matches)
            tier = 0
            rank_score = 0.0
            if lexical_score >= 0.50 or has_hypernym_match:
                # Tier 3: Exact/prefix/stem/parent-hypernym match in curated/VLM/ontology/entity tags or location
                tier = 3
                rank_score = 3.0 + lexical_score + (0.15 if has_hypernym_match else 0.0) + raw_clip_sim
            elif max_tag_clip_sim >= 0.80 and (raw_clip_sim >= 0.215 or contrastive_margin >= 0.0):
                # Tier 2: High semantic tag-confirmed match (>= 0.80) + positive visual support
                tier = 2
                rank_score = 2.0 + max_tag_clip_sim * 0.6 + raw_clip_sim
            elif gated_clip_sim >= adaptive_z_cutoff and contrastive_margin >= 0.018:
                # Tier 1: High-margin contrastive visual match (passes adaptive Z-score floor AND beats background baseline)
                tier = 1
                rank_score = 1.0 + gated_clip_sim + contrastive_margin

            if tier > 0:
                scored_candidates.append((tier, round(rank_score, 4), r))

        # If query is a known geographic place in OFFLINE_GAZETTEER and has exact Tier 3 matches,
        # do not dilute with Tier 1/2 OpenCLIP neighboring-country/state tag similarity matches.
        if q_lower in OFFLINE_GAZETTEER and any(c[0] == 3 for c in scored_candidates):
            scored_candidates = [c for c in scored_candidates if c[0] == 3]

        scored_candidates.sort(key=lambda x: (x[0], x[1], float(x[2].get("aesthetic_score") or 0.0)), reverse=True)
        filtered_rows = [item[2] for item in scored_candidates]
        if norm_sort_by != "capture_desc":
            filtered_rows = _apply_sort_by(filtered_rows, norm_sort_by, has_active_query=True)
    else:
        filtered_rows = _apply_sort_by(rows, norm_sort_by, has_active_query=False)

    # 2. Dynamic Aesthetic Percentile Cutoff (within CURRENT filtered result set)
    aesthetic_cutoff = 0.0
    if effective_percentile in ("top25", "top10", "top5") and filtered_rows:
        scores = [float(r.get("aesthetic_score") or 0.0) for r in filtered_rows if r.get("aesthetic_score") is not None]
        if scores:
            pct_map = {"top25": 75.0, "top10": 90.0, "top5": 95.0}
            target_pct = pct_map[effective_percentile]
            aesthetic_cutoff = float(np.percentile(scores, target_pct))
            filtered_rows = [r for r in filtered_rows if float(r.get("aesthetic_score") or 0.0) >= aesthetic_cutoff]
            if not active_query and norm_sort_by == "capture_desc":
                filtered_rows.sort(key=lambda r: float(r.get("aesthetic_score") or 0.0), reverse=True)

    # 3. Collapse Strafing Runs into Hero Cards (if enabled)
    if effective_collapse:
        collapsed_list = []
        seen_sequences = set()

        for r in filtered_rows:
            seq_id = r.get("sequence_id")
            seq_len = r.get("sequence_length") or 1
            if seq_id and seq_len > 1:
                if seq_id in seen_sequences:
                    continue
                seen_sequences.add(seq_id)
                collapsed_list.append(r)
            else:
                collapsed_list.append(r)
        final_list = collapsed_list
    else:
        final_list = filtered_rows

    total_matches = len(final_list)

    # 4. Pagination (supports both offset and page)
    start_idx = offset if offset is not None else (page - 1) * limit
    end_idx = start_idx + limit
    page_items = [dict(r) for r in final_list[start_idx:end_idx]]

    if ids_only:
        stub_items = [
            {
                "file_hash": r.get("file_hash") or r.get("file_path"),
                "file_path": r.get("file_path"),
                "catalog_name": r.get("catalog_name"),
                "title": r.get("title") or Path(str(r.get("file_path") or "")).stem,
            }
            for r in page_items
        ]
        return {
            "total": total_matches,
            "offset": start_idx,
            "page": page,
            "limit": limit,
            "ids_only": True,
            "photos": stub_items,
        }

    for item in page_items:
        for internal_k in ("_clean_tags", "_clean_tags_lower_set", "_corpus_tokens_str", "_corpus_words", "_corpus_stems", "_all_verified_countable", "_entity_tokens"):
            item.pop(internal_k, None)
        _serialize_photo_item(item)

    return {
        "total": total_matches,
        "offset": start_idx,
        "page": page,
        "limit": limit,
        "aesthetic_cutoff": round(aesthetic_cutoff, 2),
        "photos": page_items,
    }


# ==============================================================================
# 2A. PEOPLE & PETS IDENTITY CLUSTERS & INLINE RENAMING ("Masha", "Scout", etc.)
# ==============================================================================
class EntityRenameRequest(BaseModel):
    entity_name: str


@app.get("/api/entities")
def list_entity_clusters(
    catalog: str = Query("All Catalogs", description="Filter by catalog_name or 'All Catalogs'"),
):
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    cat_clean = (catalog or "").strip()
    if cat_clean and cat_clean.lower() not in ("all catalogs", "all", "all photos"):
        target_cat = "Keepers" if cat_clean.lower() == "keepers" else cat_clean
        rows = cursor.execute(
            """
            SELECT ec.entity_id, ec.catalog_name, ec.entity_type, ec.entity_name,
                   ec.auto_breed, ec.photo_count, ec.cover_file_hash, ec.sample_file_hash, ec.updated_at,
                   pr.thumb_360_path, pr.file_path
            FROM entity_clusters ec
            LEFT JOIN photo_records pr ON COALESCE(NULLIF(ec.cover_file_hash, ''), ec.sample_file_hash) = pr.file_hash
            WHERE ec.catalog_name = ?
            ORDER BY
                CASE WHEN ec.entity_name IS NOT NULL AND ec.entity_name != '' THEN 0 ELSE 1 END,
                CASE WHEN ec.entity_type IN ('Cat', 'Dog', 'pet_cat', 'pet_dog') THEN 0 ELSE 1 END,
                ec.photo_count DESC
            """,
            (target_cat,),
        ).fetchall()
    else:
        rows = cursor.execute(
            """
            SELECT ec.entity_id, ec.catalog_name, ec.entity_type, ec.entity_name,
                   ec.auto_breed, ec.photo_count, ec.cover_file_hash, ec.sample_file_hash, ec.updated_at,
                   pr.thumb_360_path, pr.file_path
            FROM entity_clusters ec
            LEFT JOIN photo_records pr ON COALESCE(NULLIF(ec.cover_file_hash, ''), ec.sample_file_hash) = pr.file_hash
            ORDER BY
                CASE WHEN ec.entity_name IS NOT NULL AND ec.entity_name != '' THEN 0 ELSE 1 END,
                CASE WHEN ec.entity_type IN ('Cat', 'Dog', 'pet_cat', 'pet_dog') THEN 0 ELSE 1 END,
                ec.photo_count DESC
            """
        ).fetchall()
    conn.close()

    type_map = {"pet_cat": "Cat", "pet_dog": "Dog", "person": "Person"}
    entities = []
    conn_pe = get_db_connection(DEFAULT_DB_PATH)
    cursor_pe = conn_pe.cursor()

    for r in rows:
        d = dict(r)
        raw_t = str(d.get("entity_type") or "")
        d["entity_type"] = type_map.get(raw_t, raw_t or "Pet")
        
        cover_hash = str(d.get("cover_file_hash") or d.get("sample_file_hash") or "").strip()
        if not cover_hash:
            ent_id = d.get("entity_id")
            pe_row = cursor_pe.execute(
                "SELECT photo_id, file_hash FROM photo_entities WHERE entity_id = ? ORDER BY similarity DESC, rowid ASC LIMIT 1",
                (ent_id,),
            ).fetchone()
            if pe_row:
                cover_hash = str(pe_row["file_hash"] or pe_row["photo_id"] or "").strip()
        
        d["cover_photo_id"] = cover_hash
        d["thumb_url"] = f"/api/thumbnail/{cover_hash}" if cover_hash else None
        entities.append(d)

    conn_pe.close()
    return {"total": len(entities), "entities": entities}


@app.post("/api/entities/{entity_id}/rename")
def api_rename_entity_cluster(entity_id: str, req: EntityRenameRequest):
    result = rename_entity_cluster(
        db_path=DEFAULT_DB_PATH,
        entity_id=entity_id,
        new_name=req.entity_name,
    )
    invalidate_search_index_cache()
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "Entity cluster not found"))
    return result


# ==============================================================================
# 2B. AUTO-CLUSTERED TRIPS (1–2 DAY CAPTURE BOUND + SUBJECT & VISUAL COHERENCE)
# ==============================================================================
_GENERIC_SERIES_PREFIXES = {
    "img", "dsc", "dscf", "dscn", "dji", "cf", "l", "p", "print", "edit",
    "copy", "final", "pano", "stitch", "hdr", "tif", "raw", "untitled",
    "mg", "crw", "nef", "arw",
}


def _parse_shoot_date_obj(d_str: Optional[str]) -> Optional[datetime]:
    if not d_str or d_str == "Undated":
        return None
    try:
        return datetime.strptime(str(d_str)[:10], "%Y-%m-%d")
    except Exception:
        return None


def _format_date_range(start_date: str, end_date: str) -> str:
    dt1 = _parse_shoot_date_obj(start_date)
    dt2 = _parse_shoot_date_obj(end_date)
    if not dt1:
        return start_date
    if not dt2 or start_date == end_date:
        return dt1.strftime("%b %-d, %Y")
    if dt1.year == dt2.year and dt1.month == dt2.month:
        return f"{dt1.strftime('%b %-d')}–{dt2.strftime('%-d, %Y')}"
    if dt1.year == dt2.year:
        return f"{dt1.strftime('%b %-d')} – {dt2.strftime('%b %-d, %Y')}"
    return f"{dt1.strftime('%b %-d, %Y')} – {dt2.strftime('%b %-d, %Y')}"


def _extract_series_prefix(file_path: Optional[str]) -> Optional[str]:
    stem = Path(file_path or "").stem
    s = re.sub(r"^\d{4}_\d{2}_\d{2}\s*-\s*", "", stem)
    s = re.sub(r"^\d{8}[-_]\s*", "", s)
    s = re.sub(r"^\d{1,2}-\d{1,2}-\d{2}_+", "", s)
    m = re.match(r"^([A-Za-z][A-Za-z\s]{2,24}?)[-_0-9]", s)
    if m:
        tok = re.sub(r"\s+", "", m.group(1)).lower()
        if tok not in _GENERIC_SERIES_PREFIXES and len(tok) >= 3:
            return tok
    return None


def _extract_trip_coherent_features(r: Dict[str, Any]) -> Tuple[Set[str], Set[str], Dict[str, str]]:
    """
    Returns (explicit_places, subject_tags, canonical_display_map) for a photo record.
    """
    explicit_places: Set[str] = set()
    subject_tags: Set[str] = set()
    display_map: Dict[str, str] = {}

    for col in ("lrcat_keywords", "existing_keywords"):
        for t in _parse_json_list(r.get(col)):
            t_clean = t.strip()
            if t_clean and not _is_boilerplate_tag(t_clean) and len(t_clean) > 2:
                k = t_clean.lower()
                explicit_places.add(k)
                display_map[k] = t_clean

    for col in ("specific_location", "sub_location", "city", "state_region"):
        val = str(r.get(col) or "").strip()
        if val and val.lower() not in ("unknown", "none", "null") and not _is_boilerplate_tag(val) and len(val) > 2:
            k = val.lower()
            explicit_places.add(k)
            display_map.setdefault(k, val)

    for h in _parse_json_list(r.get("hierarchical_keywords")):
        parts = [
            p.strip().replace("_", " ")
            for p in str(h).split("|")
            if p.strip() and not _is_boilerplate_tag(p)
        ]
        if len(parts) >= 2:
            root = parts[0].lower()
            leaf = parts[-1]
            k = leaf.lower()
            if root == "places" and k != "united states":
                explicit_places.add(k)
                display_map.setdefault(k, leaf.title() if leaf.islower() else leaf)
            elif root in ("landscape", "aerial", "water", "architecture", "agriculture"):
                subject_tags.add(k)
                display_map.setdefault(k, leaf.title())

    for s in _parse_json_list(r.get("key_subjects")):
        s_clean = s.strip().replace("_", " ")
        if s_clean and not _is_boilerplate_tag(s_clean) and len(s_clean) > 2:
            k = s_clean.lower()
            subject_tags.add(k)
            display_map.setdefault(k, s_clean.title())

    return explicit_places, subject_tags, display_map


def _are_trip_photos_coherent(
    r1: Dict[str, Any],
    r2: Dict[str, Any],
    norm_vectors: np.ndarray,
) -> bool:
    """
    Determines if two photos within a 1–2 day shoot window belong to the same coherent shoot/trip.
    Splits unrelated shoots even on the same day if their explicit locations/series conflict
    or their visual & subject coherence is low.
    """
    p1, s1, _ = _extract_trip_coherent_features(r1)
    p2, s2, _ = _extract_trip_coherent_features(r2)
    pref1 = _extract_series_prefix(r1.get("file_path"))
    pref2 = _extract_series_prefix(r2.get("file_path"))

    # 1. If both have non-generic filename series prefixes:
    if pref1 and pref2:
        if pref1 == pref2:
            return True
        if not (p1 & p2):
            return False

    # 2. If both have explicit location/curated tags and they are completely disjoint, split them
    if p1 and p2:
        if p1 & p2:
            return True
        return False

    # 3. Compute OpenCLIP visual cosine similarity
    v1 = r1.get("vector_index")
    v2 = r2.get("vector_index")
    n_vecs = len(norm_vectors)
    vis_sim = 0.0
    if v1 is not None and v2 is not None and 0 <= int(v1) < n_vecs and 0 <= int(v2) < n_vecs:
        vis_sim = float(np.dot(norm_vectors[int(v1)], norm_vectors[int(v2)]))

    # 4. Shared VLM subject tags + visual support
    shared_subj = s1 & s2
    if len(shared_subj) >= 2 and vis_sim >= 0.52:
        return True
    if len(shared_subj) >= 1 and vis_sim >= 0.60:
        return True

    # 5. Pure visual similarity threshold (same shoot environment/subject)
    if vis_sim >= 0.66:
        return True

    return False


def _split_window_into_coherent_subclusters(
    window_rows: List[Dict[str, Any]],
    norm_vectors: np.ndarray,
) -> List[List[Dict[str, Any]]]:
    """
    Connected-components / greedy average-linkage clustering within a 1–2 day shoot window.
    """
    ordered = sorted(
        window_rows,
        key=lambda r: (r.get("shoot_date") or "", r.get("exif_time") or "", r.get("file_path") or ""),
    )
    subclusters: List[List[Dict[str, Any]]] = []
    for r in ordered:
        placed = False
        for sc in subclusters:
            # Must not conflict with explicit places/prefixes in sc, and must match at least one member
            # while maintaining visual/subject coherence with the sub-cluster
            if any(_are_trip_photos_coherent(r, member, norm_vectors) for member in sc):
                # Also verify no hard location/prefix conflict with the first member of sc
                p_r, _, _ = _extract_trip_coherent_features(r)
                p_0, _, _ = _extract_trip_coherent_features(sc[0])
                pref_r = _extract_series_prefix(r.get("file_path"))
                pref_0 = _extract_series_prefix(sc[0].get("file_path"))
                if pref_r and pref_0 and pref_r != pref_0 and not (p_r & p_0):
                    continue
                if p_r and p_0 and not (p_r & p_0):
                    continue
                sc.append(r)
                placed = True
                break
        if not placed:
            subclusters.append([r])
    return subclusters


def _synthesize_coherent_trip_title(
    cluster_rows: List[Dict[str, Any]],
    start_date: str,
    end_date: str,
) -> Tuple[str, str, List[str]]:
    """
    Names a Trip cleanly using the shared high-frequency location/subject tag that appears
    on >= 50% of photos in the cluster, or falls back to '{Date Range} Shoot'.
    Returns (trip_name, location_summary, top_subjects).
    """
    n_photos = len(cluster_rows)
    majority_threshold = max(2, int(np.ceil(n_photos * 0.50)))

    place_doc_freq: Counter = Counter()
    subj_doc_freq: Counter = Counter()
    display_lookup: Dict[str, str] = {}

    for r in cluster_rows:
        places, subjs, dmap = _extract_trip_coherent_features(r)
        display_lookup.update(dmap)
        for p in places:
            place_doc_freq[p] += 1
        for s in subjs:
            subj_doc_freq[s] += 1

    majority_places = [
        display_lookup[k]
        for k, cnt in place_doc_freq.most_common()
        if cnt >= majority_threshold
    ]
    majority_subjects = [
        display_lookup[k]
        for k, cnt in subj_doc_freq.most_common()
        if cnt >= majority_threshold
    ]

    date_label = _format_date_range(start_date, end_date)

    if majority_places:
        primary_place = majority_places[0]
        secondary_subj = next(
            (s for s in majority_subjects if s.lower() not in primary_place.lower()),
            None,
        )
        trip_name = f"{primary_place} · {secondary_subj}" if secondary_subj else primary_place
        location_summary = ", ".join(majority_places[:2])
    elif majority_subjects:
        primary_subj = majority_subjects[0]
        second_subj = majority_subjects[1] if len(majority_subjects) > 1 else None
        trip_name = f"{primary_subj} & {second_subj}" if second_subj else primary_subj
        location_summary = f"{date_label} Shoot"
    else:
        trip_name = f"{date_label} Shoot"
        location_summary = "Field & Aerial Session"

    # Top shared subjects/tags for pill badges (excluding terms already in trip_name)
    combined_counter: Counter = Counter()
    for k, cnt in place_doc_freq.items():
        combined_counter[display_lookup[k]] += cnt * 2
    for k, cnt in subj_doc_freq.items():
        combined_counter[display_lookup[k]] += cnt

    top_subjects: List[str] = []
    for label, _ in combined_counter.most_common(8):
        if label.lower() not in trip_name.lower() and label not in top_subjects:
            top_subjects.append(label)
        if len(top_subjects) >= 4:
            break

    return trip_name, location_summary, top_subjects


def _extract_day_macro_signature(day_rows: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    """
    Returns (countries, states, portfolio_cats, cameras) for a capture date so multi-day expeditions
    in the same region/country (up to 14 days total span, <= 7 days gap) consolidate into one Trip.
    """
    countries: Set[str] = set()
    states: Set[str] = set()
    port_cats: Set[str] = set()
    cameras: Set[str] = set()

    for r in day_rows:
        ctry = str(r.get("country") or "").strip()
        if ctry and ctry != "Unknown":
            countries.add(ctry.lower())
        st = str(r.get("state_region") or "").strip()
        if st and st.lower() not in ("unknown", "general"):
            states.add(st.lower())
        cam = str(r.get("camera_model") or "").strip()
        if cam:
            cameras.add(cam.lower())
        for hk in _parse_json_list(r.get("hierarchical_keywords")):
            if str(hk).startswith("Portfolio|"):
                port_cats.add(str(hk).split("|", 1)[1].lower())

    return countries, states, port_cats, cameras


def _build_trips_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Multi-Day Expedition & Coherent Trip Clustering:
    - Excludes 'Undated' photos from automatic Trip generation.
    - Consolidates consecutive or nearby capture dates (up to 14 days total span, allowing gaps of up to 7 days)
      into a single unified expedition window whenever the days share the same Country (for non-US trips like Iceland),
      the same US State / Macro-Region, or strong Portfolio Category + Camera continuity.
    - Splits composite print-export dates or unrelated same-day shoots into coherent sub-clusters.
    - Surfaces clusters with >= 2 coherent photos as Trips.
    """
    COMPOSITE_EXPORT_DATES = {"2011-12-09", "2011-12-15", "2012-03-16"}
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        sd = str(r.get("shoot_date") or "Undated")
        if _parse_shoot_date_obj(sd) is not None:
            by_date.setdefault(sd, []).append(r)

    dated_keys = sorted(by_date.keys())
    if not dated_keys:
        return []

    # 1. Group capture dates into consolidated multi-day expedition windows (up to 14 days span, <= 7 days gap)
    date_windows: List[List[str]] = []
    for d_key in dated_keys:
        dt = _parse_shoot_date_obj(d_key)
        if not date_windows:
            date_windows.append([d_key])
            continue

        prev_key = date_windows[-1][-1]
        first_key = date_windows[-1][0]
        prev_dt = _parse_shoot_date_obj(prev_key)
        first_dt = _parse_shoot_date_obj(first_key)

        if not (dt and prev_dt and first_dt):
            date_windows.append([d_key])
            continue

        gap_days = (dt - prev_dt).days
        span_days = (dt - first_dt).days

        # Never merge composite print-export dates with neighboring dates
        if d_key in COMPOSITE_EXPORT_DATES or prev_key in COMPOSITE_EXPORT_DATES:
            date_windows.append([d_key])
            continue

        should_merge = False
        win_rows = [r for k in date_windows[-1] for r in by_date[k]]
        day_rows = by_date[d_key]
        c1, s1, p1, cam1 = _extract_day_macro_signature(win_rows)
        c2, s2, p2, cam2 = _extract_day_macro_signature(day_rows)
        non_us_1 = {c for c in c1 if c != "united states"}
        non_us_2 = {c for c in c2 if c != "united states"}

        if gap_days <= 1 and span_days <= 3:
            should_merge = True
        elif gap_days <= 7 and span_days <= 14:
            if non_us_1 and non_us_2 and (non_us_1 & non_us_2):
                # Same international expedition (e.g. June 10-17, 2016 Iceland)
                should_merge = True
            elif not non_us_1 and not non_us_2:
                # Both US: merge if they share the same state_region, or adjacent Southwest states (AZ/UT), or same portfolio theme + camera
                sw_states = {"utah", "arizona"}
                if (s1 & s2) or ((s1 <= sw_states and s2 <= sw_states) and (s1 and s2)):
                    should_merge = True
                elif (p1 & p2) and (cam1 & cam2) and gap_days <= 4:
                    should_merge = True
        # Coalesce tiny 1-3 photo shoots into adjacent expedition windows (up to 14 days gap) when countries/states do not conflict
        if not should_merge and gap_days <= 14 and span_days <= 21 and (len(day_rows) <= 3 or len(win_rows) <= 3):
            country_conflict = bool(non_us_1 and non_us_2 and not (non_us_1 & non_us_2)) or bool(non_us_1 ^ non_us_2)
            state_conflict = bool(s1 and s2 and not (s1 & s2))
            if not country_conflict and not state_conflict and ((p1 & p2) or (cam1 & cam2) or (s1 & s2) or (non_us_1 & non_us_2)):
                should_merge = True

        if should_merge:
            date_windows[-1].append(d_key)
        else:
            date_windows.append([d_key])

    norm_vectors = get_normalized_vectors_matrix()
    trips_out: List[Dict[str, Any]] = []

    for w_dates in date_windows:
        window_rows: List[Dict[str, Any]] = []
        for d_key in w_dates:
            window_rows.extend(by_date[d_key])

        # If this is a multi-day consolidated expedition (and not a composite export date), keep coherent expedition together
        is_multi_day_expedition = len(w_dates) >= 2 and not any(d in COMPOSITE_EXPORT_DATES for d in w_dates)
        if is_multi_day_expedition:
            subclusters = [window_rows]
        else:
            raw_subclusters = _split_window_into_coherent_subclusters(window_rows, norm_vectors)
            # Coalesce tiny 1-3 frame subclusters on the same day into the primary subcluster unless explicit country/state conflicts
            if len(raw_subclusters) > 1 and not any(d in COMPOSITE_EXPORT_DATES for d in w_dates):
                raw_subclusters.sort(key=len, reverse=True)
                primary_sc = list(raw_subclusters[0])
                c_main, s_main, _, _ = _extract_day_macro_signature(primary_sc)
                remaining_scs: List[List[Dict[str, Any]]] = []
                for sc in raw_subclusters[1:]:
                    c_sc, s_sc, _, _ = _extract_day_macro_signature(sc)
                    has_conflict = bool(c_main and c_sc and not (c_main & c_sc)) or bool(s_main and s_sc and not (s_main & s_sc))
                    if len(sc) <= 3 and not has_conflict:
                        primary_sc.extend(sc)
                    else:
                        remaining_scs.append(sc)
                subclusters = [primary_sc] + remaining_scs
            else:
                subclusters = raw_subclusters

        # Require >= 4 photos for standalone subclusters (or >= 3 if multi-day), avoiding tiny 2-3 photo trip fragments
        valid_subclusters = [sc for sc in subclusters if len(sc) >= 4]

        for sub_idx, sc_rows in enumerate(valid_subclusters):
            sc_dates = sorted({str(r.get("shoot_date")) for r in sc_rows if r.get("shoot_date")})
            start_d = sc_dates[0]
            end_d = sc_dates[-1]

            trip_title, location_summary, top_subjects = _synthesize_coherent_trip_title(
                sc_rows, start_d, end_d
            )

            # Unique camera models used in this trip
            cameras: List[str] = []
            for r in sc_rows:
                cam = str(r.get("camera_model") or "").strip()
                if cam and cam not in cameras:
                    cameras.append(cam)

            # Pick Hero Cover Photo (highest aesthetic_score) and up to 4 sample photos
            sorted_by_aes = sorted(
                sc_rows,
                key=lambda x: (int(x.get("is_sequence_hero") or 0), float(x.get("aesthetic_score") or 0.0)),
                reverse=True,
            )
            hero_rec = dict(sorted_by_aes[0])
            _serialize_photo_item(hero_rec)

            sample_thumbs = []
            for sr in sorted_by_aes[:4]:
                tp = sr.get("thumb_360_path")
                if tp:
                    sample_thumbs.append(f"/previews/thumbs_360/{Path(tp).name}")

            year_counts: Dict[str, int] = {}
            for r in sc_rows:
                sd = str(r.get("shoot_date") or "")
                if len(sd) >= 4 and sd[:4].isdigit():
                    yr = sd[:4]
                    year_counts[yr] = year_counts.get(yr, 0) + 1

            max_aes = round(max((float(r.get("aesthetic_score") or 0.0) for r in sc_rows), default=0.0), 4)
            max_stars = max((int(r.get("star_rating") or 0) for r in sc_rows), default=0)
            max_sharp = round(max((float(r.get("sharpness_score") or 0.0) for r in sc_rows), default=0.0), 2)

            trip_id = f"trip_{start_d}_{end_d}_s{sub_idx}"
            trips_out.append({
                "trip_id": trip_id,
                "trip_name": trip_title,
                "date_range_label": _format_date_range(start_d, end_d),
                "start_date": start_d,
                "end_date": end_d,
                "shoot_dates": sc_dates,
                "years": sorted(year_counts.keys(), reverse=True),
                "year_counts": year_counts,
                "photo_count": len(sc_rows),
                "keeper_count": sum(1 for r in sc_rows if r.get("in_keepers") or (r.get("star_rating") or 0) >= 4),
                "max_aesthetic_score": max_aes,
                "max_star_rating": max_stars,
                "max_sharpness_score": max_sharp,
                "location_name": location_summary,
                "cameras": cameras,
                "top_subjects": top_subjects,
                "hero_photo": hero_rec,
                "sample_thumbs": sample_thumbs,
                "file_hashes": [r.get("file_hash") for r in sc_rows if r.get("file_hash")],
            })

    # Sort trips newest-first by default
    trips_out.sort(
        key=lambda t: (t["start_date"], t["photo_count"]),
        reverse=True,
    )
    return trips_out


def _compute_portfolio_theme_slice(cfg: Dict[str, Any], cat_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    sub_counts: List[Dict[str, Any]] = []
    for sub_label in cfg.get("sub_regions", []):
        sub_low = sub_label.lower()
        cnt = 0
        for r in cat_rows:
            ks_low = [str(k).lower() for k in _parse_json_list(r.get("key_subjects"))]
            spec_low = str(r.get("specific_location") or "").lower()
            st_low = str(r.get("state_region") or "").lower()
            if any(sub_low == k or sub_low in k for k in ks_low) or sub_low in spec_low or sub_low == st_low:
                cnt += 1
        if cnt > 0:
            sub_counts.append({"name": sub_label, "count": cnt})

    sub_counts.sort(key=lambda x: x["count"], reverse=True)

    sorted_by_aes = sorted(
        cat_rows,
        key=lambda x: (int(x.get("is_sequence_hero") or 0), float(x.get("aesthetic_score") or 0.0)),
        reverse=True,
    )
    hero_rec = dict(sorted_by_aes[0])
    _serialize_photo_item(hero_rec)

    sample_thumbs = []
    for sr in sorted_by_aes[:4]:
        tp = sr.get("thumb_360_path")
        if tp:
            sample_thumbs.append(f"/previews/thumbs_360/{Path(tp).name}")

    cameras: List[str] = []
    for r in cat_rows:
        cam = str(r.get("camera_model") or "").strip()
        if cam and cam not in cameras:
            cameras.append(cam)

    sc_dates = sorted({str(r.get("shoot_date")) for r in cat_rows if r.get("shoot_date") and r.get("shoot_date") != "Undated"})
    max_aes = round(max((float(r.get("aesthetic_score") or 0.0) for r in cat_rows), default=0.0), 4)
    max_stars = max((int(r.get("star_rating") or 0) for r in cat_rows), default=0)
    max_sharp = round(max((float(r.get("sharpness_score") or 0.0) for r in cat_rows), default=0.0), 2)

    return {
        "date_range_label": f"{len(sc_dates)} Shoot Days" if sc_dates else "Archival Portfolio",
        "start_date": sc_dates[0] if sc_dates else "Undated",
        "end_date": sc_dates[-1] if sc_dates else "Undated",
        "shoot_dates": sc_dates,
        "photo_count": len(cat_rows),
        "keeper_count": sum(1 for r in cat_rows if r.get("in_keepers") or (r.get("star_rating") or 0) >= 4),
        "max_aesthetic_score": max_aes,
        "max_star_rating": max_stars,
        "max_sharpness_score": max_sharp,
        "cameras": cameras[:4],
        "top_subjects": [sc["name"] for sc in sub_counts[:6]],
        "sub_regions": sub_counts,
        "hero_photo": hero_rec,
        "sample_thumbs": sample_thumbs,
    }


def _build_portfolio_themes_from_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Builds the 10,000-Foot Portfolio Regions & Themes cards across all catalog rows,
    including sub-region pill counts, hero cover photo, sample thumbnails, shoot dates,
    and per-year breakdown so Year pills work seamlessly across Portfolio Regions.
    """
    from stage2_vlm import PORTFOLIO_CATEGORIES_CONFIG

    themes_out: List[Dict[str, Any]] = []
    for cfg in PORTFOLIO_CATEGORIES_CONFIG:
        cat_name = cfg["category"]
        cat_hier = f"Portfolio|{cat_name}"
        cat_rows: List[Dict[str, Any]] = []

        for r in rows:
            hk_list = _parse_json_list(r.get("hierarchical_keywords"))
            ks_list = _parse_json_list(r.get("key_subjects"))
            if cat_hier in hk_list or cat_name in ks_list:
                cat_rows.append(r)

        if not cat_rows:
            continue

        base_slice = _compute_portfolio_theme_slice(cfg, cat_rows)
        rows_by_year: Dict[str, List[Dict[str, Any]]] = {}
        for r in cat_rows:
            sd = str(r.get("shoot_date") or "")
            yr = sd[:4] if (len(sd) >= 4 and sd[:4].isdigit()) else "Undated"
            rows_by_year.setdefault(yr, []).append(r)

        year_counts = {yr: len(rlist) for yr, rlist in rows_by_year.items()}
        year_breakdown = {
            yr: _compute_portfolio_theme_slice(cfg, rlist)
            for yr, rlist in rows_by_year.items()
            if rlist
        }

        slug = re.sub(r"[^a-z0-9]+", "_", cat_name.lower()).strip("_")

        themes_out.append({
            "trip_id": f"portfolio_{slug}",
            "is_portfolio_theme": True,
            "category": cat_name,
            "portfolio_category": cat_name,
            "icon": cfg.get("icon", "🏔️"),
            "trip_name": f"{cfg.get('icon', '🏔️')} {cat_name}",
            "description": cfg.get("description", ""),
            "location_name": cfg.get("description", ""),
            "years": sorted([y for y in year_counts.keys() if y != "Undated"], reverse=True),
            "year_counts": year_counts,
            "year_breakdown": year_breakdown,
            "file_hashes": [r.get("file_hash") for r in cat_rows if r.get("file_hash")],
            **base_slice,
        })

    themes_out.sort(key=lambda t: t["photo_count"], reverse=True)
    return themes_out


def _sort_trip_or_theme_cards(
    cards: List[Dict[str, Any]],
    sort_by: str,
    is_portfolio: bool = False,
) -> List[Dict[str, Any]]:
    norm = (sort_by or "capture_desc").strip().lower()
    if norm in ("date_desc", "capture_desc"):
        if is_portfolio:
            return sorted(cards, key=lambda c: (c.get("photo_count") or 0, c.get("end_date") or ""), reverse=True)
        return sorted(
            cards,
            key=lambda c: (
                0 if (not c.get("start_date") or c.get("start_date") == "Undated") else 1,
                c.get("start_date") or "",
                c.get("photo_count") or 0,
            ),
            reverse=True,
        )
    if norm in ("date_asc", "capture_asc"):
        return sorted(
            cards,
            key=lambda c: (
                1 if (not c.get("start_date") or c.get("start_date") == "Undated") else 0,
                c.get("start_date") or "9999-99-99",
                -(c.get("photo_count") or 0),
            ),
        )
    if norm == "aesthetic_desc":
        return sorted(
            cards,
            key=lambda c: (
                float(c.get("max_aesthetic_score") or c.get("hero_photo", {}).get("aesthetic_score") or 0.0),
                int(c.get("photo_count") or 0),
            ),
            reverse=True,
        )
    if norm == "stars_desc":
        return sorted(
            cards,
            key=lambda c: (
                int(c.get("max_star_rating") or c.get("hero_photo", {}).get("star_rating") or 0),
                int(c.get("keeper_count") or 0),
                float(c.get("max_aesthetic_score") or 0.0),
            ),
            reverse=True,
        )
    if norm == "sharpness_desc":
        return sorted(
            cards,
            key=lambda c: (
                float(c.get("max_sharpness_score") or c.get("hero_photo", {}).get("sharpness_score") or 0.0),
                float(c.get("max_aesthetic_score") or 0.0),
            ),
            reverse=True,
        )
    if norm == "filename_asc":
        return sorted(
            cards,
            key=lambda c: str(c.get("category") or c.get("trip_name") or "").lower(),
        )
    return cards


@app.get("/api/trips")
async def get_trips(
    catalog: str = Query("All Catalogs"),
    hide_unsharp: bool = Query(False),
    year: Optional[str] = Query(None, description="Optional 4-digit shoot year filter"),
    sort_by: str = Query("capture_desc", description="Sort order for trips & portfolio themes"),
):
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    where_clauses = ["status != 'failed'"]
    params: List[Any] = []
    cat_clean = (catalog or "").strip()
    if cat_clean and cat_clean.lower() not in ("all catalogs", "all", "all photos"):
        if cat_clean.lower() == "keepers":
            where_clauses.append("catalog_name = 'Keepers'")
        else:
            where_clauses.append("catalog_name = ?")
            params.append(cat_clean)

    if hide_unsharp:
        where_clauses.append("(is_unsharp = 0 OR is_unsharp IS NULL)")

    rows = [
        dict(r)
        for r in cursor.execute(
            f"""
            SELECT file_path, file_hash, catalog_name, exif_time, shoot_date,
                   camera_make, camera_model,
                   gps_lat, gps_lon, gps_alt, gps_ground_truth, is_screenshot,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   star_rating, in_keepers, is_sequence_hero, aesthetic_score, sharpness_score,
                   lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                   thumb_360_path, preview_1600_path, vector_index
            FROM photo_records
            WHERE {' AND '.join(where_clauses)}
            """,
            params,
        ).fetchall()
    ]
    conn.close()

    # Build canonical trips and portfolio themes across all catalog rows first so trip_ids and available_years are invariant
    all_trips = _build_trips_from_rows(rows)
    for t in all_trips:
        t.pop("file_hashes", None)

    all_portfolio_themes = _build_portfolio_themes_from_rows(rows)
    for pt in all_portfolio_themes:
        pt.pop("file_hashes", None)

    # Compute available_years across both dated photos and trips
    year_photo_Map: Dict[str, int] = {}
    for r in rows:
        sd = str(r.get("shoot_date") or "")
        if len(sd) >= 4 and sd[:4].isdigit():
            yr = sd[:4]
            year_photo_Map[yr] = year_photo_Map.get(yr, 0) + 1
    year_trip_Map: Dict[str, int] = {}
    for t in all_trips:
        yr = (t.get("start_date") or "")[:4]
        if yr.isdigit():
            year_trip_Map[yr] = year_trip_Map.get(yr, 0) + 1

    available_years = [
        {"year": yr, "photo_count": year_photo_Map.get(yr, 0), "trip_count": year_trip_Map.get(yr, 0)}
        for yr in sorted(year_photo_Map.keys(), reverse=True)
    ]

    # Optional server-side year filter
    y_clean = (year or "").strip()
    if y_clean and y_clean.lower() not in ("all", "all years"):
        trips = [
            t for t in all_trips
            if (t.get("start_date") or "").startswith(y_clean)
            or (t.get("end_date") or "").startswith(y_clean)
            or y_clean in (t.get("year_counts") or {})
        ]
        portfolio_themes = []
        for pt in all_portfolio_themes:
            yb = (pt.get("year_breakdown") or {}).get(y_clean)
            if yb and yb.get("photo_count", 0) > 0:
                merged_pt = dict(pt)
                merged_pt.update(yb)
                portfolio_themes.append(merged_pt)
    else:
        trips = all_trips
        portfolio_themes = all_portfolio_themes

    trips = _sort_trip_or_theme_cards(trips, sort_by, is_portfolio=False)
    portfolio_themes = _sort_trip_or_theme_cards(portfolio_themes, sort_by, is_portfolio=True)

    return {
        "total_trips": len(trips),
        "total_portfolio_themes": len(portfolio_themes),
        "total_photos": len(rows),
        "available_years": available_years,
        "trips": trips,
        "portfolio_themes": portfolio_themes,
    }


# ==============================================================================
# 3. SINGLE PHOTO & METADATA DETAILS
# ==============================================================================
@app.get("/api/photo/{photo_id}")
@app.get("/api/photos/{photo_id}")
async def get_photo(photo_id: str):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    _serialize_photo_item(rec)
    return rec


# ==============================================================================
# 4. INSTANT STAR RATING OVERRIDE
# ==============================================================================
class StarRatingPayload(BaseModel):
    star_rating: int


@app.post("/api/photo/{photo_id}/star")
@app.post("/api/photos/{photo_id}/star")
async def set_star_rating(photo_id: str, payload: StarRatingPayload, background_tasks: BackgroundTasks):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    stars = max(0, min(5, payload.star_rating))
    fp = rec["file_path"]
    stem = Path(fp).name

    record_undo_snapshot(
        db_path=DEFAULT_DB_PATH,
        action_type="star_rating",
        description=f"Star rating → {stars}★ on {stem}",
        photo_ids=[rec.get("file_hash") or fp],
        create_vault_backup=False,
    )

    conn = get_db_connection(DEFAULT_DB_PATH)
    conn.execute(
        "UPDATE photo_records SET star_rating = ?, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
        (stars, fp),
    )
    conn.commit()
    conn.close()

    # Trigger safe additive XMP sync in background thread
    background_tasks.add_task(sync_record_metadata_additive, file_path=fp)

    return {
        "status": "ok",
        "file_path": fp,
        "star_rating": stars,
        "undo_status": get_undo_status(DEFAULT_DB_PATH),
    }


# ==============================================================================
# 5. SYSTEMIC "FIND SIMILAR" ENGINE (MULTI-MODAL VECTOR + COLOR + BIOME FUSION + SAMEDAY)
# ==============================================================================
@app.get("/api/photo/{photo_id}/similar")
@app.get("/api/photos/{photo_id}/similar")
async def get_similar_photos(
    photo_id: str,
    mode: str = Query("visual", pattern="^(visual|orbit|sameday)$"),
    limit: int = Query(24, ge=1, le=200),
):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    if mode == "sameday":
        target_date = str(rec.get("shoot_date") or "")
        if not target_date or target_date == "Undated":
            conn.close()
            return {
                "photo_id": photo_id,
                "mode": mode,
                "shoot_date": target_date,
                "total_same_day": 0,
                "similar_photos": [],
            }

        rows = cursor.execute("""
            SELECT file_path, file_hash, sibling_path, catalog_name,
                   thumb_360_path, preview_1600_path,
                   exif_time, shoot_date, camera_make, camera_model,
                   focal_length, shutter_speed, aperture, iso,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   star_rating, aesthetic_score, sharpness_score, is_unsharp, in_keepers,
                   is_sequence_hero, sequence_id, sequence_frame_index, sequence_length,
                   lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                   file_mtime, updated_at
            FROM photo_records
            WHERE shoot_date = ? AND status != 'failed'
            ORDER BY exif_time ASC, file_path ASC
        """, (target_date,)).fetchall()
        conn.close()

        same_day_items: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["is_current"] = d["file_path"] == rec["file_path"]
            _serialize_photo_item(d)
            same_day_items.append(d)

        return {
            "photo_id": photo_id,
            "mode": mode,
            "shoot_date": target_date,
            "total_same_day": len(same_day_items),
            "similar_photos": same_day_items[:limit],
        }

    if mode == "orbit":
        # Same-day, same-camera +-10 minute (600s) shoot window
        target_cam = str(rec.get("camera_model") or "")
        target_date = str(rec.get("shoot_date") or "")
        dt_target = _parse_exif_dt(rec.get("exif_time"))

        if not dt_target or target_date == "Undated":
            conn.close()
            return {"photo_id": photo_id, "mode": mode, "similar_photos": []}

        rows = cursor.execute("""
            SELECT file_path, file_hash, thumb_360_path, preview_1600_path,
                   exif_time, shoot_date, camera_model, star_rating,
                   aesthetic_score, sharpness_score, in_keepers,
                   lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                   file_mtime, updated_at
            FROM photo_records
            WHERE shoot_date = ? AND camera_model = ? AND file_path != ? AND status != 'failed'
        """, (target_date, target_cam, rec["file_path"])).fetchall()
        conn.close()

        orbit_matches = []
        for r in rows:
            dt_r = _parse_exif_dt(r["exif_time"])
            if dt_r:
                diff_sec = abs((dt_r - dt_target).total_seconds())
                if diff_sec <= 600:  # +-10 minutes
                    d = dict(r)
                    d["time_delta_seconds"] = diff_sec
                    _serialize_photo_item(d)
                    orbit_matches.append(d)

        orbit_matches.sort(key=lambda x: x["time_delta_seconds"])
        return {"photo_id": photo_id, "mode": mode, "similar_photos": orbit_matches[:limit]}

    # Mode: Visual — Multi-Modal Vector (0.65) + Color Signature (0.20) + Biome Jaccard (0.15)
    v_idx = rec.get("vector_index")
    norm_vectors = get_normalized_vectors_matrix()
    color_sigs = get_color_signatures_matrix()

    if v_idx is None or int(v_idx) < 0 or int(v_idx) >= len(norm_vectors):
        conn.close()
        return {"photo_id": photo_id, "mode": mode, "similar_photos": []}

    target_v_idx = int(v_idx)
    target_vec = norm_vectors[target_v_idx]
    clip_sims = np.dot(norm_vectors, target_vec)
    clip_sims[target_v_idx] = -1.0  # Exclude self

    # Strict CLIP semantic floor (>= 0.75) so weakly related scenes are never returned
    candidate_indices = np.where(clip_sims >= 0.75)[0]
    if len(candidate_indices) == 0:
        conn.close()
        return {"photo_id": photo_id, "mode": mode, "similar_photos": []}

    has_color_sigs = len(color_sigs) > target_v_idx
    if has_color_sigs:
        target_hist = color_sigs[target_v_idx, :24].astype(np.float32)
        target_sat = float(color_sigs[target_v_idx, 24])
    else:
        target_hist = None
        target_sat = 0.25

    target_mono = bool(rec.get("is_monochrome"))
    target_biome = _extract_biome_tokens(rec)

    placeholders = ",".join("?" for _ in candidate_indices)
    rows = cursor.execute(f"""
        SELECT file_path, file_hash, thumb_360_path, preview_1600_path,
               exif_time, shoot_date, star_rating, aesthetic_score, sharpness_score,
               is_monochrome, in_keepers, vector_index,
               primary_category, sub_category, state_region, specific_location,
               lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords
        FROM photo_records
        WHERE vector_index IN ({placeholders}) AND file_path != ? AND status != 'failed'
    """, [int(i) for i in candidate_indices] + [rec["file_path"]]).fetchall()
    conn.close()

    scored_results: List[Dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        cand_v_idx = int(d["vector_index"])
        c_sim = float(clip_sims[cand_v_idx])
        if c_sim < 0.75:
            continue

        # 1. Color histogram cosine similarity (24-bin HSV + luminance)
        if has_color_sigs and cand_v_idx < len(color_sigs) and target_hist is not None:
            cand_hist = color_sigs[cand_v_idx, :24].astype(np.float32)
            cand_sat = float(color_sigs[cand_v_idx, 24])
            color_sim = float(np.clip(np.dot(target_hist, cand_hist), 0.0, 1.0))
        else:
            cand_sat = target_sat
            color_sim = c_sim

        # 2. Biome / Category / Place / Lighting Jaccard similarity
        cand_biome = _extract_biome_tokens(d)
        if target_biome and cand_biome:
            union_len = len(target_biome | cand_biome)
            biome_jaccard = float(len(target_biome & cand_biome)) / float(union_len) if union_len > 0 else 0.5
        else:
            # Neutral prior when either photo has not yet completed Stage 2 tagging
            biome_jaccard = 0.55

        combined_sim = (0.65 * c_sim) + (0.20 * color_sim) + (0.15 * biome_jaccard)

        # Penalize monochrome-vs-color or severe saturation mismatches (-0.12)
        cand_mono = bool(d.get("is_monochrome"))
        if target_mono != cand_mono or abs(target_sat - cand_sat) > 0.22:
            combined_sim -= 0.12

        # Enforce strict multi-modal similarity cutoff (combined_similarity >= 0.68)
        if combined_sim < 0.68:
            continue

        _serialize_photo_item(d)
        d["clip_similarity"] = round(c_sim, 4)
        d["color_similarity"] = round(color_sim, 4)
        d["biome_similarity"] = round(biome_jaccard, 4)
        d["similarity"] = round(combined_sim, 4)
        scored_results.append(d)

    scored_results.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "photo_id": photo_id,
        "mode": mode,
        "similar_photos": scored_results[:limit],
    }


def _parse_exif_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str.strip()[:19], fmt)
        except Exception:
            pass
    return None


# ==============================================================================
# 6. CHRONOLOGICAL NEIGHBOR FILMSTRIP (-5 AND +5)
# ==============================================================================
@app.get("/api/photo/{photo_id}/neighbors")
async def get_chronological_neighbors(photo_id: str):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    cat = str(rec.get("catalog_name") or "")
    model = str(rec.get("camera_model") or "")
    sdate = str(rec.get("shoot_date") or "")
    target_fp = rec["file_path"]

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    partition_rows = cursor.execute("""
        SELECT file_path, file_hash, thumb_360_path, preview_1600_path,
               exif_time, shoot_date, star_rating, in_keepers, is_sequence_hero,
               aesthetic_score, sharpness_score, is_unsharp,
               specific_location, city, state_region, country,
               lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords
        FROM photo_records
        WHERE catalog_name = ? AND camera_model = ? AND shoot_date = ? AND status != 'failed'
        ORDER BY exif_time ASC, file_path ASC
    """, (cat, model, sdate)).fetchall()
    conn.close()

    items = [dict(r) for r in partition_rows]
    target_idx = -1
    for idx, it in enumerate(items):
        if it["file_path"] == target_fp:
            target_idx = idx
            break

    if target_idx == -1:
        return {"current_index": 0, "neighbors": []}

    start = max(0, target_idx - 5)
    end = min(len(items), target_idx + 6)
    neighbors = items[start:end]

    for n in neighbors:
        _serialize_photo_item(n)
        n["is_current"] = n["file_path"] == target_fp

    return {
        "current_index": target_idx,
        "total_in_shoot": len(items),
        "neighbors": neighbors,
    }


# ==============================================================================
# 7. SEQUENCE EXPANSION (STRAFING RUN / PANORAMA DRAWER)
# ==============================================================================
@app.get("/api/sequence/{sequence_id}")
async def get_sequence_details(sequence_id: str):
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT file_path, file_hash, thumb_360_path, preview_1600_path,
               exif_time, shoot_date, star_rating, in_keepers, is_sequence_hero,
               sequence_id, sequence_frame_index, sequence_length,
               aesthetic_score, sharpness_score, is_unsharp,
               specific_location, city, state_region, country,
               lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords
        FROM photo_records
        WHERE sequence_id = ?
        ORDER BY is_sequence_hero DESC, sequence_frame_index ASC
    """, (sequence_id,)).fetchall()
    conn.close()

    frames = [dict(r) for r in rows]
    for f in frames:
        _serialize_photo_item(f)

    return {
        "sequence_id": sequence_id,
        "total_frames": len(frames),
        "frames": frames,
    }


# ==============================================================================
# 8. EXPLICIT EXTERNAL APP LAUNCHERS & PHOTOSHOP ROUND-TRIP WATCHER
# ==============================================================================
class OpenAppPayload(BaseModel):
    app: Optional[str] = None   # lightroom | photoshop | capture_one | finder
    mode: Optional[str] = None  # alias for app


@app.post("/api/photo/{photo_id}/open")
@app.post("/api/photos/{photo_id}/open")
@app.post("/api/photos/{photo_id}/open-external")
async def open_external_app(photo_id: str, payload: OpenAppPayload):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    file_path = rec["file_path"]
    sibling_path = rec.get("sibling_path")
    app_choice = (payload.app or payload.mode or "finder").lower().strip()

    target_to_open = file_path
    cmd: List[str] = []

    if app_choice == "finder":
        cmd = ["open", "-R", file_path]
    elif app_choice == "lightroom":
        cmd = ["open", "-a", "Adobe Lightroom Classic", file_path]
    elif app_choice == "capture_one":
        cmd = ["open", "-a", "Capture One", file_path]
    elif app_choice == "photoshop":
        # If .TIF sibling exists, prioritize editing the sibling
        if sibling_path and Path(sibling_path).exists():
            target_to_open = sibling_path
        # Search for exact Photoshop app name in /Applications
        ps_candidates = glob.glob("/Applications/*Photoshop*.app") + glob.glob(
            "/Applications/Adobe Photoshop*/Adobe Photoshop*.app"
        )
        ps_app_name = "Adobe Photoshop"
        if ps_candidates:
            ps_app_name = Path(ps_candidates[0]).stem
        cmd = ["open", "-a", ps_app_name, target_to_open]
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported app: {app_choice}")

    # Register target for live edit watcher even if volume is temporarily unmounted
    _register_file_for_edit_watcher(target_to_open)

    if not Path(target_to_open).exists():
        return {
            "status": "warning",
            "app": app_choice,
            "target": target_to_open,
            "message": f"Source file does not currently exist on local disk: {target_to_open}. Verify DAS/SMB drive is mounted.",
        }

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            # Fallback to default macOS open if specific app bundle isn't installed
            if app_choice == "photoshop":
                fallback_res = subprocess.run(["open", target_to_open], capture_output=True, text=True, check=False)
                if fallback_res.returncode == 0:
                    return {
                        "status": "ok",
                        "app": app_choice,
                        "target_opened": target_to_open,
                        "message": f"Opened {Path(target_to_open).name} (watching for saved edits)",
                    }
            err_msg = res.stderr.strip() or f"Failed to launch {app_choice}"
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "app": app_choice,
                    "target": target_to_open,
                    "message": err_msg,
                },
            )
        return {
            "status": "ok",
            "app": app_choice,
            "target_opened": target_to_open,
            "message": f"Opened in {app_choice.title()} (live file watcher active)",
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(exc)},
        )


@app.post("/api/photos/{photo_id}/sync-edits")
@app.post("/api/photo/{photo_id}/sync-edits")
async def sync_single_photo_edits(photo_id: str, force: bool = Query(False)):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Photo not found")

    target_fp = rec["file_path"]
    if force and Path(target_fp).exists():
        # Force mtime reset in DB so sync_external_edits regenerates previews & vector unconditionally
        conn = get_db_connection(DEFAULT_DB_PATH)
        conn.execute("UPDATE photo_records SET file_mtime = 0 WHERE file_path = ?", (target_fp,))
        conn.commit()
        conn.close()

    res = sync_external_edits(
        db_path=DEFAULT_DB_PATH,
        vectors_path=DEFAULT_VECTORS_PATH,
        color_sigs_path=DEFAULT_COLOR_SIGS_PATH,
        thumbs_360_dir=DEFAULT_THUMBS_360_DIR,
        previews_1600_dir=DEFAULT_PREVIEWS_1600_DIR,
        target_file_paths=[target_fp],
        scan_parent_dirs=True,
    )
    global VECTORS_MTIME, COLOR_SIGS_MTIME
    VECTORS_MTIME = 0.0
    COLOR_SIGS_MTIME = 0.0

    # Refresh localized subject boxes, contrastive gates, and singular/plural deduplication on the synced file
    try:
        reassess_records_fast(
            db_path=DEFAULT_DB_PATH,
            vectors_path=DEFAULT_VECTORS_PATH,
            photo_ids=[target_fp],
            encode_text_batch_fn=encode_text_batch,
        )
    except Exception as exc:
        logging.warning(f"Fast reassessment after single-photo sync warning: {exc}")

    refreshed = resolve_photo_record(photo_id)
    if refreshed:
        _serialize_photo_item(refreshed)
    res["photo"] = refreshed
    return res


@app.post("/api/sync-edits")
async def sync_all_external_edits():
    with WATCHER_LOCK:
        watched_list = list(WATCHED_EDIT_TARGETS["files"].keys())

    res = sync_external_edits(
        db_path=DEFAULT_DB_PATH,
        vectors_path=DEFAULT_VECTORS_PATH,
        color_sigs_path=DEFAULT_COLOR_SIGS_PATH,
        thumbs_360_dir=DEFAULT_THUMBS_360_DIR,
        previews_1600_dir=DEFAULT_PREVIEWS_1600_DIR,
        target_file_paths=watched_list if watched_list else None,
        scan_parent_dirs=True,
    )
    global VECTORS_MTIME, COLOR_SIGS_MTIME
    VECTORS_MTIME = 0.0
    COLOR_SIGS_MTIME = 0.0

    synced_paths = res.get("synced_files") or watched_list
    if synced_paths:
        try:
            reassess_records_fast(
                db_path=DEFAULT_DB_PATH,
                vectors_path=DEFAULT_VECTORS_PATH,
                photo_ids=list(synced_paths),
                encode_text_batch_fn=encode_text_batch,
            )
        except Exception as exc:
            logging.warning(f"Fast reassessment after sync-edits warning: {exc}")
    return res


@app.get("/api/sync-edits/status")
async def get_sync_edits_status():
    with WATCHER_LOCK:
        return {
            "watched_files_count": len(WATCHED_EDIT_TARGETS["files"]),
            "watched_dirs_count": len(WATCHED_EDIT_TARGETS["dirs"]),
            "last_sync_event": WATCHED_EDIT_TARGETS["last_sync_event"],
        }


# ==============================================================================
# 8B. CURATED COLLECTIONS & COFFEE-TABLE BOOKS + DESKTOP HIGH-RES JPEG EXPORT
# ==============================================================================
class CreateCollectionPayload(BaseModel):
    name: str
    description: Optional[str] = ""
    photo_id: Optional[str] = None
    photo_ids: Optional[List[str]] = None


class UpdateCollectionPayload(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_photo_id: Optional[str] = None


class CollectionItemPayload(BaseModel):
    photo_id: Optional[str] = None
    photo_ids: Optional[List[str]] = None


class ReorderCollectionPayload(BaseModel):
    photo_ids: Optional[List[str]] = None
    file_hashes: Optional[List[str]] = None


def _serialize_collection_row(conn: sqlite3.Connection, col_row: Dict[str, Any]) -> Dict[str, Any]:
    cid = col_row["id"]
    item_rows = conn.execute(
        "SELECT photo_id, sort_order, added_at FROM collection_items WHERE collection_id = ? ORDER BY sort_order ASC, added_at ASC",
        (cid,),
    ).fetchall()
    photo_ids = [r["photo_id"] for r in item_rows if r["photo_id"]]

    cover_id = col_row.get("cover_photo_id") or (photo_ids[0] if photo_ids else None)
    cover_thumb_url = None
    if cover_id:
        p_row = conn.execute(
            "SELECT thumb_360_path, file_mtime, updated_at FROM photo_records WHERE file_hash = ? OR file_path = ? LIMIT 1",
            (cover_id, cover_id),
        ).fetchone()
        if p_row and p_row["thumb_360_path"]:
            t_name = Path(p_row["thumb_360_path"]).name
            cover_thumb_url = f"/previews/thumbs_360/{t_name}"

    return {
        "id": cid,
        "name": col_row["name"],
        "description": col_row.get("description") or "",
        "cover_photo_id": cover_id,
        "cover_thumb_url": cover_thumb_url,
        "item_count": len(photo_ids),
        "photo_ids": photo_ids,
        "created_at": col_row.get("created_at"),
        "updated_at": col_row.get("updated_at"),
    }


@app.get("/api/collections")
async def list_collections():
    conn = get_db_connection(DEFAULT_DB_PATH)
    rows = [
        dict(r)
        for r in conn.execute("SELECT * FROM collections ORDER BY updated_at DESC, id DESC").fetchall()
    ]
    result = [_serialize_collection_row(conn, r) for r in rows]
    conn.close()
    return {"collections": result}


@app.post("/api/collections")
async def create_collection(payload: CreateCollectionPayload):
    clean_name = (payload.name or "").strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Collection name cannot be empty")

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    initial_ids: List[str] = []
    if payload.photo_ids:
        initial_ids.extend([p for p in payload.photo_ids if p])
    if payload.photo_id and payload.photo_id not in initial_ids:
        initial_ids.insert(0, payload.photo_id)

    existing = cursor.execute(
        "SELECT * FROM collections WHERE LOWER(name) = LOWER(?)", (clean_name,)
    ).fetchone()
    if existing:
        cid = existing["id"]
    else:
        first_cover = initial_ids[0] if initial_ids else None
        cursor.execute(
            """
            INSERT INTO collections (name, description, cover_photo_id, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (clean_name, (payload.description or "").strip(), first_cover),
        )
        cid = cursor.lastrowid

    for pid in initial_ids:
        rec = resolve_photo_record(pid)
        canonical_pid = rec["file_hash"] if rec and rec.get("file_hash") else pid
        max_order = cursor.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM collection_items WHERE collection_id = ?",
            (cid,),
        ).fetchone()[0]
        cursor.execute(
            """
            INSERT OR IGNORE INTO collection_items (collection_id, photo_id, sort_order, added_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (cid, canonical_pid, int(max_order) + 1),
        )
        cursor.execute(
            "UPDATE collections SET cover_photo_id = COALESCE(cover_photo_id, ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (canonical_pid, cid),
        )

    conn.commit()
    col_row = dict(cursor.execute("SELECT * FROM collections WHERE id = ?", (cid,)).fetchone())
    serialized = _serialize_collection_row(conn, col_row)
    conn.close()
    return serialized


@app.get("/api/collections/{collection_id}")
async def get_collection_details(collection_id: int):
    conn = get_db_connection(DEFAULT_DB_PATH)
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Collection not found")

    col_meta = _serialize_collection_row(conn, dict(row))
    photo_ids = col_meta["photo_ids"]
    photos_list: List[Dict[str, Any]] = []

    if photo_ids:
        ph = ",".join("?" for _ in photo_ids)
        p_rows = [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT file_path, file_hash, sibling_path, catalog_name,
                       exif_time, shoot_date, status, camera_make, camera_model,
                       focal_length, shutter_speed, aperture, iso,
                       gps_lat, gps_lon, gps_alt, gps_ground_truth, is_aerial, is_screenshot,
                       primary_category, sub_category, confidence_score,
                       title, caption, sub_location, specific_location, city, state_region, country,
                       star_rating, color_label, pick_flag,
                       lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       thumb_360_path, preview_1600_path,
                       sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                       laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                       sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                       vector_index, in_keepers, file_mtime, updated_at
                FROM photo_records
                WHERE file_hash IN ({ph}) OR file_path IN ({ph})
                """,
                photo_ids + photo_ids,
            ).fetchall()
        ]
        by_id: Dict[str, Dict[str, Any]] = {}
        for pr in p_rows:
            _serialize_photo_item(pr)
            if pr.get("file_hash"):
                by_id[pr["file_hash"]] = pr
            if pr.get("file_path"):
                by_id[pr["file_path"]] = pr

        for pid in photo_ids:
            if pid in by_id:
                photos_list.append(by_id[pid])

    conn.close()
    col_meta["photos"] = photos_list
    return col_meta


@app.put("/api/collections/{collection_id}")
async def update_collection(collection_id: int, payload: UpdateCollectionPayload):
    conn = get_db_connection(DEFAULT_DB_PATH)
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Collection not found")

    new_name = payload.name.strip() if payload.name is not None else row["name"]
    new_desc = payload.description.strip() if payload.description is not None else (row["description"] or "")
    new_cover = payload.cover_photo_id if payload.cover_photo_id is not None else row["cover_photo_id"]

    conn.execute(
        """
        UPDATE collections
        SET name = ?, description = ?, cover_photo_id = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (new_name, new_desc, new_cover, collection_id),
    )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone())
    res = _serialize_collection_row(conn, updated)
    conn.close()
    return res


@app.delete("/api/collections/{collection_id}")
async def delete_collection(collection_id: int):
    conn = get_db_connection(DEFAULT_DB_PATH)
    conn.execute("DELETE FROM collection_items WHERE collection_id = ?", (collection_id,))
    conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "deleted_id": collection_id}


@app.post("/api/collections/{collection_id}/items")
async def add_photo_to_collection(collection_id: int, payload: CollectionItemPayload):
    conn = get_db_connection(DEFAULT_DB_PATH)
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Collection not found")

    ids_to_add: List[str] = []
    if payload.photo_ids:
        ids_to_add.extend([p for p in payload.photo_ids if p])
    if payload.photo_id and payload.photo_id not in ids_to_add:
        ids_to_add.append(payload.photo_id)

    for pid in ids_to_add:
        rec = resolve_photo_record(pid)
        canonical_pid = rec["file_hash"] if rec and rec.get("file_hash") else pid

        max_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) FROM collection_items WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()[0]
        conn.execute(
            """
            INSERT OR IGNORE INTO collection_items (collection_id, photo_id, sort_order, added_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (collection_id, canonical_pid, int(max_order) + 1),
        )
        conn.execute(
            "UPDATE collections SET cover_photo_id = COALESCE(cover_photo_id, ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (canonical_pid, collection_id),
        )
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone())
    res = _serialize_collection_row(conn, updated)
    conn.close()
    return res


@app.delete("/api/collections/{collection_id}/items/{photo_id}")
async def remove_photo_from_collection(collection_id: int, photo_id: str):
    rec = resolve_photo_record(photo_id)
    canonical_pid = rec["file_hash"] if rec and rec.get("file_hash") else photo_id

    record_undo_snapshot(
        db_path=DEFAULT_DB_PATH,
        action_type="collection_remove_item",
        description=f"Remove photo from collection #{collection_id}",
        collection_ids=[collection_id],
        create_vault_backup=False,
    )

    conn = get_db_connection(DEFAULT_DB_PATH)
    conn.execute(
        "DELETE FROM collection_items WHERE collection_id = ? AND (photo_id = ? OR photo_id = ?)",
        (collection_id, canonical_pid, photo_id),
    )
    conn.execute(
        "UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (collection_id,),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    res = _serialize_collection_row(conn, dict(row)) if row else {"status": "ok"}
    conn.close()
    return res


@app.put("/api/collections/{collection_id}/reorder")
async def reorder_collection_items(collection_id: int, payload: ReorderCollectionPayload):
    ordered_ids = payload.photo_ids or payload.file_hashes or []
    conn = get_db_connection(DEFAULT_DB_PATH)
    for idx, pid in enumerate(ordered_ids):
        conn.execute(
            "UPDATE collection_items SET sort_order = ? WHERE collection_id = ? AND photo_id = ?",
            (idx, collection_id, pid),
        )
    if ordered_ids:
        conn.execute(
            "UPDATE collections SET cover_photo_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (ordered_ids[0], collection_id),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
    res = _serialize_collection_row(conn, dict(row)) if row else {"status": "ok"}
    conn.close()
    return res


def _sanitize_folder_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", (name or "Collection").strip())
    cleaned = re.sub(r"\s+", "_", cleaned).strip("._")
    return cleaned or "MR_Darkroom_Collection"


def _run_collection_export_worker(collection_id: int, col_detail: Dict[str, Any]) -> Dict[str, Any]:
    from PIL import Image, ImageOps

    photos_list = col_detail.get("photos") or []
    total_photos = len(photos_list)
    folder_name = _sanitize_folder_name(col_detail["name"])
    desktop_root = Path.home() / "Desktop"
    export_dir = desktop_root / folder_name
    export_dir.mkdir(parents=True, exist_ok=True)

    JOB_MANAGER.start_job(
        task_type="collection_export",
        title=f"Exporting '{col_detail['name']}' to Desktop",
        total=total_photos,
        phase=f"Exporting {total_photos} high-res JPEGs to ~/Desktop/{folder_name}",
        extra={"collection_id": collection_id, "export_dir": str(export_dir)},
    )

    exported_files: List[Dict[str, Any]] = []
    master_count = 0
    preview_fallback_count = 0
    cancelled_early = False

    try:
        for idx, p in enumerate(photos_list, start=1):
            if not JOB_MANAGER.check_pause_or_cancel():
                cancelled_early = True
                break

            orig_stem = Path(p.get("file_path") or f"photo_{idx}").stem
            out_name = f"{idx:02d}_{orig_stem}.jpg"
            out_path = export_dir / out_name

            JOB_MANAGER.update_progress(
                processed=idx - 1,
                total=total_photos,
                current_file=out_name,
                phase=f"Exporting {idx} of {total_photos}: {out_name}",
            )

            master_fp = Path(p.get("sibling_path") or p.get("file_path") or "")
            if not master_fp.exists() and p.get("file_path"):
                master_fp = Path(p["file_path"])

            used_source = "master"
            src_to_load: Optional[Path] = None

            if master_fp.exists() and master_fp.is_file():
                src_to_load = master_fp
                used_source = "master"
            elif p.get("preview_1600_path") and Path(p["preview_1600_path"]).exists():
                src_to_load = Path(p["preview_1600_path"])
                used_source = "preview_1600"
            elif p.get("thumb_360_path") and Path(p["thumb_360_path"]).exists():
                src_to_load = Path(p["thumb_360_path"])
                used_source = "thumb_360"

            if src_to_load is None:
                continue

            success = False
            width, height = 0, 0
            # Try Pillow first for 4:4:4 chroma subsampling=0, quality=96
            try:
                with Image.open(src_to_load) as im:
                    im = ImageOps.exif_transpose(im)
                    if im.mode in ("I;16", "I;16L", "I;16B", "I"):
                        arr = np.array(im, dtype=np.float32)
                        max_v = float(np.max(arr)) if arr.size > 0 else 65535.0
                        if max_v > 255.0:
                            arr = np.clip((arr / 65535.0) * 255.0, 0, 255).astype(np.uint8)
                        else:
                            arr = np.clip(arr, 0, 255).astype(np.uint8)
                        im = Image.fromarray(arr)
                    elif im.mode != "RGB":
                        im = im.convert("RGB")

                    im.save(str(out_path), format="JPEG", quality=96, subsampling=0, optimize=True)
                    width, height = im.size
                    success = True
            except Exception:
                # Fallback to macOS native sips for layered 16-bit ProPhoto TIFFs or RAWs
                try:
                    sips_cmd = [
                        "sips",
                        "-s", "format", "jpeg",
                        "-s", "formatOptions", "96",
                        "--matchTo", "/System/Library/ColorSync/Profiles/sRGB Profile.icc",
                        str(src_to_load),
                        "--out", str(out_path),
                    ]
                    res = subprocess.run(sips_cmd, capture_output=True, text=True, timeout=60, check=False)
                    if res.returncode == 0 and out_path.exists():
                        with Image.open(out_path) as check_im:
                            width, height = check_im.size
                        success = True
                except Exception as e2:
                    logging.warning(f"Failed exporting {src_to_load} to {out_path}: {e2}")

            if success and out_path.exists():
                if used_source == "master":
                    master_count += 1
                else:
                    preview_fallback_count += 1
                exported_files.append({
                    "filename": out_name,
                    "path": str(out_path),
                    "source": used_source,
                    "width": width,
                    "height": height,
                    "size_mb": round(out_path.stat().st_size / (1024 * 1024), 2),
                })

            JOB_MANAGER.update_progress(
                processed=idx,
                total=total_photos,
                current_file=out_name,
                phase=f"Exported {len(exported_files)} of {total_photos} JPEGs to ~/Desktop/{folder_name}",
            )

        result_payload = {
            "status": "cancelled" if cancelled_early else "ok",
            "cancelled": cancelled_early,
            "collection_id": collection_id,
            "collection_name": col_detail["name"],
            "export_dir": str(export_dir),
            "exported_count": len(exported_files),
            "total_requested": total_photos,
            "master_count": master_count,
            "preview_fallback_count": preview_fallback_count,
            "files": exported_files,
        }
        JOB_MANAGER.finish_job(
            result=result_payload,
            phase=(
                f"Cancelled early — kept {len(exported_files)} exported JPEGs in ~/Desktop/{folder_name}"
                if cancelled_early
                else f"Exported {len(exported_files)} JPEGs to ~/Desktop/{folder_name}"
            ),
        )
        return result_payload
    except Exception as exc:
        JOB_MANAGER.finish_job(error=str(exc), phase="Export Error")
        raise


@app.post("/api/collections/{collection_id}/export")
async def export_collection_to_desktop(collection_id: int, async_job: bool = Query(False)):
    """
    Exports all photos in the Collection/Book to ~/Desktop/{Sanitized_Collection_Name}/
    as print-quality JPEGs (Quality=96, 4:4:4 subsampling=0, sRGB) named 01_{original_stem}.jpg, etc.
    Supports live progress reporting, Pause/Resume, and Cancel via JOB_MANAGER.
    """
    col_detail = await get_collection_details(collection_id)
    photos_list = col_detail.get("photos") or []
    if not photos_list:
        raise HTTPException(status_code=400, detail="Collection is empty — add photos before exporting")

    if async_job:
        threading.Thread(
            target=_run_collection_export_worker,
            args=(collection_id, col_detail),
            daemon=True,
        ).start()
        folder_name = _sanitize_folder_name(col_detail["name"])
        return {
            "status": "started",
            "collection_id": collection_id,
            "collection_name": col_detail["name"],
            "export_dir": str(Path.home() / "Desktop" / folder_name),
            "total": len(photos_list),
        }

    # Run in worker thread so FastAPI event loop remains responsive to /api/jobs/status, /pause, /cancel
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_collection_export_worker, collection_id, col_detail)
    return result


@app.post("/api/collections/{collection_id}/reveal-export")
async def reveal_exported_collection_folder(collection_id: int):
    col_detail = await get_collection_details(collection_id)
    folder_name = _sanitize_folder_name(col_detail["name"])
    export_dir = Path.home() / "Desktop" / folder_name
    if not export_dir.exists():
        export_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["open", str(export_dir)], check=False)
    return {"status": "ok", "export_dir": str(export_dir)}


# ==============================================================================
# 9. PIPELINE EXECUTION, UNIFIED BACKGROUND JOB CONTROL & AI TEACH / SCOUT
# ==============================================================================
@app.get("/api/jobs/status")
async def get_unified_job_status():
    return JOB_MANAGER.get_status()


@app.post("/api/jobs/pause")
@app.post("/api/pipeline/pause")
async def pause_background_job():
    return JOB_MANAGER.pause()


@app.post("/api/jobs/resume")
@app.post("/api/pipeline/resume")
async def resume_background_job():
    return JOB_MANAGER.resume()


@app.post("/api/jobs/cancel")
@app.post("/api/pipeline/cancel")
async def cancel_background_job():
    return JOB_MANAGER.cancel()


class RunPipelineRequest(BaseModel):
    catalog_name: str
    root_path: Optional[str] = None
    path: Optional[str] = None
    description: Optional[str] = None
    stage: int = 0  # 0 = Full 1-Click Import + AI Tagging, 1 = Stage 1 Only, 2 = Deep VLM Only
    run_ai_tagging: bool = True
    ai_mode: str = "fast_vectors"  # "fast_vectors" (fast 5-facet OpenCLIP + GPS + Ontology) or "deep_vlm"
    extract_sharpness: bool = True
    fast_only: Optional[bool] = None
    split_by_subfolder: bool = False
    selected_subfolders: Optional[List[str]] = None


@app.post("/api/pipeline/run")
async def trigger_pipeline_run(payload: RunPipelineRequest, background_tasks: BackgroundTasks):
    global PIPELINE_STATUS
    if PIPELINE_STATUS["running"]:
        raise HTTPException(status_code=409, detail="Pipeline scan already in progress")

    clean_cat_name = (payload.catalog_name or "").strip()
    if not clean_cat_name and not payload.split_by_subfolder:
        raise HTTPException(status_code=400, detail="Catalog name cannot be empty")

    explicit_root = (payload.root_path or payload.path or "").strip()
    p_exp: Optional[Path] = None
    if explicit_root:
        p_exp = Path(explicit_root).expanduser().resolve()
        if not p_exp.exists() or not p_exp.is_dir():
            raise HTTPException(status_code=400, detail=f"Folder does not exist on disk: {explicit_root}")
        if not payload.split_by_subfolder:
            conn_reg = get_db_connection(DEFAULT_DB_PATH)
            conn_reg.execute(
                """
                INSERT INTO catalogs (catalog_name, root_path, description, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(catalog_name) DO UPDATE SET
                    root_path = excluded.root_path,
                    description = COALESCE(excluded.description, catalogs.description)
                """,
                (clean_cat_name, str(p_exp), payload.description),
            )
            conn_reg.commit()
            conn_reg.close()

    def _progress_cb(processed: int, total: int, current_file: str, phase: str = "Processing..."):
        PIPELINE_STATUS["processed"] = processed
        PIPELINE_STATUS["total"] = total
        PIPELINE_STATUS["current_file"] = current_file
        PIPELINE_STATUS["phase"] = phase
        JOB_MANAGER.update_progress(processed=processed, total=total, current_file=current_file, phase=phase)
        return JOB_MANAGER.check_pause_or_cancel()

    def _worker(
        catalog_name: str,
        stage: int,
        run_ai_tagging: bool,
        ai_mode: str,
        extract_sharpness: bool,
        fast_only: Optional[bool],
        split_by_subfolder: bool = False,
        selected_subfolders: Optional[List[str]] = None,
        explicit_root_path: Optional[Path] = None,
    ):
        global PIPELINE_STATUS, VECTORS_MTIME, CROP_VECTORS_MTIME, COLOR_SIGS_MTIME
        initial_phase = (
            "Step 1: Importing Photos, Extracting GPS & Building Previews..."
            if stage in (0, 1)
            else "Step 2: AI Visual Tagging & Scene Analysis..."
        )
        PIPELINE_STATUS = {
            "running": True,
            "catalog_name": catalog_name,
            "stage": stage,
            "phase": initial_phase,
            "processed": 0,
            "total": 0,
            "current_file": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "error": None,
        }
        JOB_MANAGER.start_job(
            task_type=f"pipeline_stage_{stage}",
            title=f"Import & AI Tag ({catalog_name})" if stage == 0 or run_ai_tagging else f"Catalog Scan ({catalog_name}) — Stage {stage}",
            total=0,
            phase=initial_phase,
            extra={"catalog_name": catalog_name, "stage": stage, "split_by_subfolder": split_by_subfolder},
        )
        try:
            if stage in (0, 1):
                root: Optional[Path] = explicit_root_path
                if root is None:
                    conn = get_db_connection(DEFAULT_DB_PATH)
                    row = conn.execute(
                        "SELECT root_path FROM catalogs WHERE catalog_name = ?", (catalog_name,)
                    ).fetchone()
                    conn.close()
                    if row and row["root_path"]:
                        root = Path(row["root_path"])
                    else:
                        cfg = load_settings()
                        cats = cfg.get("catalogs", [])
                        if isinstance(cats, list):
                            cat_cfg = next(
                                (c for c in cats if isinstance(c, dict) and c.get("name") == catalog_name),
                                None,
                            )
                            if cat_cfg and cat_cfg.get("path"):
                                root = Path(cat_cfg["path"])

                if root is None or not root.exists():
                    raise FileNotFoundError(f"Catalog root_path not found or not mounted for '{catalog_name}': {root}")

                use_fast_only = bool(fast_only) if fast_only is not None else False

                # Determine whether we are splitting into per-subfolder catalogs or running a single catalog import
                target_catalog_pairs: List[Tuple[str, Path]] = []
                if split_by_subfolder:
                    sub_names = [s.strip() for s in (selected_subfolders or []) if s and s.strip()]
                    if not sub_names:
                        skip_dirs = {"backups", "backup", "_temporary", ".trash", ".trashes", "__macosx"}
                        for child in sorted(root.iterdir()):
                            if (
                                child.is_dir()
                                and not child.name.startswith(".")
                                and child.name.lower() not in skip_dirs
                                and not child.name.lower().endswith(".lrdata")
                                and not child.name.lower().endswith(".lrcat-data")
                            ):
                                sub_names.append(child.name)
                    for sub_name in sub_names:
                        sub_dir = (root / sub_name).resolve()
                        if sub_dir.exists() and sub_dir.is_dir():
                            target_catalog_pairs.append((sub_name, sub_dir))
                    if not target_catalog_pairs:
                        target_catalog_pairs.append((catalog_name or root.name, root))
                else:
                    target_catalog_pairs.append((catalog_name, root))

                total_sub_cats = len(target_catalog_pairs)
                for idx_cat, (sub_cat_name, sub_cat_root) in enumerate(target_catalog_pairs, 1):
                    if not JOB_MANAGER.check_pause_or_cancel():
                        raise RuntimeError("Import cancelled by user")

                    PIPELINE_STATUS["catalog_name"] = sub_cat_name
                    cat_prefix = f"[{idx_cat}/{total_sub_cats}: {sub_cat_name}] " if total_sub_cats > 1 else ""

                    # Register subfolder catalog in DB
                    conn_sub = get_db_connection(DEFAULT_DB_PATH)
                    conn_sub.execute(
                        """
                        INSERT INTO catalogs (catalog_name, root_path, description, created_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(catalog_name) DO UPDATE SET
                            root_path = excluded.root_path,
                            description = COALESCE(excluded.description, catalogs.description)
                        """,
                        (sub_cat_name, str(sub_cat_root), payload.description),
                    )
                    conn_sub.commit()
                    conn_sub.close()

                    def _sub_progress_cb(processed: int, total: int, current_file: str, phase: str = "Processing..."):
                        return _progress_cb(processed, total, current_file, f"{cat_prefix}{phase}")

                    run_stage1_pipeline(
                        source_dir=sub_cat_root,
                        catalog_name=sub_cat_name,
                        db_path=DEFAULT_DB_PATH,
                        vectors_path=DEFAULT_VECTORS_PATH,
                        thumbs_360_dir=DEFAULT_THUMBS_360_DIR,
                        previews_1600_dir=DEFAULT_PREVIEWS_1600_DIR,
                        progress_callback=_sub_progress_cb,
                        fast_only=use_fast_only,
                    )

                    # Invalidate in-memory vector & color signature caches so newly ingested rows are immediately available
                    VECTORS_MTIME = 0.0
                    CROP_VECTORS_MTIME = 0.0
                    COLOR_SIGS_MTIME = 0.0
                    invalidate_search_index_cache()

                    if stage == 0 or run_ai_tagging:
                        if not JOB_MANAGER.check_pause_or_cancel():
                            raise RuntimeError("Import cancelled by user")

                        # Invariant 2: Level 1 4-Pass Cascade runs automatically on every folder import
                        PIPELINE_STATUS["phase"] = f"{cat_prefix}Building multi-crop visual vectors on Apple Metal GPU..."
                        try:
                            build_or_update_crop_vectors_mps(db_path=DEFAULT_DB_PATH)
                        except Exception as exc:
                            logger.warning(f"build_or_update_crop_vectors_mps warning: {exc}")

                        mode_norm = (ai_mode or "fast_vectors").strip().lower()
                        if mode_norm == "deep_vlm":
                            reassess_records_fast(
                                db_path=DEFAULT_DB_PATH,
                                vectors_path=DEFAULT_VECTORS_PATH,
                                photo_ids=None,
                                catalog_name=sub_cat_name,
                                encode_text_batch_fn=encode_text_batch,
                                progress_cb=_sub_progress_cb,
                                run_clustering=True,
                            )
                            PIPELINE_STATUS["phase"] = f"{cat_prefix}Step 2: Deep AI Vision Scene Analysis..."
                            run_stage2_vlm(
                                db_path=DEFAULT_DB_PATH,
                                catalog_name=sub_cat_name,
                                progress_callback=_sub_progress_cb,
                            )
                        else:
                            PIPELINE_STATUS["phase"] = f"{cat_prefix}Step 2: AI Visual Tagging, GPS Ground-Truth & Location Sync..."
                            reassess_records_fast(
                                db_path=DEFAULT_DB_PATH,
                                vectors_path=DEFAULT_VECTORS_PATH,
                                photo_ids=None,
                                catalog_name=sub_cat_name,
                                encode_text_batch_fn=encode_text_batch,
                                progress_cb=_sub_progress_cb,
                                run_clustering=True,
                            )
            elif stage == 2:
                PIPELINE_STATUS["phase"] = "Step 2: AI Visual Tagging & Scene Analysis..."
                run_stage2_vlm(
                    db_path=DEFAULT_DB_PATH,
                    catalog_name=catalog_name,
                    progress_callback=_progress_cb,
                )
            invalidate_search_index_cache()
            PIPELINE_STATUS["running"] = False
            PIPELINE_STATUS["phase"] = "Completed"
            PIPELINE_STATUS["completed_at"] = datetime.now().isoformat()
            JOB_MANAGER.finish_job(phase="Completed")
        except Exception as exc:
            logging.error(f"Pipeline error: {exc}")
            PIPELINE_STATUS["running"] = False
            PIPELINE_STATUS["phase"] = "Error"
            PIPELINE_STATUS["error"] = str(exc)
            JOB_MANAGER.finish_job(error=str(exc), phase="Error")

    threading.Thread(
        target=_worker,
        args=(
            clean_cat_name,
            payload.stage,
            payload.run_ai_tagging,
            payload.ai_mode,
            payload.extract_sharpness,
            payload.fast_only,
            payload.split_by_subfolder,
            payload.selected_subfolders,
            p_exp,
        ),
        daemon=True,
    ).start()
    return {
        "status": "started",
        "catalog_name": clean_cat_name,
        "stage": payload.stage,
        "run_ai_tagging": payload.run_ai_tagging,
        "ai_mode": payload.ai_mode,
        "split_by_subfolder": payload.split_by_subfolder,
        "selected_subfolders": payload.selected_subfolders,
    }


@app.get("/api/pipeline/status")
async def get_pipeline_status():
    job_st = JOB_MANAGER.get_status()
    merged = dict(PIPELINE_STATUS)
    merged["job"] = job_st
    if job_st.get("running") and not merged.get("running"):
        merged.update({
            "running": True,
            "paused": job_st.get("paused", False),
            "cancelled": job_st.get("cancelled", False),
            "task_type": job_st.get("task_type"),
            "title": job_st.get("title"),
            "phase": job_st.get("phase"),
            "processed": job_st.get("processed", 0),
            "total": job_st.get("total", 0),
            "current_file": job_st.get("current_file"),
            "elapsed_seconds": job_st.get("elapsed_seconds", 0.0),
            "eta_seconds": job_st.get("eta_seconds"),
        })
    else:
        merged["paused"] = job_st.get("paused", False)
        merged["cancelled"] = job_st.get("cancelled", False)
        merged["elapsed_seconds"] = job_st.get("elapsed_seconds", 0.0)
        merged["eta_seconds"] = job_st.get("eta_seconds")
    return merged


class ReassessRequest(BaseModel):
    photo_ids: Optional[List[str]] = None
    trip_id: Optional[str] = None
    catalog_name: Optional[str] = None
    mode: str = "fast_vectors"  # "fast_vectors" (<1s) or "deep_vlm" (~3s/photo)
    skip_undo: bool = False
    async_job: Optional[bool] = None


@app.post("/api/reassess")
async def trigger_reassess(payload: ReassessRequest):
    target_ids: Optional[List[str]] = payload.photo_ids

    # If trip_id is provided, resolve its member file_hashes
    if payload.trip_id and not target_ids:
        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        sql = """
            SELECT file_path, file_hash, sibling_path, catalog_name,
                   exif_time, shoot_date, status, camera_make, camera_model,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   star_rating, color_label, pick_flag,
                   lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                   user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                   thumb_360_path, preview_1600_path,
                   sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                   laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                   sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                   vector_index, in_keepers
            FROM photo_records
            WHERE status != 'failed'
        """
        all_rows = [dict(r) for r in cursor.execute(sql).fetchall()]
        conn.close()
        trips_data = _build_trips_from_rows(all_rows)
        matching_trip = next((t for t in trips_data if t["trip_id"] == payload.trip_id), None)
        if matching_trip:
            target_ids = list(matching_trip.get("file_hashes") or [])
        else:
            raise HTTPException(status_code=404, detail=f"Trip not found: {payload.trip_id}")

    if target_ids:
        target_ids = list(dict.fromkeys(str(tid).strip() for tid in target_ids if tid))

    mode = (payload.mode or "fast_vectors").strip().lower()
    total_est = len(target_ids) if target_ids else 849

    if not payload.skip_undo and target_ids:
        action_label = "Deep VLM" if mode == "deep_vlm" else "Basic Tag"
        record_undo_snapshot(
            db_path=DEFAULT_DB_PATH,
            action_type=f"reassess_{mode}",
            description=f"{action_label} on {len(target_ids)} photo{'s' if len(target_ids) != 1 else ''}",
            photo_ids=target_ids,
            create_vault_backup=len(target_ids) >= 5,
        )
        # If any target photo was in [CLEARED_SLATE] state, clear that marker so Basic Tag / Deep VLM can populate fresh tags
        conn_c = get_db_connection(DEFAULT_DB_PATH)
        for i in range(0, len(target_ids), 400):
            chunk_c = target_ids[i : i + 400]
            ph_c = ",".join("?" for _ in chunk_c)
            conn_c.execute(
                f"UPDATE photo_records SET user_context_notes = '' WHERE user_context_notes = '[CLEARED_SLATE]' AND (file_hash IN ({ph_c}) OR file_path IN ({ph_c}))",
                chunk_c + chunk_c,
            )
        conn_c.commit()
        conn_c.close()
    elif not payload.skip_undo and not target_ids:
        create_rolling_vault_backup(DEFAULT_DB_PATH, reason=f"reassess_all_{mode}")

    job_title = (
        f"Deep VLM Re-Assessment ({total_est} photo{'s' if total_est != 1 else ''})"
        if mode == "deep_vlm"
        else f"Basic Tag Re-Assessment ({total_est} photo{'s' if total_est != 1 else ''})"
    )
    job_info = JOB_MANAGER.start_job(
        task_type=f"reassess_{mode}",
        title=job_title,
        total=total_est,
        phase=f"Starting {job_title}...",
    )

    def _reassess_cb(processed: int, total: int, current_file: str, phase: str = "Re-Assessing...") -> bool:
        JOB_MANAGER.update_progress(processed=processed, total=total, current_file=current_file, phase=phase)
        return JOB_MANAGER.check_pause_or_cancel()

    run_in_background = bool(payload.async_job) if payload.async_job is not None else (
        (mode == "deep_vlm" and total_est > 1) or total_est > 20
    )

    if run_in_background:
        def _bg_reassess_worker():
            try:
                if mode == "deep_vlm":
                    rep = reassess_records_deep(
                        db_path=DEFAULT_DB_PATH,
                        vectors_path=DEFAULT_VECTORS_PATH,
                        photo_ids=target_ids,
                        catalog_name=payload.catalog_name,
                        encode_text_batch_fn=encode_text_batch,
                        progress_cb=_reassess_cb,
                    )
                else:
                    rep = reassess_records_fast(
                        db_path=DEFAULT_DB_PATH,
                        vectors_path=DEFAULT_VECTORS_PATH,
                        photo_ids=target_ids,
                        catalog_name=payload.catalog_name,
                        encode_text_batch_fn=encode_text_batch,
                        progress_cb=_reassess_cb,
                    )
                invalidate_search_index_cache()
                JOB_MANAGER.update_progress(processed=total_est, total=total_est, phase="Re-Assessment Complete")
                JOB_MANAGER.finish_job(result=rep, phase="Re-Assessment Complete")
            except Exception as exc:
                logging.error(f"Background reassessment error ({mode}): {exc}")
                JOB_MANAGER.finish_job(error=str(exc), phase="Re-Assessment Error")

        threading.Thread(target=_bg_reassess_worker, daemon=True).start()
        return {
            "status": "started",
            "job_id": job_info.get("job_id") if isinstance(job_info, dict) else str(job_info),
            "mode": mode,
            "total": total_est,
            "undo_status": get_undo_status(DEFAULT_DB_PATH),
        }

    loop = asyncio.get_running_loop()
    try:
        if mode == "deep_vlm":
            report = await loop.run_in_executor(
                None,
                lambda: reassess_records_deep(
                    db_path=DEFAULT_DB_PATH,
                    vectors_path=DEFAULT_VECTORS_PATH,
                    photo_ids=target_ids,
                    catalog_name=payload.catalog_name,
                    encode_text_batch_fn=encode_text_batch,
                    progress_cb=_reassess_cb,
                ),
            )
        else:
            report = await loop.run_in_executor(
                None,
                lambda: reassess_records_fast(
                    db_path=DEFAULT_DB_PATH,
                    vectors_path=DEFAULT_VECTORS_PATH,
                    photo_ids=target_ids,
                    catalog_name=payload.catalog_name,
                    encode_text_batch_fn=encode_text_batch,
                    progress_cb=_reassess_cb,
                ),
            )
        invalidate_search_index_cache()
        JOB_MANAGER.update_progress(processed=total_est, total=total_est, phase="Re-Assessment Complete")
        JOB_MANAGER.finish_job(result=report, phase="Re-Assessment Complete")
    except Exception as exc:
        JOB_MANAGER.finish_job(error=str(exc), phase="Re-Assessment Error")
        raise

    # If specific photo_ids or trip_id were reassessed, return their refreshed serialized records (up to 500 inline)
    updated_photos: List[Dict[str, Any]] = []
    if target_ids:
        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        fetched: List[Dict[str, Any]] = []
        seen_fp = set()
        for i in range(0, min(len(target_ids), 500), 400):
            chunk_ids = target_ids[i : i + 400]
            placeholders = ",".join("?" for _ in chunk_ids)
            sql = f"""
                SELECT file_path, file_hash, sibling_path, catalog_name,
                       exif_time, shoot_date, status, camera_make, camera_model,
                       focal_length, shutter_speed, aperture, iso,
                       gps_lat, gps_lon, gps_alt, gps_ground_truth, is_aerial, is_screenshot,
                       primary_category, sub_category, confidence_score,
                       title, caption, sub_location, specific_location, city, state_region, country,
                       star_rating, color_label, pick_flag,
                       lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       thumb_360_path, preview_1600_path,
                       sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                       laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                       sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                       vector_index, in_keepers, file_mtime, updated_at
                FROM photo_records
                WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})
            """
            for r in cursor.execute(sql, chunk_ids + chunk_ids).fetchall():
                rd = dict(r)
                if rd["file_path"] not in seen_fp:
                    seen_fp.add(rd["file_path"])
                    fetched.append(rd)
        conn.close()
        order_map = {str(tid): i for i, tid in enumerate(target_ids)}
        fetched.sort(key=lambda x: order_map.get(str(x.get("file_hash") or ""), order_map.get(str(x.get("file_path") or ""), 999999)))
        for item in fetched:
            updated_photos.append(_serialize_photo_item(item))

    report["photos"] = updated_photos
    report["undo_status"] = get_undo_status(DEFAULT_DB_PATH)
    return report


# ==============================================================================
# 9B. "TEACH AI" VOICE/TEXT CONTEXT OVERRIDE & "VOICE ARCHIVE SCOUT" STORY BUILDER
# ==============================================================================
class TeachPreviewRequest(BaseModel):
    instruction: Optional[str] = None
    prompt: Optional[str] = None
    photo_ids: Optional[List[Any]] = None
    wipe_existing: Optional[bool] = False
    wipe_mode: Optional[bool] = False
    clean_slate: Optional[bool] = False


class TeachApplyRequest(BaseModel):
    photo_ids: List[Any]
    instruction: Optional[str] = None
    prompt: Optional[str] = None
    mode: str = "instant"  # "instant" (<1s) or "deep_vlm" (re-runs Qwen2.5-VL with context)
    wipe_existing: Optional[bool] = False
    wipe_mode: Optional[bool] = False
    clean_slate: Optional[bool] = False
    approved_tags: Optional[List[str]] = None
    removed_tags: Optional[List[str]] = None
    dismissed_tags: Optional[List[str]] = None
    location_updates: Optional[Dict[str, Optional[str]]] = None
    clear_existing_notes: Optional[bool] = False


def _extract_visual_vector_candidates_for_rows(
    rows: List[Dict[str, Any]],
    spoken_tags: List[str],
    negated_tags: List[str],
    wipe_mode: bool = False,
) -> List[str]:
    """
    Uses OpenCLIP vector concept probes (`vectors.npy`) and verified generic visual nouns
    on the selected photo records to propose high-confidence visual tags (`⚡`) that fit
    the selected image(s) without repeating `spoken_tags` or violating `negated_tags`.
    """
    if not rows:
        return []
    spoken_low = {str(t).strip().lower() for t in (spoken_tags or []) if str(t or "").strip()}
    neg_low = {str(t).strip().lower() for t in (negated_tags or []) if str(t or "").strip()}
    for r in rows:
        for n in _parse_json_list(r.get("negated_tags")):
            if str(n or "").strip():
                neg_low.add(str(n).strip().lower())

    visual_candidates: List[str] = []
    seen_vis: set = set()

    def _add_vis(label: str) -> None:
        clean_l = str(label or "").strip()
        ll = clean_l.lower()
        if not clean_l or ll in spoken_low or ll in neg_low or ll in seen_vis:
            return
        seen_vis.add(ll)
        visual_candidates.append(clean_l)

    try:
        vecs = get_vectors_matrix()
        if len(vecs) > 0:
            probes_map = compute_clip_concept_probes_for_rows(
                rows, vecs, encode_text_batch_fn=encode_text_batch
            )
            for r in rows:
                p = probes_map.get(r["file_path"], {})
                if p.get("is_aerial"):
                    _add_vis("Aerial Perspective")
                if p.get("has_mirror_selfie"):
                    _add_vis("Mirror Selfie")
                    _add_vis("Man")
                if p.get("has_fitting_room"):
                    _add_vis("Fitting Room")
                if p.get("has_person"):
                    _add_vis("Person")
                if p.get("has_dog"):
                    _add_vis("Dog")
                if p.get("has_cat"):
                    _add_vis("Cat")
                if p.get("has_cat_tree"):
                    _add_vis("Cat Tree")
                if p.get("has_living_room"):
                    _add_vis("Living Room")
                if p.get("has_carpet_rug"):
                    _add_vis("Carpet")
                if p.get("has_framed_art"):
                    _add_vis("Framed Art")
                if p.get("has_window_curtain"):
                    _add_vis("Window")
                if p.get("has_car"):
                    _add_vis("Car")
                if p.get("has_sports_car"):
                    _add_vis("Sports Car")
                    _add_vis("Sedan")
                if p.get("has_gas_station"):
                    _add_vis("Gas Station")
                if p.get("has_night_scene"):
                    _add_vis("Night")
                if p.get("has_artificial_light"):
                    _add_vis("Artificial Lighting")
                if p.get("has_horse"):
                    _add_vis("Horse")
                if p.get("has_bison"):
                    _add_vis("Bison")
                if p.get("has_cattle"):
                    _add_vis("Cattle")
                if p.get("has_bird"):
                    _add_vis("Bird")
                if float(p.get("f2_doors_windows_sim", 0.0)) >= 0.225 or float(p.get("lm_colonial_doors_sim", 0.0)) >= 0.245:
                    _add_vis("Doors & Windows")
                    _add_vis("Architectural Facade")
                if float(p.get("f2_boats_vessels_sim", 0.0)) >= 0.235:
                    _add_vis("Boats & Waterways")
                if float(p.get("f1_coastline_surf_sim", 0.0)) >= 0.245:
                    _add_vis("Coastline")
                if float(p.get("f2_snow_ice_sim", 0.0)) >= 0.248:
                    _add_vis("Snow & Ice")
                if float(p.get("f1_agricultural_grid_sim", 0.0)) >= 0.245:
                    _add_vis("Agricultural Geometric")
                if float(p.get("f1_canyon_badlands_sim", 0.0)) >= 0.250:
                    _add_vis("Canyon & Rock Formations")
                if float(p.get("f1_industrial_facility_sim", 0.0)) >= 0.245:
                    _add_vis("Industrial Facility")
                if float(p.get("f1_urban_skyline_sim", 0.0)) >= 0.242:
                    _add_vis("Urban Architecture")
    except Exception as exc:
        logging.warning(f"Visual vector candidate probe in teach preview skipped: {exc}")

    # Also surface verified generic visual nouns already present on the photo(s)
    for r in rows:
        existing_flat = (
            _parse_json_list(r.get("key_subjects"))
            + _parse_json_list(r.get("existing_keywords"))
            + _parse_json_list(r.get("lrcat_keywords"))
        )
        for tok in existing_flat:
            ts = str(tok or "").strip()
            if ts and ts.lower() in _GENERIC_VISUAL_NOUNS_KEEP:
                _add_vis(ts)

    return visual_candidates[:10]


@app.post("/api/ai/teach/preview")
@app.post("/api/ai/teach-preview")
async def preview_teach_instruction(payload: TeachPreviewRequest):
    text = (payload.instruction or payload.prompt or "").strip()
    force_wipe = bool(payload.wipe_existing or payload.wipe_mode or payload.clean_slate)
    parsed = parse_natural_language_teach(text, wipe_existing=force_wipe)
    is_wipe_mode = bool(parsed.get("wipe_mode"))

    spoken_tags: List[str] = list(parsed.get("positive_tags") or [])
    remove_tags: List[str] = list(parsed.get("negated_tags") or [])
    visual_tags: List[str] = []

    if payload.photo_ids:
        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        target_rows: List[Dict[str, Any]] = []
        for pid in payload.photo_ids[:24]:
            pid_str = str(pid)
            rowid_val = int(pid) if str(pid).isdigit() else -1
            row = cursor.execute(
                """
                SELECT file_path, file_hash, vector_index, is_aerial,
                       title, caption, sub_location, specific_location, city, state_region, country,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       key_subjects, existing_keywords, lrcat_keywords, hierarchical_keywords
                FROM photo_records
                WHERE file_hash = ? OR file_path = ? OR rowid = ?
                LIMIT 1
                """,
                (pid_str, pid_str, rowid_val),
            ).fetchone()
            if row:
                target_rows.append(dict(row))
        conn.close()

        if target_rows:
            visual_tags = _extract_visual_vector_candidates_for_rows(
                rows=target_rows,
                spoken_tags=spoken_tags,
                negated_tags=remove_tags,
                wipe_mode=is_wipe_mode,
            )
            if parsed.get("visual_inspect_requested"):
                try:
                    inspected = discover_visual_subjects_for_records(
                        records=target_rows,
                        db_path=DEFAULT_DB_PATH,
                        vectors_path=DEFAULT_VECTORS_PATH,
                        encode_text_batch_fn=encode_text_batch,
                    )
                    seen_vt = {v.lower() for v in visual_tags} | {s.lower() for s in spoken_tags}
                    for dt in inspected.get("discovered_tags", []):
                        dt_s = str(dt or "").strip()
                        if dt_s and dt_s.lower() not in seen_vt:
                            seen_vt.add(dt_s.lower())
                            visual_tags.append(dt_s)
                except Exception as exc:
                    logging.warning(f"Visual inspect discovery in teach preview failed: {exc}")
            if is_wipe_mode:
                seen_rem = {r.lower() for r in remove_tags}
                for rdict in target_rows:
                    cleaned_preview = apply_clean_slate_wipe_to_record(
                        rdict=rdict,
                        parsed_teach=parsed,
                        instruction_text=text,
                    )
                    for q_tag in cleaned_preview.get("quarantined_tags", []):
                        ql = str(q_tag or "").strip().lower()
                        if ql and ql not in seen_rem:
                            seen_rem.add(ql)
                            remove_tags.append(str(q_tag).strip())

    combined_add: List[str] = []
    seen_comb: set = set()
    for t in spoken_tags + visual_tags:
        tl = str(t or "").strip().lower()
        if tl and tl not in seen_comb:
            seen_comb.add(tl)
            combined_add.append(str(t).strip())

    return {
        "status": "ok",
        "parsed": parsed,
        "wipe_mode": is_wipe_mode,
        "wipe_detected_from_speech": bool(parsed.get("wipe_detected_from_speech")),
        "custom_user_phrases": parsed.get("custom_user_tags", []),
        "spoken_tags": spoken_tags,
        "visual_tags": visual_tags,
        "add_tags": combined_add,
        "added_tags": combined_add,
        "remove_tags": remove_tags,
        "removed_tags": remove_tags,
        "location_updates": parsed.get("location_updates", {}),
        "portfolio_categories": parsed.get("portfolio_categories", []),
    }


@app.post("/api/ai/teach")
async def apply_teach_instruction(payload: TeachApplyRequest):
    if not payload.photo_ids:
        raise HTTPException(status_code=400, detail="Select at least one photo to teach.")

    # Quick "Clear Prior Notes" action from the read-only reference badge
    if payload.clear_existing_notes:
        undo_entry = record_undo_snapshot(
            db_path=DEFAULT_DB_PATH,
            action_type="clear_taught_notes",
            description=f"Clear Prior Taught Notes ({len(payload.photo_ids)} photo{'s' if len(payload.photo_ids) != 1 else ''})",
            photo_ids=payload.photo_ids,
            create_vault_backup=False,
        )
        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        canonical_ids: List[str] = []
        for pid in payload.photo_ids:
            pid_str = str(pid)
            rowid_val = int(pid) if str(pid).isdigit() else -1
            row = cursor.execute(
                "SELECT file_path, file_hash, user_taught_tags, key_subjects FROM photo_records WHERE file_hash = ? OR file_path = ? OR rowid = ? LIMIT 1",
                (pid_str, pid_str, rowid_val),
            ).fetchone()
            if not row:
                continue
            rdict = dict(row)
            fp = rdict["file_path"]
            canonical_ids.append(rdict.get("file_hash") or fp)
            old_taught_low = {str(t).strip().lower() for t in _parse_json_list(rdict.get("user_taught_tags"))}
            cur_ks = [t for t in _parse_json_list(rdict.get("key_subjects")) if str(t).strip().lower() not in old_taught_low]
            cursor.execute(
                """
                UPDATE photo_records
                SET user_context_notes = NULL,
                    user_taught_tags = '[]',
                    key_subjects = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                (json.dumps(cur_ks), fp),
            )
        conn.commit()
        conn.close()

        updated_photos: List[Dict[str, Any]] = []
        if canonical_ids:
            conn2 = get_db_connection(DEFAULT_DB_PATH)
            placeholders = ",".join("?" for _ in canonical_ids)
            sql = f"""
                SELECT file_path, file_hash, sibling_path, catalog_name,
                       exif_time, shoot_date, status, camera_make, camera_model,
                       focal_length, shutter_speed, aperture, iso,
                       gps_lat, gps_lon, gps_alt, gps_ground_truth, is_aerial, is_screenshot,
                       primary_category, sub_category, confidence_score,
                       title, caption, sub_location, specific_location, city, state_region, country,
                       star_rating, color_label, pick_flag,
                       lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       thumb_360_path, preview_1600_path,
                       sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                       laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                       sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                       vector_index, in_keepers, file_mtime, updated_at
                FROM photo_records
                WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})
            """
            fetched = [dict(r) for r in conn2.execute(sql, list(canonical_ids) + list(canonical_ids)).fetchall()]
            conn2.close()
            for item in fetched:
                updated_photos.append(_serialize_photo_item(item))
        return {
            "status": "ok",
            "mode": "clear_notes",
            "updated_count": len(canonical_ids),
            "undo_available": True,
            "undo_id": undo_entry if isinstance(undo_entry, int) else (undo_entry.get("undo_id") if isinstance(undo_entry, dict) else None),
            "undo_status": get_undo_status(DEFAULT_DB_PATH),
            "photos": updated_photos,
        }

    instruction_text = (payload.instruction or payload.prompt or "").strip()
    force_wipe = bool(payload.wipe_existing or payload.wipe_mode or payload.clean_slate)
    has_explicit_approvals = payload.approved_tags is not None or payload.removed_tags is not None
    if not instruction_text and not force_wipe and not has_explicit_approvals:
        raise HTTPException(status_code=400, detail="Instruction cannot be empty.")

    parsed = parse_natural_language_teach(instruction_text, wipe_existing=force_wipe)
    is_wipe_mode = bool(parsed.get("wipe_mode"))
    is_visual_inspect = bool(parsed.get("visual_inspect_requested"))

    # Respect user's interactive Pre-Commit Review pruning (`×` dismissals & manual tag additions)
    dismissed_list = [str(t).strip() for t in (payload.dismissed_tags or []) if str(t or "").strip()]
    dismissed_low_set = {t.lower() for t in dismissed_list}

    _directive_filler_low = {
        "bro just look", "what's", "whats", "just look", "look at it",
        "tag what's", "tag whats", "in there", "tell me", "look closely",
        "reassess", "rescan", "re-scan",
    }

    if payload.approved_tags is not None:
        positive_new = [
            str(t).strip()
            for t in payload.approved_tags
            if str(t or "").strip()
            and str(t).strip().lower() not in dismissed_low_set
            and str(t).strip().lower() not in _directive_filler_low
        ]
        parsed["added_tags"] = list(positive_new)
        parsed["positive_tags"] = list(positive_new)
        # If the user dismissed (`×`) a location tag pill, clear that location field from `parsed`
        for loc_field in ("country", "state_region", "city", "specific_location"):
            loc_val = parsed.get(loc_field)
            if loc_val and str(loc_val).strip().lower() in dismissed_low_set:
                parsed[loc_field] = None
                if isinstance(parsed.get("location_updates"), dict):
                    parsed["location_updates"].pop(loc_field, None)
    else:
        positive_new = [
            t for t in (parsed.get("positive_tags") or [])
            if str(t).strip().lower() not in dismissed_low_set
            and str(t).strip().lower() not in _directive_filler_low
        ]
        if is_visual_inspect and not positive_new and payload.photo_ids:
            try:
                conn_vi = get_db_connection(DEFAULT_DB_PATH)
                cur_vi = conn_vi.cursor()
                vi_rows: List[Dict[str, Any]] = []
                for pid in payload.photo_ids[:24]:
                    pid_str = str(pid)
                    rowid_val = int(pid) if str(pid).isdigit() else -1
                    r_vi = cur_vi.execute(
                        "SELECT file_path, file_hash, vector_index, is_aerial, preview_1600_path, thumb_360_path, negated_tags FROM photo_records WHERE file_hash = ? OR file_path = ? OR rowid = ? LIMIT 1",
                        (pid_str, pid_str, rowid_val),
                    ).fetchone()
                    if r_vi:
                        vi_rows.append(dict(r_vi))
                conn_vi.close()
                if vi_rows:
                    inspected = discover_visual_subjects_for_records(
                        records=vi_rows,
                        db_path=DEFAULT_DB_PATH,
                        vectors_path=DEFAULT_VECTORS_PATH,
                        encode_text_batch_fn=encode_text_batch,
                    )
                    for dt in inspected.get("discovered_tags", []):
                        dt_s = str(dt or "").strip()
                        if dt_s and dt_s.lower() not in dismissed_low_set and dt_s not in positive_new:
                            positive_new.append(dt_s)
            except Exception as exc:
                logging.warning(f"Visual inspect discovery in teach apply failed: {exc}")

    if payload.location_updates is not None:
        for loc_field in ("country", "state_region", "city", "specific_location"):
            if loc_field in payload.location_updates:
                parsed[loc_field] = payload.location_updates[loc_field]

    if payload.removed_tags is not None:
        negated_new = [str(t).strip() for t in payload.removed_tags if str(t or "").strip()]
    else:
        negated_new = list(parsed.get("negated_tags") or [])

    # Any tag the user explicitly clicked `×` on during Pre-Commit Review is also added to negated_new
    # so fast vector reassessment never sneaks a dismissed AI tag back onto the photo!
    pos_low_final = {p.lower() for p in positive_new}
    seen_neg_init = {n.lower() for n in negated_new}
    for d_tag in dismissed_list:
        dl = d_tag.lower()
        if dl not in pos_low_final and dl not in seen_neg_init:
            seen_neg_init.add(dl)
            negated_new.append(d_tag)
    parsed["negated_tags"] = list(negated_new)

    # Snapshot all affected records BEFORE mutating so 1-Click Undo (Cmd+Z) restores exact state
    action_label = "Clean-Slate Wipe & Re-Anchor" if is_wipe_mode else "Teach AI"
    short_instr = (instruction_text[:48] + "…") if len(instruction_text) > 48 else (instruction_text or ", ".join(positive_new[:3]) or "Wipe tags")
    undo_entry = record_undo_snapshot(
        db_path=DEFAULT_DB_PATH,
        action_type="teach_wipe" if is_wipe_mode else "teach_ai",
        description=f"{action_label} ({len(payload.photo_ids)} photo{'s' if len(payload.photo_ids) != 1 else ''}): {short_instr}",
        photo_ids=payload.photo_ids,
        create_vault_backup=True,
    )

    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    canonical_ids = []
    wipe_summaries: List[Dict[str, Any]] = []
    any_cleared_slate_direct = False

    clean_pids = list(dict.fromkeys(str(pid).strip() for pid in payload.photo_ids if pid is not None and str(pid).strip()))
    matched_rows: List[Dict[str, Any]] = []
    seen_match_fp = set()
    for i in range(0, len(clean_pids), 400):
        chunk_pids = clean_pids[i : i + 400]
        ph_p = ",".join("?" for _ in chunk_pids)
        num_ids = [int(p) for p in chunk_pids if p.isdigit()]
        if num_ids:
            ph_num = ",".join("?" for _ in num_ids)
            q_sql = f"""
                SELECT file_path, file_hash, title, caption,
                       gps_lat, gps_lon, gps_ground_truth, is_aerial,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       key_subjects, existing_keywords, lrcat_keywords, hierarchical_keywords,
                       sub_location, specific_location, city, state_region, country
                FROM photo_records
                WHERE file_hash IN ({ph_p}) OR file_path IN ({ph_p}) OR rowid IN ({ph_num})
            """
            q_params = chunk_pids + chunk_pids + num_ids
        else:
            q_sql = f"""
                SELECT file_path, file_hash, title, caption,
                       gps_lat, gps_lon, gps_ground_truth, is_aerial,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       key_subjects, existing_keywords, lrcat_keywords, hierarchical_keywords,
                       sub_location, specific_location, city, state_region, country
                FROM photo_records
                WHERE file_hash IN ({ph_p}) OR file_path IN ({ph_p})
            """
            q_params = chunk_pids + chunk_pids
        for r in cursor.execute(q_sql, q_params).fetchall():
            rd = dict(r)
            if rd["file_path"] not in seen_match_fp:
                seen_match_fp.add(rd["file_path"])
                matched_rows.append(rd)

    for rdict in matched_rows:
        fp = rdict["file_path"]
        canonical_ids.append(rdict.get("file_hash") or fp)

        if is_wipe_mode:
            cleaned = apply_clean_slate_wipe_to_record(
                rdict=rdict,
                parsed_teach=parsed,
                instruction_text=instruction_text,
            )
            # If user explicitly approved a pruned tag list, ensure dismissed tags are stripped from cleaned output
            if payload.approved_tags is not None:
                cleaned_ks = [
                    t for t in _parse_json_list(cleaned.get("key_subjects"))
                    if str(t).strip().lower() not in dismissed_low_set
                ]
                cleaned_ek = [
                    t for t in _parse_json_list(cleaned.get("existing_keywords"))
                    if str(t).strip().lower() not in dismissed_low_set
                ]
                cleaned["user_taught_tags"] = json.dumps(positive_new)
                cleaned["key_subjects"] = json.dumps(list(dict.fromkeys(positive_new + cleaned_ks)))
                cleaned["existing_keywords"] = json.dumps(list(dict.fromkeys(positive_new + cleaned_ek)))

            wipe_summaries.append({
                "file_hash": rdict.get("file_hash"),
                "preserved_visual_nouns": cleaned.get("preserved_visual_nouns", []),
                "quarantined_tags": cleaned.get("quarantined_tags", []),
            })
            cursor.execute(
                """
                UPDATE photo_records
                SET title = ?,
                    caption = ?,
                    sub_location = ?,
                    specific_location = ?,
                    city = ?,
                    state_region = ?,
                    country = ?,
                    location_provenance = ?,
                    user_context_notes = ?,
                    user_taught_tags = ?,
                    negated_tags = ?,
                    subject_boxes = ?,
                    verified_subjects = ?,
                    key_subjects = ?,
                    existing_keywords = ?,
                    hierarchical_keywords = ?,
                    tag_authority_weight = 0.85,
                    assessment_tier = 'level1',
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                (
                    cleaned["title"],
                    cleaned["caption"],
                    cleaned["sub_location"],
                    cleaned["specific_location"],
                    cleaned["city"],
                    cleaned["state_region"],
                    cleaned["country"],
                    cleaned.get("location_provenance") or ("user_cleared" if not instruction_text and not positive_new else str(rdict.get("location_provenance") or "")),
                    cleaned["user_context_notes"],
                    cleaned["user_taught_tags"],
                    cleaned["negated_tags"],
                    cleaned.get("subject_boxes", json.dumps([])),
                    cleaned.get("verified_subjects", json.dumps([])),
                    cleaned["key_subjects"],
                    cleaned["existing_keywords"],
                    cleaned["hierarchical_keywords"],
                    fp,
                ),
            )
        else:
            prev_notes = str(rdict.get("user_context_notes") or "").strip()
            was_cleared_slate = (prev_notes == "[CLEARED_SLATE]")
            # Do not store conversational inspection commands ("bro just look at it and tag what's in there") as permanent user_context_notes
            if is_visual_inspect:
                note_to_store = ""
            else:
                note_to_store = instruction_text if instruction_text else ", ".join(positive_new)
            if was_cleared_slate:
                any_cleared_slate_direct = True
                updated_notes = note_to_store
            elif note_to_store and note_to_store not in prev_notes:
                updated_notes = f"{prev_notes} | {note_to_store}".strip(" |") if prev_notes else note_to_store
            else:
                updated_notes = prev_notes

            prev_taught = _parse_json_list(rdict.get("user_taught_tags"))
            prev_negated = _parse_json_list(rdict.get("negated_tags"))

            neg_lower_new = {n.lower() for n in negated_new}
            pos_lower_new = {p.lower() for p in positive_new}

            # Merge taught tags (removing any newly negated or dismissed ones)
            merged_taught: List[str] = []
            seen_t: set = set()
            for t in positive_new + prev_taught:
                tl = t.strip().lower()
                if tl and tl not in seen_t and tl not in neg_lower_new and tl not in dismissed_low_set:
                    seen_t.add(tl)
                    merged_taught.append(t.strip())

            # Merge negated tags (removing any newly taught positive ones)
            merged_negated: List[str] = []
            seen_n: set = set()
            for n in negated_new + prev_negated:
                nl = n.strip().lower()
                if nl and nl not in seen_n and nl not in pos_lower_new:
                    seen_n.add(nl)
                    merged_negated.append(n.strip())

            # Immediately place merged_taught at the front of key_subjects (and strip negated/dismissed)
            cur_subjects = [] if was_cleared_slate else _parse_json_list(rdict.get("key_subjects"))
            neg_all_low = {n.lower() for n in merged_negated} | dismissed_low_set
            updated_subjects: List[str] = []
            seen_sub: set = set()
            for s_tag in merged_taught + cur_subjects:
                sl = str(s_tag or "").strip().lower()
                if sl and sl not in seen_sub and sl not in neg_all_low:
                    seen_sub.add(sl)
                    updated_subjects.append(str(s_tag).strip())

            new_ctry = parsed.get("country") or rdict.get("country")
            new_st = parsed.get("state_region") or rdict.get("state_region")
            new_cty = parsed.get("city") or rdict.get("city")
            new_sp = parsed.get("specific_location") or rdict.get("specific_location")

            cursor.execute(
                """
                UPDATE photo_records
                SET user_context_notes = ?,
                    user_taught_tags = ?,
                    negated_tags = ?,
                    key_subjects = ?,
                    country = ?,
                    state_region = ?,
                    city = ?,
                    specific_location = ?,
                    tag_authority_weight = 2.0,
                    assessment_tier = 'level3_user',
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                (
                    updated_notes,
                    json.dumps(merged_taught),
                    json.dumps(merged_negated),
                    json.dumps(updated_subjects),
                    new_ctry,
                    new_st,
                    new_cty,
                    new_sp,
                    fp,
                ),
            )

    conn.commit()
    conn.close()

    reassess_mode = "deep_vlm" if (payload.mode or "").strip().lower() == "deep_vlm" else "fast_vectors"
    if (is_wipe_mode or any_cleared_slate_direct) and reassess_mode != "deep_vlm":
        # Clean-Slate Wipe has already synthesized clean 5-facet keywords and quarantined old guesses;
        # rebuild the self-learning ground-truth centroid index and return the freshly re-anchored records.
        try:
            build_self_learning_index(db_path=DEFAULT_DB_PATH, vectors_path=DEFAULT_VECTORS_PATH)
        except Exception as e:
            logging.warning(f"Failed rebuilding self-learning index after wipe: {e}")
        updated_photos = []
        if canonical_ids:
            conn2 = get_db_connection(DEFAULT_DB_PATH)
            seen_fp = set()
            for i in range(0, min(len(canonical_ids), 500), 400):
                chunk_c = canonical_ids[i : i + 400]
                placeholders = ",".join("?" for _ in chunk_c)
                sql = f"""
                    SELECT file_path, file_hash, sibling_path, catalog_name,
                           exif_time, shoot_date, status, camera_make, camera_model,
                           focal_length, shutter_speed, aperture, iso,
                           title, caption, sub_location, specific_location, city, state_region, country,
                           star_rating, color_label, pick_flag,
                           lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                           user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                           thumb_360_path, preview_1600_path,
                           sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                           laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                           sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                           vector_index, in_keepers, file_mtime, updated_at,
                           tag_authority_weight, assessment_tier, macro_biome
                    FROM photo_records
                    WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})
                """
                for r in conn2.execute(sql, chunk_c + chunk_c).fetchall():
                    rd = dict(r)
                    if rd["file_path"] not in seen_fp:
                        seen_fp.add(rd["file_path"])
                        updated_photos.append(_serialize_photo_item(rd))
            conn2.close()
        reassess_resp = {"photos": updated_photos}
    else:
        try:
            reassess_resp = await trigger_reassess(
                ReassessRequest(photo_ids=canonical_ids, mode=reassess_mode, skip_undo=True)
            )
            # Enforce that any tags dismissed (`×`) in Pre-Commit Review stay stripped after fast reassessment
            if dismissed_low_set and canonical_ids:
                conn3 = get_db_connection(DEFAULT_DB_PATH)
                cur3 = conn3.cursor()
                placeholders = ",".join("?" for _ in canonical_ids)
                rows3 = cur3.execute(
                    f"SELECT file_path, user_taught_tags, key_subjects, existing_keywords FROM photo_records WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})",
                    list(canonical_ids) + list(canonical_ids),
                ).fetchall()
                for r3 in rows3:
                    fp3 = r3["file_path"]
                    ut3 = [t for t in _parse_json_list(r3["user_taught_tags"]) if str(t).strip().lower() not in dismissed_low_set]
                    ks3 = [t for t in _parse_json_list(r3["key_subjects"]) if str(t).strip().lower() not in dismissed_low_set]
                    ek3 = [t for t in _parse_json_list(r3["existing_keywords"]) if str(t).strip().lower() not in dismissed_low_set]
                    cur3.execute(
                        "UPDATE photo_records SET user_taught_tags = ?, key_subjects = ?, existing_keywords = ? WHERE file_path = ?",
                        (json.dumps(ut3), json.dumps(ks3), json.dumps(ek3), fp3),
                    )
                conn3.commit()
                sql3 = f"""
                    SELECT file_path, file_hash, sibling_path, catalog_name,
                           exif_time, shoot_date, status, camera_make, camera_model,
                           focal_length, shutter_speed, aperture, iso,
                           title, caption, sub_location, specific_location, city, state_region, country,
                           star_rating, color_label, pick_flag,
                           lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                           user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                           thumb_360_path, preview_1600_path,
                           sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                           laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                           sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                           vector_index, in_keepers, file_mtime, updated_at,
                           tag_authority_weight, assessment_tier, macro_biome
                    FROM photo_records
                    WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})
                """
                fetched3 = [dict(r) for r in conn3.execute(sql3, list(canonical_ids) + list(canonical_ids)).fetchall()]
                conn3.close()
                reassess_resp = {"photos": [_serialize_photo_item(it) for it in fetched3]}
        except HTTPException:
            raise
        except Exception as exc:
            logging.exception("Teach AI reassess failed")
            return JSONResponse(
                status_code=500,
                content={"status": "error", "detail": f"Teach AI reassess error: {exc}"},
            )

    return {
        "status": "ok",
        "mode": reassess_mode,
        "wipe_mode": is_wipe_mode,
        "wipe_summaries": wipe_summaries,
        "updated_count": len(canonical_ids),
        "parsed": parsed,
        "approved_tags": positive_new,
        "removed_tags": negated_new,
        "undo_available": True,
        "undo_id": undo_entry if isinstance(undo_entry, int) else (undo_entry.get("undo_id") if isinstance(undo_entry, dict) else None),
        "undo_status": get_undo_status(DEFAULT_DB_PATH),
        "photos": reassess_resp.get("photos", []),
    }


# ==============================================================================
# 9C. 1-CLICK LOCATION CONTROLS & ACTIVE VECTOR SUBJECT RECLASSIFICATION
# ==============================================================================
class PhotoLocationUpdateRequest(BaseModel):
    action: str = "set"  # "clear" or "set"
    location: Optional[str] = None
    specific_location: Optional[str] = None
    city: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = None


class SubjectReclassifyRequest(BaseModel):
    old_label: str
    new_label: Optional[str] = ""
    action: str = "reclassify"  # "dismiss" or "reclassify"
    bbox: Optional[List[float]] = None


@app.get("/api/locations/autocomplete")
async def get_locations_autocomplete():
    """
    Returns distinct verified locations from the catalog plus canonical landmarks
    for instant Lightbox location autocomplete.
    """
    conn = get_db_connection(DEFAULT_DB_PATH)
    rows = conn.execute(
        """
        SELECT DISTINCT specific_location, city, state_region, country, location_provenance
        FROM photo_records
        WHERE status != 'failed'
          AND (specific_location != '' OR state_region != '' OR country != '')
        """
    ).fetchall()
    conn.close()

    suggestions_by_label: Dict[str, Dict[str, str]] = {}

    def _add_sug(spec: str, city: str, state: str, country: str) -> None:
        parts = [p for p in [spec, city, state, country] if p and p.lower() not in ("unknown", "none")]
        if not parts:
            return
        dedup_parts: List[str] = []
        for p in parts:
            if p not in dedup_parts:
                dedup_parts.append(p)
        label = ", ".join(dedup_parts)
        if label.lower() not in suggestions_by_label:
            suggestions_by_label[label.lower()] = {
                "label": label,
                "specific_location": spec,
                "city": city,
                "state_region": state,
                "country": country,
            }

    for r in rows:
        _add_sug(
            str(r["specific_location"] or "").strip(),
            str(r["city"] or "").strip(),
            str(r["state_region"] or "").strip(),
            str(r["country"] or "").strip(),
        )

    for g_val in GLOBAL_LANDMARK_GAZETTEER.values():
        _add_sug(
            str(g_val.get("specific_location") or "").strip(),
            "",
            str(g_val.get("state_region") or "").strip(),
            str(g_val.get("country") or "").strip(),
        )

    for st in sorted(US_STATE_NAMES):
        _add_sug(st, "", st, "United States")

    sorted_list = sorted(suggestions_by_label.values(), key=lambda x: x["label"].lower())
    return {
        "status": "ok",
        "count": len(sorted_list),
        "locations": sorted_list,
    }


def _parse_user_location_string(raw_loc: str) -> Tuple[str, str, str, str, List[str], Optional[str]]:
    """
    Resolves a human-entered location string (e.g. 'Port of Los Angeles, California',
    'Mono Lake', 'Cuba', 'San Miguel de Allende, Mexico') into
    (specific_location, city, state_region, country, extra_tags, hierarchy_path).
    """
    s = (raw_loc or "").strip()
    if not s:
        return ("", "", "", "", [], None)
    s_low = s.lower()

    # 1. Check GLOBAL_LANDMARK_GAZETTEER
    for g_val in GLOBAL_LANDMARK_GAZETTEER.values():
        spec_g = str(g_val.get("specific_location") or "").strip()
        if spec_g and (s_low == spec_g.lower() or s_low in spec_g.lower()):
            return (
                spec_g,
                "",
                str(g_val.get("state_region") or "").strip(),
                str(g_val.get("country") or "").strip(),
                list(g_val.get("tags") or []),
                str(g_val.get("hierarchy") or ""),
            )

    # 2. Check US State exact match
    us_states_by_low = {st.lower(): st for st in US_STATE_NAMES}
    if s_low in us_states_by_low:
        st_c = us_states_by_low[s_low]
        return (st_c, "", st_c, "United States", [st_c], f"Places|United States|{st_c}")

    # 3. Comma-separated parts (e.g. "Port of Los Angeles, California" or "Havana, Cuba")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) == 1:
        val = parts[0]
        # Known country check
        known_countries = {
            "iceland": "Iceland", "mexico": "Mexico", "cuba": "Cuba", "italy": "Italy",
            "france": "France", "united kingdom": "United Kingdom", "england": "United Kingdom",
            "new zealand": "New Zealand", "canada": "Canada", "japan": "Japan",
            "peru": "Peru", "chile": "Chile", "argentina": "Argentina", "costa rica": "Costa Rica",
        }
        if val.lower() in known_countries:
            c_canon = known_countries[val.lower()]
            return (c_canon, "", val if val.lower() == "england" else c_canon, c_canon, [c_canon], f"Places|{c_canon}")
        return (val, "", "", "", [val], f"Places|{val}")
    elif len(parts) == 2:
        first, second = parts[0], parts[1]
        if second.lower() in us_states_by_low:
            st_c = us_states_by_low[second.lower()]
            return (first, first, st_c, "United States", [first, st_c], f"Places|United States|{st_c}|{first}")
        return (first, first, second, second, [first, second], f"Places|{second}|{first}")
    else:
        spec_p = parts[0]
        state_p = parts[-2]
        country_p = parts[-1]
        if state_p.lower() in us_states_by_low:
            state_p = us_states_by_low[state_p.lower()]
            country_p = "United States"
        return (spec_p, parts[1] if len(parts) > 3 else spec_p, state_p, country_p, [spec_p, state_p, country_p], f"Places|{country_p}|{state_p}|{spec_p}")


@app.post("/api/photos/{photo_id:path}/location")
@app.post("/api/photo/{photo_id:path}/location")
async def update_photo_location(photo_id: str, payload: PhotoLocationUpdateRequest):
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Photo not found: {photo_id}")

    fp = rec["file_path"]
    fhash = rec.get("file_hash") or fp
    action = (payload.action or "set").strip().lower()

    record_undo_snapshot(
        db_path=DEFAULT_DB_PATH,
        action_type=f"location_{action}",
        description=f"{'Cleared' if action == 'clear' else 'Set'} location on {Path(fp).name}",
        photo_ids=[fhash],
        create_vault_backup=False,
    )

    old_locs = [
        str(rec.get(f) or "").strip()
        for f in ("specific_location", "sub_location", "city", "state_region", "country")
        if str(rec.get(f) or "").strip() and str(rec.get(f) or "").strip().lower() not in ("unknown", "none")
    ]
    old_locs_low = {ol.lower() for ol in old_locs}

    user_taught = _parse_json_list(rec.get("user_taught_tags"))
    negated = _parse_json_list(rec.get("negated_tags"))
    key_subjects = _parse_json_list(rec.get("key_subjects"))
    existing_kws = _parse_json_list(rec.get("existing_keywords"))
    hier_kws = _parse_json_list(rec.get("hierarchical_keywords"))

    if action == "clear":
        for ol in old_locs:
            if ol.lower() not in {n.lower() for n in negated}:
                negated.append(ol)
        user_taught = [t for t in user_taught if t.lower() not in old_locs_low]
        key_subjects = [t for t in key_subjects if t.lower() not in old_locs_low]
        existing_kws = [t for t in existing_kws if t.lower() not in old_locs_low]
        hier_kws = [hk for hk in hier_kws if not str(hk).lower().startswith("places|")]

        conn = get_db_connection(DEFAULT_DB_PATH)
        conn.execute(
            """
            UPDATE photo_records
            SET country = '',
                state_region = '',
                city = '',
                specific_location = '',
                sub_location = '',
                location_provenance = 'user_cleared',
                user_taught_tags = ?,
                negated_tags = ?,
                key_subjects = ?,
                existing_keywords = ?,
                hierarchical_keywords = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
            """,
            (
                json.dumps(user_taught),
                json.dumps(negated),
                json.dumps(key_subjects),
                json.dumps(existing_kws),
                json.dumps(hier_kws),
                fp,
            ),
        )
        conn.commit()
        conn.close()
    else:
        raw_loc = (payload.location or "").strip()
        if raw_loc:
            spec, city, state, country, extra_tags, hier_path = _parse_user_location_string(raw_loc)
        else:
            spec = (payload.specific_location or "").strip()
            city = (payload.city or "").strip()
            state = (payload.state_region or "").strip()
            country = (payload.country or "").strip()
            extra_tags = [x for x in (spec, city, state, country) if x]
            hier_path = "|".join(["Places"] + [x for x in (country, state, spec) if x]) if any((country, state, spec)) else None

        new_locs_low = {x.lower() for x in extra_tags if x}
        # Remove old conflicting location tags that aren't in the new location
        stale_locs_low = old_locs_low - new_locs_low
        user_taught = [t for t in user_taught if t.lower() not in stale_locs_low]
        key_subjects = [t for t in key_subjects if t.lower() not in stale_locs_low]
        negated = [n for n in negated if n.lower() not in new_locs_low]
        hier_kws = [hk for hk in hier_kws if not str(hk).lower().startswith("places|")]
        if hier_path:
            hier_kws.append(hier_path)

        for et in extra_tags:
            if et and et.lower() != "united states":
                if et.lower() not in {t.lower() for t in user_taught}:
                    user_taught.append(et)
                if et.lower() not in {t.lower() for t in key_subjects}:
                    key_subjects.insert(0, et)

        conn = get_db_connection(DEFAULT_DB_PATH)
        conn.execute(
            """
            UPDATE photo_records
            SET country = ?,
                state_region = ?,
                city = ?,
                specific_location = ?,
                location_provenance = 'user',
                user_taught_tags = ?,
                negated_tags = ?,
                key_subjects = ?,
                hierarchical_keywords = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
            """,
            (
                country,
                state,
                city,
                spec,
                json.dumps(user_taught),
                json.dumps(negated),
                json.dumps(key_subjects),
                json.dumps(hier_kws),
                fp,
            ),
        )
        conn.commit()
        conn.close()

    updated = resolve_photo_record(fp)
    if updated:
        _serialize_photo_item(updated)
    return {
        "status": "ok",
        "action": action,
        "photo": updated,
        "undo_status": get_undo_status(DEFAULT_DB_PATH),
    }


@app.post("/api/photos/{photo_id:path}/reclassify-subject")
@app.post("/api/photo/{photo_id:path}/reclassify-subject")
async def reclassify_or_dismiss_subject(photo_id: str, payload: SubjectReclassifyRequest):
    """
    Dismisses a false-positive countable subject detection or reclassifies it
    (e.g., 'Bird' -> 'Statue' or 'Person' -> 'Framed Picture'), and persists the
    768-D OpenCLIP vector boundary in `vector_concept_boundaries` so future scoring
    automatically penalizes `old_label` and boosts `new_label` for visually similar vectors.
    """
    rec = resolve_photo_record(photo_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Photo not found: {photo_id}")

    old_label = (payload.old_label or "").strip()
    if not old_label:
        raise HTTPException(status_code=400, detail="old_label is required")

    new_label = (payload.new_label or "").strip()
    is_dismiss = (payload.action or "").strip().lower() == "dismiss" or not new_label or new_label.lower() in ("none", "dismiss", "false_positive")
    if is_dismiss:
        new_label = ""

    fp = rec["file_path"]
    fhash = rec.get("file_hash") or fp

    desc = (
        f"Reclassified '{old_label}' → '{new_label}' on {Path(fp).name}"
        if new_label
        else f"Dismissed false detection '{old_label}' on {Path(fp).name}"
    )
    record_undo_snapshot(
        db_path=DEFAULT_DB_PATH,
        action_type="reclassify_subject",
        description=desc,
        photo_ids=[fhash],
        create_vault_backup=False,
    )

    # Expand old_label to include its singular/plural counterpart
    old_low = old_label.lower()
    old_variants_low: Set[str] = {old_low}
    for sing, plur in SINGULAR_PLURAL_PAIRS:
        s_low, p_low = sing.lower(), plur.lower()
        if old_low in (s_low, p_low):
            old_variants_low.add(s_low)
            old_variants_low.add(p_low)

    user_taught = _parse_json_list(rec.get("user_taught_tags"))
    negated = _parse_json_list(rec.get("negated_tags"))
    key_subjects = _parse_json_list(rec.get("key_subjects"))
    existing_kws = _parse_json_list(rec.get("existing_keywords"))
    hier_kws = _parse_json_list(rec.get("hierarchical_keywords"))
    subject_boxes = _parse_json_raw_list(rec.get("subject_boxes"))
    verified_subjects = _parse_json_raw_list(rec.get("verified_subjects"))

    for ov in sorted(old_variants_low):
        if ov not in {n.lower() for n in negated}:
            negated.append(ov.title())

    user_taught = [t for t in user_taught if t.lower() not in old_variants_low]
    key_subjects = [t for t in key_subjects if t.lower() not in old_variants_low]
    existing_kws = [t for t in existing_kws if t.lower() not in old_variants_low]
    hier_kws = [
        hk for hk in hier_kws
        if not any(ov in str(hk).lower().split("|") for ov in old_variants_low)
    ]

    new_boxes: List[Dict[str, Any]] = []
    for sb in subject_boxes:
        if not isinstance(sb, dict):
            continue
        sb_lbl = str(sb.get("label") or "").strip().lower()
        if sb_lbl in old_variants_low:
            if new_label:
                updated_sb = dict(sb)
                updated_sb["label"] = new_label
                updated_sb["reclassified_from"] = old_label
                updated_sb["source"] = "user_reclassified"
                new_boxes.append(updated_sb)
            continue
        new_boxes.append(sb)

    new_verified: List[Dict[str, Any]] = []
    for vs in verified_subjects:
        if not isinstance(vs, dict):
            continue
        vs_lbl = str(vs.get("label") or "").strip().lower()
        if vs_lbl in old_variants_low:
            if new_label:
                updated_vs = dict(vs)
                updated_vs["label"] = new_label
                updated_vs["source"] = "user_reclassified"
                new_verified.append(updated_vs)
            continue
        new_verified.append(vs)

    if new_label:
        negated = [n for n in negated if n.lower() != new_label.lower()]
        if new_label.lower() not in {t.lower() for t in user_taught}:
            user_taught.insert(0, new_label)
        if new_label.lower() not in {t.lower() for t in key_subjects}:
            key_subjects.insert(0, new_label)
        if not any(str(vs.get("label") or "").lower() == new_label.lower() for vs in new_verified):
            new_verified.append({
                "label": new_label,
                "confidence": 0.99,
                "raw_sim": 0.35,
                "margin": 0.15,
                "source": "user_reclassified",
            })

    key_subjects = deduplicate_singular_plural_tags(key_subjects)

    # Persist Active Vector Boundary in SQLite `vector_concept_boundaries`
    boundary_saved = False
    v_idx = rec.get("vector_index")
    norm_vectors = get_normalized_vectors_matrix()
    conn = get_db_connection(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    if v_idx is not None and 0 <= int(v_idx) < len(norm_vectors):
        vec_bytes = norm_vectors[int(v_idx)].astype(np.float32).tobytes()
        cursor.execute(
            """
            INSERT INTO vector_concept_boundaries
            (photo_id, file_path, file_hash, old_label, new_label, bbox_json, vector_index, vector_blob, weight, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1.0, CURRENT_TIMESTAMP)
            """,
            (
                fhash,
                fp,
                fhash,
                old_label,
                new_label,
                json.dumps(payload.bbox) if payload.bbox else "[]",
                int(v_idx),
                vec_bytes,
            ),
        )
        boundary_saved = True

    cursor.execute(
        """
        UPDATE photo_records
        SET user_taught_tags = ?,
            negated_tags = ?,
            key_subjects = ?,
            existing_keywords = ?,
            hierarchical_keywords = ?,
            subject_boxes = ?,
            verified_subjects = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE file_path = ?
        """,
        (
            json.dumps(user_taught),
            json.dumps(negated),
            json.dumps(key_subjects),
            json.dumps(existing_kws),
            json.dumps(hier_kws),
            json.dumps(new_boxes),
            json.dumps(new_verified),
            fp,
        ),
    )
    conn.commit()
    conn.close()

    updated = resolve_photo_record(fp)
    if updated:
        _serialize_photo_item(updated)

    return {
        "status": "ok",
        "old_label": old_label,
        "new_label": new_label,
        "boundary_saved": boundary_saved,
        "photo": updated,
        "undo_status": get_undo_status(DEFAULT_DB_PATH),
    }


class ScoutArchiveRequest(BaseModel):
    prompt: str
    seed_photo_ids: Optional[List[str]] = None
    auto_create_collection: bool = True
    collection_name: Optional[str] = None
    enrich_tags: bool = True
    preview_only: Optional[bool] = False
    approved_photo_ids: Optional[List[str]] = None
    approved_tags: Optional[List[str]] = None


def _decompose_scout_prompt(prompt: str) -> Dict[str, Any]:
    """
    Decomposes a natural-language Scout/Story prompt into:
      1. Multi-angle OpenCLIP semantic/compositional/detail probes
      2. Enriching theme tags to apply to discovered matches
      3. Color/Saturation expectations (e.g. vibrant/colorful vs monochrome)
      4. Suggested collection name
    """
    pl = (prompt or "").strip().lower()
    parsed_teach = parse_natural_language_teach(prompt or "")

    clip_probes: List[str] = []
    theme_tags: List[str] = list(parsed_teach.get("positive_tags") or [])
    expect_colorful = any(w in pl for w in ("colorful", "vibrant", "bright", "saturated", "vivid", "painted", "multicolored", "color"))
    expect_monochrome = any(w in pl for w in ("black and white", "monochrome", "b&w", "grayscale"))
    expect_aerial = any(w in pl for w in ("aerial", "from above", "top-down", "aircraft", "birds eye", "overhead"))

    # Detect specialized architectural / subject themes
    has_doors_windows = any(w in pl for w in ("door", "doors", "doorway", "window", "windows", "shutter", "shutters", "facade", "façade", "portal", "entryway"))
    has_horses = any(w in pl for w in ("horse", "horses", "equine", "mustang", "stallion", "mare", "foal", "colt", "equestrian", "ranch"))
    has_boats_canals = any(w in pl for w in ("boat", "boats", "gondola", "canal", "canals", "harbor", "marina", "vessel", "ship"))
    has_barns_farms = any(w in pl for w in ("barn", "barns", "farmhouse", "homestead", "silo", "farmland", "agricultural"))
    has_churches_towers = any(w in pl for w in ("church", "cathedral", "steeple", "bell tower", "campanile", "chapel", "spire"))
    has_abstract_patterns = any(w in pl for w in ("abstract", "pattern", "patterns", "geometric", "texture", "textures", "lines"))

    if has_doors_windows:
        clip_probes.extend([
            "architectural detail of colorful painted wooden doors, doorways, and arched windows on a building facade",
            "close-up street photography of vibrant painted house facades, window shutters, and wooden doors in Burano Venice Italy",
            "weathered wooden doorway, window frame, and textured plaster or brick wall architecture",
            "tight architectural study of doors and windows with bold colors and geometric framing",
        ])
        for t in ("Doors & Windows", "Architectural Facade", "Window Shutters", "Portal Detail"):
            if t not in theme_tags:
                theme_tags.append(t)

    if has_horses:
        clip_probes.extend([
            "photograph of a domestic horse, wild mustang, or equine herd standing or running in a pasture or landscape",
            "equestrian portrait of horses in a rural ranch meadow, desert, or mountain field",
            "close-up or full-body wildlife photograph of a horse",
        ])
        for t in ("Horse", "Equine", "Animal", "Wildlife & Livestock"):
            if t not in theme_tags:
                theme_tags.append(t)

    if has_boats_canals:
        clip_probes.extend([
            "wooden boats, gondolas, and watercraft moored along a scenic canal or harbor waterway",
            "waterfront architecture with boats reflecting in calm canal water",
        ])
        for t in ("Boats & Waterways", "Canal", "Maritime"):
            if t not in theme_tags:
                theme_tags.append(t)

    if has_barns_farms:
        clip_probes.extend([
            "rustic wooden barn, historic farmhouse, and agricultural outbuildings in a rural landscape",
            "weathered timber barn structure surrounded by fields and pasture",
        ])
        for t in ("Barn", "Rural Architecture", "Pastoral"):
            if t not in theme_tags:
                theme_tags.append(t)

    if has_churches_towers:
        clip_probes.extend([
            "tall church steeple, bell tower, campanile, or cathedral facade rising against the sky",
            "historic sacred architecture and landmark tower",
        ])
        for t in ("Church & Tower", "Sacred Architecture", "Landmark"):
            if t not in theme_tags:
                theme_tags.append(t)

    if has_abstract_patterns:
        clip_probes.extend([
            "abstract geometric patterns, repeating lines, and rich surface textures filling the frame",
            "fine art photographic study of natural or architectural form, rhythm, and texture",
        ])
        for t in ("Abstract Pattern", "Geometric Form", "Texture Study"):
            if t not in theme_tags:
                theme_tags.append(t)

    # Always include a cleaned semantic probe from the user's own prompt (stripping collection/command boilerplate)
    core_desc = re.sub(
        r"(?i)\b(find|search|look\s+for|scout|all\s+photos\s+of|photos\s+that\s+have|put\s+them\s+in(?:to)?\s+a\s+(?:collection|book|story).*|create\s+a\s+(?:collection|book|story).*|make\s+a\s+(?:collection|book|story).*|and\s+build\s+a\s+story.*)\b",
        " ",
        prompt or "",
    )
    core_desc = re.sub(r"\s+", " ", core_desc).strip(" ,.;:-")
    if core_desc:
        clip_probes.insert(0, f"a fine art photograph showing {core_desc}")
        if expect_colorful:
            clip_probes.append(f"vibrant, richly saturated colorful photograph of {core_desc}")

    if not clip_probes:
        clip_probes.append(f"a fine art photograph of {prompt.strip()}")

    # Determine suggested collection name if not explicitly provided
    suggested_name = None
    m_named = re.search(
        r"(?i)(?:collection|book|story|series)\s+(?:called|named|titled)\s+['\"]?([A-Za-z0-9 &,\-—'’]+?)['\"]?(?:$|[,.])",
        prompt or "",
    )
    if m_named:
        suggested_name = m_named.group(1).strip()
    if not suggested_name:
        if has_doors_windows and expect_colorful:
            suggested_name = "Colorful Doors & Windows"
        elif has_doors_windows:
            suggested_name = "Doors, Windows & Facades"
        elif has_horses:
            suggested_name = "Horses & Equine Studies"
        elif has_boats_canals:
            suggested_name = "Canals, Boats & Waterways"
        elif has_barns_farms:
            suggested_name = "Barns & Rural Homesteads"
        elif core_desc:
            words = [w for w in re.split(r"\s+", core_desc) if w.lower() not in ("the", "with", "that", "have", "some", "good", "nice", "like", "this", "these", "one")]
            suggested_name = " ".join(words[:5]).title() or "AI Scouted Story"
        else:
            suggested_name = "AI Scouted Story"

    return {
        "clip_probes": clip_probes,
        "theme_tags": theme_tags,
        "expect_colorful": expect_colorful,
        "expect_monochrome": expect_monochrome,
        "expect_aerial": expect_aerial,
        "has_doors_windows": has_doors_windows,
        "has_horses": has_horses,
        "suggested_collection_name": suggested_name,
        "parsed_teach": parsed_teach,
    }


@app.post("/api/ai/scout")
async def scout_archive_and_build_story(payload: ScoutArchiveRequest):
    """
    Multi-Signal "Voice Archive Scout" + Smart Auto-Collection / Story Builder.
    Combines:
      1. Seed photos' OpenCLIP visual centroid + color histogram (when 1+ photos are selected)
      2. Decomposed OpenCLIP semantic, secondary-element, and framing probes across all 849 vectors
      3. Color vibrancy / monochrome signature alignment from color_signatures.npy
      4. Existing tag/location confirmation (without gating out untagged photos!)
    Applies smart adaptive thresholding, enriches discovered matches in SQLite, and auto-builds a Collection.
    """
    prompt_text = (payload.prompt or "").strip()
    if not prompt_text and not payload.seed_photo_ids:
        raise HTTPException(status_code=400, detail="Provide a spoken/typed description or select seed photos to scout.")

    decomp = _decompose_scout_prompt(prompt_text)
    clip_probes = decomp["clip_probes"]
    theme_tags = decomp["theme_tags"]
    collection_title = (payload.collection_name or "").strip() or decomp["suggested_collection_name"]

    JOB_MANAGER.start_job(
        task_type="ai_scout",
        title=f"AI Archive Scout: {collection_title}",
        total=849,
        phase="Encoding OpenCLIP visual & compositional probes...",
    )

    try:
        norm_vectors = get_normalized_vectors_matrix()
        color_sigs = get_color_signatures_matrix()
        if len(norm_vectors) == 0:
            JOB_MANAGER.finish_job(error="Vector matrix is empty", phase="Error")
            raise HTTPException(status_code=500, detail="OpenCLIP vector matrix is empty")

        # 1. Encode decomposed text probes with OpenCLIP
        text_embs_dict = encode_text_batch(clip_probes)  # Dict[str, (768,)]
        text_embs = np.stack(
            [text_embs_dict[p] for p in clip_probes if p in text_embs_dict],
            axis=0,
        )  # (P, 768)
        probe_sims_matrix = np.dot(norm_vectors, text_embs.T)  # (N, P)
        # Combine max probe match (0.65) + mean probe match (0.35) so specialized detail probes shine
        text_probe_scores = (0.65 * np.max(probe_sims_matrix, axis=1)) + (0.35 * np.mean(probe_sims_matrix, axis=1))

        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()
        sql = """
            SELECT file_path, file_hash, sibling_path, catalog_name,
                   exif_time, shoot_date, status, camera_make, camera_model,
                   focal_length, shutter_speed, aperture, iso,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   star_rating, color_label, pick_flag,
                   lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                   user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                   thumb_360_path, preview_1600_path,
                   sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                   laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                   sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                   vector_index, in_keepers, file_mtime, updated_at
            FROM photo_records
            WHERE status != 'failed'
        """
        all_rows = [dict(r) for r in cursor.execute(sql).fetchall()]
        conn.close()

        # 2. Compute optional Seed Visual Centroid & Seed Color Centroid
        seed_ids_set = set(payload.seed_photo_ids or [])
        seed_vectors: List[np.ndarray] = []
        seed_hists: List[np.ndarray] = []
        seed_hashes: set = set()

        if seed_ids_set:
            for r in all_rows:
                if r.get("file_hash") in seed_ids_set or r.get("file_path") in seed_ids_set:
                    seed_hashes.add(r.get("file_hash") or r.get("file_path"))
                    v_idx = r.get("vector_index")
                    if v_idx is not None and 0 <= int(v_idx) < len(norm_vectors):
                        seed_vectors.append(norm_vectors[int(v_idx)])
                        if int(v_idx) < len(color_sigs):
                            seed_hists.append(color_sigs[int(v_idx), :24].astype(np.float32))

        if seed_vectors:
            centroid_vec = np.mean(np.stack(seed_vectors, axis=0), axis=0)
            norm_c = float(np.linalg.norm(centroid_vec))
            if norm_c > 1e-6:
                centroid_vec = centroid_vec / norm_c
            seed_sim_scores = np.dot(norm_vectors, centroid_vec)
        else:
            seed_sim_scores = None

        seed_hist_centroid = np.mean(np.stack(seed_hists, axis=0), axis=0) if seed_hists else None

        # Build keyword tokens for checking whether a photo was ALREADY tagged vs NEWLY discovered visually
        theme_tokens_lower = set()
        for t in theme_tags:
            for w in re.split(r"[\s&,/|-]+", t.lower()):
                if len(w) >= 4 and w not in ("architectural", "wildlife", "livestock", "study", "detail", "form"):
                    theme_tokens_lower.add(w)
        if decomp["has_doors_windows"]:
            theme_tokens_lower.update({"door", "doors", "doorway", "window", "windows", "shutter", "shutters", "facade", "portal"})
        if decomp["has_horses"]:
            theme_tokens_lower.update({"horse", "horses", "equine", "mustang", "stallion", "mare", "equestrian"})

        negated_query_set = {n.lower() for n in (decomp["parsed_teach"].get("negated_tags") or [])}
        scout_countable_groups = _extract_countable_query_targets(prompt_text) if not seed_ids_set else []

        scored_candidates: List[Dict[str, Any]] = []
        total_rows = len(all_rows)

        for idx, r in enumerate(all_rows):
            if idx % 100 == 0:
                JOB_MANAGER.update_progress(
                    processed=idx,
                    total=total_rows,
                    current_file=Path(r.get("file_path") or "").name,
                    phase=f"Scoring {total_rows} photos across visual, compositional & color vectors...",
                )
            v_idx = r.get("vector_index")
            if v_idx is None or int(v_idx) < 0 or int(v_idx) >= len(norm_vectors):
                continue
            vi = int(v_idx)

            if scout_countable_groups and not _passes_countable_subject_search_gate(r, scout_countable_groups):
                continue

            # Skip photos that explicitly have one of the query's negated tags or where user negated this theme
            photo_negated = {str(n).strip().lower() for n in _parse_json_list(r.get("negated_tags"))}
            if theme_tokens_lower and (photo_negated & theme_tokens_lower):
                continue

            t_sim = float(text_probe_scores[vi])
            s_sim = float(seed_sim_scores[vi]) if seed_sim_scores is not None else t_sim

            # Combine OpenCLIP text probe similarity + seed visual centroid similarity
            if seed_sim_scores is not None and prompt_text:
                base_visual_sim = (0.62 * t_sim) + (0.38 * s_sim)
            elif seed_sim_scores is not None:
                base_visual_sim = s_sim
            else:
                base_visual_sim = t_sim

            # Color vibrancy / palette alignment bonus
            color_bonus = 0.0
            sat_val = float(color_sigs[vi, 24]) if vi < len(color_sigs) else 0.25
            colorfulness = float(r.get("colorfulness_score") or 30.0)
            is_mono = bool(r.get("is_monochrome"))

            if decomp["expect_colorful"]:
                if is_mono:
                    color_bonus -= 0.06
                else:
                    # Reward high saturation & colorfulness
                    color_bonus += min(0.035, (sat_val * 0.04) + min(colorfulness / 100.0, 1.0) * 0.015)
            elif decomp["expect_monochrome"]:
                color_bonus += 0.035 if is_mono else -0.05

            if seed_hist_centroid is not None and vi < len(color_sigs):
                cand_hist = color_sigs[vi, :24].astype(np.float32)
                hist_sim = float(np.clip(np.dot(seed_hist_centroid, cand_hist), 0.0, 1.0))
                color_bonus += (hist_sim - 0.5) * 0.025

            # Check existing tags (for confirmation badge + modest boost, without penalizing untagged photos!)
            existing_bag = " ".join([
                str(r.get("title") or ""),
                str(r.get("caption") or ""),
                str(r.get("specific_location") or ""),
                str(r.get("city") or ""),
                str(r.get("state_region") or ""),
                str(r.get("country") or ""),
                " ".join(_parse_json_list(r.get("user_taught_tags"))),
                " ".join(_parse_json_list(r.get("key_subjects"))),
                " ".join(_parse_json_list(r.get("existing_keywords"))),
                " ".join(_parse_json_list(r.get("lrcat_keywords"))),
            ]).lower()

            if negated_query_set and any(neg_tok in existing_bag for neg_tok in negated_query_set):
                continue

            already_has_theme_tag = bool(
                theme_tokens_lower and any(re.search(rf"\b{re.escape(tok)}\b", existing_bag) for tok in theme_tokens_lower)
            )
            is_seed = (r.get("file_hash") in seed_hashes) or (r.get("file_path") in seed_hashes)

            tag_bonus = 0.018 if already_has_theme_tag else 0.0
            seed_bonus = 0.05 if is_seed else 0.0

            scout_score = base_visual_sim + color_bonus + tag_bonus + seed_bonus
            r["_scout_score"] = float(scout_score)
            r["_raw_clip_sim"] = float(t_sim)
            r["_seed_clip_sim"] = float(s_sim)
            r["_already_tagged"] = already_has_theme_tag
            r["_is_seed"] = is_seed
            scored_candidates.append(r)

        scored_candidates.sort(key=lambda x: x["_scout_score"], reverse=True)

        # 3. Smart Adaptive Thresholding (z-score + largest natural knee drop in top 8..36 window)
        scores_arr = np.array([c["_scout_score"] for c in scored_candidates], dtype=np.float32)
        mean_s = float(np.mean(scores_arr)) if len(scores_arr) > 0 else 0.0
        std_s = float(np.std(scores_arr)) if len(scores_arr) > 0 else 1.0
        z_Floor = mean_s + (1.35 * std_s)
        top_score = float(scores_arr[0]) if len(scores_arr) > 0 else 0.0

        # Find natural elbow/knee between rank 8 and 32
        best_k = 18
        if len(scores_arr) > 12:
            window_end = min(35, len(scores_arr) - 1)
            drops = scores_arr[6:window_end] - scores_arr[7:window_end + 1]
            knee_offset = int(np.argmax(drops))
            knee_k = 7 + knee_offset
            # Combine z-score cutoff and knee cutoff cleanly
            z_count = int(np.sum(scores_arr >= max(z_Floor, top_score - 0.055)))
            best_k = max(8, min(32, max(knee_k, z_count)))
        else:
            best_k = len(scores_arr)

        selected_matches = scored_candidates[:best_k]

        if payload.approved_tags is not None:
            theme_tags = [str(t).strip() for t in payload.approved_tags if str(t or "").strip()]

        if payload.approved_photo_ids is not None:
            approved_id_set = {str(pid).strip() for pid in payload.approved_photo_ids if str(pid or "").strip()}
            selected_matches = [
                m for m in scored_candidates
                if (str(m.get("file_hash") or "") in approved_id_set) or (str(m.get("file_path") or "") in approved_id_set)
            ]

        is_preview_only = bool(payload.preview_only)

        # Snapshot affected photos before Scout tag enrichment so 1-Click Undo (Cmd+Z) can revert
        if not is_preview_only and payload.enrich_tags and theme_tags and selected_matches:
            match_ids = [m.get("file_hash") or m.get("file_path") for m in selected_matches if m.get("file_hash") or m.get("file_path")]
            record_undo_snapshot(
                db_path=DEFAULT_DB_PATH,
                action_type="ai_scout_enrich",
                description=f"AI Archive Scout tag enrichment ({len(match_ids)} photos): {collection_title}",
                photo_ids=match_ids,
                create_vault_backup=False,
            )

        conn = get_db_connection(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        # 4. Tag Enrichment in SQLite for discovered matches
        enriched_count = 0
        if not is_preview_only and payload.enrich_tags and theme_tags and selected_matches:
            for m in selected_matches:
                fp = m["file_path"]
                prev_taught = _parse_json_list(m.get("user_taught_tags"))
                prev_ks = _parse_json_list(m.get("key_subjects"))
                prev_ek = _parse_json_list(m.get("existing_keywords"))

                changed = False
                for t in theme_tags[:6]:
                    if t.lower() not in {x.lower() for x in prev_ks}:
                        prev_ks.append(t)
                        changed = True
                    if t.lower() not in {x.lower() for x in prev_ek}:
                        prev_ek.append(t)
                        changed = True
                if changed:
                    m["key_subjects"] = json.dumps(prev_ks)
                    m["existing_keywords"] = json.dumps(prev_ek)
                    cursor.execute(
                        """
                        UPDATE photo_records
                        SET key_subjects = ?,
                            existing_keywords = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE file_path = ?
                        """,
                        (m["key_subjects"], m["existing_keywords"], fp),
                    )
                    enriched_count += 1
            conn.commit()

        # 5. Auto-Create or Update Curated Collection / Story in SQLite
        created_collection = None
        if not is_preview_only and payload.auto_create_collection and selected_matches:
            existing_col = cursor.execute(
                "SELECT * FROM collections WHERE LOWER(name) = LOWER(?)", (collection_title,)
            ).fetchone()
            hero_id = selected_matches[0].get("file_hash") or selected_matches[0].get("file_path")
            story_desc = f"AI Scouted Story ({len(selected_matches)} photos) — \"{prompt_text}\""
            if existing_col:
                cid = existing_col["id"]
                cursor.execute(
                    "UPDATE collections SET description = ?, cover_photo_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (story_desc, hero_id, cid),
                )
                cursor.execute("DELETE FROM collection_items WHERE collection_id = ?", (cid,))
            else:
                cursor.execute(
                    """
                    INSERT INTO collections (name, description, cover_photo_id, created_at, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (collection_title, story_desc, hero_id),
                )
                cid = cursor.lastrowid

            for order_idx, m in enumerate(selected_matches):
                pid = m.get("file_hash") or m.get("file_path")
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO collection_items (collection_id, photo_id, sort_order, added_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (cid, pid, order_idx),
                )
            conn.commit()
            col_row = dict(cursor.execute("SELECT * FROM collections WHERE id = ?", (cid,)).fetchone())
            created_collection = _serialize_collection_row(conn, col_row)

        conn.close()

        # Serialize match items with explicit discovery badges
        serialized_matches: List[Dict[str, Any]] = []
        newly_discovered_count = 0
        already_tagged_count = 0

        for m in selected_matches:
            already_tagged = bool(m.pop("_already_tagged", False))
            is_seed = bool(m.pop("_is_seed", False))
            s_score = round(float(m.pop("_scout_score", 0.0)), 4)
            c_sim = round(float(m.pop("_raw_clip_sim", 0.0)), 4)
            seed_sim = round(float(m.pop("_seed_clip_sim", 0.0)), 4)

            if already_tagged:
                already_tagged_count += 1
            else:
                newly_discovered_count += 1

            _serialize_photo_item(m)
            m["scout_score"] = s_score
            m["clip_similarity"] = c_sim
            m["seed_similarity"] = seed_sim
            m["is_seed"] = is_seed
            m["scout_match_type"] = "seed" if is_seed else ("existing_tag" if already_tagged else "visual_discovery")
            serialized_matches.append(m)

        response_payload = {
            "status": "ok",
            "preview_only": is_preview_only,
            "prompt": prompt_text,
            "collection_name": collection_title,
            "collection_id": created_collection.get("id") if isinstance(created_collection, dict) else None,
            "collection": created_collection,
            "total_matches": len(serialized_matches),
            "matched_count": len(serialized_matches),
            "newly_discovered_count": newly_discovered_count,
            "visual_ai_count": newly_discovered_count,
            "already_tagged_count": already_tagged_count,
            "tagged_count": already_tagged_count,
            "enriched_count": enriched_count,
            "enriched_tags": theme_tags,
            "clip_probes_used": clip_probes,
            "adaptive_cutoff": round(float(selected_matches[-1]["scout_score"]), 4) if selected_matches else 0.0,
            "undo_status": get_undo_status(DEFAULT_DB_PATH),
            "matches": serialized_matches,
            "photos": serialized_matches,
        }
        JOB_MANAGER.finish_job(
            result={"total_matches": len(serialized_matches), "collection_name": collection_title},
            phase=f"Scouted {len(serialized_matches)} photos ({newly_discovered_count} new visual discoveries)",
        )
        return response_payload
    except HTTPException:
        raise
    except Exception as exc:
        logging.exception("AI Scout failed")
        JOB_MANAGER.finish_job(error=str(exc), phase="Scout Error")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"AI Scout error: {exc}"},
        )


@app.get("/api/undo/status")
async def get_studio_undo_status():
    return get_undo_status(DEFAULT_DB_PATH)


@app.post("/api/undo")
async def trigger_studio_undo():
    res = pop_and_restore_undo(DEFAULT_DB_PATH)
    if res.get("status") == "empty":
        raise HTTPException(status_code=400, detail=res.get("message", "No actions in undo history."))

    restored_paths = res.get("restored_file_paths") or []
    restored_photos: List[Dict[str, Any]] = []
    if restored_paths:
        conn = get_db_connection(DEFAULT_DB_PATH)
        for i in range(0, min(len(restored_paths), 500), 400):
            chunk_p = restored_paths[i : i + 400]
            placeholders = ",".join("?" for _ in chunk_p)
            sql = f"""
                SELECT file_path, file_hash, sibling_path, catalog_name,
                       exif_time, shoot_date, status, camera_make, camera_model,
                       focal_length, shutter_speed, aperture, iso,
                       gps_lat, gps_lon, gps_alt, gps_ground_truth, is_aerial, is_screenshot,
                       primary_category, sub_category, confidence_score,
                       title, caption, sub_location, specific_location, city, state_region, country,
                       star_rating, color_label, pick_flag,
                       lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                       user_context_notes, user_taught_tags, negated_tags, subject_boxes, verified_subjects, location_provenance,
                       thumb_360_path, preview_1600_path,
                       sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                       laion_aesthetic_score, keepers_taste_bonus, aesthetic_score,
                       sequence_id, sequence_frame_index, sequence_length, is_sequence_hero,
                       vector_index, in_keepers, file_mtime, updated_at
                FROM photo_records
                WHERE file_path IN ({placeholders})
            """
            fetched = [dict(r) for r in conn.execute(sql, chunk_p).fetchall()]
            for item in fetched:
                restored_photos.append(_serialize_photo_item(item))
        conn.close()

    res["restored_photos"] = restored_photos
    return res


@app.get("/api/system/backups")
async def get_rolling_vault_backups():
    backups = list_vault_backups()
    return {
        "status": "ok",
        "count": len(backups),
        "backups": backups,
    }


@app.get("/api/errors")
async def get_ingestion_errors(limit: int = 100):
    conn = get_db_connection(DEFAULT_DB_PATH)
    rows = conn.execute(
        "SELECT * FROM ingestion_errors ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return {"errors": [dict(r) for r in rows]}


@app.post("/api/backup")
async def trigger_das_backup():
    cfg = load_settings()
    das_dir = Path(cfg["paths"].get("das_backup_dir", "/Volumes/Mitch_DAS_Archive/_AI_Catalog_Backup"))
    try:
        report = backup_catalog_to_das(
            das_backup_dir=das_dir,
            db_path=DEFAULT_DB_PATH,
            vectors_path=DEFAULT_VECTORS_PATH,
        )
        return {"status": "ok", "report": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ==============================================================================
# 9B. 1-CLICK REMOTE GIT AUTO-UPDATER & DATA VAULT STATUS
# ==============================================================================
def _run_git_cmd(args: List[str], timeout: float = 3.0) -> Tuple[int, str, str]:
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return res.returncode, (res.stdout or "").strip(), (res.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


@app.get("/api/system/update-check")
async def check_system_update():
    """
    Checks if a remote Git update is available from origin (with a 3s timeout so offline
    operation never hangs) and returns current version & Data Vault status.
    """
    v_info = get_version_info()
    rc_head, current_commit, _ = _run_git_cmd(["rev-parse", "--short", "HEAD"], timeout=2.0)
    rc_branch, branch, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], timeout=2.0)
    if rc_branch != 0 or not branch or branch == "HEAD":
        branch = "main"

    # Non-blocking fetch with 3.0s timeout
    fetch_rc, _, fetch_err = _run_git_cmd(["fetch", "origin", branch, "--quiet"], timeout=3.0)
    if fetch_rc != 0:
        # Try generic git fetch origin
        fetch_rc, _, fetch_err = _run_git_cmd(["fetch", "origin", "--quiet"], timeout=3.0)

    remote_ref = f"origin/{branch}"
    rc_rem, remote_commit, _ = _run_git_cmd(["rev-parse", "--short", remote_ref], timeout=2.0)
    if rc_rem != 0:
        # Fallback to origin/main
        remote_ref = "origin/main"
        rc_rem, remote_commit, _ = _run_git_cmd(["rev-parse", "--short", remote_ref], timeout=2.0)

    commits_behind = 0
    changelog: List[str] = []
    remote_version = v_info.get("version", APP_VERSION)

    if rc_rem == 0 and remote_commit:
        rc_cnt, cnt_str, _ = _run_git_cmd(["rev-list", "--count", f"HEAD..{remote_ref}"], timeout=2.0)
        if rc_cnt == 0 and cnt_str.isdigit():
            commits_behind = int(cnt_str)
        if commits_behind > 0:
            rc_log, log_out, _ = _run_git_cmd(["log", f"HEAD..{remote_ref}", "--oneline", "-n", "8"], timeout=2.0)
            if rc_log == 0 and log_out:
                changelog = [line.strip() for line in log_out.splitlines() if line.strip()]
            rc_ver, ver_out, _ = _run_git_cmd(["show", f"{remote_ref}:version.json"], timeout=2.0)
            if rc_ver == 0 and ver_out:
                try:
                    rem_v = json.loads(ver_out)
                    if isinstance(rem_v, dict) and rem_v.get("version"):
                        remote_version = str(rem_v["version"])
                except Exception:
                    pass

    return {
        "status": "ok",
        "app_name": v_info.get("app_name", APP_NAME),
        "version": v_info.get("version", APP_VERSION),
        "remote_version": remote_version,
        "branch": branch,
        "current_commit": current_commit if rc_head == 0 else None,
        "remote_commit": remote_commit if rc_rem == 0 else None,
        "commits_behind": commits_behind,
        "update_available": bool(commits_behind > 0),
        "changelog": changelog,
        "offline_or_no_remote": bool(fetch_rc != 0 and rc_rem != 0),
        "data_vault_dir": str(DATA_VAULT_DIR),
        "db_path": str(DEFAULT_DB_PATH),
    }


@app.post("/api/system/update-apply")
async def apply_system_update():
    """
    Safely stashes any local working-tree clutter, pulls the latest code & pre-built UI
    from origin, installs any updated Python dependencies, and restarts the server cleanly.
    User databases and thumbnails in ~/Library/Application Support/MRDarkroom are untouched.
    """
    ensure_data_vault_migrated()

    _, branch, _ = _run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], timeout=2.0)
    if not branch or branch == "HEAD":
        branch = "main"

    # Stash local untracked/modified code files (never touches external Data Vault)
    _run_git_cmd(["stash", "--include-untracked"], timeout=10.0)

    pull_rc, pull_out, pull_err = _run_git_cmd(["pull", "--rebase", "origin", branch], timeout=30.0)
    if pull_rc != 0:
        pull_rc, pull_out, pull_err = _run_git_cmd(["pull", "--rebase", "origin", "main"], timeout=30.0)

    # Check if requirements.txt exists and update quickly if needed
    req_file = PROJECT_ROOT / "requirements.txt"
    venv_pip = PROJECT_ROOT / ".venv" / "bin" / "pip"
    if req_file.exists() and venv_pip.exists():
        try:
            subprocess.run(
                [str(venv_pip), "install", "-q", "-r", str(req_file)],
                cwd=str(PROJECT_ROOT),
                timeout=45.0,
                capture_output=True,
            )
        except Exception as exc:
            logging.warning(f"Dependency update skipped/warning: {exc}")

    def _delayed_restart():
        time.sleep(0.9)
        logging.info("Restarting MR Darkroom server process after update...")
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as exc:
            logging.error(f"Restart execv failed: {exc}")

    threading.Thread(target=_delayed_restart, daemon=True).start()

    v_info = get_version_info()
    return {
        "status": "updating",
        "message": "Updating MR Darkroom... Reloading in 3 seconds",
        "version": v_info.get("version", APP_VERSION),
        "pull_output": pull_out or "Up to date.",
    }



# ==============================================================================
# 10. MOUNT REACT PRODUCTION BUILD
# ==============================================================================
UI_DIST = PROJECT_ROOT / "ui" / "dist"
if UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(UI_DIST), html=True), name="ui")
else:
    @app.get("/")
    async def fallback_root():
        return {
            "status": "ready",
            "message": "FastAPI Studio backend is running. Build UI with 'npm run build' in ui/.",
            "api_docs": "/api/docs",
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8501, reload=False)
