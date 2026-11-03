#!/usr/bin/env python3
"""
studio_jobs_undo.py — Unified Background Job Manager, Persistent 1-Click Undo Stack,
Automatic Rolling SQLite Vault Backups, and Offline Gazetteer for MR Darkroom.

Extracted from server.py for clean modular architecture while remaining 100%
re-exported from server.py for backward compatibility.
"""

import json
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from db_schema import (
    DATA_VAULT_DIR,
    DEFAULT_DB_PATH,
    get_db_connection,
    init_and_migrate_db,
)

# ==============================================================================
# 1. OFFLINE GEO-ATLAS GAZETTEER
# ==============================================================================
OFFLINE_GAZETTEER: Dict[str, Dict[str, Any]] = {
    "canyonlands": {"lat": 38.3269, "lon": -109.8783, "name": "Canyonlands National Park, UT"},
    "dead horse point": {"lat": 38.4842, "lon": -109.7365, "name": "Dead Horse Point, UT"},
    "green river overlook": {"lat": 38.2886, "lon": -109.9142, "name": "Green River Overlook, UT"},
    "monument valley": {"lat": 36.9980, "lon": -110.0985, "name": "Monument Valley, AZ/UT"},
    "valley of the gods": {"lat": 37.2653, "lon": -109.8392, "name": "Valley of the Gods, UT"},
    "comb ridge": {"lat": 37.3614, "lon": -109.6384, "name": "Comb Ridge, UT"},
    "factory butte": {"lat": 38.4369, "lon": -110.9135, "name": "Factory Butte, UT"},
    "shiprock": {"lat": 36.6875, "lon": -108.8364, "name": "Shiprock, NM"},
    "white sands": {"lat": 32.7872, "lon": -106.3257, "name": "White Sands National Park, NM"},
    "bosque del apache": {"lat": 33.8047, "lon": -106.8917, "name": "Bosque del Apache, NM"},
    "santa fe": {"lat": 35.6870, "lon": -105.9378, "name": "Santa Fe, NM"},
    "grand canyon": {"lat": 36.1069, "lon": -112.1129, "name": "Grand Canyon National Park, AZ"},
    "tucson": {"lat": 32.2226, "lon": -110.9747, "name": "Tucson & Sonoran Desert, AZ"},
    "sonoran desert": {"lat": 32.2535, "lon": -111.1666, "name": "Sonoran Desert, AZ"},
    "death valley": {"lat": 36.5054, "lon": -117.0794, "name": "Death Valley National Park, CA"},
    "zabriskie point": {"lat": 36.4201, "lon": -116.8122, "name": "Zabriskie Point, CA"},
    "alabama hills": {"lat": 36.6052, "lon": -118.1129, "name": "Alabama Hills, CA"},
    "mono lake": {"lat": 38.0166, "lon": -119.0099, "name": "Mono Lake, CA"},
    "eastern sierra": {"lat": 37.6485, "lon": -118.9721, "name": "Eastern Sierra / Hwy 395, CA"},
    "yosemite": {"lat": 37.7456, "lon": -119.5936, "name": "Yosemite National Park, CA"},
    "big sur": {"lat": 36.2704, "lon": -121.8081, "name": "Big Sur, CA"},
    "pescadero": {"lat": 37.2658, "lon": -122.4119, "name": "Pescadero State Beach, CA"},
    "huntington beach": {"lat": 33.6553, "lon": -118.0046, "name": "Huntington Beach, CA"},
    "anza-borrego": {"lat": 33.2559, "lon": -116.3750, "name": "Anza-Borrego Desert, CA"},
    "palm springs": {"lat": 33.8303, "lon": -116.5453, "name": "Palm Springs, CA"},
    "taft oil field": {"lat": 35.1425, "lon": -119.4565, "name": "Taft Oil Field, CA"},
    "cosumnes": {"lat": 38.2619, "lon": -121.4389, "name": "Cosumnes River Preserve, CA"},
    "los angeles": {"lat": 34.0522, "lon": -118.2437, "name": "Los Angeles, CA"},
    "rhyolite": {"lat": 36.9041, "lon": -116.8290, "name": "Rhyolite Ghost Town, NV"},
    "grand teton": {"lat": 43.7904, "lon": -110.6818, "name": "Grand Teton National Park, WY"},
    "yellowstone": {"lat": 44.4280, "lon": -110.5885, "name": "Yellowstone National Park, WY"},
    "palouse": {"lat": 46.8618, "lon": -117.3679, "name": "Palouse & Steptoe Butte, WA"},
    "bandon": {"lat": 43.1190, "lon": -124.4084, "name": "Bandon Coast, OR"},
    "moccasin": {"lat": 47.0583, "lon": -109.9577, "name": "Moccasin, MT"},
    "billings": {"lat": 45.7833, "lon": -108.5007, "name": "Billings, MT"},
    "heber valley": {"lat": 40.5070, "lon": -111.4133, "name": "Heber Valley, UT"},
    "denver": {"lat": 39.7392, "lon": -104.9903, "name": "Denver & Front Range, CO"},
    "yankton": {"lat": 42.8711, "lon": -97.3973, "name": "Yankton, SD"},
    "chicago": {"lat": 41.8781, "lon": -87.6298, "name": "Chicago, IL"},
    "houma": {"lat": 29.5958, "lon": -90.7195, "name": "Houma & Atchafalaya Bayous, LA"},
    "abbeville": {"lat": 29.9746, "lon": -92.1343, "name": "Abbeville Cypress Swamp, LA"},
    "nashville": {"lat": 36.1497, "lon": -86.8133, "name": "Nashville Parthenon, TN"},
    "everglades": {"lat": 25.2866, "lon": -80.8987, "name": "Everglades National Park, FL"},
    "washington monument": {"lat": 38.8895, "lon": -77.0353, "name": "Washington Monument, DC"},
    "washington dc": {"lat": 38.8895, "lon": -77.0353, "name": "Washington, DC"},
    "carolinas": {"lat": 35.5951, "lon": -82.5515, "name": "Carolinas & Blue Ridge, NC"},
    "kirkjufell": {"lat": 64.9417, "lon": -23.3069, "name": "Kirkjufell, Snæfellsnes, Iceland"},
    "gullfoss": {"lat": 64.3271, "lon": -20.1199, "name": "Gullfoss Waterfall, Iceland"},
    "jökulsárlón": {"lat": 64.0784, "lon": -16.2306, "name": "Jökulsárlón & Diamond Beach, Iceland"},
    "jokulsarlon": {"lat": 64.0784, "lon": -16.2306, "name": "Jökulsárlón & Diamond Beach, Iceland"},
    "reynisfjara": {"lat": 63.4042, "lon": -19.0450, "name": "Reynisfjara Black Sand Beach, Iceland"},
    "hallgrímskirkja": {"lat": 64.1417, "lon": -21.9266, "name": "Hallgrímskirkja, Reykjavík, Iceland"},
    "iceland": {"lat": 64.9631, "lon": -19.0208, "name": "Icelandic Highlands & Coast"},
    "venice": {"lat": 45.4408, "lon": 12.3155, "name": "Venice, Italy"},
    "san miguel de allende": {"lat": 20.9144, "lon": -100.7452, "name": "San Miguel de Allende, Mexico"},
    "havana": {"lat": 23.1136, "lon": -82.3666, "name": "Havana & Malecón, Cuba"},
    "cuba": {"lat": 23.1136, "lon": -82.3666, "name": "Havana & Malecón, Cuba"},
    "brighton": {"lat": 50.8225, "lon": -0.1372, "name": "Brighton & Southern England, UK"},
    "milford sound": {"lat": -44.6716, "lon": 167.9256, "name": "Milford Sound, New Zealand"},
    "new zealand": {"lat": -44.6716, "lon": 167.9256, "name": "New Zealand"},
}


# ==============================================================================
# 2. BACKGROUND PIPELINE & NON-BLOCKING LIVE JOB CONTROL MANAGER
# ==============================================================================
PIPELINE_STATUS: Dict[str, Any] = {
    "running": False,
    "stage": "idle",
    "catalog_name": None,
    "source_dir": None,
    "started_at": None,
    "finished_at": None,
    "last_summary": None,
    "last_error": None,
}


class BackgroundJobManager:
    """
    Thread-safe background job controller supporting live progress, elapsed/ETA calculation,
    Pause, Resume, and graceful Cancel across Export, Deep Re-Assess, AI Scout, and Ingest.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Not paused by default
        self._cancel_flag = False
        self._state: Dict[str, Any] = {
            "job_id": None,
            "job_type": "idle",
            "title": "Idle",
            "running": False,
            "paused": False,
            "cancelled": False,
            "processed": 0,
            "total": 0,
            "current_item": "",
            "started_at": None,
            "finished_at": None,
            "paused_accum_seconds": 0.0,
            "pause_started_at": None,
            "message": "",
            "result": None,
            "error": None,
            "extra": {},
        }

    def start_job(
        self,
        job_type: Optional[str] = None,
        title: str = "",
        total: int = 0,
        message: str = "",
        extra: Optional[Dict[str, Any]] = None,
        *,
        task_type: Optional[str] = None,
        phase: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        with self._lock:
            eff_type = job_type or task_type or "job"
            eff_msg = phase or message or f"Starting {title}..."
            job_id = f"{eff_type}_{int(time.time() * 1000)}"
            self._cancel_flag = False
            self._pause_event.set()
            merged_extra = dict(extra or {})
            if kwargs:
                merged_extra.update(kwargs)
            self._state = {
                "job_id": job_id,
                "job_type": eff_type,
                "task_type": eff_type,
                "title": title,
                "running": True,
                "paused": False,
                "cancelled": False,
                "processed": 0,
                "total": max(0, int(total)),
                "current_item": "",
                "current_file": "",
                "started_at": time.time(),
                "finished_at": None,
                "paused_accum_seconds": 0.0,
                "pause_started_at": None,
                "message": eff_msg,
                "phase": eff_msg,
                "result": None,
                "error": None,
                "extra": merged_extra,
            }
            return job_id

    def update(
        self,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        current_item: Optional[str] = None,
        current_file: Optional[str] = None,
        message: Optional[str] = None,
        phase: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            if processed is not None:
                self._state["processed"] = int(processed)
            if total is not None:
                self._state["total"] = int(total)
            eff_item = current_item if current_item is not None else current_file
            if eff_item is not None:
                self._state["current_item"] = str(eff_item)
                self._state["current_file"] = str(eff_item)
            eff_msg = message if message is not None else phase
            if eff_msg is not None:
                self._state["message"] = str(eff_msg)
                self._state["phase"] = str(eff_msg)
            if extra:
                self._state.setdefault("extra", {}).update(extra)

    def update_progress(
        self,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        current_file: Optional[str] = None,
        current_item: Optional[str] = None,
        phase: Optional[str] = None,
        message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.update(
            processed=processed,
            total=total,
            current_item=current_item if current_item is not None else current_file,
            message=message if message is not None else phase,
            extra=extra,
        )

    def check_point(
        self,
        processed: Optional[int] = None,
        total: Optional[int] = None,
        current_item: Optional[str] = None,
        message: Optional[str] = None,
    ) -> bool:
        """
        Called inside worker loops before processing each photo/step.
        Updates progress, blocks cleanly if Paused, and returns False if Cancelled.
        """
        self.update(processed=processed, total=total, current_item=current_item, message=message)
        while not self._pause_event.is_set():
            if self._cancel_flag:
                return False
            time.sleep(0.15)
        return not self._cancel_flag

    def check_pause_or_cancel(self) -> bool:
        while not self._pause_event.is_set():
            if self._cancel_flag:
                return False
            time.sleep(0.15)
        return not self._cancel_flag

    def pause(self) -> Dict[str, Any]:
        with self._lock:
            if self._state["running"] and not self._state["paused"]:
                self._state["paused"] = True
                self._state["pause_started_at"] = time.time()
                self._pause_event.clear()
        return self.status()

    def resume(self) -> Dict[str, Any]:
        with self._lock:
            if self._state["running"] and self._state["paused"]:
                if self._state["pause_started_at"]:
                    self._state["paused_accum_seconds"] += max(0.0, time.time() - self._state["pause_started_at"])
                self._state["pause_started_at"] = None
                self._state["paused"] = False
                self._pause_event.set()
        return self.status()

    def cancel(self) -> Dict[str, Any]:
        with self._lock:
            self._cancel_flag = True
            self._state["cancelled"] = True
            if self._state["paused"]:
                if self._state["pause_started_at"]:
                    self._state["paused_accum_seconds"] += max(0.0, time.time() - self._state["pause_started_at"])
                self._state["pause_started_at"] = None
                self._state["paused"] = False
            self._pause_event.set()
        return self.status()

    def finish(
        self,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            if self._state["pause_started_at"]:
                self._state["paused_accum_seconds"] += max(0.0, time.time() - self._state["pause_started_at"])
                self._state["pause_started_at"] = None
            self._state["running"] = False
            self._state["paused"] = False
            self._state["finished_at"] = time.time()
            if not error and self._state.get("total", 0) > 0:
                self._state["processed"] = self._state["total"]
            eff_msg = phase if phase is not None else message
            if eff_msg is not None:
                self._state["message"] = eff_msg
                self._state["phase"] = eff_msg
            if result is not None:
                self._state["result"] = result
            if error is not None:
                self._state["error"] = error
            self._pause_event.set()
        return self.status()

    def finish_job(
        self,
        message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.finish(message=message, result=result, error=error, phase=phase)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            st = dict(self._state)
            now = st["finished_at"] or time.time()
            started = st["started_at"]
            if started:
                paused_extra = 0.0
                if st["paused"] and st["pause_started_at"]:
                    paused_extra = max(0.0, time.time() - st["pause_started_at"])
                elapsed = max(0.0, (now - started) - st["paused_accum_seconds"] - paused_extra)
            else:
                elapsed = 0.0

            proc = int(st["processed"] or 0)
            tot = int(st["total"] or 0)
            pct = round((proc / tot) * 100.0, 1) if tot > 0 else (100.0 if st["finished_at"] else 0.0)

            eta_sec: Optional[float] = None
            if st["running"] and proc > 0 and tot > proc and elapsed > 0.2:
                rate = elapsed / float(proc)
                eta_sec = round(rate * float(tot - proc), 1)

            st["elapsed_seconds"] = round(elapsed, 1)
            st["percent"] = pct
            st["eta_seconds"] = eta_sec
            st.setdefault("task_type", st.get("job_type"))
            st.setdefault("phase", st.get("message") or "")
            st.setdefault("current_file", st.get("current_item") or "")
            return st

    def get_status(self) -> Dict[str, Any]:
        return self.status()


JOB_MANAGER = BackgroundJobManager()


# ==============================================================================
# 3. AUTOMATIC ROLLING SQLITE VAULT BACKUPS (KEEP LAST 10 SNAPSHOTS)
# ==============================================================================
VAULT_BACKUPS_DIR = DATA_VAULT_DIR / "backups"
_BACKUP_LOCK = threading.Lock()


def create_rolling_vault_backup(
    db_path: Path = DEFAULT_DB_PATH,
    reason: str = "auto",
    max_backups: int = 10,
    min_interval_seconds: float = 15.0,
) -> Dict[str, Any]:
    """
    Creates an atomic online SQLite snapshot of `photo_archive.db` inside
    `~/Library/Application Support/MRDarkroom/backups/` using `sqlite3.Connection.backup`,
    and prunes older snapshots so the 10 most recent backups are kept.
    """
    with _BACKUP_LOCK:
        try:
            db_file = Path(db_path)
            if not db_file.exists():
                return {"status": "skipped", "reason": "db_missing"}

            VAULT_BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            existing = sorted(
                VAULT_BACKUPS_DIR.glob("photo_archive_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            # Avoid spamming duplicate backups within a few seconds unless reason is explicit startup/manual
            if existing and reason not in ("startup", "manual"):
                age_sec = time.time() - existing[0].stat().st_mtime
                if age_sec < min_interval_seconds:
                    return {
                        "status": "reused_recent",
                        "backup_path": str(existing[0]),
                        "age_seconds": round(age_sec, 2),
                        "total_backups": len(existing),
                    }

            safe_reason = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in (reason or "auto"))[:24]
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
            dest_file = VAULT_BACKUPS_DIR / f"photo_archive_{stamp}_{safe_reason}.db"

            src_conn = get_db_connection(db_file)
            dst_conn = sqlite3.connect(str(dest_file))
            with dst_conn:
                src_conn.backup(dst_conn)
            dst_conn.close()
            src_conn.close()

            # Prune older backups beyond max_backups
            all_snaps = sorted(
                VAULT_BACKUPS_DIR.glob("photo_archive_*.db"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            pruned = 0
            for old_snap in all_snaps[max_backups:]:
                try:
                    old_snap.unlink()
                    pruned += 1
                except Exception:
                    pass

            return {
                "status": "ok",
                "backup_path": str(dest_file),
                "size_bytes": dest_file.stat().st_size if dest_file.exists() else 0,
                "reason": safe_reason,
                "total_backups": min(len(all_snaps), max_backups),
                "pruned_count": pruned,
            }
        except Exception as exc:
            logging.warning(f"Rolling vault backup warning ({reason}): {exc}")
            return {"status": "error", "error": str(exc)}


def list_vault_backups() -> List[Dict[str, Any]]:
    """Lists all rolling SQLite backups in `~/Library/Application Support/MRDarkroom/backups/`."""
    if not VAULT_BACKUPS_DIR.exists():
        return []
    snaps = sorted(
        VAULT_BACKUPS_DIR.glob("photo_archive_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: List[Dict[str, Any]] = []
    for p in snaps:
        st = p.stat()
        out.append({
            "filename": p.name,
            "path": str(p),
            "size_bytes": st.st_size,
            "created_at": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
        })
    return out


# ==============================================================================
# 4. PERSISTENT 1-CLICK UNDO (`Cmd+Z`) SAFETY NET
# ==============================================================================
_UNDO_COLUMNS = (
    "file_path",
    "file_hash",
    "primary_category",
    "sub_category",
    "country",
    "state_region",
    "city",
    "sub_location",
    "specific_location",
    "location_provenance",
    "title",
    "caption",
    "key_subjects",
    "hierarchical_keywords",
    "lrcat_keywords",
    "existing_keywords",
    "user_context_notes",
    "user_taught_tags",
    "negated_tags",
    "subject_boxes",
    "verified_subjects",
    "star_rating",
    "in_keepers",
    "is_aerial",
    "confidence_score",
    "status",
    "stage2_completed",
)


def _ensure_undo_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS undo_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        description TEXT NOT NULL,
        affected_count INTEGER DEFAULT 0,
        snapshot_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)


def record_undo_snapshot(
    db_path: Path = DEFAULT_DB_PATH,
    action_type: str = "teach_update",
    description: str = "AI Teach Update",
    photo_ids: Optional[List[str]] = None,
    collection_id: Optional[int] = None,
    create_vault_backup: bool = False,
    max_history: int = 35,
) -> Optional[int]:
    """
    Captures the exact pre-mutation state of affected `photo_records` rows and/or
    `collection_items` rows into `undo_history` before executing a destructive or batch update.
    Optionally triggers a rolling SQLite vault backup for batch operations.
    """
    if create_vault_backup:
        create_rolling_vault_backup(db_path=db_path, reason=action_type)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    _ensure_undo_table(conn)

    photo_rows: List[Dict[str, Any]] = []
    if photo_ids:
        clean_ids = list(dict.fromkeys(str(pid).strip() for pid in photo_ids if pid))
        if clean_ids:
            col_sql = ", ".join(_UNDO_COLUMNS)
            seen_fp = set()
            for i in range(0, len(clean_ids), 400):
                chunk = clean_ids[i : i + 400]
                placeholders = ",".join("?" for _ in chunk)
                rows = cursor.execute(
                    f"""
                    SELECT {col_sql}
                    FROM photo_records
                    WHERE file_hash IN ({placeholders}) OR file_path IN ({placeholders})
                    """,
                    chunk + chunk,
                ).fetchall()
                for r in rows:
                    rd = dict(r)
                    fp = rd.get("file_path")
                    if fp and fp not in seen_fp:
                        seen_fp.add(fp)
                        photo_rows.append(rd)

    collection_snapshot: Optional[Dict[str, Any]] = None
    if collection_id is not None:
        col_row = cursor.execute(
            "SELECT id, name, description, cover_photo_id FROM collections WHERE id = ?",
            (int(collection_id),),
        ).fetchone()
        if col_row:
            item_rows = cursor.execute(
                "SELECT collection_id, photo_id, sort_order, added_at FROM collection_items WHERE collection_id = ? ORDER BY sort_order ASC",
                (int(collection_id),),
            ).fetchall()
            collection_snapshot = {
                "collection": dict(col_row),
                "items": [dict(ir) for ir in item_rows],
            }

    affected_count = len(photo_rows) + (
        len(collection_snapshot["items"]) if collection_snapshot and not photo_rows else 0
    )
    if affected_count == 0 and collection_snapshot is None:
        conn.close()
        return None

    payload = {
        "action_type": action_type,
        "description": description,
        "photo_rows": photo_rows,
        "collection_snapshot": collection_snapshot,
    }
    cursor.execute(
        """
        INSERT INTO undo_history (action_type, description, affected_count, snapshot_json)
        VALUES (?, ?, ?, ?)
        """,
        (action_type, description, affected_count, json.dumps(payload)),
    )
    undo_id = int(cursor.lastrowid or 0)

    # Prune old undo entries beyond max_history
    cursor.execute(
        """
        DELETE FROM undo_history
        WHERE id NOT IN (
            SELECT id FROM undo_history ORDER BY id DESC LIMIT ?
        )
        """,
        (max_history,),
    )
    conn.commit()
    conn.close()
    return undo_id


def get_undo_status(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Returns the current Undo stack depth and the most recent undoable action."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    _ensure_undo_table(conn)

    count_row = cursor.execute("SELECT COUNT(*) FROM undo_history").fetchone()
    total_available = int(count_row[0]) if count_row else 0

    latest_row = cursor.execute(
        """
        SELECT id, action_type, description, affected_count, created_at
        FROM undo_history
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    latest = dict(latest_row) if latest_row else None
    if latest and "action_label" not in latest:
        latest["action_label"] = latest.get("description") or latest.get("action_type") or "Studio Action"
    return {
        "available": total_available > 0,
        "can_undo": total_available > 0,
        "count": total_available,
        "undo_count": total_available,
        "latest": latest,
    }


def pop_and_restore_undo(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Pops the most recent snapshot from `undo_history` and atomically restores all
    affected `photo_records` and/or `collections` + `collection_items` rows.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    _ensure_undo_table(conn)

    latest_row = cursor.execute(
        """
        SELECT id, action_type, description, affected_count, snapshot_json, created_at
        FROM undo_history
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()

    if not latest_row:
        conn.close()
        return {
            "status": "empty",
            "available": False,
            "can_undo": False,
            "count": 0,
            "undo_count": 0,
            "message": "Nothing to undo.",
        }

    undo_id = int(latest_row["id"])
    action_type = str(latest_row["action_type"])
    description = str(latest_row["description"])
    snapshot = json.loads(latest_row["snapshot_json"] or "{}")

    restored_photo_paths: List[str] = []
    restored_photo_hashes: List[str] = []

    photo_rows = snapshot.get("photo_rows") or []
    if photo_rows:
        update_cols = [c for c in _UNDO_COLUMNS if c != "file_path"]
        set_clause = ", ".join(f"{col} = ?" for col in update_cols)
        sql = f"UPDATE photo_records SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?"

        params_batch = []
        for r in photo_rows:
            fp = r.get("file_path")
            if not fp:
                continue
            row_vals = [r.get(col) for col in update_cols]
            row_vals.append(fp)
            params_batch.append(tuple(row_vals))
            restored_photo_paths.append(fp)
            if r.get("file_hash"):
                restored_photo_hashes.append(str(r["file_hash"]))

        if params_batch:
            cursor.executemany(sql, params_batch)

        if action_type == "reclassify_subject" and (restored_photo_hashes or restored_photo_paths):
            try:
                for fh in restored_photo_hashes:
                    cursor.execute(
                        """
                        DELETE FROM vector_concept_boundaries
                        WHERE id IN (
                            SELECT id FROM vector_concept_boundaries
                            WHERE photo_id = ? OR file_hash = ?
                            ORDER BY id DESC LIMIT 1
                        )
                        """,
                        (fh, fh),
                    )
            except Exception:
                pass

    col_snap = snapshot.get("collection_snapshot")
    restored_collection_id: Optional[int] = None
    if col_snap and col_snap.get("collection"):
        c_info = col_snap["collection"]
        cid = int(c_info["id"])
        restored_collection_id = cid
        existing_col = cursor.execute("SELECT id FROM collections WHERE id = ?", (cid,)).fetchone()
        if existing_col:
            cursor.execute(
                "UPDATE collections SET name = ?, description = ?, cover_photo_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (c_info.get("name"), c_info.get("description"), c_info.get("cover_photo_id"), cid),
            )
        else:
            cursor.execute(
                "INSERT INTO collections (id, name, description, cover_photo_id) VALUES (?, ?, ?, ?)",
                (cid, c_info.get("name"), c_info.get("description"), c_info.get("cover_photo_id")),
            )

        cursor.execute("DELETE FROM collection_items WHERE collection_id = ?", (cid,))
        items = col_snap.get("items") or []
        for item in items:
            cursor.execute(
                "INSERT OR IGNORE INTO collection_items (collection_id, photo_id, sort_order) VALUES (?, ?, ?)",
                (cid, item.get("photo_id"), int(item.get("sort_order") or 0)),
            )

    # Remove the popped undo record
    cursor.execute("DELETE FROM undo_history WHERE id = ?", (undo_id,))
    conn.commit()

    remaining_row = cursor.execute("SELECT COUNT(*) FROM undo_history").fetchone()
    remaining_count = int(remaining_row[0]) if remaining_row else 0
    next_latest_row = cursor.execute(
        "SELECT id, action_type, description, affected_count, created_at FROM undo_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    next_latest = dict(next_latest_row) if next_latest_row else None
    if next_latest and "action_label" not in next_latest:
        next_latest["action_label"] = next_latest.get("description") or next_latest.get("action_type") or "Studio Action"

    return {
        "status": "ok",
        "undone_id": undo_id,
        "action_type": action_type,
        "action_label": description,
        "description": description,
        "restored_photo_count": len(restored_photo_paths),
        "restored_photos_count": len(restored_photo_paths),
        "restored_file_paths": restored_photo_paths,
        "restored_file_hashes": restored_photo_hashes,
        "restored_collection_id": restored_collection_id,
        "available": remaining_count > 0,
        "can_undo": remaining_count > 0,
        "count": remaining_count,
        "undo_count": remaining_count,
        "latest": next_latest,
        "undo_status": {
            "available": remaining_count > 0,
            "can_undo": remaining_count > 0,
            "count": remaining_count,
            "undo_count": remaining_count,
            "latest": next_latest,
        },
        "message": f"Undid: {description}",
    }

