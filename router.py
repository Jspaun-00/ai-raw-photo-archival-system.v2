#!/usr/bin/env python3
"""
Virtual Catalog Router (router.py — Retired Physical File Mover in v3.0)
AI-Powered RAW Photo Archival System v3.0 — Mitch Rouse Edition

SAFETY GUARDRAIL (v3.0 Guiding Philosophy #1):
Original RAW/TIF files and Lightroom (.lrcat) directory structures are sacred.
Physical folder-moving (`shutil.move`) is permanently retired in v3.0 in favor of
the unified SQLite virtual catalog (`photo_archive.db`) + persistent WebP previews.
"""

import argparse
import json
from pathlib import Path
from db_schema import DEFAULT_DB_PATH, get_db_connection


def run_routing(dry_run: bool = True, copy_mode: bool = False, target_destination: Path = None):
    """
    In v3.0, physical file moving is permanently disabled to protect Lightroom (.lrcat)
    catalog links and original RAW/TIF files on DAS.
    Returns a virtual taxonomy distribution summary from `photo_archive.db`.
    """
    print(
        "[v3.0 Safety Guardrail] Physical file moving (router.py) is retired in v3.0.\n"
        "All original RAW/TIF files remain untouched in their native Lightroom catalog folders.\n"
        "Use the Virtual Catalog Silos, Smart Collections, and Semantic Search in the UI."
    )
    if not DEFAULT_DB_PATH.exists():
        return {"status": "retired_in_v3", "records": 0}

    conn = get_db_connection(DEFAULT_DB_PATH)
    rows = conn.execute("""
        SELECT catalog_name, primary_category, COUNT(*) AS cnt
        FROM photo_records
        GROUP BY catalog_name, primary_category
        ORDER BY catalog_name, cnt DESC
    """).fetchall()
    conn.close()

    summary = [dict(r) for r in rows]
    print(json.dumps({"status": "virtual_catalog_active", "breakdown": summary}, indent=2))
    return {"status": "virtual_catalog_active", "breakdown": summary}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Virtual Catalog Summary (Physical routing retired in v3.0)")
    parser.add_argument("--dry-run", action="store_true", help="Print virtual catalog breakdown")
    parser.add_argument("--copy", action="store_true", help="Ignored in v3.0 (virtual catalog active)")
    parser.add_argument("--dest", type=str, default=None, help="Ignored in v3.0")
    args = parser.parse_args()
    run_routing(dry_run=True)
