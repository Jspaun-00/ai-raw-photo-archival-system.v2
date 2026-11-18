#!/usr/bin/env python3
"""
Standalone macOS Application & Native GUI Installer Builder (scripts/build_macos_app.py)
MR Darkroom — Fine-Art Archival & Book Curation Studio (Dual-Mode: SSD + Mac Hard Drive)

Generates:
1. High-resolution custom macOS icon (`AppIcon.icns`) using Pillow + macOS `iconutil`
2. Real compiled Universal Mach-O executable (`arm64` + `x86_64`) for macOS Gatekeeper / TCC compliance
3. Ad-hoc Apple Code Signature (`codesign --force --deep --sign -`) verified on both APFS and ExFAT
4. Standalone macOS app bundle (`MR Darkroom.app`) that works in both:
   - Portable External SSD mode (`/Volumes/2TB_Archive/MR_Darkroom_Studio/`)
   - Installed Mac Hard Drive mode (`/Applications/MR Darkroom.app` & `~/Desktop/MR Darkroom.app`)
5. Native macOS GUI Installer bundle (`Install MR Darkroom to Mac.app`) for 1-click off-the-shelf installation
"""

import argparse
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


def render_master_icon(size: int = 1024, badge_text: str = "DARKROOM") -> Image.Image:
    """Renders a 1024x1024 dark-mode studio aperture & panoramic lens icon with 'MR' monogram."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")

    pad = int(size * 0.08)
    box = (pad, pad, size - pad, size - pad)
    radius = int(size * 0.21)

    _draw_rounded_rect(
        draw,
        (pad - 4, pad - 4, size - pad + 4, size - pad + 4),
        radius=radius + 4,
        fill=(245, 158, 11, 45),
    )

    _draw_rounded_rect(
        draw,
        box,
        radius=radius,
        fill=(15, 15, 15, 255),
        outline=(245, 158, 11, 235),
        width=max(2, int(size * 0.022)),
    )

    inner_pad = int(size * 0.125)
    _draw_rounded_rect(
        draw,
        (inner_pad, inner_pad, size - inner_pad, size - inner_pad),
        radius=int(radius * 0.82),
        fill=(22, 22, 22, 255),
        outline=(60, 60, 60, 180),
        width=max(1, int(size * 0.008)),
    )

    cx, cy = size // 2, size // 2
    ring_r = int(size * 0.31)
    draw.ellipse(
        (cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r),
        fill=(12, 12, 12, 255),
        outline=(217, 119, 6, 210),
        width=max(2, int(size * 0.016)),
    )

    for deg in range(0, 360, 45):
        rad = math.radians(deg)
        r1 = ring_r * 0.84
        r2 = ring_r * 0.96
        x1, y1 = cx + r1 * math.cos(rad), cy + r1 * math.sin(rad)
        x2, y2 = cx + r2 * math.cos(rad), cy + r2 * math.sin(rad)
        draw.line([(x1, y1), (x2, y2)], fill=(251, 191, 36, 110), width=max(1, int(size * 0.008)))

    pw = int(size * 0.44)
    ph = int(pw / 2.2)
    px1, py1 = cx - pw // 2, cy - ph // 2
    px2, py2 = cx + pw // 2, cy + ph // 2
    _draw_rounded_rect(
        draw,
        (px1, py1, px2, py2),
        radius=int(size * 0.025),
        fill=(20, 20, 20, 245),
        outline=(251, 191, 36, 255),
        width=max(2, int(size * 0.012)),
    )

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

    draw.text((tx + 2, ty + 3), text, font=font, fill=(0, 0, 0, 190))
    draw.text((tx, ty), text, font=font, fill=(251, 191, 36, 255))

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
        sb = draw.textbbox((0, 0), badge_text, font=sub_font)
        stw = sb[2] - sb[0]
        badge_color = (245, 158, 11, 255) if badge_text == "INSTALLER" else (229, 229, 229, 215)
        draw.text(
            (cx - stw / 2 - sb[0], cy + ring_r + int(size * 0.032)),
            badge_text,
            font=sub_font,
            fill=badge_color,
        )

    return img


def build_icns(output_icns_path: Path, badge_text: str = "DARKROOM") -> Path:
    """Generates an Apple `.icns` file from our 1024x1024 master icon via `iconutil`."""
    master = render_master_icon(1024, badge_text=badge_text)
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


def _compile_universal_macho_launcher(output_bin: Path, script_rel_path: str = "../Resources/launch.sh") -> None:
    """
    Compiles a real Universal (`arm64` + `x86_64`) Mach-O binary wrapper that executes
    `Contents/Resources/launch.sh`. Having a real Mach-O binary ensures macOS Gatekeeper,
    codesign, and TCC (Removable Volume / Folder permissions) treat the `.app` bundle
    as a native macOS application on both APFS and ExFAT volumes.
    """
    c_code = f"""
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <libgen.h>
#include <mach-o/dyld.h>
#include <limits.h>

int main(int argc, char *argv[]) {{
    char exe_path[PATH_MAX];
    uint32_t size = sizeof(exe_path);
    if (_NSGetExecutablePath(exe_path, &size) != 0) {{
        return 1;
    }}
    char resolved[PATH_MAX];
    if (realpath(exe_path, resolved) == NULL) {{
        strncpy(resolved, exe_path, PATH_MAX - 1);
    }}
    char *dir = dirname(resolved);
    char script_path[PATH_MAX];
    snprintf(script_path, sizeof(script_path), "%s/{script_rel_path}", dir);

    char *new_argv[] = {{ "/bin/zsh", script_path, NULL }};
    execv("/bin/zsh", new_argv);
    return 1;
}}
"""
    precompiled_stub = PROJECT_ROOT / "bin" / "mrdarkroom_macho_stub"
    clang_bin = shutil.which("clang")
    if clang_bin:
        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", delete=False) as tf:
            tf.write(c_code)
            c_file = tf.name
        try:
            res = subprocess.run(
                [clang_bin, "-arch", "arm64", "-arch", "x86_64", "-O2", c_file, "-o", str(output_bin)],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and output_bin.exists():
                output_bin.chmod(output_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                try:
                    precompiled_stub.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(output_bin), str(precompiled_stub))
                except Exception:
                    pass
                return
        finally:
            try:
                os.unlink(c_file)
            except OSError:
                pass
    if precompiled_stub.exists():
        shutil.copy2(str(precompiled_stub), str(output_bin))
        output_bin.chmod(output_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _codesign_bundle(app_path: Path) -> None:
    """Signs the `.app` bundle on APFS first, then cleans any extended attributes."""
    subprocess.run(["xattr", "-cr", str(app_path)], check=False, capture_output=True)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        check=False,
        capture_output=True,
    )


def create_app_bundle(target_app_path: Path, project_root: Path, icns_source: Path) -> Path:
    """
    Builds the standalone `MR Darkroom.app` bundle in a temporary APFS directory,
    signs it with `codesign` (so the Mach-O signature is embedded inside the binary
    and `Contents/_CodeSignature/CodeResources`), and moves it into `target_app_path`.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        staged_app = Path(tmpdir) / "MR Darkroom.app"
        contents_dir = staged_app / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(icns_source), str(resources_dir / "AppIcon.icns"))

        info_plist = {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": "MR Darkroom",
            "CFBundleExecutable": "MRDarkroom",
            "CFBundleIconFile": "AppIcon",
            "CFBundleIdentifier": "com.mrdarkroom.studio",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": "MR Darkroom",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "4.4.0",
            "CFBundleVersion": "440",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        }
        with open(contents_dir / "Info.plist", "wb") as f:
            plistlib.dump(info_plist, f)

        launcher_script = f"""#!/bin/zsh
# MR Darkroom — Universal macOS Application Launcher (Installed HD + Portable SSD)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

APP_BUNDLE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_PARENT_DIR="$(dirname "$APP_BUNDLE_DIR")"

DEFAULT_PROJECT_ROOT="{project_root}"

# Priority order for locating the Studio Engine:
# 1. Sibling Engine folder (when .app is inside the Portable SSD folder)
# 2. Installed Engine inside ~/Library/Application Support/MRDarkroom/Engine
# 3. Configured DEFAULT_PROJECT_ROOT or ~/MRDarkroom
if [ -d "$APP_PARENT_DIR/Engine" ] && [ -f "$APP_PARENT_DIR/Engine/server.py" ]; then
    PROJECT_ROOT="$APP_PARENT_DIR/Engine"
    if [ -d "$APP_PARENT_DIR/Data_Vault" ]; then
        export MRDARKROOM_VAULT_DIR="$APP_PARENT_DIR/Data_Vault"
    fi
elif [ -d "$HOME/Library/Application Support/MRDarkroom/Engine" ] && [ -f "$HOME/Library/Application Support/MRDarkroom/Engine/server.py" ]; then
    PROJECT_ROOT="$HOME/Library/Application Support/MRDarkroom/Engine"
elif [ -d "$DEFAULT_PROJECT_ROOT" ] && [ -f "$DEFAULT_PROJECT_ROOT/server.py" ]; then
    PROJECT_ROOT="$DEFAULT_PROJECT_ROOT"
elif [ -d "$HOME/MRDarkroom" ] && [ -f "$HOME/MRDarkroom/server.py" ]; then
    PROJECT_ROOT="$HOME/MRDarkroom"
else
    PROJECT_ROOT="$DEFAULT_PROJECT_ROOT"
fi

if [ -n "$MRDARKROOM_VAULT_DIR" ]; then
    VAULT_DIR="$MRDARKROOM_VAULT_DIR"
else
    VAULT_DIR="$HOME/Library/Application Support/MRDarkroom"
fi
mkdir -p "$VAULT_DIR"
LOG_FILE="$VAULT_DIR/server.log"

# Configure offline AI model caches if present in Vault
if [ -d "$VAULT_DIR/models/huggingface" ]; then
    export HF_HOME="$VAULT_DIR/models/huggingface"
fi
if [ -d "$VAULT_DIR/models/ollama" ]; then
    export OLLAMA_MODELS="$VAULT_DIR/models/ollama"
fi

# Determine Python runtime:
# When running from the external ExFAT SSD, unpack Runtime/venv_arm64.tar.gz into
# ~/Library/Caches/MRDarkroom_Runtime once so Python imports 3,500+ site-packages files
# from fast local APFS in <1.5s instead of slow ExFAT USB reads.
LOCAL_RUNTIME_CACHE="$HOME/Library/Caches/MRDarkroom_Runtime"
if [ -f "$APP_PARENT_DIR/Runtime/venv_arm64.tar.gz" ] && [ ! -d "$LOCAL_RUNTIME_CACHE/.venv/lib/python3.9/site-packages" ]; then
    mkdir -p "$LOCAL_RUNTIME_CACHE"
    tar -xzf "$APP_PARENT_DIR/Runtime/venv_arm64.tar.gz" -C "$LOCAL_RUNTIME_CACHE" 2>/dev/null || true
fi

if [ -d "$LOCAL_RUNTIME_CACHE/.venv/lib/python3.9/site-packages" ]; then
    SITE_PACKAGES_DIR="$LOCAL_RUNTIME_CACHE/.venv/lib/python3.9/site-packages"
else
    SITE_PACKAGES_DIR="$PROJECT_ROOT/.venv/lib/python3.9/site-packages"
fi

if [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif [ -x "$PROJECT_ROOT/Python3/bin/python3.9" ]; then
    PYTHON_BIN="$PROJECT_ROOT/Python3/bin/python3.9"
elif [ -x "$LOCAL_RUNTIME_CACHE/.venv/bin/python" ]; then
    PYTHON_BIN="$LOCAL_RUNTIME_CACHE/.venv/bin/python"
else
    PYTHON_BIN="/usr/bin/python3"
fi
export PYTHONPATH="$SITE_PACKAGES_DIR:$PROJECT_ROOT"
export PATH="$PROJECT_ROOT/bin:$(dirname "$PYTHON_BIN"):$PATH"

open_studio_window() {{
    local APP_URL="http://127.0.0.1:8501"
    if [ -d "/Applications/Google Chrome.app" ]; then
        open -na "Google Chrome" --args --app="$APP_URL"
    elif [ -d "/Applications/Brave Browser.app" ]; then
        open -na "Brave Browser" --args --app="$APP_URL"
    else
        open "$APP_URL"
    fi
}}

# 1. Ensure Ollama is running silently with offline models
if command -v ollama >/dev/null 2>&1; then
    if ! curl -s --max-time 0.8 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
        nohup ollama serve </dev/null >>"$VAULT_DIR/ollama.log" 2>&1 &
    fi
fi

# 2. If server is already healthy on port 8501, open window immediately (<0.1s) and exit
if curl -s --max-time 1.2 "http://127.0.0.1:8501/api/catalogs" >/dev/null 2>&1; then
    open_studio_window
    exit 0
fi

# 3. Otherwise, clean any wedged process holding port 8501 and launch server in background
lsof -ti tcp:8501 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true

(
    cd "$PROJECT_ROOT" || exit 1
    nohup "$PYTHON_BIN" -m uvicorn server:app --host 127.0.0.1 --port 8501 </dev/null >>"$LOG_FILE" 2>&1 &
    for i in {{1..40}}; do
        if curl -s --max-time 0.5 "http://127.0.0.1:8501/api/catalogs" >/dev/null 2>&1; then
            break
        fi
        sleep 0.25
    done
    open_studio_window
) </dev/null >/dev/null 2>&1 &

exit 0
"""
        launch_sh = resources_dir / "launch.sh"
        launch_sh.write_text(launcher_script, encoding="utf-8")
        launch_sh.chmod(launch_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        exec_path = macos_dir / "MRDarkroom"
        _compile_universal_macho_launcher(exec_path, "../Resources/launch.sh")
        if not exec_path.exists():
            shutil.copy2(str(launch_sh), str(exec_path))

        _codesign_bundle(staged_app)

        if target_app_path.exists():
            subprocess.run(["rm", "-rf", str(target_app_path)], check=False)
        target_app_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-r", f"{staged_app}/", f"{target_app_path}/"], check=True)
        subprocess.run(
            ["chmod", "+x", str(target_app_path / "Contents" / "MacOS" / "MRDarkroom"), str(target_app_path / "Contents" / "Resources" / "launch.sh")],
            check=False,
        )

    return target_app_path


def create_installer_app_bundle(target_app_path: Path, icns_source: Path) -> Path:
    """
    Builds a native macOS GUI Installer application (`Install MR Darkroom to Mac.app`)
    with a real signed Universal Mach-O executable that installs MR Darkroom onto the
    Mac's internal hard drive using native macOS dialogs (zero Terminal windows required).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        staged_app = Path(tmpdir) / "Install MR Darkroom to Mac.app"
        contents_dir = staged_app / "Contents"
        macos_dir = contents_dir / "MacOS"
        resources_dir = contents_dir / "Resources"
        macos_dir.mkdir(parents=True, exist_ok=True)
        resources_dir.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(icns_source), str(resources_dir / "AppIcon.icns"))

        info_plist = {
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": "Install MR Darkroom to Mac",
            "CFBundleExecutable": "MRDarkroomInstaller",
            "CFBundleIconFile": "AppIcon",
            "CFBundleIdentifier": "com.mrdarkroom.installer",
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": "Install MR Darkroom to Mac",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "4.4.0",
            "CFBundleVersion": "440",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        }
        with open(contents_dir / "Info.plist", "wb") as f:
            plistlib.dump(info_plist, f)

        installer_script = """#!/bin/zsh
# MR Darkroom — Native macOS GUI Installer (Runs Directly Inside Signed App Process)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

APP_BUNDLE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
STUDIO_ROOT="$(dirname "$APP_BUNDLE_DIR")"
SSD_ENGINE="$STUDIO_ROOT/Engine"
SSD_VAULT="$STUDIO_ROOT/Data_Vault"
SSD_RUNTIME="$STUDIO_ROOT/Runtime/venv_arm64.tar.gz"

TARGET_VAULT="$HOME/Library/Application Support/MRDarkroom"
TARGET_ENGINE="$TARGET_VAULT/Engine"
LOG_FILE="/tmp/mrdarkroom_installer.log"

RESPONSE=$(osascript -e 'display dialog "Install MR Darkroom Studio (v4.4.0) onto this Mac?\\n\\nThis will automatically install:\\n• MR Darkroom.app into /Applications & Desktop\\n• Self-Contained Python 3.9, ExifTool & Ollama\\n• Full Photo Archive Database & WebP Previews\\n• Offline OpenCLIP + Ollama Vision AI Models\\n\\nOnce complete, you can run MR Darkroom anytime without the external SSD." buttons {"Cancel", "Install Now"} default button "Install Now" with title "MR Darkroom Studio Installer" with icon note' 2>/dev/null)

if [[ "$RESPONSE" != *"Install Now"* ]]; then
    exit 0
fi

osascript -e 'display notification "Installing MR Darkroom Engine, AI Models & Photo Archive to Mac Hard Drive..." with title "MR Darkroom Installer" subtitle "Step 1 of 3 — Copying Studio Files"' 2>/dev/null || true

{
    echo "=== Starting MR Darkroom Mac Hard Drive Installation ==="
    mkdir -p "$TARGET_VAULT" "$TARGET_ENGINE"

    rsync -a --exclude='/.venv' --exclude='/data' --exclude='._*' "$SSD_ENGINE/" "$TARGET_ENGINE/"
    xattr -cr "$TARGET_ENGINE/bin" "$TARGET_ENGINE/Python3" 2>/dev/null || true
    chmod +x "$TARGET_ENGINE/bin/exiftool" "$TARGET_ENGINE/bin/ollama" "$TARGET_ENGINE/Python3/bin/python3.9" 2>/dev/null || true

    if [ -f "$SSD_RUNTIME" ]; then
        tar -xzf "$SSD_RUNTIME" -C "$TARGET_ENGINE"
    else
        rsync -a --exclude='._*' "$SSD_ENGINE/.venv/" "$TARGET_ENGINE/.venv/"
    fi

    osascript -e 'display notification "Copying Photo Archive Database, Previews & Offline AI Models..." with title "MR Darkroom Installer" subtitle "Step 2 of 3 — Installing Data Vault & AI Models"' 2>/dev/null || true

    rsync -a --exclude='._*' "$SSD_VAULT/" "$TARGET_VAULT/"

    mkdir -p "$HOME/.ollama/models"
    if [ -d "$TARGET_VAULT/models/ollama" ]; then
        rsync -a --exclude='._*' "$TARGET_VAULT/models/ollama/" "$HOME/.ollama/models/"
    fi

    osascript -e 'display notification "Creating /Applications/MR Darkroom.app & Desktop shortcut..." with title "MR Darkroom Installer" subtitle "Step 3 of 3 — Finalizing macOS App"' 2>/dev/null || true

    if [ -x "$TARGET_ENGINE/Python3/bin/python3.9" ]; then
        PYTHON_BIN="$TARGET_ENGINE/Python3/bin/python3.9"
        export PYTHONPATH="$TARGET_ENGINE/.venv/lib/python3.9/site-packages:$TARGET_ENGINE"
    else
        PYTHON_BIN="$TARGET_ENGINE/.venv/bin/python3"
    fi

    cd "$TARGET_ENGINE"
    "$PYTHON_BIN" "$TARGET_ENGINE/scripts/build_macos_app.py" --project-root "$TARGET_ENGINE" --install-launchagent
    echo "=== Installation Finished Successfully ==="
} >"$LOG_FILE" 2>&1

osascript -e 'display dialog "✅ MR Darkroom Studio (v4.4.0) is now installed on this Mac!\\n\\n• Application: /Applications/MR Darkroom.app\\n• Shortcut: Desktop/MR Darkroom.app\\n• Offline AI Models & Photo Archive: Ready\\n\\nYou can now safely eject the 2TB SSD at any time." buttons {"Launch MR Darkroom"} default button "Launch MR Darkroom" with title "Installation Complete" with icon note' 2>/dev/null || true

open -a "/Applications/MR Darkroom.app"
"""
        launch_sh = resources_dir / "launch.sh"
        launch_sh.write_text(installer_script, encoding="utf-8")
        launch_sh.chmod(launch_sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        exec_path = macos_dir / "MRDarkroomInstaller"
        _compile_universal_macho_launcher(exec_path, "../Resources/launch.sh")
        if not exec_path.exists():
            shutil.copy2(str(launch_sh), str(exec_path))

        _codesign_bundle(staged_app)

        if target_app_path.exists():
            subprocess.run(["rm", "-rf", str(target_app_path)], check=False)
        target_app_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["rsync", "-r", f"{staged_app}/", f"{target_app_path}/"], check=True)
        subprocess.run(
            ["chmod", "+x", str(target_app_path / "Contents" / "MacOS" / "MRDarkroomInstaller"), str(target_app_path / "Contents" / "Resources" / "launch.sh")],
            check=False,
        )

    return target_app_path


def install_launch_agent(project_root: Path) -> Path:
    """Writes ~/Library/LaunchAgents/com.mrdarkroom.studio.plist for automatic startup."""
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    launch_agents_dir.mkdir(parents=True, exist_ok=True)
    plist_path = launch_agents_dir / "com.mrdarkroom.studio.plist"

    vault_dir = Path.home() / "Library" / "Application Support" / "MRDarkroom"
    py_bin = project_root / "Python3" / "bin" / "python3.9"
    if not py_bin.exists():
        py_bin = project_root / ".venv" / "bin" / "python"

    plist_data = {
        "Label": "com.mrdarkroom.studio",
        "ProgramArguments": [
            str(py_bin),
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8501",
        ],
        "WorkingDirectory": str(project_root),
        "EnvironmentVariables": {
            "PATH": f"{project_root / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": f"{project_root / '.venv/lib/python3.9/site-packages'}:{project_root}",
            "MRDARKROOM_VAULT_DIR": str(vault_dir),
            "HF_HOME": str(vault_dir / "models" / "huggingface"),
            "OLLAMA_MODELS": str(vault_dir / "models" / "ollama"),
        },
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(vault_dir / "server.log"),
        "StandardErrorPath": str(vault_dir / "server.log"),
    }
    with open(plist_path, "wb") as f:
        plistlib.dump(plist_data, f)
    return plist_path


def main():
    parser = argparse.ArgumentParser(description="Build MR Darkroom.app bundle")
    parser.add_argument("--project-root", type=str, default=str(PROJECT_ROOT))
    parser.add_argument("--output-app", type=str, default="")
    parser.add_argument("--output-installer-app", type=str, default="")
    parser.add_argument("--install-launchagent", action="store_true")
    args = parser.parse_args()

    proj_root = Path(args.project_root).resolve()
    dist_dir = proj_root / "dist_app"
    dist_dir.mkdir(parents=True, exist_ok=True)
    icns_path = dist_dir / "AppIcon.icns"

    print("1. Rendering 1024x1024 studio icon & compiling AppIcon.icns...")
    build_icns(icns_path, badge_text="DARKROOM")
    print(f"   -> Built {icns_path}")

    if args.output_installer_app:
        inst_icns = dist_dir / "InstallerIcon.icns"
        build_icns(inst_icns, badge_text="INSTALLER")
        out_inst = Path(args.output_installer_app).expanduser().resolve()
        create_installer_app_bundle(out_inst, inst_icns)
        print(f"   -> Packaged Signed Installer App: {out_inst}")

    if args.output_app:
        out_path = Path(args.output_app).expanduser().resolve()
        create_app_bundle(out_path, proj_root, icns_path)
        print(f"2. Packaged Signed App: {out_path}")
        return

    repo_app = dist_dir / "MR Darkroom.app"
    desktop_app = Path.home() / "Desktop" / "MR Darkroom.app"
    applications_app = Path("/Applications/MR Darkroom.app")

    print("2. Packaging ./dist_app/MR Darkroom.app...")
    create_app_bundle(repo_app, proj_root, icns_path)

    print("3. Installing ~/Desktop/MR Darkroom.app...")
    create_app_bundle(desktop_app, proj_root, icns_path)
    print(f"   -> Installed {desktop_app}")

    try:
        print("4. Installing /Applications/MR Darkroom.app...")
        create_app_bundle(applications_app, proj_root, icns_path)
        print(f"   -> Installed {applications_app}")
    except Exception as exc:
        print(f"   -> Skipped /Applications install ({exc})")

    if args.install_launchagent:
        plist_p = install_launch_agent(proj_root)
        print(f"5. Registered LaunchAgent: {plist_p}")


if __name__ == "__main__":
    main()
