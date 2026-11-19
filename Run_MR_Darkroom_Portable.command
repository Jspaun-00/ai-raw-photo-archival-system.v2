#!/bin/bash
# ==============================================================================
# MR DARKROOM STUDIO (v4.5.0) — PORTABLE LAUNCHER (Run_MR_Darkroom_Portable.command)
# Runs the FastAPI Studio Engine directly off the current folder / external SSD
# with zero permanent host modifications.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect whether we are in the SSD wrapper root (containing Engine/) or directly inside Engine/
if [ -d "$SCRIPT_DIR/Engine" ] && [ -f "$SCRIPT_DIR/Engine/server.py" ]; then
    STUDIO_ROOT="$SCRIPT_DIR"
    ENGINE_DIR="$SCRIPT_DIR/Engine"
else
    STUDIO_ROOT="$SCRIPT_DIR"
    ENGINE_DIR="$SCRIPT_DIR"
fi

# Auto-detect Data Vault (Portable SSD Data_Vault vs Host Application Support)
if [ -d "$STUDIO_ROOT/Data_Vault" ] && [ -f "$STUDIO_ROOT/Data_Vault/photo_archive.db" ]; then
    VAULT_DIR="$STUDIO_ROOT/Data_Vault"
elif [ -d "$STUDIO_ROOT/../Data_Vault" ] && [ -f "$STUDIO_ROOT/../Data_Vault/photo_archive.db" ]; then
    VAULT_DIR="$(cd "$STUDIO_ROOT/../Data_Vault" && pwd)"
else
    VAULT_DIR="$HOME/Library/Application Support/MRDarkroom"
fi

export MRDARKROOM_VAULT_DIR="$VAULT_DIR"
export HF_HOME="$VAULT_DIR/models/huggingface"
export OLLAMA_MODELS="$VAULT_DIR/models/ollama"
export PATH="$ENGINE_DIR/bin:$ENGINE_DIR/bin/node-v20.18.0-darwin-arm64/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONWARNINGS="ignore"

clear
echo "=================================================================="
echo "  ⚡ MR DARKROOM STUDIO (v4.5.0) — PORTABLE MODE"
echo "=================================================================="
echo "  Engine Dir : $ENGINE_DIR"
echo "  Data Vault : $VAULT_DIR"
echo "  AI Models  : OpenCLIP ViT-L-14 + Ollama qwen2.5vl:7b (Offline)"
echo "=================================================================="
echo ""

# 1. Clear macOS quarantine attributes & normalize permissions on bundled binaries
xattr -cr "$ENGINE_DIR/bin" "$ENGINE_DIR/Python3" 2>/dev/null || true
chmod +x "$ENGINE_DIR/bin/"* "$ENGINE_DIR/scripts/"* "$ENGINE_DIR/"*.command "$ENGINE_DIR/"*.sh 2>/dev/null || true
if [ -d "$ENGINE_DIR/Python3/bin" ]; then
    chmod +x "$ENGINE_DIR/Python3/bin/"* 2>/dev/null || true
fi

# 2. Select Python Runtime (Self-Contained Python3, .venv, or System Python)
if [ -x "$ENGINE_DIR/Python3/bin/python3.9" ]; then
    PYTHON_BIN="$ENGINE_DIR/Python3/bin/python3.9"
    export PYTHONPATH="$ENGINE_DIR/.venv/lib/python3.9/site-packages:$ENGINE_DIR"
elif [ -x "$ENGINE_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ENGINE_DIR/.venv/bin/python"
    export PYTHONPATH="$ENGINE_DIR/.venv/lib/python3.9/site-packages:$ENGINE_DIR"
elif [ -x "/Library/Developer/CommandLineTools/usr/bin/python3" ]; then
    PYTHON_BIN="/Library/Developer/CommandLineTools/usr/bin/python3"
    export PYTHONPATH="$ENGINE_DIR/.venv/lib/python3.9/site-packages:$ENGINE_DIR"
else
    PYTHON_BIN="$(which python3)"
    export PYTHONPATH="$ENGINE_DIR/.venv/lib/python3.9/site-packages:$ENGINE_DIR"
fi

echo "✓ Python Runtime : $PYTHON_BIN"

# 3. Ensure Offline Ollama AI Vision Server is running
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    if [ -x "$ENGINE_DIR/bin/ollama" ]; then
        echo "🧠 Starting Offline Ollama AI Vision Server..."
        OLLAMA_MODELS="$VAULT_DIR/models/ollama" "$ENGINE_DIR/bin/ollama" serve >/tmp/mrdarkroom_ollama.log 2>&1 &
        sleep 2
    elif command -v ollama >/dev/null 2>&1; then
        echo "🧠 Starting Local Ollama AI Vision Server..."
        OLLAMA_MODELS="$VAULT_DIR/models/ollama" ollama serve >/tmp/mrdarkroom_ollama.log 2>&1 &
        sleep 2
    fi
else
    echo "✓ Ollama AI Vision Server is active on port 11434"
fi

# 4. Helper to focus existing Studio UI window or open a single standalone window
open_studio_window() {
    local URL="http://127.0.0.1:8501"
    if [ -d "/Applications/Google Chrome.app" ] && pgrep -x "Google Chrome" >/dev/null 2>&1; then
        local CHROME_RES
        CHROME_RES=$(osascript -e 'tell application "Google Chrome"
            repeat with w in windows
                set tabIdx to 0
                repeat with t in tabs of w
                    set tabIdx to tabIdx + 1
                    try
                        if (URL of t contains "127.0.0.1:8501") or (URL of t contains "localhost:8501") then
                            set active tab index of w to tabIdx
                            set index of w to 1
                            activate
                            return "FOCUSED"
                        end if
                    end try
                end repeat
            end repeat
        end tell
        return "NONE"' 2>/dev/null || echo "NONE")
        if [ "$CHROME_RES" = "FOCUSED" ]; then
            return 0
        fi
    fi
    if pgrep -x "Safari" >/dev/null 2>&1; then
        local SAFARI_RES
        SAFARI_RES=$(osascript -e 'tell application "Safari"
            repeat with w in windows
                repeat with t in tabs of w
                    try
                        if (URL of t contains "127.0.0.1:8501") or (URL of t contains "localhost:8501") then
                            set current tab of w to t
                            set index of w to 1
                            activate
                            return "FOCUSED"
                        end if
                    end try
                end repeat
            end repeat
        end tell
        return "NONE"' 2>/dev/null || echo "NONE")
        if [ "$SAFARI_RES" = "FOCUSED" ]; then
            return 0
        fi
    fi
    if [ -d "/Applications/Google Chrome.app" ]; then
        open -a "Google Chrome" --args --app="$URL"
    elif [ -d "/Applications/Brave Browser.app" ]; then
        open -a "Brave Browser" --args --app="$URL"
    else
        open "$URL"
    fi
}

# 5. Check if server is already listening on port 8501
if curl -s http://127.0.0.1:8501/api/catalogs >/dev/null 2>&1; then
    echo "✓ MR Darkroom Server is already running on http://127.0.0.1:8501"
    echo "🚀 Opening MR Darkroom Studio Window..."
    open_studio_window
    exit 0
fi

# 6. Start the FastAPI Studio Engine
echo "🚀 Starting MR Darkroom Studio Engine on http://127.0.0.1:8501..."
cd "$ENGINE_DIR"
"$PYTHON_BIN" -m uvicorn server:app --host 127.0.0.1 --port 8501 >/tmp/mrdarkroom_ssd_server.log 2>&1 &
SERVER_PID=$!

for i in {1..50}; do
    if curl -s http://127.0.0.1:8501/api/catalogs >/dev/null 2>&1; then
        echo ""
        echo "✅ MR Darkroom Studio is LIVE at http://127.0.0.1:8501"
        open_studio_window
        echo ""
        echo "Keep this window minimized while using MR Darkroom in Portable Mode."
        echo "Press Ctrl+C at any time to stop the server."
        wait $SERVER_PID
        exit 0
    fi
    sleep 0.5
done

echo "⚠️ Server took longer than expected to start. Check /tmp/mrdarkroom_ssd_server.log:"
cat /tmp/mrdarkroom_ssd_server.log
