#!/usr/bin/env python3
"""
Centralized Data Vault & Path Configuration (config_paths.py)
MR Darkroom — Dual-Mode Architecture (Portable External SSD + Local Mac Hard Drive)

Resolves all persistent database, vector matrix, WebP preview, model, and settings paths:
1. If `MRDARKROOM_VAULT_DIR` is set in the environment -> uses that directory (e.g. on the 2TB SSD).
2. Else if `./Data_Vault` or `../Data_Vault` exists next to the engine -> uses Portable SSD mode.
3. Else defaults to `~/Library/Application Support/MRDarkroom/` (Installed Mac Hard Drive mode).

Also configures offline model caches (`HF_HOME` for OpenCLIP and `OLLAMA_MODELS` for Ollama VLM)
when present inside `Data_Vault/models/` so 100% of AI features work offline on any Mac.
"""

import json
import logging
import os
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict

APP_NAME = "MR Darkroom"
APP_VERSION = "4.5.0"

PROJECT_ROOT = Path(__file__).resolve().parent


def _resolve_data_vault_dir() -> Path:
    env_vault = os.environ.get("MRDARKROOM_VAULT_DIR", "").strip()
    if env_vault:
        return Path(env_vault).expanduser().resolve()

    # Portable SSD mode: if Data_Vault sits inside or beside PROJECT_ROOT
    local_vault = PROJECT_ROOT / "Data_Vault"
    if local_vault.is_dir() and (local_vault / "photo_archive.db").exists():
        return local_vault.resolve()

    parent_vault = PROJECT_ROOT.parent / "Data_Vault"
    if parent_vault.is_dir() and (parent_vault / "photo_archive.db").exists():
        return parent_vault.resolve()

    # Standard installed Mac mode
    return Path.home() / "Library" / "Application Support" / "MRDarkroom"


DATA_VAULT_DIR = _resolve_data_vault_dir()
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

# Point HuggingFace / OpenCLIP and Ollama to portable Vault model caches if present
_hf_cache = DEFAULT_MODELS_DIR / "huggingface"
if _hf_cache.is_dir():
    os.environ.setdefault("HF_HOME", str(_hf_cache))

_ollama_cache = DEFAULT_MODELS_DIR / "ollama"
if _ollama_cache.is_dir():
    os.environ.setdefault("OLLAMA_MODELS", str(_ollama_cache))


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
    Ensures `DATA_VAULT_DIR` exists, migrates any existing files from `./data/`
    into the vault, and attempts to create a `./data` symlink (ignoring ExFAT symlink limits).
    """
    DATA_VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. If ./data is a physical directory (not a symlink and not DATA_VAULT_DIR itself), migrate
    if (
        LEGACY_DATA_DIR.exists()
        and not LEGACY_DATA_DIR.is_symlink()
        and LEGACY_DATA_DIR.resolve() != DATA_VAULT_DIR.resolve()
    ):
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

    # 2. Ensure ./data symlink points to DATA_VAULT_DIR when supported by filesystem (APFS/HFS+)
    if not LEGACY_DATA_DIR.exists() and not LEGACY_DATA_DIR.is_symlink():
        try:
            LEGACY_DATA_DIR.symlink_to(DATA_VAULT_DIR, target_is_directory=True)
        except Exception:
            # ExFAT volumes do not support POSIX symlinks; all code uses config_paths constants directly
            pass

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
