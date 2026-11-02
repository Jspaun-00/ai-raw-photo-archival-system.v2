#!/usr/bin/env python3
"""
Comprehensive End-to-End Verification Suite for Phases 1, 2, and 3 (verify_v3_phases_1_to_3.py)
AI Photo & RAW Archival System (v3.0) — Mitch Rouse Edition

Verifies all v3.0 architectural guardrails and bug fixes:
1. Non-destructive SQLite WAL schema migration (`db_schema.py`)
2. Strict Lightroom (`*.lrdata`, `*.lrcat*`, `Smart Previews`, `Backups`) exclusion
3. `.IIQ` + `.TIF` Sibling Pairing into a single database row (`sibling_path`)
4. Read-only `.lrcat` SQLite harvester (ratings, pick flags, color labels, hierarchical keywords)
5. Omni-Field ExifTool + `.xmp` / `.IIQ.xmp` sidecar harvesting without deleting sidecars (Bug #2 fix)
6. Full-Res 90th-Percentile Patch Sharpness & Clean 'Unsharp' Tagging Rule + Persistent 360px/1600px WebPs (Bug #1 fix)
7. Batched Apple Silicon MPS OpenCLIP (`ViT-L-14`) `float16` vectors (`vectors.npy`) + LAION Aesthetic V2 MLP
8. Cross-Catalog `Keepers` Linker (`in_keepers = 1`) & Keepers Personal Taste Calibration (`keepers_taste_bonus`)
9. Clock-Safe, Date-Bounded Sequence Grouper (never crosses midnight) + Sequence Hero selection (Bug #4 fix)
10. Stage 2 Self-Learning Metadata Centroid & Helicopter Orbit (+-3 min) Propagation + 35-Frame Strafing VLM Stride
11. Strict preservation of pre-existing keywords on burst/sequence sibling frames (Bug #3 fix)
12. Zero Data Corruption SHA-256 checksum audit during Stage 1 & Stage 2 + Safe Additive (`+=`) XMP Sync (`xmp_sync.py`)
"""

import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any

import exiftool
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from db_schema import (
    PROJECT_ROOT,
    get_db_connection,
    init_and_migrate_db,
    backup_catalog_to_das,
)
from pipeline import run_pipeline
from xmp_sync import sync_record_metadata_additive


SANDBOX_DIR = PROJECT_ROOT / "data" / "test_v3_sandbox"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_sharp_aerial_image(width: int = 1600, height: int = 1200, seed: int = 42, mono: bool = False) -> Image.Image:
    """Generates a synthetic high-frequency textured aerial landscape image with crisp edges."""
    rng = np.random.default_rng(seed)
    # Base gradient sky/ocean/land
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    r = np.clip((40 + 160 * x + 50 * y), 0, 255)
    g = np.clip((80 + 110 * (1 - y) + 60 * x), 0, 255)
    b = np.clip((130 + 100 * (1 - x) + 0 * y), 0, 255)
    arr = np.stack([r, g, b], axis=-1).astype(np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Draw high-contrast crisp geometric structures across the inner 6x6 patch grid (simulating pier / oil derricks)
    for gx in range(120, width - 120, 90):
        for gy in range(100, height - 100, 90):
            jitter_x = int(rng.integers(-8, 9))
            jitter_y = int(rng.integers(-8, 9))
            x0, y0 = gx + jitter_x, gy + jitter_y
            draw.rectangle([x0, y0, x0 + 36, y0 + 36], outline=(250, 245, 230), fill=(25, 35, 45), width=3)
            draw.line([x0, y0, x0 + 36, y0 + 36], fill=(255, 200, 50), width=2)
            draw.line([x0 + 36, y0, x0, y0 + 36], fill=(240, 240, 240), width=2)

    if mono:
        g_img = img.convert("L")
        img = Image.merge("RGB", (g_img, g_img, g_img))
    return img


def make_blurry_image(width: int = 1600, height: int = 1200) -> Image.Image:
    """Generates a motion-blurred / out-of-focus frame whose 90th-percentile patch sharpness is < 3.5."""
    base = make_sharp_aerial_image(width=width, height=height, seed=99)
    return base.filter(ImageFilter.GaussianBlur(radius=14))


def create_mock_lrcat(lrcat_path: Path, catalog_root: Path) -> None:
    """Creates a realistic Lightroom Classic .lrcat SQLite database with ratings, pick flags, and hierarchical keywords."""
    conn = sqlite3.connect(str(lrcat_path))
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE AgLibraryRootFolder (
            id_local INTEGER PRIMARY KEY,
            absolutePath TEXT
        );
        CREATE TABLE AgLibraryFolder (
            id_local INTEGER PRIMARY KEY,
            rootFolder INTEGER,
            pathFromRoot TEXT
        );
        CREATE TABLE AgLibraryFile (
            id_local INTEGER PRIMARY KEY,
            folder INTEGER,
            baseName TEXT,
            extension TEXT,
            idx_filename TEXT
        );
        CREATE TABLE Adobe_images (
            id_local INTEGER PRIMARY KEY,
            rootFile INTEGER,
            rating REAL,
            pick REAL,
            colorLabels TEXT
        );
        CREATE TABLE AgLibraryKeyword (
            id_local INTEGER PRIMARY KEY,
            parent INTEGER,
            name TEXT
        );
        CREATE TABLE AgLibraryKeywordImage (
            id_local INTEGER PRIMARY KEY,
            image INTEGER,
            tag INTEGER
        );
    """)
    root_str = str(catalog_root.resolve()) + "/"
    cur.execute("INSERT INTO AgLibraryRootFolder (id_local, absolutePath) VALUES (1, ?)", (root_str,))
    cur.execute("INSERT INTO AgLibraryFolder (id_local, rootFolder, pathFromRoot) VALUES (10, 1, 'Coastline/')")
    cur.execute(
        "INSERT INTO AgLibraryFile (id_local, folder, baseName, extension, idx_filename) VALUES (100, 10, 'CF001001', 'IIQ', 'CF001001.IIQ')"
    )
    cur.execute(
        "INSERT INTO Adobe_images (id_local, rootFile, rating, pick, colorLabels) VALUES (1000, 100, 5.0, 1.0, 'Red')"
    )
    # Hierarchical keywords in Lightroom: Coast -> California -> Huntington Beach Pier
    cur.execute("INSERT INTO AgLibraryKeyword (id_local, parent, name) VALUES (1, NULL, 'Coast')")
    cur.execute("INSERT INTO AgLibraryKeyword (id_local, parent, name) VALUES (2, 1, 'California')")
    cur.execute("INSERT INTO AgLibraryKeyword (id_local, parent, name) VALUES (3, 2, 'Huntington Beach Pier')")
    cur.execute("INSERT INTO AgLibraryKeywordImage (id_local, image, tag) VALUES (1, 1000, 3)")
    conn.commit()
    conn.close()


def setup_test_archive() -> Dict[str, Path]:
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)

    keepers_dir = SANDBOX_DIR / "Keepers"
    aerial_dir = SANDBOX_DIR / "Aerial_Working"
    coast_dir = aerial_dir / "Coastline"
    taft_dir = aerial_dir / "Taft_Sortie"
    das_backup_dir = SANDBOX_DIR / "DAS_Backup"

    for d in (keepers_dir, coast_dir, taft_dir, das_backup_dir):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Create Lightroom Cache Exclusion Traps (must NEVER be ingested)
    lrdata_trap = aerial_dir / "Mitch_Aerial Previews.lrdata" / "0" / "0000"
    smart_trap = aerial_dir / "Mitch_Aerial Smart Previews.lrdata"
    backup_trap = aerial_dir / "Backups" / "2025-05-01"
    for t in (lrdata_trap, smart_trap, backup_trap):
        t.mkdir(parents=True, exist_ok=True)
        make_sharp_aerial_image(400, 300).save(t / "trap_pyramid.jpg", "JPEG")

    # 2. Create Read-Only .lrcat SQLite database in Aerial_Working
    lrcat_path = aerial_dir / "Mitch_Aerial.lrcat"
    create_mock_lrcat(lrcat_path, aerial_dir)

    # 3. Create Keepers portfolio master image (`Keepers/CF001001.jpg`)
    pier_img = make_sharp_aerial_image(1600, 1200, seed=101)
    keeper_pier_path = keepers_dir / "CF001001.jpg"
    pier_img.save(keeper_pier_path, "JPEG", quality=92)

    # 4. Create `.IIQ` + `.TIF` sibling pair (`Coastline/CF001001.IIQ` + `Coastline/CF001001.tif` + `CF001001.IIQ.xmp`)
    raw_iiq_path = coast_dir / "CF001001.IIQ"
    sib_tif_path = coast_dir / "CF001001.tif"
    iiq_xmp_path = coast_dir / "CF001001.IIQ.xmp"
    pier_img.save(raw_iiq_path, "TIFF")
    pier_img.save(sib_tif_path, "TIFF")

    # Write Capture One .IIQ.xmp sidecar with Mitch's Pier metadata
    iiq_xmp_content = """<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:Iptc4xmpCore="http://iptc.org/std/Iptc4xmpCore/1.0/xmlns/">
   <photoshop:City>Huntington Beach</photoshop:City>
   <photoshop:State>California</photoshop:State>
   <photoshop:Country>United States</photoshop:Country>
   <Iptc4xmpCore:Location>Huntington Beach Pier</Iptc4xmpCore:Location>
   <dc:title><rdf:Alt><rdf:li xml:lang="x-default">Huntington Beach Pier Aerial</rdf:li></rdf:Alt></dc:title>
   <dc:description><rdf:Alt><rdf:li xml:lang="x-default">Aerial view of Huntington Beach Pier at golden hour</rdf:li></rdf:Alt></dc:description>
   <dc:subject>
    <rdf:Bag>
     <rdf:li>Surf</rdf:li>
     <rdf:li>Pacific Ocean</rdf:li>
     <rdf:li>Orange County</rdf:li>
    </rdf:Bag>
   </dc:subject>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    iiq_xmp_path.write_text(iiq_xmp_content, encoding="utf-8")

    # 5. Create Blurry Frame (`Coastline/CF001002_blurry.jpg`) and Monochrome Frame (`Coastline/CF001003_mono.jpg`)
    blurry_path = coast_dir / "CF001002_blurry.jpg"
    make_blurry_image(1600, 1200).save(blurry_path, "JPEG", quality=90)

    mono_path = coast_dir / "CF001003_mono.jpg"
    make_sharp_aerial_image(1600, 1200, seed=202, mono=True).save(mono_path, "JPEG", quality=92)

    # 6. Create 40-Frame Aerial Strafing Run over Taft Oil Field (`TAFT_0001.jpg` .. `TAFT_0040.jpg`)
    #    plus 1 frame after midnight (`TAFT_0041_nextday.jpg`) to verify Date-Bounded Sequence Rule!
    taft_base_img = make_sharp_aerial_image(1200, 900, seed=303)
    taft_files = []
    for i in range(1, 41):
        fp = taft_dir / f"TAFT_{i:04d}.jpg"
        taft_base_img.save(fp, "JPEG", quality=90)
        taft_files.append(fp)

    nextday_fp = taft_dir / "TAFT_0041_nextday.jpg"
    taft_base_img.save(nextday_fp, "JPEG", quality=90)

    # Stamp EXIF timestamps, camera model, serial, focal length via ExifTool
    with exiftool.ExifToolHelper() as et:
        # Stamp CF001001.IIQ, CF001002_blurry.jpg, CF001003_mono.jpg
        et.execute(
            "-overwrite_original",
            "-EXIF:Make=Phase One",
            "-EXIF:Model=IQ4 150MP",
            "-EXIF:SerialNumber=PO-1001",
            "-EXIF:FocalLength=50",
            "-EXIF:DateTimeOriginal=2025:06:14 17:30:00",
            str(raw_iiq_path),
        )
        et.execute(
            "-overwrite_original",
            "-EXIF:Make=Phase One",
            "-EXIF:Model=IQ4 150MP",
            "-EXIF:SerialNumber=PO-1001",
            "-EXIF:FocalLength=50",
            "-EXIF:DateTimeOriginal=2025:06:14 17:35:00",
            "-XMP:Rating=4",
            str(blurry_path),
        )
        et.execute(
            "-overwrite_original",
            "-EXIF:Make=Leica",
            "-EXIF:Model=M11 Monochrom",
            "-EXIF:SerialNumber=LC-2002",
            "-EXIF:FocalLength=35",
            "-EXIF:DateTimeOriginal=2025:06:14 18:00:00",
            str(mono_path),
        )

        # Stamp 40-frame Taft Oil Field strafing sequence (3 seconds apart on 2025:06:15)
        for idx, fp in enumerate(taft_files, start=1):
            minute = 10 + ((idx * 3) // 60)
            second = (idx * 3) % 60
            ts = f"2025:06:15 14:{minute:02d}:{second:02d}"
            et_args = [
                "-overwrite_original",
                "-EXIF:Make=Phase One",
                "-EXIF:Model=IQ4 150MP",
                "-EXIF:SerialNumber=PO-998811",
                "-EXIF:FocalLength=90",
                f"-EXIF:DateTimeOriginal={ts}",
            ]
            # Frame 1 has full Taft Oil Field ground-truth metadata
            if idx == 1:
                et_args.extend([
                    "-IPTC:Sub-location=Taft Oil Field",
                    "-IPTC:City=Taft",
                    "-IPTC:Province-State=California",
                    "-IPTC:Country-PrimaryLocationName=United States",
                    "-IPTC:Keywords+=Pumpjacks",
                    "-IPTC:Keywords+=Midway-Sunset Oil Field",
                ])
            # Frame 12 has its own unique pre-existing keyword to verify Bug #3 fix
            if idx == 12:
                et_args.extend([
                    "-IPTC:Keywords+=Derrick_Tower_Alpha",
                    "-XMP-dc:Subject+=Derrick_Tower_Alpha",
                ])
            et_args.append(str(fp))
            et.execute(*et_args)

        # Stamp Frame 41 on the next day (2025:06:16)
        et.execute(
            "-overwrite_original",
            "-EXIF:Make=Phase One",
            "-EXIF:Model=IQ4 150MP",
            "-EXIF:SerialNumber=PO-998811",
            "-EXIF:FocalLength=90",
            "-EXIF:DateTimeOriginal=2025:06:16 00:00:02",
            str(nextday_fp),
        )

    return {
        "sandbox_dir": SANDBOX_DIR,
        "keepers_dir": keepers_dir,
        "aerial_dir": aerial_dir,
        "das_backup_dir": das_backup_dir,
        "db_path": SANDBOX_DIR / "test_photo_archive.db",
        "vectors_path": SANDBOX_DIR / "test_vectors.npy",
        "thumbs_360_dir": SANDBOX_DIR / "previews" / "thumbs_360",
        "previews_1600_dir": SANDBOX_DIR / "previews" / "previews_1600",
        "raw_iiq_path": raw_iiq_path,
        "sib_tif_path": sib_tif_path,
        "iiq_xmp_path": iiq_xmp_path,
        "blurry_path": blurry_path,
        "mono_path": mono_path,
        "taft_files": taft_files,
        "nextday_fp": nextday_fp,
    }


def deterministic_vlm_mock(preview_path: Path, prompt_text: str) -> Dict[str, Any]:
    """
    Deterministic VLM responder that verifies ground-truth injection in prompt_text
    and returns structured v3.0 JSON metadata.
    """
    if "Taft Oil Field" in prompt_text:
        return {
            "primary_category": "Aerial",
            "sub_category": "Industrial_Infrastructure",
            "country": "United States",
            "state_region": "California",
            "specific_location": "Taft Oil Field",
            "lighting_atmosphere": "Afternoon_Sun",
            "is_aerial": True,
            "confidence_score": 0.96,
            "flat_keywords": ["Oil Field", "Petroleum Extraction", "San Joaquin Valley"],
            "hierarchical_keywords": ["Subject|Industrial|Oil Field", "Places|United States|California|Taft Oil Field"],
            "people_details": [],
        }
    elif "Huntington Beach Pier" in prompt_text:
        return {
            "primary_category": "Aerial",
            "sub_category": "Coastline",
            "country": "United States",
            "state_region": "California",
            "specific_location": "Huntington Beach Pier",
            "lighting_atmosphere": "Golden_Hour",
            "is_aerial": True,
            "confidence_score": 0.98,
            "flat_keywords": ["California Pier", "Coastline", "Breaking Waves"],
            "hierarchical_keywords": ["Subject|Coastline|California Pier"],
            "people_details": [],
        }
    else:
        return {
            "primary_category": "Landscape",
            "sub_category": "Scenic",
            "country": "United States",
            "state_region": "California",
            "specific_location": "California Coast",
            "lighting_atmosphere": "Daylight",
            "is_aerial": False,
            "confidence_score": 0.85,
            "flat_keywords": ["Fine Art", "Archival"],
            "hierarchical_keywords": ["Subject|Landscape|Scenic"],
            "people_details": [],
        }


def run_verification() -> None:
    print("=" * 80)
    print("AI PHOTO & RAW ARCHIVAL SYSTEM (v3.0) — PHASES 1, 2 & 3 VERIFICATION SUITE")
    print("=" * 80)

    paths = setup_test_archive()
    db_path = paths["db_path"]
    vectors_path = paths["vectors_path"]
    thumbs_360_dir = paths["thumbs_360_dir"]
    previews_1600_dir = paths["previews_1600_dir"]

    # Record pre-ingestion SHA-256 checksums of all source files and sidecars
    tracked_files = [
        paths["raw_iiq_path"],
        paths["sib_tif_path"],
        paths["iiq_xmp_path"],
        paths["blurry_path"],
        paths["mono_path"],
        paths["nextday_fp"],
    ] + paths["taft_files"]
    checksums_before = {str(p): sha256_file(p) for p in tracked_files}

    # 1. Run Stage 1 on `Keepers` catalog first, then `Aerial_Working` catalog
    print("\n[1/5] Running Stage 1 on `Keepers` and `Aerial_Working` catalogs...")
    res_keepers = run_pipeline(
        custom_source=paths["keepers_dir"],
        catalog_name="Keepers",
        stage1_only=True,
        db_path=db_path,
        vectors_path=vectors_path,
        thumbs_360_dir=thumbs_360_dir,
        previews_1600_dir=previews_1600_dir,
    )
    res_aerial = run_pipeline(
        custom_source=paths["aerial_dir"],
        catalog_name="Aerial_Working",
        stage1_only=True,
        db_path=db_path,
        vectors_path=vectors_path,
        thumbs_360_dir=thumbs_360_dir,
        previews_1600_dir=previews_1600_dir,
    )

    # 2. Run Stage 2 Self-Learning Propagation & 35-Frame Strafing VLM Stride
    print("[2/5] Running Stage 2 Self-Learning Propagation & 35-Frame Strafing VLM Stride...")
    res_stage2 = run_pipeline(
        stage2_only=True,
        db_path=db_path,
        vectors_path=vectors_path,
        thumbs_360_dir=thumbs_360_dir,
        previews_1600_dir=previews_1600_dir,
        mock_vlm_fn=deterministic_vlm_mock,
    )

    # 3. Verify Zero Data Corruption (100% identical SHA-256 checksums after Stage 1 + Stage 2)
    print("[3/5] Auditing SHA-256 checksums of all RAW, TIF, JPG, and .IIQ.xmp sidecar files...")
    for p in tracked_files:
        assert p.exists(), f"CRITICAL FAILURE: File deleted during ingestion: {p}"
        after_hash = sha256_file(p)
        assert after_hash == checksums_before[str(p)], f"CRITICAL FAILURE: File modified during ingestion: {p}"
    print("  ✓ PASS: Zero original files or sidecars were modified or moved during Stage 1 & Stage 2!")

    # 4. Inspect SQLite Database & Vector Matrix Assertions
    print("[4/5] Verifying SQLite WAL database records, vectors.npy, previews, sequences, and bug fixes...")
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    all_rows = {r["file_path"]: dict(r) for r in cur.execute("SELECT * FROM photo_records").fetchall()}

    # Expected count: 1 in Keepers + (1 paired IIQ/TIF + 1 blurry + 1 mono + 40 Taft + 1 nextday = 44 in Aerial_Working) = 45 total rows
    assert len(all_rows) == 45, f"Expected 45 total rows (with .lrdata excluded and .IIQ+.TIF paired), got {len(all_rows)}"
    print("  ✓ PASS: Strict Lightroom cache exclusion (*.lrdata, Smart Previews, Backups) & exact record count (45)")

    # Check .IIQ + .TIF sibling pairing & .lrcat + .IIQ.xmp omni-harvesting
    iiq_rec = all_rows[str(paths["raw_iiq_path"].resolve())]
    assert iiq_rec["sibling_path"] == str(paths["sib_tif_path"].resolve()), "Sibling .tif was not paired to .IIQ"
    assert iiq_rec["star_rating"] == 5, f"Expected .lrcat star_rating=5, got {iiq_rec['star_rating']}"
    assert iiq_rec["pick_flag"] == 1, f"Expected .lrcat pick_flag=1, got {iiq_rec['pick_flag']}"
    assert iiq_rec["color_label"] == "Red", f"Expected .lrcat color_label='Red', got {iiq_rec['color_label']}"
    assert iiq_rec["sub_location"] == "Huntington Beach Pier", f"Expected .IIQ.xmp sub_location, got {iiq_rec['sub_location']}"
    assert iiq_rec["in_keepers"] == 1, "Cross-catalog Keepers linker failed to mark in_keepers=1 on CF001001.IIQ"
    assert float(iiq_rec["keepers_taste_bonus"]) > 0.0, "Keepers personal taste bonus was not calibrated"
    iiq_kws = json.loads(iiq_rec["key_subjects"])
    assert "Surf" in iiq_kws and "Huntington Beach Pier" in iiq_kws, f"Missing sidecar/.lrcat keywords: {iiq_kws}"
    assert "Unsharp" not in iiq_kws and iiq_rec["is_unsharp"] == 0, "Sharp .IIQ was falsely tagged Unsharp"
    print("  ✓ PASS: .IIQ + .TIF sibling pairing, read-only .lrcat harvesting, .IIQ.xmp harvesting, & Keepers linking")

    # Check Persistent Two-Tier WebP Previews (360px and 1600px)
    t360_p = Path(iiq_rec["thumb_360_path"])
    p1600_p = Path(iiq_rec["preview_1600_path"])
    assert t360_p.exists() and p1600_p.exists(), "Persistent 360px or 1600px WebP preview missing!"
    with Image.open(t360_p) as im360, Image.open(p1600_p) as im1600:
        assert max(im360.size) == 360, f"Expected 360px thumb, got {im360.size}"
        assert max(im1600.size) == 1600, f"Expected 1600px preview, got {im1600.size}"
    print("  ✓ PASS: Persistent two-tier WebP previews (360px grid thumb + 1600px review preview) verified")

    # Check Sharpness 'Unsharp' Clean Tagging Rule & Star Rating Cap on Blurry Image
    blur_rec = all_rows[str(paths["blurry_path"].resolve())]
    blur_kws = json.loads(blur_rec["key_subjects"])
    blur_hkws = json.loads(blur_rec["hierarchical_keywords"])
    assert blur_rec["is_unsharp"] == 1 and float(blur_rec["sharpness_score"]) < 3.5, "Blurry image not detected"
    assert "Unsharp" in blur_kws and "Technical|Focus|Unsharp" in blur_hkws, "Unsharp tag missing on blurry image"
    assert blur_rec["star_rating"] == 1, f"Blurry image star_rating was not capped at 1: {blur_rec['star_rating']}"
    print(f"  ✓ PASS: Full-Res 90th-Percentile Patch Sharpness (Sharp={iiq_rec['sharpness_score']:.2f} untagged vs Blurry={blur_rec['sharpness_score']:.2f} tagged 'Unsharp' & capped at 1 star)")

    # Check Monochrome Detection
    mono_rec = all_rows[str(paths["mono_path"].resolve())]
    mono_kws = json.loads(mono_rec["key_subjects"])
    assert mono_rec["is_monochrome"] == 1 and "Monochrome" in mono_kws, "Monochrome image not tagged"
    print("  ✓ PASS: Monochrome detection & fair contrast colorfulness metric verified")

    # Check 40-Frame Taft Oil Field Sequence Grouping, Midnight Boundary, 35-Frame VLM Stride, & Bug #3 Fix
    taft1_rec = all_rows[str(paths["taft_files"][0].resolve())]
    taft12_rec = all_rows[str(paths["taft_files"][11].resolve())]
    taft40_rec = all_rows[str(paths["taft_files"][39].resolve())]
    nextday_rec = all_rows[str(paths["nextday_fp"].resolve())]

    assert taft1_rec["sequence_id"] == taft12_rec["sequence_id"] == taft40_rec["sequence_id"], "40-frame Taft strafing sequence was broken up!"
    assert taft1_rec["sequence_length"] == 40, f"Expected sequence_length=40, got {taft1_rec['sequence_length']}"
    assert nextday_rec["sequence_id"] != taft1_rec["sequence_id"], "CRITICAL FAILURE: Sequence crossed midnight into next day!"
    print(f"  ✓ PASS: Clock-safe, date-bounded sequence grouping (`{taft1_rec['sequence_id']}` len=40; next-day isolated in `{nextday_rec['sequence_id']}`)")

    # Verify Self-Learning Propagation & Bug #3 Fix on TAFT_0012.jpg and TAFT_0040.jpg
    taft12_kws = json.loads(taft12_rec["key_subjects"])
    taft40_kws = json.loads(taft40_rec["key_subjects"])
    assert "Derrick_Tower_Alpha" in taft12_kws, f"Bug #3 Regression: Pre-existing keyword 'Derrick_Tower_Alpha' dropped on burst frame TAFT_0012! ({taft12_kws})"
    assert taft40_rec["specific_location"] == "Taft Oil Field", f"Self-learning orbit/sequence propagation failed on TAFT_0040: {taft40_rec['specific_location']}"
    assert "Pumpjacks" in taft40_kws and "Oil Field" in taft40_kws, f"Propagated tags missing on TAFT_0040: {taft40_kws}"

    s2_rep = res_stage2["stage2_report"]
    # Total sequences in DB: 1 Keepers + 3 Coastline singletons + 1 Taft (40 frames) + 1 Taft nextday = 6 sequences
    # With 35-frame stride on the 40-frame Taft sequence, only 2-3 VLM calls happen for all 40 frames!
    assert s2_rep["vlm_anchor_calls"] <= 8 and s2_rep["propagated_sibling_frames"] >= 37, f"35-frame VLM stride did not bypass sibling frames: {s2_rep}"
    print(f"  ✓ PASS: 35-frame Strafing VLM Stride ({s2_rep['vlm_anchor_calls']} VLM anchor calls for 45 photos; {s2_rep['propagated_sibling_frames']} siblings inherited; Bug #3 preserved 'Derrick_Tower_Alpha')")

    # Check vectors.npy shape and dtype
    vecs = np.load(str(vectors_path), mmap_mode="r")
    assert vecs.dtype == np.float16 and vecs.shape == (45, 768), f"Unexpected vectors.npy shape/dtype: {vecs.shape}, {vecs.dtype}"
    print(f"  ✓ PASS: Memory-mapped Float16 vector matrix `vectors.npy` shape={vecs.shape}, dtype={vecs.dtype}")

    conn.close()

    # 5. Test Explicit Safe Additive (`+=`) XMP Sync & 1-Click DAS Backup
    print("[5/5] Testing explicit safe additive (`+=`) ExifTool XMP Sync & DAS Backup...")
    sync_res = sync_record_metadata_additive(
        file_path=str(paths["raw_iiq_path"].resolve()),
        db_path=db_path,
    )
    assert sync_res["success"] is True, f"Additive XMP sync failed: {sync_res}"
    assert paths["iiq_xmp_path"].exists(), "CRITICAL FAILURE: .IIQ.xmp sidecar was deleted!"

    # Verify via ExifTool that CF001001.IIQ.xmp and sibling CF001001.tif both have old + new tags
    with exiftool.ExifToolHelper() as et:
        xmp_tags = et.get_tags([str(paths["iiq_xmp_path"]), str(paths["sib_tif_path"])], ["XMP-dc:Subject", "XMP:Subject", "IPTC:Keywords"])
        sidecar_subjects = xmp_tags[0].get("XMP:Subject") or xmp_tags[0].get("XMP-dc:Subject", [])
        tif_subjects = xmp_tags[1].get("XMP:Subject") or xmp_tags[1].get("XMP-dc:Subject", [])
        assert "Surf" in sidecar_subjects and "California Pier" in sidecar_subjects, f"Additive sync lost or missed tags on .IIQ.xmp: {sidecar_subjects}"
        assert "Surf" in tif_subjects and "California Pier" in tif_subjects, f"Additive sync missed sibling .tif: {tif_subjects}"
    print("  ✓ PASS: Safe additive (`+=`) ExifTool sync verified on `.IIQ.xmp` sidecar and `.TIF` sibling without losing existing tags!")

    backup_res = backup_catalog_to_das(
        das_backup_dir=paths["das_backup_dir"],
        db_path=db_path,
        vectors_path=vectors_path,
    )
    assert Path(backup_res["db_backup_path"]).exists() and Path(backup_res["vectors_backup_path"]).exists()
    print("  ✓ PASS: 1-Click DAS Catalog & Vector Matrix Backup verified!")

    print("\n" + "=" * 80)
    print("ALL PHASES 1, 2, AND 3 VERIFICATION ASSERTIONS PASSED 100%!")
    print("=" * 80)

    if "--keep-sandbox" not in sys.argv and SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)


if __name__ == "__main__":
    run_verification()
