#!/bin/bash
# ==============================================================================
# Double-Click Launcher for Mitch Rouse Studio AI Archival System v3.0
# ==============================================================================

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Ensure log directory exists
mkdir -p "$DIR/logs"

# Ensure Ollama vision engine daemon is active if installed
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    if [ -f "/Applications/Ollama.app/Contents/Resources/ollama" ]; then
        echo "Starting local Ollama vision engine..."
        /Applications/Ollama.app/Contents/Resources/ollama serve > /dev/null 2>&1 &
        sleep 1
    elif which ollama > /dev/null 2>&1; then
        echo "Starting local Ollama vision engine..."
        ollama serve > /dev/null 2>&1 &
        sleep 1
    fi
fi

echo "=========================================================="
echo "  Launching Mitch Rouse Studio AI Archival System v3.0..."
echo "  URL: http://localhost:8501"
echo "=========================================================="

source "$DIR/.venv/bin/activate"
export PATH="$DIR/bin:$DIR/bin/node-v20.18.0-darwin-arm64/bin:$DIR/.venv/bin:$PATH"
export PYTHONWARNINGS="ignore"

# Open browser to Studio UI
(sleep 1.5 && open "http://localhost:8501") &

# Run FastAPI Studio Server (serving API + React Studio UI)
python -m uvicorn server:app --host 127.0.0.1 --port 8501
