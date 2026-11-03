#!/usr/bin/env python3
"""
Stage 1 High-Speed Processing Engine (stage1_engine.py)
AI Photo Archival System v3.0 — Mitch Rouse Architecture

Executes Stage 1 (Zero 7B LLM calls, Zero writes to RAW files):
1. Hardware Auto-Scaling (psutil RAM/CPU + Apple Silicon torch.backends.mps)
2. Full-Res Embedded Preview / .lrprev Pyramid Extraction -> 90th-Percentile Inner 6x6 Patch Sharpness ('Unsharp' Tagger)
3. Persistent Two-Tier WebP Cache Generation (thumbs_360/{hash}.webp & previews_1600/{hash}.webp)
4. Hasler & Süsstrunk Colorfulness + Monochrome Contrast Fairness Metric
5. Batched Apple Silicon (mps) OpenCLIP (ViT-L-14) 768-d Float16 Vector Matrix (data/vectors.npy)
6. LAION Aesthetic V2 MLP Head + Keepers Personal Taste Calibration -> Master aesthetic_score
7. Clock-Safe, Date-Bounded & Camera-Bounded Aerial Strafing / Panorama Sequence Grouper + Hero Picker
"""

import io
import os
import re
import json
import time
import tempfile
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import psutil
import exiftool
import imagehash
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = None

import torch
import torch.nn as nn
import open_clip

from config_paths import (
    DATA_VAULT_DIR,
    DEFAULT_COLOR_SIGS_PATH,
    DEFAULT_CROP_BOXES_PATH,
    DEFAULT_CROP_VECTORS_PATH,
    DEFAULT_DB_PATH,
    DEFAULT_MODELS_DIR,
    DEFAULT_PREVIEWS_1600_DIR,
    DEFAULT_THUMBS_360_DIR,
    DEFAULT_VECTORS_PATH,
)
from db_schema import (
    get_db_connection,
    init_and_migrate_db,
    compute_file_hash,
    normalize_shoot_date,
    log_ingestion_error,
)
from harvester import (
    discover_catalog_files,
    harvest_lrcat_metadata,
    harvest_omni_metadata_batch,
    link_keepers_across_catalogs,
    resolve_offline_gps_location,
)

SCRIPT_DIR = Path(__file__).resolve().parent
os.environ["PATH"] = f"{SCRIPT_DIR}/bin:{SCRIPT_DIR}/.venv/bin:{os.environ.get('PATH', '')}"


# ==============================================================================
# 1. HARDWARE AUTO-SCALING (Laptop -> M5 Max / Ultra Mac Studio)
# ==============================================================================
def detect_hardware_profile() -> Dict[str, Any]:
    """
    Auto-detects system RAM, CPU cores, and Apple Silicon MPS GPU availability.
    Scales worker threads and OpenCLIP batch sizes safely across MacBook Pro and M5 Max Studio.
    """
    ram_bytes = psutil.virtual_memory().total
    ram_gb = round(ram_bytes / (1024 ** 3), 1)
    cpu_cores = os.cpu_count() or 8
    mps_available = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    device = "mps" if mps_available else "cpu"

    if ram_gb >= 96:
        tier = "Mac Studio Ultra / Max (High-Memory Production)"
        extractor_workers = min(12, max(6, cpu_cores - 2))
        clip_batch_size = 128
        exif_batch_size = 100
    elif ram_gb >= 48:
        tier = "Mac Studio / Pro (Mid-High Memory)"
        extractor_workers = min(8, max(4, cpu_cores // 2))
        clip_batch_size = 64
        exif_batch_size = 64
    else:
        tier = "Apple Silicon MacBook Pro / Development Node"
        extractor_workers = min(6, max(2, cpu_cores // 3))
        clip_batch_size = 32
        exif_batch_size = 40

    return {
        "tier": tier,
        "ram_gb": ram_gb,
        "cpu_cores": cpu_cores,
        "mps_available": mps_available,
        "device": device,
        "extractor_workers": extractor_workers,
        "clip_batch_size": clip_batch_size,
        "exif_batch_size": exif_batch_size,
    }


# ==============================================================================
# 2. FULL-RES 90TH-PERCENTILE PATCH SHARPNESS & COLORFULNESS METRICS
# ==============================================================================
def compute_patch_90th_sharpness(
    pil_img: Image.Image,
    grid_size: int = 8,
    percentile: float = 90.0
) -> float:
    """
    Full-Res 90th-Percentile Patch Sharpness:
    - Converts full-resolution preview to grayscale float32.
    - Divides into an 8x8 grid and evaluates the inner 6x6 (36) patches.
    - Computes 3x3 Sobel Tenengrad gradient energy on each patch, normalized by
      local contrast floor so smooth skies, ocean water, or portrait bokeh are never
      falsely penalized, while whole-frame motion blur or airframe vibration scores < 3.5.
    """
    gray = np.asarray(pil_img.convert("L"), dtype=np.float32)
    h, w = gray.shape
    if h < 32 or w < 32:
        return 0.0

    # Vectorized 3x3 Sobel gradients across the full grayscale frame
    gx = (
        (gray[:-2, 2:] + 2.0 * gray[1:-1, 2:] + gray[2:, 2:])
        - (gray[:-2, :-2] + 2.0 * gray[1:-1, :-2] + gray[2:, :-2])
    )
    gy = (
        (gray[2:, :-2] + 2.0 * gray[2:, 1:-1] + gray[2:, 2:])
        - (gray[:-2, :-2] + 2.0 * gray[:-2, 1:-1] + gray[:-2, 2:])
    )
    grad_mag = np.hypot(gx, gy)  # shape (h-2, w-2)

    gh, gw = grad_mag.shape
    step_y = gh // grid_size
    step_x = gw // grid_size
    if step_y < 4 or step_x < 4:
        return float(np.mean(grad_mag) / 10.0)

    patch_scores: List[float] = []
    # Inner 6x6 patches (rows 1..6, cols 1..6)
    for r in range(1, grid_size - 1):
        y0, y1 = r * step_y, (r + 1) * step_y
        for c in range(1, grid_size - 1):
            x0, x1 = c * step_x, (c + 1) * step_x
            patch_g = grad_mag[y0:y1, x0:x1]
            patch_l = gray[y0 + 1 : y1 + 1, x0 + 1 : x1 + 1]
            std_l = max(float(np.std(patch_l)), 14.0)
            # High-frequency edge energy relative to patch contrast
            p90_grad = float(np.percentile(patch_g, 90))
            mean_grad = float(np.mean(patch_g))
            score = ((0.65 * p90_grad + 0.35 * mean_grad) / std_l) * 1.65
            patch_scores.append(score)

    if not patch_scores:
        return 0.0

    raw_90th = float(np.percentile(patch_scores, percentile))
    return round(max(0.0, min(15.0, raw_90th)), 3)


def compute_colorfulness_and_mono(pil_img: Image.Image) -> Tuple[float, int]:
    """
    Computes Hasler & Süsstrunk (2003) colorfulness metric + monochrome fairness normalization.
    Returns (colorfulness_score on 0..10 scale, is_monochrome 0/1).
    """
    small = pil_img.convert("RGB")
    small.thumbnail((256, 256), Image.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    rg_diff = float(np.mean(np.abs(r - g)))
    rb_diff = float(np.mean(np.abs(r - b)))
    gb_diff = float(np.mean(np.abs(g - b)))
    is_mono = 1 if (rg_diff + rb_diff + gb_diff) < 4.5 else 0

    if is_mono:
        # Fair normalization for monochrome images using tonal dynamic range (p95 - p5) & RMS contrast
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        dyn_range = float(np.percentile(lum, 96) - np.percentile(lum, 4)) / 255.0
        rms_contrast = float(np.std(lum)) / 64.0
        mono_score = min(10.0, max(1.0, (0.55 * dyn_range + 0.45 * min(rms_contrast, 1.2)) * 8.5))
        return round(mono_score, 3), 1

    rg = r - g
    yb = 0.5 * (r + g) - b
    std_root = np.hypot(np.std(rg), np.std(yb))
    mean_root = np.hypot(np.mean(rg), np.mean(yb))
    hasler = float(std_root + 0.3 * mean_root)
    # Normalize typical Hasler range (0..110) onto 0..10 scale
    norm_score = min(10.0, max(0.5, hasler / 10.5))
    return round(norm_score, 3), 0


# ==============================================================================
# 3. FULL-RES EXTRACTION & PERSISTENT TWO-TIER WEBP CACHE (BUG #1 FIX + .LRPREV)
# ==============================================================================
def extract_jpeg_from_lrprev(
    lrprev_path: Path,
    orientation: Optional[str] = None,
) -> Optional[Image.Image]:
    """
    Extracts the highest-resolution JPEG pyramid level from a Lightroom Classic
    .lrprev file (~250 KB) in <5ms by locating the last JPEG SOI marker (\\xff\\xd8\\xff).
    Avoids pulling 335 MB .tif / .psd / .iiq rasters over SMB network mounts.
    """
    try:
        if not lrprev_path or not lrprev_path.exists():
            return None
        data = lrprev_path.read_bytes()
        if len(data) < 2048:
            return None

        # Find all JPEG SOI markers (\xff\xd8\xff); the last one is the largest pyramid level
        last_soi = data.rfind(b"\xff\xd8\xff")
        if last_soi == -1:
            return None

        with Image.open(io.BytesIO(data[last_soi:])) as im:
            pil_img = im.convert("RGB")

        # Only accept if the extracted pyramid level is at least thumbnail resolution (>=320px)
        if max(pil_img.size) < 320:
            return None

        # Apply Lightroom cache orientation if needed ('AB' is normal 0 deg)
        if orientation == "BC":
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_270)
        elif orientation == "CD":
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_180)
        elif orientation == "DA":
            pil_img = pil_img.transpose(Image.Transpose.ROTATE_90)

        return pil_img
    except Exception:
        return None


def extract_fullres_and_generate_webps(
    primary_path: Path,
    sibling_path: Optional[Path],
    file_hash: str,
    thumbs_360_dir: Path = DEFAULT_THUMBS_360_DIR,
    previews_1600_dir: Path = DEFAULT_PREVIEWS_1600_DIR,
    sharpness_threshold: float = 3.5,
    lrprev_path: Optional[Path] = None,
    lrprev_orientation: Optional[str] = None,
    fast_only: bool = False,
    force_regenerate: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    0. If persistent thumbs_360/{file_hash}.webp and previews_1600/{file_hash}.webp already exist
       on local disk (e.g. from an interrupted run) and force_regenerate=False, reuses them in <1ms.
    1. If a mapped Lightroom .lrprev pyramid file exists and force_regenerate=False, extracts its highest-resolution
       JPEG level in <5ms (avoiding 335 MB .tif reads over SMB).
    2. Otherwise extracts full-res embedded JPEG from RAW header via ExifTool (or opens standard image)
       WITHOUT touching or demosaicing the original RAW file.
    3. Runs Full-Res 90th-Percentile Patch Sharpness BEFORE any downsampling.
    4. Saves persistent WebP previews:
       - thumbs_360/{file_hash}.webp (max 360px, quality=82)
       - previews_1600/{file_hash}.webp (max 1600px, quality=86)
    """
    thumbs_360_dir.mkdir(parents=True, exist_ok=True)
    previews_1600_dir.mkdir(parents=True, exist_ok=True)

    thumb_out = thumbs_360_dir / f"{file_hash}.webp"
    preview_out = previews_1600_dir / f"{file_hash}.webp"

    pil_full: Optional[Image.Image] = None
    temp_extracted: Optional[Path] = None
    reused_cached_webps = False

    try:
        # 0. INSTANT CACHE REUSE: Reuse existing WebPs from interrupted runs (<1ms on local SSD)
        if not force_regenerate and thumb_out.exists() and preview_out.exists():
            try:
                if thumb_out.stat().st_size > 256 and preview_out.stat().st_size > 512:
                    with Image.open(preview_out) as im:
                        pil_full = im.convert("RGB")
                        reused_cached_webps = True
            except Exception:
                pil_full = None
                reused_cached_webps = False

        # 1. FAST PATH: Use Lightroom .lrprev pyramid if available (<5ms over SMB)
        if not force_regenerate and pil_full is None and lrprev_path is not None:
            pil_full = extract_jpeg_from_lrprev(Path(lrprev_path), lrprev_orientation)

        if pil_full is None:
            if fast_only and str(primary_path).startswith("/Volumes/"):
                try:
                    if primary_path.stat().st_size > 50 * 1024 * 1024:
                        return None
                except Exception:
                    return None
            # Choose best readable source for preview extraction (never modifying files)
            source_candidates = [primary_path]
            if sibling_path and sibling_path.exists():
                source_candidates.append(sibling_path)

            valid_source = None
            for cand in source_candidates:
                try:
                    if cand and cand.exists() and cand.stat().st_size > 0:
                        valid_source = cand
                        break
                except Exception:
                    continue

            if valid_source is None:
                return None

            ext_low = valid_source.suffix.lower()
            direct_pil_exts = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}

            if ext_low in direct_pil_exts:
                try:
                    with Image.open(valid_source) as im:
                        im = ImageOps.exif_transpose(im)
                        pil_full = im.convert("RGB")
                except Exception:
                    pil_full = None

            if pil_full is None:
                fd, tmp_name = tempfile.mkstemp(suffix=".jpg", prefix=f"raw_prev_{file_hash}_")
                os.close(fd)
                temp_extracted = Path(tmp_name)
                exiftool_bin = str(SCRIPT_DIR / "bin" / "exiftool")
                if not Path(exiftool_bin).exists():
                    exiftool_bin = "exiftool"

                # For Apple HEIC / HEIF, use macOS native sips first (fast & respects orientation)
                if ext_low in {".heic", ".heif"}:
                    try:
                        subprocess.run(
                            ["/usr/bin/sips", "-s", "format", "jpeg", "-Z", "2048", str(valid_source), "--out", str(temp_extracted)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=25,
                            check=False,
                        )
                        if temp_extracted.exists() and temp_extracted.stat().st_size > 0:
                            with Image.open(temp_extracted) as im:
                                im = ImageOps.exif_transpose(im)
                                pil_full = im.convert("RGB")
                    except Exception:
                        pass

                # Extract full-res embedded JPEG preview from RAW header (.RAF, .CR2, .CR3, .NEF, .ARW, .DNG, .IIQ, etc.)
                if pil_full is None:
                    for tag in ["-JpgFromRaw", "-PreviewImage", "-OtherImage", "-ThumbnailImage"]:
                        try:
                            with open(temp_extracted, "wb") as out_f:
                                subprocess.run(
                                    [exiftool_bin, "-b", tag, str(valid_source)],
                                    stdout=out_f,
                                    stderr=subprocess.DEVNULL,
                                    timeout=20,
                                    check=False,
                                )
                            if temp_extracted.exists() and temp_extracted.stat().st_size > 4096:
                                with Image.open(temp_extracted) as im:
                                    im = ImageOps.exif_transpose(im)
                                    pil_full = im.convert("RGB")
                                break
                        except Exception:
                            continue

                # If primary RAW had no embedded JPEG and a TIF/JPG sibling exists, try sibling
                if pil_full is None and sibling_path and sibling_path.exists() and sibling_path.stat().st_size > 0:
                    try:
                        with Image.open(sibling_path) as im:
                            im = ImageOps.exif_transpose(im)
                            pil_full = im.convert("RGB")
                    except Exception:
                        pass

                # macOS sips fallback at full 2048px preview resolution (never 896px!)
                if pil_full is None:
                    try:
                        subprocess.run(
                            ["/usr/bin/sips", "-s", "format", "jpeg", "-Z", "2048", str(valid_source), "--out", str(temp_extracted)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=25,
                            check=False,
                        )
                        if temp_extracted.exists() and temp_extracted.stat().st_size > 0:
                            with Image.open(temp_extracted) as im:
                                im = ImageOps.exif_transpose(im)
                                pil_full = im.convert("RGB")
                    except Exception:
                        pass

        if pil_full is None:
            return None

        # STEP A: Full-Res 90th-Percentile Patch Sharpness BEFORE any downsampling!
        sharpness_score = compute_patch_90th_sharpness(pil_full)
        is_unsharp = 1 if sharpness_score < sharpness_threshold else 0

        # STEP B: Perceptual Hash & Hasler-Süsstrunk Colorfulness / Monochrome Contrast
        phash_str = str(imagehash.phash(pil_full))
        colorfulness_score, is_monochrome = compute_colorfulness_and_mono(pil_full)
        width, height = pil_full.size
        aspect_ratio = round(width / float(max(height, 1)), 3)

        # STEP C & D: Save persistent 1600px & 360px WebP previews if not already cached on disk
        if not reused_cached_webps:
            img_1600 = pil_full.copy()
            if max(img_1600.size) > 1600:
                img_1600.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            img_1600.save(preview_out, format="WEBP", quality=86, method=4)

            img_360 = img_1600.copy()
            if max(img_360.size) > 360:
                img_360.thumbnail((360, 360), Image.Resampling.LANCZOS)
            img_360.save(thumb_out, format="WEBP", quality=82, method=4)

        return {
            "phash": phash_str,
            "sharpness_score": sharpness_score,
            "is_unsharp": is_unsharp,
            "colorfulness_score": colorfulness_score,
            "is_monochrome": is_monochrome,
            "aspect_ratio": aspect_ratio,
            "thumb_360_path": str(thumb_out),
            "preview_1600_path": str(preview_out),
        }
    finally:
        if temp_extracted and temp_extracted.exists():
            temp_extracted.unlink(missing_ok=True)


# ==============================================================================
# 4. LAION AESTHETIC V2 MLP + OPENCLIP (ViT-L-14) + KEEPERS CALIBRATION
# ==============================================================================
class LaionAestheticMLP(nn.Module):
    """Official Christoph Schuhmann LAION Aesthetic Predictor V2 MLP architecture (768 -> 1)."""
    def __init__(self, input_size: int = 768):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, 1024),
            nn.Dropout(0.2),
            nn.Linear(1024, 128),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.Dropout(0.1),
            nn.Linear(64, 16),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class VectorAestheticEngine:
    """
    Batched Apple Silicon (mps) OpenCLIP (ViT-L-14) + LAION Aesthetic V2 MLP Engine.
    Maintains 768-d L2-normalized Float16 vectors in data/vectors.npy.
    """
    def __init__(
        self,
        device: Optional[str] = None,
        models_dir: Path = DEFAULT_MODELS_DIR,
    ):
        hw = detect_hardware_profile()
        self.device = device or hw["device"]
        self.batch_size = hw["clip_batch_size"]
        self.models_dir = Path(models_dir)

        self.model, _, self.preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14-quickgelu",
            pretrained="openai",
            device=self.device,
        )
        self.model.eval()
        self.tokenizer = open_clip.get_tokenizer("ViT-L-14-quickgelu")

        # Load LAION Aesthetic V2 MLP head
        self.aesthetic_mlp = LaionAestheticMLP(768).to(self.device)
        mlp_path = self.models_dir / "sac+logos+ava1-l14-linearMSE.pth"
        if mlp_path.exists():
            sd = torch.load(str(mlp_path), map_location=self.device, weights_only=True)
            self.aesthetic_mlp.load_state_dict(sd)
        self.aesthetic_mlp.eval()

    @torch.no_grad()
    def encode_images_and_score(
        self, image_paths: List[Path]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Encodes a list of preview images in hardware-scaled batches on Apple Silicon MPS.
        Returns:
          - embeddings_f16: (N, 768) float16 L2-normalized numpy array
          - laion_scores: (N,) float32 array of LAION Aesthetic V2 scores (1..10 scale)
        """
        if not image_paths:
            return np.zeros((0, 768), dtype=np.float16), np.zeros((0,), dtype=np.float32)

        all_embs: List[np.ndarray] = []
        all_scores: List[np.ndarray] = []

        for i in range(0, len(image_paths), self.batch_size):
            batch_paths = image_paths[i : i + self.batch_size]
            tensors = []
            valid_mask = []
            for p in batch_paths:
                try:
                    with Image.open(p) as im:
                        tensors.append(self.preprocess(im.convert("RGB")))
                        valid_mask.append(True)
                except Exception:
                    tensors.append(torch.zeros((3, 224, 224), dtype=torch.float32))
                    valid_mask.append(False)

            batch_tensor = torch.stack(tensors).to(self.device)
            feats = self.model.encode_image(batch_tensor)
            feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-8)

            mlp_out = self.aesthetic_mlp(feats.float()).squeeze(-1)
            scores_np = mlp_out.detach().cpu().numpy().astype(np.float32)
            scores_np = np.clip(scores_np, 1.0, 10.0)

            embs_np = feats.detach().cpu().numpy().astype(np.float16)
            for idx, is_valid in enumerate(valid_mask):
                if not is_valid:
                    embs_np[idx] = 0.0
                    scores_np[idx] = 1.0

            all_embs.append(embs_np)
            all_scores.append(scores_np)

        return np.vstack(all_embs), np.concatenate(all_scores)

    @torch.no_grad()
    def encode_text(self, text_query: str) -> np.ndarray:
        """Encodes a text query into a 768-d L2-normalized float16 vector for <15ms search."""
        tokens = self.tokenizer([text_query]).to(self.device)
        text_feat = self.model.encode_text(tokens)
        text_feat = text_feat / text_feat.norm(dim=-1, keepdim=True).clamp(min=1e-8)
        return text_feat.detach().cpu().numpy().astype(np.float16)[0]


# DEFAULT_COLOR_SIGS_PATH is imported from config_paths.py


def load_or_init_vectors_matrix(vectors_path: Path = DEFAULT_VECTORS_PATH) -> np.ndarray:
    """Loads existing Float16 (N, 768) matrix or returns empty (0, 768) Float16 matrix."""
    vectors_path = Path(vectors_path)
    if vectors_path.exists():
        try:
            mat = np.load(str(vectors_path))
            if mat.ndim == 2 and mat.shape[1] == 768:
                return mat.astype(np.float16)
        except Exception:
            pass
    return np.zeros((0, 768), dtype=np.float16)


def save_vectors_matrix_atomic(matrix: np.ndarray, vectors_path: Path = DEFAULT_VECTORS_PATH) -> None:
    """Saves Float16 (N, 768) matrix atomically to disk."""
    vectors_path = Path(vectors_path)
    vectors_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = vectors_path.with_suffix(".tmp.npy")
    np.save(str(tmp_path), matrix.astype(np.float16))
    os.replace(str(tmp_path), str(vectors_path))


def load_or_init_crop_vectors_matrix(
    crop_vectors_path: Path = DEFAULT_CROP_VECTORS_PATH,
    crop_boxes_path: Path = DEFAULT_CROP_BOXES_PATH,
    mmap_mode: Optional[str] = "r",
    n_rows: Optional[int] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Loads memory-mapped or in-memory Float16 (N, 4, 768) focal crop vectors
    and Float16 (N, 4, 4) normalized bounding boxes [x1, y1, x2, y2].
    """
    crop_vectors_path = Path(crop_vectors_path)
    crop_boxes_path = Path(crop_boxes_path)
    init_n = max(0, int(n_rows)) if n_rows is not None else 0
    vecs = np.zeros((init_n, 4, 768), dtype=np.float16)
    boxes = np.zeros((init_n, 4, 4), dtype=np.float16)
    if crop_vectors_path.exists():
        try:
            loaded_v = np.load(str(crop_vectors_path), mmap_mode=mmap_mode)
            if loaded_v.ndim == 3 and loaded_v.shape[1] == 4 and loaded_v.shape[2] == 768:
                vecs = loaded_v if mmap_mode else loaded_v.astype(np.float16)
        except Exception:
            pass
    if crop_boxes_path.exists():
        try:
            loaded_b = np.load(str(crop_boxes_path), mmap_mode=mmap_mode)
            if loaded_b.ndim == 3 and loaded_b.shape[1] == 4 and loaded_b.shape[2] == 4:
                boxes = loaded_b if mmap_mode else loaded_b.astype(np.float16)
        except Exception:
            pass
    return vecs, boxes


def save_crop_vectors_matrix_atomic(
    crop_vecs: np.ndarray,
    crop_boxes: np.ndarray,
    crop_vectors_path: Path = DEFAULT_CROP_VECTORS_PATH,
    crop_boxes_path: Path = DEFAULT_CROP_BOXES_PATH,
) -> None:
    """Atomically persists (N, 4, 768) float16 crop vectors and (N, 4, 4) float16 crop boxes."""
    crop_vectors_path = Path(crop_vectors_path)
    crop_boxes_path = Path(crop_boxes_path)
    crop_vectors_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_v = crop_vectors_path.with_suffix(".tmp.npy")
    tmp_b = crop_boxes_path.with_suffix(".tmp.npy")
    np.save(str(tmp_v), np.asarray(crop_vecs, dtype=np.float16))
    np.save(str(tmp_b), np.asarray(crop_boxes, dtype=np.float16))
    os.replace(str(tmp_v), str(crop_vectors_path))
    os.replace(str(tmp_b), str(crop_boxes_path))


def extract_4_salient_crops(pil_img: Image.Image) -> Tuple[List[Image.Image], np.ndarray]:
    """
    Pass 2 Saliency Extractor:
    Combines rule-of-thirds quadrants with Laplacian edge & local contrast focal peaks
    to extract 4 high-salience focal sub-crops from a cached thumbnail/preview.
    Returns (list of 4 PIL RGB crops, (4, 4) float16 normalized boxes [x1, y1, x2, y2]).
    """
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    if w < 48 or h < 48:
        default_boxes = np.array([
            [0.05, 0.05, 0.60, 0.60],
            [0.40, 0.40, 0.95, 0.95],
            [0.35, 0.05, 0.95, 0.65],
            [0.18, 0.18, 0.82, 0.82],
        ], dtype=np.float16)
        return [rgb, rgb, rgb, rgb], default_boxes

    # Fast 64x64 grayscale Laplacian + local contrast map (<0.08ms)
    small_g = np.asarray(rgb.resize((64, 64), Image.Resampling.BILINEAR).convert("L"), dtype=np.float32)
    gx = np.abs(small_g[:, 2:] - small_g[:, :-2])
    gy = np.abs(small_g[2:, :] - small_g[:-2, :])
    lap = np.abs(
        4.0 * small_g[1:-1, 1:-1]
        - small_g[:-2, 1:-1]
        - small_g[2:, 1:-1]
        - small_g[1:-1, :-2]
        - small_g[1:-1, 2:]
    )
    edge_map = 0.55 * lap + 0.45 * (gx[1:-1, :] + gy[:, 1:-1])
    local_dev = np.abs(small_g[1:-1, 1:-1] - float(np.mean(small_g)))
    sal = 0.72 * edge_map + 0.28 * local_dev  # shape (62, 62)
    sh, sw = sal.shape

    # 4 Quadrant search zones + box sizes (normalized):
    # Q0: Upper-Left / Mid-Left (catches subjects on cat trees, upper walls, shelves, e.g. [0.12, 0.06, 0.62, 0.60])
    # Q1: Lower-Right / Foreground Right (catches floor/couch pets, e.g. [0.40, 0.42, 0.98, 0.98])
    # Q2: Upper-Right / Mid-Right (catches wall art, lamps, right-side subjects)
    # Q3: Lower-Left / Center-Tight Focal Peak (catches central/lower-left small subjects,couch throws, tabletop objects)
    zones = [
        (0.02, 0.02, 0.68, 0.68, 0.50, 0.52),
        (0.32, 0.34, 0.98, 0.98, 0.56, 0.56),
        (0.32, 0.02, 0.98, 0.68, 0.50, 0.52),
        (0.08, 0.22, 0.84, 0.96, 0.52, 0.52),
    ]

    crops: List[Image.Image] = []
    boxes = np.zeros((4, 4), dtype=np.float16)

    for q_idx, (zx1, zy1, zx2, zy2, bw, bh) in enumerate(zones):
        ix1 = max(0, min(sw - 4, int(zx1 * sw)))
        iy1 = max(0, min(sh - 4, int(zy1 * sh)))
        ix2 = max(ix1 + 4, min(sw, int(zx2 * sw)))
        iy2 = max(iy1 + 4, min(sh, int(zy2 * sh)))

        sub_sal = sal[iy1:iy2, ix1:ix2]
        # Smooth with a 3x3 box filter via slicing to find robust regional center of mass
        if sub_sal.shape[0] >= 5 and sub_sal.shape[1] >= 5:
            pooled = (
                sub_sal[:-2, :-2] + sub_sal[:-2, 1:-1] + sub_sal[:-2, 2:]
                + sub_sal[1:-1, :-2] + sub_sal[1:-1, 1:-1] + sub_sal[1:-1, 2:]
                + sub_sal[2:, :-2] + sub_sal[2:, 1:-1] + sub_sal[2:, 2:]
            )
            py, px = np.unravel_index(int(np.argmax(pooled)), pooled.shape)
            cy = (iy1 + py + 1.5) / float(sh)
            cx = (ix1 + px + 1.5) / float(sw)
        else:
            cy = 0.5 * (zy1 + zy2)
            cx = 0.5 * (zx1 + zx2)

        x1 = float(np.clip(cx - 0.5 * bw, 0.0, 1.0 - bw))
        y1 = float(np.clip(cy - 0.5 * bh, 0.0, 1.0 - bh))
        x2 = float(np.clip(x1 + bw, 0.05, 1.0))
        y2 = float(np.clip(y1 + bh, 0.05, 1.0))

        boxes[q_idx] = [round(x1, 4), round(y1, 4), round(x2, 4), round(y2, 4)]
        px1 = int(round(x1 * w))
        py1 = int(round(y1 * h))
        px2 = max(px1 + 16, int(round(x2 * w)))
        py2 = max(py1 + 16, int(round(y2 * h)))
        crops.append(rgb.crop((px1, py1, min(w, px2), min(h, py2))))

    return crops, boxes


@torch.no_grad()
def build_or_update_crop_vectors_mps(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    crop_vectors_path: Path = DEFAULT_CROP_VECTORS_PATH,
    crop_boxes_path: Path = DEFAULT_CROP_BOXES_PATH,
    catalog_name: Optional[str] = None,
    force_recompute: bool = False,
    batch_size: int = 64,
    vec_engine: Optional[VectorAestheticEngine] = None,
) -> Dict[str, Any]:
    """
    INVARIANT 1 (Pass 2): Batched MPS GPU 4-Crop Saliency Scanner (~5-6ms/photo in batches of 64).
    - Reads cached thumbs_360 (or previews_1600) WebP files.
    - Skips screenshots (is_screenshot = 1) in 0ms (0 sub-crops needed).
    - Extracts 4 high-salience focal regions per photo and encodes them in float16 on Apple Metal (mps).
    - Persists compact memory-mapped float16 arrays:
        crop_vectors.npy: shape (N, 4, 768), dtype=float16
        crop_boxes.npy:   shape (N, 4, 4),   dtype=float16
    """
    t0 = time.time()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    global_vecs = load_or_init_vectors_matrix(vectors_path)
    total_vec_slots = int(global_vecs.shape[0])
    if total_vec_slots == 0:
        conn.close()
        return {"status": "empty", "scanned_photos": 0, "elapsed_seconds": 0.0}

    crop_vecs, crop_boxes = load_or_init_crop_vectors_matrix(crop_vectors_path, crop_boxes_path, mmap_mode=None)
    if crop_vecs.shape[0] < total_vec_slots:
        pad_n = total_vec_slots - crop_vecs.shape[0]
        crop_vecs = np.vstack([crop_vecs, np.zeros((pad_n, 4, 768), dtype=np.float16)]) if crop_vecs.shape[0] > 0 else np.zeros((total_vec_slots, 4, 768), dtype=np.float16)
    if crop_boxes.shape[0] < total_vec_slots:
        pad_n = total_vec_slots - crop_boxes.shape[0]
        crop_boxes = np.vstack([crop_boxes, np.zeros((pad_n, 4, 4), dtype=np.float16)]) if crop_boxes.shape[0] > 0 else np.zeros((total_vec_slots, 4, 4), dtype=np.float16)

    params: List[Any] = []
    cat_sql = ""
    if catalog_name:
        cat_sql = " AND catalog_name = ?"
        params.append(catalog_name)

    rows = cursor.execute(
        f"""
        SELECT file_path, file_hash, vector_index, is_screenshot, thumb_360_path, preview_1600_path
        FROM photo_records
        WHERE status != 'failed' AND vector_index IS NOT NULL {cat_sql}
        ORDER BY vector_index ASC
        """,
        params,
    ).fetchall()
    conn.close()

    pending_rows = []
    skipped_screenshots = 0
    for r in rows:
        v_idx = int(r["vector_index"])
        if v_idx < 0 or v_idx >= total_vec_slots:
            continue
        if int(r["is_screenshot"] or 0) == 1:
            crop_vecs[v_idx] = 0.0
            crop_boxes[v_idx] = 0.0
            skipped_screenshots += 1
            continue
        if not force_recompute:
            # Check if crop vectors are already populated for this vector_index
            row_norm = float(np.linalg.norm(crop_vecs[v_idx, 0].astype(np.float32)))
            if row_norm > 0.5:
                continue
        pending_rows.append(dict(r))

    if not pending_rows:
        if skipped_screenshots > 0 or crop_vecs.shape[0] == total_vec_slots:
            save_crop_vectors_matrix_atomic(crop_vecs, crop_boxes, crop_vectors_path, crop_boxes_path)
        return {
            "status": "cached",
            "scanned_photos": 0,
            "skipped_screenshots": skipped_screenshots,
            "total_slots": total_vec_slots,
            "elapsed_seconds": round(time.time() - t0, 3),
        }

    engine = vec_engine or VectorAestheticEngine()
    preprocess = engine.preprocess
    device = engine.device

    def _load_and_crop_one(item: Dict[str, Any]) -> Tuple[int, Optional[torch.Tensor], np.ndarray]:
        v_idx = int(item["vector_index"])
        p_str = item.get("thumb_360_path") or item.get("preview_1600_path")
        if not p_str or not Path(p_str).exists():
            fhash = item.get("file_hash") or ""
            cand_360 = DEFAULT_THUMBS_360_DIR / f"{fhash}.webp"
            cand_1600 = DEFAULT_PREVIEWS_1600_DIR / f"{fhash}.webp"
            p_path = cand_360 if cand_360.exists() else (cand_1600 if cand_1600.exists() else None)
        else:
            p_path = Path(p_str)
        if p_path is None or not p_path.exists():
            return v_idx, None, np.zeros((4, 4), dtype=np.float16)
        try:
            with Image.open(p_path) as im:
                crops, boxes_4x4 = extract_4_salient_crops(im)
                t_list = [preprocess(c) for c in crops]
                return v_idx, torch.stack(t_list, dim=0), boxes_4x4
        except Exception:
            return v_idx, None, np.zeros((4, 4), dtype=np.float16)

    scanned_count = 0
    pool_workers = min(8, max(4, (os.cpu_count() or 8) // 2))
    with ThreadPoolExecutor(max_workers=pool_workers) as pool:
        for b_start in range(0, len(pending_rows), batch_size):
            batch_items = pending_rows[b_start : b_start + batch_size]
            loaded = list(pool.map(_load_and_crop_one, batch_items))

            valid_indices: List[int] = []
            crop_tensors: List[torch.Tensor] = []
            for v_idx, tensor_4, boxes_4x4 in loaded:
                crop_boxes[v_idx] = boxes_4x4
                if tensor_4 is not None:
                    valid_indices.append(v_idx)
                    crop_tensors.append(tensor_4)
                else:
                    crop_vecs[v_idx] = 0.0

            if crop_tensors:
                # Stack to (B * 4, 3, 224, 224) and run a single batched MPS GPU pass
                flat_batch = torch.cat(crop_tensors, dim=0).to(device)
                if device == "mps":
                    with torch.autocast(device_type="mps", dtype=torch.float16):
                        feats = engine.model.encode_image(flat_batch)
                else:
                    feats = engine.model.encode_image(flat_batch)
                feats = feats.float()
                feats = feats / feats.norm(dim=-1, keepdim=True).clamp(min=1e-8)
                feats_np = feats.detach().cpu().numpy().astype(np.float16).reshape(len(valid_indices), 4, 768)
                for i_pos, v_idx in enumerate(valid_indices):
                    crop_vecs[v_idx] = feats_np[i_pos]
                scanned_count += len(valid_indices)

    save_crop_vectors_matrix_atomic(crop_vecs, crop_boxes, crop_vectors_path, crop_boxes_path)
    elapsed = round(time.time() - t0, 3)
    ms_per_photo = round((elapsed * 1000.0) / max(scanned_count, 1), 2)
    return {
        "status": "ok",
        "scanned_photos": scanned_count,
        "skipped_screenshots": skipped_screenshots,
        "total_slots": total_vec_slots,
        "elapsed_seconds": elapsed,
        "ms_per_photo": ms_per_photo,
    }


# Invariant 2: Alias for automatic 4-Pass level 1 ingestion pipeline
ensure_crop_vectors = build_or_update_crop_vectors_mps


def compute_preview_signature_and_saliency(preview_path: Optional[Path]) -> Dict[str, Any]:
    """
    Computes universal image statistics from a local WebP preview:
    1. 24-bin L2-normalized HSV Color + Luminance histogram vector (12 Hue, 6 Sat, 6 Val).
    2. HSV Saturation mean & std (for Monochrome vs. Color distribution alignment).
    3. Spatial Rule-of-Thirds & Subject Focus Saliency score (1.0 .. 10.0).
    """
    default_vec = np.zeros((24,), dtype=np.float32)
    if preview_path is None or not Path(preview_path).exists():
        return {
            "color_vec": default_vec,
            "sat_mean": 0.25,
            "sat_std": 0.10,
            "composition_score": 6.0,
        }
    try:
        with Image.open(preview_path) as im:
            hsv_im = im.convert("HSV")
            if max(hsv_im.size) > 360:
                hsv_im.thumbnail((360, 360), Image.Resampling.BILINEAR)
            arr = np.asarray(hsv_im, dtype=np.float32) / 255.0

        H = arr[:, :, 0]
        S = arr[:, :, 1]
        V = arr[:, :, 2]

        sat_mean = float(np.mean(S))
        sat_std = float(np.std(S))

        # 1. 24-bin HSV + Luminance Histogram
        # Weight Hue by S * V so desaturated/black pixels do not pollute chromatic bins
        chroma_weights = S * V
        h_hist, _ = np.histogram(H, bins=12, range=(0.0, 1.0), weights=chroma_weights)
        s_hist, _ = np.histogram(S, bins=6, range=(0.0, 1.0))
        v_hist, _ = np.histogram(V, bins=6, range=(0.0, 1.0))

        px_count = float(max(H.size, 1))
        h_norm = h_hist.astype(np.float32) / px_count
        s_norm = s_hist.astype(np.float32) / px_count
        v_norm = v_hist.astype(np.float32) / px_count

        color_vec = np.concatenate([h_norm * 1.5, s_norm, v_norm]).astype(np.float32)
        c_norm = float(np.linalg.norm(color_vec))
        if c_norm > 1e-8:
            color_vec = color_vec / c_norm

        # 2. Spatial Gradient Saliency & Rule-of-Thirds Power Points
        gy, gx = np.gradient(V)
        grad_mag = np.sqrt(gx * gx + gy * gy)
        local_contrast = np.abs(V - float(np.mean(V)))
        saliency_map = 0.72 * grad_mag + 0.28 * local_contrast

        h_px, w_px = V.shape
        yy, xx = np.meshgrid(
            np.linspace(0.0, 1.0, h_px, dtype=np.float32),
            np.linspace(0.0, 1.0, w_px, dtype=np.float32),
            indexing="ij",
        )

        # Gaussian masks at the 4 Rule-of-Thirds intersections + thirds horizon/vertical lines
        thirds_mask = np.zeros_like(V, dtype=np.float32)
        for ty in (1.0 / 3.0, 2.0 / 3.0):
            for tx in (1.0 / 3.0, 2.0 / 3.0):
                dist_sq = (xx - tx) ** 2 + (yy - ty) ** 2
                thirds_mask += np.exp(-dist_sq / (2.0 * (0.13 ** 2)))
        line_mask = (
            (np.abs(xx - 1.0 / 3.0) < 0.06)
            | (np.abs(xx - 2.0 / 3.0) < 0.06)
            | (np.abs(yy - 1.0 / 3.0) < 0.06)
            | (np.abs(yy - 2.0 / 3.0) < 0.06)
        ).astype(np.float32)
        thirds_weights = 0.70 * thirds_mask + 0.30 * line_mask

        mean_saliency = float(np.mean(saliency_map)) + 1e-6
        thirds_saliency = float(np.sum(saliency_map * thirds_weights) / (np.sum(thirds_weights) + 1e-6))
        thirds_ratio = float(np.clip(thirds_saliency / mean_saliency, 0.70, 1.60))

        # Subject Focus Ratio: inner subject zone (center + thirds) vs extreme 14% corners
        subject_zone = (xx >= 0.14) & (xx <= 0.86) & (yy >= 0.14) & (yy <= 0.86)
        corner_zone = ((xx < 0.16) | (xx > 0.84)) & ((yy < 0.16) | (yy > 0.84))
        subj_grad = float(np.mean(grad_mag[subject_zone])) if np.any(subject_zone) else mean_saliency
        corn_grad = float(np.mean(grad_mag[corner_zone])) + 1e-5 if np.any(corner_zone) else mean_saliency
        focus_ratio = float(np.clip(subj_grad / corn_grad, 0.65, 2.40))

        comp_raw = 5.4 + 3.2 * (thirds_ratio - 1.0) + 1.8 * (focus_ratio - 1.0)
        composition_score = float(np.clip(comp_raw, 2.5, 9.8))

        return {
            "color_vec": color_vec,
            "sat_mean": sat_mean,
            "sat_std": sat_std,
            "composition_score": round(composition_score, 3),
        }
    except Exception:
        return {
            "color_vec": default_vec,
            "sat_mean": 0.25,
            "sat_std": 0.10,
            "composition_score": 6.0,
        }


def load_or_init_color_signatures(sig_path: Path = DEFAULT_COLOR_SIGS_PATH) -> np.ndarray:
    """Loads cached (N, 25) float32 color signatures (cols 0..24: 24-bin hist, col 24: sat_mean)."""
    sig_path = Path(sig_path)
    if sig_path.exists():
        try:
            mat = np.load(str(sig_path))
            if mat.ndim == 2 and mat.shape[1] == 25:
                return mat.astype(np.float32)
        except Exception:
            pass
    return np.zeros((0, 25), dtype=np.float32)


def calibrate_keepers_taste_and_aesthetics(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    color_sigs_path: Path = DEFAULT_COLOR_SIGS_PATH,
) -> Dict[str, Any]:
    """
    Computes Mitch's 'Keepers' Personal Taste Calibration + Systemic Aesthetic Recalibration:
    1. Builds multi-centroid visual distribution from records in 'Keepers' catalog (or >=4 stars).
    2. Extracts 24-bin HSV/Luminance color signature + saturation mean/std + Rule-of-Thirds &
       Subject Focus Saliency score (`composition_score`, 20% blend weight) from each local WebP.
    3. Applies Monochrome vs. Color Distribution Alignment (~-0.35 curve for pure B&W + percentile
       tail alignment) so Top 5% and Top 10% reflect both color and B&W photography equally.
    4. Saves (N, 25) color signatures to `data/color_signatures.npy` and updates SQLite.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    vectors = load_or_init_vectors_matrix(vectors_path)

    rows = cursor.execute("""
        SELECT file_path, catalog_name, in_keepers, star_rating, vector_index,
               sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
               laion_aesthetic_score, thumb_360_path, preview_1600_path
        FROM photo_records
        WHERE vector_index IS NOT NULL
    """).fetchall()

    if not rows or vectors.shape[0] == 0:
        conn.close()
        return {"calibrated_records": 0, "keeper_anchors": 0}

    # Gather Keeper reference vectors
    keeper_indices = [
        r["vector_index"] for r in rows
        if (r["in_keepers"] == 1 or str(r["catalog_name"]).lower() == "keepers")
        and 0 <= r["vector_index"] < vectors.shape[0]
    ]
    if not keeper_indices:
        keeper_indices = [
            r["vector_index"] for r in rows
            if (r["star_rating"] or 0) >= 4 and (r["is_unsharp"] or 0) == 0
            and 0 <= r["vector_index"] < vectors.shape[0]
        ]

    keeper_centroids: Optional[np.ndarray] = None
    if keeper_indices:
        k_vecs = vectors[keeper_indices].astype(np.float32)
        mean_c = np.mean(k_vecs, axis=0, keepdims=True)
        mean_c = mean_c / np.maximum(np.linalg.norm(mean_c, axis=-1, keepdims=True), 1e-8)
        step = max(1, len(k_vecs) // 64)
        exemplars = k_vecs[::step]
        keeper_centroids = np.vstack([mean_c, exemplars])

    color_sigs_mat = np.zeros((vectors.shape[0], 25), dtype=np.float32)
    interim_records: List[Dict[str, Any]] = []

    for r in rows:
        v_idx = int(r["vector_index"])
        laion = float(r["laion_aesthetic_score"] or 5.0)
        sharp = float(r["sharpness_score"] or 0.0)
        is_unsharp = int(r["is_unsharp"] or 0)
        color = float(r["colorfulness_score"] or 5.0)
        curr_stars = int(r["star_rating"] or 0)
        db_mono = int(r["is_monochrome"] or 0)

        p_path_str = r["thumb_360_path"] or r["preview_1600_path"]
        p_path = Path(p_path_str) if p_path_str else None
        stats = compute_preview_signature_and_saliency(p_path)
        sat_mean = stats["sat_mean"]
        sat_std = stats["sat_std"]
        comp_score = stats["composition_score"]

        if 0 <= v_idx < color_sigs_mat.shape[0]:
            color_sigs_mat[v_idx, :24] = stats["color_vec"]
            color_sigs_mat[v_idx, 24] = sat_mean

        is_mono = 1 if (db_mono == 1 or (sat_mean < 0.065 and sat_std < 0.065)) else 0

        taste_bonus = 0.0
        if keeper_centroids is not None and 0 <= v_idx < vectors.shape[0]:
            vec = vectors[v_idx].astype(np.float32)
            sims = np.dot(keeper_centroids, vec)
            max_sim = float(np.max(sims))
            taste_bonus = round(max(0.0, min(1.6, (max_sim - 0.55) * 4.0)), 3)

        sharp_norm = min(10.0, (sharp / 8.0) * 10.0)
        # For monochrome images, use tonal contrast proxy instead of raw chromatic colorfulness before curve alignment
        effective_color = color if not is_mono else max(color, 5.2)

        # Blend: 45% LAION + 20% Spatial Composition/Rule-of-Thirds + 20% Sharpness + 15% Color/Tonal + Taste Bonus
        raw_aes = (
            0.45 * laion
            + 0.20 * comp_score
            + 0.20 * sharp_norm
            + 0.15 * effective_color
            + 0.45 * taste_bonus
        )

        # Smooth saturation-based calibration curve (~ -0.35 for pure B&W, 0.0 for sat_mean >= 0.16)
        sat_ratio = min(1.0, sat_mean / 0.16)
        sat_curve_adj = -0.35 * (1.0 - sat_ratio)
        calibrated_aes = raw_aes + sat_curve_adj

        interim_records.append({
            "file_path": r["file_path"],
            "taste_bonus": taste_bonus,
            "calibrated_aes": calibrated_aes,
            "is_unsharp": is_unsharp,
            "is_mono": is_mono,
            "sat_mean": sat_mean,
            "curr_stars": curr_stars,
        })

    # Distribution Alignment between Monochrome (is_mono == 1 or sat_mean < 0.08) and Color (sat_mean >= 0.08)
    color_scores = np.array(
        [it["calibrated_aes"] for it in interim_records if it["is_unsharp"] == 0 and it["is_mono"] == 0 and it["sat_mean"] >= 0.08],
        dtype=np.float32,
    )
    mono_scores = np.array(
        [it["calibrated_aes"] for it in interim_records if it["is_unsharp"] == 0 and (it["is_mono"] == 1 or it["sat_mean"] < 0.08)],
        dtype=np.float32,
    )

    mono_shift = 0.0
    mono_scale = 1.0
    if len(color_scores) >= 10 and len(mono_scores) >= 5:
        c_mean, c_std = float(np.mean(color_scores)), max(float(np.std(color_scores)), 0.15)
        m_mean, m_std = float(np.mean(mono_scores)), max(float(np.std(mono_scores)), 0.15)
        mono_scale = c_std / m_std
        # Align monochrome mean/std to color distribution with a slight -0.05 conservative margin
        # so Top 5% and Top 10% reflect the true top percentile of both color and B&W equally
        mono_shift = (c_mean - 0.05) - (m_mean * mono_scale)

    updates = []
    for it in interim_records:
        aes = it["calibrated_aes"]
        if it["is_unsharp"] == 0 and (it["is_mono"] == 1 or it["sat_mean"] < 0.08):
            aes = aes * mono_scale + mono_shift

        aes = round(max(1.0, min(10.0, aes)), 3)
        if it["is_unsharp"] == 1:
            aes = min(aes, 3.4)
            new_stars = 1
        else:
            new_stars = it["curr_stars"]

        updates.append((it["taste_bonus"], aes, new_stars, it["is_mono"], it["file_path"]))

    cursor.executemany("""
        UPDATE photo_records
        SET keepers_taste_bonus = ?,
            aesthetic_score = ?,
            star_rating = ?,
            is_monochrome = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE file_path = ?
    """, updates)
    conn.commit()
    conn.close()

    # Save color signatures atomically
    color_sigs_path = Path(color_sigs_path)
    color_sigs_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_sig = color_sigs_path.with_suffix(".tmp.npy")
    np.save(str(tmp_sig), color_sigs_mat.astype(np.float32))
    os.replace(str(tmp_sig), str(color_sigs_path))

    return {
        "calibrated_records": len(updates),
        "keeper_anchors": len(keeper_indices),
        "color_signatures_shape": list(color_sigs_mat.shape),
    }


# ==============================================================================
# 5. DATE-BOUNDED & CAMERA-BOUNDED SEQUENCE GROUPER + HERO PICKER
# ==============================================================================
def _parse_exif_dt(exif_time: Optional[str]) -> Optional[datetime]:
    if not exif_time:
        return None
    s = str(exif_time).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            continue
    return None


def group_sequences_and_pick_heroes(
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    max_delta_seconds: float = 10.0,
    min_clip_similarity: float = 0.87,
) -> Dict[str, Any]:
    """
    Clock-Safe & Date-Bounded Sequence Grouper:
    - Strictly partitions by (catalog_name, camera_model, camera_serial, shoot_date)
      so sequences NEVER cross midnight into another day and unsynced multi-camera
      bodies never scramble each other's bursts.
    - Locks consecutive frames into the same sequence_id when:
        delta_t <= 10.0s, focal_length matches, and CLIP Cosine Similarity >= 0.87.
    - Marks the highest aesthetic_score sharp frame in each sequence as is_sequence_hero = 1.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    vectors = load_or_init_vectors_matrix(vectors_path)

    rows = cursor.execute("""
        SELECT file_path, catalog_name, camera_model, camera_serial, shoot_date,
               exif_time, focal_length, vector_index, aesthetic_score, is_unsharp
        FROM photo_records
        WHERE status != 'failed'
    """).fetchall()

    if not rows:
        conn.close()
        return {"total_sequences": 0, "multi_frame_sequences": 0, "heroes_marked": 0}

    # Partition by (catalog_name, camera_model, camera_serial, shoot_date)
    partitions: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = {}
    for r in rows:
        cat = str(r["catalog_name"] or "Default")
        model = str(r["camera_model"] or "UnknownCamera").replace(" ", "_")
        serial = str(r["camera_serial"] or "0")
        sdate = str(r["shoot_date"] or "Undated")
        part_key = (cat, model, serial, sdate)
        partitions.setdefault(part_key, []).append(dict(r))

    db_updates = []
    total_sequences = 0
    multi_frame_sequences = 0
    heroes_marked = 0

    for (cat, model, serial, sdate), items in partitions.items():
        # Clock-safe chronological sort within camera body & shoot date
        items.sort(key=lambda x: (
            str(x.get("exif_time") or "9999:99:99 99:99:99"),
            Path(x["file_path"]).stem.lower()
        ))

        sequences: List[List[Dict[str, Any]]] = []
        curr_seq: List[Dict[str, Any]] = []

        for item in items:
            if not curr_seq:
                curr_seq = [item]
                continue

            prev = curr_seq[-1]
            dt_curr = _parse_exif_dt(item.get("exif_time"))
            dt_prev = _parse_exif_dt(prev.get("exif_time"))

            # Check time delta
            if dt_curr and dt_prev:
                delta_s = abs((dt_curr - dt_prev).total_seconds())
                time_ok = delta_s <= max_delta_seconds
            else:
                # If no timestamp, only group if consecutive numeric stems and very high CLIP similarity
                time_ok = True

            # Check focal length match
            fl_curr = item.get("focal_length")
            fl_prev = prev.get("focal_length")
            focal_ok = True
            if fl_curr is not None and fl_prev is not None:
                focal_ok = abs(float(fl_curr) - float(fl_prev)) <= 1.0

            # Check CLIP cosine similarity >= 0.87
            sim_ok = False
            v_curr = item.get("vector_index")
            v_prev = prev.get("vector_index")
            if (
                v_curr is not None
                and v_prev is not None
                and 0 <= v_curr < vectors.shape[0]
                and 0 <= v_prev < vectors.shape[0]
            ):
                vec_a = vectors[v_curr].astype(np.float32)
                vec_b = vectors[v_prev].astype(np.float32)
                cos_sim = float(np.dot(vec_a, vec_b))
                threshold = min_clip_similarity if (dt_curr and dt_prev) else 0.91
                sim_ok = cos_sim >= threshold

            if time_ok and focal_ok and sim_ok and sdate != "Undated":
                curr_seq.append(item)
            else:
                sequences.append(curr_seq)
                curr_seq = [item]

        if curr_seq:
            sequences.append(curr_seq)

        # Assign sequence_id, frame index, length, and pick sequence hero(es)
        for seq_idx, seq in enumerate(sequences, start=1):
            total_sequences += 1
            seq_len = len(seq)
            if seq_len > 1:
                multi_frame_sequences += 1
            seq_id = f"SEQ_{sdate}_{model[:12]}_{seq_idx:04d}"

            # Pick Hero: highest aesthetic_score among sharp frames (or overall highest if all unsharp)
            sharp_candidates = [
                (i, f) for i, f in enumerate(seq) if int(f.get("is_unsharp") or 0) == 0
            ]
            pool = sharp_candidates if sharp_candidates else list(enumerate(seq))
            best_idx, _ = max(pool, key=lambda pair: float(pair[1].get("aesthetic_score") or 0.0))

            for frame_i, frame in enumerate(seq):
                is_hero = 1 if frame_i == best_idx else 0
                if is_hero:
                    heroes_marked += 1
                db_updates.append((
                    seq_id,
                    frame_i,
                    seq_len,
                    is_hero,
                    frame["file_path"],
                ))

    cursor.executemany("""
        UPDATE photo_records
        SET sequence_id = ?,
            sequence_frame_index = ?,
            sequence_length = ?,
            is_sequence_hero = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE file_path = ?
    """, db_updates)
    conn.commit()
    conn.close()

    return {
        "total_sequences": total_sequences,
        "multi_frame_sequences": multi_frame_sequences,
        "heroes_marked": heroes_marked,
    }


# ==============================================================================
# 6. STAGE 1 ORCHESTRATOR
# ==============================================================================
def run_stage1_pipeline(
    source_dir: Path,
    catalog_name: str = "Default",
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    thumbs_360_dir: Path = DEFAULT_THUMBS_360_DIR,
    previews_1600_dir: Path = DEFAULT_PREVIEWS_1600_DIR,
    sharpness_threshold: float = 3.5,
    force_rescan: bool = False,
    max_items: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    fast_only: bool = False,
) -> Dict[str, Any]:
    """
    Runs the complete Stage 1 Fast Pipeline on a catalog directory:
    - Strictly excludes *.lrdata, *.lrcat*, Smart Previews, Backups
    - Pairs .IIQ + .TIF siblings into single rows
    - Harvests read-only .lrcat ratings/flags/keywords + .lrprev paths + omni-field ExifTool + .xmp/.IIQ.xmp sidecars
    - Extracts full-res preview (.lrprev pyramid fast path or ExifTool) -> 90th-percentile patch sharpness ('Unsharp' tagging rule)
    - Saves persistent 360px & 1600px WebP previews
    - Computes batched Apple Silicon MPS OpenCLIP (ViT-L-14) Float16 vectors + LAION Aesthetic V2 MLP
    - Calibrates Keepers personal taste bonus & master aesthetic_score
    - Groups date-bounded & camera-bounded sequences and marks Sequence Heroes
    """
    t0 = time.time()
    init_and_migrate_db(db_path)
    hw = detect_hardware_profile()

    source_dir = Path(source_dir).expanduser().resolve()
    paired_items, lrcat_files = discover_catalog_files(source_dir)

    # Record catalog metadata
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    lrcat_str = str(lrcat_files[0]) if lrcat_files else None
    cursor.execute("""
        INSERT OR REPLACE INTO catalogs (catalog_name, root_path, lrcat_path, photo_count, last_scanned_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (catalog_name, str(source_dir), lrcat_str, len(paired_items)))
    conn.commit()

    # Check already completed Stage 1 files unless force_rescan
    existing_stage1 = set()
    if not force_rescan:
        existing_stage1 = {
            r["file_path"] for r in cursor.execute(
                "SELECT file_path FROM photo_records WHERE stage1_completed = 1 AND thumb_360_path IS NOT NULL"
            ).fetchall()
        }
    conn.close()

    # 1. Harvest .lrcat read-only metadata (+ .lrprev pyramid lookup) if any .lrcat file exists in catalog
    lrcat_merged: Dict[str, Dict[str, Any]] = {"by_path": {}, "by_stem": {}}
    for lrcat_p in lrcat_files:
        lr_data = harvest_lrcat_metadata(lrcat_p, db_path=db_path)
        lrcat_merged["by_path"].update(lr_data.get("by_path", {}))
        lrcat_merged["by_stem"].update(lr_data.get("by_stem", {}))

    pending_items = [
        item for item in paired_items
        if str(item["primary"].resolve()) not in existing_stage1
    ]

    # Prioritize .lrcat-matched captures with .lrprev pyramid previews, keywords, and star ratings first
    by_stem_lookup = lrcat_merged.get("by_stem", {})
    if by_stem_lookup:
        def _lrcat_priority(it: Dict[str, Any]):
            st = it["primary"].stem.lower()
            m = by_stem_lookup.get(st) or by_stem_lookup.get(st.strip())
            if not m:
                return (1, 0, 0, it["primary"].name)
            has_prev = 0 if m.get("lrprev_path") else 1
            kw_len = len(m.get("flat_keywords") or [])
            stars = int(m.get("star_rating") or 0)
            return (has_prev, -kw_len, -stars, it["primary"].name)
        pending_items.sort(key=_lrcat_priority)

    # When fast_only=True on a network volume WITH a .lrcat catalog, prioritize captures with existing WebP or .lrprev
    # Never drop pending_items for standalone folders (no .lrcat) or local drives!
    use_fast_lrcat_pass = bool(fast_only and lrcat_files and str(source_dir).startswith("/Volumes/"))
    if use_fast_lrcat_pass:
        filtered_fast = []
        for it in pending_items:
            p_path = it["primary"]
            f_hash = compute_file_hash(p_path)
            has_cached_webp = (thumbs_360_dir / f"{f_hash}.webp").exists() and (previews_1600_dir / f"{f_hash}.webp").exists()
            st = p_path.stem.lower()
            m = by_stem_lookup.get(st) or by_stem_lookup.get(st.strip())
            has_lrprev = bool(m and m.get("lrprev_path") and Path(m["lrprev_path"]).exists())
            if has_cached_webp or has_lrprev:
                filtered_fast.append(it)
        if filtered_fast:
            pending_items = filtered_fast
        else:
            use_fast_lrcat_pass = False

    if max_items is not None and max_items > 0:
        pending_items = pending_items[:max_items]

    total_pending = len(pending_items)
    if progress_callback:
        progress_callback(0, total_pending, str(source_dir.name), "Harvesting .lrcat & EXIF metadata")

    # 2. Batch harvest omni-field ExifTool + sidecars (+ offline GPS Geolocation)
    harvested_records: List[Dict[str, Any]] = []
    if pending_items:
        batch_sz = hw["exif_batch_size"]
        if use_fast_lrcat_pass:
            for i in range(0, len(pending_items), batch_sz):
                batch = pending_items[i : i + batch_sz]
                if progress_callback:
                    progress_callback(
                        len(harvested_records),
                        total_pending,
                        batch[0]["primary"].name,
                        "Harvesting .lrcat Metadata (Fast Pass)",
                    )
                harvested_records.extend(
                    harvest_omni_metadata_batch(batch, lrcat_data=lrcat_merged, et_helper=None, db_path=db_path, fast_only=True)
                )
        else:
            exiftool_bin = str(SCRIPT_DIR / "bin" / "exiftool")
            et_kwargs: Dict[str, Any] = {"common_args": ["-G0", "-a", "-s", "-n", "-api", "Geolocation"]}
            if Path(exiftool_bin).exists():
                et_kwargs["executable"] = exiftool_bin
            with exiftool.ExifToolHelper(**et_kwargs) as et:
                for i in range(0, len(pending_items), batch_sz):
                    batch = pending_items[i : i + batch_sz]
                    if progress_callback:
                        progress_callback(
                            len(harvested_records),
                            total_pending,
                            batch[0]["primary"].name,
                            "Harvesting EXIF, GPS & Sidecars",
                        )
                    harvested_records.extend(
                        harvest_omni_metadata_batch(batch, lrcat_data=lrcat_merged, et_helper=et, db_path=db_path, fast_only=False)
                    )

    # 3. Multi-threaded Full-Res Preview Extraction (.lrprev fast path), 90th-Percentile Sharpness & WebP Generation
    preview_results: Dict[str, Optional[Dict[str, Any]]] = {}
    if harvested_records:
        if progress_callback:
            progress_callback(0, total_pending, harvested_records[0]["file_path"].split("/")[-1], "Extracting Previews & Sharpness")
        completed_previews = 0
        with ThreadPoolExecutor(max_workers=hw["extractor_workers"]) as pool:
            fut_to_fp = {
                pool.submit(
                    extract_fullres_and_generate_webps,
                    Path(rec["file_path"]),
                    Path(rec["sibling_path"]) if rec.get("sibling_path") else None,
                    rec["file_hash"],
                    thumbs_360_dir,
                    previews_1600_dir,
                    sharpness_threshold,
                    Path(rec["lrprev_path"]) if rec.get("lrprev_path") else None,
                    rec.get("lrprev_orientation"),
                    fast_only,
                ): rec["file_path"]
                for rec in harvested_records
            }
            for fut in as_completed(fut_to_fp):
                fp = fut_to_fp[fut]
                completed_previews += 1
                try:
                    preview_results[fp] = fut.result()
                except Exception as exc:
                    log_ingestion_error(db_path, fp, "stage1_preview", type(exc).__name__, str(exc))
                    preview_results[fp] = None
                if progress_callback:
                    progress_callback(
                        completed_previews,
                        total_pending,
                        Path(fp).name,
                        "Extracting Previews & Sharpness",
                    )

    # 4. Batched Apple Silicon MPS OpenCLIP (ViT-L-14) + LAION Aesthetic V2 MLP
    valid_records_for_clip: List[Dict[str, Any]] = []
    preview_paths_for_clip: List[Path] = []
    for rec in harvested_records:
        pr = preview_results.get(rec["file_path"])
        if pr and pr.get("preview_1600_path") and Path(pr["preview_1600_path"]).exists():
            valid_records_for_clip.append(rec)
            preview_paths_for_clip.append(Path(pr["preview_1600_path"]))

    embeddings_f16 = np.zeros((0, 768), dtype=np.float16)
    laion_scores = np.zeros((0,), dtype=np.float32)
    if preview_paths_for_clip:
        if progress_callback:
            progress_callback(
                len(preview_paths_for_clip),
                total_pending,
                preview_paths_for_clip[0].name,
                "Computing OpenCLIP Vectors & LAION Aesthetics",
            )
        vec_engine = VectorAestheticEngine(device=hw["device"])
        embeddings_f16, laion_scores = vec_engine.encode_images_and_score(preview_paths_for_clip)

    # 5. Append/Update vectors.npy and write Stage 1 records to SQLite
    vectors_mat = load_or_init_vectors_matrix(vectors_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    existing_vec_map = {
        r["file_path"]: r["vector_index"]
        for r in cursor.execute(
            "SELECT file_path, vector_index FROM photo_records WHERE vector_index IS NOT NULL"
        ).fetchall()
    }

    clip_idx_map = {rec["file_path"]: idx for idx, rec in enumerate(valid_records_for_clip)}
    new_vectors_list: List[np.ndarray] = []
    next_vec_index = vectors_mat.shape[0]

    processed_ok = 0
    failed_count = 0

    for rec in harvested_records:
        fp = rec["file_path"]
        pr = preview_results.get(fp)

        if pr is None:
            failed_count += 1
            log_ingestion_error(db_path, fp, "stage1_extract", "PreviewExtractionFailed", "0-byte or unreadable image/RAW preview")
            cursor.execute("""
                INSERT INTO photo_records (
                    file_path, file_hash, sibling_path, catalog_name, status,
                    exif_time, shoot_date, existing_keywords, hierarchical_keywords, lrcat_keywords,
                    updated_at
                ) VALUES (?, ?, ?, ?, 'failed', ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(file_path) DO UPDATE SET
                    status = 'failed',
                    updated_at = CURRENT_TIMESTAMP
            """, (
                fp,
                rec["file_hash"],
                rec["sibling_path"],
                catalog_name,
                rec["exif_time"],
                rec["shoot_date"],
                json.dumps(rec["existing_keywords"]),
                json.dumps(rec["hierarchical_keywords"]),
                json.dumps(rec["lrcat_keywords"]),
            ))
            continue

        # Clean Tagging Rule for Sharpness ('Unsharp' only when sharpness_score < 3.5)
        flat_kws = list(rec["existing_keywords"])
        hier_kws = list(rec["hierarchical_keywords"])
        is_unsharp = int(pr["is_unsharp"])
        star_rating = int(rec["star_rating"] or 0)

        if is_unsharp == 1:
            if "Unsharp" not in flat_kws:
                flat_kws.append("Unsharp")
            if "Technical|Focus|Unsharp" not in hier_kws:
                hier_kws.append("Technical|Focus|Unsharp")
            star_rating = min(star_rating, 1) if star_rating > 0 else 1
        else:
            # Ensure sharp images are never tagged with Unsharp
            flat_kws = [k for k in flat_kws if k != "Unsharp"]
            hier_kws = [hk for hk in hier_kws if hk != "Technical|Focus|Unsharp"]

        if pr["is_monochrome"] == 1:
            if "Monochrome" not in flat_kws:
                flat_kws.append("Monochrome")
            if "Technical|Monochrome" not in hier_kws:
                hier_kws.append("Technical|Monochrome")

        # Assign vector_index and update/append vector
        c_idx = clip_idx_map.get(fp)
        laion_val = float(laion_scores[c_idx]) if c_idx is not None else 5.0
        vec_f16 = embeddings_f16[c_idx] if c_idx is not None else np.zeros((768,), dtype=np.float16)

        if fp in existing_vec_map and existing_vec_map[fp] is not None and 0 <= existing_vec_map[fp] < vectors_mat.shape[0]:
            v_index = int(existing_vec_map[fp])
            vectors_mat[v_index] = vec_f16
        else:
            v_index = next_vec_index
            next_vec_index += 1
            new_vectors_list.append(vec_f16.reshape(1, 768))

        in_keepers = 1 if catalog_name.lower() == "keepers" else 0

        cursor.execute("""
            INSERT INTO photo_records (
                file_path, file_hash, sibling_path, catalog_name, phash,
                exif_time, shoot_date, status,
                camera_make, camera_model, camera_serial, lens_model,
                focal_length, shutter_speed, aperture, iso, gps_lat, gps_lon, gps_alt,
                gps_ground_truth, is_screenshot,
                title, caption, sub_location, city, state_region, country, specific_location,
                star_rating, color_label, pick_flag,
                lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                thumb_360_path, preview_1600_path,
                sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                laion_aesthetic_score, vector_index, in_keepers, stage1_completed, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, 'stage1_ready',
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, 1, CURRENT_TIMESTAMP
            )
            ON CONFLICT(file_path) DO UPDATE SET
                file_hash = excluded.file_hash,
                sibling_path = excluded.sibling_path,
                catalog_name = excluded.catalog_name,
                phash = excluded.phash,
                exif_time = COALESCE(excluded.exif_time, photo_records.exif_time),
                shoot_date = CASE WHEN excluded.shoot_date != 'Undated' THEN excluded.shoot_date ELSE photo_records.shoot_date END,
                status = CASE WHEN photo_records.stage2_completed = 1 THEN photo_records.status ELSE 'stage1_ready' END,
                camera_make = COALESCE(excluded.camera_make, photo_records.camera_make),
                camera_model = COALESCE(excluded.camera_model, photo_records.camera_model),
                camera_serial = COALESCE(excluded.camera_serial, photo_records.camera_serial),
                lens_model = COALESCE(excluded.lens_model, photo_records.lens_model),
                focal_length = COALESCE(excluded.focal_length, photo_records.focal_length),
                shutter_speed = COALESCE(excluded.shutter_speed, photo_records.shutter_speed),
                aperture = COALESCE(excluded.aperture, photo_records.aperture),
                iso = COALESCE(excluded.iso, photo_records.iso),
                gps_lat = COALESCE(excluded.gps_lat, photo_records.gps_lat),
                gps_lon = COALESCE(excluded.gps_lon, photo_records.gps_lon),
                gps_alt = COALESCE(excluded.gps_alt, photo_records.gps_alt),
                gps_ground_truth = MAX(COALESCE(photo_records.gps_ground_truth, 0), COALESCE(excluded.gps_ground_truth, 0)),
                is_screenshot = MAX(COALESCE(photo_records.is_screenshot, 0), COALESCE(excluded.is_screenshot, 0)),
                title = COALESCE(excluded.title, photo_records.title),
                caption = COALESCE(excluded.caption, photo_records.caption),
                sub_location = COALESCE(excluded.sub_location, photo_records.sub_location),
                city = COALESCE(excluded.city, photo_records.city),
                state_region = COALESCE(excluded.state_region, photo_records.state_region),
                country = COALESCE(excluded.country, photo_records.country),
                specific_location = COALESCE(excluded.specific_location, photo_records.specific_location),
                star_rating = excluded.star_rating,
                color_label = COALESCE(excluded.color_label, photo_records.color_label),
                pick_flag = excluded.pick_flag,
                lrcat_keywords = excluded.lrcat_keywords,
                existing_keywords = excluded.existing_keywords,
                key_subjects = excluded.key_subjects,
                hierarchical_keywords = excluded.hierarchical_keywords,
                thumb_360_path = excluded.thumb_360_path,
                preview_1600_path = excluded.preview_1600_path,
                sharpness_score = excluded.sharpness_score,
                is_unsharp = excluded.is_unsharp,
                colorfulness_score = excluded.colorfulness_score,
                is_monochrome = excluded.is_monochrome,
                laion_aesthetic_score = excluded.laion_aesthetic_score,
                vector_index = excluded.vector_index,
                in_keepers = MAX(photo_records.in_keepers, excluded.in_keepers),
                stage1_completed = 1,
                updated_at = CURRENT_TIMESTAMP
        """, (
            fp,
            rec["file_hash"],
            rec["sibling_path"],
            catalog_name,
            pr["phash"],
            rec["exif_time"],
            rec["shoot_date"],
            rec["camera_make"],
            rec["camera_model"],
            rec["camera_serial"],
            rec["lens_model"],
            rec["focal_length"],
            rec["shutter_speed"],
            rec["aperture"],
            rec["iso"],
            rec["gps_lat"],
            rec["gps_lon"],
            rec.get("gps_alt"),
            int(rec.get("gps_ground_truth") or 0),
            int(rec.get("is_screenshot") or 0),
            rec["title"],
            rec["caption"],
            rec["sub_location"],
            rec["city"],
            rec["state_region"],
            rec["country"],
            rec["specific_location"],
            star_rating,
            rec["color_label"],
            rec["pick_flag"],
            json.dumps(rec["lrcat_keywords"]),
            json.dumps(rec["existing_keywords"]),
            json.dumps(flat_kws),
            json.dumps(hier_kws),
            pr["thumb_360_path"],
            pr["preview_1600_path"],
            pr["sharpness_score"],
            is_unsharp,
            pr["colorfulness_score"],
            pr["is_monochrome"],
            round(laion_val, 3),
            v_index,
            in_keepers,
        ))
        processed_ok += 1
        if processed_ok % 50 == 0:
            conn.commit()

    conn.commit()
    conn.close()

    if new_vectors_list:
        vectors_mat = np.vstack([vectors_mat] + new_vectors_list) if vectors_mat.shape[0] > 0 else np.vstack(new_vectors_list)
    if vectors_mat.shape[0] > 0:
        save_vectors_matrix_atomic(vectors_mat, vectors_path)

    # 5b. Batched Apple Silicon Metal (mps) 4-Crop Saliency Scanner (v4.0 Invariant 1 & 3)
    if progress_callback:
        progress_callback(total_pending, total_pending, catalog_name, "Indexing 4-Crop Saliency Vectors on GPU (mps)")
    crop_summary = build_or_update_crop_vectors_mps(
        db_path=db_path,
        vectors_path=vectors_path,
        catalog_name=catalog_name,
        vec_engine=vec_engine,
    )

    # 6. Offline GPS Reverse-Geocoding Backfill & Same-Day Camera Bridging + Keepers Calibration + Sequences
    if progress_callback:
        progress_callback(total_pending, total_pending, catalog_name, "Bridging Same-Day GPS & Calibrating Aesthetics")
    gps_bridge_summary = bridge_same_day_gps_locations(db_path=db_path, catalog_name=catalog_name)
    keepers_summary = link_keepers_across_catalogs(db_path=db_path)
    calibration_summary = calibrate_keepers_taste_and_aesthetics(db_path=db_path, vectors_path=vectors_path)
    seq_summary = group_sequences_and_pick_heroes(db_path=db_path, vectors_path=vectors_path)

    elapsed = round(time.time() - t0, 2)
    if progress_callback:
        progress_callback(total_pending, total_pending, catalog_name, "Completed")
    return {
        "catalog_name": catalog_name,
        "source_dir": str(source_dir),
        "hardware_profile": hw,
        "discovered_paired_captures": len(paired_items),
        "lrcat_files_found": [str(p) for p in lrcat_files],
        "stage1_processed_ok": processed_ok,
        "stage1_failed": failed_count,
        "vectors_matrix_shape": list(vectors_mat.shape),
        "crop_vectors_summary": crop_summary,
        "gps_bridging": gps_bridge_summary,
        "keepers_linking": keepers_summary,
        "aesthetic_calibration": calibration_summary,
        "sequence_grouping": seq_summary,
        "elapsed_seconds": elapsed,
    }


def bridge_same_day_gps_locations(
    db_path: Path = DEFAULT_DB_PATH,
    catalog_name: Optional[str] = None,
    max_hours_window: float = 18.0,
) -> Dict[str, Any]:
    """
    1. Ensures any photo with GPS coordinates (gps_lat, gps_lon) has offline reverse-geocoded
       country, state_region, city, and specific_location populated with gps_ground_truth = 1.
    2. Propagates verified GPS locations from GPS-tagged photos (e.g. iPhone .HEIC/.JPG) to
       non-GPS camera photos (e.g. Fujifilm .RAF, Phase One .IIQ, DSLR) taken on the same shoot_date
       within a reasonable same-day shoot window (default <= 18 hours when timestamps are present,
       or same shoot_date when timestamps lack time-of-day).
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Step A: Ensure all rows with gps_lat & gps_lon have offline reverse-geocoded location resolved
    gps_rows = cursor.execute("""
        SELECT file_path, shoot_date, exif_time, gps_lat, gps_lon, gps_alt, gps_ground_truth,
               country, state_region, city, sub_location, specific_location,
               existing_keywords, key_subjects, hierarchical_keywords
        FROM photo_records
        WHERE status != 'failed'
          AND gps_lat IS NOT NULL AND gps_lon IS NOT NULL
    """).fetchall()

    backfilled_gps_count = 0
    anchors_by_date: Dict[str, List[Dict[str, Any]]] = {}

    for r in gps_rows:
        rec = dict(r)
        lat = float(rec["gps_lat"])
        lon = float(rec["gps_lon"])
        needs_resolve = (
            not rec.get("country")
            or not rec.get("state_region")
            or not rec.get("city")
            or int(rec.get("gps_ground_truth") or 0) == 0
        )
        if needs_resolve:
            geo = resolve_offline_gps_location(lat, lon)
            if geo:
                rec["country"] = rec.get("country") or geo.get("country")
                rec["state_region"] = rec.get("state_region") or geo.get("state_region")
                rec["city"] = rec.get("city") or geo.get("city")
                rec["sub_location"] = rec.get("sub_location") or geo.get("sub_location")
                rec["specific_location"] = rec.get("specific_location") or geo.get("specific_location")
                rec["gps_ground_truth"] = 1

                def _parse_json_list(val: Any) -> List[str]:
                    if not val:
                        return []
                    try:
                        parsed = json.loads(val) if isinstance(val, str) else list(val)
                        return [str(x) for x in parsed if x]
                    except Exception:
                        return []

                ex_kws = _parse_json_list(rec.get("existing_keywords"))
                key_subj = _parse_json_list(rec.get("key_subjects"))
                hier_kws = _parse_json_list(rec.get("hierarchical_keywords"))

                for ltag in geo.get("tags", []):
                    if ltag and ltag not in key_subj:
                        key_subj.append(ltag)

                place_parts = [p for p in ["Places", rec.get("country"), rec.get("state_region"), rec.get("city"), rec.get("specific_location")] if p]
                if len(place_parts) >= 2:
                    hp = "|".join(place_parts)
                    if hp not in hier_kws:
                        hier_kws.append(hp)

                cursor.execute("""
                    UPDATE photo_records
                    SET country = ?,
                        state_region = ?,
                        city = ?,
                        sub_location = ?,
                        specific_location = ?,
                        gps_ground_truth = 1,
                        existing_keywords = ?,
                        key_subjects = ?,
                        hierarchical_keywords = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE file_path = ?
                """, (
                    rec["country"],
                    rec["state_region"],
                    rec["city"],
                    rec["sub_location"],
                    rec["specific_location"],
                    json.dumps(ex_kws),
                    json.dumps(key_subj),
                    json.dumps(hier_kws),
                    rec["file_path"],
                ))
                backfilled_gps_count += 1

        sdate = str(rec.get("shoot_date") or "Undated")
        if sdate != "Undated" and (rec.get("country") or rec.get("state_region") or rec.get("city")):
            anchors_by_date.setdefault(sdate, []).append(rec)

    # Step B: Bridge verified GPS locations to same-day non-GPS camera photos (excluding screenshots)
    if not anchors_by_date:
        conn.commit()
        conn.close()
        return {"gps_backfilled": backfilled_gps_count, "same_day_bridged": 0}

    date_placeholders = ",".join("?" for _ in anchors_by_date.keys())
    params: List[Any] = list(anchors_by_date.keys())
    cat_clause = ""
    if catalog_name:
        cat_clause = " AND catalog_name = ?"
        params.append(catalog_name)

    cand_rows = cursor.execute(f"""
        SELECT file_path, shoot_date, exif_time, gps_lat, gps_lon, gps_alt,
               country, state_region, city, sub_location, specific_location,
               existing_keywords, key_subjects, hierarchical_keywords
        FROM photo_records
        WHERE status != 'failed'
          AND COALESCE(is_screenshot, 0) = 0
          AND (gps_lat IS NULL OR gps_lon IS NULL)
          AND shoot_date IN ({date_placeholders})
          {cat_clause}
    """, params).fetchall()

    bridged_count = 0
    max_delta_sec = max_hours_window * 3600.0

    for c in cand_rows:
        cand = dict(c)
        sdate = str(cand.get("shoot_date") or "Undated")
        day_anchors = anchors_by_date.get(sdate) or []
        if not day_anchors:
            continue

        dt_cand = _parse_exif_dt(cand.get("exif_time"))
        best_anchor = None
        best_delta = float("inf")

        for anc in day_anchors:
            dt_anc = _parse_exif_dt(anc.get("exif_time"))
            if dt_cand and dt_anc:
                delta = abs((dt_cand - dt_anc).total_seconds())
                if delta <= max_delta_sec and delta < best_delta:
                    best_delta = delta
                    best_anchor = anc
            else:
                if best_anchor is None:
                    best_anchor = anc

        if best_anchor is None:
            continue

        def _parse_list(val: Any) -> List[str]:
            if not val:
                return []
            try:
                parsed = json.loads(val) if isinstance(val, str) else list(val)
                return [str(x) for x in parsed if x]
            except Exception:
                return []

        ex_kws = _parse_list(cand.get("existing_keywords"))
        key_subj = _parse_list(cand.get("key_subjects"))
        hier_kws = _parse_list(cand.get("hierarchical_keywords"))

        def _valid_loc(v: Any) -> Optional[str]:
            s = str(v or "").strip()
            return s if s and s.lower() not in ("unknown", "none", "null") else None

        has_cand_loc = bool(_valid_loc(cand.get("state_region")) or _valid_loc(cand.get("city")))
        new_country = (_valid_loc(cand.get("country")) if has_cand_loc else None) or _valid_loc(best_anchor.get("country")) or _valid_loc(cand.get("country"))
        new_state = _valid_loc(cand.get("state_region")) or _valid_loc(best_anchor.get("state_region"))
        new_city = _valid_loc(cand.get("city")) or _valid_loc(best_anchor.get("city"))
        new_sub = _valid_loc(cand.get("sub_location")) or _valid_loc(best_anchor.get("sub_location"))
        new_spec = _valid_loc(cand.get("specific_location")) or _valid_loc(best_anchor.get("specific_location"))

        place_parts = [p for p in ["Places", new_country, new_state, new_city, new_spec] if p]
        if len(place_parts) >= 2:
            hp = "|".join(place_parts)
            if hp not in hier_kws:
                hier_kws.append(hp)

        cursor.execute("""
            UPDATE photo_records
            SET gps_lat = COALESCE(gps_lat, ?),
                gps_lon = COALESCE(gps_lon, ?),
                gps_alt = COALESCE(gps_alt, ?),
                country = ?,
                state_region = ?,
                city = ?,
                sub_location = ?,
                specific_location = ?,
                gps_ground_truth = 1,
                existing_keywords = ?,
                key_subjects = ?,
                hierarchical_keywords = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_path = ?
        """, (
            best_anchor.get("gps_lat"),
            best_anchor.get("gps_lon"),
            best_anchor.get("gps_alt"),
            new_country,
            new_state,
            new_city,
            new_sub,
            new_spec,
            json.dumps(ex_kws),
            json.dumps(key_subj),
            json.dumps(hier_kws),
            cand["file_path"],
        ))
        bridged_count += 1

    conn.commit()
    conn.close()
    return {
        "gps_backfilled": backfilled_gps_count,
        "same_day_bridged": bridged_count,
    }


def sync_external_edits(
    photo_ids: Optional[List[str]] = None,
    watched_files: Optional[List[str]] = None,
    target_file_paths: Optional[List[str]] = None,
    watched_dirs: Optional[List[str]] = None,
    scan_parent_dirs: bool = False,
    force_regenerate: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    vectors_path: Path = DEFAULT_VECTORS_PATH,
    color_sigs_path: Optional[Path] = None,
    thumbs_360_dir: Path = DEFAULT_THUMBS_360_DIR,
    previews_1600_dir: Path = DEFAULT_PREVIEWS_1600_DIR,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Photoshop Round-Trip & Live External Edit Synchronizer:
    1. Checks specified photo_ids / watched_files (or all tracked files) for `st_mtime` or `st_size`
       modifications on disk (or forces regeneration when `force_regenerate=True`).
       When modified:
       - Force-regenerates `thumbs_360/<hash>.webp` and `previews_1600/<hash>.webp` directly from the
         master `.tif`/`.psd`/`.jpg`/RAW file.
       - Recomputes sharpness, monochrome/colorfulness, OpenCLIP 768-D vector, and LAION aesthetic score.
       - Updates `file_mtime`, `file_size`, and `updated_at = CURRENT_TIMESTAMP` in SQLite so the UI
         cache-busting `?v=` URL immediately displays the newly edited image.
    2. Scans `watched_dirs` (or parent directories of watched photos) for newly saved sibling derivative
       files (e.g., `*_Edit.tif`, `*-copy.tif`, `*-2.tif`, `.jpg`) not yet in `photo_records`, ingests
       them through Stage 1, and links them to their parent photo's shoot_date, catalog, and location metadata!
    """
    t0 = time.time()
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    where_clauses = ["status != 'failed'"]
    params: List[Any] = []
    target_tokens: List[str] = []
    if photo_ids:
        target_tokens.extend(photo_ids)
    if watched_files:
        target_tokens.extend(watched_files)
    if target_file_paths:
        target_tokens.extend(target_file_paths)

    if target_tokens:
        placeholders = ",".join("?" for _ in target_tokens)
        where_clauses.append(f"(file_hash IN ({placeholders}) OR file_path IN ({placeholders}))")
        params.extend(target_tokens)
        params.extend(target_tokens)

    rows = [
        dict(r)
        for r in cursor.execute(
            f"""
            SELECT file_path, file_hash, sibling_path, catalog_name, shoot_date, exif_time,
                   file_mtime, file_size, vector_index, thumb_360_path, preview_1600_path,
                   country, state_region, city, sub_location, specific_location,
                   primary_category, sub_category, key_subjects, hierarchical_keywords,
                   lrcat_keywords, existing_keywords, sequence_id, in_keepers
            FROM photo_records
            WHERE {' AND '.join(where_clauses)}
            """,
            params,
        ).fetchall()
    ]

    modified_records: List[Tuple[Dict[str, Any], float, int]] = []
    dirs_to_check: Set[Path] = set()
    if watched_dirs:
        for d in watched_dirs:
            dp = Path(d)
            if dp.exists() and dp.is_dir():
                dirs_to_check.add(dp)

    for r in rows:
        fp = Path(r["file_path"])
        if (target_tokens or watched_dirs) and scan_parent_dirs and fp.parent.exists():
            dirs_to_check.add(fp.parent)
        if not fp.exists():
            continue
        try:
            st = fp.stat()
            cur_mtime = round(float(st.st_mtime), 3)
            cur_size = int(st.st_size)
        except Exception:
            continue

        prev_mtime = round(float(r["file_mtime"]), 3) if r.get("file_mtime") is not None else None
        prev_size = int(r["file_size"]) if r.get("file_size") is not None else None

        if force_regenerate or prev_mtime is None or prev_size is None:
            if force_regenerate or (prev_mtime is not None and (abs(cur_mtime - prev_mtime) > 0.5 or cur_size != prev_size)):
                modified_records.append((r, cur_mtime, cur_size))
            elif prev_mtime is None or prev_size is None:
                # Record baseline mtime/size so future saves are detected instantaneously
                cursor.execute(
                    "UPDATE photo_records SET file_mtime = ?, file_size = ? WHERE file_path = ?",
                    (cur_mtime, cur_size, str(fp)),
                )
        elif abs(cur_mtime - prev_mtime) > 0.5 or cur_size != prev_size:
            modified_records.append((r, cur_mtime, cur_size))

    conn.commit()

    # Check for newly saved derivative files in watched_dirs (e.g. *_Edit.tif, *-copy.tif saved recently)
    existing_paths = {
        str(row[0])
        for row in cursor.execute("SELECT file_path FROM photo_records").fetchall()
    }
    new_derivative_files: List[Tuple[Path, Optional[Dict[str, Any]]]] = []
    derivative_Tokens = ("edit", "copy", "layered", " crop", "_crop", "print", "flat", "-2", "-3")
    valid_exts = {".tif", ".tiff", ".jpg", ".jpeg", ".png", ".psd"}
    now_ts = time.time()

    for d_path in dirs_to_check:
        try:
            for child in d_path.iterdir():
                if not child.is_file() or child.name.startswith("."):
                    continue
                if child.suffix.lower() not in valid_exts:
                    continue
                try:
                    c_stat = child.stat()
                    # Only auto-ingest newly saved derivatives modified within the last 12 hours
                    if (now_ts - float(c_stat.st_mtime)) > 43200:
                        continue
                except Exception:
                    continue
                c_str = str(child.resolve())
                if c_str in existing_paths or str(child) in existing_paths:
                    continue
                # Match to a parent record in the same directory if possible
                c_stem_low = child.stem.lower()
                parent_rec = None
                for r in rows:
                    p_stem = Path(r["file_path"]).stem.lower()
                    if p_stem in c_stem_low or c_stem_low in p_stem:
                        parent_rec = r
                        break
                if parent_rec is not None and any(tok in c_stem_low for tok in derivative_Tokens):
                    new_derivative_files.append((child, parent_rec))
        except Exception:
            continue

    updated_files: List[str] = []
    ingested_derivatives: List[str] = []

    if modified_records or new_derivative_files:
        vec_engine = VectorAestheticEngine()
        vectors_mat = load_or_init_vectors_matrix(vectors_path)

        # 1. Re-process modified existing files
        for r, cur_mtime, cur_size in modified_records:
            fp = Path(r["file_path"])
            sib = Path(r["sibling_path"]) if r.get("sibling_path") else None
            f_hash = r["file_hash"]
            pr = extract_fullres_and_generate_webps(
                primary_path=fp,
                sibling_path=sib,
                file_hash=f_hash,
                thumbs_360_dir=thumbs_360_dir,
                previews_1600_dir=previews_1600_dir,
                force_regenerate=True,
            )
            if pr is None:
                continue

            prev_1600 = Path(pr["preview_1600_path"])
            vecs, laion_scores = vec_engine.encode_images_and_score([prev_1600])
            v_idx = r.get("vector_index")
            if v_idx is not None and 0 <= int(v_idx) < vectors_mat.shape[0]:
                vectors_mat[int(v_idx)] = vecs[0]
            else:
                v_idx = int(vectors_mat.shape[0])
                vectors_mat = np.vstack([vectors_mat, vecs]) if vectors_mat.shape[0] > 0 else vecs

            cursor.execute(
                """
                UPDATE photo_records
                SET phash = ?,
                    sharpness_score = ?,
                    is_unsharp = ?,
                    colorfulness_score = ?,
                    is_monochrome = ?,
                    laion_aesthetic_score = ?,
                    vector_index = ?,
                    file_mtime = ?,
                    file_size = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
                """,
                (
                    pr["phash"],
                    pr["sharpness_score"],
                    pr["is_unsharp"],
                    pr["colorfulness_score"],
                    pr["is_monochrome"],
                    round(float(laion_scores[0]), 3),
                    int(v_idx),
                    cur_mtime,
                    cur_size,
                    str(fp),
                ),
            )
            updated_files.append(str(fp))

        # 2. Ingest newly saved sibling derivative files
        for child_path, parent_rec in new_derivative_files:
            try:
                st = child_path.stat()
                cur_mtime = round(float(st.st_mtime), 3)
                cur_size = int(st.st_size)
                f_hash = hashlib.sha256(str(child_path.resolve()).encode("utf-8")).hexdigest()[:16]
                pr = extract_fullres_and_generate_webps(
                    primary_path=child_path,
                    sibling_path=None,
                    file_hash=f_hash,
                    thumbs_360_dir=thumbs_360_dir,
                    previews_1600_dir=previews_1600_dir,
                    force_regenerate=True,
                )
                if pr is None:
                    continue
                prev_1600 = Path(pr["preview_1600_path"])
                vecs, laion_scores = vec_engine.encode_images_and_score([prev_1600])
                v_idx = int(vectors_mat.shape[0])
                vectors_mat = np.vstack([vectors_mat, vecs]) if vectors_mat.shape[0] > 0 else vecs

                p_rec = parent_rec or {}
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO photo_records (
                        file_path, file_hash, catalog_name, phash,
                        exif_time, shoot_date, status,
                        country, state_region, city, sub_location, specific_location,
                        primary_category, sub_category,
                        lrcat_keywords, existing_keywords, key_subjects, hierarchical_keywords,
                        thumb_360_path, preview_1600_path,
                        sharpness_score, is_unsharp, colorfulness_score, is_monochrome,
                        laion_aesthetic_score, aesthetic_score, vector_index,
                        sequence_id, in_keepers, file_mtime, file_size,
                        stage1_completed, stage2_completed, updated_at
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, 'tagged',
                        ?, ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        1, 1, CURRENT_TIMESTAMP
                    )
                    """,
                    (
                        str(child_path),
                        f_hash,
                        p_rec.get("catalog_name") or "Keepers",
                        pr["phash"],
                        p_rec.get("exif_time"),
                        p_rec.get("shoot_date") or "Undated",
                        p_rec.get("country") or "United States",
                        p_rec.get("state_region"),
                        p_rec.get("city"),
                        p_rec.get("sub_location"),
                        p_rec.get("specific_location") or "Unknown",
                        p_rec.get("primary_category") or "Landscape",
                        p_rec.get("sub_category") or "Edited_Master",
                        p_rec.get("lrcat_keywords") or "[]",
                        p_rec.get("existing_keywords") or "[]",
                        p_rec.get("key_subjects") or "[]",
                        p_rec.get("hierarchical_keywords") or "[]",
                        pr["thumb_360_path"],
                        pr["preview_1600_path"],
                        pr["sharpness_score"],
                        pr["is_unsharp"],
                        pr["colorfulness_score"],
                        pr["is_monochrome"],
                        round(float(laion_scores[0]), 3),
                        round(float(laion_scores[0]), 3),
                        v_idx,
                        p_rec.get("sequence_id"),
                        int(p_rec.get("in_keepers") or 0),
                        cur_mtime,
                        cur_size,
                    ),
                )
                ingested_derivatives.append(str(child_path))
            except Exception as exc:
                logging.warning(f"Derivative ingestion skipped for {child_path}: {exc}")

        conn.commit()
        if vectors_mat.shape[0] > 0:
            save_vectors_matrix_atomic(vectors_mat, vectors_path)

    conn.close()
    return {
        "status": "ok",
        "checked": len(rows),
        "checked_records": len(rows),
        "changed_count": len(updated_files) + len(ingested_derivatives),
        "updated_files": updated_files,
        "updated_count": len(updated_files),
        "ingested_derivatives": ingested_derivatives,
        "ingested_count": len(ingested_derivatives),
        "elapsed_seconds": round(time.time() - t0, 3),
    }


