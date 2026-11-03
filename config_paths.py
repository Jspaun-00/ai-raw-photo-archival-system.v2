#!/usr/bin/env python3
"""
Centralized Data Vault & Path Configuration (config_paths.py)
MR Darkroom — Standalone macOS Application & Remote Git Auto-Update Architecture

Resolves all persistent database, vector matrix, WebP preview, model, and settings paths
to the user's macOS Application Support vault:
    ~/Library/Application Support/MRDarkroom/

Automatically performs a zero-downtime migration from `./data/` into the external Data Vault
and maintains `./data` as a transparent symlink so legacy relative paths continue to work
seamlessly while Git updates (`git pull` / `git reset`) never touch user data.
"""

import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict

APP_NAME = "MR Darkroom"
APP_VERSION = "4.0.0"

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_VAULT_DIR = Path.home() / "Library" / "Application Support" / "MRDarkroom"
LEGACY_DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_DB_PATH = DATA_VAULT_DIR / "photo_archive.db"
DEFAULT_VECTORS_PATH = DATA_VAULT_DIR / "vectors.npy"
DEFAULT_CROP_VECTORS_PATH = DATA_VAULT_DIR / "crop_vectors.npy"
DEFAULT_CROP_BOXES_PATH = DATA_VAULT_DIR / "crop_boxes.npy"
DEFAULT_COLOR_SIGS_PATH = DATA_VAULT_DIR / "color_signatures.npy"
DEFAULT_THUMBS_360_DIR = DATA_VAULT_DIR / "previews" / "thumbs_360"
DEFAULT_PREVIEWS_1600_DIR = DATA_VAULT_DIR / "previews" / "previews_1600"
DEFAULT_MODELS_DIR = DATA_VAULT_DIR / "models"
DEFAULT_SETTINGS_PATH = DATA_VAULT_DIR / "settings.yaml"
VERSION_FILE_PATH = PROJECT_ROOT / "version.json"


def _merge_move_tree(src: Path, dst: Path) -> None:
    """Recursively moves contents of `src` into `dst` without overwriting newer files."""
    if src.is_dir() and not src.is_symlink():
        dst.mkdir(parents=True, exist_ok=True)
        for child in list(src.iterdir()):
            _merge_move_tree(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            pass
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            # Keep whichever file is larger or newer
            try:
                if src.stat().st_mtime >= dst.stat().st_mtime or src.stat().st_size > dst.stat().st_size:
                    shutil.move(str(src), str(dst))
                else:
                    src.unlink()
            except Exception:
                pass
        else:
            shutil.move(str(src), str(dst))


def ensure_data_vault_migrated() -> Path:
    """
    Ensures `~/Library/Application Support/MRDarkroom/` exists, migrates any existing
    files from `./data/` into the external vault, and replaces `./data` with a symlink.
    """
    DATA_VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. If ./data is a physical directory (not yet a symlink), migrate its contents
    if LEGACY_DATA_DIR.exists() and not LEGACY_DATA_DIR.is_symlink():
        legacy_db = LEGACY_DATA_DIR / "photo_archive.db"
        if legacy_db.exists():
            try:
                conn = sqlite3.connect(str(legacy_db), timeout=10.0)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.close()
            except Exception as exc:
                logging.warning(f"WAL checkpoint before Data Vault migration warning: {exc}")

        for item in list(LEGACY_DATA_DIR.iterdir()):
            _merge_move_tree(item, DATA_VAULT_DIR / item.name)

        try:
            shutil.rmtree(str(LEGACY_DATA_DIR))
        except Exception as exc:
            logging.warning(f"Could not remove legacy data dir cleanly: {exc}")

    # 2. Ensure ./data symlink points to ~/Library/Application Support/MRDarkroom
    if not LEGACY_DATA_DIR.exists() and not LEGACY_DATA_DIR.is_symlink():
        try:
            LEGACY_DATA_DIR.symlink_to(DATA_VAULT_DIR, target_is_directory=True)
        except Exception as exc:
            logging.warning(f"Could not create ./data symlink to Data Vault: {exc}")

    # 3. Ensure required subdirectories exist inside Data Vault
    DEFAULT_THUMBS_360_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PREVIEWS_1600_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 4. Sync config/settings.yaml to Data Vault if not yet present
    repo_settings = PROJECT_ROOT / "config" / "settings.yaml"
    if repo_settings.exists() and not DEFAULT_SETTINGS_PATH.exists():
        try:
            shutil.copy2(str(repo_settings), str(DEFAULT_SETTINGS_PATH))
        except Exception as exc:
            logging.warning(f"Could not copy settings.yaml to Data Vault: {exc}")

    return DATA_VAULT_DIR


def get_version_info() -> Dict[str, Any]:
    """Reads version metadata from version.json."""
    info = {
        "version": APP_VERSION,
        "app_name": APP_NAME,
        "data_vault_dir": str(DATA_VAULT_DIR),
    }
    if VERSION_FILE_PATH.exists():
        try:
            with open(VERSION_FILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    info.update(loaded)
        except Exception:
            pass
    return info


# Run migration check automatically on import
ensure_data_vault_migrated()

