#!/bin/zsh
# ==============================================================================
# MR Darkroom — 1-Click macOS Studio Installer (install_mr_darkroom.command)
# Double-click this file in Finder to:
#   1. Initialize ~/Library/Application Support/MRDarkroom (Data Vault)
#   2. Build & install "MR Darkroom.app" onto your Desktop and /Applications
#   3. Register a macOS LaunchAgent so the MR Darkroom engine starts on login
# ==============================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  Installing MR Darkroom (v3.2)"
echo "  Project Root: $SCRIPT_DIR"
echo "========================================================"

# 1. Ensure Data Vault is initialized and migrated
VAULT_DIR="$HOME/Library/Application Support/MRDarkroom"
mkdir -p "$VAULT_DIR"
if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/config_paths.py"
    "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/scripts/build_macos_app.py"
fi

# 2. Copy MR Darkroom.app to /Applications if possible
if [ -d "$HOME/Desktop/MR Darkroom.app" ]; then
    rm -rf "/Applications/MR Darkroom.app" 2>/dev/null || true
    cp -R "$HOME/Desktop/MR Darkroom.app" "/Applications/MR Darkroom.app" 2>/dev/null || true
fi

# 3. Install LaunchAgent for automatic background startup on login
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
PLIST_PATH="$LAUNCH_AGENTS_DIR/com.mrdarkroom.studio.plist"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mrdarkroom.studio</string>
    <key>WorkingDirectory</key>
    <string>${SCRIPT_DIR}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${SCRIPT_DIR}/.venv/bin/python</string>
        <string>-m</string>
        <string>uvicorn</string>
        <string>server:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8501</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${VAULT_DIR}/server.log</string>
    <key>StandardErrorPath</key>
    <string>${VAULT_DIR}/server.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH" 2>/dev/null || true

echo ""
echo "✅ MR Darkroom installed successfully!"
echo "   • Desktop App:  ~/Desktop/MR Darkroom.app"
echo "   • Applications: /Applications/MR Darkroom.app"
echo "   • Data Vault:   ~/Library/Application Support/MRDarkroom"
echo ""
open "$HOME/Desktop/MR Darkroom.app"

