# 📸 MR Darkroom (v3.2)
### Professional AI-Powered Archival, Semantic Search & Book Curation Studio

[![macOS](https://img.shields.io/badge/Platform-macOS%2013%2B%20(Apple%20Silicon)-000000?style=for-the-badge&logo=apple&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Uvicorn-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20TailwindCSS-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![OpenCLIP](https://img.shields.io/badge/Vision%20Embedding-OpenCLIP%20ViT--L%2F14-FF6F00?style=for-the-badge)](https://github.com/mlfoundations/open_clip)
[![Ollama](https://img.shields.io/badge/VLM%20Reasoning-Qwen2.5--VL%207B%20(Ollama)-8A2BE2?style=for-the-badge)](https://ollama.com)
[![SQLite](https://img.shields.io/badge/Storage-SQLite%20WAL%20Data%20Vault-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![Privacy](https://img.shields.io/badge/Privacy-100%25%20Offline%20%2F%20Zero%20Cloud-22c55e?style=for-the-badge)](#)

---

## 🌟 Executive Overview

**MR Darkroom** is a production-grade, 100% offline, privacy-first photo archival and AI curation studio built specifically for fine-art landscape photographers, large-format printmakers, and archival estates managing massive photographic vaults (100,000+ images across Phase One `.IIQ`, Hasselblad `.3FR`, Nikon `.NEF`, Canon `.CR2`/`.CR3`, Sony `.ARW`, Fujifilm `.RAF`, Leica `.DNG`, Apple `.HEIC`, and archival TIFFs/JPEGs).

Traditional photo organizers either lock photographer metadata into proprietary cloud silos, require recurring SaaS fees, or rely on naive keyword matching that fails on fine-art landscapes and multi-subject scenes. **MR Darkroom** delivers a zero-cloud, hardware-accelerated local engine running natively on Apple Silicon (M1/M2/M3/M4) that unifies **sub-millisecond OpenCLIP vector search**, **high-tension spatial Vision-Language reasoning**, **natural voice/text AI teaching**, **strict location provenance**, and **multi-level atomic undo** into an ergonomic 60 FPS studio interface.

---

## 🖥️ Studio Showcase

<p align="center">
  <img src="docs/screenshots/01-studio-grid-workspace.png" width="100%" alt="MR Darkroom Studio Grid Workspace" />
</p>
<p align="center"><em>Figure 1: Main Studio Workspace — 16-inch MacBook Pro optimized 2-row Top Ribbon, Unified Catalog Selector Pill (Keepers 866), dynamic shoot dates, Curated Portfolio Quick-Pills, and high-DPI virtualized gallery grid.</em></p>

<p align="center">
  <img src="docs/screenshots/02-lightbox-inspector.png" width="100%" alt="MR Darkroom Lightbox Inspector Sidebar" />
</p>
<p align="center"><em>Figure 2: Lightbox Inspector Sidebar — High-resolution color-accurate photo canvas, verified GPS coordinates with offline reverse geocoding, verified camera EXIF telemetry, AI confidence gates, and instant sidecar sync.</em></p>

<p align="center">
  <img src="docs/screenshots/03-voice-teach-scout.png" width="100%" alt="MR Darkroom Voice Teach and Scout AI Modal" />
</p>
<p align="center"><em>Figure 3: Voice/Text Teach & Scout AI — Frictionless natural language teaching modal featuring blank-input auto-focus, real-time tag extraction, one-click (×) pre-commit pruning, and instant Enter-key application.</em></p>

<p align="center">
  <img src="docs/screenshots/04-unified-import-modal.png" width="100%" alt="MR Darkroom Unified Catalog and Import Modal" />
</p>
<p align="center"><em>Figure 4: Unified Catalog & Ingestion Modal — Native macOS folder browsing, automatic subfolder recursion, format pre-flight scanning (.RAF, .HEIC, .RAW, .JPG), and live background pipeline ingestion.</em></p>

---

## 🏗️ Technical Architecture

MR Darkroom operates as an asynchronous, multi-process studio architecture decoupled into a high-performance **FastAPI backend** and an ultra-responsive **React 18 + TailwindCSS frontend**:

```
+--------------------------------------------------------------------------------------------------+
|                                    MR DARKROOM STUDIO DESKTOP                                    |
|                                (React 18 + TailwindCSS + Vite)                                   |
|   - Unified 2-Row Top Ribbon                - Selection Action Dock (Bulk AI / Undo)             |
|   - High-DPI Virtualized Photo Grid         - Lightbox Inspector with Provenance Telemetry       |
|   - Interactive Leaflet Trips Map           - Voice/Text "Teach AI" & "Scout AI" Modal           |
+-------------------------------------------------+------------------------------------------------+
                                                  | HTTP / JSON + SSE Stream (Port 8501)
                                                  v
+-------------------------------------------------+------------------------------------------------+
|                                     FASTAPI SERVER (server.py)                                   |
|   - Asynchronous Job Manager (Cancel / Pause)   - Studio Jobs Multi-Step Atomic Undo             |
|   - Catalog Filter & Multi-Tenant Isolation     - Native macOS Folder Picker & Ingest Runners    |
+-------------------+-----------------------------+--------------------------+---------------------+
                    |                             |                          |
                    v                             v                          v
+-------------------+---------+   +---------------+----------+   +-----------+---------------------+
|        STAGE 1 ENGINE       |   |       STAGE 2 VLM        |   |         DATA VAULT              |
|      (stage1_engine.py)     |   |     (stage2_vlm.py)      |   | (~/Library/Application Support) |
| - ExifTool Preview Harvest  |   | - High-Tension Probes    |   |                                 |
| - OpenCLIP ViT-L/14 (MPS)   |   | - Multi-Crop Grounding   |   | - photo_archive.db (SQLite WAL) |
| - Offline KD-Tree Geocoder  |   | - Contrastive Habitat    |   | - stage1_embeddings.npy (768-d) |
| - Perceptual pHash Index    |   | - Ollama Qwen2.5-VL 7B   |   | - undo_snapshots.db             |
+-----------------------------+   +--------------------------+   +---------------------------------+
```

---

## ⚡ Core Innovations & Capabilities

### 1. Dual-Stage Vision Intelligence Pipeline
- **Stage 1 (Sub-Millisecond Vector Embedding):**
  - Extracts embedded full-resolution preview JPEGs directly from proprietary RAW formats in milliseconds via ExifTool without decoding multi-hundred-megabyte raw sensor bayer arrays.
  - Computes normalized 768-dimensional visual semantic vectors using Apple Silicon Metal-accelerated (`mps`) OpenCLIP ViT-L/14.
  - Generates 64-bit perceptual hashes (`pHash`) to cluster duplicate shots, bracketed exposures, and rapid burst sequences.
  - Generates and memory-maps persistent vector matrices (`stage1_embeddings.npy`) allowing 100,000+ photos to be cosine-ranked in under 12 milliseconds.
- **Stage 2 (High-Tension Spatial VLM & Contrastive Habitat Gating):**
  - Employs local Vision-Language Models (Ollama Qwen2.5-VL 7B / local multimodal backends) using structured visual grounding.
  - **Contrastive Habitat Gating:** Evaluates negative spatial probes and environmental foils to prevent "habitat bias" (e.g., stops dense forest paths from triggering false `Bird` tags, prevents wet river stones from hallucinating `Frog`, and halts distant silhouettes or statues from being labeled as live people).
  - **Multi-Crop Subject Routing:** Analyzes central subjects, golden-ratio thirds, and foreground/background layers independently so indoor foreground subjects (dogs, cats, furniture) are never drowned out by background walls.

### 2. Natural Voice & Text "Teach AI" and "Scout AI"
- **Teach AI Mode:**
  - Photographers can speak or type conversational instructions to re-anchor their archive: *"These shots are from our 2018 Iceland expedition around Kirkjufell at dusk; remove any Cuba tags."*
  - Automatically isolates positive concept anchors (`Iceland`, `Kirkjufell`, `Dusk`, `Sunset`), purges contradictory or incorrect tags, and marks them with ground-truth human provenance (`user_taught`).
  - **Pre-Commit Interactive Review:** Always opens with a 100% clean, blank input box. Real-time parsed tags appear with individual cross-out (`×`) chips, enabling instant visual pruning before committing with a single press of the `Enter` key.
- **Scout AI Mode:**
  - Zero-shot visual semantic search across the entire archival vault. Enter natural queries like *"solitary tree in golden morning mist"* or *"winding coastal highway with breaking waves"* to instantly surface matching images even if they have never been tagged with those exact keywords.

### 3. Strict Location Provenance ("Blank by Default")
- Prevents the chronic AI issue of hallucinating geographical locations based on generic scenery.
- A photo of a mountain is tagged `Mountain`, `Ridge`, and `Conifers`—it is **never** assigned `Switzerland`, `Colorado`, or `Patagonia` unless confirmed by:
  1. Valid hardware GPS coordinates in the EXIF block.
  2. Verified IPTC Country/State/City metadata from camera or original sidecar.
  3. Direct human teaching via the Teach AI interface.
- **Offline Reverse Geocoding:** Automatically resolves latitude and longitude against a local spatial KD-tree (comprising all cities over 1,000 population worldwide) in sub-millisecond time with **zero network requests and zero third-party API exposure**.

### 4. Enterprise-Grade Catalog Isolation & Data Vault
- **Strict Catalog Boundaries:** Master archival collections (`Keepers (866)`) remain strictly isolated from personal phone imports, test folders, or secondary catalogs (`Austin 2024 - 2025`). Ingestion routines never leak photos across catalog boundaries.
- **External Application Support Data Vault:**
  - System databases and embedding matrices are stored outside the Git repository in macOS standard application storage: `~/Library/Application Support/MRDarkroom/`.
  - Ensures repository operations, branches, and commits never risk database locking or multi-gigabyte binary bloat.

### 5. Multi-Step Atomic Undo
- Every visual operation—bulk tagging, tag clearing, single-photo inspection edits, Teach AI updates, and category reassignments—records atomic rollback snapshots in `undo_snapshots.db`.
- Hit `Cmd+Z` at any time to instantly restore previous tags, confidence scores, and provenance states.

---

## ⌨️ Studio Keyboard Shortcuts

| Shortcut | Context | Action |
|:---|:---|:---|
| <kbd>Cmd</kbd> + <kbd>Z</kbd> | Global | Multi-Step Atomic Undo (Rollback previous AI/tag action) |
| <kbd>Cmd</kbd> + <kbd>A</kbd> | Gallery Grid | Select all visible photos |
| <kbd>Esc</kbd> | Global | Deselect all photos / Close active modal or Lightbox |
| <kbd>Space</kbd> | Gallery Grid | Open highlighted photo in Lightbox Inspector |
| <kbd>→</kbd> / <kbd>←</kbd> | Lightbox | Step to next / previous photo in sequence |
| <kbd>Enter</kbd> | Modals | Commit Teach AI / Scout AI / Search query |
| <kbd>T</kbd> | Selection Active | Open Voice/Text Teach AI modal for selected photos |
| <kbd>S</kbd> | Global | Open Scout AI semantic visual finder |

---

## 🚀 Installation & Quickstart

### Prerequisites
- **Operating System:** macOS 13.0 (Ventura) or newer.
- **Hardware:** Apple Silicon (M1, M2, M3, M4) recommended for native Metal (`mps`) acceleration.
- **External Tools:** `exiftool` (`brew install exiftool`), `ollama` (`brew install ollama`, optional for local Stage 2 VLM).

---

### Option A: 1-Click macOS Studio Installer (Recommended)
Double-click `install_mr_darkroom.command` in the root folder, or execute:
```bash
./install_mr_darkroom.command
```
This automatically:
1. Initializes `~/Library/Application Support/MRDarkroom` (Data Vault).
2. Sets up Python virtual environment dependencies and verifies standalone Node/Vite build tools.
3. Builds and installs **MR Darkroom.app** with retina application icons directly onto your Desktop and `/Applications`.
4. Registers an optional macOS user `LaunchAgent` to serve the local darkroom engine automatically on login.

---

### Option B: Manual Developer Quickstart

#### 1. Clone the Repository
```bash
git clone https://github.com/Jspaun-00/ai-raw-photo-archival-system.v2.git
cd ai-raw-photo-archival-system.v2
```

#### 2. Configure Python Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Build UI Production Assets
```bash
cd ui
npm install
npm run build
cd ..
```

#### 4. Launch the Studio Server
```bash
python server.py --port 8501
```
Open your browser to `http://localhost:8501` to start curating.

---

## 📁 Repository Structure

```
ai-raw-photo-archival-system/
├── server.py                  # High-performance FastAPI studio server & REST endpoints
├── stage1_engine.py           # Stage 1 vector harvester, OpenCLIP ViT-L/14 & offline geocoder
├── stage2_vlm.py              # Stage 2 High-Tension spatial VLM & contrastive gating engine
├── domain_gazetteer.py        # Curated landscape ontology, spatial probes, and stopword gazetteer
├── studio_jobs_undo.py        # Background task orchestrator and atomic multi-step undo engine
├── config_paths.py            # macOS Data Vault (~/Library/Application Support/MRDarkroom) config
├── db_schema.py               # SQLite WAL table definitions and automatic migration utilities
├── harvester.py               # RAW metadata harvest, file stem parsing, and catalog binding
├── xmp_sync.py                # Bidirectional non-destructive Adobe/Lightroom XMP sidecar engine
├── install_mr_darkroom.command# 1-Click macOS Studio Installer & LaunchAgent registration script
├── scripts/
│   ├── build_macos_app.py     # Standalone MR Darkroom.app bundler & custom ICNS icon generator
│   └── capture_screenshots.js # Headless automated high-DPI studio screenshot capture script
├── docs/
│   └── screenshots/           # High-resolution retina studio screenshots (Figures 1-4)
├── ui/                        # React 18 + TailwindCSS Studio Application
│   ├── src/
│   │   ├── App.jsx            # Main studio application state and keyboard shortcut bus
│   │   ├── components/
│   │   │   ├── TopRibbon.jsx            # 16-inch consolidated 2-row navigation & catalog pill
│   │   │   ├── PhotoGrid.jsx            # Virtualized high-performance photo tile gallery
│   │   │   ├── SelectionActionBar.jsx   # Centered single-line floating action & bulk AI dock
│   │   │   ├── LightboxModal.jsx        # Full-screen inspection canvas & metadata sidebar
│   │   │   ├── VoiceTeachScoutModal.jsx # Blank-input Teach & Scout pre-commit review modal
│   │   │   ├── PipelineModal.jsx        # Unified folder browser, pre-flight scanner & importer
│   │   │   └── TripsMapView.jsx         # Interactive geospatial Leaflet mapping view
│   ├── dist/                  # Pre-compiled static production UI bundle
│   └── package.json
└── README.md                  # Executive studio documentation & architectural manual
```

---

## 🔒 Privacy & Data Sovereignty

- **Zero Cloud Reliance:** All neural network weights, vector index calculations, spatial geocoding lookups, and metadata updates run 100% on local silicon.
- **Non-Destructive File Operations:** Master RAW files remain untouched on storage. All generated tags, IPTC rights, and ratings are written either to internal SQLite tables or companion `.xmp` sidecar files compatible with Adobe Lightroom Classic, Capture One, and Apple Photos.
- **Air-Gapped Capable:** Fully functional without an active internet connection.

---

## 📄 License & Attribution

Designed and engineered for fine-art archival preservation. Distributed under the MIT License. See [LICENSE](LICENSE) for details.
