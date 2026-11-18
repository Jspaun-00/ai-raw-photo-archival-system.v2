#!/usr/bin/env python3
"""
generate_guide_visuals.py
Generates high-resolution, neutral-grey studio UI screenshots and annotated diagrams
for the MRDarkroom Studio Guide Drawer. Uses clean Helvetica-supported glyphs only.
"""

import glob
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent
PUBLIC_GUIDE_DIR = PROJECT_ROOT / "ui" / "public" / "guide"
DIST_GUIDE_DIR = PROJECT_ROOT / "ui" / "dist" / "guide"
PUBLIC_GUIDE_DIR.mkdir(parents=True, exist_ok=True)
DIST_GUIDE_DIR.mkdir(parents=True, exist_ok=True)

# Find sample real aerial photos
SAMPLE_PHOTOS = sorted(glob.glob(str(PROJECT_ROOT / "data" / "previews" / "thumbs_360" / "*.webp")))
if not SAMPLE_PHOTOS:
    SAMPLE_PHOTOS = sorted(glob.glob(str(PROJECT_ROOT / "data" / "previews" / "previews_1600" / "*.webp")))

FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
FONT_BOLD = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
FONT_REGULAR = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
FONT_SMALL = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 13)
FONT_TINY = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
FONT_MONO = ImageFont.truetype("/System/Library/Fonts/Monaco.ttf", 13)

# Neutral Dark Grey Studio Palette
BG_DARK = "#0F0F0F"
PANEL_BG = "#161616"
CARD_BG = "#1C1C1C"
HOVER_BG = "#242424"
BORDER_STD = "#2A2A2A"
BORDER_LIGHT = "#3A3A3A"
TEXT_WHITE = "#F5F5F5"
TEXT_MUTED = "#B5B5B5"
TEXT_DIM = "#808080"
GOLD_FILL = "#F59E0B"
GOLD_LIGHT = "#FBBF24"
GOLD_DARK = "#241904"
EMERALD_FILL = "#10B981"
EMERALD_LIGHT = "#34D399"
EMERALD_DARK = "#062E22"


def draw_rounded_rect(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_window_chrome(draw, width, title="MR Darkroom Studio"):
    draw.rectangle([0, 0, width, 32], fill="#141414")
    draw.line([0, 32, width, 32], fill=BORDER_STD, width=1)
    # Traffic lights
    draw.ellipse([12, 10, 24, 22], fill="#ef4444")
    draw.ellipse([30, 10, 42, 22], fill="#f59e0b")
    draw.ellipse([48, 10, 60, 22], fill="#10b981")
    # Title
    bbox = FONT_SMALL.getbbox(title)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, 8), title, fill=TEXT_MUTED, font=FONT_SMALL)


def draw_callout_box(draw, box, text_lines, border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT, font=FONT_BOLD):
    draw_rounded_rect(draw, box, radius=8, fill=bg_color, outline=border_color, width=2)
    x = box[0] + 14
    y = box[1] + 12
    for line in text_lines:
        draw.text((x, y), line, fill=text_color, font=font)
        y += 22


def draw_down_arrow(draw, start_pt, end_pt, color=GOLD_FILL, width=4):
    draw.line([start_pt, end_pt], fill=color, width=width)
    x, y = end_pt
    draw.polygon([(x - 9, y - 12), (x + 9, y - 12), (x, y + 2)], fill=color)


def draw_right_arrow(draw, start_pt, end_pt, color=GOLD_FILL, width=4):
    draw.line([start_pt, end_pt], fill=color, width=width)
    x, y = end_pt
    draw.polygon([(x - 12, y - 9), (x - 12, y + 9), (x + 2, y)], fill=color)


def draw_left_arrow(draw, start_pt, end_pt, color=GOLD_FILL, width=4):
    draw.line([start_pt, end_pt], fill=color, width=width)
    x, y = end_pt
    draw.polygon([(x + 12, y - 9), (x + 12, y + 9), (x - 2, y)], fill=color)


def draw_up_arrow(draw, start_pt, end_pt, color=GOLD_FILL, width=4):
    draw.line([start_pt, end_pt], fill=color, width=width)
    x, y = end_pt
    draw.polygon([(x - 9, y + 12), (x + 9, y + 12), (x, y - 2)], fill=color)


# =============================================================================
# IMAGE 1: CREATE A COLLECTION (COLLECTIONS VIEW)
# =============================================================================
def gen_step1():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Curated Collections View")

    # Top Ribbon Bar
    draw.rectangle([0, 32, W, 92], fill=PANEL_BG)
    draw.line([0, 92, W, 92], fill=BORDER_STD, width=1)
    # Logo
    draw_rounded_rect(draw, [16, 44, 52, 80], radius=6, fill=GOLD_FILL)
    draw.text((22, 53), "MR", fill="#000", font=FONT_BOLD)
    draw.text((62, 53), "MR Darkroom", fill=TEXT_WHITE, font=FONT_BOLD)

    # View Mode Switcher
    switcher_x = 220
    modes = [("All Photos", False), ("By Date", False), ("By Trip", False), ("* Curated Collections", True)]
    for label, is_active in modes:
        tw = FONT_SMALL.getbbox(label)[2] - FONT_SMALL.getbbox(label)[0] + 24
        if is_active:
            draw_rounded_rect(draw, [switcher_x, 44, switcher_x + tw, 78], radius=6, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
            draw.text((switcher_x + 12, 53), label, fill="#090909", font=FONT_BOLD)
        else:
            draw_rounded_rect(draw, [switcher_x, 44, switcher_x + tw, 78], radius=6, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
            draw.text((switcher_x + 12, 53), label, fill=TEXT_MUTED, font=FONT_SMALL)
        switcher_x += tw + 10

    # Left Sidebar (Collections list)
    sidebar_w = 300
    draw.rectangle([0, 93, sidebar_w, H], fill=PANEL_BG)
    draw.line([sidebar_w, 93, sidebar_w, H], fill=BORDER_STD, width=1)

    # Big Yellow "Create New Collection" Button
    btn_box = [18, 112, sidebar_w - 18, 166]
    draw_rounded_rect(draw, btn_box, radius=10, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    btn_text = "+ Create New Collection"
    tw = FONT_BOLD.getbbox(btn_text)[2] - FONT_BOLD.getbbox(btn_text)[0]
    draw.text((btn_box[0] + (btn_box[2] - btn_box[0] - tw) // 2, 130), btn_text, fill="#090909", font=FONT_BOLD)

    # Collection Items in Sidebar
    cols = [
        ("TV 1 - Ranch Gallery", "8 Plates • 12K Master", True),
        ("TV 2 - Living Room", "14 Plates • 12K Master", False),
        ("Palouse Farmland", "26 Plates • Portfolio", False),
        ("Teton Range Aerials", "19 Plates • Archival", False),
    ]
    cy = 186
    for title, sub, active in cols:
        cbox = [14, cy, sidebar_w - 14, cy + 62]
        if active:
            draw_rounded_rect(draw, cbox, radius=8, fill=HOVER_BG, outline=GOLD_FILL, width=2)
            draw.text((26, cy + 12), title, fill=GOLD_LIGHT, font=FONT_BOLD)
            draw.text((26, cy + 36), sub, fill=TEXT_MUTED, font=FONT_TINY)
        else:
            draw_rounded_rect(draw, cbox, radius=8, fill=CARD_BG, outline=BORDER_STD, width=1)
            draw.text((26, cy + 12), title, fill=TEXT_WHITE, font=FONT_SMALL)
            draw.text((26, cy + 36), sub, fill=TEXT_DIM, font=FONT_TINY)
        cy += 70

    # Right Gallery Area (Curated photo grid)
    gx = sidebar_w + 22
    gy = 112
    p_w, p_h = 192, 128
    idx = 0
    for r in range(3):
        for c in range(3):
            rx = gx + c * (p_w + 16)
            ry = gy + r * (p_h + 16)
            if idx < len(SAMPLE_PHOTOS):
                try:
                    p_im = Image.open(SAMPLE_PHOTOS[idx]).convert("RGB").resize((p_w, p_h))
                    im.paste(p_im, (rx, ry))
                except Exception:
                    draw.rectangle([rx, ry, rx + p_w, ry + p_h], fill=CARD_BG)
            else:
                draw.rectangle([rx, ry, rx + p_w, ry + p_h], fill=CARD_BG)
            draw.rectangle([rx, ry, rx + p_w, ry + p_h], outline=BORDER_LIGHT, width=1)
            idx += 1

    # Callout Arrow to Create Collection Button
    callout_box = [sidebar_w + 30, 108, sidebar_w + 430, 178]
    draw_callout_box(draw, callout_box, [
        "1. Click '+ Create New Collection'",
        "Large yellow button in the left sidebar"
    ], border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT)
    draw_left_arrow(draw, (callout_box[0], 139), (btn_box[2] + 6, 139), color=GOLD_FILL, width=4)

    return im


# =============================================================================
# IMAGE 2: NAME YOUR COLLECTION (MANDATORY REQUIREMENT)
# =============================================================================
def gen_step2():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Create Collection Modal")

    # Darkened background grid
    for r in range(4):
        for c in range(5):
            draw.rectangle([c * 195, 34 + r * 130, c * 195 + 185, 34 + r * 130 + 120], fill="#131313", outline=BORDER_STD)

    # Modal Overlay (Centered)
    mw, mh = 620, 420
    mx = (W - mw) // 2 + 40
    my = (H - mh) // 2 + 12

    draw_rounded_rect(draw, [mx - 4, my - 4, mx + mw + 4, my + mh + 4], radius=16, fill="#000000")
    draw_rounded_rect(draw, [mx, my, mx + mw, my + mh], radius=14, fill=PANEL_BG, outline=GOLD_FILL, width=2)

    # Modal Header
    draw.text((mx + 28, my + 22), "Create a New Collection", fill=TEXT_WHITE, font=FONT_TITLE)
    draw.text((mx + 28, my + 54), "Enter a title for this gallery showcase. You can reorder plates anytime.", fill=TEXT_MUTED, font=FONT_SMALL)
    draw.line([mx + 24, my + 80, mx + mw - 24, my + 80], fill=BORDER_STD, width=1)

    # Field 1: Collection Name
    draw.text((mx + 28, my + 96), "COLLECTION NAME * (REQUIRED)", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw_rounded_rect(draw, [mx + 28, my + 122, mx + mw - 28, my + 172], radius=8, fill=BG_DARK, outline=GOLD_FILL, width=2)
    draw.text((mx + 42, my + 137), "Ranch Gallery", fill=TEXT_WHITE, font=FONT_BOLD)

    # Field 2: Description (Optional)
    draw.text((mx + 28, my + 190), "DESCRIPTION (OPTIONAL — YES / NO)", fill=TEXT_MUTED, font=FONT_BOLD)
    draw_rounded_rect(draw, [mx + 28, my + 216, mx + mw - 28, my + 282], radius=8, fill=BG_DARK, outline=BORDER_LIGHT, width=1)
    draw.text((mx + 42, my + 230), "Curated 12K aerial plates for Ranch Gallery 65\" TV display", fill=TEXT_MUTED, font=FONT_REGULAR)

    # Footnote / Warning Badge
    warn_box = [mx + 28, my + 298, mx + mw - 28, my + 338]
    draw_rounded_rect(draw, warn_box, radius=6, fill=GOLD_DARK, outline=GOLD_FILL, width=1)
    draw.text((warn_box[0] + 14, warn_box[1] + 11), "IMPORTANT: The Create button stays locked until a name is typed!", fill=GOLD_LIGHT, font=FONT_SMALL)

    # Footer Buttons
    draw.line([mx + 24, my + 352, mx + mw - 24, my + 352], fill=BORDER_STD, width=1)
    # Cancel
    draw_rounded_rect(draw, [mx + mw - 310, my + 364, mx + mw - 205, my + 404], radius=8, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
    draw.text((mx + mw - 280, my + 375), "Cancel", fill=TEXT_MUTED, font=FONT_BOLD)

    # Glowing Yellow Create Collection Button
    create_btn = [mx + mw - 195, my + 364, mx + mw - 28, my + 404]
    draw_rounded_rect(draw, create_btn, radius=8, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    draw.text((create_btn[0] + 16, my + 375), "Create Collection", fill="#090909", font=FONT_BOLD)

    # Inset comparison badge on left
    draw_rounded_rect(draw, [18, 160, 195, 340], radius=10, fill=PANEL_BG, outline=GOLD_FILL, width=2)
    draw.text((30, 174), "BUTTON STATE:", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.text((30, 206), "1. Name Empty:", fill=TEXT_MUTED, font=FONT_SMALL)
    draw_rounded_rect(draw, [30, 228, 180, 258], radius=6, fill="#262626", outline="#3A3A3A")
    draw.text((40, 235), "Create (Locked)", fill="#777777", font=FONT_TINY)
    draw.text((30, 274), "2. Name Typed:", fill=EMERALD_LIGHT, font=FONT_SMALL)
    draw_rounded_rect(draw, [30, 296, 180, 326], radius=6, fill=GOLD_FILL, outline=GOLD_LIGHT)
    draw.text((38, 303), "Create (Lights Up!)", fill="#000", font=FONT_TINY)

    return im


# =============================================================================
# IMAGE 3: ADD PHOTO FROM GRID VIEW (BOTTOM ACTION DOCK)
# =============================================================================
def gen_step3():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Grid View & Bottom Action Dock")

    # Photo Grid (3 cols, 2 rows)
    gx = 24
    gy = 46
    pw, ph = 290, 190
    idx = 0
    for r in range(2):
        for c in range(3):
            rx = gx + c * (pw + 20)
            ry = gy + r * (ph + 20)
            isSelected = (r == 0 and c == 1)
            if idx < len(SAMPLE_PHOTOS):
                try:
                    p_im = Image.open(SAMPLE_PHOTOS[idx]).convert("RGB").resize((pw, ph))
                    im.paste(p_im, (rx, ry))
                except Exception:
                    draw.rectangle([rx, ry, rx + pw, ry + ph], fill=CARD_BG)
            else:
                draw.rectangle([rx, ry, rx + pw, ry + ph], fill=CARD_BG)
            if isSelected:
                draw.rectangle([rx, ry, rx + pw, ry + ph], outline=GOLD_LIGHT, width=4)
                draw_rounded_rect(draw, [rx + 10, ry + 10, rx + 135, ry + 36], radius=6, fill=GOLD_FILL)
                draw.text((rx + 18, ry + 15), "* SELECTED", fill="#000", font=FONT_SMALL)
            else:
                draw.rectangle([rx, ry, rx + pw, ry + ph], outline=BORDER_LIGHT, width=1)
            idx += 1

    # Open Dropdown Popover above bottom action dock
    pop_w, pop_h = 280, 185
    pop_x = (W - pop_w) // 2 + 20
    pop_y = H - 265
    draw_rounded_rect(draw, [pop_x, pop_y, pop_x + pop_w, pop_y + pop_h], radius=10, fill=PANEL_BG, outline=GOLD_FILL, width=2)
    draw.text((pop_x + 16, pop_y + 12), "Add to Collection", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.line([pop_x + 12, pop_y + 38, pop_x + pop_w - 12, pop_y + 38], fill=BORDER_STD, width=1)

    # Dropdown Items
    draw_rounded_rect(draw, [pop_x + 10, pop_y + 46, pop_x + pop_w - 10, pop_y + 82], radius=6, fill=GOLD_DARK, outline=GOLD_FILL, width=2)
    draw.text((pop_x + 18, pop_y + 55), "TV 1 - Ranch Gallery", fill=GOLD_LIGHT, font=FONT_BOLD)

    draw_rounded_rect(draw, [pop_x + 10, pop_y + 90, pop_x + pop_w - 10, pop_y + 126], radius=6, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
    draw.text((pop_x + 18, pop_y + 99), "Palouse Farmland (26)", fill=TEXT_WHITE, font=FONT_REGULAR)

    draw_rounded_rect(draw, [pop_x + 10, pop_y + 134, pop_x + pop_w - 10, pop_y + 170], radius=6, fill=CARD_BG, outline=GOLD_FILL, width=1)
    draw.text((pop_x + 18, pop_y + 143), "+ Create New Collection...", fill=GOLD_LIGHT, font=FONT_SMALL)

    # Bottom Floating Selection Dock
    dock_w = 680
    dock_h = 56
    dock_x = (W - dock_w) // 2
    dock_y = H - 72
    draw_rounded_rect(draw, [dock_x, dock_y, dock_x + dock_w, dock_y + dock_h], radius=12, fill=PANEL_BG, outline=BORDER_LIGHT, width=2)
    draw_rounded_rect(draw, [dock_x + 14, dock_y + 10, dock_x + 125, dock_y + 46], radius=8, fill=GOLD_FILL)
    draw.text((dock_x + 24, dock_y + 19), "1 Selected", fill="#000", font=FONT_BOLD)

    draw_rounded_rect(draw, [dock_x + 138, dock_y + 10, dock_x + 290, dock_y + 46], radius=8, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
    draw.text((dock_x + 155, dock_y + 19), "AI Keywords", fill=TEXT_WHITE, font=FONT_SMALL)

    draw_rounded_rect(draw, [dock_x + 302, dock_y + 10, dock_x + 495, dock_y + 46], radius=8, fill=GOLD_DARK, outline=GOLD_FILL, width=2)
    draw.text((dock_x + 322, dock_y + 19), "Add to Collection", fill=GOLD_LIGHT, font=FONT_BOLD)

    draw_rounded_rect(draw, [dock_x + 508, dock_y + 10, dock_x + 664, dock_y + 46], radius=8, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
    draw.text((dock_x + 550, dock_y + 19), "Export", fill=TEXT_WHITE, font=FONT_SMALL)

    # Callout Arrow to Collection item
    callout = [30, pop_y + 30, pop_x - 35, pop_y + 100]
    draw_callout_box(draw, callout, [
        "Click target collection",
        "(e.g. TV 1 or Palouse)"
    ], border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT)
    draw_right_arrow(draw, (callout[2], pop_y + 64), (pop_x + 4, pop_y + 64), color=GOLD_FILL, width=4)

    return im


# =============================================================================
# IMAGE 4: ADD PHOTO FROM FULLSCREEN LIGHTBOX
# =============================================================================
def gen_step4():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), "#0A0A0A")
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Fullscreen Lightbox View (Spacebar)")

    if SAMPLE_PHOTOS:
        try:
            big_im = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((W - 100, H - 130))
            im.paste(big_im, (50, 90))
        except Exception:
            pass

    # Top Lightbox Navigation Bar
    draw.rectangle([0, 32, W, 84], fill=PANEL_BG)
    draw.line([0, 84, W, 84], fill=BORDER_STD, width=1)

    draw.text((20, 48), "Rouse_MM_20201002_00073.dng", fill=TEXT_WHITE, font=FONT_BOLD)
    draw.text((310, 48), "5 Stars", fill=GOLD_LIGHT, font=FONT_BOLD)

    # Add to Collection button (Highlighted in Yellow)
    draw_rounded_rect(draw, [420, 40, 620, 76], radius=6, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    draw.text((442, 49), "+ Add to Collection", fill="#090909", font=FONT_BOLD)

    # Lightroom Edit button
    draw_rounded_rect(draw, [634, 40, 810, 76], radius=6, fill=CARD_BG, outline=BORDER_LIGHT, width=1)
    draw.text((648, 49), "Edit in Lightroom (L)", fill=TEXT_WHITE, font=FONT_SMALL)

    # Toast Notification on right
    draw_rounded_rect(draw, [420, 94, 660, 132], radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL, width=2)
    draw.text((436, 105), "Added to Ranch Gallery", fill=EMERALD_LIGHT, font=FONT_BOLD)

    # Callout Arrow
    callout = [W - 420, 155, W - 40, 225]
    draw_callout_box(draw, callout, [
        "In Fullscreen Lightbox:",
        "Click 'Add to Collection' in top bar"
    ], border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT)
    draw_down_arrow(draw, (callout[0] + 60, callout[1]), (520, 80), color=GOLD_FILL, width=4)

    return im


# =============================================================================
# IMAGE 5: 65" TV SHOWCASE 16:9 CROP & 3 DIRECT EXPORT BUTTONS
# =============================================================================
def gen_step5():
    W, H = 960, 560
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — 65\" TV Showcase 16:9 Crop Placement")

    # Header Bar
    draw.rectangle([0, 32, W, 90], fill=PANEL_BG)
    draw.line([0, 90, W, 90], fill=BORDER_STD, width=1)
    draw.text((22, 48), "65\" TV Showcase 16:9 Crop Placement", fill=TEXT_WHITE, font=FONT_BOLD)
    draw_rounded_rect(draw, [365, 44, 520, 76], radius=8, fill=GOLD_DARK, outline=GOLD_FILL, width=1)
    draw.text((380, 52), "Collection: Ranch Gallery", fill=GOLD_LIGHT, font=FONT_SMALL)
    draw_rounded_rect(draw, [535, 44, 745, 76], radius=8, fill=EMERALD_DARK, outline=EMERALD_FILL, width=1)
    draw.text((550, 52), "12,000 x 6,750 px • 180 DPI", fill=EMERALD_LIGHT, font=FONT_SMALL)

    # Central Crop Area with Photo
    cw, ch = 580, 310
    cx = (W - cw) // 2
    cy = 102
    if len(SAMPLE_PHOTOS) > 1:
        try:
            p_im = Image.open(SAMPLE_PHOTOS[1]).convert("RGB").resize((cw, ch))
            im.paste(p_im, (cx, cy))
        except Exception:
            draw.rectangle([cx, cy, cx + cw, cy + ch], fill=CARD_BG)
    else:
        draw.rectangle([cx, cy, cx + cw, cy + ch], fill=CARD_BG)

    # 16:9 Green Crop Bounding Box
    crop_h = int(cw * 9 / 16)
    crop_y = cy + (ch - crop_h) // 2
    draw.rectangle([cx, crop_y, cx + cw, crop_y + crop_h], outline=EMERALD_FILL, width=4)
    draw_rounded_rect(draw, [cx + cw // 2 - 105, crop_y + 14, cx + cw // 2 + 105, crop_y + 44], radius=12, fill=BG_DARK, outline=EMERALD_LIGHT, width=2)
    draw.text((cx + cw // 2 - 86, crop_y + 21), "DRAG UP/DOWN TO FRAME", fill=EMERALD_LIGHT, font=FONT_SMALL)

    # Presets & Apply to All Controls
    py = cy + ch + 12
    draw.text((24, py + 8), "PRESETS:", fill=TEXT_MUTED, font=FONT_SMALL)
    draw_rounded_rect(draw, [110, py, 210, py + 32], radius=6, fill=CARD_BG, outline=BORDER_LIGHT)
    draw.text((126, py + 8), "Sky / Top", fill=TEXT_WHITE, font=FONT_SMALL)

    draw_rounded_rect(draw, [220, py, 360, py + 32], radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL)
    draw.text((238, py + 8), "Golden Horizon", fill=EMERALD_LIGHT, font=FONT_SMALL)

    draw_rounded_rect(draw, [370, py, 520, py + 32], radius=6, fill=CARD_BG, outline=BORDER_LIGHT)
    draw.text((384, py + 8), "Foreground / Bottom", fill=TEXT_WHITE, font=FONT_SMALL)

    draw_rounded_rect(draw, [W - 280, py, W - 24, py + 32], radius=6, fill=CARD_BG, outline=GOLD_FILL)
    draw.text((W - 260, py + 8), "Apply Placement to All Photos", fill=GOLD_LIGHT, font=FONT_SMALL)

    # Footer with 3 Direct 1-Click Buttons
    fy = H - 72
    draw.rectangle([0, fy, W, H], fill=PANEL_BG)
    draw.line([0, fy, W, fy], fill=BORDER_STD, width=1)

    draw.text((24, fy + 26), "Target: 12,000 x 6,750 px • 180 DPI • Embedded IPTC/XMP", fill=TEXT_MUTED, font=FONT_SMALL)

    # Button 1: Desktop
    draw_rounded_rect(draw, [415, fy + 14, 575, fy + 58], radius=8, fill=EMERALD_DARK, outline=EMERALD_FILL, width=2)
    draw.text((442, fy + 26), "To Desktop", fill=EMERALD_LIGHT, font=FONT_BOLD)

    # Button 2: iCloud (Highlighted)
    draw_rounded_rect(draw, [588, fy + 14, 755, fy + 58], radius=8, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    draw.text((614, fy + 26), "To iCloud TV", fill="#090909", font=FONT_BOLD)

    # Button 3: Choose Folder
    draw_rounded_rect(draw, [768, fy + 14, W - 20, fy + 58], radius=8, fill=CARD_BG, outline=BORDER_LIGHT, width=2)
    draw.text((790, fy + 26), "Choose Folder", fill=TEXT_WHITE, font=FONT_BOLD)

    return im


# =============================================================================
# IMAGE 6: MACOS FINDER ICLOUD TV FOLDER STRUCTURE
# =============================================================================
def gen_step6():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "macOS Finder — iCloud Drive / TV Folder / Ranch Gallery")

    # Finder Toolbar
    draw.rectangle([0, 32, W, 72], fill=PANEL_BG)
    draw.line([0, 72, W, 72], fill=BORDER_STD, width=1)
    draw.text((20, 44), "<  >   iCloud Drive   >   TV Folder   >   Ranch Gallery", fill=TEXT_WHITE, font=FONT_BOLD)

    # Sidebar
    sw = 220
    draw.rectangle([0, 73, sw, H], fill=PANEL_BG)
    draw.line([sw, 73, sw, H], fill=BORDER_STD, width=1)
    draw.text((18, 90), "FAVORITES", fill=TEXT_DIM, font=FONT_TINY)
    draw.text((26, 114), "Desktop", fill=TEXT_MUTED, font=FONT_SMALL)
    draw.text((26, 142), "Downloads", fill=TEXT_MUTED, font=FONT_SMALL)

    draw.text((18, 182), "CLOUD DRIVES", fill=TEXT_DIM, font=FONT_TINY)
    draw_rounded_rect(draw, [12, 204, sw - 12, 238], radius=6, fill=HOVER_BG, outline=GOLD_FILL, width=1)
    draw.text((26, 213), "iCloud Drive", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.text((26, 250), "Google Drive", fill=TEXT_MUTED, font=FONT_SMALL)

    # Main Finder Column (Subfolders named after Collections)
    lw = 270
    draw.rectangle([sw + 1, 73, sw + lw, H], fill=BG_DARK)
    draw.line([sw + lw, 73, sw + lw, H], fill=BORDER_STD, width=1)
    draw.text((sw + 18, 90), "TV FOLDER SUBFOLDERS:", fill=TEXT_DIM, font=FONT_TINY)

    folders = [
        ("Ranch Gallery", True),
        ("Palouse", False),
        ("TV 1 - Living Room", False),
        ("TV 2 - Office", False),
    ]
    fy = 116
    for fname, is_active in folders:
        if is_active:
            draw_rounded_rect(draw, [sw + 12, fy, sw + lw - 12, fy + 40], radius=6, fill=GOLD_FILL)
            draw.text((sw + 24, fy + 11), fname, fill="#090909", font=FONT_BOLD)
        else:
            draw_rounded_rect(draw, [sw + 12, fy, sw + lw - 12, fy + 40], radius=6, fill=CARD_BG, outline=BORDER_STD)
            draw.text((sw + 24, fy + 11), fname, fill=TEXT_WHITE, font=FONT_SMALL)
        fy += 50

    # Inside Selected Folder (Ranch Gallery)
    file_x = sw + lw + 22
    draw.text((file_x, 90), "12K MASTER JPEGS IN 'Ranch Gallery':", fill=TEXT_DIM, font=FONT_TINY)

    files = [
        "Rouse_MM_20201002_00073_12K_TV_16x9.jpg",
        "Rouse_MM_20201002_00082_12K_TV_16x9.jpg",
        "Rouse_MM_20201002_00088_12K_TV_16x9.jpg",
    ]
    ffy = 116
    for fn in files:
        draw_rounded_rect(draw, [file_x, ffy, W - 22, ffy + 42], radius=6, fill=CARD_BG, outline=BORDER_LIGHT)
        draw.text((file_x + 14, ffy + 12), fn, fill=TEXT_WHITE, font=FONT_SMALL)
        ffy += 52

    # Preview Card for Apple TV sync
    tv_card = [file_x, 290, W - 22, H - 24]
    draw_rounded_rect(draw, tv_card, radius=10, fill=GOLD_DARK, outline=GOLD_FILL, width=2)
    draw.text((tv_card[0] + 18, tv_card[1] + 18), "Automatic Collection Folder Naming", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.text((tv_card[0] + 18, tv_card[1] + 48), "• Collection 'Ranch Gallery' -> TV Folder / Ranch Gallery", fill=TEXT_WHITE, font=FONT_SMALL)
    draw.text((tv_card[0] + 18, tv_card[1] + 74), "• Collection 'Palouse' -> TV Folder / Palouse", fill=TEXT_WHITE, font=FONT_SMALL)
    draw.text((tv_card[0] + 18, tv_card[1] + 100), "• Point Apple TV Photos app directly to each subfolder!", fill=EMERALD_LIGHT, font=FONT_BOLD)

    return im


# =============================================================================
# IMAGE 7: LIGHTROOM CLASSIC EDIT BUTTON & SHORTCUT (L KEY)
# =============================================================================
def gen_step7():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Launching Adobe Lightroom Classic (Key L)")

    pw, ph = 500, 340
    px = 34
    py = 90
    if SAMPLE_PHOTOS:
        try:
            p_im = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((pw, ph))
            im.paste(p_im, (px, py))
        except Exception:
            pass

    draw.rectangle([px, py, px + pw, py + ph], outline=GOLD_FILL, width=3)

    draw_rounded_rect(draw, [px + 12, py + 12, px + 310, py + 48], radius=6, fill=BG_DARK, outline=BORDER_LIGHT)
    draw.text((px + 22, py + 22), "Rouse_MM_20201002_00073.dng", fill=TEXT_WHITE, font=FONT_SMALL)

    rx = px + pw + 34
    draw.text((rx, 90), "OPEN IN LIGHTROOM CLASSIC", fill=GOLD_LIGHT, font=FONT_TITLE)

    lr_btn = [rx, 136, W - 34, 194]
    draw_rounded_rect(draw, lr_btn, radius=10, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    draw.text((rx + 24, 156), "Edit in Lightroom (Press L)", fill="#090909", font=FONT_BOLD)

    draw_rounded_rect(draw, [rx, 214, rx + 220, 268], radius=8, fill=CARD_BG, outline=GOLD_FILL, width=2)
    draw.text((rx + 20, 232), "KEYBOARD HOTKEY:  L", fill=GOLD_LIGHT, font=FONT_BOLD)

    ey = 294
    draw.text((rx, ey), "1. Auto-finds master .lrcat catalog", fill=TEXT_WHITE, font=FONT_REGULAR)
    draw.text((rx, ey + 30), "2. Opens Lightroom to this exact RAW", fill=TEXT_WHITE, font=FONT_REGULAR)
    draw.text((rx, ey + 60), "3. Works from Grid or Fullscreen view", fill=TEXT_WHITE, font=FONT_REGULAR)

    return im


# =============================================================================
# IMAGE 8: LIGHTROOM SAVE METADATA (CMD+S) & SYNC EDITS
# =============================================================================
def gen_step8():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Lightroom Save (Cmd+S) & Sync Edits Roundtrip")

    # Step A: Lightroom Classic Side
    box_a = [32, 68, 455, H - 34]
    draw_rounded_rect(draw, box_a, radius=12, fill=PANEL_BG, outline=BORDER_LIGHT, width=2)
    draw.text((54, 92), "STEP A: In Lightroom Classic", fill=GOLD_LIGHT, font=FONT_TITLE)
    draw.text((54, 134), "1. Crop, color grade, or adjust exposure", fill=TEXT_WHITE, font=FONT_REGULAR)
    draw.text((54, 168), "2. Press Cmd + S (Save Metadata)", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.text((54, 194), "   Saves adjustments to .xmp sidecar on disk", fill=TEXT_MUTED, font=FONT_SMALL)

    draw_rounded_rect(draw, [54, 236, 260, 294], radius=8, fill=GOLD_DARK, outline=GOLD_FILL, width=2)
    draw.text((76, 254), "Press  Cmd + S", fill=GOLD_LIGHT, font=FONT_TITLE)
    draw.text((54, 316), "Wait 30 sec - 2 min for preview cache write", fill=TEXT_MUTED, font=FONT_SMALL)

    # Step B: MRDarkroom Sync Side
    box_b = [505, 68, W - 32, H - 34]
    draw_rounded_rect(draw, box_b, radius=12, fill=PANEL_BG, outline=EMERALD_FILL, width=2)
    draw.text((528, 92), "STEP B: In MR Darkroom", fill=EMERALD_LIGHT, font=FONT_TITLE)

    sync_btn = [528, 140, W - 56, 198]
    draw_rounded_rect(draw, sync_btn, radius=10, fill=EMERALD_FILL, outline=EMERALD_LIGHT, width=2)
    draw.text((552, 160), "Click 'Sync Edits' (or Shift+S)", fill="#051b14", font=FONT_BOLD)

    draw_rounded_rect(draw, [528, 220, W - 56, 266], radius=8, fill=EMERALD_DARK, outline=EMERALD_FILL)
    draw.text((544, 234), "Preview & edits updated immediately!", fill=EMERALD_LIGHT, font=FONT_BOLD)

    # Before / After visual thumbnails inside Step B
    if SAMPLE_PHOTOS:
        try:
            raw_im = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((165, 110))
            im.paste(raw_im, (528, 300))
            draw.rectangle([528, 300, 528 + 165, 300 + 110], outline=BORDER_LIGHT, width=1)
            draw.text((528, 418), "Before (Original)", fill=TEXT_MUTED, font=FONT_TINY)

            edited_im = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((165, 110))
            im.paste(edited_im, (720, 300))
            draw.rectangle([720, 300, 720 + 165, 300 + 110], outline=EMERALD_FILL, width=2)
            draw.text((720, 418), "After (Synced Grade)", fill=EMERALD_LIGHT, font=FONT_TINY)
        except Exception:
            pass

    draw_right_arrow(draw, (460, 250), (500, 250), color=GOLD_FILL, width=4)

    return im


# =============================================================================
# IMAGE 9: INGEST & LIGHTROOM CATALOG AUTO-DETECTION
# =============================================================================
def gen_step9():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Creating a Catalog & Master Shoot Ingest")

    mw, mh = 760, 430
    mx = (W - mw) // 2
    my = (H - mh) // 2 + 12
    draw_rounded_rect(draw, [mx, my, mx + mw, my + mh], radius=14, fill=PANEL_BG, outline=GOLD_FILL, width=2)

    draw.text((mx + 28, my + 24), "Create Catalog & Master Shoot Ingest", fill=TEXT_WHITE, font=FONT_TITLE)
    draw.text((mx + 28, my + 56), "Select your master shoot folder on external RAID, DAS, or NVMe SSD (not SD cards).", fill=TEXT_MUTED, font=FONT_SMALL)
    draw.line([mx + 24, my + 84, mx + mw - 24, my + 84], fill=BORDER_STD, width=1)

    draw.text((mx + 28, my + 102), "1. MASTER SHOOT DIRECTORY (EXTERNAL RAID / SSD):", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw_rounded_rect(draw, [mx + 28, my + 128, mx + mw - 28, my + 176], radius=8, fill=BG_DARK, outline=BORDER_LIGHT, width=2)
    draw.text((mx + 42, my + 144), "/Volumes/Pegasus_RAID/2026_Shoots/Ranch_Catalog", fill=TEXT_WHITE, font=FONT_MONO)

    draw.text((mx + 28, my + 198), "2. AUTO-DETECTED LIGHTROOM FILES:", fill=EMERALD_LIGHT, font=FONT_BOLD)

    b1 = [mx + 28, my + 224, mx + mw - 28, my + 270]
    draw_rounded_rect(draw, b1, radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL)
    draw.text((b1[0] + 16, b1[1] + 14), "Auto-Identified .lrcat Database: 'Ranch_Catalog.lrcat'", fill=EMERALD_LIGHT, font=FONT_BOLD)

    b2 = [mx + 28, my + 282, mx + mw - 28, my + 328]
    draw_rounded_rect(draw, b2, radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL)
    draw.text((b2[0] + 16, b2[1] + 14), "Found .lrdata Previews (Instant high-res display without RAW delay)", fill=EMERALD_LIGHT, font=FONT_BOLD)

    draw.line([mx + 24, my + 348, mx + mw - 24, my + 348], fill=BORDER_STD, width=1)
    ingest_btn = [mx + mw - 240, my + 364, mx + mw - 28, my + 412]
    draw_rounded_rect(draw, ingest_btn, radius=8, fill=GOLD_FILL, outline=GOLD_LIGHT, width=2)
    draw.text((ingest_btn[0] + 48, my + 379), "Start Ingest", fill="#090909", font=FONT_BOLD)

    return im


# =============================================================================
# IMAGE 10: SAMSUNG FRAME TV DISPLAYS STUDIO & INTERACTIVE MATTING
# =============================================================================
def gen_step10():
    W, H = 960, 580
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Samsung Frame TV Displays Studio & Live Matting")

    # Header Bar (TV Displays Tab & Controls)
    draw.rectangle([0, 32, W, 84], fill=PANEL_BG)
    draw.line([0, 84, W, 84], fill=BORDER_STD, width=1)

    # Nav Tabs
    tabs = ["Grid", "Trips", "Collections", "TV Displays"]
    tx = 16
    for t in tabs:
        isActive = (t == "TV Displays")
        bg = GOLD_DARK if isActive else CARD_BG
        border = GOLD_FILL if isActive else BORDER_STD
        color = GOLD_LIGHT if isActive else TEXT_MUTED
        draw_rounded_rect(draw, [tx, 44, tx + 94, 74], radius=6, fill=bg, outline=border, width=1)
        draw.text((tx + 12, 52), t, fill=color, font=FONT_SMALL)
        tx += 102

    # TV Online Pill
    draw_rounded_rect(draw, [tx + 12, 44, tx + 180, 74], radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL, width=1)
    draw.text((tx + 24, 52), "TV1 Online (Frame)", fill=EMERALD_LIGHT, font=FONT_SMALL)

    # Scan Wi-Fi Network Button
    scan_btn = [W - 360, 42, W - 180, 74]
    draw_rounded_rect(draw, scan_btn, radius=6, fill=CARD_BG, outline=GOLD_FILL, width=1)
    draw.text((scan_btn[0] + 12, 51), "Scan Wi-Fi for TVs", fill=GOLD_LIGHT, font=FONT_SMALL)

    # Add from Collection Button
    add_btn = [W - 170, 42, W - 16, 74]
    draw_rounded_rect(draw, add_btn, radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL, width=1)
    draw.text((add_btn[0] + 14, 51), "+ Add Collection", fill=EMERALD_LIGHT, font=FONT_SMALL)

    # Callout for Scan Wi-Fi
    draw_callout_box(draw, [W - 380, 94, W - 16, 142], ["Click 'Scan Wi-Fi' to discover Frame TVs", "automatically on local subnet (no manual IP)"], border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT, font=FONT_TINY)
    draw_up_arrow(draw, (W - 270, 94), (W - 270, 78), color=GOLD_FILL, width=3)

    # Studio Workbench Left: Simulated Frame TV Canvas with Beveled Mat
    tv_w, tv_h = 440, 248
    tv_x, tv_y = 20, 156
    draw.rectangle([tv_x - 4, tv_y - 4, tv_x + tv_w + 4, tv_y + tv_h + 4], fill="#141414", outline="#2e2e2e", width=2)
    # Mat board fill (Antique Ivory / Warm Rag)
    mat_color = (234, 219, 202)
    draw.rectangle([tv_x, tv_y, tv_x + tv_w, tv_y + tv_h], fill=mat_color)

    # Window Aperture (Slim Optical - 88% width, 44% top lift)
    win_w, win_h = 360, 180
    win_x = tv_x + (tv_w - win_w) // 2
    win_y = tv_y + int((tv_h - win_h) * 0.44)

    # 45° Bevel Cut around aperture (3/4 depth = 5px on this scale)
    bw = 5
    top_outer, top_inner = (196, 190, 175), (173, 166, 151)
    bot_outer, bot_inner = (238, 233, 222), (248, 246, 240)
    left_outer, left_inner = (210, 204, 190), (192, 186, 171)
    right_outer, right_inner = (230, 225, 213), (240, 235, 224)

    draw.polygon([(win_x - bw, win_y - bw), (win_x + win_w + bw, win_y - bw), (win_x + win_w, win_y), (win_x, win_y)], fill=top_inner)
    draw.polygon([(win_x, win_y + win_h), (win_x + win_w, win_y + win_h), (win_x + win_w + bw, win_y + win_h + bw), (win_x - bw, win_y + win_h + bw)], fill=bot_inner)
    draw.polygon([(win_x - bw, win_y - bw), (win_x, win_y), (win_x, win_y + win_h), (win_x - bw, win_y + win_h + bw)], fill=left_inner)
    draw.polygon([(win_x + win_w, win_y), (win_x + win_w + bw, win_y - bw), (win_x + win_w + bw, win_y + win_h + bw), (win_x + win_w, win_y + win_h)], fill=right_inner)

    # Paste sample aerial photo into aperture
    if SAMPLE_PHOTOS:
        try:
            sample_im = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((win_w, win_h))
            im.paste(sample_im, (win_x, win_y))
        except Exception:
            draw.rectangle([win_x, win_y, win_x + win_w, win_y + win_h], fill="#1c2430")
    else:
        draw.rectangle([win_x, win_y, win_x + win_w, win_y + win_h], fill="#1c2430")

    draw.rectangle([win_x, win_y, win_x + win_w, win_y + win_h], outline=(158, 152, 140), width=1)

    # Callout for 45° Bevel Cut
    draw_callout_box(draw, [20, 94, 340, 142], ["Authentic 45° White-Core Paper Bevel", "Soft diffuse lighting & optical depth"], border_color=EMERALD_FILL, bg_color=EMERALD_DARK, text_color=EMERALD_LIGHT, font=FONT_TINY)
    draw_down_arrow(draw, (180, 142), (win_x + 60, win_y - 2), color=EMERALD_FILL, width=3)

    # Studio Workbench Right: Controls Panel
    rx = 480
    draw.text((rx, 156), "MAT STYLE:", fill=TEXT_MUTED, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 80, 150, rx + 180, 178], radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL, width=1)
    draw.text((rx + 92, 158), "Single Mat", fill=EMERALD_LIGHT, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 190, 150, rx + 300, 178], radius=6, fill=CARD_BG, outline=BORDER_STD)
    draw.text((rx + 202, 158), "Double Mat", fill=TEXT_WHITE, font=FONT_TINY)

    draw.text((rx, 196), "ASPECT RATIO:", fill=TEXT_MUTED, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 100, 190, rx + 240, 218], radius=6, fill=GOLD_DARK, outline=GOLD_FILL, width=1)
    draw.text((rx + 112, 198), "Original (No Crop)", fill=GOLD_LIGHT, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 248, 190, rx + 348, 218], radius=6, fill=CARD_BG, outline=BORDER_STD)
    draw.text((rx + 260, 198), "16:9 + Mat", fill=TEXT_WHITE, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 356, 190, rx + 430, 218], radius=6, fill=CARD_BG, outline=BORDER_STD)
    draw.text((rx + 368, 198), "3:1 Pano", fill=TEXT_WHITE, font=FONT_TINY)

    draw.text((rx, 236), "BORDER SIZE:", fill=TEXT_MUTED, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 90, 230, rx + 220, 258], radius=6, fill=EMERALD_DARK, outline=EMERALD_FILL, width=1)
    draw.text((rx + 102, 238), "Slim Optical (88%)", fill=EMERALD_LIGHT, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 228, 230, rx + 340, 258], radius=6, fill=CARD_BG, outline=BORDER_STD)
    draw.text((rx + 240, 238), "Slim Centered", fill=TEXT_WHITE, font=FONT_TINY)
    draw_rounded_rect(draw, [rx + 348, 230, rx + 440, 258], radius=6, fill=CARD_BG, outline=BORDER_STD)
    draw.text((rx + 358, 238), "Medium Wide", fill=TEXT_WHITE, font=FONT_TINY)

    # Color Swatches Bar
    draw.text((rx, 276), "12 ARCHIVAL MAT COLORS:", fill=TEXT_MUTED, font=FONT_TINY)
    colors = [
        ("#F4EFE6", "Warm White"),
        ("#D8CBB7", "Sandstone"),
        ("#E8DEC8", "Wheat"),
        ("#4E5B4B", "Sage Olive"),
        ("#28382B", "Forest Pine"),
        ("#581C25", "Burgundy"),
        ("#2A2E33", "Slate"),
    ]
    cx = rx
    for hex_c, cname in colors:
        draw_rounded_rect(draw, [cx, 296, cx + 48, 322], radius=4, fill=hex_c, outline=BORDER_LIGHT)
        cx += 54

    # Action Buttons
    apply_all_btn = [rx, 340, rx + 210, 380]
    draw_rounded_rect(draw, apply_all_btn, radius=8, fill=CARD_BG, outline=GOLD_FILL, width=1)
    draw.text((rx + 18, 352), "Apply Style to All Photos", fill=GOLD_LIGHT, font=FONT_SMALL)

    update_tv_btn = [rx + 220, 340, rx + 440, 380]
    draw_rounded_rect(draw, update_tv_btn, radius=8, fill=EMERALD_FILL, outline=EMERALD_LIGHT, width=2)
    draw.text((rx + 238, 352), "Update Photo on TV", fill="#051b14", font=FONT_BOLD)

    # Bottom Photo Cards (Sequence & Reordering)
    draw.line([0, 412, W, 412], fill=BORDER_STD, width=1)
    draw.text((20, 422), "CURATED ART ON DISPLAY (Drag cards or use < / > to reorder sequence):", fill=TEXT_MUTED, font=FONT_TINY)

    card_w, card_h = 210, 120
    for idx in range(4):
        card_x = 20 + idx * 230
        card_y = 442
        is_active = (idx == 0)
        border_c = EMERALD_FILL if is_active else BORDER_STD
        draw_rounded_rect(draw, [card_x, card_y, card_x + card_w, card_y + card_h], radius=8, fill=CARD_BG, outline=border_c, width=2 if is_active else 1)

        # Inner mini TV preview
        if idx < len(SAMPLE_PHOTOS):
            try:
                thumb = Image.open(SAMPLE_PHOTOS[idx]).convert("RGB").resize((card_w - 12, card_h - 40))
                im.paste(thumb, (card_x + 6, card_y + 6))
            except Exception:
                pass

        # Index badge & Reorder controls
        badge_txt = f"#{idx + 1} On TV" if is_active else f"#{idx + 1}"
        draw_rounded_rect(draw, [card_x + 8, card_y + card_h - 28, card_x + 80, card_y + card_h - 6], radius=4, fill="#111111", outline=border_c)
        draw.text((card_x + 14, card_y + card_h - 24), badge_txt, fill=EMERALD_LIGHT if is_active else TEXT_WHITE, font=FONT_TINY)

        # Left / Right reorder arrows
        draw_rounded_rect(draw, [card_x + card_w - 56, card_y + card_h - 28, card_x + card_w - 32, card_y + card_h - 6], radius=4, fill="#1c1c1c", outline=BORDER_LIGHT)
        draw.text((card_x + card_w - 50, card_y + card_h - 24), "<", fill=TEXT_WHITE, font=FONT_TINY)

        draw_rounded_rect(draw, [card_x + card_w - 28, card_y + card_h - 28, card_x + card_w - 6, card_y + card_h - 6], radius=4, fill="#1c1c1c", outline=BORDER_LIGHT)
        draw.text((card_x + card_w - 22, card_y + card_h - 24), ">", fill=TEXT_WHITE, font=FONT_TINY)

    # Callout for Reorder Controls
    draw_callout_box(draw, [W - 320, 420, W - 16, 458], ["Click < / > to reorder sequence", "First card is displayed on TV"], border_color=GOLD_FILL, bg_color=GOLD_DARK, text_color=GOLD_LIGHT, font=FONT_TINY)

    return im


# =============================================================================
# IMAGE 11: SINGLE MAT VS DOUBLE MAT ARCHITECTURE & PRESERVATION
# =============================================================================
def gen_step11():
    W, H = 960, 540
    im = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(im)
    draw_window_chrome(draw, W, "MR Darkroom — Single Mat vs. Double Mat Museum Framing")

    card_w = (W - 60) // 2
    card_h = H - 60
    cy = 46

    # ================= LEFT: SINGLE MAT =================
    lx = 20
    draw_rounded_rect(draw, [lx, cy, lx + card_w, cy + card_h], radius=12, fill=PANEL_BG, outline=BORDER_LIGHT, width=2)
    draw.text((lx + 20, cy + 18), "1. SINGLE MAT (Contemporary Gallery)", fill=GOLD_LIGHT, font=FONT_BOLD)
    draw.text((lx + 20, cy + 42), "Pure, minimalist presentation for panoramas & landscape", fill=TEXT_MUTED, font=FONT_TINY)

    # Mini 16:9 Frame TV Canvas
    mw, mh = card_w - 40, 200
    mx = lx + 20
    my = cy + 70
    draw.rectangle([mx, my, mx + mw, my + mh], fill=(244, 239, 230), outline="#111111", width=2)

    # Single aperture with 45° bevel cut
    aw, ah = int(mw * 0.76), int(mh * 0.68)
    ax = mx + (mw - aw) // 2
    ay = my + int((mh - ah) * 0.44)

    # 45° bevel
    bw = 6
    draw.polygon([(ax - bw, ay - bw), (ax + aw + bw, ay - bw), (ax + aw, ay), (ax, ay)], fill=(173, 166, 151))
    draw.polygon([(ax, ay + ah), (ax + aw, ay + ah), (ax + aw + bw, ay + ah + bw), (ax - bw, ay + ah + bw)], fill=(248, 246, 240))
    draw.polygon([(ax - bw, ay - bw), (ax, ay), (ax, ay + ah), (ax - bw, ay + ah + bw)], fill=(192, 186, 171))
    draw.polygon([(ax + aw, ay), (ax + aw + bw, ay - bw), (ax + aw + bw, ay + ah + bw), (ax + aw, ay + ah)], fill=(240, 235, 224))

    if SAMPLE_PHOTOS:
        try:
            p1 = Image.open(SAMPLE_PHOTOS[0]).convert("RGB").resize((aw, ah))
            im.paste(p1, (ax, ay))
        except Exception:
            pass

    draw.rectangle([ax, ay, ax + aw, ay + ah], outline=(158, 152, 140), width=1)

    # Callout list
    oy = my + mh + 16
    specs_left = [
        ("• 45° White-Core Bevel Cut:", "Gentle chamfer down to the artwork"),
        ("• Subtle Gallery Shading:", "Warm diffuse overhead tone (3/4 trim depth)"),
        ("• Native Aspect Preservation:", "Zero forced cropping, true 3:1 & 2:1 panos"),
        ("• Slim Optical Elevation:", "Subtle 44% top / 56% bottom vertical lift"),
    ]
    for title, desc in specs_left:
        draw.text((lx + 20, oy), title, fill=GOLD_LIGHT, font=FONT_TINY)
        draw.text((lx + 20, oy + 16), desc, fill=TEXT_WHITE, font=FONT_TINY)
        oy += 36

    # ================= RIGHT: DOUBLE MAT =================
    rx = lx + card_w + 20
    draw_rounded_rect(draw, [rx, cy, rx + card_w, cy + card_h], radius=12, fill=PANEL_BG, outline=EMERALD_FILL, width=2)
    draw.text((rx + 20, cy + 18), "2. DOUBLE MAT (Architectural Luxury)", fill=EMERALD_LIGHT, font=FONT_BOLD)
    draw.text((rx + 20, cy + 42), "Outer museum mat board + inner accent reveal strip", fill=TEXT_MUTED, font=FONT_TINY)

    # Mini 16:9 Frame TV Canvas with Deep Pine Outer Mat
    mx2 = rx + 20
    draw.rectangle([mx2, my, mx2 + mw, my + mh], fill=(40, 56, 43), outline="#111111", width=2)

    # Double Mat: Outer Bevel + Inner Mat Reveal + Inner Bevel
    reveal = 10
    o_bw = 4
    i_bw = 5

    # Outer mat opening
    oax = ax - reveal
    oay = ay - reveal
    oaw = aw + reveal * 2
    oah = ah + reveal * 2

    # Outer bevel
    draw.polygon([(oax - o_bw, oay - o_bw), (oax + oaw + o_bw, oay - o_bw), (oax + oaw, oay), (oax, oay)], fill=(173, 166, 151))
    draw.polygon([(oax, oay + oah), (oax + oaw, oay + oah), (oax + oaw + o_bw, oay + oah + o_bw), (oax - o_bw, oay + oah + o_bw)], fill=(248, 246, 240))
    draw.polygon([(oax - o_bw, oay - o_bw), (oax, oay), (oax, oay + oah), (oax - o_bw, oay + oah + o_bw)], fill=(192, 186, 171))
    draw.polygon([(oax + oaw, oay), (oax + oaw + o_bw, oay - o_bw), (oax + oaw + o_bw, oay + oah + o_bw), (oax + oaw, oay + oah)], fill=(240, 235, 224))

    # Inner mat reveal strip (Warm White Rag)
    draw.rectangle([oax, oay, oax + oaw, oay + oah], fill=(244, 239, 230))

    # Inner bevel
    draw.polygon([(ax - i_bw, ay - i_bw), (ax + aw + i_bw, ay - i_bw), (ax + aw, ay), (ax, ay)], fill=(173, 166, 151))
    draw.polygon([(ax, ay + ah), (ax + aw, ay + ah), (ax + aw + i_bw, ay + ah + i_bw), (ax - i_bw, ay + ah + i_bw)], fill=(248, 246, 240))
    draw.polygon([(ax - i_bw, ay - i_bw), (ax, ay), (ax, ay + ah), (ax - i_bw, ay + ah + i_bw)], fill=(192, 186, 171))
    draw.polygon([(ax + aw, ay), (ax + aw + i_bw, ay - i_bw), (ax + aw + i_bw, ay + ah + i_bw), (ax + aw, ay + ah)], fill=(240, 235, 224))

    if SAMPLE_PHOTOS and len(SAMPLE_PHOTOS) > 1:
        try:
            p2 = Image.open(SAMPLE_PHOTOS[1]).convert("RGB").resize((aw, ah))
            im.paste(p2, (rx + 20 + (mw - aw) // 2, ay))
        except Exception:
            pass

    draw.rectangle([rx + 20 + (mw - aw) // 2, ay, rx + 20 + (mw - aw) // 2 + aw, ay + ah], outline=(158, 152, 140), width=1)

    # Callout list for double mat
    oy2 = my + mh + 16
    specs_right = [
        ("• Outer Mat Board:", "Deep Forest Pine, Burgundy, Terracotta, or Slate"),
        ("• Outer 45° Bevel Cut:", "Transitions smoothly down to the inner mat reveal"),
        ("• Inner Accent Reveal Strip:", "1/4\" archival warm cotton-rag contrast reveal"),
        ("• Inner 45° Bevel Cut:", "Second chamfered cut framing the artwork surface"),
    ]
    for title, desc in specs_right:
        draw.text((rx + 20, oy2), title, fill=EMERALD_LIGHT, font=FONT_TINY)
        draw.text((rx + 20, oy2 + 16), desc, fill=TEXT_WHITE, font=FONT_TINY)
        oy2 += 36

    return im


def main():
    generators = [
        ("step1_create_collection.png", gen_step1),
        ("step2_name_collection.png", gen_step2),
        ("step3_add_from_grid.png", gen_step3),
        ("step4_add_from_lightbox.png", gen_step4),
        ("step5_tv_crop_modal.png", gen_step5),
        ("step6_finder_icloud_tv.png", gen_step6),
        ("step7_lightroom_edit.png", gen_step7),
        ("step8_lightroom_sync.png", gen_step8),
        ("step9_ingest_auto_detect.png", gen_step9),
        ("step10_tv_displays.png", gen_step10),
        ("step11_single_vs_double_mat.png", gen_step11),
    ]

    for filename, fn in generators:
        im = fn()
        pub_path = PUBLIC_GUIDE_DIR / filename
        dist_path = DIST_GUIDE_DIR / filename
        im.save(pub_path, "PNG", quality=95)
        im.save(dist_path, "PNG", quality=95)
        print(f"Generated {filename}: {im.size} -> {pub_path}")


if __name__ == "__main__":
    main()
