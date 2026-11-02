#!/usr/bin/env python3
"""
Standalone macOS Application Builder & Custom .icns Icon Generator (scripts/build_macos_app.py)
MR Darkroom — Fine-Art Archival & Book Curation Studio

Generates:
1. High-resolution custom macOS icon (`AppIcon.icns`) using Pillow + macOS `iconutil`
   featuring a dark-mode studio rounded squircle, warm amber/gold panoramic lens ring,
   panoramic horizon frame, and bold "MR" monogram.
2. Standalone macOS app bundle (`MR Darkroom.app`) in both:
   - `./dist_app/MR Darkroom.app`
   - `~/Desktop/MR Darkroom.app`
"""

import math
import os
import plistlib
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def render_master_icon(size: int = 1024) -> Image.Image:
    """Renders a 1024x1024 dark-mode studio aperture & panoramic lens icon with 'MR' monogram."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    pad = int(size * 0.08)
    box = (pad, pad, size - pad, size - pad)
    radius = int(size * 0.21)

    # Outer drop glow / border
    _draw_rounded_rect(
        draw,
        (pad - 4, pad - 4, size - pad + 4, size - pad + 4),
        radius=radius + 4,
        fill=(245, 158, 11, 45),
    )

    # Main dark studio squircle body
    _draw_rounded_rect(
        draw,
        box,
        radius=radius,
        fill=(12, 15, 22, 255),
        outline=(245, 158, 11, 235),
        width=max(2, int(size * 0.022)),
    )

    # Subtle inner matte frame
    inner_pad = int(size * 0.125)
    _draw_rounded_rect(
        draw,
        (inner_pad, inner_pad, size - inner_pad, size - inner_pad),
        radius=int(radius * 0.82),
        fill=(18, 22, 33, 255),
        outline=(51, 65, 85, 180),
        width=max(1, int(size * 0.008)),
    )

    # Studio aperture ring in center
    cx, cy = size // 2, size // 2
    ring_r = int(size * 0.31)
    draw.ellipse(
        (cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r),
        fill=(10, 12, 18, 255),
        outline=(217, 119, 6, 210),
        width=max(2, int(size * 0.016)),
    )

    # Subtle aperture blades ticks
    for deg in range(0, 360, 45):
        rad = math.radians(deg)
        r1 = ring_r * 0.84
        r2 = ring_r * 0.96
        x1, y1 = cx + r1 * math.cos(rad), cy + r1 * math.sin(rad)
        x2, y2 = cx + r2 * math.cos(rad), cy + r2 * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=(251, 191, 36, 110), width=max(1, int(size * 0.008)))

    # Panoramic 2.2:1 golden ratio frame inside the lens
    pw = int(size * 0.44)
    ph = int(pw / 2.2)
    px1, py1 = cx - pw // 2, cy - ph // 2
    px2, py2 = cx + pw // 2, cy + ph // 2
    _draw_rounded_rect(
        draw,
        (px1, py1, px2, py2),
        radius=int(size * 0.025),
        fill=(17, 21, 32, 245),
        outline=(251, 191, 36, 255),
        width=max(2, int(size * 0.012)),
    )

    # Draw bold "MR" monogram in the center of the panoramic frame
    font_size = int(size * 0.165)
    font = None
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]:
        if os.path.exists(candidate):
            try:
                font = ImageFont.truetype(candidate, font_size)
                break
            except Exception:
                pass
    if font is None:
        font = ImageFont.load_default()

    text = "MR"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1]

    # Subtle shadow + bright gold monogram
    draw.text((tx + 2, ty + 3), text, font=font, fill=(0, 0, 0, 190))
    draw.text((tx, ty), text, font=font, fill=(251, 191, 36, 255))

    # Small "DARKROOM" label below aperture ring
    sub_size = int(size * 0.045)
    sub_font = None
    for candidate in [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        if os.path.exists(candidate):
            try:
                sub_font = ImageFont.truetype(candidate, sub_size)
                break
            except Exception:
                pass
    if sub_font:
        sub_text = "DARKROOM"
        sb = draw.textbbox((0, 0), sub_text, font=sub_font)
        stw = sb[2] - sb[0]
        draw.text(
            (cx - stw / 2 - sb[0], cy + ring_r + int(size * 0.032)),
            sub_text,
            font=sub_font,
            fill=(226, 232, 240, 215),
        )

    return img


def build_icns(output_icns_path: Path) -> Path:
    """Generates an Apple `.icns` file from our 1024x1024 master icon via `iconutil`."""
    master = render_master_icon(1024)
    output_icns_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        iconset_dir = Path(tmpdir) / "AppIcon.iconset"
        iconset_dir.mkdir(parents=True, exist_ok=True)

        sizes = [
            (16, "icon_16x16.png"),
            (32, "icon_16x16@2x.png"),
            (32, "icon_32x32.png"),
            (64, "icon_32x32@2x.png"),
            (128, "icon_128x128.png"),
            (256, "icon_128x128@2x.png"),
            (256, "icon_256x256.png"),
            (512, "icon_256x256@2x.png"),
            (512, "icon_512x512.png"),
            (1024, "icon_512x512@2x.png"),
        ]
        for px, fname in sizes:
            resized = master.resize((px, px), Image.Resampling.LANCZOS)
            resized.save(str(iconset_dir / fname), format="PNG")

        res = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_icns_path)],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            raise RuntimeError(f"iconutil failed: {res.stderr}")

    return output_icns_path


def create_app_bundle(target_app_path: Path, project_root: Path, icns_source: Path) -> Path:
    """Builds a standalone macOS `.app` bundle at `target_app_path`."""
    if target_app_path.exists():
        shutil.rmtree(str(target_app_path))

    contents_dir = target_app_path / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy AppIcon.icns
    shutil.copy2(str(icns_source), str(resources_dir / "AppIcon.icns"))

    # 2. Write Info.plist
    info_plist = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "MR Darkroom",
        "CFBundleExecutable": "MRDarkroom",
        "CFBundleIconFile": "AppIcon",
        "CFBundleIdentifier": "com.mrdarkroom.studio",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "MR Darkroom",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "3.2.0",
        "CFBundleVersion": "320",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    with open(contents_dir / "Info.plist", "wb") as f:
        plistlib.dump(info_plist, f)

    # 3. Write executable launcher script
    launcher_script = f"""#!/bin/zsh
# MR Darkroom — Standalone macOS Application Launcher
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

DEFAULT_PROJECT_ROOT="{project_root}"
if [ -d "$DEFAULT_PROJECT_ROOT" ] && [ -f "$DEFAULT_PROJECT_ROOT/server.py" ]; then
    PROJECT_ROOT="$DEFAULT_PROJECT_ROOT"
elif [ -d "$HOME/MRDarkroom" ] && [ -f "$HOME/MRDarkroom/server.py" ]; then
    PROJECT_ROOT="$HOME/MRDarkroom"
elif [ -d "$HOME/ai-raw-photo-archival-system" ] && [ -f "$HOME/ai-raw-photo-archival-system/server.py" ]; then
    PROJECT_ROOT="$HOME/ai-raw-photo-archival-system"
else
    PROJECT_ROOT="$DEFAULT_PROJECT_ROOT"
fi

VAULT_DIR="$HOME/Library/Application Support/MRDarkroom"
mkdir -p "$VAULT_DIR"
LOG_FILE="$VAULT_DIR/server.log"

export PATH="$PROJECT_ROOT/bin:$PROJECT_ROOT/.venv/bin:$PATH"

# 1. Ensure Ollama is running silently if installed
if command -v ollama >/dev/null 2>&1; then
    if ! pgrep -x "ollama" >/dev/null 2>&1; then
        nohup ollama serve >>"$VAULT_DIR/ollama.log" 2>&1 &
    fi
fi

# 2. Check if MR Darkroom FastAPI server is already listening on port 8501
if ! curl -s --max-time 1 "http://127.0.0.1:8501/api/photos?limit=1" >/dev/null 2>&1; then
    cd "$PROJECT_ROOT" || exit 1
    nohup "$PROJECT_ROOT/.venv/bin/python" -m uvicorn server:app --host 127.0.0.1 --port 8501 >>"$LOG_FILE" 2>&1 &

    # Wait up to 6 seconds for server readiness
    for i in {{1..24}}; do
        if curl -s --max-time 1 "http://127.0.0.1:8501/api/photos?limit=1" >/dev/null 2>&1; then
            break
        fi
        sleep 0.25
    done
fi

# 3. Launch dedicated chromeless app window (Google Chrome --app mode or default browser fallback)
APP_URL="http://127.0.0.1:8501"
if [ -d "/Applications/Google Chrome.app" ]; then
    open -na "Google Chrome" --args --app="$APP_URL"
elif [ -d "/Applications/Brave Browser.app" ]; then
    open -na "Brave Browser" --args --app="$APP_URL"
else
    open "$APP_URL"
fi
"""
    exec_path = macos_dir / "MRDarkroom"
    exec_path.write_text(launcher_script, encoding="utf-8")
    exec_path.chmod(exec_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Touch bundle to refresh Finder icon cache
    subprocess.run(["touch", str(target_app_path)], check=False)
    return target_app_path


def main():
    dist_dir = PROJECT_ROOT / "dist_app"
    dist_dir.mkdir(parents=True, exist_ok=True)
    icns_path = dist_dir / "AppIcon.icns"

    print("1. Rendering 1024x1024 studio icon & compiling AppIcon.icns...")
    build_icns(icns_path)
    print(f"   -> Built {icns_path}")

    repo_app = dist_dir / "MR Darkroom.app"
    desktop_app = Path.home() / "Desktop" / "MR Darkroom.app"

    print("2. Packaging ./dist_app/MR Darkroom.app...")
    create_app_bundle(repo_app, PROJECT_ROOT, icns_path)

    print("3. Installing ~/Desktop/MR Darkroom.app...")
    create_app_bundle(desktop_app, PROJECT_ROOT, icns_path)
    print(f"   -> Installed {desktop_app}")


if __name__ == "__main__":
    main()

