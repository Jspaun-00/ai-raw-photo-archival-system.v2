#!/usr/bin/env python3
"""
Master Ingestion & AI Enrichment Pipeline Orchestrator (pipeline.py — v3.0)
AI Photo & RAW Archival System (v3.0) — Mitch Rouse Archive

Architecture:
- Stage 1 (Fast Extraction, Full-Res 90th-Percentile Patch Sharpness, Persistent 360px/1600px WebPs,
           Omni-Metadata + Read-Only .lrcat Harvesting, .IIQ+.TIF Sibling Pairing,
           Batched Apple Silicon MPS OpenCLIP ViT-L-14 Float16 Vectors + LAION Aesthetic V2 MLP,
           Keepers Personal Taste Calibration, Date-Bounded & Camera-Bounded Sequence Grouping):
  Runs ZERO 7B LLM calls and NEVER modifies or moves original RAW/TIF files.
- Stage 2 (Self-Learning Metadata Centroid & Helicopter Orbit Time-Window Propagation +
           35-Frame Strafing Run Qwen2.5-VL Stride):
  Runs in the background with pause/resume support, injecting verified ground-truth location/project
  names into Qwen2.5-VL and propagating semantic tags across sequence siblings while strictly
  preserving each frame's own existing keywords, Lightroom tags, and sharpness status.
- Optional Explicit Additive Metadata Sync (`--sync-xmp`):
  Uses `+=` additive ExifTool semantics via `xmp_sync.py` only when explicitly requested.
"""

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

from config_paths import DEFAULT_SETTINGS_PATH
from db_schema import (
    DEFAULT_DB_PATH,
    DEFAULT_PREVIEWS_1600_DIR,
    DEFAULT_THUMBS_360_DIR,
    DEFAULT_VECTORS_PATH,
    PROJECT_ROOT,
    backup_catalog_to_das,
    init_and_migrate_db,
)
from stage1_engine import (
    detect_hardware_profile,
    run_stage1_pipeline,
)
from stage2_vlm import (
    reassess_records_fast,
    run_stage2_vlm,
)
from xmp_sync import (
    sync_pending_records_batch,
)

os.environ["PATH"] = f"{PROJECT_ROOT}/bin:{PROJECT_ROOT}/.venv/bin:{os.environ.get('PATH', '')}"

CONFIG_PATH = DEFAULT_SETTINGS_PATH if DEFAULT_SETTINGS_PATH.exists() else (PROJECT_ROOT / "config" / "settings.yaml")
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "pipeline.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def load_settings() -> Dict[str, Any]:
    default_cfg: Dict[str, Any] = {
        "paths": {
            "source_dir": str(Path.home() / "Desktop" / "Photo"),
            "das_backup_dir": "/Volumes/Mitch_DAS_Archive/_AI_Catalog_Backup",
            "db_path": str(DEFAULT_DB_PATH),
            "vectors_path": str(DEFAULT_VECTORS_PATH),
            "thumbs_360_dir": str(DEFAULT_THUMBS_360_DIR),
            "previews_1600_dir": str(DEFAULT_PREVIEWS_1600_DIR),
        },
        "catalogs": [
            {
                "name": "Desktop_Photo",
                "path": str(Path.home() / "Desktop" / "Photo"),
                "is_keepers": False,
            }
        ],
        "processing": {
            "vlm_model": "qwen2.5vl:7b",
            "sharpness_unsharp_threshold": 3.5,
            "strafing_vlm_stride_frames": 35,
            "strafing_clip_drop_threshold": 0.85,
            "helicopter_orbit_window_seconds": 180.0,
            "centroid_similarity_threshold": 0.84,
        },
    }
    if CONFIG_PATH.exists() and yaml is not None:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            for section in ("paths", "processing"):
                if section in loaded and isinstance(loaded[section], dict):
                    default_cfg[section].update(loaded[section])
            if "catalogs" in loaded and isinstance(loaded["catalogs"], list):
                default_cfg["catalogs"] = loaded["catalogs"]
        except Exception as exc:
            logging.warning(f"Failed to parse settings.yaml: {exc}")
    return default_cfg


def run_pipeline(
    custom_source: Optional[Path] = None,
    catalog_name: Optional[str] = None,
    force_rescan: bool = False,
    stage1_only: bool = False,
    stage2_only: bool = False,
    sync_xmp: bool = False,
    backup_das: bool = False,
    db_path: Optional[Path] = None,
    vectors_path: Optional[Path] = None,
    thumbs_360_dir: Optional[Path] = None,
    previews_1600_dir: Optional[Path] = None,
    mock_vlm_fn: Optional[Callable[[Path, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Runs the v3.0 Two-Stage Archival Pipeline:
    - Stage 1: Fast Extraction, 90th-Percentile Sharpness, Persistent 360/1600 WebPs,
      Omni-Metadata + Read-Only .lrcat Harvesting, .IIQ+.TIF Sibling Pairing,
      MPS OpenCLIP ViT-L-14 Float16 Vectors + LAION Aesthetic V2 MLP, Keepers Taste Calibration,
      and Date/Camera-Bounded Sequence Grouping.
    - Stage 2: Self-Learning Metadata Centroid & Helicopter Orbit Time-Window Propagation +
      35-Frame Strafing Sequence Qwen2.5-VL Enrichment.
    """
    t0 = time.time()
    cfg = load_settings()

    active_db = Path(db_path or cfg["paths"]["db_path"])
    active_vecs = Path(vectors_path or cfg["paths"]["vectors_path"])
    active_t360 = Path(thumbs_360_dir or cfg["paths"]["thumbs_360_dir"])
    active_p1600 = Path(previews_1600_dir or cfg["paths"]["previews_1600_dir"])

    init_and_migrate_db(active_db)
    hw = detect_hardware_profile()

    sharp_thresh = float(cfg["processing"].get("sharpness_unsharp_threshold", 3.5))
    vlm_model = str(cfg["processing"].get("vlm_model", "qwen2.5vl:7b"))
    stride = int(cfg["processing"].get("strafing_vlm_stride_frames", 35))
    clip_drop = float(cfg["processing"].get("strafing_clip_drop_threshold", 0.85))
    orbit_win = float(cfg["processing"].get("helicopter_orbit_window_seconds", 180.0))
    centroid_sim = float(cfg["processing"].get("centroid_similarity_threshold", 0.84))

    stage1_reports: List[Dict[str, Any]] = []
    stage2_report: Optional[Dict[str, Any]] = None
    xmp_sync_report: Optional[Dict[str, Any]] = None
    das_backup_report: Optional[Dict[str, Any]] = None

    # Determine target catalogs to scan for Stage 1
    if not stage2_only:
        targets: List[ Dict[str, str] ] = []
        if custom_source is not None:
            src_p = Path(custom_source).expanduser().resolve()
            cat_label = catalog_name or src_p.name
            targets.append({"name": cat_label, "path": str(src_p)})
        else:
            for c in cfg.get("catalogs", []):
                c_name = c.get("name", "Default")
                c_path = Path(c.get("path", "")).expanduser()
                if catalog_name and c_name != catalog_name:
                    continue
                if c_path.exists():
                    targets.append({"name": c_name, "path": str(c_path.resolve())})

        for tgt in targets:
            src_path = Path(tgt["path"])
            if not src_path.exists():
                logging.warning(f"Catalog source path does not exist: {src_path}")
                continue
            s1_res = run_stage1_pipeline(
                source_dir=src_path,
                catalog_name=tgt["name"],
                db_path=active_db,
                vectors_path=active_vecs,
                thumbs_360_dir=active_t360,
                previews_1600_dir=active_p1600,
                sharpness_threshold=sharp_thresh,
                force_rescan=force_rescan,
            )
            # Invariant 3: Automatically run v4.0 4-Pass Cascade + Entity Clustering on newly ingested catalog
            try:
                fast_res = reassess_records_fast(
                    db_path=active_db,
                    vectors_path=active_vecs,
                    catalog_name=tgt["name"],
                )
                s1_res["v4_cascade_summary"] = fast_res
            except Exception as exc:
                logging.warning(f"Automatic v4.0 cascade after Stage 1 failed: {exc}")
            stage1_reports.append(s1_res)

    # Run Stage 2 unless --stage1-only was requested
    if not stage1_only:
        stage2_report = run_stage2_vlm(
            db_path=active_db,
            vectors_path=active_vecs,
            catalog_name=catalog_name,
            vlm_model=vlm_model,
            strafing_stride=stride,
            similarity_drop_threshold=clip_drop,
            orbit_window_seconds=orbit_win,
            centroid_similarity_threshold=centroid_sim,
            force_rerun=force_rescan,
            mock_vlm_fn=mock_vlm_fn,
        )

    # Run Additive XMP Sync ONLY if explicitly requested
    if sync_xmp:
        xmp_sync_report = sync_pending_records_batch(
            db_path=active_db,
            catalog_name=catalog_name,
        )

    # Run DAS Backup ONLY if explicitly requested
    if backup_das:
        das_dir = Path(cfg["paths"]["das_backup_dir"])
        das_backup_report = backup_catalog_to_das(
            das_backup_dir=das_dir,
            db_path=active_db,
            vectors_path=active_vecs,
        )

    summary = {
        "hardware_profile": hw,
        "stage1_reports": stage1_reports,
        "stage2_report": stage2_report,
        "xmp_sync_report": xmp_sync_report,
        "das_backup_report": das_backup_report,
        "total_elapsed_seconds": round(time.time() - t0, 2),
    }
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Photo & RAW Archival Pipeline Orchestrator (v3.0)")
    parser.add_argument("--source", type=str, default=None, help="Custom source directory containing photos")
    parser.add_argument("--catalog", type=str, default=None, help="Catalog name (e.g. Keepers, Aerial_Working)")
    parser.add_argument("--force", action="store_true", help="Force a fresh re-scan of Stage 1 / Stage 2")
    parser.add_argument("--stage1-only", action="store_true", help="Run Stage 1 only (Zero LLM calls; UI immediately usable)")
    parser.add_argument("--stage2-only", action="store_true", help="Run Stage 2 VLM & self-learning propagation only")
    parser.add_argument("--sync-xmp", action="store_true", help="Explicitly embed approved tags additively (+=) via ExifTool")
    parser.add_argument("--backup-das", action="store_true", help="Mirror photo_archive.db and vectors.npy to DAS backup dir")
    args = parser.parse_args()

    result = run_pipeline(
        custom_source=Path(args.source) if args.source else None,
        catalog_name=args.catalog,
        force_rescan=args.force,
        stage1_only=args.stage1_only,
        stage2_only=args.stage2_only,
        sync_xmp=args.sync_xmp,
        backup_das=args.backup_das,
    )
    print(json.dumps(result, indent=2))
