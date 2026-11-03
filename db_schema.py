#!/usr/bin/env python3
"""
Database Schema, Non-Destructive Migration & DAS Mirror Engine (db_schema.py)
AI Photo Archival System v3.0 — Mitch Rouse Architecture

Implements:
1. Non-destructive SQLite WAL schema upgrade for photo_records
2. Multi-catalog virtual silos table (catalogs)
3. Loud, transparent error tracking table (ingestion_errors)
4. Self-learning location/project centroid index table (metadata_centroids)
5. Atomic online SQLite + vectors.npy backup utility to Direct-Attached Storage (DAS)
"""

import os
import json
import shutil
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from config_paths import (
    DATA_VAULT_DIR,
    DEFAULT_COLOR_SIGS_PATH,
    DEFAULT_CROP_BOXES_PATH,
    DEFAULT_CROP_VECTORS_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_MODELS_DIR,
    DEFAULT_PREVIEWS_1600_DIR,
    DEFAULT_SETTINGS_PATH,
    DEFAULT_THUMBS_360_DIR,
    DEFAULT_VECTORS_PATH,
    PROJECT_ROOT,
)

SCRIPT_DIR = PROJECT_ROOT

# Complete v3.0 columns to ensure on photo_records (non-destructive migration)
V3_COLUMNS = [
    ("file_hash", "TEXT"),
    ("sibling_path", "TEXT"),
    ("catalog_name", "TEXT DEFAULT 'Default'"),
    ("shoot_date", "TEXT DEFAULT 'Undated'"),
    ("camera_make", "TEXT"),
    ("camera_model", "TEXT"),
    ("camera_serial", "TEXT"),
    ("lens_model", "TEXT"),
    ("focal_length", "REAL"),
    ("shutter_speed", "TEXT"),
    ("aperture", "REAL"),
    ("iso", "INTEGER"),
    ("gps_lat", "REAL"),
    ("gps_lon", "REAL"),
    ("gps_alt", "REAL"),
    ("gps_ground_truth", "INTEGER DEFAULT 0"),
    ("is_screenshot", "INTEGER DEFAULT 0"),
    ("title", "TEXT"),
    ("caption", "TEXT"),
    ("sub_location", "TEXT"),
    ("city", "TEXT"),
    ("star_rating", "INTEGER DEFAULT 0"),
    ("color_label", "TEXT"),
    ("pick_flag", "INTEGER DEFAULT 0"),
    ("lrcat_keywords", "TEXT"),
    ("existing_keywords", "TEXT"),
    ("hierarchical_keywords", "TEXT"),
    ("sub_category", "TEXT"),
    ("thumb_360_path", "TEXT"),
    ("preview_1600_path", "TEXT"),
    ("sharpness_score", "REAL"),
    ("is_unsharp", "INTEGER DEFAULT 0"),
    ("colorfulness_score", "REAL"),
    ("is_monochrome", "INTEGER DEFAULT 0"),
    ("laion_aesthetic_score", "REAL"),
    ("keepers_taste_bonus", "REAL DEFAULT 0.0"),
    ("aesthetic_score", "REAL"),
    ("vector_index", "INTEGER"),
    ("sequence_id", "TEXT"),
    ("sequence_frame_index", "INTEGER DEFAULT 0"),
    ("sequence_length", "INTEGER DEFAULT 1"),
    ("is_sequence_hero", "INTEGER DEFAULT 0"),
    ("in_keepers", "INTEGER DEFAULT 0"),
    ("stage1_completed", "INTEGER DEFAULT 0"),
    ("stage2_completed", "INTEGER DEFAULT 0"),
    ("xmp_synced", "INTEGER DEFAULT 0"),
    ("xmp_synced_at", "TIMESTAMP"),
    ("file_mtime", "REAL"),
    ("file_size", "INTEGER"),
    ("user_context_notes", "TEXT"),
    ("user_taught_tags", "TEXT DEFAULT '[]'"),
    ("negated_tags", "TEXT DEFAULT '[]'"),
    ("subject_boxes", "TEXT DEFAULT '[]'"),
    ("verified_subjects", "TEXT DEFAULT '[]'"),
    ("location_provenance", "TEXT DEFAULT ''"),
    ("macro_biome", "TEXT DEFAULT ''"),
    ("updated_at", "TIMESTAMP"),
]


def compute_file_hash(file_path: Path) -> str:
    """Computes a deterministic 24-char SHA-256 hex digest from the resolved path."""
    try:
        resolved = str(file_path.resolve())
    except Exception:
        resolved = str(file_path)
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:24]


def normalize_shoot_date(exif_time: Optional[str]) -> str:
    """Extracts YYYY-MM-DD from EXIF DateTimeOriginal ('YYYY:MM:DD HH:MM:SS' or ISO format).
    Rejects bogus Mac HFS / Unix epoch years (<= 1989) as 'Undated'.
    """
    if not exif_time:
        return "Undated"
    s = str(exif_time).strip()
    if len(s) >= 10:
        date_part = s[:10].replace(":", "-").replace("/", "-")
        parts = date_part.split("-")
        if len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 4:
            year = int(parts[0])
            if 1990 <= year <= 2035:
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
            return "Undated"
    if len(s) >= 4 and s[:4].isdigit():
        year = int(s[:4])
        if 1990 <= year <= 2035:
            return f"{s[:4]}-01-01"
        return "Undated"
    return "Undated"


def get_db_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Opens SQLite connection in WAL mode with foreign keys and busy timeout."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA mmap_size=268435456;")  # 256MB mmap for sub-15ms queries
    return conn


def init_and_migrate_db(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Non-destructively creates or upgrades photo_archive.db to v3.0 schema.
    Returns migration summary dictionary.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # 1. Base table creation (compatible with v2.0 + v3.0)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS photo_records (
            file_path TEXT PRIMARY KEY,
            phash TEXT,
            exif_time TEXT,
            status TEXT,
            primary_category TEXT,
            country TEXT,
            state_region TEXT,
            specific_location TEXT,
            key_subjects TEXT,
            is_aerial INTEGER DEFAULT 0,
            confidence_score REAL,
            hierarchical_keywords TEXT,
            sub_category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Inspect existing columns and add missing v3.0 columns non-destructively
    existing_cols = {
        row["name"] for row in cursor.execute("PRAGMA table_info(photo_records);").fetchall()
    }
    added_columns = []
    for col_name, col_def in V3_COLUMNS:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE photo_records ADD COLUMN {col_name} {col_def};")
            added_columns.append(col_name)

    # 3. Auxiliary v3.0 tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalogs (
            catalog_name TEXT PRIMARY KEY,
            root_path TEXT NOT NULL,
            lrcat_path TEXT,
            description TEXT,
            photo_count INTEGER DEFAULT 0,
            last_scanned_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            stage TEXT,
            error_type TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata_centroids (
            cluster_id TEXT PRIMARY KEY,
            label TEXT,
            country TEXT,
            state_region TEXT,
            city TEXT,
            specific_location TEXT,
            sub_location TEXT,
            keywords_json TEXT,
            hierarchical_json TEXT,
            centroid_vector BLOB,
            sample_count INTEGER DEFAULT 0,
            time_windows_json TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cover_photo_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collection_items (
            collection_id INTEGER NOT NULL,
            photo_id TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (collection_id, photo_id)
        );
    """)

    # 4. Backfill file_hash, shoot_date, and catalog_name on any legacy v2.0 rows
    legacy_rows = cursor.execute("""
        SELECT file_path, exif_time, catalog_name, file_hash, shoot_date, status
        FROM photo_records
        WHERE file_hash IS NULL OR shoot_date IS NULL OR shoot_date = 'Undated' OR catalog_name IS NULL
    """).fetchall()

    backfilled_count = 0
    for row in legacy_rows:
        fp = row["file_path"]
        fhash = row["file_hash"] or compute_file_hash(Path(fp))
        sdate = normalize_shoot_date(row["exif_time"])
        cat_name = row["catalog_name"]
        if not cat_name or cat_name == "Default":
            # Infer reasonable catalog name from path if legacy
            if "Keeper" in fp:
                cat_name = "Keepers"
            elif "Aerial" in fp:
                cat_name = "Aerial_Working"
            elif "Desktop/Photo" in fp:
                cat_name = "Desktop_Photo"
            else:
                cat_name = "Legacy_Archive"

        stage2_done = 1 if row["status"] in ("tagged", "inherited") else 0
        cursor.execute("""
            UPDATE photo_records
            SET file_hash = ?,
                shoot_date = ?,
                catalog_name = ?,
                stage2_completed = CASE WHEN stage2_completed = 0 THEN ? ELSE stage2_completed END,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """, (fhash, sdate, cat_name, stage2_done, fp))
        backfilled_count += 1

    # 5. Create Persistent Undo History Table (for 1-Click Cmd+Z Undo across Teach, Scout, Batch & Collection edits)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS undo_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        description TEXT NOT NULL,
        affected_count INTEGER DEFAULT 0,
        snapshot_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5b. Create Active Vector Boundary Learning Table (for user old_label -> new_label spatial/tag reclassifications)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vector_concept_boundaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        photo_id TEXT DEFAULT '',
        file_path TEXT DEFAULT '',
        file_hash TEXT DEFAULT '',
        old_label TEXT NOT NULL,
        new_label TEXT DEFAULT '',
        bbox_json TEXT DEFAULT '[]',
        vector_index INTEGER,
        vector_blob BLOB,
        weight REAL DEFAULT 1.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    vcb_cols = {
        row[1] for row in cursor.execute("PRAGMA table_info(vector_concept_boundaries);").fetchall()
    }
    for vcb_col, vcb_def in [
        ("photo_id", "TEXT DEFAULT ''"),
        ("file_path", "TEXT DEFAULT ''"),
        ("file_hash", "TEXT DEFAULT ''"),
        ("weight", "REAL DEFAULT 1.0"),
    ]:
        if vcb_col not in vcb_cols:
            cursor.execute(f"ALTER TABLE vector_concept_boundaries ADD COLUMN {vcb_col} {vcb_def};")

    # 5c. Create v4.0 People & Pets Entity Clustering Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_clusters (
        entity_id TEXT PRIMARY KEY,
        entity_type TEXT NOT NULL,
        entity_name TEXT DEFAULT '',
        auto_breed TEXT DEFAULT '',
        auto_breed_or_subtype TEXT DEFAULT '',
        catalog_name TEXT DEFAULT '',
        cover_file_hash TEXT DEFAULT '',
        sample_file_hash TEXT DEFAULT '',
        sample_preview_path TEXT DEFAULT '',
        sample_bbox TEXT DEFAULT '[]',
        representative_photo_id TEXT DEFAULT '',
        representative_file_path TEXT DEFAULT '',
        representative_bbox_json TEXT DEFAULT '[]',
        centroid_vector BLOB,
        photo_count INTEGER DEFAULT 0,
        confidence_score REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    ec_cols = {row[1] for row in cursor.execute("PRAGMA table_info(entity_clusters);").fetchall()}
    for ec_col, ec_def in [
        ("auto_breed", "TEXT DEFAULT ''"),
        ("cover_file_hash", "TEXT DEFAULT ''"),
        ("sample_file_hash", "TEXT DEFAULT ''"),
        ("sample_preview_path", "TEXT DEFAULT ''"),
        ("sample_bbox", "TEXT DEFAULT '[]'"),
    ]:
        if ec_col not in ec_cols:
            cursor.execute(f"ALTER TABLE entity_clusters ADD COLUMN {ec_col} {ec_def};")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS photo_entities (
        entity_id TEXT NOT NULL,
        photo_id TEXT DEFAULT '',
        file_hash TEXT DEFAULT '',
        file_path TEXT NOT NULL,
        catalog_name TEXT DEFAULT '',
        entity_type TEXT DEFAULT '',
        entity_name TEXT DEFAULT '',
        breed_label TEXT DEFAULT '',
        confidence REAL DEFAULT 0.0,
        crop_index INTEGER DEFAULT 0,
        bbox TEXT DEFAULT '[]',
        bbox_json TEXT DEFAULT '[]',
        similarity REAL DEFAULT 0.0,
        bridged_by_burst INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (entity_id, file_path)
    );
    """)
    pe_cols = {row[1] for row in cursor.execute("PRAGMA table_info(photo_entities);").fetchall()}
    for pe_col, pe_def in [
        ("file_hash", "TEXT DEFAULT ''"),
        ("entity_type", "TEXT DEFAULT ''"),
        ("entity_name", "TEXT DEFAULT ''"),
        ("breed_label", "TEXT DEFAULT ''"),
        ("confidence", "REAL DEFAULT 0.0"),
        ("bbox", "TEXT DEFAULT '[]'"),
    ]:
        if pe_col not in pe_cols:
            cursor.execute(f"ALTER TABLE photo_entities ADD COLUMN {pe_col} {pe_def};")

    # 6. Create high-speed indexes for sub-15ms queries
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_photo_status ON photo_records(status);",
        "CREATE INDEX IF NOT EXISTS idx_photo_conf ON photo_records(confidence_score);",
        "CREATE INDEX IF NOT EXISTS idx_photo_created ON photo_records(created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photo_catalog ON photo_records(catalog_name);",
        "CREATE INDEX IF NOT EXISTS idx_photo_shoot_date ON photo_records(shoot_date DESC, exif_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photo_aesthetic ON photo_records(aesthetic_score DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photo_unsharp ON photo_records(is_unsharp);",
        "CREATE INDEX IF NOT EXISTS idx_photo_star ON photo_records(star_rating DESC);",
        "CREATE INDEX IF NOT EXISTS idx_photo_sequence ON photo_records(sequence_id, is_sequence_hero);",
        "CREATE INDEX IF NOT EXISTS idx_photo_keepers ON photo_records(in_keepers);",
        "CREATE INDEX IF NOT EXISTS idx_photo_vector_idx ON photo_records(vector_index);",
        "CREATE INDEX IF NOT EXISTS idx_photo_file_hash ON photo_records(file_hash);",
        "CREATE INDEX IF NOT EXISTS idx_photo_macro_biome ON photo_records(macro_biome);",
        "CREATE INDEX IF NOT EXISTS idx_errors_stage ON ingestion_errors(stage, created_at DESC);",
        "CREATE INDEX IF NOT EXISTS idx_collection_items_col ON collection_items(collection_id, sort_order ASC);",
        "CREATE INDEX IF NOT EXISTS idx_collection_items_photo ON collection_items(photo_id);",
        "CREATE INDEX IF NOT EXISTS idx_undo_created ON undo_history(created_at DESC, id DESC);",
        "CREATE INDEX IF NOT EXISTS idx_vec_boundary_labels ON vector_concept_boundaries(old_label, new_label);",
        "CREATE INDEX IF NOT EXISTS idx_entity_clusters_cat ON entity_clusters(catalog_name, entity_type, photo_count DESC);",
        "CREATE INDEX IF NOT EXISTS idx_entity_clusters_name ON entity_clusters(entity_name);",
        "CREATE INDEX IF NOT EXISTS idx_photo_entities_photo ON photo_entities(photo_id);",
        "CREATE INDEX IF NOT EXISTS idx_photo_entities_file ON photo_entities(file_path);",
        "CREATE INDEX IF NOT EXISTS idx_photo_entities_cat ON photo_entities(catalog_name, entity_id);",
    ]
    for idx_sql in indexes:
        cursor.execute(idx_sql)

    conn.commit()
    total_records = cursor.execute("SELECT COUNT(*) FROM photo_records;").fetchone()[0]
    conn.close()

    return {
        "db_path": str(db_path),
        "added_columns": added_columns,
        "backfilled_rows": backfilled_count,
        "total_records": total_records,
    }


def log_ingestion_error(
    db_path: Path,
    file_path: str,
    stage: str,
    error_type: str,
    error_message: str
) -> None:
    """Records an error loudly and transparently to SQLite ingestion_errors + errors.log."""
    logging.getLogger("errors").error(f"[{stage}] {error_type} on {file_path}: {error_message}")
    try:
        conn = get_db_connection(db_path)
        conn.execute(
            """
            INSERT INTO ingestion_errors (file_path, stage, error_type, error_message)
            VALUES (?, ?, ?, ?)
            """,
            (str(file_path), stage, error_type, str(error_message)[:2000])
        )
        conn.commit()
        conn.close()
    except Exception as db_err:
        logging.getLogger("errors").critical(f"Failed to write ingestion_error to DB: {db_err}")


def backup_catalog_to_das(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    das_backup_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    1-Click atomic online backup of photo_archive.db and vectors.npy to Direct-Attached Storage (DAS).
    Uses SQLite's online backup API so concurrent reads/writes are never corrupted.
    """
    target_dir = Path(das_backup_dir or (Path.home() / "Desktop" / "DAS_Catalog_Backup")).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_db = target_dir / "photo_archive.db"
    dest_vectors = target_dir / "vectors.npy"

    src_conn = get_db_connection(db_path)
    dst_conn = sqlite3.connect(str(dest_db))
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    vectors_copied = False
    if Path(vectors_path).exists():
        tmp_vec = target_dir / f"vectors.npy.tmp_{timestamp}"
        shutil.copy2(str(vectors_path), str(tmp_vec))
        os.replace(str(tmp_vec), str(dest_vectors))
        vectors_copied = True

    return {
        "status": "ok",
        "backup_dir": str(target_dir),
        "db_backup_path": str(dest_db),
        "vectors_backup_path": str(dest_vectors),
        "db_size_bytes": dest_db.stat().st_size if dest_db.exists() else 0,
        "vectors_copied": vectors_copied,
        "timestamp": timestamp,
    }


if __name__ == "__main__":
    summary = init_and_migrate_db()
    print(f"✓ Database migrated to v3.0: {json.dumps(summary, indent=2)}")
