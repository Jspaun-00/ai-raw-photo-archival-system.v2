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

echo "[switch_catalog] Requesting Adobe Lightroom Classic to quit..."
osascript -e 'tell application "Adobe Lightroom Classic" to quit' 2>/dev/null || true

# Wait for Lightroom Classic binary to exit completely (up to 35 seconds)
for i in {1..70}; do
    if ! pgrep -f "Adobe Lightroom Classic.app/Contents/MacOS/Adobe Lightroom Classic" > /dev/null 2>&1 && \
       ! pgrep -x "Adobe Lightroom Classic" > /dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# Wait for SQLite .lrcat.lock and LaunchServices termination state to clear
sleep 2.0

echo "[switch_catalog] Launching destination catalog: $TARGET_CAT"
for attempt in {1..5}; do
    open -a "Adobe Lightroom Classic" "$TARGET_CAT" 2>/dev/null || open "$TARGET_CAT" 2>/dev/null || true
    sleep 2.0
    if pgrep -f "Adobe Lightroom Classic.app/Contents/MacOS/Adobe Lightroom Classic" > /dev/null 2>&1 || \
       pgrep -x "Adobe Lightroom Classic" > /dev/null 2>&1; then
        osascript -e 'tell application "Adobe Lightroom Classic" to activate' 2>/dev/null || true
        echo "[switch_catalog] Adobe Lightroom Classic launched successfully on attempt $attempt."
        exit 0
    fi
done

open "$TARGET_CAT" 2>/dev/null || true
exit 0
