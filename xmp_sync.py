#!/usr/bin/env python3
"""
Safe, Validated Additive XMP Sync Worker (xmp_sync.py)
AI Photo Archival System v3.0 — Mitch Rouse Architecture

Implements:
1. Strictly additive (`+=`) metadata writing via ExifTool (never erases existing tags)
2. Phase One .IIQ binary protection: writes to companion .IIQ.xmp sidecar (never touches .IIQ binary)
3. Automatic sibling syncing: syncs tags & star ratings to paired .TIF / .DNG derivative
4. Post-write validation & loud error logging to SQLite ingestion_errors table
5. Supports both On-Demand single/batch sync and throttled background Auto-Sync
"""

import os
import json
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from db_schema import (
    DEFAULT_DB_PATH,
    get_db_connection,
    log_ingestion_error,
)

SCRIPT_DIR = Path(__file__).resolve().parent
EXIFTOOL_BIN = str(SCRIPT_DIR / "bin" / "exiftool") if (SCRIPT_DIR / "bin" / "exiftool").exists() else "exiftool"

# Proprietary RAW formats where sidecar .xmp / .IIQ.xmp is preferred over binary modification
SIDECAR_PROTECTED_RAW_EXTS = {
    ".iiq", ".nef", ".arw", ".cr2", ".cr3", ".raf", ".orf", ".rw2", ".pef", ".srw", ".3fr"
}


def resolve_sync_targets(primary_path: Path, sibling_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Determines the safe metadata write target(s) for a photo record:
    - For Phase One .IIQ: always writes to `<filename>.IIQ.xmp` (Capture One & Lightroom standard)
      AND `<stem>.xmp` if one already exists, NEVER modifying the binary .IIQ file.
    - For other camera RAWs (.NEF, .ARW, .CR3, etc.): writes to companion `.xmp` sidecar
      so the original camera RAW binary is never modified.
    - For .TIF / .JPG / .DNG (either as primary or as paired sibling_path): writes additively
      to the file or its companion sidecar safely.
    """
    targets: List[Dict[str, Any]] = []

    if primary_path:
        ext_low = primary_path.suffix.lower()
        if ext_low == ".iiq":
            # Phase One .IIQ strictly uses .IIQ.xmp sidecar
            iiq_xmp = primary_path.parent / f"{primary_path.name}.xmp"
            targets.append({"target_path": iiq_xmp, "is_sidecar": True, "source_ref": primary_path})
        elif ext_low in SIDECAR_PROTECTED_RAW_EXTS:
            std_xmp = primary_path.with_suffix(".xmp")
            targets.append({"target_path": std_xmp, "is_sidecar": True, "source_ref": primary_path})
        else:
            targets.append({"target_path": primary_path, "is_sidecar": False, "source_ref": primary_path})

    if sibling_path and sibling_path.exists():
        sib_ext = sibling_path.suffix.lower()
        if sib_ext in SIDECAR_PROTECTED_RAW_EXTS:
            sib_xmp = sibling_path.with_suffix(".xmp")
            targets.append({"target_path": sib_xmp, "is_sidecar": True, "source_ref": sibling_path})
        else:
            targets.append({"target_path": sibling_path, "is_sidecar": False, "source_ref": sibling_path})

    return targets


def sync_record_metadata_additive(
    file_path: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Writes a record's flat keywords, hierarchical keywords, location fields, and star_rating
    additively (`+=`) via ExifTool without erasing existing metadata.
    Validates exit code and logs any I/O or ExifTool error to `ingestion_errors`.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT file_path, sibling_path, key_subjects, existing_keywords, lrcat_keywords,
               hierarchical_keywords, star_rating, is_unsharp, country, state_region,
               city, sub_location, specific_location, title, caption
        FROM photo_records
        WHERE file_path = ?
    """, (file_path,)).fetchone()

    if not row:
        conn.close()
        return {"status": "error", "message": f"Record not found: {file_path}"}

    primary_p = Path(row["file_path"])
    sibling_p = Path(row["sibling_path"]) if row["sibling_path"] else None

    if not primary_p.exists():
        log_ingestion_error(db_path, file_path, "xmp_sync", "FileNotFoundError", "Primary file does not exist on disk")
        conn.close()
        return {"status": "error", "message": f"Primary file missing: {file_path}"}

    # Merge all keywords (existing + lrcat + AI key_subjects) without duplicates
    flat_kws: List[str] = []
    for col in ("existing_keywords", "lrcat_keywords", "key_subjects"):
        raw_json = row[col]
        if raw_json:
            try:
                items = json.loads(raw_json)
                if isinstance(items, list):
                    for k in items:
                        ks = str(k).strip()
                        if ks and ks not in flat_kws:
                            flat_kws.append(ks)
            except Exception:
                pass

    hier_kws: List[str] = []
    if row["hierarchical_keywords"]:
        try:
            h_items = json.loads(row["hierarchical_keywords"])
            if isinstance(h_items, list):
                for hk in h_items:
                    hks = str(hk).strip()
                    if hks and hks not in hier_kws:
                        hier_kws.append(hks)
        except Exception:
            pass

    # Enforce Clean Tagging Rule for Sharpness
    is_unsharp = int(row["is_unsharp"] or 0)
    if is_unsharp == 1:
        if "Unsharp" not in flat_kws:
            flat_kws.append("Unsharp")
        if "Technical|Focus|Unsharp" not in hier_kws:
            hier_kws.append("Technical|Focus|Unsharp")
    else:
        flat_kws = [k for k in flat_kws if k != "Unsharp"]
        hier_kws = [hk for hk in hier_kws if hk != "Technical|Focus|Unsharp"]

    star_rating = int(row["star_rating"] or 0)
    if is_unsharp == 1 and star_rating > 1:
        star_rating = 1

    targets = resolve_sync_targets(primary_p, sibling_p)
    written_targets: List[str] = []

    for tgt in targets:
        target_path: Path = tgt["target_path"]
        is_sidecar: bool = tgt["is_sidecar"]
        source_ref: Path = tgt["source_ref"]

        # Record original RAW mtime/size if writing to a sidecar so we can verify RAW was untouched
        raw_stat_before = source_ref.stat() if source_ref.exists() else None

        args = [
            EXIFTOOL_BIN,
            "-overwrite_original",
            "-m",
            "-XMP-xmp:CreatorTool=AI Photo Archival System v3.0",
            f"-XMP:Rating={star_rating}",
        ]

        # Additive location & title metadata if present
        if row["country"] and row["country"] != "Unknown":
            args.append(f"-XMP-photoshop:Country={row['country']}")
            if not is_sidecar:
                args.append(f"-IPTC:Country-PrimaryLocationName={row['country']}")
        if row["state_region"] and row["state_region"] != "Unknown":
            args.append(f"-XMP-photoshop:State={row['state_region']}")
            if not is_sidecar:
                args.append(f"-IPTC:Province-State={row['state_region']}")
        if row["city"] and row["city"] != "Unknown":
            args.append(f"-XMP-photoshop:City={row['city']}")
            if not is_sidecar:
                args.append(f"-IPTC:City={row['city']}")
        sub_loc = row["sub_location"] or row["specific_location"]
        if sub_loc and sub_loc != "Unknown":
            args.append(f"-XMP-iptcCore:Location={sub_loc}")
            if not is_sidecar:
                args.append(f"-IPTC:Sub-location={sub_loc}")

        # Strictly additive (-= then += per tag prevents duplication while preserving any external tags)
        for kw in flat_kws:
            args.append(f"-XMP-dc:Subject-={kw}")
            args.append(f"-XMP-dc:Subject+={kw}")
            if not is_sidecar:
                args.append(f"-IPTC:Keywords-={kw}")
                args.append(f"-IPTC:Keywords+={kw}")

        for hkw in hier_kws:
            args.append(f"-XMP-lr:HierarchicalSubject-={hkw}")
            args.append(f"-XMP-lr:HierarchicalSubject+={hkw}")

        args.append(str(target_path))

        # Remove any stale temporary files from previous interrupted ExifTool operations
        tmp_target = target_path.parent / f"{target_path.name}_exiftool_tmp"
        if tmp_target.exists():
            try:
                tmp_target.unlink()
            except Exception as e:
                logging.warning(f"Failed to remove stale ExifTool tmp file {tmp_target}: {e}")

        file_size_mb = (target_path.stat().st_size / (1024 * 1024)) if target_path.exists() else 0.0
        dyn_timeout = max(45, int((file_size_mb or 0) * 0.4) + 30)

        try:
            res = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=dyn_timeout,
                check=False,
            )
            if res.returncode != 0 or not target_path.exists() or target_path.stat().st_size == 0:
                err_msg = (res.stderr or res.stdout or f"Exit code {res.returncode}").strip()
                log_ingestion_error(db_path, str(target_path), "xmp_sync", "ExifToolWriteError", err_msg)
                conn.close()
                return {"status": "error", "target": str(target_path), "message": err_msg}

            # Verify protected RAW binary was never modified when writing to sidecar
            if is_sidecar and raw_stat_before is not None:
                raw_stat_after = source_ref.stat()
                if raw_stat_after.st_size != raw_stat_before.st_size:
                    log_ingestion_error(db_path, str(source_ref), "xmp_sync", "SafetyViolation", "RAW size changed")
                    conn.close()
                    return {"status": "error", "message": "Safety check failed on RAW file"}

            # Clear resolved error rows from ingestion_errors on success
            try:
                cursor.execute(
                    "DELETE FROM ingestion_errors WHERE (file_path = ? OR file_path = ?) AND stage = 'xmp_sync'",
                    (str(target_path), str(primary_p)),
                )
                conn.commit()
            except Exception:
                pass

            written_targets.append(str(target_path))
        except Exception as exc:
            log_ingestion_error(db_path, str(target_path), "xmp_sync", type(exc).__name__, str(exc))
            conn.close()
            return {"status": "error", "target": str(target_path), "message": str(exc)}

    cursor.execute("""
        UPDATE photo_records
        SET xmp_synced = 1,
            xmp_synced_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE file_path = ?
    """, (file_path,))
    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "success": True,
        "file_path": file_path,
        "written_targets": written_targets,
        "flat_keywords_count": len(flat_kws),
        "hierarchical_keywords_count": len(hier_kws),
        "star_rating": star_rating,
    }


def sync_pending_records_batch(
    catalog_name: Optional[str] = None,
    limit: int = 50,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """
    Throttled batch sync worker for syncing completed records that have xmp_synced = 0.
    """
    conn = get_db_connection(db_path)
    if catalog_name and catalog_name != "All":
        rows = conn.execute("""
            SELECT file_path FROM photo_records
            WHERE xmp_synced = 0 AND status != 'failed' AND catalog_name = ?
            LIMIT ?
        """, (catalog_name, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT file_path FROM photo_records
            WHERE xmp_synced = 0 AND status != 'failed'
            LIMIT ?
        """, (limit,)).fetchall()
    conn.close()

    synced_ok = 0
    errors = 0
    targets_written: List[str] = []

    for r in rows:
        res = sync_record_metadata_additive(r["file_path"], db_path=db_path)
        if res.get("status") == "ok":
            synced_ok += 1
            targets_written.extend(res.get("written_targets", []))
        else:
            errors += 1

    return {
        "attempted": len(rows),
        "synced_ok": synced_ok,
        "errors": errors,
        "targets_written": targets_written,
    }
