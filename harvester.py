#!/usr/bin/env python3
"""
Phase 1 Harvester Engine (harvester.py)
AI Photo Archival System v3.0 — Mitch Rouse Architecture

Implements:
1. Strict Lightroom Cache Exclusion (*.lrdata, *.lrcat*, Pre-views.db, Smart Previews, Backups)
2. .IIQ + .TIF Sibling Pairing (single database row per capture with primary RAW + sibling_path)
3. Read-Only Lightroom Classic (.lrcat) SQLite Harvester (ratings, flags, color labels, AgLibraryKeyword trees)
4. Omni-Field ExifTool + Companion .xmp / .IIQ.xmp Sidecar Harvester (never deletes or modifies sidecars/RAWs)
5. Cross-Catalog Keepers Linker (stem & pHash matching against Keepers portfolio)
"""

import os
import re
import fnmatch
import json
import shutil
import sqlite3
import tempfile
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set

import exiftool
import imagehash

from db_schema import (
    DEFAULT_DB_PATH,
    get_db_connection,
    compute_file_hash,
    normalize_shoot_date,
    log_ingestion_error,
)

SCRIPT_DIR = Path(__file__).resolve().parent
os.environ["PATH"] = f"{SCRIPT_DIR}/bin:{SCRIPT_DIR}/.venv/bin:{os.environ.get('PATH', '')}"

# Extension priority for pairing .IIQ + .TIF (or RAW + derivative) siblings
RAW_PRIORITY_ORDER = [
    ".iiq", ".dng", ".nef", ".arw", ".cr3", ".cr2",
    ".raf", ".orf", ".rw2", ".pef", ".srw", ".3fr",
]
DERIVATIVE_PRIORITY_ORDER = [
    ".tif", ".tiff", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp"
]
ALL_SUPPORTED_EXTENSIONS = set(RAW_PRIORITY_ORDER + DERIVATIVE_PRIORITY_ORDER)

EXCLUDED_DIR_PATTERNS = [
    "*.lrdata",
    "*.lrcat*",
    "Smart Previews*",
    "Backups",
    ".Spotlight-V100",
    ".Trashes",
    ".fseventsd",
    "__MACOSX",
    "cache",
    "thumbs_360",
    "previews_1600",
    ".git",
    ".venv",
    "node_modules",
]

EXCLUDED_FILE_PATTERNS = [
    "Pre-views.db",
    "Previews.db",
    "root-pixels.db",
    "*.lrcat",
    "*.lrcat-wal",
    "*.lrcat-shm",
    "*.lrcat.lock",
    ".DS_Store",
    "._*",
]

# Omni-field tags harvested from RAW, sibling TIF, and companion .xmp / .IIQ.xmp sidecars
OMNI_EXIF_TAGS = [
    # Keywords & Hierarchical Taxonomies
    "IPTC:Keywords",
    "XMP-dc:Subject",
    "XMP:Subject",
    "XMP-lr:HierarchicalSubject",
    "XMP-digiKam:TagsList",
    # Captions & Descriptions
    "IPTC:Caption-Abstract",
    "XMP-dc:Description",
    "EXIF:ImageDescription",
    "XMP-exif:UserComment",
    "EXIF:UserComment",
    # Titles & Headlines
    "IPTC:ObjectName",
    "IPTC:Headline",
    "XMP-dc:Title",
    # Locations & GPS + ExifTool Offline Geolocation
    "IPTC:Sub-location",
    "XMP-iptcCore:Location",
    "IPTC:City",
    "XMP-photoshop:City",
    "IPTC:Province-State",
    "XMP-photoshop:State",
    "IPTC:Country-PrimaryLocationName",
    "XMP-photoshop:Country",
    "Composite:GPSLatitude",
    "Composite:GPSLongitude",
    "Composite:GPSAltitude",
    "GPS:GPSLatitude",
    "GPS:GPSLongitude",
    "GPS:GPSAltitude",
    "GPS:GPSLatitudeRef",
    "GPS:GPSLongitudeRef",
    "EXIF:GPSLatitude",
    "EXIF:GPSLongitude",
    "EXIF:GPSAltitude",
    "EXIF:GPSLatitudeRef",
    "EXIF:GPSLongitudeRef",
    "GeolocationCity",
    "GeolocationRegion",
    "GeolocationSubregion",
    "GeolocationCountry",
    "GeolocationCountryCode",
    # Ratings & Labels
    "XMP:Rating",
    "EXIF:Rating",
    "XMP:Label",
    # Camera, Software & Exposure EXIF
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
    "XMP:DateCreated",
    "QuickTime:CreateDate",
    "QuickTime:CreationDate",
    "EXIF:Make",
    "EXIF:Model",
    "EXIF:Software",
    "XMP:CreatorTool",
    "PNG:Software",
    "EXIF:SerialNumber",
    "EXIF:InternalSerialNumber",
    "MakerNotes:SerialNumber",
    "EXIF:LensModel",
    "XMP-aux:Lens",
    "EXIF:FocalLength",
    "EXIF:ExposureTime",
    "EXIF:FNumber",
    "EXIF:ISO",
    "EXIF:ExposureBiasValue",
]

# Offline Iconic Landmark & National Park Coordinate Proximity Table:
# (lat, lon, radius_km, specific_location, city, state_region, country, extra_tags)
_OFFLINE_LANDMARK_COORDS: List[Tuple[float, float, float, str, Optional[str], Optional[str], str, List[str]]] = [
    (37.7456, -119.5936, 28.0, "Yosemite National Park", "Yosemite Valley", "California", "United States", ["Yosemite", "National Parks & Mountains", "Mountains"]),
    (38.0071, -119.0124, 18.0, "Mono Lake", "Lee Vining", "California", "United States", ["Mono Lake", "Eastern Sierra & Highway 395", "Desert"]),
    (36.6063, -118.1128, 18.0, "Alabama Hills", "Lone Pine", "California", "United States", ["Alabama Hills", "Eastern Sierra & Highway 395", "Desert"]),
    (36.5054, -117.0794, 45.0, "Death Valley National Park", "Furnace Creek", "California", "United States", ["Death Valley", "Desert"]),
    (36.2704, -121.8081, 25.0, "Big Sur", "Big Sur", "California", "United States", ["Big Sur", "California Coast", "Coastline & Piers"]),
    (36.5165, -121.9427, 8.0, "Point Lobos", "Carmel-by-the-Sea", "California", "United States", ["Point Lobos", "California Coast", "Coastline & Piers"]),
    (35.1425, -119.4565, 18.0, "Taft Oil Field", "Taft", "California", "United States", ["Taft Oil Field", "Oil Fields", "Oil Fields & Industrial"]),
    (35.1897, -119.7911, 22.0, "Carrizo Plain", "California Valley", "California", "United States", ["Carrizo Plain", "California"]),
    (33.8734, -115.9010, 35.0, "Joshua Tree National Park", "Joshua Tree", "California", "United States", ["Joshua Tree", "Desert"]),
    (33.2559, -116.3989, 25.0, "Anza-Borrego Desert", "Borrego Springs", "California", "United States", ["Anza-Borrego Desert", "Desert"]),
    (39.0968, -120.0324, 24.0, "Lake Tahoe", "South Lake Tahoe", "California", "United States", ["Lake Tahoe", "Mountains", "National Parks & Mountains"]),
    (43.7904, -110.6818, 35.0, "Grand Teton National Park", "Jackson", "Wyoming", "United States", ["Grand Tetons", "Mountains", "National Parks & Mountains"]),
    (44.4280, -110.5885, 55.0, "Yellowstone National Park", "Yellowstone", "Wyoming", "United States", ["Yellowstone", "National Parks & Mountains"]),
    (44.5902, -104.7146, 12.0, "Devils Tower", "Devils Tower", "Wyoming", "United States", ["Devils Tower", "Butte", "Buttes"]),
    (36.0544, -112.1401, 40.0, "Grand Canyon National Park", "Grand Canyon Village", "Arizona", "United States", ["Grand Canyon", "National Parks & Mountains"]),
    (36.9980, -110.0985, 25.0, "Monument Valley", "Monument Valley", "Arizona", "United States", ["Monument Valley", "Butte", "Buttes", "Desert"]),
    (37.2667, -109.8333, 18.0, "Valley of the Gods", "Mexican Hat", "Utah", "United States", ["Valley of the Gods", "Butte", "Buttes", "Desert"]),
    (38.3269, -109.8783, 35.0, "Canyonlands National Park", "Moab", "Utah", "United States", ["Canyonlands & Moab", "Desert"]),
    (38.7331, -109.5925, 22.0, "Arches National Park", "Moab", "Utah", "United States", ["Canyonlands & Moab", "Desert"]),
    (37.2982, -113.0263, 25.0, "Zion National Park", "Springdale", "Utah", "United States", ["Zion", "Desert"]),
    (37.5930, -112.1871, 20.0, "Bryce Canyon National Park", "Bryce", "Utah", "United States", ["Bryce Canyon", "Desert"]),
    (32.7872, -106.3257, 28.0, "White Sands National Park", "Alamogordo", "New Mexico", "United States", ["White Sands", "Desert"]),
    (25.2866, -80.8987, 45.0, "Everglades National Park", "Homestead", "Florida", "United States", ["Everglades", "National Parks & Mountains"]),
    (47.0326, -117.2966, 38.0, "Palouse", "Colfax", "Washington", "United States", ["Palouse", "Farmland", "Palouse & Farmland"]),
    (46.8523, -121.7603, 25.0, "Mount Rainier National Park", "Ashford", "Washington", "United States", ["Mount Rainier", "Mountains", "National Parks & Mountains"]),
    (47.8021, -123.6044, 38.0, "Olympic National Park", "Port Angeles", "Washington", "United States", ["Olympic National Park", "National Parks & Mountains"]),
    (45.5762, -122.1158, 15.0, "Multnomah Falls", "Bridal Veil", "Oregon", "United States", ["Multnomah Falls", "Columbia River Gorge", "Oregon"]),
    (42.9446, -122.1090, 22.0, "Crater Lake National Park", "Crater Lake", "Oregon", "United States", ["Crater Lake", "Oregon", "National Parks & Mountains"]),
    (45.8918, -123.9615, 14.0, "Cannon Beach", "Cannon Beach", "Oregon", "United States", ["Cannon Beach", "Oregon Coast", "Coastline & Piers"]),
    (43.1180, -124.4307, 18.0, "Bandon Coast", "Bandon", "Oregon", "United States", ["Bandon Coast", "Oregon Coast", "Coastline & Piers"]),
    (48.7596, -113.7870, 45.0, "Glacier National Park", "West Glacier", "Montana", "United States", ["Glacier National Park", "Montana", "National Parks & Mountains"]),
    (34.8697, -111.7610, 22.0, "Sedona", "Sedona", "Arizona", "United States", ["Sedona", "Arizona", "Desert"]),
    (36.8619, -111.3743, 18.0, "Antelope Canyon & Horseshoe Bend", "Page", "Arizona", "United States", ["Antelope Canyon", "Page", "Arizona", "Desert"]),
    (64.0484, -16.1794, 18.0, "Jökulsárlón & Diamond Beach", "Jökulsárlón", "Austurland", "Iceland", ["Iceland", "Jökulsárlón & Diamond Beach", "Glacial Ice & Black Sand"]),
    (64.9417, -23.3069, 15.0, "Kirkjufell Mountain", "Grundarfjörður", "Vesturland", "Iceland", ["Iceland", "Kirkjufell Mountain"]),
    (64.3271, -20.1199, 15.0, "Gullfoss Waterfall", "Bláskógabyggð", "Suðurland", "Iceland", ["Iceland", "Gullfoss & Icelandic Waterfalls"]),
    (64.1417, -21.9266, 12.0, "Hallgrímskirkja, Reykjavík", "Reykjavík", "Capital Region", "Iceland", ["Iceland", "Hallgrímskirkja, Reykjavík"]),
    (63.4042, -19.0450, 14.0, "Reynisfjara Black Sand Beach", "Vík", "Suðurland", "Iceland", ["Iceland", "Reynisfjara Black Sand Beach"]),
]

_GEOLOCATION_CACHE: Dict[Tuple[float, float], Dict[str, Any]] = {}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def resolve_offline_gps_location(
    lat: float,
    lon: float,
    meta_dicts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    100% Offline Reverse-Geocoder:
    Converts decimal `(lat, lon)` coordinates into `{country, state_region, city, sub_location,
    specific_location, tags, hierarchy, gps_ground_truth}` using:
    1. Curated National Parks & Iconic Photography Landmarks proximity table (`_OFFLINE_LANDMARK_COORDS`)
    2. ExifTool's built-in offline Geolocation database (`GeolocationCity`, `GeolocationRegion`,
       `GeolocationSubregion`, `GeolocationCountry`) — either already harvested in `meta_dicts`
       or queried offline via `./bin/exiftool -api Geolocation=lat,lon -j`.
    """
    cache_key = (round(float(lat), 4), round(float(lon), 4))
    if cache_key in _GEOLOCATION_CACHE and not meta_dicts:
        return dict(_GEOLOCATION_CACHE[cache_key])

    # 1. Check proximity to iconic National Parks / Landmarks first
    matched_landmark = None
    best_dist = 999999.0
    for lm_lat, lm_lon, rad_km, lm_spec, lm_city, lm_state, lm_country, lm_tags in _OFFLINE_LANDMARK_COORDS:
        d_km = _haversine_km(lat, lon, lm_lat, lm_lon)
        if d_km <= rad_km and d_km < best_dist:
            best_dist = d_km
            matched_landmark = (lm_spec, lm_city, lm_state, lm_country, list(lm_tags))

    # 2. Extract ExifTool offline Geolocation fields from meta_dicts if present
    geo_city: Optional[str] = None
    geo_region: Optional[str] = None
    geo_subregion: Optional[str] = None
    geo_country: Optional[str] = None

    if meta_dicts:
        geo_city = _first_non_empty(meta_dicts, ["ExifTool:GeolocationCity", "Extra:GeolocationCity", "GeolocationCity"])
        geo_region = _first_non_empty(meta_dicts, ["ExifTool:GeolocationRegion", "Extra:GeolocationRegion", "GeolocationRegion"])
        geo_subregion = _first_non_empty(meta_dicts, ["ExifTool:GeolocationSubregion", "Extra:GeolocationSubregion", "GeolocationSubregion"])
        geo_country = _first_non_empty(meta_dicts, ["ExifTool:GeolocationCountry", "Extra:GeolocationCountry", "GeolocationCountry"])

    # 3. If not in meta_dicts, run fast offline ExifTool Geolocation lookup
    if not (geo_city or geo_region or geo_country):
        if cache_key in _GEOLOCATION_CACHE:
            cached = _GEOLOCATION_CACHE[cache_key]
            geo_city = cached.get("city")
            geo_region = cached.get("state_region")
            geo_subregion = cached.get("sub_location")
            geo_country = cached.get("country")
        else:
            try:
                import subprocess
                et_bin = str(SCRIPT_DIR / "bin" / "exiftool")
                if not os.path.exists(et_bin):
                    et_bin = shutil.which("exiftool") or "exiftool"
                proc = subprocess.run(
                    [et_bin, "-api", f"Geolocation={lat:.6f},{lon:.6f}", "-j"],
                    capture_output=True,
                    text=True,
                    timeout=3.0,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    arr = json.loads(proc.stdout)
                    if isinstance(arr, list) and arr:
                        gobj = arr[0]
                        geo_city = str(gobj.get("GeolocationCity") or "").strip() or None
                        geo_region = str(gobj.get("GeolocationRegion") or "").strip() or None
                        geo_subregion = str(gobj.get("GeolocationSubregion") or "").strip() or None
                        geo_country = str(gobj.get("GeolocationCountry") or "").strip() or None
            except Exception as exc:
                logging.debug(f"Offline ExifTool geolocation lookup skipped for ({lat}, {lon}): {exc}")

    country = (matched_landmark[3] if matched_landmark else None) or geo_country or "United States"
    state_region = (matched_landmark[2] if matched_landmark else None) or geo_region or None
    city = (matched_landmark[1] if matched_landmark else None) or geo_city or None
    if matched_landmark and geo_region and matched_landmark[2] and geo_region.lower() != matched_landmark[2].lower():
        sub_location = matched_landmark[0]
    else:
        sub_location = (matched_landmark[0] if matched_landmark else None) or geo_subregion or None

    if matched_landmark:
        specific_location = matched_landmark[0]
    elif city and state_region:
        specific_location = f"{city}, {state_region}"
    elif city and country and country != "United States":
        specific_location = f"{city}, {country}"
    else:
        specific_location = city or sub_location or state_region or country

    tags: List[str] = []
    if matched_landmark:
        for t in matched_landmark[4]:
            if t and t != "National Parks & Mountains" and t not in tags:
                tags.append(t)

    hier_parts = ["Places", country]
    if state_region:
        hier_parts.append(state_region)
    if matched_landmark and matched_landmark[0] not in hier_parts:
        hier_parts.append(matched_landmark[0])
    elif city and city not in hier_parts:
        hier_parts.append(city)
    hierarchy = "|".join(hier_parts)

    res = {
        "country": country,
        "state_region": state_region,
        "city": city,
        "sub_location": sub_location,
        "specific_location": specific_location,
        "tags": tags,
        "hierarchy": hierarchy,
        "gps_ground_truth": 1,
    }
    _GEOLOCATION_CACHE[cache_key] = res
    return dict(res)


def is_excluded_path(path: Path, root_dir: Optional[Path] = None) -> bool:
    """
    Strictly checks if a file or any of its directories inside root_dir match Lightroom cache
    or system exclusion rules (*.lrdata, *.lrcat*, Pre-views.db, Smart Previews, Backups).
    """
    name = path.name
    if name.startswith("._") or name == ".DS_Store" or name.startswith("."):
        return True
    for pat in EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatchcase(name.lower(), pat.lower()):
            return True

    parts_to_check = path.parts
    if root_dir is not None:
        try:
            parts_to_check = path.relative_to(root_dir).parts[:-1]
        except Exception:
            parts_to_check = path.parts[:-1]

    for part in parts_to_check:
        part_low = part.lower()
        for dpat in EXCLUDED_DIR_PATTERNS:
            if fnmatch.fnmatchcase(part_low, dpat.lower()):
                return True
    return False


def _ext_rank(ext: str) -> int:
    """Lower rank number = higher priority as primary file_path."""
    ext_low = ext.lower()
    if ext_low in RAW_PRIORITY_ORDER:
        return RAW_PRIORITY_ORDER.index(ext_low)
    if ext_low in DERIVATIVE_PRIORITY_ORDER:
        return len(RAW_PRIORITY_ORDER) + DERIVATIVE_PRIORITY_ORDER.index(ext_low)
    return 999


def discover_catalog_files(root_dir: Path) -> Tuple[List[Dict[str, Optional[Path]]], List[Path]]:
    """
    Walks root_dir while strictly excluding Lightroom caches (*.lrdata, Smart Previews, Backups).
    Supports standalone folders (no .lrcat required) as well as Lightroom catalog folders.
    Groups files in the same folder sharing the same case-insensitive stem so .IIQ + .TIF or .RAF + .JPG
    siblings become a single entry: {'primary': Path, 'sibling': Optional[Path], 'all_files': List[Path]}.
    Also returns any discovered .lrcat files in root_dir.
    """
    root_dir = Path(root_dir).expanduser().resolve()
    if not root_dir.exists():
        return [], []

    lrcat_files: List[Path] = []
    grouped: Dict[Tuple[str, str], List[Path]] = {}

    for dirpath, dirnames, filenames in os.walk(str(root_dir)):
        curr_dir = Path(dirpath)
        # Prune excluded directories in-place so os.walk never descends into *.lrdata or Backups
        dirnames[:] = [
            d for d in dirnames
            if not any(fnmatch.fnmatchcase(d.lower(), pat.lower()) for pat in EXCLUDED_DIR_PATTERNS)
            and not d.startswith(".")
        ]

        # Deduplicate filenames to guard against macOS smbfs getdirentries64 repeat bug on >1000-file folders
        for fname in sorted(set(filenames)):
            fpath = curr_dir / fname
            if fname.lower().endswith(".lrcat") and not fname.startswith("._"):
                if fpath not in lrcat_files:
                    lrcat_files.append(fpath)
                continue

            if is_excluded_path(fpath, root_dir=root_dir):
                continue

            ext_low = fpath.suffix.lower()
            if ext_low not in ALL_SUPPORTED_EXTENSIONS:
                continue

            key = (str(curr_dir), fpath.stem.lower())
            bucket = grouped.setdefault(key, [])
            if fpath not in bucket:
                bucket.append(fpath)

    paired_items: List[Dict[str, Any]] = []
    for (_, _), candidates in sorted(grouped.items(), key=lambda x: x[0]):
        sorted_cands = sorted(candidates, key=lambda p: (_ext_rank(p.suffix), p.name))
        primary = sorted_cands[0]
        sibling = sorted_cands[1] if len(sorted_cands) > 1 else None
        paired_items.append({
            "primary": primary,
            "sibling": sibling,
            "all_files": sorted_cands,
        })

    return paired_items, lrcat_files


def _extract_exact_frame_stem(base_name: str) -> Tuple[str, str]:
    """
    Returns (stripped_date_stem, canonical_frame_stem) for matching print derivatives
    to their original camera capture record without merging generic stems like 'untitled'.
    """
    s = re.sub(r"^\d{4}_\d{2}_\d{2}\s*-\s*", "", str(base_name or "").strip()).strip()
    s_clean = re.sub(
        r"((?:[-_](?:edit|copy|fnl|print|master|\d+x\d+))|-\d+)+$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip().lower()
    s_cf = re.sub(r"^(cf\d+)_\d+$", r"\1", s_clean, flags=re.IGNORECASE)
    if re.match(r"^(untitled|tests?|img|cf|dunes|emptyname|hdr_test|merge_auto|_mg)$", s_cf):
        s_cf = s.lower()
    return s.lower(), s_cf


def _sanitize_capture_time(
    raw_ct: Optional[str],
    has_camera_exif: bool,
    base_name: str,
    date_year: Optional[Any] = None,
    date_month: Optional[Any] = None,
    date_day: Optional[Any] = None,
) -> Optional[str]:
    """
    Validates capture_time against bogus epochs (<= 1989) and batch-export timestamps
    (2018-07-02 flattened print exports with zero camera EXIF).
    """
    ct = str(raw_ct or "").strip()
    if not ct and date_year is not None and date_month is not None and date_day is not None:
        try:
            y, m, d = int(round(float(date_year))), int(round(float(date_month))), int(round(float(date_day)))
            if 1990 <= y <= 2035:
                ct = f"{y:04d}-{m:02d}-{d:02d}T00:00:00"
        except Exception:
            pass

    if ct:
        norm_d = normalize_shoot_date(ct)
        if norm_d == "Undated":
            return None
        # Guardrail against 2018-07-02 batch print export timestamp when camera EXIF is absent
        if norm_d == "2018-07-02" and not has_camera_exif:
            s_inner, _ = _extract_exact_frame_stem(base_name)
            m_inner = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{2})(?:[._-]|$)", s_inner)
            if m_inner:
                mm, dd, yy = int(m_inner.group(1)), int(m_inner.group(2)), int(m_inner.group(3))
                yyyy = 2000 + yy if yy < 70 else 1900 + yy
                if 1 <= mm <= 12 and 1 <= dd <= 31:
                    return f"{yyyy:04d}-{mm:02d}-{dd:02d}T12:00:00"
            return None
        return ct
    return None


def harvest_lrcat_metadata(lrcat_path: Path, db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Dict[str, Any]]:
    """
    Copies a Lightroom Classic (.lrcat) SQLite database (and any sibling *Previews.lrdata/previews.db)
    to a local temporary directory in tempfile.gettempdir() before querying so SMB mounts and
    filenames with spaces never trigger sqlite3.OperationalError locking/URI errors.
    Extracts star ratings, pick flags, color labels, hierarchical/flat AgLibraryKeyword trees,
    and resolves the matching .lrprev pyramid preview file path for each image.
    Returns a dictionary keyed by normalized lowercase file stem and full path.
    """
    lrcat_path = Path(lrcat_path).expanduser().resolve()
    if not lrcat_path.exists():
        return {}

    harvested_by_path: Dict[str, Dict[str, Any]] = {}
    harvested_by_stem: Dict[str, Dict[str, Any]] = {}

    tmp_lrcat: Optional[Path] = None
    tmp_prevdb: Optional[Path] = None
    conn: Optional[sqlite3.Connection] = None
    prev_conn: Optional[sqlite3.Connection] = None

    try:
        # 0. Copy .lrcat to local temp file to avoid SMB locking & URI space issues
        fd, tmp_lrcat_str = tempfile.mkstemp(suffix=".lrcat", prefix="agy_lrcat_")
        os.close(fd)
        tmp_lrcat = Path(tmp_lrcat_str)
        shutil.copy2(str(lrcat_path), str(tmp_lrcat))

        # Check for sibling *Previews.lrdata/previews.db
        previews_lrdata_dir: Optional[Path] = None
        exact_prev_dir = lrcat_path.parent / f"{lrcat_path.stem} Previews.lrdata"
        if (exact_prev_dir / "previews.db").exists():
            previews_lrdata_dir = exact_prev_dir
        else:
            for cand_dir in sorted(lrcat_path.parent.glob("*Previews.lrdata")):
                if (cand_dir / "previews.db").exists():
                    previews_lrdata_dir = cand_dir
                    break

        prev_by_img_id: Dict[int, Tuple[str, str, str]] = {}
        prev_by_uuid: Dict[str, Tuple[str, str, str]] = {}

        if previews_lrdata_dir is not None:
            try:
                prev_db_src = previews_lrdata_dir / "previews.db"
                fd_p, tmp_prev_str = tempfile.mkstemp(suffix=".db", prefix="agy_prevdb_")
                os.close(fd_p)
                tmp_prevdb = Path(tmp_prev_str)
                shutil.copy2(str(prev_db_src), str(tmp_prevdb))

                prev_conn = sqlite3.connect(str(tmp_prevdb), timeout=15.0)
                prev_conn.row_factory = sqlite3.Row
                for pr in prev_conn.execute("SELECT imageId, uuid, digest, orientation FROM ImageCacheEntry;").fetchall():
                    uuid_str = str(pr["uuid"] or "").strip()
                    digest_str = str(pr["digest"] or "").strip()
                    orient_str = str(pr["orientation"] or "AB").strip()
                    if uuid_str and digest_str:
                        info_tuple = (uuid_str, digest_str, orient_str)
                        prev_by_uuid[uuid_str.upper()] = info_tuple
                        if pr["imageId"] is not None:
                            try:
                                prev_by_img_id[int(round(float(pr["imageId"])))] = info_tuple
                            except Exception:
                                pass
                prev_conn.close()
                prev_conn = None
            except Exception as prev_exc:
                log_ingestion_error(db_path, str(previews_lrdata_dir), "lrprev_db_harvest", type(prev_exc).__name__, str(prev_exc))

        conn = sqlite3.connect(str(tmp_lrcat), timeout=15.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        tables = {
            r["name"] for r in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        }

        if "Adobe_images" not in tables or "AgLibraryFile" not in tables:
            conn.close()
            conn = None
            return {}

        # 1. Build keyword hierarchy map from AgLibraryKeyword if present
        kw_map: Dict[int, Dict[str, Any]] = {}
        if "AgLibraryKeyword" in tables:
            kw_cols = {
                r["name"] for r in cursor.execute("PRAGMA table_info(AgLibraryKeyword);").fetchall()
            }
            name_col = "name" if "name" in kw_cols else "lc_name"
            parent_col = "parent" if "parent" in kw_cols else None
            include_col = "includeOnExport" if "includeOnExport" in kw_cols else None

            select_cols = f"id_local, {name_col}"
            if parent_col:
                select_cols += f", {parent_col}"
            if include_col:
                select_cols += f", {include_col}"

            for r in cursor.execute(f"SELECT {select_cols} FROM AgLibraryKeyword;").fetchall():
                kw_id = r["id_local"]
                kw_name = r[name_col]
                kw_parent = r[parent_col] if parent_col else None
                kw_map[kw_id] = {"name": kw_name, "parent": kw_parent}

        def get_kw_hierarchy(kw_id: int) -> Tuple[Optional[str], Optional[str]]:
            node = kw_map.get(kw_id)
            if not node or not node.get("name"):
                return None, None
            flat_name = str(node["name"]).strip()
            chain = [flat_name]
            curr_parent = node.get("parent")
            visited = {kw_id}
            while curr_parent and curr_parent in kw_map and curr_parent not in visited:
                visited.add(curr_parent)
                pnode = kw_map[curr_parent]
                pname = str(pnode.get("name") or "").strip()
                if pname:
                    chain.append(pname)
                curr_parent = pnode.get("parent")
            chain.reverse()
            hier = "|".join(chain) if len(chain) > 1 else flat_name
            return flat_name, hier

        # 2. Map image id_local -> keywords from AgLibraryKeywordImage
        img_keywords: Dict[int, Tuple[List[str], List[str]]] = {}
        if "AgLibraryKeywordImage" in tables and kw_map:
            for r in cursor.execute("SELECT image, tag FROM AgLibraryKeywordImage;").fetchall():
                img_id = r["image"]
                tag_id = r["tag"]
                flat_k, hier_k = get_kw_hierarchy(tag_id)
                if flat_k:
                    flats, hiers = img_keywords.setdefault(img_id, ([], []))
                    if flat_k not in flats:
                        flats.append(flat_k)
                    if hier_k and hier_k not in hiers:
                        hiers.append(hier_k)

        # 2b. Map image id_local -> EXIF from AgHarvestedExifMetadata if present
        img_exif: Dict[int, Dict[str, Any]] = {}
        if "AgHarvestedExifMetadata" in tables:
            try:
                cm_join = "LEFT JOIN AgInternedExifCameraModel cm ON e.cameraModelRef = cm.id_local" if "AgInternedExifCameraModel" in tables else ""
                cm_col = "cm.value AS camera_model" if "AgInternedExifCameraModel" in tables else "NULL AS camera_model"
                cs_join = "LEFT JOIN AgInternedExifCameraSN cs ON e.cameraSNRef = cs.id_local" if "AgInternedExifCameraSN" in tables else ""
                cs_col = "cs.value AS camera_sn" if "AgInternedExifCameraSN" in tables else "NULL AS camera_sn"
                ln_join = "LEFT JOIN AgInternedExifLens ln ON e.lensRef = ln.id_local" if "AgInternedExifLens" in tables else ""
                ln_col = "ln.value AS lens_model" if "AgInternedExifLens" in tables else "NULL AS lens_model"

                exif_q = f"""
                    SELECT e.image AS image_id, e.aperture, e.focalLength, e.isoSpeedRating,
                           e.shutterSpeed, e.gpsLatitude, e.gpsLongitude,
                           e.dateYear, e.dateMonth, e.dateDay,
                           {cm_col}, {cs_col}, {ln_col}
                    FROM AgHarvestedExifMetadata e
                    {cm_join}
                    {cs_join}
                    {ln_join}
                """
                for er in cursor.execute(exif_q).fetchall():
                    im_id = er["image_id"]
                    if im_id is None:
                        continue
                    ap_val = round(2.0 ** (float(er["aperture"]) / 2.0), 1) if er["aperture"] is not None else None
                    sh_val = None
                    if er["shutterSpeed"] is not None:
                        try:
                            sh_sec = 1.0 / (2.0 ** float(er["shutterSpeed"]))
                            sh_val = _format_shutter(sh_sec)
                        except Exception:
                            pass
                    img_exif[int(im_id)] = {
                        "camera_model": str(er["camera_model"]).strip() if er["camera_model"] else None,
                        "camera_serial": str(er["camera_sn"]).strip() if er["camera_sn"] else None,
                        "lens_model": str(er["lens_model"]).strip() if er["lens_model"] else None,
                        "focal_length": float(er["focalLength"]) if er["focalLength"] is not None else None,
                        "iso": int(round(float(er["isoSpeedRating"]))) if er["isoSpeedRating"] is not None else None,
                        "aperture": ap_val,
                        "shutter_speed": sh_val,
                        "gps_lat": float(er["gpsLatitude"]) if er["gpsLatitude"] is not None else None,
                        "gps_lon": float(er["gpsLongitude"]) if er["gpsLongitude"] is not None else None,
                        "date_year": er["dateYear"],
                        "date_month": er["dateMonth"],
                        "date_day": er["dateDay"],
                    }
            except Exception:
                pass

        # 3. Query Adobe_images + AgLibraryFile (+ optional Folder / RootFolder)
        img_cols = {
            r["name"] for r in cursor.execute("PRAGMA table_info(Adobe_images);").fetchall()
        }
        file_cols = {
            r["name"] for r in cursor.execute("PRAGMA table_info(AgLibraryFile);").fetchall()
        }
        cap_expr = "i.captureTime" if "captureTime" in img_cols else "''"
        img_uuid_expr = "i.id_global" if "id_global" in img_cols else "''"
        file_uuid_expr = "f.id_global" if "id_global" in file_cols else "''"
        has_folders = "AgLibraryFolder" in tables and "AgLibraryRootFolder" in tables
        if has_folders:
            query = f"""
                SELECT
                    i.id_local AS image_id,
                    {img_uuid_expr} AS image_uuid,
                    i.rating AS rating,
                    i.pick AS pick,
                    i.colorLabels AS color_label,
                    {cap_expr} AS capture_time,
                    {file_uuid_expr} AS file_uuid,
                    f.baseName AS base_name,
                    f.extension AS extension,
                    fl.pathFromRoot AS path_from_root,
                    rf.absolutePath AS root_path
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
                LEFT JOIN AgLibraryFolder fl ON f.folder = fl.id_local
                LEFT JOIN AgLibraryRootFolder rf ON fl.rootFolder = rf.id_local
            """
        else:
            query = f"""
                SELECT
                    i.id_local AS image_id,
                    {img_uuid_expr} AS image_uuid,
                    i.rating AS rating,
                    i.pick AS pick,
                    i.colorLabels AS color_label,
                    {cap_expr} AS capture_time,
                    {file_uuid_expr} AS file_uuid,
                    f.baseName AS base_name,
                    f.extension AS extension,
                    '' AS path_from_root,
                    '' AS root_path
                FROM Adobe_images i
                JOIN AgLibraryFile f ON i.rootFile = f.id_local
            """

        raw_lrcat_rows = cursor.execute(query).fetchall()

        # Pass 1: Build lookup of canonical frame stems that have true camera EXIF or valid non-export capture dates
        cam_sibling_by_frame: Dict[str, Dict[str, Any]] = {}
        earlier_sibling_by_frame: Dict[str, Dict[str, Any]] = {}
        for r in raw_lrcat_rows:
            img_id = int(r["image_id"])
            bname = str(r["base_name"] or "").strip()
            if not bname:
                continue
            ex = img_exif.get(img_id, {})
            has_cam = bool(ex.get("camera_model") or ex.get("aperture") is not None or ex.get("iso") is not None)
            clean_ct = _sanitize_capture_time(
                str(r["capture_time"] or "").strip(),
                has_cam,
                bname,
                ex.get("date_year"),
                ex.get("date_month"),
                ex.get("date_day"),
            )
            if clean_ct:
                s1, s2 = _extract_exact_frame_stem(bname)
                if has_cam:
                    cam_sibling_by_frame.setdefault(s1, {"capture_time": clean_ct, **ex})
                    if s2:
                        cam_sibling_by_frame.setdefault(s2, {"capture_time": clean_ct, **ex})
                elif not clean_ct.startswith("2018-07-02"):
                    earlier_sibling_by_frame.setdefault(s1, {"capture_time": clean_ct, **ex})
                    if s2:
                        earlier_sibling_by_frame.setdefault(s2, {"capture_time": clean_ct, **ex})

        for r in raw_lrcat_rows:
            img_id = int(r["image_id"])
            raw_base_name = str(r["base_name"] or "")
            base_name = raw_base_name.strip()
            ext = str(r["extension"] or "").strip()
            if not base_name:
                continue

            rating = int(round(float(r["rating"]))) if r["rating"] is not None else 0
            pick = int(round(float(r["pick"]))) if r["pick"] is not None else 0
            color_label = str(r["color_label"] or "").strip()
            ex = dict(img_exif.get(img_id, {}))
            has_cam = bool(ex.get("camera_model") or ex.get("aperture") is not None or ex.get("iso") is not None)
            s1, s2 = _extract_exact_frame_stem(base_name)

            # If this is a flattened print derivative with zero camera EXIF, inherit true camera captureTime & EXIF from its original frame sibling if present
            if not has_cam:
                sib = cam_sibling_by_frame.get(s1) or cam_sibling_by_frame.get(s2)
                if sib:
                    for k_ex in ("camera_model", "camera_serial", "lens_model", "focal_length", "iso", "aperture", "shutter_speed"):
                        if not ex.get(k_ex) and sib.get(k_ex) is not None:
                            ex[k_ex] = sib[k_ex]
                    has_cam = True
                    raw_ct_override = sib["capture_time"]
                else:
                    raw_ct_override = str(r["capture_time"] or "").strip()
            else:
                raw_ct_override = str(r["capture_time"] or "").strip()

            capture_time = _sanitize_capture_time(
                raw_ct_override,
                has_cam,
                base_name,
                ex.get("date_year"),
                ex.get("date_month"),
                ex.get("date_day"),
            )
            if not capture_time and not has_cam:
                sib_early = earlier_sibling_by_frame.get(s1) or earlier_sibling_by_frame.get(s2)
                if sib_early and sib_early.get("capture_time"):
                    capture_time = sib_early["capture_time"]

            flats, hiers = img_keywords.get(img_id, ([], []))

            # Resolve .lrprev path if previews.db was found
            lrprev_path_str: Optional[str] = None
            lrprev_orient: Optional[str] = None
            if previews_lrdata_dir is not None:
                prev_match = (
                    prev_by_img_id.get(int(img_id))
                    or prev_by_uuid.get(str(r["file_uuid"] or "").strip().upper())
                    or prev_by_uuid.get(str(r["image_uuid"] or "").strip().upper())
                )
                if prev_match:
                    u_str, d_str, o_str = prev_match
                    cand_lrprev = previews_lrdata_dir / u_str[0] / u_str[0:4] / f"{u_str}-{d_str}.lrprev"
                    lrprev_path_str = str(cand_lrprev)
                    lrprev_orient = o_str

            entry = {
                "star_rating": max(0, min(5, rating)),
                "pick_flag": pick,
                "color_label": color_label,
                "capture_time": capture_time or "",
                "flat_keywords": list(flats),
                "hierarchical_keywords": list(hiers),
                "lrprev_path": lrprev_path_str,
                "lrprev_orientation": lrprev_orient,
                **ex,
            }

            for stem_key in {base_name.lower(), raw_base_name.lower(), s1, s2}:
                if not stem_key:
                    continue
                if stem_key in harvested_by_stem:
                    prev = harvested_by_stem[stem_key]
                    prev["star_rating"] = max(prev["star_rating"], entry["star_rating"])
                    prev["pick_flag"] = max(prev["pick_flag"], entry["pick_flag"])
                    if not prev["color_label"] and entry["color_label"]:
                        prev["color_label"] = entry["color_label"]
                    if not prev.get("capture_time") and entry.get("capture_time"):
                        prev["capture_time"] = entry["capture_time"]
                    if not prev.get("camera_model") and entry.get("camera_model"):
                        prev["camera_model"] = entry["camera_model"]
                    if not prev.get("lrprev_path") and entry.get("lrprev_path"):
                        prev["lrprev_path"] = entry["lrprev_path"]
                        prev["lrprev_orientation"] = entry["lrprev_orientation"]
                    for k in entry["flat_keywords"]:
                        if k not in prev["flat_keywords"]:
                            prev["flat_keywords"].append(k)
                    for hk in entry["hierarchical_keywords"]:
                        if hk not in prev["hierarchical_keywords"]:
                            prev["hierarchical_keywords"].append(hk)
                else:
                    harvested_by_stem[stem_key] = {
                        **entry,
                        "flat_keywords": list(entry["flat_keywords"]),
                        "hierarchical_keywords": list(entry["hierarchical_keywords"]),
                    }

            root_p = str(r["root_path"] or "")
            rel_p = str(r["path_from_root"] or "")
            if root_p:
                full_p = os.path.normpath(os.path.join(root_p, rel_p, f"{raw_base_name}.{ext}")).lower()
                harvested_by_path[full_p] = harvested_by_stem[base_name.lower()]

        conn.close()
        conn = None
    except Exception as e:
        log_ingestion_error(db_path, str(lrcat_path), "lrcat_harvest", type(e).__name__, str(e))
    finally:
        for c in (conn, prev_conn):
            if c is not None:
                try:
                    c.close()
                except Exception:
                    pass
        for tmp_f in (tmp_lrcat, tmp_prevdb):
            if tmp_f is not None and tmp_f.exists():
                try:
                    tmp_f.unlink()
                except Exception:
                    pass

    return {
        "by_path": harvested_by_path,
        "by_stem": harvested_by_stem,
    }


def find_companion_sidecars(primary_path: Path, sibling_path: Optional[Path] = None) -> List[Path]:
    """
    Finds all existing companion .xmp / .IIQ.xmp sidecar files for a primary RAW and optional sibling.
    Never modifies or deletes any sidecar.
    """
    candidates: List[Path] = []
    for base in [primary_path, sibling_path]:
        if base is None:
            continue
        parent = base.parent
        # Standard .xmp replacement (e.g. CF001234.xmp)
        candidates.append(base.with_suffix(".xmp"))
        candidates.append(base.with_suffix(".XMP"))
        # Phase One / Capture One / Lightroom additive extension (e.g. CF001234.IIQ.xmp)
        candidates.append(parent / f"{base.name}.xmp")
        candidates.append(parent / f"{base.name}.XMP")

    existing_unique: List[Path] = []
    seen: Set[str] = set()
    for c in candidates:
        try:
            if c.exists() and c.is_file():
                resolved = str(c.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    existing_unique.append(c)
        except Exception:
            continue
    return existing_unique


def _to_list_of_strings(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        out = []
        for item in val:
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    s = str(val).strip()
    if not s:
        return []
    if "," in s and "|" not in s:
        return [p.strip() for p in s.split(",") if p.strip()]
    return [s]


def _first_non_empty(meta_list: List[Dict[str, Any]], keys: List[str]) -> Optional[str]:
    for meta in meta_list:
        for k in keys:
            val = meta.get(k)
            if val is None and ":" in k:
                bare_k = k.split(":", 1)[1]
                val = meta.get(bare_k)
                if val is None:
                    suffix_k = f":{bare_k}"
                    for mk, mv in meta.items():
                        if mk.endswith(suffix_k):
                            val = mv
                            break
            if val is not None:
                if isinstance(val, list):
                    joined = ", ".join(str(x).strip() for x in val if str(x).strip())
                    if joined:
                        return joined
                else:
                    s = str(val).strip()
                    if s and s.lower() not in ("none", "null", "unknown", ""):
                        return s
    return None


def _parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().lower().replace("mm", "").replace("f/", "").strip()
        if "/" in s:
            num, den = s.split("/", 1)
            return float(num) / float(den) if float(den) != 0 else None
        match = re.search(r"[-+]?\d*\.?\d+", s)
        return float(match.group(0)) if match else None
    except Exception:
        return None


def _parse_int(val: Any) -> Optional[int]:
    f = _parse_float(val)
    return int(round(f)) if f is not None else None


def _format_shutter(val: Any) -> Optional[str]:
    if val is None:
        return None
    try:
        f = float(val)
        if f <= 0:
            return None
        if f >= 1.0:
            return f"{f:.1f}s" if f % 1 != 0 else f"{int(f)}s"
        inv = int(round(1.0 / f))
        return f"1/{inv}s" if inv > 0 else str(val)
    except Exception:
        return str(val).strip()


def harvest_omni_metadata_batch(
    paired_items: List[Dict[str, Any]],
    lrcat_data: Optional[Dict[str, Dict[str, Any]]] = None,
    et_helper: Optional[exiftool.ExifToolHelper] = None,
    db_path: Path = DEFAULT_DB_PATH,
    fast_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Harvests metadata for a batch of paired items across:
    - Primary RAW / image file
    - Companion sibling (.TIF / .DNG)
    - Companion .xmp and .IIQ.xmp sidecar files
    - Read-only .lrcat records
    Never deletes or modifies any files.
    """
    own_et = False
    if et_helper is None and not fast_only:
        et_helper = exiftool.ExifToolHelper(
            common_args=["-G0", "-a", "-s", "-n", "-m", "-fast2", "-api", "Geolocation"]
        )
        et_helper.run()
        own_et = True

    results: List[Dict[str, Any]] = []
    lrcat_by_path = (lrcat_data or {}).get("by_path", {})
    lrcat_by_stem = (lrcat_data or {}).get("by_stem", {})

    try:
        for item in paired_items:
            primary: Path = item["primary"]
            sibling: Optional[Path] = item.get("sibling")

            # Match .lrcat metadata if available
            lr_entry = (
                lrcat_by_path.get(str(primary).lower())
                or lrcat_by_stem.get(primary.stem.lower())
                or lrcat_by_stem.get(primary.stem.strip().lower())
            )

            sidecars: List[Path] = []
            meta_dicts: List[Dict[str, Any]] = []

            if not fast_only:
                sidecars = find_companion_sidecars(primary, sibling)

                # Query ExifTool across all non-empty existing files for this capture
                sources_to_query: List[str] = []
                for cand in [primary, sibling] + sidecars:
                    if cand is not None and cand.exists():
                        try:
                            if cand.stat().st_size > 0:
                                sources_to_query.append(str(cand))
                        except Exception:
                            pass

                if sources_to_query and et_helper is not None:
                    try:
                        # Query sidecars and sibling as well as primary; sidecar tags take precedence for ratings/keywords
                        raw_metas = et_helper.get_tags(sources_to_query, OMNI_EXIF_TAGS)
                        if isinstance(raw_metas, list):
                            meta_dicts = raw_metas
                    except Exception:
                        # Fallback per-file if one file in batch had corrupt header
                        for src_f in sources_to_query:
                            try:
                                m = et_helper.get_tags([src_f], OMNI_EXIF_TAGS)
                                if m:
                                    meta_dicts.extend(m)
                            except Exception as inner_e:
                                log_ingestion_error(db_path, src_f, "exif_harvest", type(inner_e).__name__, str(inner_e))

            # Collect all flat and hierarchical keywords across RAW + TIF + .xmp + .IIQ.xmp
            flat_kws: List[str] = []
            hier_kws: List[str] = []

            for md in meta_dicts:
                for kw_tag in ["IPTC:Keywords", "XMP-dc:Subject", "XMP:Subject", "Keywords", "Subject"]:
                    for kw in _to_list_of_strings(md.get(kw_tag)):
                        if kw not in flat_kws:
                            flat_kws.append(kw)
                for h_tag in ["XMP-lr:HierarchicalSubject", "XMP:HierarchicalSubject", "XMP-digiKam:TagsList", "XMP:TagsList", "HierarchicalSubject"]:
                    for hkw in _to_list_of_strings(md.get(h_tag)):
                        if hkw not in hier_kws:
                            hier_kws.append(hkw)
                        # Also ensure leaf of hierarchical keyword is in flat_kws
                        leaf = hkw.split("|")[-1].split("/")[-1].strip()
                        if leaf and leaf not in flat_kws:
                            flat_kws.append(leaf)

            lrcat_kws: List[str] = []
            if lr_entry:
                for k in lr_entry.get("flat_keywords", []):
                    if k not in lrcat_kws:
                        lrcat_kws.append(k)
                    if k not in flat_kws:
                        flat_kws.append(k)
                for hk in lr_entry.get("hierarchical_keywords", []):
                    if hk not in hier_kws:
                        hier_kws.append(hk)
                    leaf = hk.split("|")[-1].split("/")[-1].strip()
                    if leaf and leaf not in flat_kws:
                        flat_kws.append(leaf)

            # Prioritize sidecar/TIF descriptions & titles while using RAW for camera EXIF
            meta_sidecar_first = list(reversed(meta_dicts)) if len(meta_dicts) > 1 else meta_dicts

            camera_make = _first_non_empty(meta_dicts, ["EXIF:Make"])
            camera_model = _first_non_empty(meta_dicts, ["EXIF:Model"]) or (lr_entry.get("camera_model") if lr_entry else None)
            camera_serial = _first_non_empty(
                meta_dicts,
                ["EXIF:SerialNumber", "EXIF:InternalSerialNumber", "MakerNotes:SerialNumber"]
            ) or (lr_entry.get("camera_serial") if lr_entry else None)
            lens_model = _first_non_empty(meta_dicts, ["EXIF:LensModel", "XMP-aux:Lens", "XMP:Lens", "Composite:LensID"]) or (lr_entry.get("lens_model") if lr_entry else None)
            focal_length = _parse_float(_first_non_empty(meta_dicts, ["EXIF:FocalLength", "XMP:FocalLength"])) or (lr_entry.get("focal_length") if lr_entry else None)
            shutter_speed = _format_shutter(_first_non_empty(meta_dicts, ["EXIF:ExposureTime", "XMP:ExposureTime"])) or (lr_entry.get("shutter_speed") if lr_entry else None)
            aperture = _parse_float(_first_non_empty(meta_dicts, ["EXIF:FNumber", "XMP:FNumber"])) or (lr_entry.get("aperture") if lr_entry else None)
            iso = _parse_int(_first_non_empty(meta_dicts, ["EXIF:ISO", "XMP:ISO"])) or (lr_entry.get("iso") if lr_entry else None)

            has_cam_exif = bool(camera_model or aperture is not None or iso is not None)
            raw_dto = _first_non_empty(meta_dicts, ["EXIF:DateTimeOriginal", "QuickTime:CreationDate", "QuickTime:CreateDate"])
            lr_ct = lr_entry.get("capture_time") if lr_entry else None
            raw_create = _first_non_empty(meta_dicts, ["EXIF:CreateDate", "XMP:DateCreated"])

            cand_ct = raw_dto or lr_ct or raw_create
            clean_ct = _sanitize_capture_time(cand_ct, has_cam_exif, primary.stem)
            if not clean_ct and lr_entry is None:
                # Fallback to non-2018_07_02 filename date pattern (e.g., "2025-04-12..." or "Screenshot 2025-04-12 at 14.22.10")
                m_pfx = re.search(r"(\d{4})[_-]?(\d{2})[_-]?(\d{2})", primary.stem.strip())
                if m_pfx:
                    y_p, m_p, d_p = int(m_pfx.group(1)), int(m_pfx.group(2)), int(m_pfx.group(3))
                    pfx_date = f"{y_p:04d}-{m_p:02d}-{d_p:02d}"
                    if 1990 <= y_p <= 2035 and 1 <= m_p <= 12 and 1 <= d_p <= 31 and pfx_date != "2018-07-02":
                        clean_ct = f"{pfx_date}T12:00:00"
            if clean_ct:
                exif_time = clean_ct.replace("T", " ").replace("-", ":")[:19]
                shoot_date = normalize_shoot_date(exif_time)
            else:
                exif_time = None
                shoot_date = "Undated"

            # Extract signed decimal GPS coordinates (prefer Composite:GPSLatitude/Longitude which include N/S and E/W signs)
            comp_lat = _parse_float(_first_non_empty(meta_dicts, ["Composite:GPSLatitude", "XMP:GPSLatitude"]))
            comp_lon = _parse_float(_first_non_empty(meta_dicts, ["Composite:GPSLongitude", "XMP:GPSLongitude"]))
            raw_lat = _parse_float(_first_non_empty(meta_dicts, ["GPS:GPSLatitude", "EXIF:GPSLatitude"]))
            raw_lon = _parse_float(_first_non_empty(meta_dicts, ["GPS:GPSLongitude", "EXIF:GPSLongitude"]))
            lat_ref = (_first_non_empty(meta_dicts, ["GPS:GPSLatitudeRef", "EXIF:GPSLatitudeRef"]) or "").strip().upper()
            lon_ref = (_first_non_empty(meta_dicts, ["GPS:GPSLongitudeRef", "EXIF:GPSLongitudeRef"]) or "").strip().upper()
            if raw_lat is not None and lat_ref.startswith("S") and raw_lat > 0:
                raw_lat = -raw_lat
            if raw_lon is not None and lon_ref.startswith("W") and raw_lon > 0:
                raw_lon = -raw_lon

            gps_lat = comp_lat if comp_lat is not None else (raw_lat if raw_lat is not None else (lr_entry.get("gps_lat") if lr_entry else None))
            gps_lon = comp_lon if comp_lon is not None else (raw_lon if raw_lon is not None else (lr_entry.get("gps_lon") if lr_entry else None))
            gps_alt = _parse_float(_first_non_empty(meta_dicts, ["Composite:GPSAltitude", "GPS:GPSAltitude", "EXIF:GPSAltitude"]))

            title = _first_non_empty(
                meta_sidecar_first,
                ["IPTC:ObjectName", "XMP-dc:Title", "XMP:Title", "IPTC:Headline", "XMP:Headline", "XMP-photoshop:Headline"]
            )
            caption = _first_non_empty(
                meta_sidecar_first,
                ["IPTC:Caption-Abstract", "XMP-dc:Description", "XMP:Description", "EXIF:ImageDescription", "XMP-exif:UserComment", "XMP:UserComment", "EXIF:UserComment"]
            )
            sub_location = _first_non_empty(
                meta_sidecar_first,
                ["IPTC:Sub-location", "XMP-iptcCore:Location", "XMP:Location", "XMP:Sub-location"]
            )
            city = _first_non_empty(meta_sidecar_first, ["IPTC:City", "XMP-photoshop:City", "XMP:City"])
            state_region = _first_non_empty(meta_sidecar_first, ["IPTC:Province-State", "XMP-photoshop:State", "XMP:State", "XMP:Province-State"])
            country = _first_non_empty(meta_sidecar_first, ["IPTC:Country-PrimaryLocationName", "XMP-photoshop:Country", "XMP:Country"])

            # Offline GPS Reverse-Geocoding Ground Truth:
            # Whenever decimal GPS coordinates exist, resolve city, state_region, country, and nearby landmarks offline!
            gps_ground_truth = 0
            if gps_lat is not None and gps_lon is not None and not (abs(gps_lat) < 0.0001 and abs(gps_lon) < 0.0001):
                explicit_sub_location = sub_location
                geo_resolved = resolve_offline_gps_location(gps_lat, gps_lon, meta_dicts=meta_dicts)
                gps_ground_truth = 1
                country = country or geo_resolved.get("country")
                state_region = state_region or geo_resolved.get("state_region")
                city = city or geo_resolved.get("city")
                sub_location = explicit_sub_location or geo_resolved.get("sub_location")
                specific_location = explicit_sub_location or geo_resolved.get("specific_location") or city or state_region
                for g_tag in geo_resolved.get("tags", []):
                    if g_tag and g_tag not in flat_kws:
                        flat_kws.append(g_tag)
                g_hier = geo_resolved.get("hierarchy")
                if g_hier and g_hier not in hier_kws:
                    hier_kws.insert(0, g_hier)
            else:
                # Specific location synthesis from sub_location / city / title if present
                specific_location = sub_location or city or None

            # Detect Screenshots (.png without camera EXIF, or EXIF UserComment/Software/filename 'Screenshot')
            software_str = (_first_non_empty(meta_dicts, ["EXIF:Software", "XMP:CreatorTool", "PNG:Software"]) or "").lower()
            user_comment_str = (caption or "").lower()
            stem_low = primary.stem.lower()
            is_screenshot = 0
            if (
                "screenshot" in user_comment_str
                or "screen shot" in user_comment_str
                or "screenshot" in stem_low
                or "screen shot" in stem_low
                or "screencapture" in software_str
                or (primary.suffix.lower() == ".png" and not camera_make and not camera_model and not lr_entry)
            ):
                is_screenshot = 1
                for sc_tag in ("Screenshot", "Screen Capture"):
                    if sc_tag not in flat_kws:
                        flat_kws.append(sc_tag)
                if "Technical|Screenshot" not in hier_kws:
                    hier_kws.append("Technical|Screenshot")

            # Star rating & color label from XMP/EXIF + .lrcat (take max rating)
            xmp_rating = _parse_int(_first_non_empty(meta_sidecar_first, ["XMP:Rating", "EXIF:Rating"])) or 0
            lr_rating = lr_entry.get("star_rating", 0) if lr_entry else 0
            star_rating = max(0, min(5, max(xmp_rating, lr_rating)))

            color_label = _first_non_empty(meta_sidecar_first, ["XMP:Label"]) or (lr_entry.get("color_label") if lr_entry else None)
            pick_flag = lr_entry.get("pick_flag", 0) if lr_entry else 0

            results.append({
                "file_path": str(primary.resolve()),
                "file_hash": compute_file_hash(primary),
                "sibling_path": str(sibling.resolve()) if sibling else None,
                "sidecar_paths": [str(s.resolve()) for s in sidecars],
                "exif_time": exif_time,
                "shoot_date": shoot_date,
                "camera_make": camera_make,
                "camera_model": camera_model,
                "camera_serial": camera_serial,
                "lens_model": lens_model,
                "focal_length": focal_length,
                "shutter_speed": shutter_speed,
                "aperture": aperture,
                "iso": iso,
                "gps_lat": gps_lat,
                "gps_lon": gps_lon,
                "gps_alt": gps_alt,
                "gps_ground_truth": gps_ground_truth,
                "is_screenshot": is_screenshot,
                "title": title,
                "caption": caption,
                "sub_location": sub_location,
                "city": city,
                "state_region": state_region,
                "country": country,
                "specific_location": specific_location,
                "star_rating": star_rating,
                "color_label": color_label,
                "pick_flag": pick_flag,
                "existing_keywords": flat_kws,
                "hierarchical_keywords": hier_kws,
                "lrcat_keywords": lrcat_kws,
                "lrprev_path": lr_entry.get("lrprev_path") if lr_entry else None,
                "lrprev_orientation": lr_entry.get("lrprev_orientation") if lr_entry else None,
            })
    finally:
        if own_et:
            try:
                et_helper.terminate()
            except Exception:
                pass

    return results


def link_keepers_across_catalogs(
    db_path: Path = DEFAULT_DB_PATH,
    phash_max_dist: int = 2
) -> Dict[str, int]:
    """
    Cross-Catalog Keepers Linker:
    1. Marks all records in the 'Keepers' catalog with in_keepers = 1.
    2. Finds any record in other catalogs (e.g. Aerial_RAW_Archive, Aerial_Working)
       sharing the same normalized filename stem OR perceptual hash (Hamming dist <= 2)
       as a Keepers image, and sets in_keepers = 1.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Ensure all rows explicitly in Keepers catalog have in_keepers = 1
    cursor.execute("""
        UPDATE photo_records
        SET in_keepers = 1
        WHERE LOWER(catalog_name) = 'keepers'
    """)

    keeper_rows = cursor.execute("""
        SELECT file_path, phash
        FROM photo_records
        WHERE LOWER(catalog_name) = 'keepers' OR in_keepers = 1
    """).fetchall()

    GENERIC_STEM_PREFIXES = {"img", "dsc", "dscf", "dji", "p", "sam", "scan", "photo", "pic", "raw", "c"}
    keeper_stems: Set[str] = set()
    keeper_hashes = []
    for r in keeper_rows:
        stem = Path(r["file_path"]).stem.lower()
        # Strip common derivative suffixes like _edit, -Edit, _master for stem matching (never strip pure camera numbers into generic prefixes)
        clean_stem = re.sub(r"[-_](edit|master|final|copy|v\d+)$", "", stem, flags=re.IGNORECASE)
        if stem and stem not in GENERIC_STEM_PREFIXES and len(stem) >= 4:
            keeper_stems.add(stem)
        if clean_stem and clean_stem not in GENERIC_STEM_PREFIXES and len(clean_stem) >= 4:
            keeper_stems.add(clean_stem)
        if r["phash"]:
            try:
                keeper_hashes.append(imagehash.hex_to_hash(r["phash"]))
            except Exception:
                pass

    if not keeper_stems and not keeper_hashes:
        conn.commit()
        conn.close()
        return {"keepers_count": 0, "linked_across_catalogs": 0}

    candidate_rows = cursor.execute("""
        SELECT file_path, phash, in_keepers
        FROM photo_records
        WHERE LOWER(catalog_name) != 'keepers'
    """).fetchall()

    linked_count = 0
    for r in candidate_rows:
        fp = r["file_path"]
        stem = Path(fp).stem.lower()
        clean_stem = re.sub(r"[-_](edit|master|final|copy|v\d+)$", "", stem, flags=re.IGNORECASE)

        matched = False
        if stem and stem not in GENERIC_STEM_PREFIXES and len(stem) >= 4 and stem in keeper_stems:
            matched = True
        elif clean_stem and clean_stem not in GENERIC_STEM_PREFIXES and len(clean_stem) >= 4 and clean_stem in keeper_stems:
            matched = True
        elif r["phash"] and keeper_hashes:
            try:
                cand_h = imagehash.hex_to_hash(r["phash"])
                for kh in keeper_hashes:
                    if (cand_h - kh) <= phash_max_dist:
                        matched = True
                        break
            except Exception:
                pass

        if matched:
            linked_count += 1
            if r["in_keepers"] != 1:
                cursor.execute(
                    "UPDATE photo_records SET in_keepers = 1, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
                    (fp,)
                )

    conn.commit()
    conn.close()
    return {
        "keepers_count": len(keeper_rows),
        "linked_across_catalogs": linked_count,
    }
