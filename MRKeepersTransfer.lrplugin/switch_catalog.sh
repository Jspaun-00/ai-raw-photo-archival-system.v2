#!/bin/bash
# ==============================================================================
# MR KEEPERS TRANSFER — CATALOG SWITCHER
# Closes Lightroom Classic gracefully, waits for database lock release,
# and relaunches Lightroom Classic with the designated destination catalog.
# ==============================================================================

TARGET_CAT="$1"

if [ -z "$TARGET_CAT" ]; then
    echo "Error: No target catalog path provided."
    exit 1
fi

# 1. Ask Lightroom Classic to quit gracefully via AppleScript
osascript -e 'tell application "Adobe Lightroom Classic" to quit' 2>/dev/null || true

# 2. Wait for process to exit (up to 30 seconds)
for i in {1..60}; do
    if ! pgrep -x "Adobe Lightroom Classic" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# 3. Buffer for SQLite lockfile release
sleep 1.2

# 4. Open Lightroom Classic with the destination catalog
open -a "Adobe Lightroom Classic" "$TARGET_CAT"
