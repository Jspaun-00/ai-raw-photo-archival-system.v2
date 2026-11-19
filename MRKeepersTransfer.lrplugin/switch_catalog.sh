#!/bin/bash
# ==============================================================================
# MR KEEPERS TRANSFER — CATALOG SWITCHER
# Uses Lightroom Classic's native catalog-relaunch handler (LibraryRelaunchUtils)
# immediately (~0.5s after DNG export) instead of blocking for 35 seconds, and
# ensures Lightroom reopens with the destination catalog if it exits cleanly.
# ==============================================================================

TARGET_CAT="$1"

if [ -z "$TARGET_CAT" ]; then
    echo "Error: No target catalog path provided."
    exit 1
fi

# 1. Pre-configure Lightroom Classic's "Don't show again" preference for catalog relaunch
defaults write com.adobe.LightroomClassicCC7 AgLibrary_relaunchLightroomForNewLibrary -string "relaunch" 2>/dev/null || true
EXISTING_PROMPTS="$(defaults read com.adobe.LightroomClassicCC7 doNotShowPrompts 2>/dev/null || echo "")"
if [[ "$EXISTING_PROMPTS" != *"AgLibrary_relaunchLightroomForNewLibrary"* ]]; then
    defaults write com.adobe.LightroomClassicCC7 doNotShowPrompts -string "${EXISTING_PROMPTS}AgLibrary_relaunchLightroomForNewLibrary," 2>/dev/null || true
fi

# 2. Immediately trigger Lightroom Classic's native catalog switch (< 1 second after export)
sleep 0.4
echo "[switch_catalog] Requesting Lightroom Classic to switch to catalog: $TARGET_CAT"
open -a "Adobe Lightroom Classic" "$TARGET_CAT" 2>/dev/null || open "$TARGET_CAT" 2>/dev/null || true

# Bring Lightroom Classic to front so any first-time confirmation or relaunch bezel is visible immediately
osascript -e 'tell application "Adobe Lightroom Classic" to activate' 2>/dev/null || true

# 3. Watch for up to 20 seconds: if Lightroom exits completely during the switch and stays closed >2.5s,
#    re-open "$TARGET_CAT" to guarantee the destination catalog launches.
SAW_EXIT=0
CLOSED_TICKS=0
for i in {1..40}; do
    if ! pgrep -f "Adobe Lightroom Classic.app/Contents/MacOS/Adobe Lightroom Classic" > /dev/null 2>&1 && \
       ! pgrep -x "Adobe Lightroom Classic" > /dev/null 2>&1; then
        SAW_EXIT=1
        CLOSED_TICKS=$((CLOSED_TICKS + 1))
        if [ "$CLOSED_TICKS" -ge 5 ]; then
            echo "[switch_catalog] Lightroom stayed closed after exit; launching destination catalog: $TARGET_CAT"
            open -a "Adobe Lightroom Classic" "$TARGET_CAT" 2>/dev/null || open "$TARGET_CAT" 2>/dev/null || true
            sleep 2.0
            osascript -e 'tell application "Adobe Lightroom Classic" to activate' 2>/dev/null || true
            exit 0
        fi
    else
        if [ "$SAW_EXIT" -eq 1 ]; then
            echo "[switch_catalog] Lightroom Classic automatically relaunched into destination catalog."
            osascript -e 'tell application "Adobe Lightroom Classic" to activate' 2>/dev/null || true
            exit 0
        fi
    fi
    sleep 0.5
done

exit 0
