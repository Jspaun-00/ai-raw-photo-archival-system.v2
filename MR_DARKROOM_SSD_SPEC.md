# MR Darkroom Studio — Portable SSD & 1-Click Mac Installer Specification

## Overview
This package (`MR_Darkroom_Studio`) is a self-contained, zero-dependency distribution of **MR Darkroom Studio (v4.4.0)**. It is designed to operate in two modes from the 2TB external drive (`/Volumes/2TB_Archive/MR_Darkroom_Studio`):

1. **Mode A — Run Directly From the 2TB SSD (`⚡ 1. Run MR Darkroom (From SSD).command`)**
   - Runs the MR Darkroom engine, SQLite catalog (`photo_archive.db`), 768-D OpenCLIP vector index (`vectors.npy`), rendered WebP preview cache (`previews/`), and offline AI models (`OpenCLIP ViT-L-14` + `Ollama qwen2.5vl:7b`) directly from the external SSD.
   - Zero manual setup, zero terminal typing, and no developer tools (VS Code, Git, Homebrew, or npm) required.

2. **Mode B — Install Permanently to Mac Hard Drive (`📥 2. Install MR Darkroom to Mac Hard Drive.command`)**
   - Copies the entire MR Darkroom Engine, Python runtime, ExifTool, Ollama binary, offline AI model weights (`OpenCLIP` + `qwen2.5vl:7b`), and Data Vault onto the Mac's internal SSD (`~/Library/Application Support/MRDarkroom`).
   - Builds and installs the native macOS application bundle at `/Applications/MR Darkroom.app` and places a shortcut at `~/Desktop/MR Darkroom.app`.
   - Registers the background LaunchAgent (`~/Library/LaunchAgents/com.mrdarkroom.studio.plist`) so MR Darkroom runs automatically like any native macOS app, even after the 2TB SSD is ejected.

---

## Package Directory Layout
```text
/Volumes/2TB_Archive/MR_Darkroom_Studio/
├── ⚡ 1. Run MR Darkroom (From SSD).command
├── 📥 2. Install MR Darkroom to Mac Hard Drive.command
├── MR_DARKROOM_SSD_SPEC.md
├── Engine/
│   ├── server.py
│   ├── config_paths.py
│   ├── stage1_ingest.py / stage2_vlm.py / stage3_index.py / ...
│   ├── bin/
│   │   ├── exiftool              # Self-contained Perl ExifTool binary + lib/
│   │   └── ollama                # Self-contained macOS universal Ollama binary
│   ├── scripts/
│   │   └── build_macos_app.py    # Native macOS .app bundle + LaunchAgent builder
│   └── ui/
│       └── dist/                 # Pre-compiled production React/Vite studio UI
├── Runtime/
│   └── venv_arm64.tar.gz         # Self-contained Apple Silicon Python virtual environment
└── Data_Vault/
    ├── photo_archive.db          # Master SQLite database (WAL-checkpointed)
    ├── vectors.npy               # 768-D OpenCLIP image embeddings
    ├── crop_vectors.npy          # Sub-region crop embeddings
    ├── previews/                 # Instant high-res WebP preview hierarchy
    └── models/
        ├── huggingface/          # Offline OpenCLIP ViT-L-14 weights (1.6 GB)
        └── ollama/               # Offline Ollama qwen2.5vl:7b VLM weights (6.0 GB)
```

---

## Dynamic Path Resolution (`config_paths.py`)
`Engine/config_paths.py` contains zero hardcoded user paths. It dynamically locates the active `Data_Vault` in the following priority order:
1. `MRDARKROOM_VAULT_DIR` environment variable (set automatically by `⚡ 1. Run MR Darkroom (From SSD).command`).
2. Sibling `../Data_Vault` directory alongside `Engine/` (Portable SSD layout).
3. Local `./Data_Vault` directory inside the project folder.
4. `~/Library/Application Support/MRDarkroom` (Installed Mac Hard Drive layout).

In addition, `config_paths.py` automatically configures:
- `HF_HOME` → `<DATA_VAULT_DIR>/models/huggingface`
- `OLLAMA_MODELS` → `<DATA_VAULT_DIR>/models/ollama`
- `PATH` → prepends `<ENGINE_DIR>/bin` so bundled `exiftool` and `ollama` are always found first.
