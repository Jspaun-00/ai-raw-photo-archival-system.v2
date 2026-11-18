#!/bin/bash
# ==============================================================================
# MR DARKROOM STUDIO (v4.5.0) — PERMANENT MAC INSTALLER (Install_MR_Darkroom_To_Mac.command)
# "Toss-the-SSD" Safeguard Installer:
# Copies the complete Studio Engine, Standalone Python 3.9, .venv, ExifTool,
# Ollama, Offline AI Models, and Data Vault to ~/Library/Application Support/MRDarkroom,
# builds /Applications/MR Darkroom.app & ~/Desktop/MR Darkroom.app, and registers
# the LaunchAgent daemon so MR Darkroom runs permanently on this Mac without the SSD.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -d "$SCRIPT_DIR/Engine" ] && [ -f "$SCRIPT_DIR/Engine/server.py" ]; then
    STUDIO_ROOT="$SCRIPT_DIR"
    SRC_ENGINE="$SCRIPT_DIR/Engine"
else
    STUDIO_ROOT="$SCRIPT_DIR"
    SRC_ENGINE="$SCRIPT_DIR"
fi

if [ -d "$STUDIO_ROOT/Data_Vault" ] && [ -f "$STUDIO_ROOT/Data_Vault/photo_archive.db" ]; then
    SRC_VAULT="$STUDIO_ROOT/Data_Vault"
elif [ -d "$STUDIO_ROOT/../Data_Vault" ] && [ -f "$STUDIO_ROOT/../Data_Vault/photo_archive.db" ]; then
    SRC_VAULT="$(cd "$STUDIO_ROOT/../Data_Vault" && pwd)"
else
    SRC_VAULT="$HOME/Library/Application Support/MRDarkroom"
fi

SSD_RUNTIME="$STUDIO_ROOT/Runtime/venv_arm64.tar.gz"
TARGET_VAULT="$HOME/Library/Application Support/MRDarkroom"
TARGET_ENGINE="$TARGET_VAULT/Engine"

clear
echo "=================================================================="
echo "  📥 MR DARKROOM STUDIO (v4.5.0) — PERMANENT MAC INSTALLER"
echo "=================================================================="
echo "  Source Engine     : $SRC_ENGINE"
echo "  Source Data Vault : $SRC_VAULT"
echo "  Install Location  : $TARGET_VAULT"
echo "  Mac Applications  : /Applications/MR Darkroom.app"
echo "  Desktop Shortcut  : ~/Desktop/MR Darkroom.app"
echo "=================================================================="
echo ""

mkdir -p "$TARGET_VAULT" "$TARGET_ENGINE"

echo "[1/5] Copying MR Darkroom Studio Engine, Production UI & Binaries to Mac Hard Drive..."
rsync -a \
  --exclude='/.venv' \
  --exclude='/data' \
  --exclude='._*' \
  --exclude='/ui/node_modules' \
  "$SRC_ENGINE/" "$TARGET_ENGINE/"

xattr -cr "$TARGET_ENGINE/bin" "$TARGET_ENGINE/Python3" 2>/dev/null || true
chmod +x "$TARGET_ENGINE/bin/"* "$TARGET_ENGINE/scripts/"* "$TARGET_ENGINE/"*.command "$TARGET_ENGINE/"*.sh 2>/dev/null || true
if [ -d "$TARGET_ENGINE/Python3/bin" ]; then
    chmod +x "$TARGET_ENGINE/Python3/bin/"* 2>/dev/null || true
fi
echo "      ✓ Studio Engine & binaries installed."

echo "[2/5] Installing Isolated Python Runtime (.venv)..."
if [ -f "$SSD_RUNTIME" ]; then
    tar -xzf "$SSD_RUNTIME" -C "$TARGET_ENGINE"
elif [ -d "$SRC_ENGINE/.venv" ]; then
    rsync -a --exclude='._*' "$SRC_ENGINE/.venv/" "$TARGET_ENGINE/.venv/"
fi
ln -sf "$TARGET_ENGINE/bin/exiftool" "$TARGET_ENGINE/.venv/bin/exiftool" 2>/dev/null || true
ln -sf "$TARGET_ENGINE/bin/lib" "$TARGET_ENGINE/.venv/bin/lib" 2>/dev/null || true
ln -sf "$TARGET_ENGINE/bin/ollama" "$TARGET_ENGINE/.venv/bin/ollama" 2>/dev/null || true
echo "      ✓ Isolated Python packages installed."

echo "[3/5] Syncing Photo Archive Database, Previews & Offline AI Models..."
if [ "$SRC_VAULT" != "$TARGET_VAULT" ]; then
    rsync -a --exclude='._*' --exclude='Engine' "$SRC_VAULT/" "$TARGET_VAULT/"
    echo "      ✓ Data Vault & Offline AI Models copied to Mac Hard Drive."
else
    echo "      ✓ Local Data Vault already active at $TARGET_VAULT."
fi

echo "[4/5] Configuring Local Ollama AI Vision Engine..."
mkdir -p "$HOME/.ollama/models"
if [ -d "$TARGET_VAULT/models/ollama" ]; then
    rsync -a --exclude='._*' "$TARGET_VAULT/models/ollama/" "$HOME/.ollama/models/"
fi
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    if [ -x "$TARGET_ENGINE/bin/ollama" ]; then
        OLLAMA_MODELS="$TARGET_VAULT/models/ollama" "$TARGET_ENGINE/bin/ollama" serve >/tmp/mrdarkroom_ollama.log 2>&1 &
        sleep 2
    fi
fi
echo "      ✓ Ollama AI Vision Engine ready."

echo "[5/5] Building Native macOS Application (/Applications/MR Darkroom.app) & LaunchAgent..."
if [ -x "$TARGET_ENGINE/Python3/bin/python3.9" ]; then
    PYTHON_BIN="$TARGET_ENGINE/Python3/bin/python3.9"
    export PYTHONPATH="$TARGET_ENGINE/.venv/lib/python3.9/site-packages:$TARGET_ENGINE"
elif [ -x "$TARGET_ENGINE/.venv/bin/python" ]; then
    PYTHON_BIN="$TARGET_ENGINE/.venv/bin/python"
    export PYTHONPATH="$TARGET_ENGINE/.venv/lib/python3.9/site-packages:$TARGET_ENGINE"
else
    PYTHON_BIN="/usr/bin/python3"
fi

cd "$TARGET_ENGINE"
"$PYTHON_BIN" "$TARGET_ENGINE/scripts/build_macos_app.py" --project-root "$TARGET_ENGINE" --install-launchagent

PLIST_PATH="$HOME/Library/LaunchAgents/com.mrdarkroom.studio.plist"
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH" 2>/dev/null || true

echo ""
echo "=================================================================="
echo "  ✅ INSTALLATION COMPLETE!"
echo "=================================================================="
echo "  • App Installed : /Applications/MR Darkroom.app"
echo "  • Desktop App   : ~/Desktop/MR Darkroom.app"
echo "  • Local Engine  : ~/Library/Application Support/MRDarkroom/Engine"
echo "  • Local Vault   : ~/Library/Application Support/MRDarkroom"
echo "  • LaunchAgent   : ~/Library/LaunchAgents/com.mrdarkroom.studio.plist"
echo "=================================================================="
echo ""
