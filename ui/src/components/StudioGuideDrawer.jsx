import React, { useState, useEffect, useRef } from 'react';
import {
  Lightbulb,
  X,
  RefreshCw,
  Cloud,
  Layers,
  Keyboard,
  Tv,
  ChevronRight,
  Sparkles,
  ArrowLeftRight,
  FolderPlus,
  Database,
  AlertTriangle,
  ZoomIn,
  Maximize2,
  Wifi,
  Palette,
} from 'lucide-react';

/**
 * StudioGuideDrawer.jsx
 *
 * Neutral-grey studio workflow guide & visual step-by-step reference.
 * - Matches MRDarkroom's neutral dark grey palette (#0F0F0F, #121212, #161616, #1C1C1C, #262626) with yellow (#F59E0B) highlights.
 * - Scalable width: draggable resize edge (380px–1200px) + 1-click Width Presets (Normal / Wide / Max) + Text & Image Scale (100% / 125% / 150%).
 * - Click any screenshot to open a full-screen zoom modal for effortless inspection.
 * - Ordered chronologically:
 *   1. Ingest & Catalog (Steps 1–4)
 *   2. Keyboard Keys (Step 5)
 *   3. Collections (Steps 6–11)
 *   4. Edit & Sync LR (Steps 12–16)
 *   5. Export & TV 12K (Steps 17–20)
 *   6. iCloud & Drives (Step 21)
 *   7. Samsung Frame TVs (Steps 22–25)
 */
const VALID_TOPICS = ['import', 'keyboard', 'collections', 'lightroom', 'exports', 'cloud', 'tv_studio'];

export default function StudioGuideDrawer({
  isOpen,
  onClose,
  position = 'right', // 'left' | 'right'
  onTogglePosition,
  initialTopic = 'import',
}) {
  const [activeTopic, setActiveTopic] = useState(() => (VALID_TOPICS.includes(initialTopic) ? initialTopic : 'import'));
  const [zoomedImage, setZoomedImage] = useState(null);
  const [drawerWidth, setDrawerWidth] = useState(() => {
    try {
      const saved = parseInt(localStorage.getItem('mrdarkroom_guide_width'), 10);
      return saved && saved >= 380 && saved <= 1200 ? saved : 600;
    } catch {
      return 600;
    }
  });
  const [scalePercent, setScalePercent] = useState(() => {
    try {
      const saved = parseInt(localStorage.getItem('mrdarkroom_guide_scale'), 10);
      return [100, 125, 150].includes(saved) ? saved : 125;
    } catch {
      return 125;
    }
  });

  const scrollContainerRef = useRef(null);
  const isResizingRef = useRef(false);

  const updateWidth = (newW) => {
    const clamped = Math.max(380, Math.min(1200, newW));
    setDrawerWidth(clamped);
    try {
      localStorage.setItem('mrdarkroom_guide_width', String(clamped));
    } catch {}
  };

  const updateScale = (newScale) => {
    setScalePercent(newScale);
    try {
      localStorage.setItem('mrdarkroom_guide_scale', String(newScale));
    } catch {}
  };

  const handleSelectTopic = (topicId) => {
    const target = VALID_TOPICS.includes(topicId) ? topicId : 'import';
    setActiveTopic(target);
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  // Sync initial topic when opening
  useEffect(() => {
    if (isOpen) {
      const target = VALID_TOPICS.includes(initialTopic) ? initialTopic : 'import';
      setActiveTopic(target);
      if (scrollContainerRef.current) {
        scrollContainerRef.current.scrollTo({ top: 0 });
      }
    }
  }, [isOpen, initialTopic]);

  // Drag-to-resize handler
  useEffect(() => {
    if (!isOpen) return;
    const handleMouseMove = (e) => {
      if (!isResizingRef.current) return;
      const maxAllowed = Math.min(1200, Math.floor(window.innerWidth * 0.82));
      if (position === 'right') {
        const newWidth = window.innerWidth - e.clientX;
        updateWidth(Math.min(maxAllowed, newWidth));
      } else {
        const newWidth = e.clientX;
        updateWidth(Math.min(maxAllowed, newWidth));
      }
    };
    const handleMouseUp = () => {
      if (isResizingRef.current) {
        isResizingRef.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isOpen, position]);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        if (zoomedImage) {
          setZoomedImage(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, zoomedImage]);

  if (!isOpen) return null;

  // Ordered chronologically from start of workflow to finish
  const topics = [
    {
      id: 'import',
      title: '1. Ingest & Catalog',
      icon: FolderPlus,
      badge: 'Steps 1-4',
    },
    {
      id: 'keyboard',
      title: '2. Keyboard Keys',
      icon: Keyboard,
      badge: 'Step 5',
    },
    {
      id: 'collections',
      title: '3. Collections',
      icon: Layers,
      badge: 'Steps 6-11',
    },
    {
      id: 'lightroom',
      title: '4. Edit & Sync LR',
      icon: RefreshCw,
      badge: 'Steps 12-16',
    },
    {
      id: 'exports',
      title: '5. Export & TV 12K',
      icon: Tv,
      badge: 'Steps 17-20',
    },
    {
      id: 'cloud',
      title: '6. iCloud & Drives',
      icon: Cloud,
      badge: 'Step 21',
    },
    {
      id: 'tv_studio',
      title: '7. Samsung Frame TVs',
      icon: Tv,
      badge: 'Steps 22-25',
    },
  ];

  // Dynamic font size multipliers based on scalePercent
  const baseTextSize =
    scalePercent >= 150 ? '16px' : scalePercent >= 125 ? '14.5px' : '13px';
  const headingTextSize =
    scalePercent >= 150 ? '18px' : scalePercent >= 125 ? '16px' : '14.5px';

  // Reusable clickable screenshot card with zoom trigger
  const GuideScreenshot = ({ src, alt, caption }) => (
    <div className="mt-2.5 space-y-1.5">
      <div
        onClick={() => setZoomedImage({ src, alt, caption })}
        className="group relative rounded-xl overflow-hidden border-2 border-[#333333] hover:border-amber-400 shadow-xl bg-[#0F0F0F] cursor-zoom-in transition-all"
        title="Click to enlarge screenshot full-screen"
      >
        <img
          src={src}
          alt={alt}
          className="w-full h-auto object-contain block"
        />
        <div className="absolute bottom-2 right-2 px-2.5 py-1 rounded-md bg-black/85 border border-amber-400/70 text-amber-300 text-[11px] font-bold flex items-center gap-1.5 shadow-lg group-hover:bg-amber-400 group-hover:text-zinc-950 transition">
          <ZoomIn className="w-3.5 h-3.5" />
          <span>Click to Enlarge</span>
        </div>
      </div>
      {caption && (
        <div className="text-xs text-amber-300 font-mono bg-[#1C1C1C] px-3 py-2 rounded-lg border border-[#333333]">
          {caption}
        </div>
      )}
    </div>
  );

  return (
    <>
      <aside
        style={{ width: `${drawerWidth}px`, maxWidth: '82vw', minWidth: '380px' }}
        className={`h-full shrink-0 bg-[#121212] shadow-2xl flex flex-col pointer-events-auto select-text text-zinc-100 z-20 overflow-hidden relative ${
          position === 'left' ? 'border-r-2 border-[#2A2A2A]' : 'border-l-2 border-[#2A2A2A]'
        }`}
      >
        {/* ========================================================================= */}
        {/* DRAGGABLE RESIZE HANDLE ON INNER EDGE                                     */}
        {/* ========================================================================= */}
        <div
          onMouseDown={(e) => {
            e.preventDefault();
            isResizingRef.current = true;
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
          }}
          title="Drag edge to make the Help Guide wider or narrower"
          className={`absolute top-0 bottom-0 w-2.5 z-30 cursor-col-resize hover:bg-amber-400/50 active:bg-amber-400 transition-colors ${
            position === 'left' ? 'right-0' : 'left-0'
          }`}
        />

        {/* ========================================================================= */}
        {/* DRAWER HEADER (Title, Dock Left/Right, Close)                             */}
        {/* ========================================================================= */}
        <div className="flex items-center justify-between px-4 py-3.5 border-b border-[#262626] bg-[#161616] shrink-0 gap-2">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-amber-400/15 border border-amber-400/50 flex items-center justify-center text-amber-300 shadow-md shrink-0">
              <Lightbulb className="w-5 h-5 text-amber-400 stroke-[2.5]" />
            </div>
            <div className="min-w-0">
              <h2 className="text-[15px] font-black text-zinc-100 tracking-wide flex items-center gap-2 truncate">
                <span className="truncate">Studio Workflow Guide</span>
                <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded bg-amber-400 text-zinc-950 uppercase tracking-wider shrink-0">
                  STEP-BY-STEP
                </span>
              </h2>
              <p className="text-xs text-zinc-400 truncate">
                Drag border or use size controls below to enlarge text &amp; screenshots
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {onTogglePosition && (
              <button
                type="button"
                onClick={onTogglePosition}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#222222] hover:bg-[#2C2C2C] text-zinc-200 hover:text-white text-xs font-bold border border-[#383838] transition cursor-pointer shrink-0 whitespace-nowrap"
                title={`Dock to ${position === 'left' ? 'Right' : 'Left'} side`}
              >
                <ArrowLeftRight className="w-3.5 h-3.5 shrink-0" />
                <span>{position === 'left' ? 'Dock Right ▶' : '◀ Dock Left'}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-[#222222] hover:bg-red-950/70 text-zinc-200 hover:text-red-200 text-xs font-bold border border-[#383838] hover:border-red-700/60 transition cursor-pointer shrink-0 whitespace-nowrap"
              title="Close Guide (Esc)"
            >
              <X className="w-4 h-4 shrink-0" />
              <span>Close</span>
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* SCALABILITY BAR: PANEL WIDTH + TEXT/IMAGE ZOOM CONTROLS                   */}
        {/* ========================================================================= */}
        <div className="px-4 py-2.5 border-b border-[#262626] bg-[#141414] flex items-center justify-between gap-2 flex-wrap shrink-0 text-xs">
          <div className="flex items-center gap-1.5">
            <Maximize2 className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-zinc-300 font-semibold">Panel Width:</span>
            {[
              { label: 'Compact', w: 480 },
              { label: 'Wide', w: 680 },
              { label: 'Extra Large', w: 920 },
            ].map((preset) => {
              const active = Math.abs(drawerWidth - preset.w) < 60;
              return (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => updateWidth(preset.w)}
                  className={`px-2.5 py-1 rounded-md font-bold transition cursor-pointer border ${
                    active
                      ? 'bg-amber-400 text-zinc-950 border-amber-300'
                      : 'bg-[#1F1F1F] hover:bg-[#2A2A2A] text-zinc-200 border-[#333333]'
                  }`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-1.5">
            <ZoomIn className="w-4 h-4 text-amber-400 shrink-0" />
            <span className="text-zinc-300 font-semibold">Text Size:</span>
            {[
              { label: '100%', s: 100 },
              { label: '125%', s: 125 },
              { label: '150%', s: 150 },
            ].map((sz) => {
              const active = scalePercent === sz.s;
              return (
                <button
                  key={sz.label}
                  type="button"
                  onClick={() => updateScale(sz.s)}
                  className={`px-2.5 py-1 rounded-md font-bold transition cursor-pointer border ${
                    active
                      ? 'bg-amber-400 text-zinc-950 border-amber-300'
                      : 'bg-[#1F1F1F] hover:bg-[#2A2A2A] text-zinc-200 border-[#333333]'
                  }`}
                >
                  {sz.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* TOPIC SELECTOR PILLS (Chronological 1 → 6 Order, Neutral Grey + Yellow)   */}
        {/* ========================================================================= */}
        <div className="p-2.5 border-b border-[#262626] bg-[#161616] grid grid-cols-2 gap-2 shrink-0">
          {topics.map((t) => {
            const isActive = activeTopic === t.id;
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => handleSelectTopic(t.id)}
                className={`flex items-center justify-between px-3 py-2.5 rounded-lg text-[13px] font-bold truncate transition cursor-pointer border ${
                  isActive
                    ? 'bg-amber-400 text-zinc-950 border-amber-300 shadow-md font-black'
                    : 'bg-[#1F1F1F] hover:bg-[#292929] text-zinc-200 hover:text-white border-[#333333]'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <Icon
                    className={`w-4 h-4 shrink-0 ${
                      isActive ? 'text-zinc-950 stroke-[2.5]' : 'text-amber-400'
                    }`}
                  />
                  <span className="truncate">{t.title}</span>
                </div>
                <span
                  className={`text-[11px] font-mono px-2 py-0.5 rounded shrink-0 ${
                    isActive
                      ? 'bg-zinc-950 text-amber-300 font-bold'
                      : 'bg-[#141414] text-zinc-400 border border-[#2C2C2C]'
                  }`}
                >
                  {t.badge}
                </span>
              </button>
            );
          })}
        </div>

        {/* ========================================================================= */}
        {/* TOPIC CONTENT (Scrollable Step-by-Step with Large Screenshots)            */}
        {/* ========================================================================= */}
        <div
          ref={scrollContainerRef}
          style={{ fontSize: baseTextSize }}
          className="flex-1 overflow-y-auto p-4 space-y-6 text-zinc-200 leading-relaxed select-text bg-[#121212]"
        >
          {/* ======================================================================= */}
          {/* TOPIC 1: CREATING A CATALOG & INGESTING (STEPS 1 - 4)                   */}
          {/* ======================================================================= */}
          {activeTopic === 'import' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Database className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>1. Creating a Catalog &amp; Ingesting (Steps 1 – 4)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Point MRDarkroom at any master shoot directory on your external RAID, DAS, or NVMe SSD. It automatically identifies your Lightroom Classic catalog and preview caches.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2 font-bold text-amber-400">
                  <Sparkles className="w-4 h-4 shrink-0" />
                  <span>Important: Select Your Master Shoot Folder (Not an SD Card)</span>
                </div>
                <p className="text-zinc-300">
                  MRDarkroom does <strong className="text-white">not</strong> run on raw camera SD cards. Instead, choose the master shoot folder on your external drive where Lightroom Classic has already imported your RAW/DNG files.
                </p>

                <GuideScreenshot
                  src="/guide/step9_ingest_auto_detect.png"
                  alt="Master Shoot Ingest and Lightroom Catalog Auto-Detection"
                  caption="👉 Select your master shoot folder — MRDarkroom auto-detects the .lrcat database and .lrdata previews automatically."
                />

                <div className="grid grid-cols-2 gap-2.5 text-xs font-mono pt-2">
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2C2C2C]">
                    <div className="text-amber-400 font-bold mb-1">1. Auto-Identifies .lrcat</div>
                    <div className="text-zinc-400">Locates your Lightroom SQLite catalog database automatically</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2C2C2C]">
                    <div className="text-amber-400 font-bold mb-1">2. Reads .lrdata Caches</div>
                    <div className="text-zinc-400">Extracts instant 1:1 previews without slow RAW re-rendering</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2C2C2C]">
                    <div className="text-amber-400 font-bold mb-1">3. Syncs Stars &amp; XMP</div>
                    <div className="text-zinc-400">Preserves Adobe star ratings, flags, crops, and color grades</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2C2C2C]">
                    <div className="text-amber-400 font-bold mb-1">4. AI Tagging &amp; GPS</div>
                    <div className="text-zinc-400">Indexes landmarks, regions, and aerial telemetry</div>
                  </div>
                </div>
              </div>

              {/* STEP 1 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    1
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ 📥 Import &amp; AI Tag ] in the Top Banner
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Click the <strong className="text-white">📥 Import &amp; AI Tag</strong> button in the top right banner (or open the catalog selector dropdown) to launch the Pipeline Ingest window.
                </p>
              </div>

              {/* STEP 2 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    2
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ Select Source Folder ] &amp; Choose Your Shoot Directory
                  </h4>
                </div>
                <p className="text-zinc-300">
                  In the macOS Finder window that opens, select your master shoot folder on your external RAID or SSD (for example, <code className="text-amber-300 font-mono">/Volumes/StudioRAID/2026_Palouse_Aerials</code>).
                </p>
              </div>

              {/* STEP 3 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    3
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Verify Automatic .lrcat Catalog Detection &amp; Name
                  </h4>
                </div>
                <p className="text-zinc-300">
                  MRDarkroom immediately scans the folder, identifies the <code className="text-amber-300 font-mono">.lrcat</code> database and <code className="text-amber-300 font-mono">.lrdata</code> preview pyramid, and pre-fills the catalog name (e.g., <code className="text-amber-300 font-mono">Palouse</code> or <code className="text-amber-300 font-mono">Ranch Gallery</code>).
                </p>
              </div>

              {/* STEP 4 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    4
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ Start Ingest ] (Yellow Action Button)
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Click the yellow <strong className="text-amber-300">Start Ingest</strong> button. Your photos, star ratings, and high-resolution previews populate the grid within seconds.
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectTopic('keyboard')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2"
                >
                  <span>Next: 2. Keyboard Keys &amp; Speed Culling (Step 5)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 2: KEYBOARD KEYS & SPEED CULLING (STEP 5)                         */}
          {/* ======================================================================= */}
          {activeTopic === 'keyboard' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Keyboard className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>2. Keyboard Keys &amp; Speed Culling (Step 5)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Navigate the grid, open full-screen Lightbox, rate photos 1–5 stars, and select ranges rapidly using standard desktop shortcuts.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-4">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    5
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click to Highlight (Yellow Frame) &amp; Use Keyboard Shortcuts
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Click any thumbnail once to highlight it with a <strong className="text-amber-300">bright yellow border</strong>. From there, use your keyboard to move through the shoot and assign star ratings:
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Spacebar or Double-Click</div>
                    <div className="text-white font-bold">Open / Close Lightbox Loupe</div>
                    <div className="text-xs text-zinc-400">Inspect the highlighted photo full-screen; press Spacebar or Esc to return to Grid.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">← / → Arrow Keys</div>
                    <div className="text-white font-bold">Step Through Photos</div>
                    <div className="text-xs text-zinc-400">Moves the yellow highlight left or right across the grid or inside Lightbox.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Keys 1, 2, 3, 4, 5</div>
                    <div className="text-white font-bold">Set Star Rating (1–5 ★)</div>
                    <div className="text-xs text-zinc-400">Immediately rates the highlighted photo (or all selected photos).</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Key 0</div>
                    <div className="text-white font-bold">Clear Star Rating</div>
                    <div className="text-xs text-zinc-400">Removes stars from the highlighted selection.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">⌘ + Click (Cmd / Ctrl)</div>
                    <div className="text-white font-bold">Select Multiple Photos</div>
                    <div className="text-xs text-zinc-400">Toggle individual photos in or out of your active selection.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Shift + Click</div>
                    <div className="text-white font-bold">Select Range of Photos</div>
                    <div className="text-xs text-zinc-400">Selects every photo between your first click and second click.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Key L</div>
                    <div className="text-white font-bold">Edit in Lightroom Classic</div>
                    <div className="text-xs text-zinc-400">Opens the highlighted photo directly inside its source .lrcat catalog in Lightroom.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">Shift + S</div>
                    <div className="text-white font-bold">Sync Lightroom Edits</div>
                    <div className="text-xs text-zinc-400">Pulls saved XMP metadata and updated previews back from Lightroom.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">⌘Z (Command + Z)</div>
                    <div className="text-white font-bold">Undo Last Rating / Action</div>
                    <div className="text-xs text-zinc-400">Restores previous star rating or batch update.</div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-[#121212] border border-[#2E2E2E] space-y-1">
                    <div className="font-mono font-black text-amber-400">⌘A (Command + A)</div>
                    <div className="text-white font-bold">Select All Loaded Photos</div>
                    <div className="text-xs text-zinc-400">Highlights all photos currently visible in the filtered view.</div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleSelectTopic('collections')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2"
                >
                  <span>Next: 3. Creating &amp; Curating Collections (Steps 6–11)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 3: COLLECTIONS (STEPS 6 - 11)                                     */}
          {/* ======================================================================= */}
          {activeTopic === 'collections' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Layers className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>3. Curated Collections &amp; TV Sets (Steps 6 – 11)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Create named collections (such as <strong className="text-amber-300">TV 1</strong>, <strong className="text-amber-300">Ranch Gallery</strong>, or <strong className="text-amber-300">Palouse</strong>), add photos from the Grid or Lightbox, and sequence them.
                </p>
              </div>

              {/* STEP 6 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    6
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ ★ Curated Collections ] in Top Ribbon
                  </h4>
                </div>
                <p className="text-zinc-300">
                  In the top banner view switcher, click <strong className="text-amber-300">★ Curated Collections</strong> to open the collections workspace.
                </p>
                <GuideScreenshot
                  src="/guide/step1_create_collection.png"
                  alt="Collections View & Large Yellow Create New Collection Button"
                  caption="👉 Click [ ★ Curated Collections ] in the top bar, then click the large yellow [ ＋ Create New Collection ] button on the left."
                />
              </div>

              {/* STEP 7 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    7
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Type a Collection Name to Unlock [ ✓ Create Collection ]
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Clicking <strong className="text-amber-300">＋ Create New Collection</strong> opens the creation dialog.
                </p>
                <div className="p-3.5 rounded-lg bg-[#121212] border-2 border-amber-400/60 space-y-1">
                  <div className="font-bold text-amber-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>IMPORTANT: YOU MUST TYPE A COLLECTION NAME FIRST</span>
                  </div>
                  <p className="text-zinc-200">
                    The <strong className="text-white">Create Collection</strong> button stays <span className="underline font-bold">locked and grey</span> while the name box is empty. As soon as you type a name (such as <code className="bg-black px-1.5 py-0.5 rounded text-amber-300">Ranch Gallery</code>, <code className="bg-black px-1.5 py-0.5 rounded text-amber-300">Palouse</code>, or <code className="bg-black px-1.5 py-0.5 rounded text-amber-300">TV 1</code>), the button lights up <strong className="text-amber-300">bright yellow</strong> so you can click it.
                  </p>
                </div>
                <GuideScreenshot
                  src="/guide/step2_name_collection.png"
                  alt="Create Collection Modal Showing Locked vs Unlocked Yellow Button"
                  caption="👉 Type a name (e.g., Ranch Gallery or Palouse) — the button turns bright yellow once a name is entered."
                />
              </div>

              {/* STEP 8 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    8
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Add Photos from Grid View (Bottom Action Bar)
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Switch to <strong className="text-white">Grid View</strong> and click any photo (or <kbd className="px-1.5 py-0.5 bg-[#262626] text-amber-300 rounded font-mono">⌘+Click</kbd> / <kbd className="px-1.5 py-0.5 bg-[#262626] text-amber-300 rounded font-mono">Shift+Click</kbd> multiple photos) so they highlight in yellow.
                </p>
                <p className="text-zinc-300">
                  In the bottom action bar, click <strong className="text-amber-300">📚 Add to Collection ▾</strong> and pick <code className="text-amber-300 font-mono">TV 1</code>, <code className="text-amber-300 font-mono">Ranch Gallery</code>, or <code className="text-amber-300 font-mono">Palouse</code>.
                </p>
                <GuideScreenshot
                  src="/guide/step3_add_from_grid.png"
                  alt="Add Selected Photos to Collection from Grid Bottom Bar"
                  caption="👉 Highlight photo(s) in the Grid, click [ 📚 Add to Collection ▾ ] at the bottom, and choose your collection."
                />
              </div>

              {/* STEP 9 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    9
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Add Photos from Full-Screen Lightbox View
                  </h4>
                </div>
                <p className="text-zinc-300">
                  While viewing a photo full-screen in Lightbox (opened with <kbd className="px-1.5 py-0.5 bg-[#262626] text-amber-300 rounded font-mono">Spacebar</kbd> or double-click), click <strong className="text-amber-300">📚 Add to Collection ▾</strong> in the top bar and choose your target collection.
                </p>
                <GuideScreenshot
                  src="/guide/step4_add_from_lightbox.png"
                  alt="Add Photo to Collection from Fullscreen Lightbox Header"
                  caption="👉 In Full-Screen Lightbox, click [ 📚 Add to Collection ▾ ] in the top bar."
                />
              </div>

              {/* STEP 10 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    10
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Drag &amp; Drop to Reorder Collection Sequence
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Inside <strong className="text-amber-300">★ Curated Collections</strong>, click a collection on the left (e.g. <code className="text-amber-300 font-mono">Ranch Gallery</code>) and drag any photo card to rearrange the display sequence. Your order saves automatically.
                </p>
              </div>

              {/* STEP 11 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    11
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Collection Name Becomes Your Export Subfolder Name
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Whatever you name your collection (<code className="text-amber-300 font-mono">TV 1</code>, <code className="text-amber-300 font-mono">Ranch Gallery</code>, <code className="text-amber-300 font-mono">Palouse</code>) is automatically used as the subfolder name inside <strong className="text-white">TV Folder</strong> when you export!
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectTopic('lightroom')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2"
                >
                  <span>Next: 4. Edit in Lightroom &amp; Live Sync (Steps 12–16)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 4: EDIT IN LIGHTROOM & SYNC (STEPS 12 - 16)                       */}
          {/* ======================================================================= */}
          {activeTopic === 'lightroom' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <RefreshCw className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>4. Edit in Lightroom Classic &amp; Sync (Steps 12 – 16)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Jump straight from any photo into Adobe Lightroom Classic, make your Develop adjustments, save metadata, and sync changes right back into MRDarkroom.
                </p>
              </div>

              {/* STEP 12 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    12
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ 🎨 Edit in Lightroom ] or Press Key [ L ]
                  </h4>
                </div>
                <p className="text-zinc-300">
                  With any photo highlighted in Grid View or open in Full-Screen Lightbox, click <strong className="text-amber-300">🎨 Edit in Lightroom</strong> in the bar, or press <kbd className="px-2 py-0.5 bg-[#262626] text-amber-300 rounded font-mono font-bold">L</kbd> on your keyboard.
                </p>
                <GuideScreenshot
                  src="/guide/step7_lightroom_edit.png"
                  alt="Edit in Lightroom Button and Key L Shortcut"
                  caption="👉 Click [ ⚡ Edit in Lightroom ] or press [ L ] — MRDarkroom auto-locates the source .lrcat catalog and opens the photo in Lightroom Classic."
                />
              </div>

              {/* STEP 13 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    13
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Adjust Exposure, Color, or Crop in Lightroom Develop
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Lightroom Classic opens directly to your selected RAW/DNG frame. Make any Develop module edits you want (Exposure, White Balance, Shadows, Tone Curve, Masking, or Crop).
                </p>
              </div>

              {/* STEP 14 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    14
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Press ⌘S (Command + S) in Lightroom &amp; Wait 30s – 2m
                  </h4>
                </div>
                <div className="p-3.5 rounded-lg bg-[#121212] border-2 border-amber-400/60 space-y-1.5">
                  <div className="font-bold text-amber-300 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>SAVE METADATA TO FILE IN LIGHTROOM (⌘S)</span>
                  </div>
                  <p className="text-zinc-200">
                    When finished editing in Lightroom, press <kbd className="px-2 py-0.5 bg-black text-amber-300 rounded font-mono font-bold">⌘S</kbd> (Command + S on Mac, or <strong>Metadata &rarr; Save Metadata to File</strong>) and allow <strong>30 seconds to 2–3 minutes</strong> for Lightroom to write the updated <code className="text-amber-300 font-mono">.xmp</code> sidecar and preview cache to disk.
                  </p>
                </div>
              </div>

              {/* STEP 15 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    15
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ 🔄 Sync Edits ] (or Press Shift + S) in MRDarkroom
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Return to MRDarkroom and click <strong className="text-amber-300">🔄 Sync Edits</strong> in the bottom bar or Lightbox top bar (or press <kbd className="px-1.5 py-0.5 bg-[#262626] text-amber-300 rounded font-mono font-bold">Shift + S</kbd>).
                </p>
                <GuideScreenshot
                  src="/guide/step8_lightroom_sync.png"
                  alt="Save Metadata in Lightroom and Click Sync Edits in MRDarkroom"
                  caption="👉 Press ⌘S in Lightroom, wait 30s–2m for disk write, then click [ 🔄 Sync Edits ] in MRDarkroom to refresh the image."
                />
              </div>

              {/* STEP 16 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    16
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Updated Grade &amp; Crop Appear Immediately
                  </h4>
                </div>
                <p className="text-zinc-300">
                  MRDarkroom re-renders the preview with your new Lightroom develop settings and updates the thumbnail and Lightbox view in place.
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectTopic('exports')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2"
                >
                  <span>Next: 5. Export &amp; 65" TV Showcase (Steps 17–20)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 5: EXPORT & 65" TV SHOWCASE (STEPS 17 - 20)                       */}
          {/* ======================================================================= */}
          {activeTopic === 'exports' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Tv className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>5. Export &amp; 65" TV Showcase 12K (Steps 17 – 20)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Frame 16:9 TV crops or custom print dimensions, then export with 1 click to Desktop, Mitch’s iCloud Drive <strong className="text-amber-300">TV Folder</strong>, or any Finder directory.
                </p>
              </div>

              {/* STEP 17 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    17
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click [ 📤 Export ] &rarr; Choose [ 📺 65" TV Showcase ] or [ 🖼️ Custom Print ]
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Inside a collection (e.g. <code className="text-amber-300 font-mono">TV 1</code>, <code className="text-amber-300 font-mono">Ranch Gallery</code>, or <code className="text-amber-300 font-mono">Palouse</code>) or with photos highlighted in Grid View, click <strong className="text-amber-300">📤 Export</strong>.
                </p>
              </div>

              {/* STEP 18 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    18
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Drag the 16:9 Crop Box Up or Down to Frame the Horizon
                  </h4>
                </div>
                <p className="text-zinc-300">
                  In the <strong className="text-white">65" TV Showcase 16:9 Crop Placement</strong> window, drag the crop window vertically to frame sky, horizon, or foreground. Every file is rendered at <strong className="text-amber-300">12,000 × 6,750 px (180 DPI, sRGB Quality 96)</strong> with embedded IPTC/XMP metadata.
                </p>
                <GuideScreenshot
                  src="/guide/step5_tv_crop_modal.png"
                  alt="65-inch TV Showcase 16:9 Crop Placement and 3 Direct Export Buttons"
                  caption="👉 Drag the 16:9 box up or down to frame your shot, then click Desktop, iCloud Drive, or Choose Folder at the bottom right."
                />
              </div>

              {/* STEP 19 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    19
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Click Your Destination Button (Named Automatically by Collection)
                  </h4>
                </div>
                <p className="text-zinc-300">
                  At the bottom right of the export modal are three direct 1-click buttons:
                </p>
                <div className="space-y-2.5">
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#333333] flex items-start gap-3">
                    <span className="text-lg">🖥️</span>
                    <div>
                      <span className="font-black text-white">1. Desktop</span>
                      <p className="text-zinc-300 text-xs mt-0.5">
                        Saves directly into <code className="text-amber-300 font-mono">~/Desktop/TV Folder/{'{Collection Name}'}/</code>
                      </p>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#121212] border-2 border-amber-400/70 flex items-start gap-3">
                    <span className="text-lg">☁️</span>
                    <div>
                      <span className="font-black text-amber-300">2. iCloud Drive (Recommended for Apple TVs)</span>
                      <p className="text-zinc-200 text-xs mt-0.5">
                        Saves directly into Mitch’s iCloud Drive under <code className="text-amber-300 font-mono">iCloud Drive / TV Folder / {'{Collection Name}'}/</code>. If your collection is <code className="text-amber-300 font-mono">TV 1</code>, it exports to <code className="text-amber-300 font-mono">TV Folder/TV 1/</code>. If your collection is <code className="text-amber-300 font-mono">Ranch Gallery</code> or <code className="text-amber-300 font-mono">Palouse</code>, it exports to <code className="text-amber-300 font-mono">TV Folder/Ranch Gallery/</code> or <code className="text-amber-300 font-mono">TV Folder/Palouse/</code>!
                      </p>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-[#121212] border border-[#333333] flex items-start gap-3">
                    <span className="text-lg">📁</span>
                    <div>
                      <span className="font-black text-white">3. Choose Folder...</span>
                      <p className="text-zinc-300 text-xs mt-0.5">
                        Opens macOS Finder so you can pick any custom folder, external drive, or <code className="text-amber-300 font-mono">Google Drive &rarr; My Drive</code>.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* STEP 20 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    20
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Verify Subfolders in macOS Finder (iCloud Drive &rarr; TV Folder)
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Open macOS Finder and click <strong className="text-white">iCloud Drive &rarr; TV Folder</strong>. Each exported collection appears in its own clean subfolder:
                </p>
                <GuideScreenshot
                  src="/guide/step6_finder_icloud_tv.png"
                  alt="macOS Finder Showing iCloud Drive TV Folder with TV 1, TV 2, Ranch Gallery, and Palouse"
                  caption="👉 iCloud Drive > TV Folder automatically organizes subfolders for TV 1, TV 2, Ranch Gallery, and Palouse."
                />
                <button
                  type="button"
                  onClick={() => handleSelectTopic('cloud')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2"
                >
                  <span>Next: 6. iCloud TV &amp; Google Drive Setup (Step 21)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 6: ICLOUD & GOOGLE DRIVE SETUP (STEP 21)                          */}
          {/* ======================================================================= */}
          {activeTopic === 'cloud' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Cloud className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>6. iCloud TV &amp; Google Drive Setup (Step 21)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  How your exported collection folders sync across Apple TV, iPad, iPhone, and Google Drive.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    21
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Automatic iCloud TV Folder Hierarchy
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Because macOS mounts iCloud Drive natively, your login is permanent. Every time you click <strong className="text-amber-300">☁️ iCloud Drive</strong> in the Export window, MRDarkroom writes 12K 16:9 JPEGs directly into:
                </p>
                <div className="p-3.5 rounded-lg bg-[#101010] font-mono text-xs text-zinc-200 space-y-1 border border-[#2E2E2E]">
                  <div className="text-amber-400 font-bold">iCloud Drive / TV Folder /</div>
                  <div className="pl-4 text-zinc-200">├── TV 1 / <span className="text-zinc-500">(Main Gallery 65" OLED)</span></div>
                  <div className="pl-4 text-zinc-200">├── TV 2 / <span className="text-zinc-500">(Living Room Display)</span></div>
                  <div className="pl-4 text-amber-300">├── Ranch Gallery / <span className="text-zinc-500">(Curated Ranch Exhibition)</span></div>
                  <div className="pl-4 text-zinc-200">└── Palouse / <span className="text-zinc-500">(Palouse Hills Collection)</span></div>
                </div>
                <p className="text-xs text-zinc-400">
                  A local mirror is also kept at <code className="text-zinc-200 font-mono">~/Desktop/TV Folder/</code> for instant desktop access.
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <h4 style={{ fontSize: headingTextSize }} className="font-bold text-amber-400">
                  Displaying Subfolders on Apple TV
                </h4>
                <ol className="list-decimal pl-5 text-zinc-300 space-y-1.5">
                  <li>On your Apple TV, open <strong className="text-white">Photos</strong> (or <strong className="text-white">Settings &rarr; General &rarr; Screensaver</strong>).</li>
                  <li>Navigate to <strong className="text-amber-300">TV Folder</strong> and pick the subfolder for that room (<strong className="text-white">TV 1</strong>, <strong className="text-white">TV 2</strong>, <strong className="text-white">Ranch Gallery</strong>, or <strong className="text-white">Palouse</strong>).</li>
                  <li>Select <strong>Start Slideshow</strong> or <strong>Set as Screensaver</strong> — every photo fills the 16:9 4K/8K screen edge-to-edge with zero black bars.</li>
                </ol>
              </div>

              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-2">
                <h4 style={{ fontSize: headingTextSize }} className="font-bold text-white flex items-center gap-2">
                  <span>📁</span>
                  <span>Mounting Google Drive in macOS Finder</span>
                </h4>
                <p className="text-zinc-300">
                  If you also use <strong className="text-white">Google Drive for Desktop</strong>, sign in once on your Mac so <code className="text-amber-300 font-mono">Google Drive</code> appears in your Finder sidebar. Then click <strong className="text-amber-300">📁 Choose Folder...</strong> during export and select any folder inside <code className="text-amber-300 font-mono">Google Drive &rarr; My Drive</code>.
                </p>
                <button
                  type="button"
                  onClick={() => handleSelectTopic('tv_studio')}
                  className="w-full py-2.5 px-4 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md border border-amber-300 flex items-center justify-center gap-2 mt-4"
                >
                  <span>Next: 7. Samsung Frame TVs — Live Art Mode &amp; Mats (Steps 22–25)</span>
                  <ChevronRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          )}

          {/* ======================================================================= */}
          {/* TOPIC 7: SAMSUNG FRAME TVS — LIVE ART MODE & MATS (STEPS 22–25)         */}
          {/* ======================================================================= */}
          {activeTopic === 'tv_studio' && (
            <div className="space-y-6">
              <div className="p-4 rounded-xl bg-[#1A1A1A] border-l-4 border-amber-400 border border-[#2E2E2E]">
                <h3
                  style={{ fontSize: headingTextSize }}
                  className="font-black text-white flex items-center gap-2"
                >
                  <Tv className="w-5 h-5 text-amber-400 shrink-0" />
                  <span>7. Samsung Frame TVs — Live Art Mode &amp; Mats (Steps 22–25)</span>
                </h3>
                <p className="text-zinc-300 mt-1">
                  Direct Wi-Fi TV discovery, 45° white-core beveled mats, native aspect ratio preservation, Single &amp; Double Mats, and sequence reordering.
                </p>
              </div>

              {/* STEP 22 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    22
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Wi-Fi Network Auto-Discovery &amp; Instant TV Pairing
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Switch to the <strong className="text-amber-300">TV Displays</strong> studio tab in the top navigation ribbon. MRDarkroom automatically connects to all known Samsung Frame TVs on your local Wi-Fi.
                </p>
                <ul className="list-disc pl-5 text-zinc-300 space-y-1.5">
                  <li>
                    Click <strong className="text-amber-300">Scan Wi-Fi Network for TVs</strong> to probe your subnet for Samsung SmartTV WebSocket services (port 8002). Detected displays (e.g., <code className="text-zinc-200 font-mono">TV1 (QN55LS03HEFXZA) at 192.168.68.88</code>) appear instantly in the left sidebar.
                  </li>
                  <li>
                    If your TV is on a separate VLAN or static subnet, click <strong className="text-white">+ Add TV</strong> to punch in the exact IP address directly.
                  </li>
                  <li>
                    The sidebar live badge indicates <span className="text-emerald-400 font-bold">🟢 Online (Art Mode)</span> or <span className="text-zinc-400 font-bold">⚪ Standby</span> with real-time websocket heartbeat.
                  </li>
                </ul>
                <GuideScreenshot
                  src="/guide/step10_tv_displays.png"
                  alt="Samsung Frame TV Displays Studio: Wi-Fi Discovery, Live Controls, Mat Editor, and Sequence Reordering"
                  caption="👉 Step 22 & 25: Auto-scan local Wi-Fi for Frame TVs, reorder photos with ◀ / ▶, toggle Art Mode, and customize beveled mats."
                />
              </div>

              {/* STEP 23 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    23
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Preserve Native Aspect Ratios Without Black Bars
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Ordinary media players force panoramic or medium-format photos into a 16:9 box by either forcibly cropping the composition or introducing unsightly black letterbox / pillarbox bands.
                </p>
                <div className="p-3.5 rounded-lg bg-[#101010] border border-[#2E2E2E] space-y-2">
                  <div className="text-amber-400 font-bold text-xs uppercase tracking-wider">
                    How MRDarkroom's Fine-Art Matting Preserves Your Vision:
                  </div>
                  <ul className="list-disc pl-5 text-zinc-300 text-xs space-y-1.5">
                    <li>
                      <strong className="text-white">Original Ratio (No Crop)</strong>: Renders a true archival museum mat board around your artwork at its exact Lightroom Develop crop (e.g., 3:1 panoramic, 2:1, 4:3 Phase One, 3:2 full frame, 5:4 large format). Zero image cropping, zero black bars!
                    </li>
                    <li>
                      <strong className="text-white">16:9 Crop + Mat</strong>: When you desire a wide 16:9 aperture framed inside an outer mat, choose this option and simply click &amp; drag the photo inside the mat window to pan your exact vertical or horizontal composition.
                    </li>
                    <li>
                      <strong className="text-white">Slim Optical Border (★ Recommended)</strong>: Panoramas are optically weighted slightly above center (44% top margin / 56% bottom) so the wider mat at the base anchors the expansive horizon naturally without looking sagging.
                    </li>
                    <li>
                      <strong className="text-white">Museum Proportions</strong>: Choose between <code className="text-amber-300 font-mono">Slim Optical (88%)</code>, <code className="text-zinc-300 font-mono">Slim Centered (88%)</code>, <code className="text-zinc-300 font-mono">Medium Optical (78%)</code>, <code className="text-zinc-300 font-mono">Wide Exhibition (64%)</code>, or <code className="text-zinc-300 font-mono">Extra-Large Mat (52%)</code>.
                    </li>
                  </ul>
                </div>
              </div>

              {/* STEP 24 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    24
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Single Mat vs. Double Mat with Authentic 45° White-Core Bevel Cut
                  </h4>
                </div>
                <p className="text-zinc-300">
                  Calibrated directly against macro photography of Samsung's physical Frame TV mat boards. Rather than an artificial digital black drop shadow, MRDarkroom renders a physical <strong className="text-amber-300">45-degree angled paper bevel cut</strong> with warm cotton-rag texture and subtle diffuse overhead shading.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2E2E2E] space-y-1.5">
                    <span className="font-bold text-amber-400 uppercase tracking-wide">Single Archival Mat</span>
                    <p className="text-zinc-300">
                      A single 8-ply museum board with a clean 45° chamfer revealing the bright white core paper underneath. Soft top/left shadow slope with illuminated bottom/right slope for genuine physical depth.
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-[#121212] border border-[#2E2E2E] space-y-1.5">
                    <span className="font-bold text-amber-400 uppercase tracking-wide">Double Mat Presentation</span>
                    <p className="text-zinc-300">
                      An outer mat board layered over an inner accent mat with a 1/4" reveal and dual 45° bevel cuts. Perfect for accentuating image colors (e.g. Warm White Rag outer mat over a Burgundy or Sage Olive inner accent).
                    </p>
                  </div>
                </div>
                <p className="text-zinc-300 text-xs">
                  Choose from <strong className="text-white">12 Archival Museum Colors</strong>: Warm White Rag, Polar Museum White, Antique Ivory, Sandstone Tan, Wheat Cream, Sage Olive Green, Deep Forest Pine, Desert Terracotta, Burgundy Wine, French Museum Navy, Gallery Slate, and Archival Onyx Black.
                </p>
                <GuideScreenshot
                  src="/guide/step11_single_vs_double_mat.png"
                  alt="Single Mat vs Double Mat Architectural Comparison with 45° Bevel Cut and Archival Colors"
                  caption="👉 Step 24: Single vs Double Mat cross-section, 45° angled white-core bevel cut, 3/4 depth shading, and archival color presets."
                />
              </div>

              {/* STEP 25 */}
              <div className="p-4 rounded-xl bg-[#181818] border border-[#2C2C2C] space-y-3">
                <div className="flex items-center gap-2.5">
                  <span className="w-7 h-7 rounded-full bg-amber-400 text-zinc-950 font-black text-xs flex items-center justify-center shrink-0">
                    25
                  </span>
                  <h4 style={{ fontSize: headingTextSize }} className="font-black text-white">
                    Sequence Reordering, Batch Styling &amp; Curated TV Slideshow
                  </h4>
                </div>
                <ul className="list-disc pl-5 text-zinc-300 space-y-2">
                  <li>
                    <strong className="text-white">Sequence Reordering</strong>: Drag and drop any photo card or click the <code className="text-amber-300 font-mono">◀ Move Earlier</code> / <code className="text-amber-300 font-mono">▶ Move Later</code> buttons. The sequence order is saved instantly to the database and synced to the TV slideshow sequence.
                  </li>
                  <li>
                    <strong className="text-white">Apply Style to All Photos</strong>: Configure your ideal mat style, border width, and mat color on one photo, then click <strong className="text-amber-300">Apply Style to All Photos</strong>. MRDarkroom re-renders the entire collection in the background and updates the TV seamlessly.
                  </li>
                  <li>
                    <strong className="text-white">Clean Unsynced</strong>: If older uncurated photos or leftover hardware placeholders exist on the TV ROM, click <strong className="text-red-400">Clean Unsynced</strong> to purge them with one click so only your curated artwork remains.
                  </li>
                  <li>
                    <strong className="text-white">Slideshow Timing &amp; Instant Display</strong>: Set your slideshow interval from <code className="text-zinc-200 font-mono">5 Mins</code>, <code className="text-zinc-200 font-mono">15 Mins</code>, <code className="text-zinc-200 font-mono">1 Hour</code> up to <code className="text-zinc-200 font-mono">24 Hours</code>. Click <strong className="text-emerald-400">Display Now</strong> on any card to project that photo to the TV screen in real time.
                  </li>
                </ul>
                <div className="p-3.5 rounded-lg bg-emerald-950/30 border border-emerald-500/30 flex items-center gap-3">
                  <Sparkles className="w-5 h-5 text-emerald-400 shrink-0" />
                  <p className="text-xs text-emerald-200">
                    <strong>Studio Tip:</strong> All mat rendering is performed locally using lossless 4K rasterization (3840 &times; 2160 @ 300 DPI) before sending over local Wi-Fi. The TV displays a flawless fine-art print quality with zero compression artifacts.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* DRAWER FOOTER                                                            */}
        {/* ========================================================================= */}
        <div className="p-3.5 border-t border-[#262626] bg-[#161616] flex items-center justify-between text-xs text-zinc-400 shrink-0">
          <span className="flex items-center gap-2 font-mono">
            <span className="w-2 h-2 rounded-full bg-amber-400"></span>
            <span>Width: {drawerWidth}px • Zoom: {scalePercent}%</span>
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition cursor-pointer shadow-md uppercase tracking-wide border border-amber-300"
          >
            Close Guide
          </button>
        </div>
      </aside>

      {/* ========================================================================= */}
      {/* FULL-SCREEN SCREENSHOT LIGHTBOX ZOOM MODAL                                */}
      {/* ========================================================================= */}
      {zoomedImage && (
        <div
          onClick={() => setZoomedImage(null)}
          className="fixed inset-0 z-[20000] bg-black/90 backdrop-blur-sm flex flex-col items-center justify-center p-6 cursor-zoom-out select-none"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-[92vw] max-h-[90vh] bg-[#161616] border-2 border-amber-400 rounded-2xl shadow-2xl overflow-hidden flex flex-col cursor-default"
          >
            <div className="flex items-center justify-between px-5 py-3.5 bg-[#121212] border-b border-[#2C2C2C]">
              <div className="flex items-center gap-2.5">
                <ZoomIn className="w-5 h-5 text-amber-400" />
                <span className="font-black text-white text-base">{zoomedImage.alt}</span>
              </div>
              <button
                type="button"
                onClick={() => setZoomedImage(null)}
                className="px-3.5 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs cursor-pointer transition"
              >
                ✕ Close Full Screen (Esc)
              </button>
            </div>
            <div className="p-4 bg-[#0F0F0F] flex items-center justify-center overflow-auto">
              <img
                src={zoomedImage.src}
                alt={zoomedImage.alt}
                className="max-w-[88vw] max-h-[76vh] w-auto h-auto object-contain rounded-lg border border-[#2C2C2C]"
              />
            </div>
            {zoomedImage.caption && (
              <div className="px-5 py-3 bg-[#161616] border-t border-[#2C2C2C] text-sm text-amber-300 font-mono">
                {zoomedImage.caption}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
