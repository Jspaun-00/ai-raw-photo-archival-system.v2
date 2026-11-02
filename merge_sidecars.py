#!/usr/bin/env python3
"""
Safe Sidecar & Additive Metadata Sync Utility (merge_sidecars.py — v3.0)
AI-Powered RAW Photo Archival System v3.0

Upgraded for v3.0 Zero-Data-Corruption Safety:
- NEVER deletes .xmp or .IIQ.xmp sidecars by default (`delete_sidecars=False`).
- Harvests sidecar keywords/captions/locations non-destructively and embeds tags
  using strictly additive (`+=`) ExifTool semantics via `xmp_sync.py`.
"""

import argparse
import json
from pathlib import Path

from db_schema import DEFAULT_DB_PATH
from xmp_sync import sync_pending_records_batch


def merge_metadata(target_dir: Path = None, delete_sidecars: bool = False, catalog_name: str = None):
    """
    Runs safe additive (`+=`) metadata sync for approved records in photo_archive.db.
    Note: `delete_sidecars` is deprecated in v3.0 and ignored unless explicitly forced,
    preserving Capture One (.IIQ.xmp) and Lightroom (.xmp) sidecar compatibility.
    """
    report = sync_pending_records_batch(
        db_path=DEFAULT_DB_PATH,
        catalog_name=catalog_name,
    )
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Safe Additive Metadata & Sidecar Sync (v3.0)")
    parser.add_argument("--catalog", type=str, default=None, help="Optional catalog_name filter")
    args = parser.parse_args()

    merge_metadata(catalog_name=args.catalog, delete_sidecars=False)
