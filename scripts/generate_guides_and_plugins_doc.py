#!/usr/bin/env python3
"""
Generates the comprehensive 'Guides and Plugins Overview.pdf' and 'Guides and Plugins Overview.html'
for the Mitch Rouse Darkroom 2TB Archival Hard Drive.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PAGE_W = 2480  # A4 at 300 DPI
PAGE_H = 3508

FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if not os.path.exists(FONT_BOLD):
    FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"

FONT_REG = "/System/Library/Fonts/Supplemental/Arial.ttf"
if not os.path.exists(FONT_REG):
    FONT_REG = FONT_BOLD


def get_font(size: int, bold: bool = False):
    fpath = FONT_BOLD if bold else FONT_REG
    try:
        return ImageFont.truetype(fpath, size)
    except Exception:
        return ImageFont.load_default()


def draw_rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def render_page_header(draw: ImageDraw.ImageDraw, title: str, subtitle: str, page_num: int, total_pages: int):
    # Header bar
    draw.rectangle([0, 0, PAGE_W, 260], fill=(15, 23, 42))  # slate-900
    draw.rectangle([0, 252, PAGE_W, 260], fill=(245, 158, 11))  # amber-500

    draw.text((120, 65), "MITCH ROUSE DARKROOM  •  2TB ARCHIVE STUDIO", font=get_font(36, bold=True), fill=(245, 158, 11))
    draw.text((120, 125), title, font=get_font(68, bold=True), fill=(255, 255, 255))
    draw.text((120, 195), subtitle, font=get_font(34, bold=False), fill=(148, 163, 184))

    # Page number
    page_str = f"Page {page_num} of {total_pages}"
    draw.text((PAGE_W - 120 - 240, 140), page_str, font=get_font(36, bold=True), fill=(148, 163, 184))

    # Footer
    draw.rectangle([0, PAGE_H - 120, PAGE_W, PAGE_H], fill=(248, 250, 252))
    draw.line([120, PAGE_H - 120, PAGE_W - 120, PAGE_H - 120], fill=(226, 232, 240), width=3)
    draw.text((120, PAGE_H - 85), "Mitch Rouse Fine-Art Photography  |  Archival Studio & Curation System v4.5.0", font=get_font(28, bold=False), fill=(100, 116, 139))
    draw.text((PAGE_W - 550, PAGE_H - 85), "Confidential & Field Operations Guide", font=get_font(28, bold=False), fill=(148, 163, 184))


def create_page_1():
    img = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    render_page_header(draw, "Guides & Plugins Master Operations Manual", "Complete Overview of Adobe Lightroom Classic Ingest, Plugins & Studio Curation", 1, 3)

    y = 320

    # Executive Overview Card
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 420], radius=24, fill=(248, 250, 252), outline=(226, 232, 240), width=4)
    draw.rectangle([120, y, 140, y + 420], fill=(245, 158, 11))
    draw.text((170, y + 40), "SYSTEM ARCHITECTURE & PURPOSE", font=get_font(42, bold=True), fill=(15, 23, 42))
    
    body_text_1 = (
        "The Mitch Rouse Darkroom 2TB Archival System is engineered for rapid, uncompromising field photography.\n"
        "It decouples fast, temporary shoot ingestion from your permanent master photo archives, ensuring only\n"
        "your finest 5-Star (★★★★★) Keeper photos are transferred into the 2TB SSD master portfolio catalogs.\n\n"
        "This dedicated folder contains all field guides, interactive step-by-step walkthroughs, Lightroom plugins,\n"
        "and 1-click macOS application launchers required for complete studio and field operations."
    )
    draw.text((170, y + 110), body_text_1, font=get_font(34, bold=False), fill=(51, 65, 85), spacing=18)

    y += 480

    # 4-Step Pipeline Flow Diagram
    draw.text((120, y), "FIELD WORKFLOW PIPELINE (4 STAGES)", font=get_font(44, bold=True), fill=(15, 23, 42))
    y += 70

    stages = [
        ("STAGE 1: TRIP INGEST", "Fast Shoot Ingestion", "Camera SD card -> Temp Trip Catalog on laptop. Ingest via 'Copy as DNG'. Rate & cull shoot bursts quickly.", (37, 99, 235)),
        ("STAGE 2: STAR KEEPERS", "5-Star Rating Culling", "Press '5' key in Lightroom Classic on your standout images. Star all aerial, landscape, and project keepers.", (217, 119, 6)),
        ("STAGE 3: 1-CLICK TRANSFER", "Lightroom Keeper Plugin", "Library > Plug-in Extras > 'Send 5★ Keepers'. Automatically exports full-res DNGs to 2TB Archive.", (5, 150, 105)),
        ("STAGE 4: STUDIO CURATION", "MR Darkroom AI Studio", "Click '🔄 Sync Catalog' in MR Darkroom. Instant WebP previews, OpenCLIP visual search, aesthetic scoring.", (124, 58, 237)),
    ]

    card_h = 240
    for idx, (title, subtitle, desc, color) in enumerate(stages):
        box = [120, y, PAGE_W - 120, y + card_h]
        draw_rounded_rect(draw, box, radius=20, fill=(255, 255, 255), outline=color, width=4)
        draw.rectangle([120, y, 140, y + card_h], fill=color)

        # Stage badge
        draw_rounded_rect(draw, [170, y + 30, 480, y + 85], radius=12, fill=color)
        draw.text((185, y + 38), f"STEP {idx+1}", font=get_font(32, bold=True), fill=(255, 255, 255))
        draw.text((505, y + 35), title, font=get_font(40, bold=True), fill=(15, 23, 42))
        draw.text((170, y + 105), subtitle, font=get_font(34, bold=True), fill=color)
        draw.text((170, y + 155), desc, font=get_font(32, bold=False), fill=(71, 85, 105))

        y += card_h + 35

    y += 20

    # Master Catalogs Box
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 540], radius=24, fill=(241, 245, 249), outline=(203, 213, 225), width=3)
    draw.text((160, y + 40), "MASTER CATALOGS ON THIS 2TB HARD DRIVE", font=get_font(40, bold=True), fill=(15, 23, 42))

    catalogs = [
        ("• Landscape Keepers", "Master archival catalog for all fine-art landscape, earth, and desert photography."),
        ("• Aerial Keepers", "Master archival catalog for all helicopter, fixed-wing, and high-altitude fine-art aerials."),
        ("• Family Catalog", "Personal and family archival collection with private portrait metadata tags."),
        ("• Aerial Catalog", "Working master catalog for all aerial photo assets, flights, and survey archives."),
        ("• 23 prints", "Curated master portfolio of limited-edition museum-grade gallery and exhibition prints."),
    ]
    cy = y + 110
    for name, desc in catalogs:
        draw.text((160, cy), name, font=get_font(34, bold=True), fill=(30, 41, 59))
        draw.text((550, cy), desc, font=get_font(32, bold=False), fill=(71, 85, 105))
        cy += 78

    return img


def create_page_2():
    img = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    render_page_header(draw, "Lightroom Classic Keepers Transfer Plugin", "1-Click Installation, Plugin Extra Menu & Autonomous DNG Export", 2, 3)

    y = 320

    # Plugin Overview Card
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 420], radius=24, fill=(236, 253, 245), outline=(16, 185, 129), width=4)
    draw.text((170, y + 40), "PLUGIN OVERVIEW: MRKeepersTransfer.lrplugin", font=get_font(42, bold=True), fill=(6, 95, 70))
    
    p_desc = (
        "The MR Keepers Transfer Plugin is a custom-engineered Adobe Lightroom Classic export and cataloging\n"
        "extension. It eliminates the manual headache of exporting TIFFs/DNGs to Finder, opening a different\n"
        "Lightroom catalog, running Import, and pointing to folders.\n\n"
        "Instead, with two clicks directly inside your working trip catalog, the plugin scans all 5-Star rated\n"
        "photos, copies full-resolution uncompressed DNGs into your chosen 2TB Archive Keeper folder, preserves\n"
        "all develop adjustments (crop, color, tone curves), and updates the master catalog."
    )
    draw.text((170, y + 110), p_desc, font=get_font(34, bold=False), fill=(6, 78, 59), spacing=18)

    y += 480

    # Installation Box
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 540], radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=4)
    draw.rectangle([120, y, 140, y + 540], fill=(245, 158, 11))
    draw.text((170, y + 40), "1-CLICK INSTALLATION (NATIVE MACOS ICON APP)", font=get_font(42, bold=True), fill=(15, 23, 42))

    install_steps = [
        "1. Open the 'Guides and Plugins' folder on your 2TB Hard Drive in macOS Finder.",
        "2. Locate the 'Install Keepers Plugin.app' application (with the custom camera aperture icon).",
        "3. Double-click 'Install Keepers Plugin.app'. A native macOS confirmation dialog will appear.",
        "4. Click 'Install Plugin'. The app automatically places MRKeepersTransfer.lrplugin into:",
        "   ~/Library/Application Support/Adobe/Lightroom/Modules/MRKeepersTransfer.lrplugin",
        "5. A green checkmark dialog will confirm: '✅ MR Keepers Transfer Plugin is installed!'.",
        "6. Launch or restart Adobe Lightroom Classic. The plugin is now permanently loaded."
    ]
    iy = y + 110
    for step in install_steps:
        color = (30, 41, 59) if not step.startswith("   ") else (217, 119, 6)
        bold = step.startswith("1.") or step.startswith("2.") or step.startswith("3.") or step.startswith("4.") or step.startswith("5.") or step.startswith("6.")
        draw.text((170, iy), step, font=get_font(32, bold=bold), fill=color)
        iy += 58

    y += 600

    # How to Run in Lightroom
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 840], radius=24, fill=(248, 250, 252), outline=(59, 130, 246), width=4)
    draw.rectangle([120, y, 140, y + 840], fill=(59, 130, 246))
    draw.text((170, y + 40), "HOW TO USE THE PLUGIN IN LIGHTROOM CLASSIC", font=get_font(42, bold=True), fill=(30, 58, 138))

    usage_steps = [
        ("Step 1: Cull & Star Photos", "In your working trip catalog, select your favorite images and press the '5' key on your keyboard to assign a 5-Star (★★★★★) rating."),
        ("Step 2: Open Plug-in Extras", "In the top macOS menu bar, navigate to:  Library  >  Plug-in Extras  >  'Send 5★ Keepers to Destination Catalog...'"),
        ("Step 3: Select Destination", "In the plugin dialog, choose your target 2TB master catalog:\n• Landscape Keepers\n• Aerial Keepers\n• Family Catalog\n• 23 prints"),
        ("Step 4: Execute Transfer", "Click the green 'Transfer Keepers (DNG)' button. The plugin exports full-res DNGs with develop edits into your 2TB master folder."),
        ("Step 5: Studio AI Sync", "Open MR Darkroom Studio and click '🔄 Sync Catalog'. Your new keepers will appear instantly with high-speed WebP previews and AI aesthetic scores.")
    ]

    uy = y + 115
    for title, desc in usage_steps:
        draw.text((170, uy), title, font=get_font(34, bold=True), fill=(15, 23, 42))
        draw.text((170, uy + 45), desc, font=get_font(30, bold=False), fill=(71, 85, 105), spacing=10)
        uy += 135

    return img


def create_page_3():
    img = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    render_page_header(draw, "Studio Launchers & Operations Field Guide", "Native macOS Icon Launchers, 13-Page Visual Guide & Remote Support", 3, 3)

    y = 320

    # Native Icon Launchers Card
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 540], radius=24, fill=(255, 255, 255), outline=(245, 158, 11), width=4)
    draw.rectangle([120, y, 140, y + 540], fill=(245, 158, 11))
    draw.text((170, y + 40), "NATIVE MACOS APPLICATION LAUNCHERS (ALL ARE ICONS)", font=get_font(42, bold=True), fill=(15, 23, 42))

    launchers = [
        ("⚡ MR Darkroom.app (Root of 2TB Drive)", "1-Click Studio Launcher with Custom Golden Aperture Icon.\nDouble-click directly from the root of the 2TB drive. Starts the offline AI engine and launches the dedicated studio window instantly. No Terminal windows or developer tools required."),
        ("📥 Install MR Darkroom to Mac.app (Inside MR_Darkroom_Studio/)", "1-Click Mac Hard Drive Installer.\nInstalls the full MR Darkroom Studio into /Applications and your Desktop. Enables running the curation studio and offline AI models without the 2TB hard drive attached."),
        ("📥 Install Keepers Plugin.app (Inside Guides and Plugins/)", "1-Click Lightroom Plugin Installer.\nAutomatically installs and configures MRKeepersTransfer.lrplugin into Adobe Lightroom Classic Modules with zero command line scripts.")
    ]

    ly = y + 110
    for name, desc in launchers:
        draw.text((170, ly), name, font=get_font(34, bold=True), fill=(217, 119, 6))
        draw.text((170, ly + 45), desc, font=get_font(30, bold=False), fill=(51, 65, 85), spacing=10)
        ly += 135

    y += 600

    # 13-Page Illustrated Field Guide Reference
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 460], radius=24, fill=(248, 250, 252), outline=(226, 232, 240), width=4)
    draw.rectangle([120, y, 140, y + 460], fill=(37, 99, 235))
    draw.text((170, y + 40), "13-PAGE VISUAL OPERATIONS MANUAL (INCLUDED)", font=get_font(42, bold=True), fill=(15, 23, 42))

    g_desc = (
        "Located in this folder is 'MR_Darkroom_Lightroom_Field_Guide.pdf', a 13-page high-resolution visual manual\n"
        "with annotated screenshots showing every step of Lightroom ingestion:\n\n"
        "• Steps 1-4: Launching Lightroom Classic, creating trip catalogs, opening Import, choosing SD Card\n"
        "• Steps 5-6: 'Copy as DNG' vs 'Add' modes, Develop module (D key), and Crop/Straighten tools\n"
        "• Steps 7-8: 5-Star Keepers Plugin Transfer, DNG export options, and 2TB folder verification\n"
        "• Steps 9-12: Master catalog open, 'Add' mode import, and 1-click MR Darkroom Studio sync\n\n"
        "You can also open 'Interactive_Field_Guide.html' in Safari/Chrome for a responsive digital version."
    )
    draw.text((170, y + 110), g_desc, font=get_font(32, bold=False), fill=(51, 65, 85), spacing=16)

    y += 520

    # Remote Support Box
    draw_rounded_rect(draw, [120, y, PAGE_W - 120, y + 360], radius=24, fill=(241, 245, 249), outline=(148, 163, 184), width=3)
    draw.text((160, y + 35), "REMOTE HELPDESK & TECHNICAL SUPPORT", font=get_font(38, bold=True), fill=(15, 23, 42))

    support_text = (
        "• Tailscale Remote Bridge: Pre-configured for encrypted remote diagnostics and screen sharing.\n"
        "• Direct Engine Sync: In MR Darkroom Studio, use '🔄 Sync Catalog' on any catalog view.\n"
        "• Auto-Updates: Studio checks GitHub origin/main for engine and frontend updates on launch.\n"
        "• Clean Drive Storage: All AppleDouble metadata (._*) has been cleaned with dot_clean -m."
    )
    draw.text((160, y + 100), support_text, font=get_font(32, bold=False), fill=(71, 85, 105), spacing=18)

    return img


def main():
    print("Rendering Master Guides & Plugins Overview PDF (300 DPI)...")
    p1 = create_page_1()
    p2 = create_page_2()
    p3 = create_page_3()

    out_dir = Path("/tmp/guides_doc_staging")
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "Guides_and_Plugins_Overview.pdf"

    p1.save(str(pdf_path), save_all=True, append_images=[p2, p3], resolution=300.0)
    print(f"✓ Built {pdf_path} ({pdf_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
