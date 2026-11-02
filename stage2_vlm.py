#!/usr/bin/env python3
"""
Phase 3 Engine: Stage 2 Self-Learning Metadata Propagation & Smart VLM Enrichment (stage2_vlm.py)
AI Photo & RAW Archival System (v3.0) — Mitch Rouse Aerial & Landscape Archive

Executes:
1. Self-Learning Metadata Centroid & Helicopter Orbit Time-Window Index:
   - Indexes curated photos in photo_archive.db (Pier names, Taft oil fields, LA freeways,
     Canyonlands, Palouse, Venice, etc.) by (shoot_timestamp_window, clip_vector_centroid,
     curated_location_and_keywords) into `metadata_centroids`.
   - Matches untagged photos via:
     (a) +-3 minute (180s) same-camera, same-day helicopter orbit window, OR
     (b) CLIP cosine similarity >= 0.84 to a learned location/project centroid.
   - Injects verified ground-truth location/project tags into the Qwen2.5-VL prompt
     and preserves them on the record.
2. Strafing Run VLM Stride (35-Frame Anchor Stride + CLIP Drift Trigger):
   - Inside sequences (>10 frames), runs Qwen2.5-VL (`qwen2.5vl:7b`) ONLY on the
     Sequence Hero (`is_sequence_hero == 1`) + 1 anchor frame every 35 frames
     (or whenever CLIP cosine similarity drops below 0.85).
   - Propagates semantic VLM tags across sibling frames in the same-day sequence while
     strictly preserving each file's own `existing_keywords`, `lrcat_keywords`,
     `sharpness_score`, `is_unsharp` ('Unsharp'), and `is_monochrome` tags (Bug #3 fix).
3. Background Pause/Resume & Per-Catalog Targeting.
"""

import json
import logging
import re
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
from PIL import Image

try:
    import ollama
except ImportError:
    ollama = None

try:
    import cv2
    import insightface
    BIOMETRICS_AVAILABLE = True
except ImportError:
    BIOMETRICS_AVAILABLE = False

from db_schema import (
    DEFAULT_DB_PATH,
    DEFAULT_PREVIEWS_1600_DIR,
    DEFAULT_VECTORS_PATH,
    PROJECT_ROOT,
    get_db_connection,
    log_ingestion_error,
)
from stage1_engine import (
    _parse_exif_dt,
    load_or_init_vectors_matrix,
)

DIRECTIVE_PATH = PROJECT_ROOT / "config" / "directive.txt"
REF_FACES_DIR = PROJECT_ROOT / "reference_faces"

# Global pause flag for background execution control from FastAPI UI or CLI
STAGE2_PAUSE_EVENT = threading.Event()


def _safe_json_list(val: Any) -> List[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            return [x.strip() for x in val.split(",") if x.strip()]
    return []


def resolve_ollama_model(preferred_model: str = "qwen2.5vl:7b") -> str:
    """Dynamically resolves model name matching Ollama local catalog."""
    if ollama is None:
        return preferred_model
    try:
        models_resp = ollama.list()
        models = (
            models_resp.get("models", [])
            if isinstance(models_resp, dict)
            else getattr(models_resp, "models", [])
        )
        avail = []
        for m in models:
            name = (
                m.get("model", "") or m.get("name", "")
                if isinstance(m, dict)
                else getattr(m, "model", "")
            )
            if name:
                avail.append(name)
        if preferred_model in avail:
            return preferred_model
        pref_norm = preferred_model.replace("-", "").replace("_", "").lower()
        for m in avail:
            if m.replace("-", "").replace("_", "").lower() == pref_norm or "qwen2.5" in m.lower():
                return m
    except Exception:
        pass
    return preferred_model


# ==============================================================================
# 1. OPTIONAL BIOMETRICS (INSIGHTFACE)
# ==============================================================================
class BiometricMatcher:
    def __init__(self, ref_dir: Path = REF_FACES_DIR):
        self.ref_dir = ref_dir
        self.face_app = None
        self.reference_embeddings: Dict[str, np.ndarray] = {}
        self._initialized = False

    def ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        if not BIOMETRICS_AVAILABLE or not self.ref_dir.exists():
            return
        ref_images = list(self.ref_dir.glob("*.jpg")) + list(self.ref_dir.glob("*.png"))
        if not ref_images:
            return
        try:
            self.face_app = insightface.app.FaceAnalysis(name="buffalo_l")
            self.face_app.prepare(ctx_id=0, det_size=(640, 640))
            for ref_img in ref_images:
                img = cv2.imread(str(ref_img))
                if img is not None:
                    faces = self.face_app.get(img)
                    if faces:
                        person_name = ref_img.stem.replace("_", " ").title()
                        self.reference_embeddings[person_name] = faces[0].embedding
        except Exception as exc:
            logging.warning(f"Biometric initialization skipped: {exc}")

    def detect_faces(self, preview_path: Optional[Path]) -> List[str]:
        if preview_path is None or not preview_path.exists():
            return []
        self.ensure_initialized()
        if not self.reference_embeddings or self.face_app is None:
            return []
        try:
            img = cv2.imread(str(preview_path))
            if img is None:
                return []
            faces = self.face_app.get(img)
            matches = []
            for face in faces:
                for name, emb in self.reference_embeddings.items():
                    sim = float(
                        np.dot(face.embedding, emb)
                        / (np.linalg.norm(face.embedding) * np.linalg.norm(emb) + 1e-8)
                    )
                    if sim > 0.50:
                        matches.append(f"Person: {name}")
            return matches
        except Exception:
            return []


# ==============================================================================
# 2. SELF-LEARNING METADATA CENTROID & HELICOPTER ORBIT TIME-WINDOW INDEX
# ==============================================================================
from domain_gazetteer import (
    GENERIC_NOISE_TAGS,
    AERIAL_ONLY_LANDMARKS,
    _ANIMAL_ONTOLOGY,
    _PEOPLE_ONTOLOGY,
    _FLORA_ONTOLOGY,
    _STRUCTURE_ONTOLOGY,
    CONCEPT_PROBE_PROMPTS,
    GLOBAL_LANDMARK_GAZETTEER,
    FILLER_NOISE_WORDS,
    JARGON_FACET_TAGS_LOWER,
    HALLUCINATED_SPEC_LOCATIONS_LOWER,
    _UNDERSCORE_SUBJECT_MAP,
    PORTFOLIO_CATEGORIES_CONFIG,
    _TEACH_GEO_GAZETTEER,
    _TEACH_SUBJECT_CONCEPTS,
    _GENERIC_VISUAL_NOUNS_KEEP,
    SINGULAR_PLURAL_PAIRS,
    COUNTABLE_DISCRETE_SUBJECT_TAGS_LOWER,
    COUNTABLE_SEARCH_CONCEPTS,
    deduplicate_singular_plural_tags,
)


def _is_curated_record(row: Dict[str, Any]) -> Tuple[bool, str, List[str], List[str]]:
    """
    Determines whether a photo record carries genuine HUMAN-VERIFIED ground-truth
    location or subject metadata suitable for self-learning propagation.
    Quarantines unverified AI guesses so visual reference centroids and orbit anchors
    are built strictly from human-verified sources (.lrcat keywords, existing EXIF/XMP
    keywords, user-taught tags/notes, or deterministic filename shorthand stems).
    Returns (is_curated, cluster_label, curated_flat_kws, curated_hier_kws).
    """
    sub_loc = str(row.get("sub_location") or "").strip()
    spec_loc = str(row.get("specific_location") or "").strip()
    city = str(row.get("city") or "").strip()
    state = str(row.get("state_region") or "").strip()
    country = str(row.get("country") or "").strip()
    title = str(row.get("title") or "").strip()
    caption = str(row.get("caption") or "").strip()

    negated_low = {k.lower().strip() for k in _safe_json_list(row.get("negated_tags")) if k.strip()}
    user_taught = [
        k for k in _safe_json_list(row.get("user_taught_tags"))
        if k.lower().strip() not in GENERIC_NOISE_TAGS and k.lower().strip() not in negated_low
    ]
    user_note = str(row.get("user_context_notes") or "").strip()

    existing_kws = [
        k for k in _safe_json_list(row.get("existing_keywords"))
        if k.lower().strip() not in GENERIC_NOISE_TAGS and k.lower().strip() not in negated_low
    ]
    lrcat_kws = [
        k for k in _safe_json_list(row.get("lrcat_keywords"))
        if k.lower().strip() not in GENERIC_NOISE_TAGS and k.lower().strip() not in negated_low
    ]
    # Filter accidental 'england' import tag left checked on Sept/Oct 2009 US shoots (Tetons / Denver trip 07)
    sdate_str = str(row.get("shoot_date") or "")
    fp_stem_low = Path(str(row.get("file_path") or "")).stem.lower()
    if sdate_str in ("2009-09-28", "2009-10-01") or "teton" in fp_stem_low or any("denver" in k.lower() for k in lrcat_kws):
        lrcat_kws = [k for k in lrcat_kws if k.lower().strip() != "england"]
        existing_kws = [k for k in existing_kws if k.lower().strip() != "england"]
        if country.lower() == "united kingdom":
            country = "United States"
        if state.lower() == "england":
            state = ""

    # Clear any location field that has been explicitly negated by the user
    if spec_loc.lower() in negated_low or spec_loc.lower() in HALLUCINATED_SPEC_LOCATIONS_LOWER:
        spec_loc = ""
    if sub_loc.lower() in negated_low:
        sub_loc = ""
    if city.lower() in negated_low:
        city = ""
    if state.lower() in negated_low:
        state = ""
    if country.lower() in negated_low:
        country = ""

    has_gps_ground_truth = bool(
        int(row.get("gps_ground_truth") or 0) == 1
        or (row.get("gps_lat") is not None and row.get("gps_lon") is not None)
    )
    gps_loc_tags = [t for t in (spec_loc, city, state, country) if t and t.lower() not in ("unknown", "none", "general") and t.lower() not in negated_low]
    curated_flat = list(dict.fromkeys(user_taught + lrcat_kws + existing_kws + (gps_loc_tags if has_gps_ground_truth else [])))
    has_human_verified_source = bool(user_taught or user_note or lrcat_kws or existing_kws or has_gps_ground_truth)
    if not has_human_verified_source or not curated_flat:
        return False, "", [], []

    hier_kws = [
        k for k in _safe_json_list(row.get("hierarchical_keywords"))
        if (k.startswith("Places|") or k.startswith("Coast|") or k.startswith("Location|"))
        and not any(neg in k.lower() for neg in negated_low)
        and not (
            (sdate_str in ("2009-09-28", "2009-10-01") or "teton" in fp_stem_low)
            and ("united kingdom" in k.lower() or "england" in k.lower())
        )
    ]

    # Only trust spec_loc/sub_loc/city as the cluster label if confirmed by human-verified tags/notes/lrcat/title/GPS
    human_blob_low = " ".join(curated_flat + [title, caption, user_note, fp_stem_low]).lower()
    verified_loc_candidates = []
    for v in (sub_loc, spec_loc, title, city):
        if not v or v.lower() in ("unknown", "none", "general") or v.lower() in HALLUCINATED_SPEC_LOCATIONS_LOWER:
            continue
        if has_gps_ground_truth or any(tok in human_blob_low for tok in v.lower().split() if len(tok) >= 3):
            verified_loc_candidates.append(v)

    if verified_loc_candidates:
        cluster_label = verified_loc_candidates[0]
    elif curated_flat:
        cluster_label = curated_flat[0]
    elif caption and len(caption) <= 64:
        cluster_label = caption
    else:
        return False, "", [], []

    # Build hierarchical place tag if known and verified
    if country and country.lower() != "unknown":
        reg = state or "General"
        loc = verified_loc_candidates[0] if verified_loc_candidates else ""
        if loc and loc.lower() != "unknown":
            place_tag = f"Places|{country}|{reg}|{loc}"
        else:
            place_tag = f"Places|{country}|{reg}"
        if place_tag not in hier_kws:
            hier_kws.append(place_tag)

    return True, cluster_label, curated_flat, hier_kws


def build_self_learning_index(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
) -> Dict[str, Any]:
    """
    Scans photo_archive.db for records with HUMAN-VERIFIED ground-truth metadata
    (.lrcat keywords, existing EXIF/XMP keywords, GPS ground truth, or user-taught tags/notes),
    builds normalized CLIP vector centroids and time windows in `metadata_centroids`,
    and returns an in-memory index for fast Stage 2 lookup. Unverified AI guesses are
    strictly excluded so they can never self-corrupt future ingest or propagation runs.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    vectors = load_or_init_vectors_matrix(vectors_path)

    rows = cursor.execute("""
        SELECT file_path, catalog_name, camera_model, camera_serial, shoot_date, exif_time,
               gps_lat, gps_lon, gps_ground_truth, is_screenshot,
               sub_location, specific_location, city, state_region, country, title, caption,
               existing_keywords, lrcat_keywords, hierarchical_keywords,
               user_taught_tags, user_context_notes, negated_tags, vector_index
        FROM photo_records
        WHERE status != 'failed'
    """).fetchall()

    clusters: Dict[str, Dict[str, Any]] = {}
    orbit_anchors: List[Dict[str, Any]] = []

    for r in rows:
        row_dict = dict(r)
        is_curated, label, flat_kws, hier_kws = _is_curated_record(row_dict)
        if not is_curated:
            continue

        v_idx = row_dict.get("vector_index")
        has_vec = (
            v_idx is not None
            and 0 <= int(v_idx) < vectors.shape[0]
            and np.linalg.norm(vectors[int(v_idx)]) > 0.1
        )
        dt = _parse_exif_dt(row_dict.get("exif_time"))

        anchor_entry = {
            "file_path": row_dict["file_path"],
            "camera_model": str(row_dict.get("camera_model") or "Unknown"),
            "camera_serial": str(row_dict.get("camera_serial") or "0"),
            "shoot_date": str(row_dict.get("shoot_date") or "Undated"),
            "dt": dt,
            "exif_time": row_dict.get("exif_time"),
            "cluster_label": label,
            "sub_location": row_dict.get("sub_location"),
            "specific_location": row_dict.get("specific_location") or row_dict.get("sub_location"),
            "city": row_dict.get("city"),
            "state_region": row_dict.get("state_region"),
            "country": row_dict.get("country"),
            "title": row_dict.get("title"),
            "caption": row_dict.get("caption"),
            "curated_keywords": flat_kws,
            "hierarchical_keywords": hier_kws,
            "vector_index": int(v_idx) if has_vec else None,
        }
        orbit_anchors.append(anchor_entry)

        norm_key = label.strip().lower()
        if norm_key not in clusters:
            clusters[norm_key] = {
                "cluster_name": label,
                "country": row_dict.get("country"),
                "state_region": row_dict.get("state_region"),
                "city": row_dict.get("city"),
                "sub_location": row_dict.get("sub_location"),
                "specific_location": row_dict.get("specific_location") or row_dict.get("sub_location"),
                "curated_keywords": list(flat_kws),
                "hierarchical_keywords": list(hier_kws),
                "vector_indices": [],
                "timestamps": [],
                "sample_count": 0,
            }
        c = clusters[norm_key]
        c["sample_count"] += 1
        for kw in flat_kws:
            if kw not in c["curated_keywords"]:
                c["curated_keywords"].append(kw)
        for hkw in hier_kws:
            if hkw not in c["hierarchical_keywords"]:
                c["hierarchical_keywords"].append(hkw)
        if not c["country"] and row_dict.get("country"):
            c["country"] = row_dict.get("country")
        if not c["state_region"] and row_dict.get("state_region"):
            c["state_region"] = row_dict.get("state_region")
        if not c["city"] and row_dict.get("city"):
            c["city"] = row_dict.get("city")
        if not c["sub_location"] and row_dict.get("sub_location"):
            c["sub_location"] = row_dict.get("sub_location")
        if not c["specific_location"] and row_dict.get("specific_location"):
            c["specific_location"] = row_dict.get("specific_location")
        if has_vec:
            c["vector_indices"].append(int(v_idx))
        if row_dict.get("exif_time"):
            c["timestamps"].append(str(row_dict["exif_time"]))

    # Persist centroids into SQLite `metadata_centroids` table
    cursor.execute("DELETE FROM metadata_centroids;")
    centroid_records: List[Dict[str, Any]] = []
    centroid_matrix_list: List[np.ndarray] = []

    for norm_key, c in clusters.items():
        v_indices = c["vector_indices"]
        centroid_bytes: Optional[bytes] = None
        centroid_vec: Optional[np.ndarray] = None

        if v_indices:
            vecs = vectors[v_indices].astype(np.float32)
            mean_v = np.mean(vecs, axis=0)
            norm = float(np.linalg.norm(mean_v))
            if norm > 1e-8:
                centroid_vec = (mean_v / norm).astype(np.float32)
                centroid_bytes = centroid_vec.astype(np.float16).tobytes()

        ts_sorted = sorted(c["timestamps"])
        t_start = ts_sorted[0] if ts_sorted else None
        t_end = ts_sorted[-1] if ts_sorted else None

        cursor.execute("""
            INSERT OR REPLACE INTO metadata_centroids (
                cluster_id, label, country, state_region, city, specific_location, sub_location,
                keywords_json, hierarchical_json, centroid_vector, sample_count,
                time_windows_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            norm_key,
            c["cluster_name"],
            c["country"],
            c["state_region"],
            c["city"],
            c["specific_location"],
            c["sub_location"],
            json.dumps(c["curated_keywords"]),
            json.dumps(c["hierarchical_keywords"]),
            centroid_bytes,
            c["sample_count"],
            json.dumps({"start": t_start, "end": t_end}),
        ))

        if centroid_vec is not None:
            centroid_records.append(c)
            centroid_matrix_list.append(centroid_vec.reshape(1, 768))

    conn.commit()
    conn.close()

    centroid_matrix = (
        np.vstack(centroid_matrix_list)
        if centroid_matrix_list
        else np.zeros((0, 768), dtype=np.float32)
    )

    return {
        "centroids_count": len(clusters),
        "vector_centroids_count": len(centroid_records),
        "orbit_anchors_count": len(orbit_anchors),
        "centroid_records": centroid_records,
        "centroid_matrix": centroid_matrix,
        "orbit_anchors": orbit_anchors,
    }


def lookup_ground_truth_context(
    record: Dict[str, Any],
    learned_index: Dict[str, Any],
    vectors: np.ndarray,
    orbit_window_seconds: float = 180.0,
    centroid_similarity_threshold: float = 0.84,
) -> Optional[Dict[str, Any]]:
    """
    Checks if a photo matches existing ground-truth metadata via:
    1. Helicopter Orbit Time-Window Propagation (+-180s on same camera & same shoot_date), OR
    2. Self-Learning CLIP Centroid Cosine Similarity (>= 0.84).
    Returns matched ground-truth metadata dict if found, else None.
    """
    cam_model = str(record.get("camera_model") or "Unknown")
    cam_serial = str(record.get("camera_serial") or "0")
    sdate = str(record.get("shoot_date") or "Undated")
    dt_curr = _parse_exif_dt(record.get("exif_time"))

    # 1. Check +-3 minute (180s) same-camera, same-date helicopter orbit window
    if dt_curr and sdate != "Undated":
        matching_orbits: List[Tuple[float, Dict[str, Any]]] = []
        for anchor in learned_index.get("orbit_anchors", []):
            if anchor["file_path"] == record.get("file_path"):
                continue
            if anchor["shoot_date"] != sdate:
                continue
            if anchor["camera_model"] != cam_model or anchor["camera_serial"] != cam_serial:
                continue
            if anchor["dt"] is None:
                continue
            delta = abs((dt_curr - anchor["dt"]).total_seconds())
            if delta <= orbit_window_seconds:
                # Prioritize anchors that have explicit location fields, then by smallest time delta
                has_loc_priority = 0 if (anchor.get("sub_location") or anchor.get("specific_location") or anchor.get("city")) else 1
                matching_orbits.append((delta, has_loc_priority, anchor))

        if matching_orbits:
            matching_orbits.sort(key=lambda x: (x[1], x[0]))
            best_delta, _, primary_orbit = matching_orbits[0]

            merged_kws: List[str] = []
            merged_hkws: List[str] = []
            for _, _, orb in matching_orbits:
                for kw in orb.get("curated_keywords", []):
                    if kw not in merged_kws:
                        merged_kws.append(kw)
                for hkw in orb.get("hierarchical_keywords", []):
                    if hkw not in merged_hkws:
                        merged_hkws.append(hkw)

            def _first_orb_field(f_name: str) -> Optional[str]:
                for _, _, orb in matching_orbits:
                    val = orb.get(f_name)
                    if val and str(val).strip().lower() not in ("", "unknown", "none"):
                        return str(val).strip()
                return None

            return {
                "match_type": "helicopter_orbit_window",
                "match_score": round(1.0 - (best_delta / max(orbit_window_seconds, 1.0)) * 0.1, 3),
                "delta_seconds": round(best_delta, 1),
                "cluster_name": _first_orb_field("sub_location") or _first_orb_field("specific_location") or primary_orbit["cluster_label"],
                "country": _first_orb_field("country"),
                "state_region": _first_orb_field("state_region"),
                "city": _first_orb_field("city"),
                "sub_location": _first_orb_field("sub_location"),
                "specific_location": _first_orb_field("specific_location") or _first_orb_field("sub_location"),
                "curated_keywords": merged_kws,
                "hierarchical_keywords": merged_hkws,
            }

    # 2. Check CLIP Cosine Similarity >= 0.84 against learned metadata centroids
    v_idx = record.get("vector_index")
    c_mat = learned_index.get("centroid_matrix")
    c_recs = learned_index.get("centroid_records", [])
    if (
        v_idx is not None
        and c_mat is not None
        and c_mat.shape[0] > 0
        and 0 <= int(v_idx) < vectors.shape[0]
    ):
        vec = vectors[int(v_idx)].astype(np.float32)
        if np.linalg.norm(vec) > 0.1:
            sims = np.dot(c_mat, vec)
            best_i = int(np.argmax(sims))
            best_sim = float(sims[best_i])
            if best_sim >= centroid_similarity_threshold:
                matched_c = c_recs[best_i]
                return {
                    "match_type": "clip_centroid_similarity",
                    "match_score": round(best_sim, 4),
                    "cluster_name": matched_c["cluster_name"],
                    "country": matched_c.get("country"),
                    "state_region": matched_c.get("state_region"),
                    "city": matched_c.get("city"),
                    "sub_location": matched_c.get("sub_location"),
                    "specific_location": matched_c.get("specific_location"),
                    "curated_keywords": list(matched_c.get("curated_keywords", [])),
                    "hierarchical_keywords": list(matched_c.get("hierarchical_keywords", [])),
                }

    return None


# ==============================================================================
# 2B. PERSPECTIVE CLASSIFICATION, CONDITIONAL GUIDE DOCS & ONTOLOGY EXPANDER
# ==============================================================================
AERIAL_ONLY_LANDMARKS = {
    "taft oil field": ("Taft Oil Field", "California"),
    "taft oil fields": ("Taft Oil Field", "California"),
    "taft_oil_field": ("Taft Oil Field", "California"),
    "taft_oil_fields": ("Taft Oil Field", "California"),
    "palouse": ("Palouse", "Washington"),
    "palouse_hills": ("Palouse", "Washington"),
    "palouse rolling hills": ("Palouse", "Washington"),
    "palouse_rolling_loess_hills": ("Palouse", "Washington"),
    "carrizo plain": ("Carrizo Plain", "California"),
    "carrizo_plain": ("Carrizo Plain", "California"),
    "owens lake": ("Owens Lake", "California"),
    "owens_lake": ("Owens Lake", "California"),
    "brighton west pier": ("Brighton West Pier", "United Kingdom"),
    "huntington beach pier": ("Huntington Beach Pier", "California"),
    "manhattan beach pier": ("Manhattan Beach Pier", "California"),
}

AERIAL_GUIDE_DIRECTIVE = """You are an elite, forensic-grade visual archivist and metadata specialist for Mitch Rouse's professional fine-art, commercial, and aerial photography archive.
Analyze the provided image AND any pre-existing file metadata/context provided in the prompt, then output a single, strictly valid JSON object.

### PERSPECTIVE CONTEXT: AERIAL PHOTOGRAPHY
This photograph was captured from an aircraft / helicopter or high oblique vantage point.

### RULES & CRITICAL DIRECTIVES:
1. PRESERVE PRE-EXISTING METADATA:
   If the user prompt includes pre-existing keywords, locations, titles, captions, or learned ground-truth context from the archive, treat those as verified ground truth and incorporate them into your JSON output.
2. SPECIFIC GEOGRAPHICAL & AERIAL VISUAL ANCHORS:
   Only apply a named location below when visually matches AND does not conflict with verified file keywords:
   - Taft Oil Field (San Joaquin Valley, CA): Dense industrial grid of pumpjacks, steam pipes, circular tanks, and dirt service roads on arid earth. -> Country: "United States", State: "California", Specific Location: "Taft Oil Field"
   - Palouse Rolling Loess Hills (Eastern WA): Smooth, undulating wave-like hills of green/gold wheat and fallow earth. -> Country: "United States", State: "Washington", Specific Location: "Palouse"
   - Braided Glacial Rivers & Silt Deltas: Intricate dendritic channels and sandbars. -> Sub-Category: "Braided_River_Delta"
   - Piers & Coastal Infrastructure: Distinguish intact vs skeletal ruins when supported by metadata.
   - If you are not at least 85% certain of a specific named landmark, set "specific_location": "Unknown".
3. SINGLE-VALUE CATEGORY FIELDS & 8-12 FACETED VISUAL KEYWORDS:
   "primary_category", "sub_category", and "lighting_atmosphere" MUST be a single string value using underscores for spaces.
   Provide 8 to 12 concrete, observable keywords in "flat_keywords" covering all 5 visual facets:
   (1) Primary Subject(s) (2-3 tags: main structures, landforms, industrial or coastal elements),
   (2) Secondary Elements & Sub-Details (2-3 tags: roads, channels, piers, boats, bridges, cliffs, trees),
   (3) Materials, Surface Texture & Color Character (2 tags: stone, sand, water, metal, earth + color palette),
   (4) Framing & Composition Geometry (1-2 tags: overhead geometric pattern, wide panoramic vista, leading lines, aerial perspective),
   (5) Lighting & Atmosphere (1-2 tags: golden hour light, crisp midday sun, soft overcast, atmospheric mist).
   NEVER output generic filler words ("beautiful", "scenic", "artistic", "stunning").
4. RETURN ONLY VALID JSON matching this schema:
{
  "primary_category": "Aerial",
  "sub_category": "One specific sub-type (e.g., Oil_Field, Coastline, Braided_River_Delta, Freeway_Interchange, Mountain_Range, Agricultural_Grid)",
  "country": "Country name or Unknown",
  "state_region": "State/Province or null",
  "city": "City/Town or null",
  "specific_location": "Exact landmark or Unknown",
  "is_aerial": true,
  "lighting_atmosphere": "Single phrase (e.g., Golden_Hour, Harsh_Midday, Overcast_Diffused, Twilight, Fog_Mist)",
  "confidence_score": 0.92,
  "key_subjects": ["specific_subject_1", "specific_subject_2", "secondary_detail_1"],
  "flat_keywords": ["primary_1", "primary_2", "secondary_detail_1", "secondary_detail_2", "material_texture", "color_character", "composition_framing", "lighting_condition"],
  "hierarchical_keywords": ["Category|Subcategory|Subject", "Places|Country|State|Location"],
  "people_details": []
}"""

TERRESTRIAL_GUIDE_DIRECTIVE = """You are an elite, forensic-grade visual archivist and metadata specialist for Mitch Rouse's professional fine-art, terrestrial landscape, ranch, wildlife, and portrait archive.
Analyze the provided image AND any pre-existing file metadata/context provided in the prompt, then output a single, strictly valid JSON object.

### PERSPECTIVE CONTEXT: TERRESTRIAL / GROUND-LEVEL PHOTOGRAPHY
This photograph was captured at ground level (eye-level landscape, ranch, architectural structure, wildlife, botanical study, or human portrait).

### CRITICAL ANTI-HALLUCINATION RULES FOR TERRESTRIAL PHOTOS:
1. NEVER GUESS AERIAL OILFIELDS OR UNCONFIRMED LANDMARKS:
   - STRICTLY FORBIDDEN: Do NOT output "Taft Oil Field", "Taft Oil Fields", "Palouse", "Carrizo Plain", or "Owens Lake" unless those exact words appear in the Verified File Keywords in the prompt!
   - Do NOT guess a specific US State or named National Park unless it is explicitly stated in the Verified File Keywords/Location in the prompt or unmistakable (like Monument Valley mittens or Half Dome). When unconfirmed, set "specific_location": "Unknown" and "state_region": null.
2. TERRESTRIAL LANDSCAPE, RANCH, STRUCTURE, WILDLIFE & PEOPLE TAXONOMY:
   Identify all visible foreground and midground subjects with high precision:
   - Rural & Ranch Structures: Barn, Old_Barn, Farmhouse, Homestead, Cabin, Corral, Wooden_Fence, Windmill, Silo, Ranch, Pasture, Dirt_Road, Highway, Colonial_Doors, Wooden_Door, Window_Shutters, Stucco_Facade, Archway.
   - Wildlife & Animals: Bison, Buffalo, Horse, Quarter_Horses, Cattle, Cow, Elk, Deer, Pelican, Eagle, Hawk, Heron, Crane, Waterfowl, Bird, Dog, Wildlife, Animal.
   - People & Portraits: Person, People, Man, Woman, Boy, Girl, Photographer, Cowboy, Rancher, Rider, Family, Portrait (include demographic/role in "people_details" and "key_subjects").
   - Flora & Trees: Wildflowers, Lupine, Poppies, Yucca, Joshua_Tree, Saguaro, Cactus, Oak_Tree, Aspen, Cypress, Pine, Forest, Kelp, Autumn_Foliage.
   - Natural Landforms: Canyon, Desert_Mesa, Butte, Sand_Dunes, Mountain_Peak, Rock_Formation, Waterfall, Creek, River, Lake, Coastline, Sea_Stacks, Marsh, Bayou.
3. SINGLE-VALUE CATEGORY FIELDS & 8-12 FACETED VISUAL KEYWORDS:
   "primary_category" (e.g., "Landscape", "Wildlife", "Architecture", "People", "Botanical"), "sub_category", and "lighting_atmosphere" MUST be single strings.
   Provide 8 to 12 concrete, observable keywords in "flat_keywords" covering all 5 visual facets:
   (1) Primary Subject(s) (2-3 tags: main structures, landforms, wildlife, or people),
   (2) Secondary Elements & Sub-Details (2-3 tags: doors, windows, archways, fences, bridges, piers, boats, foreground flora, rock spires),
   (3) Materials, Surface Texture & Color Character (2 tags: weathered wood, stucco, sandstone, metal, ice, sand + vibrant saturated color, warm golden palette, muted earth tones, or monochrome),
   (4) Framing & Composition Geometry (1-2 tags: centered symmetrical framing, tight architectural detail, wide panoramic vista, leading lines, eye-level terrestrial),
   (5) Lighting & Atmosphere (1-2 tags: golden hour light, dramatic storm light, soft overcast, dawn mist, midday sun).
   NEVER output generic filler words ("beautiful", "scenic", "artistic", "stunning").
4. RETURN ONLY VALID JSON matching this schema:
{
  "primary_category": "Landscape | Wildlife | Architecture | People | Botanical",
  "sub_category": "Specific sub-type (e.g., Ranch_Barn, Bison_Herd, Desert_Canyon, Coastal_Rocks, Wildflower_Meadow, Photographer_Portrait, Cypress_Bayou)",
  "country": "United States or Unknown",
  "state_region": "Confirmed State or null",
  "city": "Confirmed City or null",
  "specific_location": "Confirmed landmark from prompt or Unknown",
  "is_aerial": false,
  "lighting_atmosphere": "Single phrase (e.g., Golden_Hour, Dramatic_Storm_Light, Soft_Overcast, Dawn_Mist, Midday_Sun)",
  "confidence_score": 0.90,
  "key_subjects": ["specific_subject_1", "specific_subject_2", "parent_category"],
  "flat_keywords": ["primary_1", "primary_2", "secondary_detail_1", "secondary_detail_2", "material_texture", "color_character", "composition_framing", "lighting_condition"],
  "hierarchical_keywords": ["Subjects|Category|Specific", "Landscape|Terrain|Feature"],
  "people_details": [{"demographic": "Man | Woman | Boy | Girl", "role": "Photographer | Rancher | Subject"}]
}"""


def has_human_landmark_confirmation(record: Dict[str, Any], landmark_key: str) -> bool:
    """
    Returns True ONLY if the photo's original human metadata (.lrcat_keywords, existing_keywords,
    title, caption, or filename stem) explicitly mentions the landmark_key.
    """
    lk = landmark_key.lower().replace("_", " ").strip()
    tokens_to_check = [lk]
    if "taft" in lk:
        tokens_to_check.append("taft")
    if "palouse" in lk:
        tokens_to_check.append("palouse")
        tokens_to_check.append("steptoe")

    human_sources: List[str] = []
    for col in ("lrcat_keywords", "existing_keywords"):
        human_sources.extend(_safe_json_list(record.get(col)))
    for col in ("title", "caption", "sub_location"):
        val = str(record.get(col) or "").strip()
        if val:
            human_sources.append(val)
    fp = str(record.get("file_path") or "")
    if fp:
        human_sources.append(Path(fp).stem)

    blob = " ".join(human_sources).lower().replace("_", " ").replace("-", " ")
    return any(tok in blob for tok in tokens_to_check)


def select_guide_directive(
    record: Dict[str, Any],
    ground_truth: Optional[Dict[str, Any]] = None,
    clip_probes: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """
    Selects AERIAL_GUIDE_DIRECTIVE vs TERRESTRIAL_GUIDE_DIRECTIVE based on:
    - OpenCLIP zero-shot perspective score (if available in clip_probes)
    - Non-boilerplate Human .lrcat / existing keywords (ignoring 'Mitch Rouse Aerials' / 'aerials' preset)
    - Catalog context ('4_Landscape_Keepers' / 'Keepers' defaults to Terrestrial unless visually/keyword confirmed Aerial)
    Returns (directive_text, is_confirmed_aerial).
    """
    human_kws = [
        k.lower().strip()
        for k in (_safe_json_list(record.get("lrcat_keywords")) + _safe_json_list(record.get("existing_keywords")))
        if k.lower().strip() not in GENERIC_NOISE_TAGS
    ]
    human_blob = " ".join(human_kws)

    explicit_aerial_kw = any(
        w in human_blob
        for w in ("helicopter", "taft", "palouse", "air to air", "overflight")
    )
    explicit_terrestrial_kw = any(
        w in human_blob
        for w in ("barn", "bison", "buffalo", "ranch", "portrait", "mitch shooting", "alice", "family", "trail", "canyon", "trees", "yosemite", "grand canyon", "monument valley", "395", "tucson", "denver", "carolinas", "everglades", "lousiana", "louisiana", "houma")
    )

    if clip_probes and "is_aerial" in clip_probes:
        is_aerial = bool(clip_probes["is_aerial"])
    elif explicit_aerial_kw and not explicit_terrestrial_kw:
        is_aerial = True
    elif explicit_terrestrial_kw:
        is_aerial = False
    else:
        cat_name = str(record.get("catalog_name") or "").lower()
        # Keepers catalog is Terestrial -2.lrcat unless visually confirmed aerial
        is_aerial = "aerial" in cat_name and "keepers" not in cat_name

    if is_aerial:
        return AERIAL_GUIDE_DIRECTIVE, True
    return TERRESTRIAL_GUIDE_DIRECTIVE, False


# (_ANIMAL_ONTOLOGY, _PEOPLE_ONTOLOGY, _FLORA_ONTOLOGY, _STRUCTURE_ONTOLOGY imported from domain_gazetteer.py)


def strip_hallucinated_landmarks(
    flat_kws: List[str],
    hier_kws: List[str],
    record: Dict[str, Any],
    specific_location: Optional[str],
    state_region: Optional[str],
    is_confirmed_aerial: bool,
    clip_probes: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[str], Optional[str], Optional[str]]:
    """
    Removes hallucinated aerial landmark tags (like Taft Oil Field or Palouse) and
    unconfirmed directive exemplar strings (like Canyonlands National Park, Venice Beach Breakwater,
    Steptoe Butte, Contour_Wheat_Farming) when:
    - The photo's original human .lrcat_keywords / existing_keywords / filename do NOT contain that landmark, AND
    - Either the photo is Terrestrial (not aerial) OR its visual similarity to that landmark is low.
    """
    forbidden_substrings: List[str] = []
    states_to_clear_if_unconfirmed: List[str] = []

    for lm_key, (canonical_lm, lm_state) in AERIAL_ONLY_LANDMARKS.items():
        has_human = has_human_landmark_confirmation(record, lm_key)
        if has_human:
            continue

        # Check if OpenCLIP visual probe strongly confirms this exact landmark on an aerial photo
        visually_confirmed = False
        if is_confirmed_aerial and clip_probes:
            if "taft" in lm_key and clip_probes.get("taft_sim", 0.0) >= 0.29:
                visually_confirmed = True
            elif "palouse" in lm_key and clip_probes.get("palouse_sim", 0.0) >= 0.29:
                visually_confirmed = True

        if not visually_confirmed:
            forbidden_substrings.append(lm_key)
            forbidden_substrings.append(canonical_lm.lower())
            if "taft" in lm_key:
                forbidden_substrings.extend(["taft oil", "taft_oil", "oil_field", "oil field", "pumpjack", "san joaquin"])
            if "palouse" in lm_key:
                forbidden_substrings.extend(["palouse", "loess", "steptoe butte", "steptoe_butte", "contour wheat farming", "contour_wheat_farming", "contour farming", "contour_farming"])
                if not has_human_landmark_confirmation(record, "washington"):
                    states_to_clear_if_unconfirmed.append("washington")

    # Also strip unconfirmed directive exemplar hallucinations copied by Qwen2.5-VL from config/directive.txt
    if not has_human_landmark_confirmation(record, "canyonlands") and not has_human_landmark_confirmation(record, "greenriver") and not has_human_landmark_confirmation(record, "moab"):
        forbidden_substrings.extend(["canyonlands national park", "canyonlands_national_park", "canyonlands", "braided_river_delta", "braided river delta", "silt_bars", "silt bars"])
        if not has_human_landmark_confirmation(record, "utah") and not has_human_landmark_confirmation(record, "vlygods") and not has_human_landmark_confirmation(record, "vly of gods") and not has_human_landmark_confirmation(record, "monument valley"):
            states_to_clear_if_unconfirmed.append("utah")

    if not has_human_landmark_confirmation(record, "venice"):
        forbidden_substrings.extend([
            "venice beach breakwater",
            "venice_beach_breakwater",
            "venice lagoon & canals",
            "venice_lagoon_canals",
            "venice lagoon",
            "venice_lagoon",
            "venice canals",
            "venice_canals",
            "venice_canal",
            "venetian_canals",
            "venetian canals",
            "venetian architecture",
            "venetian_architecture",
            "venice beach",
            "venice_beach",
            "rialto bridge",
            "rialto_bridge",
            "bridge of sighs",
            "bridge_of_sighs",
            "grand canal",
            "grand_canal",
            "venice",
            "veneto",
            "italy",
        ])
        states_to_clear_if_unconfirmed.extend(["veneto", "italy"])

    sdate_str = str(record.get("shoot_date") or "")
    if sdate_str != "2012-03-09" and not has_human_landmark_confirmation(record, "mexico"):
        forbidden_substrings.extend([
            "el triunfo",
            "el_triunfo",
            "abandoned_mission_san_juan_bautista",
            "abandoned mission san juan bautista",
            "jalisco_mexico",
            "jalisco",
            "riviera gas station",
            "riviera_gas_station",
            "san miguel de allende",
            "san_miguel_de_allende",
            "guanajuato",
            "oaxaca",
            "mexico",
            "latin america",
            "latin_america",
            "latin_american_colonial",
            "spanish_colonial_facade",
        ])
        states_to_clear_if_unconfirmed.extend(["guanajuato", "jalisco", "baja california sur", "mexico"])

    if not has_human_landmark_confirmation(record, "pregerson"):
        forbidden_substrings.extend(["judge harry pregerson interchange", "judge_harry_pregerson_interchange"])

    if not forbidden_substrings:
        return flat_kws, hier_kws, specific_location, state_region

    def _is_tainted(text: str) -> bool:
        tl = text.lower().replace("_", " ").strip()
        return any(fb in tl for fb in forbidden_substrings)

    cleaned_flat = [k for k in flat_kws if not _is_tainted(k)]
    cleaned_hier = [hk for hk in hier_kws if not _is_tainted(hk)]

    cleaned_spec = specific_location
    if cleaned_spec and _is_tainted(cleaned_spec):
        cleaned_spec = "Unknown"

    cleaned_state = state_region
    if cleaned_state and cleaned_state.lower().strip() in states_to_clear_if_unconfirmed:
        cleaned_state = None
        cleaned_hier = [
            hk for hk in cleaned_hier
            if not any(st in hk.lower() for st in states_to_clear_if_unconfirmed)
        ]
        cleaned_flat = [
            k for k in cleaned_flat
            if k.lower().strip() not in states_to_clear_if_unconfirmed
        ]

    return cleaned_flat, cleaned_hier, cleaned_spec, cleaned_state


def expand_hierarchical_ontology(
    flat_kws: List[str],
    hier_kws: List[str],
    record: Dict[str, Any],
    clip_probes: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], List[str]]:
    """
    Universal Multi-Tier Ontological Tag Expander (Parent -> Mid -> Specific) & Identity Indexer.
    Enforces High-Tension Contrastive Habitat/Artifact Gating & Taxonomic Abstention:
    - Countable discrete subjects (Animals, People, Boats, Vehicles) are ONLY expanded or kept
      when verified by Contrastive Foil Probes (`clip_probes`), explicit `user_taught_tags`,
      or genuine non-place/non-preset `.lrcat` subject tags.
    - Place names (`Hawkeye Ranch`, `Deer Creek`, `Bighorn Mountains`) and bulk presets
      (`Mitch shooting`, `Alice`) never trigger false animal or person tags.
    - Taxonomic Abstention: distant/ambiguous people abstain to `Person` rather than guessing `Man`/`Woman`.
    - Deduplicates singular/plural pairs using verified subject counts.
    """
    probes = clip_probes or {}
    user_taught_list = [str(t).strip() for t in _safe_json_list(record.get("user_taught_tags")) if str(t).strip()]
    user_taught_low = {t.lower() for t in user_taught_list}
    negated_low = {str(t).lower().strip() for t in _safe_json_list(record.get("negated_tags")) if str(t).strip()}

    # Identify genuine human subject keywords in .lrcat (excluding place names & bulk import presets)
    _PLACE_AND_PRESET_TOKENS = {
        "hawkeye", "hawkeye ranch", "deer creek", "deer_creek", "bighorn", "bighorn mountains",
        "mitch shooting", "mitch_shooting", "mitch rouse aerials", "aerials", "to print",
        "alice", "west coast imaging*  alice", "west coast imaging* alice", "elkhorn",
    }
    lrcat_subject_kws: List[str] = []
    for lk in _safe_json_list(record.get("lrcat_keywords")):
        lk_clean = str(lk or "").strip()
        lk_low = lk_clean.lower().replace("_", " ").strip()
        if not lk_low or lk_low in GENERIC_NOISE_TAGS or lk_low in _PLACE_AND_PRESET_TOKENS or lk_low in negated_low:
            continue
        if any(p_tok in lk_low for p_tok in ("hawkeye", "deer creek", "bighorn", "mitch shooting", "alice")):
            continue
        lrcat_subject_kws.append(lk_clean)

    verified_subj_labels_low = {
        str(vs.get("label") if isinstance(vs, dict) else vs).lower().strip()
        for vs in (probes.get("verified_subjects") or [])
        if vs
    }

    # Determine which countable subject families have positive verification
    has_verified_animal = bool(
        probes.get("has_bison")
        or probes.get("has_horse")
        or probes.get("has_cattle")
        or probes.get("has_bird")
        or probes.get("has_frog")
        or probes.get("has_dog")
        or probes.get("has_cat")
        or probes.get("has_deer")
        or probes.get("has_bear")
        or probes.get("has_wildlife")
        or bool(verified_subj_labels_low & {"bison", "buffalo", "horse", "horses", "cattle", "cow", "bird", "birds", "frog", "frogs", "dog", "dogs", "cat", "cats", "deer", "elk", "bear", "wildlife", "animal", "animals"})
        or any(
            w in " ".join(lrcat_subject_kws).lower().split()
            for w in ("bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "bird", "birds", "heron", "egret", "pelican", "eagle", "owl", "frog", "frogs", "dog", "dogs", "cat", "cats", "deer", "elk", "bear", "sheep")
        )
        or bool(user_taught_low & set(_ANIMAL_ONTOLOGY.keys()))
    )
    has_verified_person = bool(
        probes.get("has_person")
        or bool(verified_subj_labels_low & {"person", "people", "man", "woman", "photographer", "mitch rouse (subject)"})
        or any(
            w in " ".join(lrcat_subject_kws).lower().split()
            for w in ("person", "people", "portrait", "family", "man", "woman", "cowboy", "rancher")
        )
        or bool(user_taught_low & (set(_PEOPLE_ONTOLOGY.keys()) | {"mitch rouse (subject)", "mitch rouse"}))
    )
    has_verified_boat = bool(
        probes.get("has_boat")
        or bool(verified_subj_labels_low & {"boat", "boats", "fishing boat", "ship", "vessel", "canoe", "kayak", "sailboat"})
        or any(w in " ".join(lrcat_subject_kws).lower().split() for w in ("boat", "boats", "ship", "canoe", "kayak", "sailboat", "harbor", "marina"))
        or bool(user_taught_low & {"boat", "boats", "fishing boat", "ship", "vessel", "canoe", "kayak", "rowboat", "sailboat"})
    )
    has_verified_vehicle = bool(
        probes.get("has_car")
        or probes.get("has_train")
        or probes.get("has_airplane")
        or bool(verified_subj_labels_low & {"car", "cars", "vehicle", "truck", "train", "locomotive", "airplane", "aircraft", "helicopter"})
        or any(w in " ".join(lrcat_subject_kws).lower().split() for w in ("car", "cars", "truck", "train", "locomotive", "airplane", "helicopter"))
        or bool(user_taught_low & {"car", "cars", "vehicle", "truck", "automobile", "train", "trains", "locomotive", "airplane", "airplanes", "aircraft", "helicopter"})
    )

    # Filter incoming flat_kws & hier_kws to strip unverified countable discrete subjects (from old noisy runs or habitat guesses)
    _ANIMAL_ALL_TAGS_LOW = {
        "animal", "animals", "wildlife", "fauna", "bird", "birds", "waterfowl", "raptor", "avian",
        "heron", "great blue heron", "egret", "pelican", "hawk", "eagle", "bald eagle", "owl",
        "sandhill crane", "duck", "goose", "gull", "seagull", "seabird", "blackbird", "magpie", "crow",
        "bison", "american bison", "buffalo", "ungulates", "mammals",
        "horse", "horses", "equine", "cattle", "cow", "cows", "livestock", "angus", "elk", "deer", "mule deer",
        "antelope", "pronghorn", "sheep", "bighorn sheep", "dog", "dogs", "canine", "cat", "cats",
        "feline", "frog", "frogs", "toad", "amphibian", "bear", "grizzly bear", "black bear",
        "wildlife & animals", "horses & cattle",
    }
    _PERSON_ALL_TAGS_LOW = {
        "person", "people", "human", "man", "men", "male", "woman", "women", "female",
        "portrait", "portraits", "child", "children", "boy", "girl", "family", "photographer", "mitch rouse (subject)",
        "cowboy", "rancher", "farmer", "worker", "individual", "group",
    }
    _BOAT_ALL_TAGS_LOW = {
        "boat", "boats", "fishing boat", "ship", "ships", "vessel", "vessels", "watercraft", "maritime",
        "canoe", "kayak", "rowboat", "sailboat", "sailboats", "yacht", "yachts", "barge", "gondola",
    }
    _VEHICLE_ALL_TAGS_LOW = {
        "car", "cars", "vehicle", "vehicles", "automobile", "truck", "pickup truck",
        "train", "trains", "locomotive", "freight train", "airplane", "airplanes", "aircraft", "biplane",
    }
    _BIRD_WORD_TOKENS = {
        "bird", "birds", "avian", "waterfowl", "raptor", "heron", "egret", "pelican",
        "hawk", "eagle", "owl", "duck", "goose", "gull", "seagull", "seabird", "blackbird", "magpie", "crow",
    }

    lrcat_subj_words = set(re.findall(r"[a-z0-9]+", " ".join(lrcat_subject_kws).lower()))

    out_flat: List[str] = []
    for k in dict.fromkeys(flat_kws):
        k_low = str(k or "").strip().lower()
        if not k_low or k_low in negated_low:
            continue
        k_words = set(re.findall(r"[a-z0-9]+", k_low))
        if k_low not in user_taught_low:
            # Never strip protected compound place/architecture phrases like "Bosque del Apache National Wildlife Refuge" or "Boathouse"
            is_protected_place_or_struct = any(
                p in k_low for p in ("wildlife refuge", "boathouse", "hawkeye", "deer creek", "bighorn", "eagle mountain", "elkhorn", "pigeon point")
            )
            if not is_protected_place_or_struct:
                if (k_low in _ANIMAL_ALL_TAGS_LOW or bool(k_words & _ANIMAL_ALL_TAGS_LOW)) and not has_verified_animal:
                    continue
                if (k_low in _PERSON_ALL_TAGS_LOW or bool(k_words & _PERSON_ALL_TAGS_LOW)) and not has_verified_person:
                    continue
                if (k_low in _BOAT_ALL_TAGS_LOW or bool(k_words & _BOAT_ALL_TAGS_LOW)) and not has_verified_boat:
                    continue
                if (k_low in _VEHICLE_ALL_TAGS_LOW or bool(k_words & _VEHICLE_ALL_TAGS_LOW)) and not has_verified_vehicle:
                    continue
                # Enforce per-species verification when clip_probes is present:
                if clip_probes is not None:
                    if bool(k_words & _BIRD_WORD_TOKENS) and not (
                        probes.get("has_bird") or bool(lrcat_subj_words & _BIRD_WORD_TOKENS)
                    ):
                        continue
                    if bool(k_words & {"frog", "frogs", "toad", "amphibian"}) and not (
                        probes.get("has_frog") or bool(lrcat_subj_words & {"frog", "frogs", "toad"})
                    ):
                        continue
                    if bool(k_words & {"dog", "dogs", "canine"}) and not (
                        probes.get("has_dog") or bool(lrcat_subj_words & {"dog", "dogs"})
                    ):
                        continue
                    if bool(k_words & {"cat", "cats", "feline"}) and not (
                        probes.get("has_cat") or bool(lrcat_subj_words & {"cat", "cats"})
                    ):
                        continue
                    if bool(k_words & {"bison", "buffalo"}) and not (
                        probes.get("has_bison") or bool(lrcat_subj_words & {"bison", "buffalo"})
                    ):
                        continue
                    if bool(k_words & {"horse", "horses", "equine", "cattle", "cow", "cows", "livestock", "angus"}) and not (
                        probes.get("has_horse") or probes.get("has_cattle") or bool(lrcat_subj_words & {"horse", "horses", "cattle", "cow", "cows"})
                    ):
                        continue
        out_flat.append(k)

    out_hier: List[str] = []
    for hk in dict.fromkeys(hier_kws):
        hk_low = str(hk or "").strip().lower()
        if not hk_low:
            continue
        hk_words = set(re.findall(r"[a-z0-9]+", hk_low))
        if (hk_low.startswith("subjects|animals") or hk_low.startswith("subjects|wildlife") or hk_low == "portfolio|wildlife & animals" or bool(hk_words & _ANIMAL_ALL_TAGS_LOW)) and not has_verified_animal:
            continue
        if (hk_low.startswith("subjects|people") or hk_low.startswith("people|") or hk_low.startswith("identity|") or bool(hk_words & _PERSON_ALL_TAGS_LOW)) and not has_verified_person:
            continue
        if (hk_low.startswith("subjects|watercraft") or bool(hk_words & _BOAT_ALL_TAGS_LOW)) and not has_verified_boat:
            continue
        if clip_probes is not None and not (user_taught_low & _BIRD_WORD_TOKENS):
            if bool(hk_words & _BIRD_WORD_TOKENS) and not (
                probes.get("has_bird") or bool(lrcat_subj_words & _BIRD_WORD_TOKENS)
            ):
                continue
        out_hier.append(hk)

    def _add_flat(tag: str) -> None:
        if tag and tag.lower().strip() not in negated_low and tag not in out_flat:
            out_flat.append(tag)

    def _add_hier(htag: str) -> None:
        if htag and htag not in out_hier:
            out_hier.append(htag)

    # Build verified signals for Animal & People expansion (NEVER from place names or unverified VLM guesses)
    verified_animal_signals: List[str] = list(user_taught_list) + list(lrcat_subject_kws)
    verified_people_signals: List[str] = list(user_taught_list) + list(lrcat_subject_kws)
    if clip_probes:
        if probes.get("has_bison"):
            verified_animal_signals.append("bison")
        if probes.get("has_horse"):
            verified_animal_signals.append("horse")
        if probes.get("has_cattle"):
            verified_animal_signals.append("cattle")
        if probes.get("has_bird"):
            verified_animal_signals.append("bird")
        if probes.get("has_frog"):
            verified_animal_signals.append("frog")
        if probes.get("has_dog"):
            verified_animal_signals.append("dog")
        if probes.get("has_cat"):
            verified_animal_signals.append("cat")
        if probes.get("has_deer"):
            verified_animal_signals.append("deer")
        if probes.get("has_bear"):
            verified_animal_signals.append("bear")
        if probes.get("has_wildlife"):
            verified_animal_signals.append("wildlife")
        if probes.get("has_person"):
            verified_people_signals.append("person")
            if probes.get("is_male_person"):
                verified_people_signals.append("man")
            if probes.get("is_female_person"):
                verified_people_signals.append("woman")
            if probes.get("is_photographer"):
                verified_people_signals.append("photographer")
            if probes.get("has_mirror_selfie"):
                verified_people_signals.append("mirror selfie")
    else:
        # When clip_probes is None (e.g., unit test or direct call), allow explicit flat_kws that aren't place names
        verified_animal_signals.extend(out_flat)
        verified_people_signals.extend(out_flat)

    def _build_word_sets(sig_list: List[str]) -> Tuple[Set[str], Set[str]]:
        phrases = set()
        words = set()
        for sig in sig_list:
            s_clean = str(sig or "").lower().replace("_", " ").replace("-", " ").strip()
            if not s_clean or s_clean in _PLACE_AND_PRESET_TOKENS:
                continue
            phrases.add(s_clean)
            for w in re.split(r"[^a-z0-9]+", s_clean):
                if len(w) >= 2:
                    words.add(w)
        return phrases, words

    anim_phrases, anim_words = _build_word_sets(verified_animal_signals)
    peop_phrases, peop_words = _build_word_sets(verified_people_signals)

    # General signals for Flora & Structures (non-countable scene/architecture features)
    scene_signals: List[str] = list(lrcat_subject_kws) + list(out_flat)
    if clip_probes:
        if probes.get("has_cat_tree"):
            scene_signals.append("cat tree")
        if probes.get("has_living_room"):
            scene_signals.append("living room")
        if probes.get("has_fitting_room"):
            scene_signals.append("fitting room")
        if probes.get("has_sports_car"):
            scene_signals.extend(["sports car", "sedan", "car"])
        elif probes.get("has_car"):
            scene_signals.append("car")
        if probes.get("has_gas_station"):
            scene_signals.append("gas station")
    for hk in out_hier:
        scene_signals.extend(p.strip() for p in str(hk).split("|") if p.strip())
    scene_phrases, scene_words = _build_word_sets(scene_signals)

    def _matches_in(ont_key: str, phrases: Set[str], words: Set[str]) -> bool:
        if " " in ont_key:
            return ont_key in phrases or any(re.search(rf"\b{re.escape(ont_key)}\b", p) for p in phrases)
        return ont_key in words or ont_key in phrases

    # 1. Expand Verified Animals / Wildlife
    if has_verified_animal:
        for k, (spec, mids, parents, hpath) in _ANIMAL_ONTOLOGY.items():
            if _matches_in(k, anim_phrases, anim_words):
                _add_flat(spec)
                for m in mids:
                    _add_flat(m)
                for p in parents:
                    _add_flat(p)
                _add_hier(hpath)

    # 2. Expand Verified People / Human / Gender / Identity (with Taxonomic Abstention)
    has_any_person = False
    if has_verified_person:
        for k, (spec, mids, parents, hpath) in _PEOPLE_ONTOLOGY.items():
            if _matches_in(k, peop_phrases, peop_words):
                has_any_person = True
                _add_flat(spec)
                for m in mids:
                    _add_flat(m)
                for p in parents:
                    _add_flat(p)
                _add_hier(hpath)

        # Taxonomic Abstention: if person is present, but neither male nor female passed the high-confidence margin
        # (and user did not explicitly teach man/woman), abstain to Person/People/Human!
        user_taught_gender = bool(user_taught_low & {"man", "men", "male", "woman", "women", "female", "boy", "girl"})
        if clip_probes is not None and not user_taught_gender:
            if not probes.get("is_male_person"):
                out_flat = [t for t in out_flat if t.lower() not in ("man", "men", "male", "boy")]
                out_hier = [h for h in out_hier if not h.lower().endswith(("|man", "|male", "|boy"))]
            if not probes.get("is_female_person"):
                out_flat = [t for t in out_flat if t.lower() not in ("woman", "women", "female", "girl")]
                out_hier = [h for h in out_hier if not h.lower().endswith(("|woman", "|female", "|girl"))]

        # Mitch Rouse Identity Rule: ONLY when a verified person is actually in the frame (or explicitly taught by user)
        raw_lrcat_low = [k.lower() for k in _safe_json_list(record.get("lrcat_keywords")) + _safe_json_list(record.get("existing_keywords"))]
        is_mitch_subject = (
            "mitch rouse (subject)" in user_taught_low
            or "self portrait" in peop_phrases
            or (
                has_any_person
                and (
                    "mitch shooting" in raw_lrcat_low
                    or "mitch_shooting" in raw_lrcat_low
                    or (probes.get("is_photographer") and probes.get("is_male_person"))
                )
            )
        )
        if is_mitch_subject:
            for t in ("Mitch Rouse (Subject)", "Photographer", "Man", "Person"):
                _add_flat(t)
            _add_hier("Identity|Mitch Rouse")
            _add_hier("Subjects|People|Photographer")
            _add_hier("Subjects|People|Man")

    # 3. Expand Flora / Plants / Trees / Wildflowers (exclude "cat tree" from triggering botanical tree/plant tags)
    flora_phrases = [p for p in scene_phrases if "cat tree" not in p]
    flora_words = set(re.findall(r"[a-z0-9]+", " ".join(flora_phrases)))
    for k, (spec, mids, parents, hpath) in _FLORA_ONTOLOGY.items():
        if _matches_in(k, flora_phrases, flora_words):
            _add_flat(spec)
            for m in mids:
                _add_flat(m)
            for p in parents:
                _add_flat(p)
            _add_hier(hpath)

    # 4. Expand Structures / Architecture / Ranch / Infrastructure (gate Boats unless has_verified_boat, gate Vehicles unless has_verified_vehicle)
    for k, (spec, mids, parents, hpath) in _STRUCTURE_ONTOLOGY.items():
        if k in ("boat", "boats", "fishing boat", "ship", "canoe", "kayak", "sailboat") and not has_verified_boat:
            continue
        if k in ("car", "cars", "sports car", "sedan", "lexus") and not has_verified_vehicle:
            continue
        if _matches_in(k, scene_phrases, scene_words):
            _add_flat(spec)
            for m in mids:
                _add_flat(m)
            for p in parents:
                _add_flat(p)
            _add_hier(hpath)

    # 4B. Night & Artificial Lighting Verification
    if clip_probes and probes.get("is_night_artificial"):
        out_flat = [
            t for t in out_flat
            if t.lower().strip() not in ("midday sun", "daylight", "afternoon sun", "morning sun", "golden hour", "bright daylight")
        ]
        _add_flat("Night")
        _add_flat("Artificial Lighting")
        _add_hier("Lighting|Night")
        _add_hier("Lighting|Artificial_Lighting")

    # 5. Perspective Hierarchical Tag (never clutter flat keywords with internal 'Terrestrial' or 'Eye-level terrestrial')
    if clip_probes and "is_aerial" in clip_probes:
        is_aer = bool(clip_probes["is_aerial"])
    else:
        is_aer = "Aerial" in out_flat or bool(record.get("is_aerial"))
    if is_aer:
        _add_flat("Aerial")
        _add_hier("Perspective|Aerial")
    else:
        _add_hier("Perspective|Terrestrial")

    # 6. Deduplicate singular/plural pairs (never emit both Boat and Boats, Bird and Birds, Butte and Buttes, etc.)
    out_flat = deduplicate_singular_plural_tags(
        out_flat,
        subject_counts=probes.get("subject_counts"),
    )

    return out_flat, out_hier


# ==============================================================================
# 3. PROMPT BUILDER & VLM INFERENCE CALLER
# ==============================================================================
def build_vlm_prompt(
    record: Dict[str, Any],
    ground_truth: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Constructs the context-enriched prompt for Qwen2.5-VL, injecting both the file's
    own embedded metadata AND any verified self-learning ground-truth location/project tags.
    """
    hints: List[str] = []

    if record.get("camera_make") or record.get("camera_model"):
        hints.append(f"Camera: {record.get('camera_make') or ''} {record.get('camera_model') or ''}".strip())
    if record.get("lens_model"):
        hints.append(f"Lens: {record.get('lens_model')}")
    if record.get("focal_length"):
        hints.append(f"Focal Length: {record.get('focal_length')}mm")
    if record.get("shutter_speed"):
        hints.append(f"Shutter: {record.get('shutter_speed')}s")
    if record.get("aperture"):
        hints.append(f"Aperture: f/{record.get('aperture')}")
    if record.get("iso"):
        hints.append(f"ISO: {record.get('iso')}")
    if record.get("shoot_date") and record.get("shoot_date") != "Undated":
        hints.append(f"Shoot Date: {record.get('shoot_date')}")

    # Own embedded metadata
    own_kws = _safe_json_list(record.get("existing_keywords")) + _safe_json_list(record.get("lrcat_keywords"))
    own_kws = [k for k in dict.fromkeys(own_kws) if k.lower() not in GENERIC_NOISE_TAGS]
    if own_kws:
        hints.append(f"Verified File Keywords: {', '.join(own_kws)}")

    for label, field in [
        ("Title", "title"),
        ("Caption", "caption"),
        ("Sub-location", "sub_location"),
        ("Specific Location", "specific_location"),
        ("City", "city"),
        ("State/Region", "state_region"),
        ("Country", "country"),
    ]:
        val = record.get(field)
        if val and str(val).strip().lower() not in ("", "unknown", "none"):
            hints.append(f"Verified {label}: {val}")

    # Self-learning Ground-Truth Context Injection
    if ground_truth:
        gt_parts = []
        for k in ("sub_location", "specific_location", "city", "state_region", "country"):
            if ground_truth.get(k):
                gt_parts.append(f"{k}={ground_truth[k]}")
        if ground_truth.get("curated_keywords"):
            gt_parts.append(f"keywords={', '.join(ground_truth['curated_keywords'][:15])}")
        hints.append(
            f"Verified Archive Ground-Truth Match ({ground_truth['match_type']}, "
            f"landmark='{ground_truth['cluster_name']}'): {'; '.join(gt_parts)}"
        )

    # Photographer's Taught Context / Overrides (Highest Authority)
    user_note = str(record.get("user_context_notes") or "").strip()
    if user_note == "[CLEARED_SLATE]":
        user_note = ""
    user_taught = _safe_json_list(record.get("user_taught_tags"))
    negated = _safe_json_list(record.get("negated_tags"))
    if user_note:
        hints.append(f"PHOTOGRAPHER GROUND-TRUTH OVERRIDE NOTE (MUST OBEY): {user_note}")
    if user_taught:
        hints.append(f"PHOTOGRAPHER TAUGHT TAGS (MUST INCLUDE): {', '.join(user_taught)}")
    if negated:
        hints.append(f"PHOTOGRAPHER FORBIDDEN / NEGATED TAGS (NEVER OUTPUT THESE): {', '.join(negated)}")

    prompt = "Analyze photograph based on directive and return valid JSON."
    if hints:
        prompt += "\n\nVerified Context & Ground-Truth Metadata (MUST preserve exact names):\n"
        prompt += "\n".join(f"- {h}" for h in hints)
    return prompt


def call_qwen_vlm(
    preview_path: Path,
    prompt_text: str,
    directive_text: str,
    vlm_model: str = "qwen2.5vl:7b",
    mock_vlm_fn: Optional[Callable[[Path, str], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Executes Qwen2.5-VL inference on an 896px in-memory resized buffer of the preview image
    (never deleting or modifying the persistent 1600px / 360px WebP files!).
    """
    if mock_vlm_fn is not None:
        return mock_vlm_fn(preview_path, prompt_text)

    if ollama is None:
        raise RuntimeError("ollama Python package is not available.")

    # Encode an<=896px RGB JPEG into bytes in memory so persistent WebP previews are never modified
    import io
    with Image.open(preview_path) as im:
        im_copy = im.convert("RGB")
        if max(im_copy.size) > 896:
            im_copy.thumbnail((896, 896), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im_copy.save(buf, format="JPEG", quality=85)
        img_bytes = buf.getvalue()

    target_model = resolve_ollama_model(vlm_model)
    resp = ollama.generate(
        model=target_model,
        system=directive_text,
        prompt=prompt_text,
        images=[img_bytes],
        keep_alive="1h",
        format="json",
        options={
            "num_ctx": 4096,
            "num_predict": 768,
            "temperature": 0.1,
        },
    )
    raw_response = resp.get("response", "") if isinstance(resp, dict) else getattr(resp, "response", "")
    try:
        ai_data = json.loads(raw_response)
    except Exception:
        match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        ai_data = json.loads(match.group(0)) if match else {}

    # Sanitize single-value category fields
    extra_pipe_tags = []
    for field in ["primary_category", "sub_category", "lighting_atmosphere"]:
        val = ai_data.get(field)
        if isinstance(val, str) and ("|" in val or "/" in val or "," in val):
            parts = [p.strip() for p in re.split(r"[|/,]", val) if p.strip()]
            if parts:
                ai_data[field] = parts[0].replace(" ", "_") if field != "primary_category" else parts[0]
                extra_pipe_tags.extend(p.replace(" ", "_") for p in parts[1:])
        elif isinstance(val, str) and field == "sub_category":
            ai_data[field] = val.strip().replace(" ", "_")

    if extra_pipe_tags:
        fk = ai_data.get("flat_keywords", [])
        if not isinstance(fk, list):
            fk = []
        fk.extend(extra_pipe_tags)
        ai_data["flat_keywords"] = fk

    return ai_data


# ==============================================================================
# 4. RECORD MERGER (STRICTLY PRESERVES FRAME-SPECIFIC KEYWORDS & SHARPNESS)
# ==============================================================================
def merge_ai_and_frame_metadata(
    frame_record: Dict[str, Any],
    ai_data: Dict[str, Any],
    ground_truth: Optional[Dict[str, Any]],
    faces_detected: List[str],
    status_label: str,
    clip_probes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Merges VLM semantic output + ground-truth context with a specific frame's own
    pre-existing keywords, Lightroom tags, and technical sharpness/monochrome tags.
    Fixes v2.0 Bug #3: never drops existing keywords on burst/sequence sibling frames,
    and never contaminates sharp frames with 'Unsharp' or vice versa.
    Also applies perspective-gated landmark sanitization and multi-tier ontology expansion.
    """
    # 1. Start with frame's own pre-existing & Lightroom keywords
    own_existing = _safe_json_list(frame_record.get("existing_keywords"))
    own_lrcat = _safe_json_list(frame_record.get("lrcat_keywords"))
    own_hier = _safe_json_list(frame_record.get("hierarchical_keywords"))

    flat_kws: List[str] = []
    hier_kws: List[str] = []

    for k in own_lrcat + own_existing:
        if k not in ("Unsharp", "Monochrome") and k not in flat_kws:
            flat_kws.append(k)

    for hk in own_hier:
        if hk not in ("Technical|Focus|Unsharp", "Technical|Monochrome") and hk not in hier_kws:
            hier_kws.append(hk)

    # 2. Add Ground-Truth Self-Learning Keywords & Location
    if ground_truth:
        for gk in ground_truth.get("curated_keywords", []):
            if gk not in flat_kws:
                flat_kws.append(gk)
        for ghk in ground_truth.get("hierarchical_keywords", []):
            if ghk not in hier_kws:
                hier_kws.append(ghk)

    # 3. Add VLM semantic keywords & categories
    for k in (ai_data.get("flat_keywords") or []) + (ai_data.get("key_subjects") or []):
        k_str = str(k).strip()
        if k_str and k_str not in ("Unsharp", "Monochrome") and k_str not in flat_kws:
            flat_kws.append(k_str)

    for hk in ai_data.get("hierarchical_keywords") or []:
        hk_str = str(hk).strip()
        if hk_str and hk_str not in ("Technical|Focus|Unsharp", "Technical|Monochrome") and hk_str not in hier_kws:
            hier_kws.append(hk_str)

    primary_cat = str(ai_data.get("primary_category") or frame_record.get("primary_category") or "Landscape").strip()
    sub_cat = str(ai_data.get("sub_category") or frame_record.get("sub_category") or "").strip()
    lighting = str(ai_data.get("lighting_atmosphere") or "").strip()

    if primary_cat and primary_cat not in flat_kws:
        flat_kws.append(primary_cat)
    if sub_cat and sub_cat not in flat_kws:
        flat_kws.append(sub_cat)
    if lighting:
        if lighting not in flat_kws:
            flat_kws.append(lighting)
        l_tag = f"Lighting|{lighting}"
        if l_tag not in hier_kws:
            hier_kws.append(l_tag)

    # People details from VLM
    people_list = ai_data.get("people_details", [])
    if isinstance(people_list, list):
        for p in people_list:
            if isinstance(p, dict):
                demo = p.get("demographic")
                role = p.get("role")
                hair = p.get("hair")
                if demo:
                    if demo not in flat_kws:
                        flat_kws.append(demo)
                    if f"Subjects|People|{demo}" not in hier_kws:
                        hier_kws.append(f"Subjects|People|{demo}")
                if role:
                    if role not in flat_kws:
                        flat_kws.append(role)
                    if f"Subjects|People|{role}" not in hier_kws:
                        hier_kws.append(f"Subjects|People|{role}")
                if hair:
                    if hair not in flat_kws:
                        flat_kws.append(hair)
                    if f"People|Hair|{hair}" not in hier_kws:
                        hier_kws.append(f"People|Hair|{hair}")

    # Biometric faces
    for f_name in faces_detected:
        if f_name not in flat_kws:
            flat_kws.append(f_name)
        clean_name = f_name.replace("Person: ", "").strip()
        h_face = f"People|Named|{clean_name}"
        if h_face not in hier_kws:
            hier_kws.append(h_face)

    # 4. Resolve authoritative location fields — Strict Location Provenance (100% Blank by Default unless verified)
    geo_anchor = (clip_probes or {}).get("_geo_anchor")
    if geo_anchor is None:
        geo_anchor = decode_shorthand_geography(frame_record, probes=clip_probes)

    if str(frame_record.get("location_provenance") or "").strip() == "user_cleared":
        country = ""
        state_region = ""
        city = ""
        sub_location = ""
        specific_location = ""
        location_provenance = "user_cleared"
    elif geo_anchor is not None:
        country = str(geo_anchor.get("country") or "").strip()
        state_region = str(geo_anchor.get("state_region") or "").strip()
        city = str(geo_anchor.get("city") or frame_record.get("city") or "").strip()
        sub_location = str(frame_record.get("sub_location") or "").strip()
        specific_location = str(geo_anchor.get("specific_location") or sub_location or "").strip()
        location_provenance = str(geo_anchor.get("source") or "verified").strip()
    else:
        country = ""
        state_region = ""
        city = ""
        sub_location = ""
        specific_location = ""
        location_provenance = ""

    for bad_val in ("unknown", "none", "general", "not specified"):
        if country.lower() == bad_val:
            country = ""
        if state_region.lower() == bad_val:
            state_region = ""
        if city.lower() == bad_val:
            city = ""
        if specific_location.lower() == bad_val:
            specific_location = ""

    _, is_confirmed_aerial = select_guide_directive(frame_record, ground_truth=ground_truth, clip_probes=clip_probes)
    if ai_data.get("is_aerial") is True and is_confirmed_aerial:
        is_aerial = 1
    else:
        is_aerial = 1 if is_confirmed_aerial else 0

    if not is_aerial and primary_cat == "Aerial":
        primary_cat = "Landscape"
        flat_kws = [k for k in flat_kws if k != "Aerial"]

    # 4B. Strip any hallucinated aerial landmarks (e.g., Taft Oil Field or Palouse on unconfirmed terrestrial photos)
    flat_kws, hier_kws, specific_location, state_region = strip_hallucinated_landmarks(
        flat_kws=flat_kws,
        hier_kws=hier_kws,
        record=frame_record,
        specific_location=specific_location or None,
        state_region=state_region or None,
        is_confirmed_aerial=bool(is_aerial),
        clip_probes=clip_probes,
    )
    specific_location = str(specific_location or "").strip()
    state_region = str(state_region or "").strip()
    if specific_location.lower() in ("unknown", "none"):
        specific_location = ""
    if state_region.lower() in ("unknown", "none"):
        state_region = ""

    # If no verified geo_anchor, strip any AI-guessed Places| or state/country names from flat_kws and hier_kws
    if not location_provenance or location_provenance == "user_cleared":
        country = ""
        state_region = ""
        city = ""
        specific_location = ""
        hier_kws = [hk for hk in hier_kws if not str(hk).lower().startswith("places|")]

    # Only add named landmarks to flat_kws; do NOT duplicate reverse-geocoded GPS municipal addresses
    if specific_location and location_provenance not in ("gps_ground_truth", "gps", "gps_same_day") and specific_location not in flat_kws:
        if not (city and state_region and specific_location.lower() == f"{city}, {state_region}".lower()):
            flat_kws.append(specific_location)

    if country:
        reg_val = state_region or country
        if specific_location and specific_location != reg_val:
            p_tag = f"Places|{country}|{reg_val}|{specific_location}"
        else:
            p_tag = f"Places|{country}|{reg_val}"
        if p_tag not in hier_kws:
            hier_kws.append(p_tag)

    # 4C. Multi-tier Ontology Expansion (Parent -> Mid -> Specific for Animals, People, Mitch Identity, Flora, Structures)
    flat_kws, hier_kws = expand_hierarchical_ontology(
        flat_kws=flat_kws,
        hier_kws=hier_kws,
        record=frame_record,
        clip_probes=clip_probes,
    )

    # 4D. 5-Facet Visual Keyword Synthesis
    flat_kws, hier_kws = synthesize_5facet_visual_keywords(
        record=frame_record,
        probes=clip_probes or {},
        flat_kws=flat_kws,
        hier_kws=hier_kws,
        primary_category=primary_cat,
        country=country,
        state_region=state_region,
        specific_location=specific_location,
    )

    # 4E. Enforce Persistent User Teach Overrides (Taught tags & Negated tags)
    flat_kws, hier_kws, country, state_region, city, specific_location = apply_user_teach_overrides(
        flat_kws=flat_kws,
        hier_kws=hier_kws,
        record=frame_record,
        country=country,
        state_region=state_region,
        city=city,
        specific_location=specific_location,
    )
    country = str(country or "").strip()
    state_region = str(state_region or "").strip()
    city = str(city or "").strip()
    specific_location = str(specific_location or "").strip()
    for bad_val in ("unknown", "none"):
        if country.lower() == bad_val:
            country = ""
        if state_region.lower() == bad_val:
            state_region = ""
        if city.lower() == bad_val:
            city = ""
        if specific_location.lower() == bad_val:
            specific_location = ""

    if (country or state_region or city or specific_location) and not location_provenance:
        location_provenance = "user"

    # 5. Frame-Specific Technical Rules: Sharpness ('Technical|Focus|Unsharp' in hier_kws ONLY, not as a visible tag pill) & Monochrome
    is_unsharp = int(frame_record.get("is_unsharp") or 0)
    is_mono = int(frame_record.get("is_monochrome") or 0)

    flat_kws = [k for k in flat_kws if k not in ("Unsharp", "Sharp", "Eye-level terrestrial", "Eye-level", "Terrestrial")]
    if is_unsharp == 1:
        if "Technical|Focus|Unsharp" not in hier_kws:
            hier_kws.append("Technical|Focus|Unsharp")
    else:
        hier_kws = [hk for hk in hier_kws if hk != "Technical|Focus|Unsharp"]

    if is_mono == 1:
        if "Monochrome" not in flat_kws:
            flat_kws.append("Monochrome")
        if "Technical|Monochrome" not in hier_kws:
            hier_kws.append("Technical|Monochrome")

    flat_kws = deduplicate_singular_plural_tags(
        list(dict.fromkeys(flat_kws)),
        subject_counts=(clip_probes or {}).get("subject_counts"),
    )

    conf_score = float(ai_data.get("confidence_score") or 0.85)
    if ground_truth and conf_score < 0.88:
        conf_score = max(conf_score, 0.90)

    return {
        "file_path": frame_record["file_path"],
        "status": status_label,
        "primary_category": primary_cat,
        "sub_category": sub_cat,
        "country": country,
        "state_region": state_region,
        "city": city,
        "sub_location": sub_location,
        "specific_location": specific_location,
        "location_provenance": location_provenance,
        "subject_boxes": json.dumps((clip_probes or {}).get("subject_boxes", [])),
        "verified_subjects": json.dumps((clip_probes or {}).get("verified_subjects", [])),
        "key_subjects": json.dumps(list(dict.fromkeys(flat_kws))),
        "hierarchical_keywords": json.dumps(list(dict.fromkeys(hier_kws))),
        "is_aerial": is_aerial,
        "confidence_score": round(conf_score, 3),
    }


# ==============================================================================
# 5. STAGE 2 ORCHESTRATOR WITH 35-FRAME STRAFING STRIDE
# ==============================================================================
def select_sequence_vlm_anchor_indices(
    seq_frames: List[Dict[str, Any]],
    vectors: np.ndarray,
    stride: int = 35,
    similarity_drop_threshold: float = 0.85,
) -> List[int]:
    """
    Selects which frame indices inside a sequence must be sent to Qwen2.5-VL:
    - Always includes the Sequence Hero (`is_sequence_hero == 1`, or index 0 if none marked).
    - For sequences > 10 frames (e.g., 4,000-frame aerial strafing runs), selects 1 anchor frame
      every `stride` (35) frames.
    - Also triggers a new VLM anchor whenever a frame's CLIP cosine similarity to the most recent
      selected anchor drops below `similarity_drop_threshold` (0.85).
    """
    n = len(seq_frames)
    if n == 0:
        return []
    if n == 1:
        return [0]

    selected_set = set()
    hero_indices = [i for i, f in enumerate(seq_frames) if int(f.get("is_sequence_hero") or 0) == 1]
    primary_hero_idx = hero_indices[0] if hero_indices else 0
    selected_set.add(primary_hero_idx)

    if n > 10:
        for i in range(0, n, stride):
            selected_set.add(i)

    # Check CLIP similarity drift across sequence order
    last_anchor_vec: Optional[np.ndarray] = None
    v_hero = seq_frames[primary_hero_idx].get("vector_index")
    if v_hero is not None and 0 <= int(v_hero) < vectors.shape[0]:
        last_anchor_vec = vectors[int(v_hero)].astype(np.float32)

    last_anchor_idx = 0
    for i, frame in enumerate(seq_frames):
        if i in selected_set:
            v_idx = frame.get("vector_index")
            if v_idx is not None and 0 <= int(v_idx) < vectors.shape[0]:
                last_anchor_vec = vectors[int(v_idx)].astype(np.float32)
            last_anchor_idx = i
            continue

        # Check stride or similarity drop < 0.85
        if n > 10 and (i - last_anchor_idx) >= stride:
            selected_set.add(i)
            last_anchor_idx = i
            v_idx = frame.get("vector_index")
            if v_idx is not None and 0 <= int(v_idx) < vectors.shape[0]:
                last_anchor_vec = vectors[int(v_idx)].astype(np.float32)
            continue

        v_idx = frame.get("vector_index")
        if (
            last_anchor_vec is not None
            and v_idx is not None
            and 0 <= int(v_idx) < vectors.shape[0]
        ):
            vec = vectors[int(v_idx)].astype(np.float32)
            sim = float(np.dot(last_anchor_vec, vec))
            if sim < similarity_drop_threshold:
                selected_set.add(i)
                last_anchor_vec = vec
                last_anchor_idx = i

    return sorted(selected_set)


def run_stage2_vlm(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    catalog_name: Optional[str] = None,
    vlm_model: str = "qwen2.5vl:7b",
    strafing_stride: int = 35,
    similarity_drop_threshold: float = 0.85,
    orbit_window_seconds: float = 180.0,
    centroid_similarity_threshold: float = 0.84,
    force_rerun: bool = False,
    max_sequences: Optional[int] = None,
    pause_event: Optional[threading.Event] = None,
    mock_vlm_fn: Optional[Callable[[Path, str], Dict[str, Any]]] = None,
    progress_callback: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    """
    Executes Stage 2 Self-Learning Metadata Propagation & Smart VLM Enrichment:
    1. Builds Self-Learning Metadata Centroid & Helicopter Orbit Time-Window Index.
    2. Groups pending Stage 1 photos by `sequence_id`.
    3. Inside each sequence, runs Qwen2.5-VL ONLY on the Sequence Hero + 1 anchor every 35 frames
       (or when CLIP similarity drops < 0.85), propagating semantic tags across sibling frames while
       strictly preserving each frame's own pre-existing keywords, .lrcat tags, and sharpness tags.
    """
    t0 = time.time()

    def _emit_progress(done_cnt: int, total_cnt: int, cur_file: str, phase_msg: str = "AI Visual Tagging & Scene Analysis") -> None:
        if progress_callback is None:
            return
        try:
            progress_callback(done_cnt, total_cnt, cur_file, phase_msg)
        except TypeError:
            try:
                progress_callback(done_cnt, total_cnt, cur_file)
            except Exception:
                pass

    directive_text = (
        DIRECTIVE_PATH.read_text(encoding="utf-8")
        if DIRECTIVE_PATH.exists()
        else "Analyze photograph and return valid JSON metadata."
    )

    # 1. Build Self-Learning Centroid & Orbit Index from all curated records in DB
    learned_index = build_self_learning_index(db_path=db_path, vectors_path=vectors_path)
    vectors = load_or_init_vectors_matrix(vectors_path)
    biometrics = BiometricMatcher()

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    done_clauses = ["stage1_completed = 1", "status != 'failed'", "stage2_completed = 1"]
    done_params: List[Any] = []
    if catalog_name and catalog_name != "All Catalogs":
        done_clauses.append("catalog_name = ?")
        done_params.append(catalog_name)
    already_done = 0
    if not force_rerun:
        already_done = int(
            cursor.execute(
                f"SELECT COUNT(*) FROM photo_records WHERE {' AND '.join(done_clauses)}",
                done_params,
            ).fetchone()[0]
        )

    where_clauses = ["stage1_completed = 1", "status != 'failed'"]
    params: List[Any] = []
    if not force_rerun:
        where_clauses.append("(stage2_completed = 0 OR stage2_completed IS NULL)")
    if catalog_name and catalog_name != "All Catalogs":
        where_clauses.append("catalog_name = ?")
        params.append(catalog_name)

    query = f"""
        SELECT file_path, catalog_name, sequence_id, sequence_frame_index, sequence_length,
               is_sequence_hero, exif_time, shoot_date,
               camera_make, camera_model, camera_serial, lens_model,
               focal_length, shutter_speed, aperture, iso,
               gps_lat, gps_lon, gps_alt, gps_ground_truth, is_screenshot,
               title, caption, sub_location, specific_location, city, state_region, country,
               existing_keywords, lrcat_keywords, key_subjects, hierarchical_keywords,
               preview_1600_path, thumb_360_path,
               sharpness_score, is_unsharp, is_monochrome, vector_index,
               primary_category, sub_category,
               user_context_notes, user_taught_tags, negated_tags,
               subject_boxes, verified_subjects, location_provenance
        FROM photo_records
        WHERE {' AND '.join(where_clauses)}
        ORDER BY sequence_id ASC, sequence_frame_index ASC
    """
    rows = [dict(r) for r in cursor.execute(query, params).fetchall()]
    conn.close()

    total_frames_scope = already_done + len(rows)
    _emit_progress(
        already_done,
        max(1, total_frames_scope),
        Path(rows[0]["file_path"]).name if rows else "All photos tagged",
        "AI Visual Tagging & Scene Analysis",
    )

    if not rows:
        return {
            "status": "completed",
            "total_pending_frames": 0,
            "already_completed_frames": already_done,
            "vlm_anchor_calls": 0,
            "propagated_sibling_frames": 0,
            "ground_truth_matches": 0,
            "centroids_indexed": learned_index["centroids_count"],
            "elapsed_seconds": round(time.time() - t0, 2),
        }

    probes_map = compute_clip_concept_probes_for_rows(rows=rows, vectors=vectors, db_path=db_path)
    resolved_geo_map = propagate_shoot_day_geography(rows=rows, probes_map=probes_map, vectors=vectors)
    for fp_k, g_val in resolved_geo_map.items():
        if fp_k in probes_map:
            probes_map[fp_k]["_geo_anchor"] = g_val

    # Group frames by sequence_id
    sequences_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        seq_key = str(r.get("sequence_id") or f"SINGLE_{r['file_path']}")
        sequences_map.setdefault(seq_key, []).append(r)

    vlm_calls = 0
    propagated_frames = 0
    ground_truth_matches = 0
    completed_in_run = 0
    paused_early = False

    seq_items = list(sequences_map.items())
    if max_sequences is not None:
        seq_items = seq_items[:max_sequences]

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    for seq_id, seq_frames in seq_items:
        # Check pause signal
        active_pause = pause_event or STAGE2_PAUSE_EVENT
        if active_pause.is_set():
            paused_early = True
            break

        anchor_indices = select_sequence_vlm_anchor_indices(
            seq_frames,
            vectors=vectors,
            stride=strafing_stride,
            similarity_drop_threshold=similarity_drop_threshold,
        )

        anchor_results: Dict[int, Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = {}

        # Run VLM on selected anchor frames in this sequence
        for a_idx in anchor_indices:
            anchor_frame = seq_frames[a_idx]
            cur_fname = Path(anchor_frame["file_path"]).name
            _emit_progress(
                already_done + completed_in_run,
                max(1, total_frames_scope),
                cur_fname,
                f"AI Vision Tagging: {cur_fname}",
            )
            gt = lookup_ground_truth_context(
                anchor_frame,
                learned_index=learned_index,
                vectors=vectors,
                orbit_window_seconds=orbit_window_seconds,
                centroid_similarity_threshold=centroid_similarity_threshold,
            )
            if gt is not None:
                ground_truth_matches += 1

            prompt_str = build_vlm_prompt(anchor_frame, ground_truth=gt)
            frame_directive, _ = select_guide_directive(anchor_frame, ground_truth=gt)
            preview_p = Path(anchor_frame.get("preview_1600_path") or anchor_frame.get("thumb_360_path") or "")

            try:
                ai_out = call_qwen_vlm(
                    preview_path=preview_p,
                    prompt_text=prompt_str,
                    directive_text=frame_directive if DIRECTIVE_PATH.exists() else directive_text,
                    vlm_model=vlm_model,
                    mock_vlm_fn=mock_vlm_fn,
                )
                vlm_calls += 1
            except Exception as exc:
                log_ingestion_error(
                    db_path,
                    anchor_frame["file_path"],
                    "stage2_vlm",
                    type(exc).__name__,
                    str(exc),
                )
                # Fallback semantic synthesis from ground truth + existing metadata if VLM unavailable
                ai_out = {
                    "primary_category": "Aerial" if "aerial" in str(anchor_frame.get("catalog_name", "")).lower() else "Landscape",
                    "sub_category": "Archival",
                    "country": (gt or {}).get("country") or anchor_frame.get("country") or "United States",
                    "state_region": (gt or {}).get("state_region") or anchor_frame.get("state_region"),
                    "specific_location": (gt or {}).get("specific_location") or anchor_frame.get("specific_location") or "Unknown",
                    "flat_keywords": (gt or {}).get("curated_keywords", []),
                    "hierarchical_keywords": (gt or {}).get("hierarchical_keywords", []),
                    "is_aerial": "aerial" in str(anchor_frame.get("catalog_name", "")).lower(),
                    "confidence_score": 0.80 if gt else 0.65,
                }

            anchor_results[a_idx] = (ai_out, gt)

        # Apply to all frames in the sequence (anchors get status='tagged', siblings get status='inherited')
        db_batch_updates = []
        for f_idx, frame in enumerate(seq_frames):
            # Find nearest evaluated anchor in sequence
            nearest_a_idx = min(anchor_indices, key=lambda a: abs(f_idx - a))
            ai_data, anchor_gt = anchor_results[nearest_a_idx]

            # Also check if this individual sibling frame has its own direct ground-truth match
            frame_gt = lookup_ground_truth_context(
                frame,
                learned_index=learned_index,
                vectors=vectors,
                orbit_window_seconds=orbit_window_seconds,
                centroid_similarity_threshold=centroid_similarity_threshold,
            ) or anchor_gt

            preview_p = Path(frame.get("preview_1600_path") or frame.get("thumb_360_path") or "")
            faces = biometrics.detect_faces(preview_p if preview_p.exists() else None)

            is_direct_anchor = f_idx in anchor_results
            status_label = "tagged" if is_direct_anchor else "inherited"
            if not is_direct_anchor:
                propagated_frames += 1

            merged = merge_ai_and_frame_metadata(
                frame_record=frame,
                ai_data=ai_data,
                ground_truth=frame_gt,
                faces_detected=faces,
                status_label=status_label,
                clip_probes=probes_map.get(frame["file_path"], {}),
            )

            db_batch_updates.append((
                merged["status"],
                merged["primary_category"],
                merged["sub_category"],
                merged["country"],
                merged["state_region"],
                merged["city"],
                merged["sub_location"],
                merged["specific_location"],
                merged["location_provenance"],
                merged["subject_boxes"],
                merged["verified_subjects"],
                merged["key_subjects"],
                merged["hierarchical_keywords"],
                merged["is_aerial"],
                merged["confidence_score"],
                merged["file_path"],
            ))

        cursor.executemany("""
            UPDATE photo_records
            SET status = ?,
                primary_category = ?,
                sub_category = ?,
                country = ?,
                state_region = ?,
                city = ?,
                sub_location = ?,
                specific_location = ?,
                location_provenance = ?,
                subject_boxes = ?,
                verified_subjects = ?,
                key_subjects = ?,
                hierarchical_keywords = ?,
                is_aerial = ?,
                confidence_score = ?,
                stage2_completed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """, db_batch_updates)
        conn.commit()
        completed_in_run += len(db_batch_updates)
        last_fname = Path(seq_frames[-1]["file_path"]).name if seq_frames else ""
        _emit_progress(
            already_done + completed_in_run,
            max(1, total_frames_scope),
            last_fname,
            f"Tagged {already_done + completed_in_run} / {total_frames_scope} ({last_fname})",
        )

    conn.close()

    return {
        "status": "paused" if paused_early else "completed",
        "total_pending_frames": len(rows),
        "already_completed_frames": already_done,
        "completed_in_run": completed_in_run,
        "sequences_processed": len(seq_items),
        "vlm_anchor_calls": vlm_calls,
        "propagated_sibling_frames": propagated_frames,
        "ground_truth_matches": ground_truth_matches,
        "centroids_indexed": learned_index["centroids_count"],
        "elapsed_seconds": round(time.time() - t0, 2),
    }


# ==============================================================================
# 6. PROGRESSIVE CROSS-CATALOG LEARNING, GLOBAL LANDMARK GAZETTEER & SHOOT-DAY PROPAGATION
# ==============================================================================
# (CONCEPT_PROBE_PROMPTS and GLOBAL_LANDMARK_GAZETTEER imported from domain_gazetteer.py)


def decode_shorthand_geography(
    record: Dict[str, Any],
    probes: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Deterministic Filename Stem, .lrcat Keyword & Verified Location Decoder.
    Parses geographic/landmark shorthand in filenames (e.g., VlyGods, MnuVly, TetonColors,
    Yospano, Zabriski, TrippleWF, DC_Flags, Venice), user-taught geography, and curated .lrcat/existing metadata
    as 100% ground-truth anchors before any visual guessing. Never returns negated locations.
    """
    negated_low = {k.lower().strip() for k in _safe_json_list(record.get("negated_tags")) if k.strip()}
    loc_prov = str(record.get("location_provenance") or "").strip()
    if loc_prov == "user_cleared":
        return None

    user_taught = [k.strip() for k in _safe_json_list(record.get("user_taught_tags")) if k.strip()]
    user_note = str(record.get("user_context_notes") or "").strip()

    # 0A. Direct User-Set Location Provenance (via 1-click Lightbox Set Location control)
    if loc_prov == "user":
        u_ctry = str(record.get("country") or "").strip()
        u_st = str(record.get("state_region") or "").strip()
        u_city = str(record.get("city") or "").strip()
        u_spec = str(record.get("specific_location") or "").strip()
        if any(v and v.lower() != "unknown" for v in (u_ctry, u_st, u_city, u_spec)):
            loc_label = u_spec or u_city or u_st or u_ctry
            reg_label = u_st or u_ctry or loc_label
            ctry_label = u_ctry or ("United States" if u_st else loc_label)
            u_tags = list(dict.fromkeys([t for t in [u_spec, u_city, u_st, u_ctry] if t and t.lower() not in ("unknown", "") and t.lower() not in negated_low]))
            return {
                "source": "user_taught",
                "specific_location": loc_label,
                "state_region": u_st or None,
                "city": u_city or None,
                "country": ctry_label,
                "hierarchy": f"Places|{ctry_label}|{reg_label}|{loc_label}" if loc_label != reg_label else f"Places|{ctry_label}|{reg_label}",
                "tags": u_tags,
            }

    # 0. Highest-priority: User-Taught Geography (never overridden by filename or shoot-day rules)
    if user_taught or user_note:
        parsed_ut = parse_natural_language_teach(
            user_note or " ".join(user_taught),
            explicit_add_tags=user_taught,
            explicit_remove_tags=list(negated_low),
        )
        ut_country = parsed_ut.get("country") or (str(record.get("country") or "").strip() if user_taught else "")
        ut_state = parsed_ut.get("state_region") or (str(record.get("state_region") or "").strip() if user_taught else "")
        ut_spec = parsed_ut.get("specific_location") or (str(record.get("specific_location") or "").strip() if user_taught else "")
        if ut_country and ut_country.lower() not in ("unknown", "") and ut_country.lower() not in negated_low:
            loc_label = ut_spec or ut_state or ut_country
            reg_label = ut_state or ut_country
            return {
                "source": "user_taught",
                "specific_location": loc_label,
                "state_region": ut_state or None,
                "country": ut_country,
                "hierarchy": f"Places|{ut_country}|{reg_label}|{loc_label}" if loc_label != reg_label else f"Places|{ut_country}|{reg_label}",
                "tags": [t for t in parsed_ut.get("added_tags", []) if t.lower().strip() not in negated_low],
            }

    fp_name = Path(str(record.get("file_path") or "")).stem.lower()
    # Strip leading YYYY_MM_DD - prefix if present
    fp_clean = re.sub(r"^\d{4}_\d{2}_\d{2}\s*-\s*", "", fp_name)
    fp_norm = fp_clean.replace("_", " ").replace("-", " ")

    sdate = str(record.get("shoot_date") or "")
    lrcat_kws = [
        k.strip() for k in _safe_json_list(record.get("lrcat_keywords"))
        if k.strip().lower() not in GENERIC_NOISE_TAGS and k.strip().lower() not in negated_low
    ]
    if sdate in ("2009-09-28", "2009-10-01") or "teton" in fp_clean or any("denver" in k.lower() for k in lrcat_kws):
        lrcat_kws = [k for k in lrcat_kws if k.lower() != "england"]

    exist_kws = [
        k.strip() for k in _safe_json_list(record.get("existing_keywords"))
        if k.strip().lower() not in GENERIC_NOISE_TAGS and k.strip().lower() not in negated_low
    ]
    if sdate in ("2009-09-28", "2009-10-01") or "teton" in fp_clean:
        exist_kws = [k for k in exist_kws if k.lower() != "england"]

    kw_blob = " ".join(k.lower() for k in lrcat_kws + exist_kws)
    orig_spec = str(record.get("specific_location") or "").strip()
    orig_city = str(record.get("city") or "").strip()
    orig_state = str(record.get("state_region") or "").strip()
    orig_country = str(record.get("country") or "").strip()
    if orig_spec.lower() in negated_low:
        orig_spec = ""
    if orig_city.lower() in negated_low:
        orig_city = ""
    if orig_state.lower() in negated_low:
        orig_state = ""
    if orig_country.lower() in negated_low:
        orig_country = ""

    # 0B. Verified GPS Ground Truth (EXIF GPS coordinates or same-day GPS camera bridge)
    has_gps_gt = bool(
        int(record.get("gps_ground_truth") or 0) == 1
        or (record.get("gps_lat") is not None and record.get("gps_lon") is not None)
    )
    if has_gps_gt and (orig_country or orig_state or orig_city or orig_spec):
        gps_country = orig_country or "United States"
        gps_state = orig_state or None
        gps_spec = (
            orig_spec
            if (orig_spec and orig_spec.lower() not in ("unknown", "none", "general"))
            else (f"{orig_city}, {orig_state}" if (orig_city and orig_state) else (orig_city or orig_state or gps_country))
        )
        place_parts = [p for p in ["Places", gps_country, gps_state, orig_city, gps_spec] if p]
        return {
            "source": "gps_ground_truth",
            "specific_location": gps_spec,
            "state_region": gps_state,
            "city": orig_city or None,
            "country": gps_country,
            "hierarchy": "|".join(dict.fromkeys(place_parts)),
            "tags": [],
        }

    # 1. Explicit Filename Shorthand Stem Rules (Highest Priority — never overridden)
    if any(tok in fp_clean for tok in ("vlygods", "vly_of_gods", "valley_of_the_gods")):
        return {
            "source": "filename_stem",
            "specific_location": "Valley of the Gods",
            "state_region": "Utah",
            "country": "United States",
            "hierarchy": "Places|United States|Utah|Valley of the Gods",
            "tags": ["Valley of the Gods", "Utah", "Butte", "Buttes", "Sandstone Butte", "Red Rock Spire", "Desert Monolith", "Cedar Mesa"],
        }

    if any(tok in fp_clean for tok in ("mnuvly", "mnvly", "monvly", "monvalley", "monv_", "mexhat", "mv_fog", "teardrop")):
        return {
            "source": "filename_stem",
            "specific_location": "Monument Valley",
            "state_region": "Arizona",
            "country": "United States",
            "hierarchy": "Places|United States|Arizona|Monument Valley",
            "tags": ["Monument Valley", "Arizona", "Utah", "Butte", "Buttes", "Mitten Buttes", "Sandstone Butte", "Desert Monolith", "Colorado Plateau"],
        }

    if "half_a_butte" in fp_clean or "butte" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Monument Valley & Colorado Plateau",
            "state_region": "Arizona",
            "country": "United States",
            "hierarchy": "Places|United States|Arizona|Monument Valley",
            "tags": ["Butte", "Buttes", "Sandstone Butte", "Desert Monolith", "Monument Valley", "Colorado Plateau"],
        }

    if any(tok in fp_clean for tok in ("teton", "tetoncolors", "tetoncolor")):
        return {
            "source": "filename_stem",
            "specific_location": "Grand Teton National Park",
            "state_region": "Wyoming",
            "country": "United States",
            "hierarchy": "Places|United States|Wyoming|Grand Tetons",
            "tags": ["Grand Teton National Park", "Grand Tetons", "Tetons", "Teton Range", "Wyoming", "Mountain Peak", "Alpine Peaks", "Jackson Hole"],
        }

    if "yellowstone" in fp_clean or "yellowstone" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Yellowstone National Park",
            "state_region": "Wyoming",
            "country": "United States",
            "hierarchy": "Places|United States|Wyoming|Yellowstone",
            "tags": ["Yellowstone National Park", "Yellowstone", "Wyoming"],
        }

    if any(tok in fp_clean for tok in ("southfork", "hawkeye")) or any(tok in kw_blob for tok in ("southfork", "hawkeye")):
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Hawkeye Ranch & Southfork Valley",
            "state_region": "Wyoming",
            "country": "United States",
            "hierarchy": "Places|United States|Wyoming|Southfork Valley",
            "tags": ["Hawkeye Ranch", "Southfork Valley", "Cody", "Wyoming", "Ranch", "Barns & Ranch"],
        }

    if "humphrey" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Humphrey, Nebraska",
            "state_region": "Nebraska",
            "country": "United States",
            "hierarchy": "Places|United States|Nebraska|Humphrey",
            "tags": ["Humphrey, Nebraska", "Nebraska", "Grain Elevator", "Farmland", "Great Plains"],
        }

    if any(tok in fp_clean for tok in ("cayucos", "pier", "bolsa", "avila", "pointlobos", "point_lobos", "laguna", "catalina", "santabarbara", "santa_barbara")):
        if "pointlobos" in fp_clean or "point_lobos" in fp_clean:
            spec_c = "Point Lobos"
        elif "cayucos" in fp_clean or "pier" in fp_clean or "bolsa" in fp_clean or "avila" in fp_clean:
            spec_c = "California Piers & Coast"
        else:
            spec_c = "California Coast"
        return {
            "source": "filename_stem",
            "specific_location": spec_c,
            "state_region": "California",
            "country": "United States",
            "hierarchy": f"Places|United States|California|{spec_c}",
            "tags": [spec_c, "California Coast", "California", "Coastline & Piers"] + (["California Piers", "Pier"] if "pier" in fp_clean or "cayucos" in fp_clean or "bolsa" in fp_clean or "avila" in fp_clean else []),
        }

    if "lapush" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "La Push & Olympic Coast",
            "state_region": "Washington",
            "country": "United States",
            "hierarchy": "Places|United States|Washington|Olympic Coast",
            "tags": ["La Push", "Olympic Coast", "Washington", "Pacific Northwest", "Coastline & Piers"],
        }

    if any(tok in fp_clean for tok in ("montanaplains", "greatfalls", "grainsilomontana", "twodot", "2dot")):
        return {
            "source": "filename_stem",
            "specific_location": "Billings & Montana Plains",
            "state_region": "Montana",
            "country": "United States",
            "hierarchy": "Places|United States|Montana|Montana Plains",
            "tags": ["Billings & Montana Plains", "Montana", "Farmland", "Barns & Ranch", "Great Plains"],
        }

    if "bighorn" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Bighorn Mountains",
            "state_region": "Wyoming",
            "country": "United States",
            "hierarchy": "Places|United States|Wyoming|Bighorn Mountains",
            "tags": ["Bighorn Mountains", "Wyoming", "Mountains"],
        }

    if "louisville" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Louisville, Kentucky",
            "state_region": "Kentucky",
            "country": "United States",
            "hierarchy": "Places|United States|Kentucky|Louisville",
            "tags": ["Louisville", "Kentucky", "Urban"],
        }

    if "savannah" in fp_clean or "savannah" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Savannah, Georgia",
            "state_region": "Georgia",
            "country": "United States",
            "hierarchy": "Places|United States|Georgia|Savannah",
            "tags": ["Savannah, Georgia", "Savannah", "Georgia", "Historic Architecture"],
        }

    if "stgeorge" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "St. George & Red Cliffs",
            "state_region": "Utah",
            "country": "United States",
            "hierarchy": "Places|United States|Utah|St. George",
            "tags": ["St. George", "Utah", "Desert", "Red Rock"],
        }

    if any(tok in fp_clean for tok in ("moab", "upheaval", "canyonlands", "deadhorse")):
        return {
            "source": "filename_stem",
            "specific_location": "Canyonlands & Moab",
            "state_region": "Utah",
            "country": "United States",
            "hierarchy": "Places|United States|Utah|Canyonlands & Moab",
            "tags": ["Canyonlands & Moab", "Canyonlands National Park", "Moab", "Utah", "Desert", "Canyon", "Butte"],
        }

    if "tahoe" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Lake Tahoe",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Lake Tahoe",
            "tags": ["Lake Tahoe", "Sierra Nevada", "California", "Mountains", "Lake"],
        }

    if any(tok in fp_clean for tok in ("joshua", "jtree")) or "joshua tree" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Joshua Tree",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Joshua Tree",
            "tags": ["Joshua Tree", "Joshua Tree National Park", "Mojave Desert", "California", "Desert"],
        }

    if sdate == "2014-03-17" and any(tok in fp_clean for tok in ("sunsetbch", "tidalflat")):
        return {
            "source": "filename_stem",
            "specific_location": "Bandon Coast",
            "state_region": "Oregon",
            "country": "United States",
            "hierarchy": "Places|United States|Oregon|Bandon",
            "tags": ["Bandon Coast", "Oregon Coast", "Oregon", "Sea Stacks", "Pacific Northwest"],
        }

    if "huntington_beach" in fp_clean or "huntington beach" in fp_norm:
        return {
            "source": "filename_stem",
            "specific_location": "Huntington Beach",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Huntington Beach",
            "tags": ["Huntington Beach", "California Coast", "California", "Beach"],
        }

    if "dunes" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Desert Sand Dunes",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Landscape|Desert|Sand_Dunes",
            "tags": ["Sand Dunes", "Desert", "Dunes"],
        }

    if "heber" in fp_clean or sdate in ("2004-03-01", "2004-03-02", "2004-03-03"):
        return {
            "source": "filename_stem",
            "specific_location": "Heber Valley",
            "state_region": "Utah",
            "country": "United States",
            "hierarchy": "Places|United States|Utah|Heber Valley",
            "tags": ["Heber Valley", "Utah", "Wasatch Back", "Winter"],
        }

    if any(tok in fp_clean for tok in ("malacon", "malecon", "hotelnational", "backofstatue", "roundarmory", "fort_layered", "viajanite", "fire_boat", "gasstation1")) or (sdate in ("2014-12-11", "2014-12-12", "2014-12-13") and "dsc00096" not in fp_clean):
        return {
            "source": "filename_stem",
            "specific_location": "Havana & Malecón",
            "state_region": "La Habana",
            "country": "Cuba",
            "hierarchy": "Places|Caribbean|Cuba|Havana",
            "tags": ["Havana", "Cuba", "Malecón", "Caribbean", "Colonial Architecture"],
        }

    if any(tok in fp_clean for tok in ("dc_flags", "circle_of_flags")) or orig_spec in ("Washington Monument", "United States Capitol"):
        loc_name = "United States Capitol" if orig_spec == "United States Capitol" else "Washington Monument"
        return {
            "source": "filename_or_landmark",
            "specific_location": loc_name,
            "state_region": "Washington DC",
            "country": "United States",
            "hierarchy": f"Places|United States|Washington DC|{loc_name}",
            "tags": [loc_name, "Washington Monument", "Washington DC", "District of Columbia", "National Mall", "Obelisk", "Monument", "American Flags"],
        }

    if any(tok in fp_clean for tok in ("venice_1", "goingtoschoolinvenice", "venice_artist")) or "venice" in kw_blob:
        return {
            "source": "filename_or_landmark",
            "specific_location": "Venice",
            "state_region": "Veneto",
            "country": "Italy",
            "hierarchy": "Places|Europe|Italy|Venice",
            "tags": ["Venice", "Italy", "Veneto", "Grand Canal", "Venetian Architecture", "Canal", "Europe"],
        }

    if "fishharbor" in fp_clean:
        return None

    if any(tok in fp_clean for tok in ("tripplewf", "backwindowpano")) or "kirkjufell" in orig_spec.lower():
        return {
            "source": "iceland_landmark",
            "specific_location": "Kirkjufell Mountain",
            "state_region": "Snæfellsnes",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland|Kirkjufell",
            "tags": ["Iceland", "Kirkjufell", "Kirkjufellsfoss", "Snæfellsnes", "Waterfall", "Mountain Peak", "Nordic Landscape", "Europe"],
        }

    if any(tok in fp_clean for tok in ("vertwf", "vert_wf")) or "gullfoss" in orig_spec.lower():
        return {
            "source": "iceland_landmark",
            "specific_location": "Gullfoss & Icelandic Waterfalls",
            "state_region": "Suðurland",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland|Gullfoss",
            "tags": ["Iceland", "Gullfoss", "Icelandic Waterfall", "Waterfall", "Basalt Canyon", "Nordic Landscape", "Europe"],
        }

    if "jökulsárlón" in orig_spec.lower() or "jokulsarlon" in orig_spec.lower():
        return {
            "source": "iceland_landmark",
            "specific_location": "Jökulsárlón & Diamond Beach",
            "state_region": "Austurland",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland|Jokulsarlon",
            "tags": ["Iceland", "Jokulsarlon", "Jökulsárlón", "Diamond Beach", "Glacial Lagoon", "Icebergs", "Black Sand Beach", "Europe"],
        }

    if "reynisfjara" in orig_spec.lower():
        return {
            "source": "iceland_landmark",
            "specific_location": "Reynisfjara Black Sand Beach",
            "state_region": "Suðurland",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland|Reynisfjara",
            "tags": ["Iceland", "Reynisfjara", "Reynisdrangar", "Vik", "Black Sand Beach", "Basalt Sea Stacks", "North Atlantic", "Europe"],
        }

    if "reykjav" in orig_spec.lower() or "hallgrimskirkja" in orig_spec.lower() or "hallgrímskirkja" in orig_spec.lower():
        return {
            "source": "iceland_landmark",
            "specific_location": "Hallgrímskirkja & Reykjavík",
            "state_region": "Capital Region",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland|Reykjavik",
            "tags": ["Iceland", "Reykjavik", "Reykjavík", "Hallgrimskirkja", "Hallgrímskirkja", "Nordic Architecture", "Europe"],
        }

    if orig_country == "Iceland" or orig_state == "Iceland":
        return {
            "source": "iceland_country",
            "specific_location": orig_spec if (orig_spec and orig_spec not in ("Unknown", "Canyonlands National Park")) else "Icelandic Highlands & Coast",
            "state_region": "Iceland",
            "country": "Iceland",
            "hierarchy": "Places|Europe|Iceland",
            "tags": ["Iceland", "Nordic Landscape", "Europe"],
        }

    if sdate == "2012-03-09" or any(m in kw_blob for m in ("mexico", "san miguel de allende", "oaxaca", "guanajuato")):
        loc_m = "San Miguel de Allende"
        st_m = "Guanajuato"
        extra_door_tags = []
        if probes and probes.get("lm_colonial_doors_sim", 0.0) >= 0.22:
            extra_door_tags = ["Doors", "Door", "Wooden Door", "Colonial Doors", "Colonial Architecture", "Courtyard"]
        return {
            "source": "mexico_landmark",
            "specific_location": loc_m,
            "state_region": st_m,
            "country": "Mexico",
            "hierarchy": f"Places|North America|Mexico|{loc_m}",
            "tags": ["Mexico", loc_m, st_m, "Colonial Architecture", "Latin America"] + extra_door_tags,
        }

    if any(tok in fp_clean for tok in ("yosemite", "yospano")) or "yosemite" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Yosemite National Park",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Yosemite",
            "tags": ["Yosemite", "Yosemite National Park", "Half Dome", "El Capitan", "Yosemite Valley", "California", "Sierra Nevada"],
        }

    if any(tok in fp_clean for tok in ("bigsur", "big_sur", "pfeiffer")) or "big sur" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Big Sur",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Big Sur",
            "tags": ["Big Sur", "Pfeiffer Beach", "California Coast", "California", "Sea Stacks"],
        }

    if "pescadero" in fp_clean or "pescadero" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Pescadero State Beach",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Pescadero",
            "tags": ["Pescadero", "Pescadero State Beach", "California Coast", "California"],
        }

    if any(tok in fp_clean for tok in ("consumnes", "cosumnes")) or "cosumnes" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Cosumnes River Preserve",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Cosumnes River Preserve",
            "tags": ["Cosumnes River Preserve", "Central Valley", "California", "Wetlands"],
        }

    if any(tok in fp_clean for tok in ("alabama", "alabamahills", "lonepine")) or "alabama hills" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Alabama Hills",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Alabama Hills",
            "tags": ["Alabama Hills", "Lone Pine", "Mount Whitney", "Eastern Sierra", "Highway 395", "California", "Sierra Nevada"],
        }

    if any(tok in fp_clean for tok in ("mono_", "monolake", "tufa", "leevining", "grantlake")) or "mono lake" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Mono Lake",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Mono Lake",
            "tags": ["Mono Lake", "Tufa Towers", "Eastern Sierra", "Highway 395", "California", "Sierra Nevada"],
        }

    if any(tok in fp_clean for tok in ("whitney", "395")) or "395" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Eastern Sierra & Highway 395",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Eastern Sierra",
            "tags": ["Eastern Sierra", "Highway 395", "Mount Whitney", "Sierra Nevada", "California"],
        }

    if any(tok in fp_clean for tok in ("zabriski", "zabrinksi", "deathv", "dthvly", "dvpano", "dv_dunes", "dv_stdy")) or "death valley" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Death Valley National Park",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Death Valley",
            "tags": ["Death Valley", "Death Valley National Park", "Zabriskie Point", "Mesquite Flat Sand Dunes", "California"],
        }

    if "rhyolite" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Rhyolite Ghost Town",
            "state_region": "Nevada",
            "country": "United States",
            "hierarchy": "Places|United States|Nevada|Rhyolite",
            "tags": ["Rhyolite", "Ghost Town", "Nevada", "Amargosa Desert"],
        }

    if any(tok in fp_clean for tok in ("anzabor", "borrego", "anzapan")) or "borrego" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Anza-Borrego Desert",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Anza-Borrego",
            "tags": ["Anza-Borrego Desert", "Borrego Springs", "California", "Sonoran Desert"],
        }

    if any(tok in fp_clean for tok in ("palm_springs", "palmsprings")):
        return {
            "source": "filename_stem",
            "specific_location": "Palm Springs",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Palm Springs",
            "tags": ["Palm Springs", "Coachella Valley", "California"],
        }

    if any(tok in fp_clean for tok in ("grand_canyon", "grandcanyon", "gc_newpict")) or "grand canyon" in fp_norm or "grand canyon" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Grand Canyon National Park",
            "state_region": "Arizona",
            "country": "United States",
            "hierarchy": "Places|United States|Arizona|Grand Canyon",
            "tags": ["Grand Canyon", "Grand Canyon National Park", "Arizona", "Colorado River", "Canyon", "Butte"],
        }

    if "greenriver" in fp_clean:
        return {
            "source": "filename_stem",
            "specific_location": "Green River Overlook, Canyonlands",
            "state_region": "Utah",
            "country": "United States",
            "hierarchy": "Places|United States|Utah|Canyonlands|Green River Overlook",
            "tags": ["Green River Overlook", "Canyonlands National Park", "Utah", "Butte", "Buttes"],
        }

    if "whitesands" in fp_clean or "white sands" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "White Sands National Park",
            "state_region": "New Mexico",
            "country": "United States",
            "hierarchy": "Places|United States|New Mexico|White Sands",
            "tags": ["White Sands", "White Sands National Park", "Gypsum Dunes", "New Mexico"],
        }

    if "bosque" in fp_clean or "bosque" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Bosque del Apache",
            "state_region": "New Mexico",
            "country": "United States",
            "hierarchy": "Places|United States|New Mexico|Bosque del Apache",
            "tags": ["Bosque del Apache", "New Mexico", "Wetlands", "Wildlife Refuge"],
        }

    if "santafe" in fp_clean or "santa fe" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Santa Fe",
            "state_region": "New Mexico",
            "country": "United States",
            "hierarchy": "Places|United States|New Mexico|Santa Fe",
            "tags": ["Santa Fe", "New Mexico", "Adobe Architecture", "Southwest"],
        }

    if any(tok in fp_clean for tok in ("bandon", "coosbay")) or "bandon" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Bandon Coast",
            "state_region": "Oregon",
            "country": "United States",
            "hierarchy": "Places|United States|Oregon|Bandon",
            "tags": ["Bandon", "Oregon Coast", "Oregon", "Sea Stacks", "Pacific Northwest"],
        }

    if "chicago" in fp_clean or "chicago" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Chicago",
            "state_region": "Illinois",
            "country": "United States",
            "hierarchy": "Places|United States|Illinois|Chicago",
            "tags": ["Chicago", "Chicago Skyline", "Illinois", "Lake Michigan", "Cityscape"],
        }

    if any(tok in fp_clean for tok in ("abbeville", "abberville")):
        return {
            "source": "filename_stem",
            "specific_location": "Abbeville Cypress Swamp",
            "state_region": "Louisiana",
            "country": "United States",
            "hierarchy": "Places|United States|Louisiana|Abbeville",
            "tags": ["Abbeville", "Louisiana", "Atchafalaya Basin", "Cypress Swamp", "Bayou"],
        }

    if "houma" in fp_clean or "houma" in kw_blob or any(tok in kw_blob for tok in ("louisiana", "lousiana", "louisana")):
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Houma & Louisiana Bayous",
            "state_region": "Louisiana",
            "country": "United States",
            "hierarchy": "Places|United States|Louisiana|Houma",
            "tags": ["Houma", "Louisiana", "Bayou", "Cypress Swamp", "Wetlands"],
        }

    if any(tok in fp_clean for tok in ("everglades", "tamiami")) or "everglades" in kw_blob:
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Everglades National Park",
            "state_region": "Florida",
            "country": "United States",
            "hierarchy": "Places|United States|Florida|Everglades",
            "tags": ["Everglades", "Everglades National Park", "Florida", "Wetlands"],
        }

    if any(tok in fp_clean for tok in ("yankton", "south_dakota")):
        return {
            "source": "filename_stem",
            "specific_location": "Yankton",
            "state_region": "South Dakota",
            "country": "United States",
            "hierarchy": "Places|United States|South Dakota|Yankton",
            "tags": ["Yankton", "South Dakota", "Great Plains", "Rural"],
        }

    if any(tok in fp_clean for tok in ("mocasin", "moccasin")):
        return {
            "source": "filename_stem",
            "specific_location": "Moccasin",
            "state_region": "Montana",
            "country": "United States",
            "hierarchy": "Places|United States|Montana|Moccasin",
            "tags": ["Moccasin", "Montana", "Judith Basin", "Barn", "Homestead"],
        }

    if "billings" in kw_blob:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Billings & Yellowstone Valley",
            "state_region": "Montana",
            "country": "United States",
            "hierarchy": "Places|United States|Montana|Billings",
            "tags": ["Billings", "Montana"],
        }

    if any(tok in fp_clean for tok in ("parthenon", "nashville")):
        return {
            "source": "filename_stem",
            "specific_location": "Nashville Parthenon",
            "state_region": "Tennessee",
            "country": "United States",
            "hierarchy": "Places|United States|Tennessee|Nashville|Parthenon",
            "tags": ["Nashville Parthenon", "Nashville", "Tennessee", "Classical Architecture"],
        }

    if any(tok in fp_clean for tok in ("brighton", "cheltenham")) or ("england" in kw_blob and sdate not in ("2009-09-28", "2009-10-01")):
        return {
            "source": "filename_or_lrcat",
            "specific_location": "Brighton & Southern England",
            "state_region": "England",
            "country": "United Kingdom",
            "hierarchy": "Places|Europe|United Kingdom|England|Brighton",
            "tags": ["Brighton", "England", "United Kingdom", "Europe"],
        }

    if any(tok in fp_clean for tok in ("milfordsound", "auckland", "aukcty", "nzlonghike")) or orig_country == "New Zealand":
        return {
            "source": "filename_or_country",
            "specific_location": "Milford Sound & South Island" if "milford" in fp_clean else "New Zealand",
            "state_region": "Southland",
            "country": "New Zealand",
            "hierarchy": "Places|Oceania|New Zealand|Fiordland",
            "tags": ["New Zealand", "Milford Sound", "Fiordland", "South Island", "Oceania"],
        }

    if "tucson" in kw_blob or "saguaro" in fp_clean:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Tucson & Sonoran Desert",
            "state_region": "Arizona",
            "country": "United States",
            "hierarchy": "Places|United States|Arizona|Tucson",
            "tags": ["Tucson", "Sonoran Desert", "Saguaro", "Arizona"],
        }

    if "denver" in kw_blob or "redrocks" in fp_clean or "red_rocks" in fp_clean:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Denver & Front Range",
            "state_region": "Colorado",
            "country": "United States",
            "hierarchy": "Places|United States|Colorado|Denver",
            "tags": ["Denver", "Colorado", "Front Range", "Red Rocks"],
        }

    if "carolinas" in kw_blob or "tripeast" in fp_clean:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Carolinas & Blue Ridge",
            "state_region": "North Carolina",
            "country": "United States",
            "hierarchy": "Places|United States|North Carolina|Carolinas",
            "tags": ["Carolinas", "North Carolina", "South Carolina", "Appalachians"],
        }

    if "palouse" in kw_blob or "steptoe" in fp_clean:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Palouse",
            "state_region": "Washington",
            "country": "United States",
            "hierarchy": "Places|United States|Washington|Palouse",
            "tags": ["Palouse", "Steptoe Butte", "Washington", "Rolling Hills", "Butte"],
        }

    if "taft" in kw_blob:
        return {
            "source": "lrcat_keyword",
            "specific_location": "Taft Oil Field",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Places|United States|California|Taft Oil Field",
            "tags": ["Taft Oil Field", "San Joaquin Valley", "California", "Oil Field", "Oil Fields & Industrial"],
        }

    # Explicit US State / Country keyword in .lrcat (e.g., "Arizona" on MorningRoad_1h_tm or test_1354)
    _EXPLICIT_LRCAT_STATES = {
        "arizona": "Arizona",
        "utah": "Utah",
        "wyoming": "Wyoming",
        "montana": "Montana",
        "california": "California",
        "colorado": "Colorado",
        "new mexico": "New Mexico",
        "washington": "Washington",
        "oregon": "Oregon",
        "florida": "Florida",
        "louisiana": "Louisiana",
        "nevada": "Nevada",
        "nebraska": "Nebraska",
        "illinois": "Illinois",
        "tennessee": "Tennessee",
        "georgia": "Georgia",
        "kentucky": "Kentucky",
        "north carolina": "North Carolina",
        "south carolina": "South Carolina",
        "south dakota": "South Dakota",
    }
    lrcat_low_tokens = {k.lower().replace("_", " ").strip() for k in lrcat_kws}
    for st_key, st_canon in _EXPLICIT_LRCAT_STATES.items():
        if st_key in lrcat_low_tokens and st_key not in negated_low:
            return {
                "source": "lrcat_keyword",
                "specific_location": st_canon,
                "state_region": st_canon,
                "country": "United States",
                "hierarchy": f"Places|United States|{st_canon}",
                "tags": [st_canon],
            }

    is_la_highway = (
        any("los_angeles" in str(k).lower() or "los angeles" in str(k).lower() for k in lrcat_kws + exist_kws)
        or (
            sdate == "2012-03-16"
            and (
                "freeway_interchange" in str(record.get("sub_category") or "").lower()
                or bool(probes and probes.get("lm_highway_interchange_sim", 0.0) >= 0.255)
            )
        )
    )
    if is_la_highway:
        return {
            "source": "filename_stem",
            "specific_location": "Los Angeles Freeway Interchange",
            "state_region": "California",
            "country": "United States",
            "hierarchy": "Architecture|Infrastructure|Highway_Interchange",
            "tags": ["Bridges & Freeways", "Highway Interchange", "Overpass", "Freeway", "Urban", "Los Angeles", "California"],
        }

    return None


def propagate_shoot_day_geography(
    rows: List[Dict[str, Any]],
    probes_map: Dict[str, Dict[str, Any]],
    vectors: Optional[np.ndarray] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Two-Stage Geographic Resolver with Tightened Consensus & Cosine Similarity Gate:
    1. Resolves deterministic filename/lrcat/landmark anchors per photo (`decode_shorthand_geography`).
    2. Propagates verified Shoot-Day & Coherent Expedition Geography ONLY when:
       - Not a composite print-export date (`2011-12-09`, `2011-12-15`, `2012-03-16`), AND
       - At least 2+ photos (and >= 35% of the day's frames) confirm the location OR it comes from an explicit .lrcat keyword, AND
       - The receiving sibling photo has OpenCLIP cosine similarity >= 0.72 to an anchor photo from that date
         (or is part of the verified 2016-06-10..2016-06-17 Iceland expedition / 2012-03-09 San Miguel de Allende shoot).
    """
    COMPOSITE_EXPORT_DATES = {"2011-12-09", "2011-12-15", "2012-03-16"}
    resolved_by_fp: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        fp = r["file_path"]
        if str(r.get("location_provenance") or "").strip() == "user_cleared":
            continue
        probes = probes_map.get(fp, {})
        direct = decode_shorthand_geography(r, probes=probes)
        if direct is not None:
            neg_low = {k.lower().strip() for k in _safe_json_list(r.get("negated_tags")) if k.strip()}
            if neg_low:
                cand_locs = {
                    str(direct.get("country") or "").lower().strip(),
                    str(direct.get("state_region") or "").lower().strip(),
                    str(direct.get("specific_location") or "").lower().strip(),
                } - {""}
                if cand_locs & neg_low:
                    direct = None
            if direct is not None:
                resolved_by_fp[fp] = direct

    # Helper to compute normalized vector for a row
    def _row_vec(rec: Dict[str, Any]) -> Optional[np.ndarray]:
        if vectors is None:
            return None
        v_idx = rec.get("vector_index")
        if v_idx is None or int(v_idx) < 0 or int(v_idx) >= vectors.shape[0]:
            return None
        v = vectors[int(v_idx)].astype(np.float32)
        n = float(np.linalg.norm(v))
        return (v / n) if n > 1e-6 else None

    # Group dated photos by shoot_date
    by_date: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        sd = str(r.get("shoot_date") or "Undated")
        if sd != "Undated":
            by_date.setdefault(sd, []).append(r)

    sorted_dates = sorted(by_date.keys())
    date_macro_override: Dict[str, Dict[str, Any]] = {}
    date_anchor_vecs: Dict[str, List[np.ndarray]] = {}

    # Check each date's dominant verified anchor (requiring >= 2 photos and >= 35% of day's frames, or lrcat keyword)
    for sd in sorted_dates:
        if sd in COMPOSITE_EXPORT_DATES:
            continue
        day_rows = by_date[sd]
        anchored_pairs = [(r, resolved_by_fp[r["file_path"]]) for r in day_rows if r["file_path"] in resolved_by_fp]
        if not anchored_pairs:
            continue

        # Count consensus by (country, state_region, specific_location)
        loc_counts: Dict[Tuple[str, Optional[str], str], List[Tuple[Dict[str, Any], Dict[str, Any]]]] = {}
        for r_item, a_item in anchored_pairs:
            # Never propagate a freeway interchange anchor to non-freeway photos on the same date
            if a_item.get("hierarchy") == "Architecture|Infrastructure|Highway_Interchange":
                continue
            key = (str(a_item.get("country") or ""), a_item.get("state_region"), str(a_item.get("specific_location") or ""))
            loc_counts.setdefault(key, []).append((r_item, a_item))

        if not loc_counts:
            continue

        best_key, best_group = max(loc_counts.items(), key=lambda kv: len(kv[1]))
        count_anchored = len(best_group)
        frac_anchored = count_anchored / max(1, len(day_rows))
        has_lrcat_source = any("lrcat" in str(a.get("source") or "") or a.get("source") == "gps_ground_truth" for _, a in best_group)
        is_iceland_date = best_key[0] == "Iceland" or ("2016-06-10" <= sd <= "2016-06-17")

        if (count_anchored >= 2 and frac_anchored >= 0.35) or has_lrcat_source or is_iceland_date:
            date_macro_override[sd] = best_group[0][1]
            vecs_list = []
            for r_item, _ in best_group:
                rv = _row_vec(r_item)
                if rv is not None:
                    vecs_list.append(rv)
            date_anchor_vecs[sd] = vecs_list

    # Bridge 1-2 day gaps ONLY inside the verified 2016-06-10..2016-06-17 Iceland expedition
    for sd in sorted_dates:
        if "2016-06-10" <= sd <= "2016-06-17" and sd not in date_macro_override:
            date_macro_override[sd] = {
                "source": "shoot_day_iceland",
                "specific_location": "Icelandic Highlands & Coast",
                "state_region": "Iceland",
                "country": "Iceland",
                "hierarchy": "Places|Europe|Iceland",
                "tags": ["Iceland", "Nordic Landscape", "Europe"],
            }

    # Propagate shoot-day macro geography to unanchored sibling frames on that date
    for sd, day_rows in by_date.items():
        macro = date_macro_override.get(sd)
        if not macro:
            continue
        anchor_vecs = date_anchor_vecs.get(sd, [])

        for r in day_rows:
            fp = r["file_path"]
            if str(r.get("location_provenance") or "").strip() == "user_cleared":
                continue
            probes = probes_map.get(fp, {})
            existing_res = resolved_by_fp.get(fp)
            neg_low = {k.lower().strip() for k in _safe_json_list(r.get("negated_tags")) if k.strip()}

            # Never propagate outdoor shoot-day geography onto screenshots
            if int(r.get("is_screenshot") or 0) == 1:
                continue

            # Never override user-taught geography, GPS ground truth, explicit .lrcat keywords, or explicit filename_stem rules
            if existing_res and existing_res.get("source") in ("user_taught", "filename_stem", "gps_ground_truth", "lrcat_keyword", "filename_or_lrcat"):
                continue

            # Never propagate a shoot-day location that has been explicitly negated on this record
            if neg_low:
                macro_locs = {
                    str(macro.get("country") or "").lower().strip(),
                    str(macro.get("state_region") or "").lower().strip(),
                    str(macro.get("specific_location") or "").lower().strip(),
                } - {""}
                if macro_locs & neg_low:
                    continue

            if macro["country"] == "Iceland":
                # Refine Icelandic sub-landmark using OpenCLIP landmark probes + filename stems
                fp_low = Path(fp).stem.lower()
                if "fishharbor" in fp_low:
                    continue
                if "tripplewf" in fp_low or "backwindow" in fp_low or probes.get("lm_kirkjufell_sim", 0.0) >= 0.27:
                    resolved_by_fp[fp] = dict(GLOBAL_LANDMARK_GAZETTEER["iceland_kirkjufell"], source="shoot_day_iceland")
                elif "vertwf" in fp_low or "vert_wf" in fp_low or "3037" in fp_low or "3072" in fp_low or probes.get("lm_gullfoss_sim", 0.0) >= 0.26:
                    resolved_by_fp[fp] = dict(GLOBAL_LANDMARK_GAZETTEER["iceland_gullfoss"], source="shoot_day_iceland")
                elif any(x in fp_low for x in ("2756", "2796", "2798", "2805", "2806")) or probes.get("lm_jokulsarlon_sim", 0.0) >= 0.26:
                    resolved_by_fp[fp] = dict(GLOBAL_LANDMARK_GAZETTEER["iceland_jokulsarlon"], source="shoot_day_iceland")
                elif "3150" in fp_low or "3151" in fp_low or probes.get("lm_hallgrimskirkja_sim", 0.0) >= 0.25:
                    resolved_by_fp[fp] = dict(GLOBAL_LANDMARK_GAZETTEER["iceland_hallgrimskirkja"], source="shoot_day_iceland")
                elif "2671" in fp_low or "vertpano5" in fp_low or probes.get("lm_reynisfjara_sim", 0.0) >= 0.26:
                    resolved_by_fp[fp] = dict(GLOBAL_LANDMARK_GAZETTEER["iceland_reynisfjara"], source="shoot_day_iceland")
                else:
                    resolved_by_fp[fp] = {
                        "source": "shoot_day_iceland",
                        "specific_location": existing_res["specific_location"] if (existing_res and existing_res["country"] == "Iceland") else "Icelandic Highlands & Coast",
                        "state_region": "Iceland",
                        "country": "Iceland",
                        "hierarchy": "Places|Europe|Iceland",
                        "tags": ["Iceland", "Nordic Landscape", "Europe"],
                    }
            elif macro["country"] == "Mexico" and sd == "2012-03-09":
                door_tags = []
                if probes.get("lm_colonial_doors_sim", 0.0) >= 0.22:
                    door_tags = ["Doors", "Door", "Wooden Door", "Colonial Doors", "Colonial Architecture", "Courtyard"]
                base_loc = existing_res["specific_location"] if (existing_res and existing_res["country"] == "Mexico") else macro["specific_location"]
                base_st = existing_res["state_region"] if (existing_res and existing_res["country"] == "Mexico") else macro["state_region"]
                resolved_by_fp[fp] = {
                    "source": "shoot_day_mexico",
                    "specific_location": base_loc,
                    "state_region": base_st,
                    "country": "Mexico",
                    "hierarchy": f"Places|North America|Mexico|{base_loc}",
                    "tags": list(dict.fromkeys(["Mexico", base_loc, base_st, "Colonial Architecture", "Latin America"] + door_tags)),
                }
            elif existing_res is None:
                # Require OpenCLIP cosine similarity >= 0.72 to at least one anchor photo on that date
                rv = _row_vec(r)
                max_sim = 0.0
                if rv is not None and anchor_vecs:
                    max_sim = max(float(np.dot(rv, av)) for av in anchor_vecs)
                if max_sim >= 0.72:
                    resolved_by_fp[fp] = {
                        "source": "shoot_day_propagated",
                        "specific_location": macro["specific_location"],
                        "state_region": macro["state_region"],
                        "country": macro["country"],
                        "hierarchy": macro["hierarchy"],
                        "tags": list(macro["tags"]),
                    }

    # Extreme-confidence World Landmark fallback ONLY when unmistakable (best_sim >= 0.315 and margin >= 0.035)
    for r in rows:
        fp = r["file_path"]
        if fp in resolved_by_fp or str(r.get("location_provenance") or "").strip() == "user_cleared":
            continue
        probes = probes_map.get(fp, {})
        lm_ranked = sorted(
            (
                (float(probes.get(f"{entry['probe_key']}_sim", 0.0)), lm_id, entry)
                for lm_id, entry in GLOBAL_LANDMARK_GAZETTEER.items()
                if lm_id not in ("venice_italy", "colonial_doors_mexico")
            ),
            key=lambda x: x[0],
            reverse=True,
        )
        if lm_ranked:
            best_sim, best_id, best_entry = lm_ranked[0]
            second_sim = lm_ranked[1][0] if len(lm_ranked) > 1 else 0.0
            if best_sim >= 0.315 and (best_sim - second_sim) >= 0.035:
                resolved_by_fp[fp] = dict(best_entry, source="clip_landmark_gazetteer")

    return resolved_by_fp


def load_vector_concept_boundaries(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Loads active user-taught visual concept boundary corrections (`old_label -> new_label` + 768-d embedding)
    from `vector_concept_boundaries` so visually similar vectors penalize `old_label` and boost `new_label`.
    """
    boundaries: List[Dict[str, Any]] = []
    try:
        conn = get_db_connection(db_path)
        rows = conn.execute(
            "SELECT id, old_label, new_label, vector_blob, weight FROM vector_concept_boundaries"
        ).fetchall()
        conn.close()
        for r in rows:
            blob = r["vector_blob"]
            if not blob:
                continue
            if len(blob) == 768 * 4:
                arr = np.frombuffer(blob, dtype=np.float32).copy()
            elif len(blob) == 768 * 2:
                arr = np.frombuffer(blob, dtype=np.float16).astype(np.float32)
            else:
                continue
            norm = float(np.linalg.norm(arr))
            if norm > 1e-6 and arr.shape[0] == 768:
                boundaries.append({
                    "id": r["id"],
                    "old_label": str(r["old_label"] or "").strip(),
                    "old_low": str(r["old_label"] or "").strip().lower(),
                    "new_label": str(r["new_label"] or "").strip(),
                    "new_low": str(r["new_label"] or "").strip().lower(),
                    "vec": arr / norm,
                    "weight": float(r["weight"] or 1.0),
                })
    except Exception as exc:
        logging.debug(f"load_vector_concept_boundaries skipped: {exc}")
    return boundaries


def localize_verified_subject_boxes(
    record: Dict[str, Any],
    verified_subjects: List[Dict[str, Any]],
    plural_hints: Optional[Dict[str, bool]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Fast local spatial subject bounding-box localizer (< 3ms per photo with verified subjects):
    Computes normalized [x1, y1, x2, y2] subject regions and instance counts (`subject_counts`)
    from the thumbnail/preview image using multi-scale gradient + center-weighted contrast saliency,
    while preserving any user-reclassified boxes on the record.
    """
    if not verified_subjects:
        return [], {}

    plural_hints = plural_hints or {}
    existing_boxes_raw = _safe_json_list(record.get("subject_boxes"))
    preserved_user_boxes: List[Dict[str, Any]] = []
    for eb in existing_boxes_raw:
        if isinstance(eb, dict) and eb.get("source") == "user_reclassified":
            preserved_user_boxes.append(eb)

    img_path_str = str(record.get("thumb_360_path") or record.get("preview_1600_path") or "").strip()
    candidate_regions: List[List[float]] = []

    if img_path_str and Path(img_path_str).exists():
        try:
            with Image.open(img_path_str) as im:
                im_rgb = im.convert("RGB").resize((64, 64), Image.Resampling.BILINEAR)
                arr = np.asarray(im_rgb, dtype=np.float32) / 255.0
                # Compute local gradient energy + color contrast from border mean
                gx = np.abs(np.diff(arr, axis=1, prepend=arr[:, :1, :])).mean(axis=2)
                gy = np.abs(np.diff(arr, axis=0, prepend=arr[:1, :, :])).mean(axis=2)
                border_pixels = np.concatenate([arr[0, :, :], arr[-1, :, :], arr[:, 0, :], arr[:, -1, :]], axis=0)
                border_mean = border_pixels.mean(axis=0)
                color_diff = np.linalg.norm(arr - border_mean, axis=2)

                yy, xx = np.mgrid[0:64, 0:64]
                center_prior = np.exp(-(((xx - 31.5) / 26.0) ** 2 + ((yy - 31.5) / 26.0) ** 2))
                sal = (0.55 * (gx + gy) + 0.45 * color_diff) * (0.45 + 0.55 * center_prior)

                # Smooth saliency with a 5x5 box filter via cumulative sums
                sal_pad = np.pad(sal, 2, mode="edge")
                sal_smooth = (
                    sal_pad[0:64, 0:64] + sal_pad[2:66, 2:66] + sal_pad[4:68, 4:68]
                    + sal_pad[0:64, 4:68] + sal_pad[4:68, 0:64]
                ) / 5.0

                thresh = float(np.percentile(sal_smooth, 82))
                mask = sal_smooth >= max(thresh, 1e-4)
                ys, xs = np.where(mask)
                if len(xs) >= 6:
                    # Check if mask splits into 2 distinct horizontal clusters (e.g. multiple subjects)
                    x_min, x_max = int(xs.min()), int(xs.max())
                    y_min, y_max = int(ys.min()), int(ys.max())
                    x_span = x_max - x_min
                    if x_span >= 26:
                        mid_x = (x_min + x_max) // 2
                        mid_col_mass = int(mask[:, max(0, mid_x - 2):min(64, mid_x + 3)].sum())
                        left_mask = mask[:, :mid_x]
                        right_mask = mask[:, mid_x:]
                        if mid_col_mass <= 4 and left_mask.sum() >= 8 and right_mask.sum() >= 8:
                            ly, lx = np.where(left_mask)
                            ry, rx = np.where(right_mask)
                            candidate_regions.append([
                                round(max(0.04, (lx.min() - 2) / 64.0), 3),
                                round(max(0.04, (ly.min() - 2) / 64.0), 3),
                                round(min(0.96, (lx.max() + 3) / 64.0), 3),
                                round(min(0.96, (ly.max() + 3) / 64.0), 3),
                            ])
                            candidate_regions.append([
                                round(max(0.04, (rx.min() + mid_x - 2) / 64.0), 3),
                                round(max(0.04, (ry.min() - 2) / 64.0), 3),
                                round(min(0.96, (rx.max() + mid_x + 3) / 64.0), 3),
                                round(min(0.96, (ry.max() + 3) / 64.0), 3),
                            ])
                    if not candidate_regions:
                        candidate_regions.append([
                            round(max(0.05, (x_min - 3) / 64.0), 3),
                            round(max(0.05, (y_min - 3) / 64.0), 3),
                            round(min(0.95, (x_max + 4) / 64.0), 3),
                            round(min(0.95, (y_max + 4) / 64.0), 3),
                        ])
        except Exception:
            pass

    if not candidate_regions:
        candidate_regions = [[0.22, 0.20, 0.78, 0.82]]

    boxes_out: List[Dict[str, Any]] = list(preserved_user_boxes)
    subject_counts: Dict[str, int] = {}

    for idx_vs, vs in enumerate(verified_subjects):
        lbl = str(vs.get("label") or "").strip()
        if not lbl:
            continue
        lbl_low = lbl.lower()
        conf = round(float(vs.get("confidence") or 0.85), 3)
        margin = round(float(vs.get("margin") or 0.05), 3)
        explicit_bbox = vs.get("bbox")

        if isinstance(explicit_bbox, list) and len(explicit_bbox) == 4:
            subject_counts[lbl_low] = subject_counts.get(lbl_low, 0) + 1
            boxes_out.append({
                "id": f"subj_{lbl_low}_{subject_counts[lbl_low]}",
                "label": lbl,
                "confidence": conf,
                "margin": margin,
                "bbox": [round(float(x), 3) for x in explicit_bbox],
                "source": vs.get("source") or "multiregion_detector",
            })
            continue

        is_plural = bool(plural_hints.get(lbl_low, False)) or len(candidate_regions) > 1
        cnt = max(2, len(candidate_regions)) if is_plural else 1
        subject_counts[lbl_low] = cnt

        if is_plural and len(candidate_regions) >= 2:
            for r_idx, bbox in enumerate(candidate_regions[:3]):
                boxes_out.append({
                    "id": f"subj_{lbl_low}_{r_idx + 1}",
                    "label": lbl,
                    "confidence": conf,
                    "margin": margin,
                    "bbox": bbox,
                    "source": vs.get("source") or "contrastive_gate",
                })
        else:
            bbox = candidate_regions[idx_vs % len(candidate_regions)]
            boxes_out.append({
                "id": f"subj_{lbl_low}_1",
                "label": lbl,
                "confidence": conf,
                "margin": margin,
                "bbox": bbox,
                "source": vs.get("source") or "contrastive_gate",
            })

    return boxes_out, subject_counts


_OPENCLIP_PROBE_MODEL_CACHE: Dict[str, Any] = {}
_MULTIREGION_CROP_CACHE_PATH = DEFAULT_DB_PATH.parent / "multiregion_crop_sims_v1.json"
_MULTIREGION_CROP_MEM_CACHE: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None

_MULTIREGION_BOX_SPECS: Dict[str, List[float]] = {
    "upper_left": [0.15, 0.08, 0.58, 0.58],
    "upper_right": [0.42, 0.06, 0.94, 0.58],
    "lower_left": [0.06, 0.42, 0.58, 0.96],
    "lower_right": [0.42, 0.45, 0.98, 0.98],
    "center": [0.18, 0.14, 0.82, 0.88],
    "upper_sky": [0.05, 0.02, 0.95, 0.38],
}

_MULTIREGION_PROBE_KEYS = (
    "dog", "dog_indoor", "cat", "cat_indoor", "cat_tree", "living_room", "framed_art",
    "mirror_selfie", "fitting_room", "person", "person_2", "male", "female",
    "car_vehicle", "sports_car_sedan", "gas_station",
    "light_night_artificial", "light_daylight_midday",
    "foil_empty_room_carpet", "foil_framed_picture_wall", "foil_statue_sculpture",
)


def _get_openclip_probe_singleton():
    if "model" not in _OPENCLIP_PROBE_MODEL_CACHE:
        import open_clip
        from stage1_engine import detect_hardware_profile

        hw = detect_hardware_profile()
        dev = hw["device"]
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14-quickgelu", pretrained="openai", device=dev
        )
        model.eval()
        tok = open_clip.get_tokenizer("ViT-L-14-quickgelu")
        _OPENCLIP_PROBE_MODEL_CACHE["model"] = model
        _OPENCLIP_PROBE_MODEL_CACHE["preprocess"] = preprocess
        _OPENCLIP_PROBE_MODEL_CACHE["tokenizer"] = tok
        _OPENCLIP_PROBE_MODEL_CACHE["device"] = dev
    return _OPENCLIP_PROBE_MODEL_CACHE


def _compute_multiregion_crop_sims_for_candidates(
    candidate_rows: List[Dict[str, Any]],
    key_to_vec: Dict[str, np.ndarray],
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Evaluates 6 spatial sub-regions per image using OpenCLIP ViT-L-14-quickgelu so multiple
    distinct subjects in different parts of the frame (e.g. a dog on the lower-right rug AND
    a cat on the upper-left cat tree, or a gas station canopy above a sports car at night)
    are independently detected with regional bounding boxes. Cached on disk by file_hash.
    """
    global _MULTIREGION_CROP_MEM_CACHE
    if _MULTIREGION_CROP_MEM_CACHE is None:
        if _MULTIREGION_CROP_CACHE_PATH.exists():
            try:
                _MULTIREGION_CROP_MEM_CACHE = json.loads(_MULTIREGION_CROP_CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                _MULTIREGION_CROP_MEM_CACHE = {}
        else:
            _MULTIREGION_CROP_MEM_CACHE = {}

    active_keys = [k for k in _MULTIREGION_PROBE_KEYS if k in key_to_vec]
    if not active_keys or not candidate_rows:
        return {}

    results_by_fp: Dict[str, Dict[str, Dict[str, float]]] = {}
    missing_rows: List[Tuple[str, str, Path]] = []

    for r in candidate_rows:
        fp = r["file_path"]
        fhash = str(r.get("file_hash") or "").strip()
        if not fhash:
            continue
        cached = _MULTIREGION_CROP_MEM_CACHE.get(fhash)
        if cached and all(rn in cached for rn in _MULTIREGION_BOX_SPECS):
            results_by_fp[fp] = cached
            continue
        prev_p = DEFAULT_PREVIEWS_1600_DIR / f"{fhash}.webp"
        img_p = prev_p if prev_p.exists() else Path(fp)
        if img_p.exists():
            missing_rows.append((fp, fhash, img_p))

    if len(candidate_rows) > 500 and len(missing_rows) > 500:
        missing_rows = missing_rows[:500]

    if missing_rows:
        try:
            import torch
            from PIL import Image

            ctx = _get_openclip_probe_singleton()
            model = ctx["model"]
            preprocess = ctx["preprocess"]
            dev = ctx["device"]
            text_mat = np.stack([key_to_vec[k] for k in active_keys], axis=0).astype(np.float32)  # (K, D)

            batch_size_imgs = 16
            dirty = False
            for start_i in range(0, len(missing_rows), batch_size_imgs):
                chunk = missing_rows[start_i : start_i + batch_size_imgs]
                tensors_list = []
                meta_index: List[Tuple[str, str, str]] = []
                for fp, fhash, img_p in chunk:
                    try:
                        with Image.open(img_p) as im:
                            im_rgb = im.convert("RGB")
                            w, h = im_rgb.size
                            for reg_name, (x0, y0, x1, y1) in _MULTIREGION_BOX_SPECS.items():
                                crop_im = im_rgb.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1)))
                                tensors_list.append(preprocess(crop_im))
                                meta_index.append((fp, fhash, reg_name))
                    except Exception:
                        continue
                if not tensors_list:
                    continue
                with torch.no_grad():
                    batch_t = torch.stack(tensors_list).to(dev)
                    img_feats = model.encode_image(batch_t)
                    img_feats = img_feats / img_feats.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                    feats_np = img_feats.cpu().numpy().astype(np.float32)  # (N_crops, D)
                sims_mat = np.dot(feats_np, text_mat.T)  # (N_crops, K)
                for row_i, (fp, fhash, reg_name) in enumerate(meta_index):
                    reg_dict = {active_keys[k_i]: round(float(sims_mat[row_i, k_i]), 4) for k_i in range(len(active_keys))}
                    _MULTIREGION_CROP_MEM_CACHE.setdefault(fhash, {})[reg_name] = reg_dict
                    results_by_fp.setdefault(fp, {})[reg_name] = reg_dict
                dirty = True

            if dirty:
                try:
                    _MULTIREGION_CROP_CACHE_PATH.write_text(json.dumps(_MULTIREGION_CROP_MEM_CACHE), encoding="utf-8")
                except Exception:
                    pass
        except Exception as e:
            logging.warning(f"Multi-region crop detector skipped: {e}")

    return results_by_fp


def compute_clip_concept_probes_for_rows(
    rows: List[Dict[str, Any]],
    vectors: np.ndarray,
    encode_text_batch_fn: Optional[Callable[[List[str]], Dict[str, np.ndarray]]] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> Dict[str, Dict[str, Any]]:
    """
    Computes vectorized OpenCLIP zero-shot perspective, Top-Level Scene Context Router,
    Context-Scoped Contrastive Habitat/Artifact Foil gates, Multi-Region Spatial Subject
    Detection, active vector boundary adjustments, and spatial subject boxes across a batch of photo records.
    Returns { file_path: probe_dict }.
    """
    if encode_text_batch_fn is None:
        try:
            import torch

            ctx = _get_openclip_probe_singleton()
            model = ctx["model"]
            tok = ctx["tokenizer"]
            dev = ctx["device"]
            prompts_list = list(CONCEPT_PROBE_PROMPTS.values())
            with torch.no_grad():
                tokens = tok(prompts_list).to(dev)
                feat = model.encode_text(tokens)
                feat = feat / feat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                arr = feat.cpu().numpy().astype(np.float32)
            emb_map = {p: v for p, v in zip(prompts_list, arr)}
        except Exception as e:
            logging.warning(f"OpenCLIP probe encoding skipped: {e}")
            emb_map = {}
    else:
        emb_map = encode_text_batch_fn(list(CONCEPT_PROBE_PROMPTS.values()))

    key_to_vec: Dict[str, np.ndarray] = {}
    for k, prompt_str in CONCEPT_PROBE_PROMPTS.items():
        if prompt_str in emb_map:
            key_to_vec[k] = emb_map[prompt_str]

    learned_boundaries = load_vector_concept_boundaries(db_path=db_path)
    n_vecs = vectors.shape[0]
    probes_by_fp: Dict[str, Dict[str, Any]] = {}

    # Pre-identify candidate everyday/indoor/portrait/automotive frames that benefit from multi-region crop analysis
    multiregion_candidates: List[Dict[str, Any]] = []
    if key_to_vec and n_vecs > 0:
        mr_trigger_keys = [
            k for k in (
                "scene_indoor_domestic", "scene_mirror_selfie", "scene_urban_automotive",
                "dog_indoor", "cat_indoor", "cat_tree", "living_room", "mirror_selfie",
                "fitting_room", "sports_car_sedan", "gas_station", "dog", "cat", "car_vehicle",
            )
            if k in key_to_vec
        ]
        if mr_trigger_keys:
            mr_mat = np.stack([key_to_vec[k] for k in mr_trigger_keys], axis=0).astype(np.float32)
            for r in rows:
                v_idx = r.get("vector_index")
                if v_idx is None or int(v_idx) < 0 or int(v_idx) >= n_vecs:
                    continue
                v = vectors[int(v_idx)].astype(np.float32)
                vn = float(np.linalg.norm(v))
                if vn < 1e-6:
                    continue
                v = v / vn
                max_mr = float(np.max(np.dot(mr_mat, v)))
                if len(rows) <= 150 or max_mr >= 0.215:
                    multiregion_candidates.append(r)

    multiregion_map = _compute_multiregion_crop_sims_for_candidates(multiregion_candidates, key_to_vec)

    for r in rows:
        fp = r["file_path"]
        v_idx = r.get("vector_index")
        neg_low = {str(t).lower().strip() for t in _safe_json_list(r.get("negated_tags")) if str(t).strip()}
        user_taught_low = {str(t).lower().strip() for t in _safe_json_list(r.get("user_taught_tags")) if str(t).strip()}
        lrcat_kws = [
            k.lower().strip()
            for k in _safe_json_list(r.get("lrcat_keywords"))
            if k.lower().strip() not in GENERIC_NOISE_TAGS and k.lower().strip() not in neg_low
        ]
        human_kws = [
            k.lower().strip()
            for k in (_safe_json_list(r.get("lrcat_keywords")) + _safe_json_list(r.get("existing_keywords")))
            if k.lower().strip() not in GENERIC_NOISE_TAGS and k.lower().strip() not in neg_low
        ]
        human_blob = " ".join(human_kws)
        lrcat_words = set(re.split(r"[^a-z0-9]+", " ".join(lrcat_kws)))

        explicit_aerial_kw = any(
            w in human_blob for w in ("helicopter", "taft", "palouse", "air to air", "overflight")
        )
        explicit_terrestrial_kw = any(
            w in human_blob
            for w in (
                "barn", "bison", "buffalo", "ranch", "portrait", "mitch shooting", "alice", "family",
                "trail", "yosemite", "grand canyon", "monument valley", "395", "tucson",
                "denver", "carolinas", "everglades", "lousiana", "louisiana", "houma",
            )
        )

        if v_idx is None or int(v_idx) < 0 or int(v_idx) >= n_vecs or not key_to_vec:
            is_aer = explicit_aerial_kw and not explicit_terrestrial_kw
            probes_by_fp[fp] = {"is_aerial": is_aer, "scene_context": "outdoor_nature", "verified_subjects": [], "subject_boxes": [], "subject_counts": {}}
            continue

        vec = vectors[int(v_idx)].astype(np.float32)
        norm = float(np.linalg.norm(vec))
        if norm < 1e-6:
            is_aer = explicit_aerial_kw and not explicit_terrestrial_kw
            probes_by_fp[fp] = {"is_aerial": is_aer, "scene_context": "outdoor_nature", "verified_subjects": [], "subject_boxes": [], "subject_counts": {}}
            continue
        vec = vec / norm

        def _sim(k_name: str) -> float:
            v_p = key_to_vec.get(k_name)
            return float(np.dot(vec, v_p)) if v_p is not None else 0.0

        crop_sims = multiregion_map.get(fp, {})

        def _best_crop(k_name: str, regions: Optional[ Tuple[str, ...] ] = None) -> Tuple[float, Optional[str]]:
            if not crop_sims:
                return 0.0, None
            best_v = 0.0
            best_r = None
            target_regs = regions or tuple(_MULTIREGION_BOX_SPECS.keys())
            for rn in target_regs:
                val = float(crop_sims.get(rn, {}).get(k_name, 0.0))
                if val > best_v:
                    best_v = val
                    best_r = rn
            return best_v, best_r

        # Compute Active Vector Boundary adjustments (old_label penalty, new_label boost)
        concept_delta: Dict[str, float] = {}
        boosted_custom_labels: List[Tuple[str, float]] = []
        for b_item in learned_boundaries:
            b_sim = float(np.dot(vec, b_item["vec"]))
            if b_sim >= 0.72:
                w = b_item["weight"] * b_sim
                old_l = b_item["old_low"]
                new_l = b_item["new_low"]
                concept_delta[old_l] = concept_delta.get(old_l, 0.0) - (0.095 * w)
                if new_l and new_l not in ("none", "dismiss", "false_positive", "empty"):
                    concept_delta[new_l] = concept_delta.get(new_l, 0.0) + (0.075 * w)
                    boosted_custom_labels.append((b_item["new_label"], round(b_sim, 3)))

        def _adj(base_score: float, *labels: str) -> float:
            d = sum(concept_delta.get(lb.lower(), 0.0) for lb in labels)
            return base_score + d

        aerial_sim = max(_sim("aerial_1"), _sim("aerial_2"))
        terrestrial_sim = max(_sim("terrestrial_1"), _sim("terrestrial_2"))
        bg_sim = _sim("bg_landscape")

        # Top-Level Scene Context Router
        scene_indoor_sim = max(_sim("scene_indoor_domestic"), _sim("living_room"), _sim("cat_tree"))
        scene_mirror_sim = max(_sim("scene_mirror_selfie"), _sim("mirror_selfie"), _sim("fitting_room"))
        scene_auto_sim = max(_sim("scene_urban_automotive"), _sim("sports_car_sedan"), _sim("gas_station"))
        scene_nature_sim = max(_sim("scene_outdoor_nature"), bg_sim)

        # Contrastive Habitat Foils & Inanimate Artifact Foils
        foil_forest = _sim("foil_empty_forest_path")
        foil_trees = _sim("foil_empty_trees_sky")
        foil_wet_rocks = _sim("foil_wet_rocks_moss")
        foil_water = _sim("foil_empty_water_pond")
        foil_ranch = _sim("foil_empty_ranch_barn")
        foil_desert = _sim("foil_empty_desert_rocks")
        foil_statue = _sim("foil_statue_sculpture")
        foil_framed_pic = _sim("foil_framed_picture_wall")
        foil_empty_carpet = _sim("foil_empty_room_carpet")

        foil_habitat_max = max(bg_sim, foil_forest, foil_trees, foil_wet_rocks, foil_water, foil_ranch, foil_desert)
        foil_artifact_max = max(foil_statue, foil_framed_pic)

        if explicit_aerial_kw and not explicit_terrestrial_kw:
            is_aerial = True
        elif explicit_terrestrial_kw:
            is_aerial = False
        elif max(scene_indoor_sim, scene_mirror_sim, scene_auto_sim) >= 0.225:
            is_aerial = False
        else:
            is_aerial = bool(aerial_sim > terrestrial_sim + 0.020 and aerial_sim >= 0.195)

        if is_aerial:
            scene_context = "aerial"
        elif scene_mirror_sim >= 0.235 and scene_mirror_sim >= scene_nature_sim + 0.025:
            scene_context = "mirror_portrait"
        elif scene_indoor_sim >= 0.215 and scene_indoor_sim >= scene_nature_sim + 0.020:
            scene_context = "indoor_domestic"
        elif scene_auto_sim >= 0.220 and scene_auto_sim >= scene_nature_sim + 0.020:
            scene_context = "urban_automotive"
        else:
            scene_context = "outdoor_nature"

        is_everyday_non_nature = scene_context in ("mirror_portrait", "indoor_domestic", "urban_automotive")

        person_sim = _adj(max(_sim("person"), _sim("person_2")), "person", "people", "human", "man", "woman")
        male_sim = _adj(_sim("male"), "man", "male", "person")
        female_sim = _adj(_sim("female"), "woman", "female", "person")
        photog_sim = _adj(_sim("photographer"), "photographer", "mitch rouse (subject)", "person")
        mirror_selfie_sim = _adj(max(_sim("mirror_selfie"), _sim("scene_mirror_selfie")), "mirror selfie", "selfie", "person")
        fitting_room_sim = _adj(_sim("fitting_room"), "fitting room")
        living_room_sim = _adj(max(_sim("living_room"), _sim("scene_indoor_domestic")), "living room")
        cat_tree_sim = _adj(_sim("cat_tree"), "cat tree")
        framed_art_sim = _adj(_sim("framed_art"), "framed art")

        bison_sim = _adj(_sim("bison"), "bison", "buffalo")
        horse_sim = _adj(_sim("horse"), "horse", "horses")
        cattle_sim = _adj(_sim("cattle"), "cattle", "cow", "cows")
        bird_sim = _adj(_sim("bird"), "bird", "birds", "heron", "egret", "pelican", "hawk", "eagle")
        frog_sim = _adj(_sim("frog"), "frog", "frogs", "toad")
        dog_sim = _adj(max(_sim("dog"), _sim("dog_indoor")), "dog", "dogs", "pet")
        cat_sim = _adj(max(_sim("cat"), _sim("cat_indoor")), "cat", "cats", "pet")
        deer_sim = _adj(_sim("deer_elk"), "deer", "elk")
        bear_sim = _adj(_sim("bear"), "bear")
        wildlife_sim = _adj(_sim("wildlife"), "wildlife", "animal", "animals")
        boat_sim = _adj(_sim("f2_boats_vessels"), "boat", "boats", "fishing boat", "ship", "vessel", "canoe", "kayak")
        car_sim = _adj(max(_sim("car_vehicle"), _sim("sports_car_sedan")), "car", "cars", "sports car", "sedan", "vehicle", "truck")
        sports_car_sim = _adj(_sim("sports_car_sedan"), "sports car", "sedan", "car", "lexus")
        gas_station_sim = _adj(_sim("gas_station"), "gas station", "gas pump")
        train_sim = _adj(_sim("train_rail"), "train", "trains", "locomotive")
        airplane_sim = _adj(_sim("airplane"), "airplane", "airplanes", "aircraft")
        taft_sim = _sim("taft")
        palouse_sim = _sim("palouse")

        # Multi-region crop signals for foreground/background dual subjects & night sky lighting
        crop_dog_sim, crop_dog_reg = _best_crop("dog_indoor", ("lower_right", "lower_left", "center"))
        crop_dog_gen_sim, crop_dog_gen_reg = _best_crop("dog", ("lower_right", "lower_left", "center"))
        if crop_dog_gen_sim > crop_dog_sim:
            crop_dog_sim, crop_dog_reg = crop_dog_gen_sim, crop_dog_gen_reg
        crop_dog_foil = float(crop_sims.get(crop_dog_reg or "lower_right", {}).get("foil_empty_room_carpet", foil_empty_carpet))

        crop_cat_sim, crop_cat_reg = _best_crop("cat_indoor", ("upper_left", "upper_right", "center", "lower_left"))
        crop_cat_gen_sim, crop_cat_gen_reg = _best_crop("cat", ("upper_left", "upper_right", "center", "lower_left"))
        if crop_cat_gen_sim > crop_cat_sim:
            crop_cat_sim, crop_cat_reg = crop_cat_gen_sim, crop_cat_gen_reg
        crop_cat_foil = float(crop_sims.get(crop_cat_reg or "upper_left", {}).get("foil_empty_room_carpet", foil_empty_carpet))

        crop_cattree_sim, crop_cattree_reg = _best_crop("cat_tree", ("upper_left", "upper_right", "center"))
        crop_mirror_sim, crop_mirror_reg = _best_crop("mirror_selfie", ("center", "upper_left", "upper_right"))
        crop_fitting_sim, _ = _best_crop("fitting_room", ("center", "upper_left", "upper_right"))
        crop_male_sim, _ = _best_crop("male", ("center", "upper_left", "upper_right"))
        crop_female_sim, _ = _best_crop("female", ("center", "upper_left", "upper_right"))
        crop_sportscar_sim, crop_sportscar_reg = _best_crop("sports_car_sedan", ("center", "lower_left", "lower_right"))
        crop_gas_sim, crop_gas_reg = _best_crop("gas_station", ("upper_right", "upper_left", "upper_sky", "center"))

        # Context-Scoped Foil Gating:
        # Never allow a background wall prop (`foil_framed_picture_wall`) to veto a Mirror Selfie or Indoor Pet!
        has_mirror_selfie = bool(
            (scene_context == "mirror_portrait" or mirror_selfie_sim >= 0.232 or crop_mirror_sim >= 0.240)
            and max(mirror_selfie_sim, crop_mirror_sim) > foil_statue + 0.035
            and not bool(neg_low & {"mirror selfie", "selfie", "person", "people"})
        )
        has_fitting_room = bool(
            (fitting_room_sim >= 0.230 or (has_mirror_selfie and crop_fitting_sim >= 0.245))
            and not bool(neg_low & {"fitting room"})
        )

        effective_person_artifact_foil = foil_statue if (has_mirror_selfie or scene_context == "mirror_portrait") else foil_artifact_max
        person_foil = (
            max(bg_sim, effective_person_artifact_foil)
            if is_everyday_non_nature
            else max(bg_sim, foil_forest, foil_trees, foil_ranch, foil_artifact_max)
        )
        has_person = bool(
            has_mirror_selfie
            or (
                person_sim >= 0.258
                and (person_sim - person_foil) >= 0.028
                and (person_sim - effective_person_artifact_foil) >= 0.025
            )
            or bool(user_taught_low & {"person", "people", "man", "woman", "portrait", "photographer", "mitch rouse (subject)", "mirror selfie", "selfie"})
            or bool(lrcat_words & {"portrait", "family", "person", "people", "cowboy", "rancher"})
        ) and not bool(neg_low & {"person", "people", "human"})

        # Taxonomic Abstention: classify Man or Woman when certainty margin is clear
        eff_male = max(male_sim, crop_male_sim) if has_mirror_selfie else male_sim
        eff_female = max(female_sim, crop_female_sim) if has_mirror_selfie else female_sim
        is_male_person = bool(
            has_person
            and (
                (male_sim >= 0.265 and (male_sim - female_sim) >= 0.038 and (male_sim - effective_person_artifact_foil) >= 0.030)
                or (has_mirror_selfie and eff_male >= 0.175 and (eff_male - eff_female) >= 0.008)
                or bool(user_taught_low & {"man", "male", "mitch rouse (subject)"})
            )
            and not bool(neg_low & {"man", "male"})
        )
        is_female_person = bool(
            has_person
            and not is_male_person
            and (
                (female_sim >= 0.265 and (female_sim - male_sim) >= 0.038 and (female_sim - effective_person_artifact_foil) >= 0.030)
                or (has_mirror_selfie and eff_female >= 0.175 and (eff_female - eff_male) >= 0.015)
                or bool(user_taught_low & {"woman", "female"})
            )
            and not bool(neg_low & {"woman", "female"})
        )
        is_photographer = bool(
            has_person
            and not has_mirror_selfie
            and (
                (photog_sim >= 0.258 and (photog_sim - person_foil) >= 0.025)
                or "photographer" in user_taught_low
                or ("mitch shooting" in human_blob and person_sim >= 0.245)
            )
        )

        fp_stem_low = Path(fp).stem.lower()
        fp_stem_words = set(re.findall(r"[a-z]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", Path(fp).stem).lower()))

        bird_foil = max(bg_sim, foil_forest, foil_trees, foil_water, foil_ranch, foil_artifact_max)
        has_bird = bool(
            (
                not is_everyday_non_nature
                and bird_sim >= 0.278
                and (bird_sim - bird_foil) >= 0.038
                and (bird_sim - foil_artifact_max) >= 0.032
            )
            or bool(user_taught_low & {"bird", "birds", "heron", "egret", "pelican", "hawk", "eagle", "owl", "waterfowl"})
            or bool(lrcat_words & {"bird", "birds", "heron", "egret", "pelican", "eagle", "owl", "waterfowl"})
            or bool(fp_stem_words & {"bird", "birds", "blackbird", "heron", "egret", "pelican", "hawk", "eagle", "owl"})
        ) and not bool(neg_low & {"bird", "birds"})

        frog_foil = max(bg_sim, foil_wet_rocks, foil_water, foil_forest, foil_artifact_max)
        has_frog = bool(
            (
                not is_everyday_non_nature
                and frog_sim >= 0.285
                and (frog_sim - frog_foil) >= 0.042
                and (frog_sim - foil_artifact_max) >= 0.035
            )
            or bool(user_taught_low & {"frog", "frogs", "toad", "amphibian"})
            or bool(lrcat_words & {"frog", "frogs", "toad"})
        ) and not bool(neg_low & {"frog", "frogs"})

        # Context-Scoped Multi-Region Pet Detection:
        # In indoor scenes, compare against empty room carpet + statue foil (never let a framed picture on a wall veto a live pet!)
        dog_foil = (
            max(foil_empty_carpet, foil_statue)
            if scene_context == "indoor_domestic"
            else max(bg_sim, foil_ranch, foil_forest, foil_desert, foil_artifact_max)
        )
        has_dog_global = (
            dog_sim >= (0.235 if scene_context == "indoor_domestic" else 0.278)
            and (dog_sim - dog_foil) >= (0.025 if scene_context == "indoor_domestic" else 0.038)
            and (dog_sim - foil_statue) >= 0.032
        )
        has_dog_regional = (
            crop_dog_sim >= 0.240
            and (crop_dog_sim - crop_dog_foil) >= 0.035
            and (scene_context == "indoor_domestic" or dog_sim >= 0.215)
        )
        has_dog = bool(
            has_dog_global
            or has_dog_regional
            or bool(user_taught_low & {"dog", "dogs", "canine", "puppy", "chihuahua"})
            or bool(lrcat_words & {"dog", "dogs"})
        ) and not bool(neg_low & {"dog", "dogs"})

        cat_foil = (
            max(foil_empty_carpet, foil_statue)
            if scene_context == "indoor_domestic"
            else max(bg_sim, foil_ranch, foil_forest, foil_artifact_max)
        )
        has_cat_global = (
            cat_sim >= (0.245 if scene_context == "indoor_domestic" else 0.282)
            and (cat_sim - cat_foil) >= (0.030 if scene_context == "indoor_domestic" else 0.040)
            and (cat_sim - foil_statue) >= 0.032
        )
        has_cat_regional = (
            crop_cat_sim >= 0.238
            and (crop_cat_sim - crop_cat_foil) >= 0.042
            and (scene_context == "indoor_domestic" or cat_sim >= 0.195 or crop_cattree_sim >= 0.248)
        )
        has_cat = bool(
            has_cat_global
            or has_cat_regional
            or bool(user_taught_low & {"cat", "cats", "feline", "kitten"})
            or bool(lrcat_words & {"cat", "cats"})
        ) and not bool(neg_low & {"cat", "cats"})

        has_cat_tree = bool(
            (cat_tree_sim >= 0.235 or (has_cat and crop_cattree_sim >= 0.248))
            and not bool(neg_low & {"cat tree"})
        )
        has_living_room = bool(
            scene_context == "indoor_domestic"
            and (living_room_sim >= 0.215 or has_cat_tree)
            and not has_fitting_room
            and not bool(neg_low & {"living room"})
        )
        crop_framed_sim, _ = _best_crop("framed_art", ("upper_right", "upper_left", "center"))
        crop_carpet_sim, _ = _best_crop("foil_empty_room_carpet", ("lower_left", "lower_right", "center"))
        has_carpet_rug = bool(
            scene_context == "indoor_domestic"
            and (foil_empty_carpet >= 0.215 or crop_carpet_sim >= 0.220)
            and not bool(neg_low & {"carpet", "rug"})
        )
        has_framed_art = bool(
            scene_context == "indoor_domestic"
            and (framed_art_sim >= 0.215 or foil_framed_pic >= 0.215 or crop_framed_sim >= 0.160)
            and not bool(neg_low & {"framed art"})
        )

        bison_foil = max(bg_sim, foil_ranch, foil_desert, foil_forest, foil_artifact_max)
        has_bison = bool(
            (
                not is_everyday_non_nature
                and bison_sim >= 0.275
                and (bison_sim - bison_foil) >= 0.035
            )
            or bool(user_taught_low & {"bison", "buffalo", "american bison"})
            or bool(lrcat_words & {"bison", "buffalo"})
        ) and not bool(neg_low & {"bison", "buffalo"})

        horse_foil = max(bg_sim, foil_ranch, foil_forest, foil_desert, foil_artifact_max)
        has_horse = bool(
            (
                not is_everyday_non_nature
                and horse_sim >= 0.275
                and (horse_sim - horse_foil) >= 0.035
            )
            or bool(user_taught_low & {"horse", "horses", "equine"})
            or bool(lrcat_words & {"horse", "horses"})
        ) and not bool(neg_low & {"horse", "horses"})

        has_cattle = bool(
            (
                not is_everyday_non_nature
                and cattle_sim >= 0.278
                and (cattle_sim - horse_foil) >= 0.038
            )
            or bool(user_taught_low & {"cattle", "cow", "cows", "livestock"})
            or bool(lrcat_words & {"cattle", "cow", "cows"})
        ) and not bool(neg_low & {"cattle", "cow", "cows"})

        has_deer = bool(
            (
                not is_everyday_non_nature
                and deer_sim >= 0.282
                and (deer_sim - max(bg_sim, foil_forest, foil_ranch, foil_artifact_max)) >= 0.040
            )
            or bool(user_taught_low & {"deer", "elk", "antelope", "pronghorn"})
        ) and not bool(neg_low & {"deer", "elk"})

        has_bear = bool(
            (
                not is_everyday_non_nature
                and bear_sim >= 0.285
                and (bear_sim - max(bg_sim, foil_forest, foil_wet_rocks, foil_artifact_max)) >= 0.042
            )
            or bool(user_taught_low & {"bear", "grizzly bear", "black bear"})
        ) and not bool(neg_low & {"bear"})

        has_wildlife = bool(
            has_bison or has_horse or has_cattle or has_bird or has_frog or has_deer or has_bear
            or (
                not is_everyday_non_nature
                and wildlife_sim >= 0.282
                and (wildlife_sim - foil_habitat_max) >= 0.040
                and (wildlife_sim - foil_artifact_max) >= 0.035
            )
        ) and not bool(neg_low & {"wildlife", "animal", "animals"})

        boat_foil = max(bg_sim, foil_water, foil_ranch, foil_wet_rocks, foil_forest)
        has_boat = bool(
            (
                boat_sim >= 0.268
                and (boat_sim - boat_foil) >= 0.035
                and not is_aerial
            )
            or (
                (bool(fp_stem_words & {"boat", "boats", "fishharbor", "harbor", "venice", "marina", "sailboat", "yacht"}) or "fishharbor" in fp_stem_low)
                and "boathouse" not in fp_stem_low
            )
            or bool(user_taught_low & {"boat", "boats", "fishing boat", "ship", "vessel", "canoe", "kayak", "sailboat"})
            or bool(lrcat_words & {"boat", "boats", "ship", "canoe", "kayak", "sailboat", "harbor"})
        ) and not bool(neg_low & {"boat", "boats"})

        has_sports_car = bool(
            (
                (sports_car_sim >= 0.245 or crop_sportscar_sim >= 0.260)
                and (max(sports_car_sim, crop_sportscar_sim) - bg_sim) >= 0.040
            )
            or bool(user_taught_low & {"sports car", "sedan", "lexus"})
        ) and not bool(neg_low & {"car", "cars", "sports car", "sedan", "vehicle"})

        has_car = bool(
            has_sports_car
            or (car_sim >= 0.258 and (car_sim - foil_habitat_max) >= 0.035)
            or bool(user_taught_low & {"car", "cars", "vehicle", "truck", "automobile", "sports car", "sedan", "lexus"})
        ) and not bool(neg_low & {"car", "cars", "vehicle"})

        has_gas_station = bool(
            (
                (gas_station_sim >= 0.220 or crop_gas_sim >= 0.265)
                and (has_car or scene_context == "urban_automotive" or gas_station_sim >= 0.245)
            )
            or bool(user_taught_low & {"gas station", "gas pump", "service station"})
        ) and not bool(neg_low & {"gas station"})

        # Night & Artificial Lighting vs Daylight detection (compares night vs daylight within the same upper sky/corner region)
        night_full_sim = _sim("light_night_artificial")
        day_full_sim = _sim("light_daylight_midday")
        night_sky_sim, night_sky_reg = _best_crop("light_night_artificial", ("upper_sky", "upper_left", "upper_right"))
        day_same_reg_sim = float(
            crop_sims.get(night_sky_reg or "upper_left", {}).get("light_daylight_midday", day_full_sim)
        )
        is_night_artificial = bool(
            (
                (night_full_sim >= 0.140 and night_full_sim >= day_full_sim + 0.025)
                or (night_sky_sim >= 0.185 and night_sky_sim >= day_same_reg_sim + 0.032)
            )
            and (is_everyday_non_nature or has_car or has_gas_station or night_full_sim >= 0.210)
            and not bool(neg_low & {"night", "artificial lighting"})
        )

        has_train = bool(
            (train_sim >= 0.280 and (train_sim - foil_habitat_max) >= 0.040)
            or bool(user_taught_low & {"train", "trains", "locomotive"})
        ) and not bool(neg_low & {"train", "trains"})

        has_airplane = bool(
            (airplane_sim >= 0.282 and (airplane_sim - max(foil_habitat_max, aerial_sim)) >= 0.040)
            or bool(user_taught_low & {"airplane", "airplanes", "aircraft"})
        ) and not bool(neg_low & {"airplane", "airplanes", "aircraft"})

        # Build verified_subjects list with confidence, contrastive margins, and regional bounding boxes
        verified_subjects: List[Dict[str, Any]] = []
        plural_hints: Dict[str, bool] = {}

        def _add_vs(
            label: str,
            score: float,
            foil_score: float,
            is_plural_hint: bool = False,
            bbox: Optional[List[float]] = None,
            source_override: Optional[str] = None,
        ) -> None:
            entry_vs: Dict[str, Any] = {
                "label": label,
                "confidence": round(max(0.55, min(0.99, float(score) * 3.25)), 3),
                "raw_sim": round(float(score), 4),
                "margin": round(float(score - foil_score), 4),
                "source": source_override or ("user_taught" if label.lower() in user_taught_low else "contrastive_gate"),
            }
            if bbox is not None:
                entry_vs["bbox"] = bbox
            verified_subjects.append(entry_vs)
            plural_hints[label.lower()] = is_plural_hint

        if has_bison:
            _add_vs("Bison", bison_sim, bison_foil, is_plural_hint=True)
        if has_horse:
            _add_vs("Horse", horse_sim, horse_foil, is_plural_hint=("horses" in lrcat_words or "horses" in user_taught_low))
        if has_cattle:
            _add_vs("Cattle", cattle_sim, horse_foil, is_plural_hint=True)
        if has_bird:
            _add_vs("Bird", bird_sim, bird_foil, is_plural_hint=("birds" in lrcat_words or "birds" in user_taught_low or "birds" in fp_stem_words))
        if has_frog:
            _add_vs("Frog", frog_sim, frog_foil, is_plural_hint=("frog" in lrcat_words or "frogs" in user_taught_low))
        if has_dog:
            dog_best_score = max(dog_sim, crop_dog_sim)
            dog_bbox = _MULTIREGION_BOX_SPECS.get(crop_dog_reg) if (has_dog_regional and crop_dog_reg) else None
            _add_vs(
                "Dog",
                dog_best_score,
                crop_dog_foil if has_dog_regional else dog_foil,
                is_plural_hint=("dogs" in lrcat_words or "dogs" in user_taught_low),
                bbox=dog_bbox,
                source_override="multiregion_detector" if has_dog_regional else None,
            )
        if has_cat:
            cat_best_score = max(cat_sim, crop_cat_sim)
            cat_bbox = _MULTIREGION_BOX_SPECS.get(crop_cat_reg) if (has_cat_regional and crop_cat_reg) else None
            _add_vs(
                "Cat",
                cat_best_score,
                crop_cat_foil if has_cat_regional else cat_foil,
                is_plural_hint=("cats" in lrcat_words or "cats" in user_taught_low),
                bbox=cat_bbox,
                source_override="multiregion_detector" if has_cat_regional else None,
            )
        if has_cat_tree:
            ct_best = max(cat_tree_sim, crop_cattree_sim)
            ct_bbox = _MULTIREGION_BOX_SPECS.get(crop_cattree_reg or "upper_left")
            _add_vs(
                "Cat Tree",
                ct_best,
                crop_cat_foil,
                is_plural_hint=False,
                bbox=ct_bbox,
                source_override="multiregion_detector",
            )
        if has_deer:
            _add_vs("Deer", deer_sim, foil_habitat_max, is_plural_hint=False)
        if has_bear:
            _add_vs("Bear", bear_sim, foil_habitat_max, is_plural_hint=False)
        if has_person:
            p_label = "Man" if is_male_person else ("Woman" if is_female_person else "Person")
            p_score = max(person_sim, mirror_selfie_sim, crop_mirror_sim) if has_mirror_selfie else person_sim
            p_bbox = _MULTIREGION_BOX_SPECS.get(crop_mirror_reg or "center") if has_mirror_selfie else None
            _add_vs(p_label, p_score, person_foil, is_plural_hint=("people" in lrcat_words or "family" in lrcat_words), bbox=p_bbox)
        if has_mirror_selfie:
            _add_vs("Mirror Selfie", max(mirror_selfie_sim, crop_mirror_sim), foil_statue, is_plural_hint=False, bbox=_MULTIREGION_BOX_SPECS.get(crop_mirror_reg or "center"))
        if has_boat:
            _add_vs("Boat", boat_sim, boat_foil, is_plural_hint=("boats" in lrcat_words or "fishharbor" in fp_stem_low))
        if has_car:
            car_best = max(car_sim, sports_car_sim, crop_sportscar_sim)
            car_bbox = _MULTIREGION_BOX_SPECS.get(crop_sportscar_reg or "center") if has_sports_car else None
            _add_vs("Car", car_best, bg_sim, is_plural_hint=False, bbox=car_bbox)
        if has_sports_car:
            _add_vs("Sports Car", max(sports_car_sim, crop_sportscar_sim), bg_sim, is_plural_hint=False, bbox=_MULTIREGION_BOX_SPECS.get(crop_sportscar_reg or "center"))
        if has_gas_station:
            _add_vs("Gas Station", max(gas_station_sim, crop_gas_sim), bg_sim, is_plural_hint=False, bbox=_MULTIREGION_BOX_SPECS.get(crop_gas_reg or "upper_right"))
        if has_train:
            _add_vs("Train", train_sim, foil_habitat_max, is_plural_hint=False)
        if has_airplane:
            _add_vs("Airplane", airplane_sim, foil_habitat_max, is_plural_hint=False)

        for custom_lbl, custom_sim in boosted_custom_labels:
            if custom_lbl.lower() not in {v["label"].lower() for v in verified_subjects} and custom_lbl.lower() not in neg_low:
                verified_subjects.append({
                    "label": custom_lbl,
                    "confidence": round(min(0.98, 0.80 + (custom_sim - 0.72) * 0.6), 3),
                    "raw_sim": custom_sim,
                    "margin": round(custom_sim - 0.72, 4),
                    "source": "vector_boundary_learned",
                })

        subject_boxes, subject_counts = localize_verified_subject_boxes(
            record=r,
            verified_subjects=verified_subjects,
            plural_hints=plural_hints,
        )

        probe_entry: Dict[str, Any] = {
            "is_aerial": is_aerial,
            "scene_context": scene_context,
            "aerial_sim": round(aerial_sim, 4),
            "terrestrial_sim": round(terrestrial_sim, 4),
            "foil_habitat_max": round(foil_habitat_max, 4),
            "foil_artifact_max": round(foil_artifact_max, 4),
            "has_person": has_person,
            "is_male_person": is_male_person,
            "is_female_person": is_female_person,
            "is_photographer": is_photographer,
            "has_mirror_selfie": has_mirror_selfie,
            "has_fitting_room": has_fitting_room,
            "has_living_room": has_living_room,
            "has_carpet_rug": has_carpet_rug,
            "has_cat_tree": has_cat_tree,
            "has_framed_art": has_framed_art,
            "has_bison": has_bison,
            "has_horse": has_horse,
            "has_cattle": has_cattle,
            "has_bird": has_bird,
            "has_frog": has_frog,
            "has_dog": has_dog,
            "has_cat": has_cat,
            "has_deer": has_deer,
            "has_bear": has_bear,
            "has_wildlife": has_wildlife,
            "has_boat": has_boat,
            "has_car": has_car,
            "has_sports_car": has_sports_car,
            "has_gas_station": has_gas_station,
            "is_night_artificial": is_night_artificial,
            "has_train": has_train,
            "has_airplane": has_airplane,
            "verified_subjects": verified_subjects,
            "subject_boxes": subject_boxes,
            "subject_counts": subject_counts,
            "boosted_custom_labels": [c[0] for c in boosted_custom_labels],
            "taft_sim": round(taft_sim, 4),
            "palouse_sim": round(palouse_sim, 4),
            "lm_hallgrimskirkja_sim": round(_sim("lm_hallgrimskirkja"), 4),
            "lm_kirkjufell_sim": round(_sim("lm_kirkjufell"), 4),
            "lm_jokulsarlon_sim": round(_sim("lm_jokulsarlon"), 4),
            "lm_reynisfjara_sim": round(_sim("lm_reynisfjara"), 4),
            "lm_gullfoss_sim": round(_sim("lm_gullfoss"), 4),
            "lm_valley_of_gods_sim": round(_sim("lm_valley_of_gods"), 4),
            "lm_monument_valley_sim": round(_sim("lm_monument_valley"), 4),
            "lm_castleton_fisher_sim": round(_sim("lm_castleton_fisher"), 4),
            "lm_devils_tower_sim": round(_sim("lm_devils_tower"), 4),
            "lm_grand_tetons_sim": round(_sim("lm_grand_tetons"), 4),
            "lm_mount_rainier_sim": round(_sim("lm_mount_rainier"), 4),
            "lm_yosemite_sim": round(_sim("lm_yosemite"), 4),
            "lm_mono_lake_sim": round(_sim("lm_mono_lake"), 4),
            "lm_washington_monument_sim": round(_sim("lm_washington_monument"), 4),
            "lm_chicago_sim": round(_sim("lm_chicago"), 4),
            "lm_venice_italy_sim": round(_sim("lm_venice_italy"), 4),
            "lm_colonial_doors_sim": round(_sim("lm_colonial_doors"), 4),
            "lm_highway_interchange_sim": round(_sim("lm_highway_interchange"), 4),
        }
        # Attach 5-Facet Visual Probe Scores
        for fk in CONCEPT_PROBE_PROMPTS:
            if fk.startswith(("f1_", "f2_", "f3_", "f4_", "f5_")):
                probe_entry[f"{fk}_sim"] = round(_sim(fk), 4)
        probes_by_fp[fp] = probe_entry

    return probes_by_fp


# ==============================================================================
# 6B. CLEAN PHOTOGRAPHER KEYWORDS & 10,000-FOOT PORTFOLIO CATEGORIES
# ==============================================================================
# (FILLER_NOISE_WORDS, JARGON_FACET_TAGS_LOWER, HALLUCINATED_SPEC_LOCATIONS_LOWER,
#  _UNDERSCORE_SUBJECT_MAP, PORTFOLIO_CATEGORIES_CONFIG imported from domain_gazetteer.py)


def _clean_single_photographer_tag(raw_tag: str, is_aerial: bool = False) -> Optional[str]:
    """
    Normalizes a candidate keyword into a clean, concrete photographer tag, or returns None if it is
    art-school jargon, lighting/camera metadata filler, or hallucinated micro-location noise.
    """
    t = str(raw_tag or "").strip()
    if not t:
        return None
    t_low = t.lower()

    if t_low in FILLER_NOISE_WORDS or t_low in GENERIC_NOISE_TAGS or t_low in JARGON_FACET_TAGS_LOWER:
        return None

    # Strip any Visual_Facets or Lighting or unconfirmed Aerial tags
    if t_low.startswith(("visual_facets", "lighting|", "atmosphere|sky", "f1_", "f2_", "f3_", "f4_", "f5_")):
        return None
    if "mitch rouse aerial" in t_low or t_low == "aerials":
        return None
    if not is_aerial and t_low in ("aerial", "aerial photography", "aerial view", "overhead"):
        return None

    # Filter out camera/lens/lighting/composition/EXIF phrases and raw dates
    if re.match(r"^\d{4}[-_/]\d{2}[-_/]\d{2}$", t_low):
        return None
    bad_substrings = (
        "palette", "framing", "composition", "diffused light", "golden hour",
        "daylight sun", "storm light", "mist & haze", "earth tones", "atmospheric tones",
        "saturated color", "wood texture", "masonry wall", "natural stone", "metal & steel",
        "water & ice", "earth & sand", "panoramic vista", "leading lines", "overhead geometric",
        "layered landscape", "tight architectural", "centered symmetrical", "surface & surf",
        "west coast imaging", "mitch shooting", "to print", "keepers arch", "not specified",
        "canon ", "nikon ", "sony ", "hasselblad", "phase one", "leica", "f/", "mm ", "iso ",
        "focal length", "shoot date", "shutter speed", "aperture", "midday sun", "afternoon sun",
        "morning sun", "dawn sunrise", "foggy morning", "foggy day", "foggy dawn", "night landscape",
        "marsh landscapes", "desert scenics", "rural landscape", "urban landscape",
    )
    if any(bs in t_low for bs in bad_substrings):
        return None

    # Handle underscore tokens from VLM outputs
    if "_" in t:
        if t_low in _UNDERSCORE_SUBJECT_MAP:
            return _UNDERSCORE_SUBJECT_MAP[t_low]
        # Drop technical/lighting/composition underscore strings
        if any(w in t_low for w in ("light", "shadow", "contrast", "exposure", "angle", "focus", "depth", "shot", "view", "viewpoint", "perspective", "color", "tone", "texture", "pattern", "composition", "framing", "background", "foreground", "sky", "cloud")):
            return None
        # Convert remaining concrete 2-word underscore subjects to Title Case
        parts = [p for p in t.split("_") if p]
        if len(parts) <= 3:
            cleaned_words = " ".join(parts).title()
            if cleaned_words.lower() in JARGON_FACET_TAGS_LOWER or cleaned_words.lower() in FILLER_NOISE_WORDS:
                return None
            return cleaned_words
        return None

    # Normalize specific location / landmark synonyms into canonical photographer labels
    canon_map = {
        "grand teton national park": "Grand Tetons",
        "teton range": "Grand Tetons",
        "tetons": "Grand Tetons",
        "yosemite national park": "Yosemite",
        "death valley national park": "Death Valley",
        "canyonlands national park": "Canyonlands & Moab",
        "grand canyon national park": "Grand Canyon",
        "white sands national park": "White Sands",
        "yellowstone national park": "Yellowstone",
        "everglades national park": "Everglades",
        "joshua tree national park": "Joshua Tree",
        "jokulsarlon": "Jökulsárlón & Diamond Beach",
        "jökulsárlón": "Jökulsárlón & Diamond Beach",
        "diamond beach": "Jökulsárlón & Diamond Beach",
        "kirkjufell": "Kirkjufell Mountain",
        "gullfoss": "Gullfoss & Icelandic Waterfalls",
        "hallgrimskirkja": "Hallgrímskirkja, Reykjavík",
        "hallgrímskirkja": "Hallgrímskirkja, Reykjavík",
        "hallgrímskirkja & reykjavík": "Hallgrímskirkja, Reykjavík",
        "reynisfjara": "Reynisfjara Black Sand Beach",
        "bandon": "Bandon Coast",
        "nashville parthenon": "Nashville",
        "urban highway interchange": "Bridges & Freeways",
        "los angeles freeway interchange": "Bridges & Freeways",
        "highway interchange": "Bridges & Freeways",
        "wooden door": "Doors & Windows",
        "colonial doors": "Doors & Windows",
    }
    if t_low in canon_map:
        return canon_map[t_low]

    return t


def assign_portfolio_categories(
    record: Dict[str, Any],
    probes: Dict[str, Any],
    flat_kws: List[str],
    hier_kws: List[str],
    country: Optional[str] = None,
    state_region: Optional[str] = None,
    specific_location: Optional[str] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Determines the 10,000-Foot Portfolio Categories (`Portfolio|<Category>`) and canonical sub-region/theme
    keywords for a photo based on verified geography, filename stems, .lrcat keywords, and high-confidence OpenCLIP probes.
    """
    fp_low = Path(str(record.get("file_path") or "")).stem.lower()
    ctry = str(country if country is not None else (record.get("country") or "")).strip()
    state = str(state_region if state_region is not None else (record.get("state_region") or "")).strip()
    spec = str(specific_location if specific_location is not None else (record.get("specific_location") or "")).strip()
    if ctry.lower() == "unknown":
        ctry = ""
    if state.lower() == "unknown":
        state = ""
    if spec.lower() == "unknown":
        spec = ""
    is_aerial = bool(probes.get("is_aerial", record.get("is_aerial")))

    kw_low_set = {str(k).lower().strip() for k in flat_kws if str(k).strip()}
    kw_words = set(re.split(r"[^a-z0-9]+", " ".join(kw_low_set))) - {""}
    blob = " ".join([fp_low, ctry.lower(), state.lower(), spec.lower()] + list(kw_low_set))

    categories: List[str] = []
    theme_tags: List[str] = []

    def _add_cat(cat_name: str, sub_tags: Optional[List[str]] = None) -> None:
        if cat_name not in categories:
            categories.append(cat_name)
        for st in (sub_tags or []):
            if st and st not in theme_tags:
                theme_tags.append(st)

    # 1. Iceland
    if ctry == "Iceland" or state == "Iceland" or "iceland" in blob:
        iceland_subs = ["Iceland"]
        if any(x in blob for x in ("jökulsárlón", "jokulsarlon", "diamond beach", "iceberg", "glacial lagoon")):
            iceland_subs.extend(["Jökulsárlón & Diamond Beach", "Glacial Ice & Black Sand"])
        if "kirkjufell" in blob or "tripplewf" in fp_low:
            iceland_subs.append("Kirkjufell Mountain")
        if "gullfoss" in blob or "vertwf" in fp_low or "waterfall" in blob:
            iceland_subs.append("Gullfoss & Icelandic Waterfalls")
        if any(x in blob for x in ("hallgrímskirkja", "hallgrimskirkja", "reykjavik", "reykjavík")):
            iceland_subs.append("Hallgrímskirkja, Reykjavík")
        if "reynisfjara" in blob or "black sand" in blob:
            iceland_subs.append("Reynisfjara Black Sand Beach")
        _add_cat("Iceland", iceland_subs)

    # 2. Oil Fields & Industrial
    if (
        any(x in blob for x in (
            "taft", "oil field", "oil facility", "oil refinery", "oil derrick",
            "oil production", "oil storage", "industrial pipeline", "industrial site",
            "industrial machinery", "industrial structure", "industrial ruins",
            "sugar_beet_factory", "power plant", "abandoned machinery", "caterpillar",
            "pipe derrick",
        ))
        or (is_aerial and float(probes.get("f1_industrial_facility_sim", 0.0)) >= 0.24)
    ):
        ind_subs = []
        if any(x in blob for x in ("taft", "oil field", "oil derrick", "oil production", "oil storage", "pipe derrick")):
            ind_subs.append("Oil Fields")
        if "taft" in blob and is_aerial:
            ind_subs.append("Taft Oil Field")
        if any(x in blob for x in ("industrial", "refinery", "facility", "plant", "machinery", "sugar_beet", "caterpillar", "derrick")):
            ind_subs.append("Industrial")
        _add_cat("Oil Fields & Industrial", ind_subs or ["Industrial"])

    # 3. Coastline & Piers
    if (
        any(x in blob for x in (
            "big sur", "point lobos", "pescadero", "huntington beach", "bandon", "oregon coast",
            "california coast", "california piers", "cayucos", "bolsa", "avila", "laguna",
            "santa barbara", "catalina", "la push", "olympic coast", "sea stacks", "pier",
        ))
        or float(probes.get("f1_coastline_surf_sim", 0.0)) >= 0.245
    ):
        coast_subs = []
        if "big sur" in blob:
            coast_subs.extend(["Big Sur", "California Coast"])
        elif "point lobos" in blob:
            coast_subs.extend(["Point Lobos", "California Coast"])
        elif "huntington beach" in blob:
            coast_subs.extend(["Huntington Beach", "California Coast", "California Piers"])
        elif any(x in blob for x in ("bandon", "oregon coast", "coosbay", "sunsetbch", "tidalflat")):
            coast_subs.extend(["Bandon Coast", "Oregon Coast"])
        elif any(x in blob for x in ("cayucos", "bolsa", "avila", "pier")):
            coast_subs.extend(["California Piers", "California Coast"])
        elif state == "California":
            coast_subs.append("California Coast")
        if float(probes.get("f1_coastline_surf_sim", 0.0)) >= 0.23 or "surf" in blob or "ocean" in blob or "beach" in blob:
            coast_subs.append("Ocean & Surf")
        _add_cat("Coastline & Piers", coast_subs or ["Ocean & Surf"])

    # 4. Desert (Southwest, Colorado Plateau, Death Valley, Eastern Sierra, White Sands, Sonoran)
    if (
        any(x in blob for x in (
            "monument valley", "valley of the gods", "canyonlands", "moab", "green river overlook",
            "upheaval", "deadhorse", "death valley", "zabriskie", "alabama hills", "mono lake",
            "eastern sierra", "highway 395", "white sands", "anza-borrego", "borrego",
            "tucson", "sonoran", "saguaro", "joshua tree", "sandstone butte", "mitten buttes",
            "desert monolith", "desert sand dunes", "rhyolite", "st. george",
        ))
        or (state in ("Utah", "Arizona", "New Mexico", "Nevada") and float(probes.get("f1_desert_arid_sim", 0.0)) >= 0.21)
    ):
        des_subs = ["Desert"]
        if "monument valley" in blob:
            des_subs.extend(["Monument Valley", "Buttes"])
        if "valley of the gods" in blob:
            des_subs.extend(["Valley of the Gods", "Buttes"])
        if any(x in blob for x in ("canyonlands", "moab", "green river overlook", "upheaval", "deadhorse")):
            des_subs.append("Canyonlands & Moab")
        if "death valley" in blob or "zabriskie" in blob:
            des_subs.append("Death Valley")
        if "alabama hills" in blob or "lone pine" in blob:
            des_subs.extend(["Alabama Hills", "Eastern Sierra & Highway 395"])
        if "mono lake" in blob or "tufa" in blob:
            des_subs.extend(["Mono Lake", "Eastern Sierra & Highway 395"])
        if "eastern sierra" in blob or "highway 395" in blob:
            des_subs.append("Eastern Sierra & Highway 395")
        if "white sands" in blob:
            des_subs.append("White Sands")
        if "borrego" in blob:
            des_subs.append("Anza-Borrego Desert")
        if "tucson" in blob or "sonoran" in blob or "saguaro" in blob:
            des_subs.append("Tucson & Sonoran Desert")
        if "joshua tree" in blob:
            des_subs.append("Joshua Tree")
        _add_cat("Desert", des_subs)

    # 5. National Parks & Mountains
    if (
        any(x in blob for x in (
            "yosemite", "half dome", "el capitan", "teton", "jackson hole", "yellowstone",
            "grand canyon", "everglades", "lake tahoe", "bighorn mountains", "milford sound",
            "fiordland", "sierra nevada", "wasatch", "heber valley", "red rocks", "front range",
        ))
        or float(probes.get("f1_mountain_peak_sim", 0.0)) >= 0.245
    ):
        np_subs = []
        if "yosemite" in blob:
            np_subs.extend(["Yosemite", "Mountains"])
        if "teton" in blob:
            np_subs.extend(["Grand Tetons", "Mountains"])
        if "grand canyon" in blob:
            np_subs.append("Grand Canyon")
        if "yellowstone" in blob:
            np_subs.append("Yellowstone")
        if "everglades" in blob:
            np_subs.append("Everglades")
        if "lake tahoe" in blob or "tahoe" in blob:
            np_subs.extend(["Lake Tahoe", "Mountains"])
        if "bighorn" in blob:
            np_subs.extend(["Bighorn Mountains", "Mountains"])
        if not np_subs:
            np_subs.append("Mountains")
        _add_cat("National Parks & Mountains", np_subs)

    # 6. Palouse & Farmland
    if (
        any(x in blob for x in (
            "palouse", "steptoe", "hawkeye ranch", "southfork", "moccasin", "mocasin",
            "humphrey", "montana plains", "billings", "yankton", "grain elevator", "grain silo",
            "barn", "homestead", "farmland", "corral", "pasture",
        ))
        or float(probes.get("f1_barn_farmstead_sim", 0.0)) >= 0.235
        or float(probes.get("f1_ranch_pasture_sim", 0.0)) >= 0.235
    ):
        farm_subs = []
        if "palouse" in blob or "steptoe" in blob:
            farm_subs.extend(["Palouse", "Farmland"])
        if "hawkeye" in blob or "southfork" in blob:
            farm_subs.extend(["Hawkeye Ranch & Southfork Valley", "Barns & Ranch"])
        if "moccasin" in blob or "mocasin" in blob:
            farm_subs.extend(["Moccasin", "Barns & Ranch"])
        if "humphrey" in blob:
            farm_subs.extend(["Humphrey, Nebraska", "Farmland"])
        if "billings" in blob or "montana plains" in blob or state == "Montana":
            farm_subs.append("Billings & Montana Plains")
        if "barn" in blob or "homestead" in blob or "ranch" in blob or float(probes.get("f1_barn_farmstead_sim", 0.0)) >= 0.225:
            farm_subs.append("Barns & Ranch")
        if not farm_subs:
            farm_subs.append("Farmland")
        _add_cat("Palouse & Farmland", farm_subs)

    # 7. Urban & Architecture
    if (
        any(x in blob for x in (
            "chicago", "washington monument", "united states capitol", "washington dc",
            "national mall", "venice", "san miguel de allende", "havana", "malecón", "malecon",
            "nashville", "parthenon", "savannah", "louisville", "brighton", "freeway",
            "highway interchange", "bridges & freeways", "overpass", "cityscape", "skyscraper",
        ))
        or float(probes.get("f1_urban_skyline_sim", 0.0)) >= 0.235
    ):
        urb_subs = ["Urban"]
        if "chicago" in blob:
            urb_subs.append("Chicago")
        if "washington dc" in blob or "washington monument" in blob or "capitol" in blob:
            urb_subs.append("Washington DC")
        if "venice" in blob and ctry == "Italy":
            urb_subs.append("Venice")
        if "san miguel" in blob or ctry == "Mexico":
            urb_subs.append("San Miguel de Allende")
        if "havana" in blob or "malec" in blob or ctry == "Cuba":
            urb_subs.append("Havana & Malecón")
        if "nashville" in blob or "parthenon" in blob:
            urb_subs.append("Nashville")
        if "savannah" in blob:
            urb_subs.append("Savannah, Georgia")
        if any(x in blob for x in ("freeway", "highway interchange", "bridges & freeways", "overpass", "bridge")):
            urb_subs.append("Bridges & Freeways")
        _add_cat("Urban & Architecture", urb_subs)

    # 8. Still Life & Cultural Details
    doors_sim = max(float(probes.get("f2_doors_windows_sim", 0.0)), float(probes.get("lm_colonial_doors_sim", 0.0)))
    if (
        doors_sim >= 0.225
        or any(x in blob for x in ("doors & windows", "wooden door", "colonial doors", "colonial architecture", "wildflowers", "still life", "courtyard"))
        or str(record.get("primary_category") or "") == "Still Life"
    ):
        sl_subs = []
        if doors_sim >= 0.225 or "door" in blob or "window" in blob:
            sl_subs.append("Doors & Windows")
        if "colonial" in blob or ctry in ("Mexico", "Cuba"):
            sl_subs.append("Colonial Architecture")
        if "wildflower" in blob or "poppy" in blob or "lupine" in blob or "sunflower" in blob:
            sl_subs.append("Wildflowers")
        if not sl_subs:
            sl_subs.append("Still Life")
        _add_cat("Still Life & Cultural Details", sl_subs)

    # 9. Wildlife & Animals vs. Pets & Animals — Strictly gated by verified discrete subject tags or Contrastive Foil Probes
    kw_words = set(re.findall(r"[a-z0-9]+", " ".join(str(x).lower() for x in flat_kws + hier_kws)))
    has_verified_pets = (
        bool(probes.get("has_dog"))
        or bool(probes.get("has_cat"))
        or bool(kw_words & {"dog", "dogs", "puppy", "chihuahua", "terrier", "cat", "cats", "kitten", "feline", "pet", "pets"})
    )
    if has_verified_pets:
        pet_subs = ["Pets"]
        if probes.get("has_dog") or bool(kw_words & {"dog", "dogs", "puppy", "chihuahua", "terrier", "canine"}):
            pet_subs.append("Dog")
        if probes.get("has_cat") or bool(kw_words & {"cat", "cats", "kitten", "feline"}):
            pet_subs.append("Cat")
        _add_cat("Pets & Animals", pet_subs)

    has_verified_wildlife = (
        bool(probes.get("has_wildlife"))
        or bool(probes.get("has_bison"))
        or bool(probes.get("has_horse"))
        or bool(probes.get("has_cattle"))
        or bool(probes.get("has_bird"))
        or bool(probes.get("has_frog"))
        or bool(probes.get("has_deer"))
        or bool(probes.get("has_bear"))
        or bool(kw_words & {"bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "bird", "birds", "heron", "egret", "pelican", "hawk", "eagle", "elk", "deer", "sheep", "frog", "frogs", "bear", "bears", "wildlife"})
    )
    if has_verified_wildlife:
        wl_subs = ["Wildlife"]
        if probes.get("has_bison") or bool(kw_words & {"bison", "buffalo"}):
            wl_subs.append("Bison")
        if probes.get("has_horse") or probes.get("has_cattle") or bool(kw_words & {"horse", "horses", "cattle", "cow", "cows", "livestock", "equine"}):
            wl_subs.append("Horses & Cattle")
        if probes.get("has_bird") or bool(kw_words & {"bird", "birds", "heron", "egret", "pelican", "hawk", "eagle", "owl", "sandhill", "waterfowl", "gull"}):
            wl_subs.append("Bird")
        _add_cat("Wildlife & Animals", wl_subs)

    # 10. Portraits & People
    if (
        bool(probes.get("has_person"))
        or bool(probes.get("has_mirror_selfie"))
        or bool(kw_words & {"person", "people", "man", "woman", "portrait", "selfie"})
    ):
        pp_subs = ["People"]
        if probes.get("has_mirror_selfie") or "selfie" in kw_words:
            pp_subs.append("Mirror Selfie")
        _add_cat("Portraits & People", pp_subs)

    # 11. Automotive & Urban
    if (
        bool(probes.get("has_car"))
        or bool(probes.get("has_sports_car"))
        or bool(probes.get("has_gas_station"))
        or bool(kw_words & {"car", "sedan", "coupe", "lexus", "vehicle", "automobile", "truck"})
    ):
        au_subs = []
        if probes.get("has_sports_car") or probes.get("has_car") or bool(kw_words & {"car", "sedan", "coupe", "lexus", "vehicle", "automobile"}):
            au_subs.append("Car")
        if probes.get("has_gas_station") or "gas station" in blob:
            au_subs.append("Gas Station")
        _add_cat("Automotive & Urban", au_subs)

    # 12. Architecture & Interiors
    if (
        bool(probes.get("has_living_room"))
        or bool(probes.get("has_fitting_room"))
        or bool(kw_words & {"living", "interior", "room", "bedroom", "kitchen", "couch", "sofa", "carpet", "rug"})
    ):
        ai_subs = []
        if probes.get("has_living_room") or "living room" in blob:
            ai_subs.append("Living Room")
        if probes.get("has_fitting_room") or "fitting room" in blob:
            ai_subs.append("Fitting Room")
        _add_cat("Architecture & Interiors", ai_subs)

    # Fallback if no category matched yet: NEVER blindly default to "National Parks & Mountains" for general photos!
    if not categories:
        scene_ctx = str(probes.get("scene_context") or "outdoor_nature")
        if scene_ctx == "indoor_domestic":
            _add_cat("Architecture & Interiors", [])
        elif scene_ctx == "mirror_portrait":
            _add_cat("Portraits & People", [])
        elif scene_ctx == "urban_automotive":
            _add_cat("Automotive & Urban", [])
        elif state in ("Utah", "Arizona", "New Mexico", "Nevada") and float(probes.get("sc_outdoor_nature_sim", 0.0)) >= 0.20:
            _add_cat("Desert", ["Desert"])
        elif state in ("Wyoming", "Montana", "Colorado", "Washington") and float(probes.get("sc_outdoor_nature_sim", 0.0)) >= 0.20:
            _add_cat("National Parks & Mountains", ["Mountains"])
        else:
            _add_cat("Everyday & Lifestyle", [])

    # Update hierarchical_keywords with Portfolio|<Category> and strip all old Visual_Facets / Lighting / Atmosphere / schema placeholder noise
    clean_hier: List[str] = []
    for hk in hier_kws:
        hk_str = str(hk or "").strip()
        if not hk_str:
            continue
        hk_low = hk_str.lower()
        if hk_low.startswith(("visual_facets|", "lighting|", "atmosphere|sky", "portfolio|", "perspective|")):
            continue
        if any(bad_seg in hk_low for bad_seg in ("|specific", "|feature", "|subcategory", "|category|", "subjects|category")):
            continue
        if not is_aerial and hk_low.startswith("aerial|"):
            continue
        if hk_str not in clean_hier:
            clean_hier.append(hk_str)

    for cat in categories:
        p_hier = f"Portfolio|{cat}"
        if p_hier not in clean_hier:
            clean_hier.append(p_hier)

    return categories, theme_tags, clean_hier


def synthesize_5facet_visual_keywords(
    record: Dict[str, Any],
    probes: Dict[str, Any],
    flat_kws: List[str],
    hier_kws: List[str],
    primary_category: str = "Landscape",
    country: Optional[str] = None,
    state_region: Optional[str] = None,
    specific_location: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    """
    Clean Photographer Keyword & 10,000-Foot Portfolio Category Engine:
    - Purges all art-school compositional/lighting/color/surface jargon (`_FACET1..5`, `Visual_Facets|...`).
    - Strips workflow strings (`TO PRINT`, `Alice`, `Mitch Rouse Aerials`, `Not specified`, etc.) and hallucinated micro-locations.
    - Normalizes concrete VLM subject tags (`sandstone_butte` -> `Butte`, `grain_elevator` -> `Grain Elevator`).
    - Assigns high-precision 10,000-Foot Portfolio Categories (`Portfolio|<Category>`) and searchable photographer tags.
    - Separates visual keywords from location metadata (`City`, `County`, `State`, `Country` live in `📍 Location Metadata`,
      not duplicated as 5 redundant GPS tag pills in `Keywords & Studio Tags`).
    """
    is_aerial = bool(probes.get("is_aerial", record.get("is_aerial")))
    ctry = str(country if country is not None else (record.get("country") or "")).strip()
    if ctry.lower() in ("unknown", "none", "general", "not specified"):
        ctry = ""
    state = str(state_region if state_region is not None else (record.get("state_region") or "")).strip()
    if state.lower() in ("unknown", "none", "general", "not specified"):
        state = ""
    city = str(record.get("city") or "").strip()
    if city.lower() in ("unknown", "none", "general", "not specified"):
        city = ""
    sub_loc = str(record.get("sub_location") or "").strip()
    if sub_loc.lower() in ("unknown", "none", "general", "not specified"):
        sub_loc = ""
    spec = str(specific_location if specific_location is not None else (record.get("specific_location") or "")).strip()
    if spec.lower() in ("unknown", "none", "general", "not specified"):
        spec = ""

    taught_low_set = {str(t).strip().lower() for t in _safe_json_list(record.get("user_taught_tags")) if str(t).strip()}

    # Build the set of structured GPS / municipal location values already displayed in Location Metadata
    redundant_loc_low = {"united states"}
    for lv in (city, sub_loc, state, ctry):
        if lv:
            redundant_loc_low.add(lv.lower())
    if city and state:
        redundant_loc_low.add(f"{city}, {state}".lower())
    is_gps_record = (
        int(record.get("gps_ground_truth") or 0) == 1
        or record.get("gps_lat") is not None
        or str(record.get("location_provenance") or "") in ("exif_gps", "same_day_gps")
        or (city and state and spec.lower() == f"{city}, {state}".lower())
    )
    if is_gps_record and spec:
        redundant_loc_low.add(spec.lower())

    out_flat: List[str] = []
    seen_low = set()

    def _add_clean(raw_t: Optional[str]) -> None:
        cleaned = _clean_single_photographer_tag(raw_t or "", is_aerial=is_aerial)
        if not cleaned:
            return
        c_low = cleaned.lower()
        # Never duplicate structured municipal/GPS location strings or County names in visual studio tags unless user-taught
        if c_low not in taught_low_set:
            if c_low in redundant_loc_low or c_low.endswith(" county"):
                return
        if c_low not in seen_low:
            seen_low.add(c_low)
            out_flat.append(cleaned)

    # 1. Compute 10,000-Foot Portfolio Categories & Sub-Region Theme Tags first
    categories, theme_tags, clean_hier = assign_portfolio_categories(
        record=record,
        probes=probes,
        flat_kws=flat_kws,
        hier_kws=hier_kws,
        country=ctry,
        state_region=state,
        specific_location=spec,
    )

    # 2. Only add named iconic landmarks (not reverse-geocoded GPS municipal addresses) and visual theme tags
    if spec and not is_gps_record and spec.lower() not in HALLUCINATED_SPEC_LOCATIONS_LOWER:
        _add_clean(spec)
    for tt in theme_tags:
        _add_clean(tt)

    # 3. Add cleaned concrete subject & .lrcat keywords from flat_kws
    for k in flat_kws:
        _add_clean(k)

    # 4. Add concrete high-confidence visual subjects from OpenCLIP & Multi-Region probes ONLY when genuinely present
    if bool(probes.get("has_dog")):
        _add_clean("Dog")
    if bool(probes.get("has_cat")):
        _add_clean("Cat")
    if bool(probes.get("has_cat_tree")):
        _add_clean("Cat Tree")
    if bool(probes.get("has_living_room")):
        _add_clean("Living Room")
    if bool(probes.get("has_carpet_rug")):
        _add_clean("Carpet")
    if bool(probes.get("has_framed_art")):
        _add_clean("Framed Art")
    if bool(probes.get("has_mirror_selfie")):
        _add_clean("Mirror Selfie")
        _add_clean("Man")
        _add_clean("Person")
    if bool(probes.get("has_fitting_room")):
        _add_clean("Fitting Room")
    if bool(probes.get("has_sports_car")):
        _add_clean("Sports Car")
        _add_clean("Sedan")
        _add_clean("Car")
    elif bool(probes.get("has_car")):
        _add_clean("Car")
    if bool(probes.get("has_gas_station")):
        _add_clean("Gas Station")
    if bool(probes.get("is_night_artificial")):
        _add_clean("Night")
        _add_clean("Artificial Lighting")
    if float(probes.get("f2_doors_windows_sim", 0.0)) >= 0.225 or float(probes.get("lm_colonial_doors_sim", 0.0)) >= 0.225:
        _add_clean("Doors & Windows")
    if bool(probes.get("has_boat")):
        _add_clean("Boat")
    if float(probes.get("f2_snow_ice_sim", 0.0)) >= 0.245:
        _add_clean("Snow & Ice")
    for boosted_lbl in probes.get("boosted_custom_labels", []):
        _add_clean(boosted_lbl)
    if is_aerial:
        _add_clean("Aerial")

    # 4B. Pure-Vision Fallback when flat_kws was wiped/empty and no specialized object probe fired:
    # Populate top concrete OpenCLIP scene/feature tags so `⚡ Basic Tag` never leaves a photo with 0 tags.
    if not out_flat:
        scene_ctx = str(probes.get("scene_context") or "outdoor_nature")
        if scene_ctx == "indoor_domestic":
            _add_clean("Indoor")
            _add_clean("Interior")
        elif scene_ctx == "mirror_portrait":
            _add_clean("Portrait")
            _add_clean("Indoor")
        elif scene_ctx == "urban_automotive":
            _add_clean("Urban")
            _add_clean("Street")
        fallback_probe_map = (
            ("f1_mountain_peak_sim", ("Mountains", "Landscape")),
            ("f1_canyon_mesa_sim", ("Canyon", "Sandstone")),
            ("f1_coastline_surf_sim", ("Coastline", "Ocean")),
            ("f1_river_waterway_sim", ("River", "Water")),
            ("f1_lake_lagoon_sim", ("Lake", "Water")),
            ("f1_forest_woods_sim", ("Forest", "Trees")),
            ("f1_desert_arid_sim", ("Desert", "Landscape")),
            ("f1_ranch_pasture_sim", ("Farmland", "Pasture")),
            ("f1_barn_farmstead_sim", ("Barn", "Ranch")),
            ("f1_colonial_facade_sim", ("Building", "Architecture")),
            ("f1_industrial_facility_sim", ("Industrial", "Structure")),
            ("f1_urban_skyline_sim", ("Urban", "Architecture")),
            ("f2_doors_windows_sim", ("Doors & Windows", "Architecture")),
            ("f2_archway_courtyard_sim", ("Archway", "Architecture")),
            ("f2_fence_corral_sim", ("Fence", "Rural")),
            ("f2_bridge_pier_sim", ("Bridge", "Structure")),
            ("f2_rock_outcrop_sim", ("Rock Formation", "Geology")),
            ("f2_foreground_flora_sim", ("Flora", "Plants")),
            ("f2_water_reflection_sim", ("Water", "Reflection")),
            ("f2_road_pathway_sim", ("Road", "Pathway")),
            ("f2_clouds_sky_sim", ("Clouds", "Sky")),
            ("f2_snow_ice_sim", ("Snow & Ice", "Winter")),
        )
        scored_fallbacks = sorted(
            ((float(probes.get(pk, 0.0)), tags_tuple) for pk, tags_tuple in fallback_probe_map),
            key=lambda x: x[0],
            reverse=True,
        )
        for sim_val, tags_tuple in scored_fallbacks[:2]:
            if sim_val >= 0.215:
                for ft in tags_tuple:
                    _add_clean(ft)
        if not out_flat:
            if scene_ctx == "indoor_domestic":
                _add_clean("Indoor")
            elif categories and categories[0] == "Everyday & Lifestyle":
                _add_clean("Everyday")
                _add_clean("Lifestyle")
            else:
                _add_clean("Landscape")

    # Note: Do NOT dump internal Portfolio Category container names (e.g., "National Parks & Mountains") into key_subjects!
    # Portfolio categories are stored in `Portfolio|<Category>` inside `hierarchical_keywords` and `primary_category`.

    # 5. Deduplicate singular/plural pairs (never emit both Boat & Boats, Bird & Birds, Butte & Buttes, etc.)
    out_flat = deduplicate_singular_plural_tags(out_flat, subject_counts=probes.get("subject_counts"))

    return out_flat, clean_hier


# (_TEACH_GEO_GAZETTEER and _TEACH_SUBJECT_CONCEPTS imported from domain_gazetteer.py)


_WIPE_INTENT_REGEX = re.compile(
    r"\b(?:wipe(?:\s+(?:the|all|existing))?(?:\s+tags)?|clear\s+(?:all\s+|the\s+|existing\s+)?tags|start\s+fresh|reset\s+(?:all\s+|the\s+|existing\s+)?tags|cater\s+(?:them|these|it|tags)?\s*around|rebuild\s+(?:them|these|it|tags)?\s*(?:around|from))\b",
    re.IGNORECASE,
)

# Visual inspection / re-scan directives spoken in natural language (e.g. "bro just look at it and tag what's in there")
_VISUAL_INSPECT_DIRECTIVE_REGEX = re.compile(
    r"\b(?:just\s+look(?:\s+at\s+(?:it|this|these|them))?|look\s+(?:closely\s+)?at\s+(?:it|this|these|them|the\s+(?:photo|image|picture|frame))|tag\s+what(?:'s|s|\s+is)\s+in\s+(?:there|it|this|here)|tell\s+me\s+what(?:'s|s|\s+is)\s+in|what(?:'s|s|\s+is)\s+in\s+(?:there|this\s+(?:photo|image|picture))|what\s+do\s+you\s+see|what\s+you\s+see|reassess(?:\s+what\s+you\s+see)?|rescan(?:\s+(?:it|this|these))?|scan\s+(?:it|this|these)\s+again|inspect\s+(?:it|this|these))\b",
    re.IGNORECASE,
)

# Conversational command intros spoken in natural run-on speech transcripts (e.g., Web Speech API)
_SPEECH_COMMAND_INTRO_PATTERNS = [
    re.compile(
        r"\b(?:bro\s+|dude\s+|man\s+|hey\s+|so\s+|and\s+|also\s+|then\s+|well\s+|okay\s+|um\s+|uh\s+)*"
        r"(?:just\s+)?(?:look(?:\s+closely)?(?:\s+at\s+(?:it|this|these|them|the\s+(?:photo|image|picture)))?\s*(?:and\s+)?)?"
        r"(?:tag\s+what(?:'s|s|\s+is)\s+in\s+(?:there|it|this|here)|tell\s+me\s+what(?:'s|s|\s+is)\s+in\s+(?:there|it|this|here)|reassess(?:\s+what\s+you\s+see)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+|well\s+|okay\s+|um\s+|uh\s+)*"
        r"(?:(?:these|this|those|they|it)\s+)?"
        r"(?:i\s+(?:also\s+|really\s+|just\s+)?(?:want|would\s+like|need)\s+(?:you\s+to\s+)?)?"
        r"(?:(?:these|this|those|them|it|the\s+(?:photos?|images?|frames?|pictures?|shots?))\s+)?"
        r"(?:to\s+be\s+|to\s+have\s+|should\s+be\s+|should\s+have\s+|need\s+to\s+be\s+)?"
        r"(?:tagged\s+(?:as|with|around|for)|tags?\s+(?:around|for|as|of|with|like)|tag(?:ged)?\s+(?:this|these|them|it)?\s*(?:as|with|around|for)|labeled\s+(?:as|with)|called|named)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+)*"
        r"(?:i\s+(?:also\s+|just\s+)?(?:want|would\s+like|need)\s+to\s+)"
        r"(?:tag|add(?:\s+tags?)?|label|call|name|put)\s*"
        r"(?:(?:these|this|them|it|the\s+(?:photos?|images?|frames?))\s*)?"
        r"(?:as|with|around|for)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+)*(?:please\s+)?"
        r"(?:cater|rebuild|center|focus|base)\s+"
        r"(?:(?:this|these|them|it|the\s+(?:location|tags?|photos?|images?)|location|tags?)\s+)?"
        r"(?:around|on|off(?:\s+of)?|from)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+)*(?:please\s+)?"
        r"(?:add|include|put|give\s+(?:it|them|this|these))\s+"
        r"(?:(?:the|some)\s+)?(?:tags?|keywords?|labels?)\s*"
        r"(?:around|for|as|of|with|to\s+be)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+)*"
        r"(?:(?:these|this|they|it)\s+)?(?:were|was|are|is)\s+"
        r"(?:taken|shot|photographed|captured|filmed)\s+(?:in|at|near|around|on|by)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|then\s+)*"
        r"(?:there\s+(?:are|is|were|was)|(?:this|it)\s+(?:has|shows|is\s+showing|is\s+a|is\s+an)|(?:these|they)\s+(?:have|show|are\s+showing|are))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:so\s+|and\s+|also\s+|please\s+)*"
        r"(?:find|search(?:\s+for)?|look\s+for|scout(?:\s+for)?|show(?:\s+me)?)\s*"
        r"(?:(?:all(?:\s+the)?|any|every|some)\s+)?"
        r"(?:(?:photos?|images?|pictures?|frames?|shots?)\s+(?:of|with|that\s+have|showing|featuring)\s+)?",
        re.IGNORECASE,
    ),
]

_CUSTOM_PHRASE_STOPWORDS = {
    "a", "an", "the", "this", "these", "that", "those", "it", "them", "they",
    "i", "we", "you", "me", "my", "our", "want", "would", "like", "need",
    "to", "be", "have", "has", "had", "is", "are", "was", "were", "tagged",
    "tag", "tags", "around", "as", "with", "for", "of", "in", "at", "on",
    "from", "off", "base", "based", "cater", "catered", "location", "photo",
    "photos", "image", "images", "picture", "pictures", "frame", "frames",
    "shot", "shots", "please", "also", "and", "or", "so", "well", "okay",
    "there", "here", "some", "all", "existing", "metadata", "keywords",
    "bro", "dude", "hey", "just", "look", "looking", "closely", "what",
    "what's", "whats", "tell", "see", "seeing", "reassess", "rescan", "scan",
    "inspect", "describe", "identify", "figure", "out", "whatever", "inside",
}

_ACRONYM_UPPER_KEEP = {"usa", "us", "uk", "uae", "dc", "nyc", "la", "sf", "ii", "iii", "iv", "rv", "suv", "atv"}


def _title_case_custom_tag(raw_phrase: str) -> str:
    """Formats a user-spoken custom tag into clean Title Case while preserving numbers and acronyms."""
    words = [w for w in re.split(r"\s+", raw_phrase.strip()) if w]
    if not words:
        return ""
    small_joiners = {"of", "the", "and", "in", "on", "at", "by", "for", "to"}
    out_words: List[str] = []
    for idx, w in enumerate(words):
        w_low = w.lower()
        if w_low in _ACRONYM_UPPER_KEEP:
            out_words.append(w_low.upper())
        elif idx > 0 and idx < len(words) - 1 and w_low in small_joiners:
            out_words.append(w_low)
        elif w[0].isdigit():
            out_words.append(w)
        else:
            out_words.append(w.capitalize())
    return " ".join(out_words)


def _extract_custom_user_phrases(pos_blob: str) -> List[str]:
    """
    Splits run-on speech transcripts on conversational command boundaries and extracts
    the user's intended custom noun/tag phrases verbatim (e.g., "Mitch Rouse Residence",
    "Pickles", "12 Cows"), even if they do not exist in any preset ontology dictionary.
    """
    if not pos_blob or not pos_blob.strip():
        return []

    work = pos_blob.strip()
    matched_command = False
    for pat in _SPEECH_COMMAND_INTRO_PATTERNS:
        if pat.search(work):
            matched_command = True
            work = pat.sub(" |CMD| ", work)

    # Also split on prepositional facility/location connectors inside a clause ("at an oil facility", "in a barn")
    work = re.sub(
        r"\b(?:at|in|inside|near|with)\s+(?:a|an|the)\s+",
        " |CMD| ",
        work,
        flags=re.IGNORECASE,
    )

    if matched_command or "|CMD|" in work:
        raw_segments = [s.strip() for s in work.split("|CMD|") if s.strip()]
    else:
        # User typed or spoke direct tag phrases without conversational intros (e.g. "Mitch Rouse Residence, Pickles")
        raw_segments = [ work ]

    extracted: List[str] = []
    for seg in raw_segments:
        # Sub-split on explicit list separators (comma, slash, "and", "plus", "also")
        sub_parts = re.split(
            r"\s*(?:[,;/]|(?:\b(?:and|plus|also|as\s+well\s+as)\b))\s*",
            seg,
            flags=re.IGNORECASE,
        )
        for sp in sub_parts:
            tokens = [
                t for t in re.findall(r"[a-zA-Z0-9'\-]+", sp.strip())
                if t.strip("'-")
            ]
            # Strip leading filler/stopwords ("a", "the", "so", "these", "around", etc.)
            while tokens and tokens[0].lower() in _CUSTOM_PHRASE_STOPWORDS:
                tokens.pop(0)
            # Strip trailing filler/stopwords ("please", "too", "tags", "photo", etc.)
            while tokens and tokens[-1].lower() in _CUSTOM_PHRASE_STOPWORDS:
                tokens.pop()

            if not tokens or len(tokens) > 6:
                continue
            # Ignore if all remaining tokens are stopwords
            if all(t.lower() in _CUSTOM_PHRASE_STOPWORDS for t in tokens):
                continue

            candidate = _title_case_custom_tag(" ".join(tokens))
            if candidate and len(candidate) >= 2 and candidate not in extracted:
                extracted.append(candidate)

    return extracted


def parse_natural_language_teach(
    instruction: str,
    explicit_add_tags: Optional[List[str]] = None,
    explicit_remove_tags: Optional[List[str]] = None,
    wipe_existing: bool = False,
) -> Dict[str, Any]:
    """
    Parses a natural-language correction or teaching note from the photographer
    (e.g., "These were taken in Houma Louisiana at an oil facility, not Venice",
    "Wipe the tags on these images and cater them around South America / Cuba", or
    "so these I want these to be tagged as Mitch Rouse residence I want this to have tags around pickles")
    into structured positive locations, verbatim custom user phrases + expanded ontology tags,
    negated/contradicted tags, and Clean-Slate Wipe & Re-Anchor mode (`wipe_mode`).
    """
    text = str(instruction or "").strip()
    if text in ("[CLEARED_SLATE]", "bro just look at it and tag what's in there"):
        if text == "[CLEARED_SLATE]":
            text = ""
    auto_wipe_detected = bool(_WIPE_INTENT_REGEX.search(text))
    visual_inspect_requested = bool(_VISUAL_INSPECT_DIRECTIVE_REGEX.search(text))
    wipe_mode = bool(wipe_existing or auto_wipe_detected)

    # Strip meta-command prefixes ("Wipe the tags on these images and cater them around ...", "bro just look at it and tag what's in there")
    cleaned_text = re.sub(
        r"\b(?:please\s+)?(?:wipe|clear|reset)\s+(?:all\s+|the\s+|existing\s+)?(?:tags|metadata|locations)?(?:\s+on\s+(?:these|this|the)\s+(?:images?|photos?|frames?))?\s*(?:and\s+)?(?:cater\s+(?:them|these|it)?\s*around|rebuild\s+(?:them|these|it)?\s*(?:around|from)|start\s+fresh(?:\s+with|\s+around)?)?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    cleaned_text = _VISUAL_INSPECT_DIRECTIVE_REGEX.sub(" ", cleaned_text)
    cleaned_text = re.sub(
        r"\b(?:cater\s+(?:them|these|it|the\s+tags)\s+around|rebuild\s+(?:them|these|it|the\s+tags)\s+(?:around|from)|start\s+fresh\s+(?:with|around))\b",
        " ",
        cleaned_text,
        flags=re.IGNORECASE,
    ).strip()

    negated_tags: List[str] = list(explicit_remove_tags or [])
    added_tags: List[str] = list(explicit_add_tags or [])
    resolved_country: Optional[str] = None
    resolved_state: Optional[str] = None
    resolved_city: Optional[str] = None
    resolved_spec: Optional[str] = None
    force_aerial: Optional[bool] = None

    # Split clauses on comma/semicolon/period/pipe to isolate negated clauses ("not X", "isn't X", "never X", "remove X")
    clauses = [c.strip() for c in re.split(r"[,;.|]|\bbut\b|\band\s+not\b", cleaned_text or text) if c.strip() and c.strip() != "[CLEARED_SLATE]"]
    positive_clauses: List[str] = []

    neg_pattern = re.compile(
        r"\b(?:not\s+in|not\s+at|not\s+from|not\s+a|not\s+an|not|isn't|isnt|aren't|arent|wasn't|wasnt|weren't|werent|never|remove|delete|strip)\s+([a-zA-Z0-9\s\-']+)",
        re.IGNORECASE,
    )

    for cl in clauses:
        m = neg_pattern.search(cl)
        if m:
            # Everything before the negation match in the same clause is still positive!
            prefix_pos = cl[: m.start()].strip()
            if prefix_pos:
                positive_clauses.append(prefix_pos)
            neg_phrase = m.group(1).strip().lower()
            # Ignore meta-nouns like "tags" or "existing tags" if "remove existing tags" was spoken
            if neg_phrase in ("tags", "the tags", "all tags", "existing tags", "old tags", "metadata"):
                continue
            matched_known = False
            for gkey, ginfo in _TEACH_GEO_GAZETTEER.items():
                if re.search(rf"\b{re.escape(gkey)}\b", neg_phrase):
                    matched_known = True
                    for t in ginfo.get("tags", []):
                        if t not in negated_tags:
                            negated_tags.append(t)
                    for fld in ("city", "state_region", "specific_location"):
                        if ginfo.get(fld) and ginfo[fld] not in negated_tags:
                            negated_tags.append(ginfo[fld])
                    if ginfo.get("country") and ginfo["country"].lower() == gkey and ginfo["country"] not in negated_tags:
                        negated_tags.append(ginfo["country"])
            for skey, stags in _TEACH_SUBJECT_CONCEPTS.items():
                if re.search(rf"\b{re.escape(skey)}\b", neg_phrase):
                    matched_known = True
                    if stags[0] not in negated_tags:
                        negated_tags.append(stags[0])
            if "aerial" in neg_phrase:
                force_aerial = False
                negated_tags.append("Aerial")
            elif "terrestrial" in neg_phrase:
                force_aerial = True
                negated_tags.append("Terrestrial")
            if not matched_known and neg_phrase:
                clean_neg = neg_phrase.title()
                if clean_neg not in negated_tags:
                    negated_tags.append(clean_neg)
        else:
            positive_clauses.append(cl)

    pos_blob = " ".join(positive_clauses)
    pos_low = pos_blob.lower()

    # 1. Extract open-vocabulary custom phrases spoken by the user (e.g., "Mitch Rouse Residence", "Pickles", "12 Cows")
    custom_user_phrases = _extract_custom_user_phrases(pos_blob)

    # 2. Detect positive geographic locations in order of specificity (longer keys first)
    geo_matched_tags: List[str] = []
    for gkey in sorted(_TEACH_GEO_GAZETTEER.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(gkey)}\b", pos_low):
            ginfo = _TEACH_GEO_GAZETTEER[gkey]
            if ginfo.get("country") and not resolved_country:
                resolved_country = ginfo["country"]
            if ginfo.get("state_region") and not resolved_state:
                resolved_state = ginfo["state_region"]
            if ginfo.get("city") and not resolved_city:
                resolved_city = ginfo["city"]
            if ginfo.get("specific_location") and not resolved_spec:
                resolved_spec = ginfo["specific_location"]
            for t in ginfo.get("tags", []):
                if t not in geo_matched_tags:
                    geo_matched_tags.append(t)

    # 3. Detect positive subject/facility/landmark concepts
    ontology_matched_tags: List[str] = []
    for skey in sorted(_TEACH_SUBJECT_CONCEPTS.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(skey)}\b", pos_low):
            for st in _TEACH_SUBJECT_CONCEPTS[skey]:
                if st not in ontology_matched_tags:
                    ontology_matched_tags.append(st)

    # 4. Also check multi-tier ontologies (_ANIMAL_ONTOLOGY, _PEOPLE_ONTOLOGY, _FLORA_ONTOLOGY, _STRUCTURE_ONTOLOGY)
    for ont_dict in (_ANIMAL_ONTOLOGY, _PEOPLE_ONTOLOGY, _FLORA_ONTOLOGY, _STRUCTURE_ONTOLOGY):
        for okey, (spec, mids, parents, _) in ont_dict.items():
            if re.search(rf"\b{re.escape(okey)}\b", pos_low):
                for tag_item in [spec] + list(mids) + list(parents):
                    if tag_item not in ontology_matched_tags:
                        ontology_matched_tags.append(tag_item)

    if re.search(r"\baerial\b|\bhelicopter\b|\bfrom the air\b", pos_low):
        force_aerial = True
        if "Aerial" not in ontology_matched_tags:
            ontology_matched_tags.append("Aerial")
    elif re.search(r"\bterrestrial\b|\bground level\b", pos_low):
        force_aerial = False
        if "Terrestrial" not in ontology_matched_tags:
            ontology_matched_tags.append("Terrestrial")

    # Place custom user-spoken phrases FIRST in priority (skipping any phrase that is purely a space-joined duplicate of 2 already-matched geo tags like "Houma Louisiana")
    known_geo_low = {gt.lower() for gt in geo_matched_tags}
    for cphrase in custom_user_phrases:
        cp_words = cphrase.lower().split()
        if len(cp_words) >= 2 and all(w in known_geo_low for w in cp_words) and cphrase.lower() not in known_geo_low:
            continue
        if cphrase.lower() not in {a.lower() for a in added_tags}:
            added_tags.append(cphrase)

    for gt in geo_matched_tags + ontology_matched_tags:
        if gt.lower() not in {a.lower() for a in added_tags}:
            added_tags.append(gt)

    # Also ensure resolved positive locations are included in added_tags and never in negated_tags
    pos_loc_values = [v for v in (resolved_city, resolved_state, resolved_country, resolved_spec) if v]
    for ploc in pos_loc_values:
        if ploc.lower() not in {a.lower() for a in added_tags}:
            added_tags.append(ploc)
    pos_loc_lower = {v.lower().strip() for v in pos_loc_values}
    negated_tags = [n for n in negated_tags if n.lower().strip() not in pos_loc_lower]

    # Ensure Specific Location combines facility + city/state when both are present (e.g., "Oil Facility, Houma, Louisiana")
    if resolved_city and resolved_state:
        if any("oil facility" in t.lower() for t in added_tags):
            resolved_spec = f"Oil Facility — {resolved_city}, {resolved_state}"
        elif not resolved_spec:
            resolved_spec = f"{resolved_city}, {resolved_state}"

    # Remove any accidentally overlapping negated tags from added_tags
    neg_low_set = {n.lower().strip() for n in negated_tags}
    added_tags = [t for t in added_tags if t.lower().strip() not in neg_low_set]

    dedup_added: List[str] = []
    seen_add_low: set = set()
    for t in added_tags:
        tl = t.strip().lower()
        if tl and tl not in seen_add_low:
            seen_add_low.add(tl)
            dedup_added.append(t.strip())

    dedup_negated = list(dict.fromkeys(negated_tags))
    location_updates = {
        k: v
        for k, v in {
            "country": resolved_country,
            "state_region": resolved_state,
            "city": resolved_city,
            "specific_location": resolved_spec,
        }.items()
        if v
    }

    return {
        "instruction": text,
        "intent": "visual_inspect" if (visual_inspect_requested and not dedup_added) else "explicit_teach",
        "visual_inspect_requested": visual_inspect_requested,
        "wipe_mode": wipe_mode,
        "wipe_detected_from_speech": auto_wipe_detected,
        "custom_user_tags": custom_user_phrases,
        "added_tags": dedup_added,
        "positive_tags": dedup_added,
        "negated_tags": dedup_negated,
        "country": resolved_country,
        "state_region": resolved_state,
        "city": resolved_city,
        "specific_location": resolved_spec,
        "location_updates": location_updates,
        "force_aerial": force_aerial,
    }


def discover_visual_subjects_for_records(
    records: List[Dict[str, Any]],
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    encode_text_batch_fn: Optional[Callable[[List[str]], Dict[str, np.ndarray]]] = None,
) -> Dict[str, Any]:
    """
    Runs Multi-Region Subject Detection + Scene-Aware OpenCLIP Concept Probes +
    Ontology Synthesis on the target photo record(s) when the user issues a
    visual inspection directive (e.g., "bro just look at it and tag what's in there",
    "look closely and tell me what's in this photo", "reassess what you see").
    Returns the discovered visual tags, per-photo tags, and bounding boxes.
    """
    if not records:
        return {"discovered_tags": [], "per_photo_tags": {}, "per_photo_boxes": {}, "per_photo_verified": {}}
    vectors = load_or_init_vectors_matrix(vectors_path)
    probes_map = compute_clip_concept_probes_for_rows(
        rows=records,
        vectors=vectors,
        encode_text_batch_fn=encode_text_batch_fn,
        db_path=db_path,
    )
    discovered_all: List[str] = []
    per_photo_tags: Dict[str, List[str]] = {}
    per_photo_boxes: Dict[str, List[Dict[str, Any]]] = {}
    per_photo_verified: Dict[str, List[str]] = {}

    for r in records:
        fp = r["file_path"]
        probes = probes_map.get(fp, {})
        seed_flat = [
            k for k in _safe_json_list(r.get("key_subjects"))
            if str(k or "").strip().lower() not in ("bro just look", "what's", "whats", "national parks & mountains", "eye-level terrestrial", "eye-level", "terrestrial", "unsharp", "sharp")
        ]
        if probes.get("is_night_artificial"):
            seed_flat = [k for k in seed_flat if str(k).strip().lower() != "midday sun"]
        exp_flat, exp_hier = expand_hierarchical_ontology(
            flat_kws=seed_flat,
            hier_kws=_safe_json_list(r.get("hierarchical_keywords")),
            record=r,
            clip_probes=probes,
        )
        synth_flat, _ = synthesize_5facet_visual_keywords(
            record=r,
            probes=probes,
            flat_kws=exp_flat,
            hier_kws=exp_hier,
            primary_category=str(r.get("primary_category") or "Everyday & Lifestyle"),
            country=r.get("country"),
            state_region=r.get("state_region"),
            specific_location=r.get("specific_location"),
        )
        per_photo_tags[fp] = synth_flat
        per_photo_boxes[fp] = probes.get("subject_boxes", [])
        per_photo_verified[fp] = probes.get("verified_subjects", [])
        for t in synth_flat:
            if t not in discovered_all:
                discovered_all.append(t)

    return {
        "discovered_tags": discovered_all,
        "per_photo_tags": per_photo_tags,
        "per_photo_boxes": per_photo_boxes,
        "per_photo_verified": per_photo_verified,
    }


def apply_clean_slate_wipe_to_record(
    rec: Optional[Dict[str, Any]] = None,
    parsed_teach: Optional[Dict[str, Any]] = None,
    rdict: Optional[Dict[str, Any]] = None,
    instruction_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes "Clean-Slate Wipe & Re-Anchor" on a single photo record:
    1. Clears all existing AI-generated geographic fields (`country`, `state_region`, `city`,
       `specific_location`, `sub_location`) and existing `key_subjects` / `hierarchical_keywords`.
    2. Quarantines the old/wiped geographic locations and wrong regional/style tags into
       `negated_tags` so they can never bounce back—WITHOUT blocking valid generic visual nouns
       (like `Door`, `Doors & Windows`, `Building`, `Water`, `Coastline`, `Boat`, `Tree`, `Mountain`, etc.
       in `_GENERIC_VISUAL_NOUNS_KEEP`) unless the user explicitly negated them.
    3. Preserves valid generic visual nouns that were on the photo, combines them with the user's
       new positive tags (`parsed_teach["added_tags"]`), and rebuilds `hierarchical_keywords`
       and `Portfolio|<Category>` strictly around the new context.
    """
    rec = rec or rdict or {}
    parsed_teach = parsed_teach or {}
    added_tags = list(parsed_teach.get("added_tags") or [])
    explicit_negated = list(parsed_teach.get("negated_tags") or [])
    explicit_neg_low = {n.lower().strip() for n in explicit_negated if n.strip()}
    clean_instr = str(instruction_text or parsed_teach.get("instruction") or "").strip()

    # Pure "Clear Tags" (no new instruction or re-anchor target): wipe all tags cleanly to [] so the photographer starts fresh
    if not clean_instr and not added_tags:
        old_flat = _safe_json_list(rec.get("key_subjects")) + _safe_json_list(rec.get("existing_keywords")) + _safe_json_list(rec.get("lrcat_keywords"))
        wiped_list = list(dict.fromkeys(str(t).strip() for t in old_flat if str(t or "").strip()))
        is_aer_cur = bool(rec.get("is_aerial"))
        has_exif_gps = int(rec.get("gps_ground_truth") or 0) == 1 or rec.get("gps_lat") is not None
        return {
            "title": Path(str(rec.get("file_path") or "Photo")).stem,
            "caption": "",
            "country": str(rec.get("country") or "").strip() if has_exif_gps else "",
            "state_region": str(rec.get("state_region") or "").strip() if has_exif_gps else "",
            "city": str(rec.get("city") or "").strip() if has_exif_gps else "",
            "specific_location": str(rec.get("specific_location") or "").strip() if has_exif_gps else "",
            "sub_location": str(rec.get("sub_location") or "").strip() if has_exif_gps else "",
            "location_provenance": "exif_gps" if has_exif_gps else "user_cleared",
            "is_aerial": 1 if is_aer_cur else 0,
            "user_context_notes": "[CLEARED_SLATE]",
            "key_subjects": json.dumps([]),
            "existing_keywords": json.dumps([]),
            "hierarchical_keywords": json.dumps([]),
            "user_taught_tags": json.dumps([]),
            "negated_tags": json.dumps([]),
            "subject_boxes": json.dumps([]),
            "verified_subjects": json.dumps([]),
            "preserved_visual_nouns": [],
            "quarantined_tags": wiped_list,
            "wiped_and_quarantined": wiped_list,
        }

    new_country = str(parsed_teach.get("country") or "").strip()
    new_state = str(parsed_teach.get("state_region") or "").strip()
    new_city = str(parsed_teach.get("city") or "").strip()
    new_spec = str(parsed_teach.get("specific_location") or new_city or new_state or new_country or "").strip()
    for bad_loc in ("unknown", "none", "general", "not specified"):
        if new_country.lower() == bad_loc:
            new_country = ""
        if new_state.lower() == bad_loc:
            new_state = ""
        if new_city.lower() == bad_loc:
            new_city = ""
        if new_spec.lower() == bad_loc:
            new_spec = ""

    new_positive_low = {t.lower().strip() for t in added_tags if t.strip()}
    for v in (new_country, new_state, new_city, new_spec):
        if v and str(v).strip().lower() != "unknown":
            new_positive_low.add(str(v).strip().lower())

    # Gather old location fields & old tags to determine what gets quarantined vs. preserved
    old_locs = [
        str(rec.get(fld) or "").strip()
        for fld in ("country", "state_region", "city", "specific_location", "sub_location")
    ]
    old_flat = _safe_json_list(rec.get("key_subjects")) + _safe_json_list(rec.get("existing_keywords")) + _safe_json_list(rec.get("lrcat_keywords"))

    quarantined_tags: List[str] = list(explicit_negated)
    preserved_visual_nouns: List[str] = []

    for loc_val in old_locs:
        if not loc_val or loc_val.lower() in ("unknown", "none", "general", "not specified"):
            continue
        loc_low = loc_val.lower().strip()
        if loc_low not in new_positive_low and loc_low not in _GENERIC_VISUAL_NOUNS_KEEP:
            if loc_val not in quarantined_tags:
                quarantined_tags.append(loc_val)

    for old_t in old_flat:
        t_clean = str(old_t or "").strip()
        if not t_clean:
            continue
        t_low = t_clean.lower()
        if t_low in explicit_neg_low:
            if t_clean not in quarantined_tags:
                quarantined_tags.append(t_clean)
            continue
        if t_low in new_positive_low:
            continue
        # If it is a safelisted generic visual noun (Door, Doors & Windows, Building, Boat, etc.), preserve it!
        if t_low in _GENERIC_VISUAL_NOUNS_KEEP:
            if t_clean not in preserved_visual_nouns:
                preserved_visual_nouns.append(t_clean)
        else:
            # Otherwise it was an old regional/location/style guess — quarantine it in negated_tags
            if t_clean not in quarantined_tags:
                quarantined_tags.append(t_clean)

    # Merge existing negated_tags that don't conflict with the new positive tags
    for prev_neg in _safe_json_list(rec.get("negated_tags")):
        pn_clean = str(prev_neg or "").strip()
        if pn_clean and pn_clean.lower() not in new_positive_low and pn_clean not in quarantined_tags:
            quarantined_tags.append(pn_clean)

    # Build the clean re-anchored flat keywords: user's new tags first, then preserved generic visual nouns
    combined_seed_flat = list(dict.fromkeys(added_tags + preserved_visual_nouns))
    seed_hier: List[str] = []
    if new_country:
        reg_part = new_state or new_country
        loc_part = new_spec or new_city or reg_part
        if loc_part and loc_part != reg_part:
            seed_hier.append(f"Places|{new_country}|{reg_part}|{loc_part}")
        else:
            seed_hier.append(f"Places|{new_country}|{reg_part}")

    is_aer = parsed_teach.get("force_aerial")
    if is_aer is None:
        is_aer = bool(rec.get("is_aerial"))

    temp_rec = dict(rec)
    temp_rec["country"] = new_country
    temp_rec["state_region"] = new_state
    temp_rec["city"] = new_city
    temp_rec["specific_location"] = new_spec
    temp_rec["sub_location"] = ""
    temp_rec["is_aerial"] = 1 if is_aer else 0

    rebuilt_flat, rebuilt_hier = synthesize_5facet_visual_keywords(
        record=temp_rec,
        probes={"is_aerial": bool(is_aer)},
        flat_kws=combined_seed_flat,
        hier_kws=seed_hier,
        primary_category=str(rec.get("primary_category") or "Landscape"),
        country=new_country,
        state_region=new_state,
        specific_location=new_spec,
    )

    # Ensure every user-taught positive tag is present at the front and no quarantined tag remains
    quarantined_low = {q.lower().strip() for q in quarantined_tags}
    final_flat: List[str] = []
    for t in added_tags + rebuilt_flat:
        t_str = str(t or "").strip()
        if t_str and t_str.lower() not in quarantined_low and t_str not in final_flat:
            final_flat.append(t_str)
    final_flat = deduplicate_singular_plural_tags(final_flat)

    final_hier: List[str] = []
    for hk in rebuilt_hier:
        hk_str = str(hk or "").strip()
        if not hk_str:
            continue
        parts_low = [p.strip().lower() for p in hk_str.split("|") if p.strip()]
        if any(pl in quarantined_low for pl in parts_low):
            continue
        if hk_str not in final_hier:
            final_hier.append(hk_str)

    clean_title = new_spec if new_spec else (added_tags[0] if added_tags else (rec.get("title") or "Untitled"))
    clean_caption = f"{clean_title} — {', '.join(final_flat[:5])}" if final_flat else clean_title
    clean_note = str(instruction_text or parsed_teach.get("instruction") or "").strip()
    loc_prov = "user" if (new_country or new_state or new_city or new_spec) else "user_cleared"

    return {
        "title": clean_title,
        "caption": clean_caption,
        "country": new_country,
        "state_region": new_state,
        "city": new_city,
        "specific_location": new_spec,
        "sub_location": "",
        "location_provenance": loc_prov,
        "is_aerial": 1 if is_aer else 0,
        "user_context_notes": clean_note,
        "key_subjects": json.dumps(final_flat),
        "existing_keywords": json.dumps(preserved_visual_nouns),
        "hierarchical_keywords": json.dumps(final_hier),
        "user_taught_tags": json.dumps(list(dict.fromkeys(added_tags))),
        "negated_tags": json.dumps(list(dict.fromkeys(quarantined_tags))),
        "preserved_visual_nouns": preserved_visual_nouns,
        "quarantined_tags": [q for q in quarantined_tags if q not in explicit_negated],
        "wiped_and_quarantined": [q for q in quarantined_tags if q not in explicit_negated],
    }


def apply_user_teach_overrides(
    flat_kws: List[str],
    hier_kws: List[str],
    record: Dict[str, Any],
    country: Optional[str],
    state_region: Optional[str],
    city: Optional[str],
    specific_location: Optional[str],
) -> Tuple[List[str], List[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Enforces persistent photographer-taught tags (`user_taught_tags`), context notes (`user_context_notes`),
    and negated tags (`negated_tags`) on a photo record so future fast or deep reassessments NEVER revert them.
    """
    taught = _safe_json_list(record.get("user_taught_tags"))
    negated = _safe_json_list(record.get("negated_tags"))
    user_note = str(record.get("user_context_notes") or "").strip()
    if user_note == "[CLEARED_SLATE]":
        user_note = ""
    loc_prov = str(record.get("location_provenance") or "").strip()

    if loc_prov == "user_cleared":
        country = ""
        state_region = ""
        city = ""
        specific_location = ""
        hier_kws = [hk for hk in hier_kws if not str(hk).lower().startswith("places|")]

    if not taught and not negated and not user_note:
        return flat_kws, hier_kws, country, state_region, city, specific_location

    # If user_note is present (and location wasn't explicitly cleared), also parse any geographic overrides from it
    if user_note and loc_prov != "user_cleared":
        parsed_note = parse_natural_language_teach(user_note, explicit_add_tags=taught, explicit_remove_tags=negated)
        taught = parsed_note["added_tags"]
        negated = parsed_note["negated_tags"]
        if parsed_note.get("country"):
            country = parsed_note["country"]
        if parsed_note.get("state_region"):
            state_region = parsed_note["state_region"]
        if parsed_note.get("city"):
            city = parsed_note["city"]
        if parsed_note.get("specific_location"):
            specific_location = parsed_note["specific_location"]

    neg_low = {n.lower().strip() for n in negated if n.strip()}
    if neg_low:
        flat_kws = [
            k for k in flat_kws
            if k.lower().strip() not in neg_low
            and not any(re.search(rf"\b{re.escape(nl)}\b", k.lower()) for nl in neg_low)
        ]
        hier_kws = [
            hk for hk in hier_kws
            if not any(nl in hk.lower() for nl in neg_low)
        ]
        if city and city.lower().strip() in neg_low:
            city = ""
        if state_region and state_region.lower().strip() in neg_low:
            state_region = ""
        if country and country.lower().strip() in neg_low:
            country = ""
        if specific_location and any(nl in specific_location.lower() for nl in neg_low):
            specific_location = f"{city}, {state_region}" if (city and state_region) else (state_region or "")

    # Prepend taught tags so they appear first in priority (and on PhotoCard / Lightbox)
    prioritized_taught: List[str] = []
    for t in taught:
        t_clean = str(t).strip()
        if t_clean and t_clean.lower() not in neg_low:
            prioritized_taught.append(t_clean)
    remaining_flat = [k for k in flat_kws if k.lower().strip() not in {pt.lower() for pt in prioritized_taught}]
    flat_kws = prioritized_taught + remaining_flat

    if country and str(country).strip().lower() not in ("", "unknown", "none"):
        reg_val = state_region or country
        if specific_location and str(specific_location).strip().lower() not in ("", "unknown", "none") and specific_location != reg_val:
            p_tag = f"Places|{country}|{reg_val}|{specific_location}"
        else:
            p_tag = f"Places|{country}|{reg_val}"
        if p_tag not in hier_kws:
            hier_kws.insert(0, p_tag)

    return flat_kws, hier_kws, country, state_region, city, specific_location


def reassess_records_fast(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    photo_ids: Optional[List[str]] = None,
    catalog_name: Optional[str] = None,
    encode_text_batch_fn: Optional[Callable[[List[str]], Dict[str, np.ndarray]]] = None,
    progress_cb: Optional[Callable[[int, int, str], bool]] = None,
) -> Dict[str, Any]:
    """
    Fast Vector & Ontology Re-Assessment (< 1 second):
    Re-evaluates selected photos (or entire catalog) using cached OpenCLIP vectors +
    Contrastive Habitat & Artifact Foil Gates + Spatial Subject Verification +
    Strict Location Provenance (100% Blank by Default unless verified) +
    multi-tier ontology expansion + 5-facet visual keyword synthesis +
    persistent photographer Teach Mode overrides.
    """
    t0 = time.time()
    vectors = load_or_init_vectors_matrix(vectors_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    where_clauses = ["status != 'failed'"]
    params: List[Any] = []
    filter_ids_in_python: Optional[set] = None
    if photo_ids:
        clean_ids = list(dict.fromkeys(str(pid).strip() for pid in photo_ids if pid))
        if len(clean_ids) <= 400:
            placeholders = ",".join("?" for _ in clean_ids)
            where_clauses.append(f"(file_hash IN ({placeholders}) OR file_path IN ({placeholders}))")
            params.extend(clean_ids)
            params.extend(clean_ids)
        else:
            filter_ids_in_python = set(clean_ids)
    elif catalog_name and catalog_name != "All Catalogs":
        if catalog_name.lower() == "keepers":
            where_clauses.append("catalog_name = 'Keepers'")
        else:
            where_clauses.append("catalog_name = ?")
            params.append(catalog_name)

    rows = [
        dict(r)
        for r in cursor.execute(
            f"""
            SELECT file_path, file_hash, catalog_name, exif_time, shoot_date,
                   camera_make, camera_model, camera_serial,
                   gps_lat, gps_lon, gps_alt, gps_ground_truth, is_screenshot,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   existing_keywords, lrcat_keywords, key_subjects, hierarchical_keywords,
                   preview_1600_path, thumb_360_path,
                   primary_category, sub_category, is_aerial, is_unsharp, is_monochrome,
                   confidence_score, vector_index, status,
                   user_context_notes, user_taught_tags, negated_tags,
                   subject_boxes, verified_subjects, location_provenance
            FROM photo_records
            WHERE {' AND '.join(where_clauses)}
            """,
            params,
        ).fetchall()
    ]
    if filter_ids_in_python is not None:
        rows = [
            r for r in rows
            if r.get("file_hash") in filter_ids_in_python or r.get("file_path") in filter_ids_in_python
        ]

    if not rows:
        conn.close()
        return {"status": "ok", "mode": "fast_vectors", "reassessed_count": 0, "elapsed_seconds": 0.0}

    probes_map = compute_clip_concept_probes_for_rows(
        rows=rows, vectors=vectors, encode_text_batch_fn=encode_text_batch_fn, db_path=db_path
    )
    resolved_geo_map = propagate_shoot_day_geography(rows=rows, probes_map=probes_map, vectors=vectors)

    US_STATE_NAMES_LOWER = {
        "utah", "california", "arizona", "colorado", "washington", "oregon",
        "wyoming", "new mexico", "florida", "louisiana", "montana", "nevada",
        "illinois", "south dakota", "tennessee", "north carolina", "south carolina",
        "nebraska", "kentucky", "georgia", "new york", "new_york", "minnesota",
        "idaho", "texas", "alaska", "hawaii",
    }

    UNVERIFIED_PLACE_TAGS_LOWER = US_STATE_NAMES_LOWER | {
        "united states", "unknown", "none", "general", "not specified",
        "glacier national park", "state route 183", "canyonlands",
        "canyonlands national park", "canyonlands & moab", "arches national park",
        "monument valley", "valley of the gods", "palouse", "palouse & farmland",
        "taft oil field", "oil fields & industrial", "san francisco bay", "bay area",
        "san francisco", "chicago", "denver", "denver trip 07", "england",
        "united kingdom", "brighton", "southern england", "italy", "venice", "veneto",
        "grand canal", "venetian architecture", "mexico", "san miguel de allende",
        "guanajuato", "oaxaca", "colonial mexico", "latin america", "cuba", "havana",
        "havana & malecón", "malecón", "malecon", "caribbean", "south america",
        "peru", "cusco", "argentina", "patagonia", "chile", "colombia", "brazil",
        "new zealand", "milford sound", "fiordland", "south island",
        "iceland", "icelandic highlands & coast", "reykjavik", "reykjavík",
        "hallgrimskirkja", "hallgrímskirkja", "hallgrímskirkja, reykjavík",
        "hallgrímskirkja & reykjavík", "capital region", "suðurland", "austurland",
        "vesturland", "jokulsarlon", "jökulsárlón", "jökulsárlón & diamond beach",
        "diamond beach", "kirkjufell", "kirkjufell mountain", "snæfellsnes",
        "gullfoss", "gullfoss & icelandic waterfalls", "icelandic waterfall",
        "reynisfjara", "reynisfjara black sand beach", "reynisdrangar", "vik",
        "nordic landscape", "nordic architecture", "europe", "north atlantic",
        "grand teton", "grand tetons", "grand teton national park", "yellowstone",
        "yellowstone national park", "yosemite", "yosemite national park",
        "death valley", "death valley national park", "zabriskie point",
        "alabama hills", "mono lake", "eastern sierra", "eastern sierra & highway 395",
        "big sur", "pescadero", "pescadero state beach", "point lobos",
        "huntington beach", "anza-borrego", "anza-borrego desert", "joshua tree",
        "tucson", "tucson & sonoran desert", "sonoran desert", "grand canyon",
        "grand canyon national park", "white sands", "white sands national park",
        "bosque del apache", "santa fe", "shiprock", "comb ridge", "factory butte",
        "dead horse point", "green river overlook", "heber valley", "moccasin",
        "billings", "billings & montana plains", "hawkeye ranch",
        "hawkeye ranch & southfork valley", "southfork valley", "cody",
        "humphrey, nebraska", "yankton", "everglades", "everglades national park",
        "washington dc", "washington, d.c.", "washington monument", "nashville",
        "savannah, georgia", "carolinas", "carolinas & blue ridge",
        "american southwest", "pacific northwest", "gulf coast", "sierra nevada",
    }

    updates = []
    hallucinations_stripped = 0
    ontology_enriched = 0
    landmark_propagated = 0
    total_rows = len(rows)
    cancelled = False

    for idx_row, r in enumerate(rows):
        fp = r["file_path"]
        if progress_cb is not None:
            should_continue = progress_cb(idx_row, total_rows, Path(fp).name)
            if not should_continue:
                cancelled = True
                break
        sdate = str(r.get("shoot_date") or "")
        fp_stem_low = Path(fp).stem.lower()
        probes = probes_map.get(fp, {})
        geo_anchor = resolved_geo_map.get(fp)
        is_confirmed_aerial = bool(probes.get("is_aerial", False))

        orig_flat = _safe_json_list(r.get("key_subjects"))
        orig_hier = _safe_json_list(r.get("hierarchical_keywords"))
        orig_spec = r.get("specific_location")
        orig_state = r.get("state_region")
        primary_cat = str(r.get("primary_category") or "Landscape").strip()

        # Ensure own lrcat_keywords and existing_keywords are always included (cleaned of workflow/aerial/GPS/filler noise)
        row_city_low = str(r.get("city") or "").strip().lower()
        row_sub_low = str(r.get("sub_location") or "").strip().lower()
        row_state_low = str(r.get("state_region") or "").strip().lower()
        row_ctry_low = str(r.get("country") or "").strip().lower()
        row_spec_low = str(r.get("specific_location") or "").strip().lower()
        is_gps_row = (
            int(r.get("gps_ground_truth") or 0) == 1
            or r.get("gps_lat") is not None
            or str(r.get("location_provenance") or "") in ("exif_gps", "same_day_gps")
            or (row_city_low and row_state_low and row_spec_low == f"{row_city_low}, {row_state_low}")
        )
        redundant_gps_low = {
            x for x in (
                row_city_low,
                row_sub_low,
                row_state_low,
                row_ctry_low,
                f"{row_city_low}, {row_state_low}" if (row_city_low and row_state_low) else "",
                row_spec_low if is_gps_row else "",
                "united states",
            )
            if x
        }

        def _clean_lrcat_list(raw_list: List[str], strip_gps: bool = False) -> List[str]:
            cleaned_l: List[str] = []
            for item in raw_list:
                s = str(item or "").strip()
                sl = s.lower()
                if not s or sl in (
                    "mitch rouse aerials", "aerials", "to print", "mitch shooting",
                    "alice", "west coast imaging*  alice", "west coast imaging* alice",
                    "bro just look", "what's", "whats", "national parks & mountains",
                    "eye-level terrestrial", "eye-level", "terrestrial", "unsharp", "sharp",
                ):
                    continue
                if strip_gps and (sl in redundant_gps_low or sl.endswith(" county")):
                    continue
                if bool(probes.get("is_night_artificial")) and sl in ("midday sun", "daylight", "sunny", "bright sun"):
                    continue
                if (bool(probes.get("has_dog")) or bool(probes.get("has_cat")) or bool(probes.get("has_mirror_selfie"))) and sl in ("framed art", "picture frame", "carpet"):
                    continue
                if sl in ("lousiana", "louisana"):
                    s = "Louisiana"
                if s not in cleaned_l:
                    cleaned_l.append(s)
            return cleaned_l

        own_lrcat = _clean_lrcat_list(_safe_json_list(r.get("lrcat_keywords")), strip_gps=False)
        own_exist = _clean_lrcat_list(_safe_json_list(r.get("existing_keywords")), strip_gps=True)
        orig_flat = _clean_lrcat_list(orig_flat, strip_gps=True)

        # Clean accidental 'england' import preset on Sept/Oct 2009 US shoots (Tetons / Denver trip 07)
        if sdate in ("2009-09-28", "2009-10-01") or "teton" in fp_stem_low or any("denver" in k.lower() for k in own_lrcat + orig_flat):
            own_lrcat = [k for k in own_lrcat if str(k).strip().lower() != "england"]
            own_exist = [k for k in own_exist if str(k).strip().lower() != "england"]
            orig_flat = [k for k in orig_flat if str(k).strip().lower() not in ("england", "united kingdom", "denver trip 07" if "teton" in fp_stem_low else "")]
            orig_hier = [hk for hk in orig_hier if "united kingdom" not in hk.lower() and "england" not in hk.lower()]

        base_flat = list(
            dict.fromkeys(
                own_lrcat
                + own_exist
                + orig_flat
            )
        )
        base_hier = list(dict.fromkeys(orig_hier))

        # Clean print-collection tag "Alice" ("west coast imaging*  Alice") residue
        if "Subjects|People|Named|Alice" in base_hier or any(str(k).strip().lower() == "alice" for k in base_flat):
            own_lrcat_low = {str(k).strip().lower() for k in own_lrcat}
            if "alice" not in own_lrcat_low:
                base_flat = [
                    k for k in base_flat
                    if str(k).strip().lower() not in {"alice", "west coast imaging*  alice"}
                ]
            if "Subjects|People|Named|Alice" in base_hier:
                base_hier = [
                    hk for hk in base_hier
                    if hk not in {"Subjects|People|Named|Alice", "Subjects|People|Female", "Subjects|People"}
                ]
                base_flat = [
                    k for k in base_flat
                    if k not in {"Woman", "Female", "Portrait", "Person", "People", "Human"}
                ]

        # Remove opposite perspective tags before re-expanding
        if is_confirmed_aerial:
            base_flat = [k for k in base_flat if k != "Terrestrial"]
            base_hier = [hk for hk in base_hier if hk != "Perspective|Terrestrial"]
        else:
            base_flat = [k for k in base_flat if k != "Aerial"]
            base_hier = [hk for hk in base_hier if hk != "Perspective|Aerial"]
            if primary_cat == "Aerial":
                primary_cat = "Landscape"

        # 1. Strip unconfirmed hallucinated aerial landmarks & directive exemplars
        clean_flat, clean_hier, _, _ = strip_hallucinated_landmarks(
            flat_kws=base_flat,
            hier_kws=base_hier,
            record=r,
            specific_location=orig_spec,
            state_region=orig_state,
            is_confirmed_aerial=is_confirmed_aerial,
            clip_probes=probes,
        )

        # 1B. Strict Location Provenance (100% Blank by Default unless verified in geo_anchor)
        own_lrcat_low_set = {str(k).strip().lower() for k in own_lrcat}
        taught_low_set = {str(k).strip().lower() for k in _safe_json_list(r.get("user_taught_tags"))}
        authoritative_keep_low = own_lrcat_low_set | taught_low_set

        if geo_anchor is not None:
            landmark_propagated += 1
            clean_country = str(geo_anchor.get("country") or "").strip()
            clean_state = str(geo_anchor.get("state_region") or "").strip()
            clean_city = str(geo_anchor.get("city") or r.get("city") or "").strip()
            clean_spec = str(geo_anchor.get("specific_location") or "").strip()
            loc_prov = str(geo_anchor.get("source") or "verified").strip()

            for bad_loc in ("unknown", "none", "general", "not specified"):
                if clean_country.lower() == bad_loc:
                    clean_country = ""
                if clean_state.lower() == bad_loc:
                    clean_state = ""
                if clean_city.lower() == bad_loc:
                    clean_city = ""
                if clean_spec.lower() == bad_loc:
                    clean_spec = ""
            if clean_city.lower() == "venice" and clean_country != "Italy":
                clean_city = ""

            # Conflict Resolution: If international (e.g., Iceland, Italy, Mexico, UK, NZ), strip conflicting US state/place tags
            if clean_country and clean_country != "United States":
                clean_flat = [
                    k for k in clean_flat
                    if k.lower().strip() not in US_STATE_NAMES_LOWER
                    and "united states" not in k.lower()
                    and "canyonlands" not in k.lower()
                ]
                clean_hier = [
                    hk for hk in clean_hier
                    if not hk.startswith("Places|United States")
                    and not any(f"|{st}|" in hk.lower() or hk.lower().endswith(f"|{st}") for st in US_STATE_NAMES_LOWER)
                ]
            else:
                # US Landmark / State resolved: strip conflicting other US states in clean_flat & Places| hierarchy
                target_st_low = clean_state.lower().strip()
                other_states = US_STATE_NAMES_LOWER - {target_st_low}
                if target_st_low == "arizona" and "monument valley" in clean_spec.lower():
                    other_states = other_states - {"utah"}
                clean_flat = [
                    k for k in clean_flat
                    if k.lower().strip() not in other_states or k.lower().strip() in authoritative_keep_low
                ]
                clean_hier = [
                    hk for hk in clean_hier
                    if not (
                        hk.startswith("Places|United States|")
                        and any(f"places|united states|{ost}" in hk.lower() for ost in other_states)
                    )
                ]

            for gtag in geo_anchor.get("tags", []):
                if gtag and gtag not in clean_flat:
                    clean_flat.append(gtag)
            ghier = geo_anchor.get("hierarchy")
            if ghier and ghier not in clean_hier:
                clean_hier.append(ghier)
        else:
            # No verified location provenance -> 100% Blank by Default!
            clean_country = ""
            clean_state = ""
            clean_city = ""
            clean_spec = ""
            loc_prov = "user_cleared" if str(r.get("location_provenance") or "") == "user_cleared" else ""
            # Strip all unverified state/country/landmark guesses from flat_kws and Places| from hier_kws
            clean_flat = [
                k for k in clean_flat
                if k.lower().strip() not in UNVERIFIED_PLACE_TAGS_LOWER
                or k.lower().strip() in authoritative_keep_low
            ]
            clean_hier = [
                hk for hk in clean_hier
                if not str(hk).lower().startswith("places|")
            ]

        if len(clean_flat) < len(base_flat) or clean_spec != (orig_spec or ""):
            hallucinations_stripped += 1

        # Strip cross-state landmark residue from earlier runs when state does not match
        st_check = clean_state.lower().strip()
        if st_check != "louisiana" and "houma" not in fp_stem_low and "abbeville" not in fp_stem_low:
            clean_flat = [k for k in clean_flat if k.lower().strip() not in ("houma", "houma & louisiana bayous", "bayou", "cypress swamp", "abbeville", "abbeville cypress swamp", "louisana", "lousiana")]
            clean_hier = [hk for hk in clean_hier if "louisiana" not in hk.lower() and "houma" not in hk.lower()]
            if clean_spec and ("houma" in clean_spec.lower() or "louisiana" in clean_spec.lower()):
                clean_spec = clean_state
        if st_check != "oregon" and "bandon" not in fp_stem_low and "coosbay" not in fp_stem_low:
            clean_flat = [k for k in clean_flat if k.lower().strip() not in ("bandon", "bandon coast", "oregon coast")]
            clean_hier = [hk for hk in clean_hier if "oregon" not in hk.lower() and "bandon" not in hk.lower()]
        if "consumnes" not in fp_stem_low and "cosumnes" not in fp_stem_low:
            clean_flat = [k for k in clean_flat if "cosumnes" not in k.lower() and "consumnes" not in k.lower()]
            clean_hier = [hk for hk in clean_hier if "cosumnes" not in hk.lower()]
            if clean_spec and "cosumnes" in clean_spec.lower():
                clean_spec = clean_state

        # Ensure Butte tag (singular, deduplicated) on any Monument Valley or Valley of the Gods record
        if clean_spec and any(lm in clean_spec.lower() for lm in ("monument valley", "valley of the gods", "castleton", "devils tower", "butte")):
            for btag in ("Butte", "Sandstone Butte", "Desert Monolith"):
                if btag not in clean_flat:
                    clean_flat.append(btag)
            if "Landscape|Desert|Butte" not in clean_hier:
                clean_hier.append("Landscape|Desert|Butte")

        # 2. Multi-tier Ontology Expansion (Animals, People, Mitch Identity, Flora, Structures)
        exp_flat, exp_hier = expand_hierarchical_ontology(
            flat_kws=clean_flat,
            hier_kws=clean_hier,
            record=r,
            clip_probes=probes,
        )

        # 2B. Clean Photographer Keywords & 10,000-Foot Portfolio Categories
        exp_flat, exp_hier = synthesize_5facet_visual_keywords(
            record=r,
            probes=probes,
            flat_kws=exp_flat,
            hier_kws=exp_hier,
            primary_category=primary_cat,
            country=clean_country,
            state_region=clean_state,
            specific_location=clean_spec,
        )

        # Clean AI/VLM candidate tags before applying authoritative user teach overrides
        exp_flat = [
            t for t in (_clean_single_photographer_tag(k, is_aerial=is_confirmed_aerial) for k in exp_flat)
            if t is not None
        ]
        exp_flat = list(dict.fromkeys(exp_flat))

        # 2C. Enforce Persistent User Teach Overrides (Taught tags & Negated tags have full authority)
        exp_flat, exp_hier, clean_country, clean_state, clean_city, clean_spec = apply_user_teach_overrides(
            flat_kws=exp_flat,
            hier_kws=exp_hier,
            record=r,
            country=clean_country,
            state_region=clean_state,
            city=clean_city,
            specific_location=clean_spec,
        )
        clean_country = str(clean_country or "").strip()
        clean_state = str(clean_state or "").strip()
        clean_city = str(clean_city or "").strip()
        clean_spec = str(clean_spec or "").strip()
        for bad_loc in ("unknown", "none"):
            if clean_country.lower() == bad_loc:
                clean_country = ""
            if clean_state.lower() == bad_loc:
                clean_state = ""
            if clean_city.lower() == bad_loc:
                clean_city = ""
            if clean_spec.lower() == bad_loc:
                clean_spec = ""

        if (clean_country or clean_state or clean_city or clean_spec) and not loc_prov:
            loc_prov = "user"

        exp_flat = deduplicate_singular_plural_tags(
            list(dict.fromkeys(exp_flat)),
            subject_counts=probes.get("subject_counts"),
        )

        if len(exp_flat) > len(clean_flat) or len(exp_hier) > len(clean_hier):
            ontology_enriched += 1

        # Update primary_category from the synthesized Portfolio|<Category> hierarchy so catch-all categories are fixed
        portfolio_cats_in_hier = [
            hk.split("|", 1)[1].strip()
            for hk in exp_hier
            if str(hk).startswith("Portfolio|") and "|" in str(hk)
        ]
        if portfolio_cats_in_hier:
            primary_cat = portfolio_cats_in_hier[0]

        # 3. Preserve Technical Sharpness & Monochrome rules in hierarchical_keywords (NEVER clutter visual key_subjects with Unsharp)
        exp_flat = [k for k in exp_flat if k not in ("Unsharp", "Sharp", "Eye-level terrestrial", "Eye-level", "Terrestrial", "National Parks & Mountains")]
        if int(r.get("is_unsharp") or 0) == 1:
            if "Technical|Focus|Unsharp" not in exp_hier:
                exp_hier.append("Technical|Focus|Unsharp")
        else:
            exp_hier = [hk for hk in exp_hier if hk != "Technical|Focus|Unsharp"]

        if int(r.get("is_monochrome") or 0) == 1:
            if "Monochrome" not in exp_flat:
                exp_flat.append("Monochrome")
            if "Technical|Monochrome" not in exp_hier:
                exp_hier.append("Technical|Monochrome")

        if int(r.get("is_screenshot") or 0) == 1:
            for st_tag in ("Screenshot", "Screen Capture"):
                if st_tag not in exp_flat:
                    exp_flat.append(st_tag)
            if "Technical|Screenshot" not in exp_hier:
                exp_hier.append("Technical|Screenshot")

        row_update = (
            primary_cat,
            clean_country,
            clean_state,
            clean_city,
            clean_spec,
            loc_prov,
            json.dumps(probes.get("subject_boxes", [])),
            json.dumps(probes.get("verified_subjects", [])),
            json.dumps(list(dict.fromkeys(exp_flat))),
            json.dumps(list(dict.fromkeys(exp_hier))),
            1 if is_confirmed_aerial else 0,
            json.dumps(own_lrcat),
            json.dumps(own_exist),
            fp,
        )
        updates.append(row_update)

        if len(updates) % 200 == 0:
            cursor.executemany(
                """
                UPDATE photo_records
                SET primary_category = ?,
                    country = ?,
                    state_region = ?,
                    city = ?,
                    specific_location = ?,
                    location_provenance = ?,
                    subject_boxes = ?,
                    verified_subjects = ?,
                    key_subjects = ?,
                    hierarchical_keywords = ?,
                    is_aerial = ?,
                    lrcat_keywords = ?,
                    existing_keywords = ?,
                    status = CASE WHEN status = 'stage1_ready' THEN 'tagged' ELSE status END,
                    stage2_completed = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                updates[-200:],
            )
            conn.commit()

    rem_count = len(updates) % 200
    if rem_count > 0:
        cursor.executemany(
            """
            UPDATE photo_records
            SET primary_category = ?,
                country = ?,
                state_region = ?,
                city = ?,
                specific_location = ?,
                location_provenance = ?,
                subject_boxes = ?,
                verified_subjects = ?,
                key_subjects = ?,
                hierarchical_keywords = ?,
                is_aerial = ?,
                lrcat_keywords = ?,
                existing_keywords = ?,
                status = CASE WHEN status = 'stage1_ready' THEN 'tagged' ELSE status END,
                stage2_completed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
            """,
            updates[-rem_count:],
        )
        conn.commit()
    conn.close()

    # Rebuild cross-catalog metadata centroids with the cleaned & enriched records
    learned_idx = build_self_learning_index(db_path=db_path, vectors_path=vectors_path)

    return {
        "status": "cancelled" if cancelled else "ok",
        "mode": "fast_vectors",
        "reassessed_count": len(updates),
        "hallucinations_stripped": hallucinations_stripped,
        "landmark_propagated": landmark_propagated,
        "ontology_enriched": ontology_enriched,
        "centroids_indexed": learned_idx["centroids_count"],
        "elapsed_seconds": round(time.time() - t0, 3),
    }


def reassess_records_deep(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    photo_ids: Optional[List[str]] = None,
    catalog_name: Optional[str] = None,
    vlm_model: str = "qwen2.5vl:7b",
    encode_text_batch_fn: Optional[Callable[[List[str]], Dict[str, np.ndarray]]] = None,
    progress_cb: Optional[Callable[[int, int, str], bool]] = None,
) -> Dict[str, Any]:
    """
    Deep VLM Spot Re-Assessment (~3s per photo):
    Re-runs Qwen2.5-VL on the selected photo(s) or Trip, injecting the perspective-gated
    Aerial vs. Terrestrial guide doc, latest learned cross-catalog ground-truth hints,
    hallucinated landmark stripping, 5-facet visual keyword synthesis, and persistent Teach Mode overrides.
    """
    t0 = time.time()
    learned_index = build_self_learning_index(db_path=db_path, vectors_path=vectors_path)
    vectors = load_or_init_vectors_matrix(vectors_path)
    biometrics = BiometricMatcher()

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    where_clauses = ["status != 'failed'"]
    params: List[Any] = []
    filter_ids_in_python: Optional[set] = None
    if photo_ids:
        clean_ids = list(dict.fromkeys(str(pid).strip() for pid in photo_ids if pid))
        if len(clean_ids) <= 400:
            placeholders = ",".join("?" for _ in clean_ids)
            where_clauses.append(f"(file_hash IN ({placeholders}) OR file_path IN ({placeholders}))")
            params.extend(clean_ids)
            params.extend(clean_ids)
        else:
            filter_ids_in_python = set(clean_ids)
    elif catalog_name and catalog_name != "All Catalogs":
        if catalog_name.lower() == "keepers":
            where_clauses.append("catalog_name = 'Keepers'")
        else:
            where_clauses.append("catalog_name = ?")
            params.append(catalog_name)

    rows = [
        dict(r)
        for r in cursor.execute(
            f"""
            SELECT file_path, file_hash, catalog_name, sequence_id, sequence_frame_index, sequence_length,
                   is_sequence_hero, exif_time, shoot_date,
                   camera_make, camera_model, camera_serial, lens_model,
                   focal_length, shutter_speed, aperture, iso,
                   gps_lat, gps_lon, gps_alt, gps_ground_truth, is_screenshot,
                   title, caption, sub_location, specific_location, city, state_region, country,
                   existing_keywords, lrcat_keywords, key_subjects, hierarchical_keywords,
                   preview_1600_path, thumb_360_path,
                   sharpness_score, is_unsharp, is_monochrome, vector_index,
                   primary_category, sub_category,
                   user_context_notes, user_taught_tags, negated_tags,
                   subject_boxes, verified_subjects, location_provenance
            FROM photo_records
            WHERE {' AND '.join(where_clauses)}
            """,
            params,
        ).fetchall()
    ]
    if filter_ids_in_python is not None:
        rows = [
            r for r in rows
            if r.get("file_hash") in filter_ids_in_python or r.get("file_path") in filter_ids_in_python
        ]

    if not rows:
        conn.close()
        return {"status": "ok", "mode": "deep_vlm", "reassessed_count": 0, "elapsed_seconds": 0.0}

    probes_map = compute_clip_concept_probes_for_rows(
        rows=rows, vectors=vectors, encode_text_batch_fn=encode_text_batch_fn, db_path=db_path
    )
    resolved_geo_map = propagate_shoot_day_geography(rows=rows, probes_map=probes_map, vectors=vectors)
    for fp_k, g_val in resolved_geo_map.items():
        if fp_k in probes_map:
            probes_map[fp_k]["_geo_anchor"] = g_val

    updates = []
    vlm_calls = 0
    total_rows = len(rows)
    cancelled = False

    for idx_row, frame in enumerate(rows):
        fp = frame["file_path"]
        if progress_cb is not None:
            should_continue = progress_cb(idx_row, total_rows, Path(fp).name)
            if not should_continue:
                cancelled = True
                break
        probes = probes_map.get(fp, {})
        gt = lookup_ground_truth_context(
            frame,
            learned_index=learned_index,
            vectors=vectors,
            orbit_window_seconds=180.0,
            centroid_similarity_threshold=0.86,
        )
        frame_directive, _ = select_guide_directive(frame, ground_truth=gt, clip_probes=probes)
        prompt_str = build_vlm_prompt(frame, ground_truth=gt)
        preview_p = Path(frame.get("preview_1600_path") or frame.get("thumb_360_path") or "")

        try:
            ai_out = call_qwen_vlm(
                preview_path=preview_p,
                prompt_text=prompt_str,
                directive_text=frame_directive,
                vlm_model=vlm_model,
            )
            vlm_calls += 1
        except Exception as exc:
            logging.warning(f"Deep VLM reassessment fallback for {fp}: {exc}")
            ai_out = {
                "primary_category": frame.get("primary_category") or "Landscape",
                "sub_category": frame.get("sub_category") or "Archival",
                "country": frame.get("country") or "",
                "state_region": frame.get("state_region") or "",
                "specific_location": frame.get("specific_location") or "",
                "flat_keywords": _safe_json_list(frame.get("key_subjects")),
                "hierarchical_keywords": _safe_json_list(frame.get("hierarchical_keywords")),
                "is_aerial": bool(probes.get("is_aerial")),
                "confidence_score": 0.85,
            }

        faces = biometrics.detect_faces(preview_p if preview_p.exists() else None)
        merged = merge_ai_and_frame_metadata(
            frame_record=frame,
            ai_data=ai_out,
            ground_truth=gt,
            faces_detected=faces,
            status_label="tagged",
            clip_probes=probes,
        )
        row_tuple = (
            merged["status"],
            merged["primary_category"],
            merged["sub_category"],
            merged["country"],
            merged["state_region"],
            merged["city"],
            merged["sub_location"],
            merged["specific_location"],
            merged["location_provenance"],
            merged["subject_boxes"],
            merged["verified_subjects"],
            merged["key_subjects"],
            merged["hierarchical_keywords"],
            merged["is_aerial"],
            merged["confidence_score"],
            fp,
        )
        updates.append(row_tuple)
        # Commit each photo immediately so cancelling mid-batch keeps all completed photos!
        cursor.execute(
            """
            UPDATE photo_records
            SET status = ?,
                primary_category = ?,
                sub_category = ?,
                country = ?,
                state_region = ?,
                city = ?,
                sub_location = ?,
                specific_location = ?,
                location_provenance = ?,
                subject_boxes = ?,
                verified_subjects = ?,
                key_subjects = ?,
                hierarchical_keywords = ?,
                is_aerial = ?,
                confidence_score = ?,
                stage2_completed = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
            """,
            row_tuple,
        )
        conn.commit()
    conn.close()

    return {
        "status": "ok",
        "mode": "deep_vlm",
        "reassessed_count": len(updates),
        "vlm_calls": vlm_calls,
        "elapsed_seconds": round(time.time() - t0, 2),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 2 Self-Learning & VLM Enrichment Engine (v3.0)")
    parser.add_argument("--catalog", type=str, default=None, help="Filter to a specific catalog_name")
    parser.add_argument("--stride", type=int, default=35, help="Strafing sequence VLM anchor stride (default: 35)")
    parser.add_argument("--force", action="store_true", help="Re-run Stage 2 even on already completed records")
    args = parser.parse_args()

    summary = run_stage2_vlm(
        catalog_name=args.catalog,
        strafing_stride=args.stride,
        force_rerun=args.force,
    )
    print(json.dumps(summary, indent=2))
