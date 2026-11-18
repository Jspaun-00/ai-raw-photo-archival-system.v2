import React, { useState, useEffect } from 'react';
import {
  Printer,
  X,
  Check,
  Download,
  Info,
  Sliders,
  Sparkles
} from 'lucide-react';

/**
 * CustomPrintModal.jsx
 *
 * High-contrast modal for configuring custom print sizing JPEG exports.
 * Provides instant 1-click presets (3600px - 12000px) and 240/300 DPI density selection.
 */
export default function CustomPrintModal({
  isOpen,
  onClose,
  photos = [],
  collectionName = null,
  onConfirmExport,
  isBusy = false,
}) {
  const photoCount = Array.isArray(photos) ? photos.length : 1;
  const [targetLongEdge, setTargetLongEdge] = useState(6000);
  const [customInput, setCustomInput] = useState('6000');
  const [dpi, setDpi] = useState(300);
  const [isPickingFolder, setIsPickingFolder] = useState(false);

  // Samsung Frame TV discovery & direct slideshow push state
  const [samsungTvs, setSamsungTvs] = useState([
    { ip: '192.168.68.88', name: 'TV1', model: 'QN55LS03HEFXZA', frame_support: true }
  ]);
  const [selectedTvIp, setSelectedTvIp] = useState('192.168.68.88');
  const [isDiscoveringTvs, setIsDiscoveringTvs] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    fetch('/api/samsung-tvs')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !data || !Array.isArray(data.tvs) || data.tvs.length === 0) return;
        setSamsungTvs(data.tvs);
        setSelectedTvIp((prev) =>
          data.tvs.some((t) => t.ip === prev) ? prev : data.tvs[0].ip
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  const handleDiscoverSamsungTvs = async () => {
    setIsDiscoveringTvs(true);
    try {
      const res = await fetch('/api/samsung-tvs/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.tvs) && data.tvs.length > 0) {
          setSamsungTvs(data.tvs);
          setSelectedTvIp((prev) =>
            data.tvs.some((t) => t.ip === prev) ? prev : data.tvs[0].ip
          );
        }
      }
    } catch (err) {
      console.error('Samsung TV discovery error:', err);
    } finally {
      setIsDiscoveringTvs(false);
    }
  };

  if (!isOpen) return null;

  const presets = [
    { px: 3600, label: '3,600 px', desc: '12" Print @ 300 DPI (Small / Proof)' },
    { px: 4800, label: '4,800 px', desc: '16" Print @ 300 DPI (Medium Frame)' },
    { px: 6000, label: '6,000 px', desc: '20" Print @ 300 DPI (Large Fine Art)' },
    { px: 7200, label: '7,200 px', desc: '24" Print @ 300 DPI (Gallery Exhibition)' },
    { px: 9000, label: '9,000 px', desc: '30" Print @ 300 DPI (Museum Wall)' },
    { px: 12000, label: '12,000 px', desc: '40" Print @ 300 DPI (Master Showcase)' },
  ];

  const handleSelectPreset = (pxVal) => {
    setTargetLongEdge(pxVal);
    setCustomInput(String(pxVal));
  };

  const handleCustomInputChange = (e) => {
    const val = e.target.value;
    setCustomInput(val);
    const num = parseInt(val, 10);
    if (!isNaN(num) && num > 0) {
      setTargetLongEdge(num);
    }
  };

  const printInchesLongEdge = (targetLongEdge / dpi).toFixed(1);
  const printInchesShortEdge = ((targetLongEdge / dpi) * (2 / 3)).toFixed(1);

  const triggerExportWithDestination = (dest, folderPath = null, extraOptions = {}) => {
    if (onConfirmExport) {
      onConfirmExport({
        long_edge: targetLongEdge,
        dpi: dpi,
        target_destination: dest,
        custom_folder_path: folderPath,
        ...extraOptions,
      });
    }
  };

  const handlePickFolderAndExport = async () => {
    setIsPickingFolder(true);
    try {
      const res = await fetch('/api/system/choose-folder', { method: 'POST' });
      const data = await res.json();
      const chosenPath = data.folder_path || data.path;
      if (chosenPath) {
        triggerExportWithDestination('custom', chosenPath);
      }
    } catch (err) {
      console.error('Folder picker error:', err);
    } finally {
      setIsPickingFolder(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[10100] flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-fade-in"
      style={{ zIndex: 10100 }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !isBusy) onClose();
      }}
    >
      <div
        className="w-full max-w-2xl bg-slate-900 border border-purple-500/40 rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        style={{
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.9), 0 0 35px rgba(168, 85, 247, 0.25)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/20 border border-purple-400/30 flex items-center justify-center text-purple-300">
              <Printer className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                Custom Print Sizing Export
                {collectionName && (
                  <span className="text-xs font-black px-2.5 py-0.5 rounded-md bg-amber-400/20 border border-amber-400/50 text-amber-300">
                    📁 {collectionName}
                  </span>
                )}
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-900/60 border border-purple-400/50 text-purple-200 font-normal">
                  JPEG
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Exporting <strong className="text-white">{photoCount}</strong> photo{photoCount === 1 ? '' : 's'} with Lightroom edits & embedded IPTC metadata
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isBusy}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6 overflow-y-auto max-h-[75vh]">
          {/* Section 1: Presets */}
          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5" />
              1. Choose Target Long-Edge Size:
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {presets.map((p) => {
                const isSelected = targetLongEdge === p.px;
                return (
                  <button
                    key={p.px}
                    type="button"
                    onClick={() => handleSelectPreset(p.px)}
                    className={`flex flex-col text-left p-3 rounded-xl border transition cursor-pointer ${
                      isSelected
                        ? 'bg-purple-950/60 border-purple-400 shadow-md ring-1 ring-purple-400/50'
                        : 'bg-slate-800/60 border-slate-700/80 hover:bg-slate-800 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className={`text-sm font-bold ${isSelected ? 'text-purple-200' : 'text-slate-200'}`}>
                        {p.label}
                      </span>
                      {isSelected && <Check className="w-4 h-4 text-purple-400" />}
                    </div>
                    <span className="text-[11px] text-slate-400 mt-1 leading-tight">
                      {p.desc}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Custom Pixel Input */}
            <div className="mt-3 flex items-center gap-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <span className="text-xs text-slate-300 font-medium whitespace-nowrap">
                Or Custom Long Edge:
              </span>
              <div className="relative flex-1">
                <input
                  type="number"
                  min="800"
                  max="30000"
                  step="100"
                  value={customInput}
                  onChange={handleCustomInputChange}
                  className="w-full bg-slate-900 border border-slate-700 focus:border-purple-400 rounded-lg px-3 py-1.5 text-sm text-white font-mono outline-none transition"
                  placeholder="e.g. 6000"
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-500 font-mono pointer-events-none">
                  pixels
                </span>
              </div>
            </div>
          </div>

          {/* Section 2: Print Density (DPI) */}
          <div className="space-y-3">
            <label className="text-xs font-semibold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5" />
              2. Print Density Resolution (DPI):
            </label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setDpi(300)}
                className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                  dpi === 300
                    ? 'bg-purple-950/60 border-purple-400 shadow-md ring-1 ring-purple-400/50'
                    : 'bg-slate-800/60 border-slate-700/80 hover:bg-slate-800 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-bold ${dpi === 300 ? 'text-purple-200' : 'text-slate-200'}`}>
                    300 DPI
                  </span>
                  {dpi === 300 && <Check className="w-4 h-4 text-purple-400" />}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Standard Gallery Master (Maximum sharpness for close viewing)
                </div>
              </button>

              <button
                type="button"
                onClick={() => setDpi(240)}
                className={`p-3 rounded-xl border text-left transition cursor-pointer ${
                  dpi === 240
                    ? 'bg-purple-950/60 border-purple-400 shadow-md ring-1 ring-purple-400/50'
                    : 'bg-slate-800/60 border-slate-700/80 hover:bg-slate-800 hover:border-slate-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-sm font-bold ${dpi === 240 ? 'text-purple-200' : 'text-slate-200'}`}>
                    240 DPI
                  </span>
                  {dpi === 240 && <Check className="w-4 h-4 text-purple-400" />}
                </div>
                <div className="text-[11px] text-slate-400 mt-1">
                  Fine Art Inkjet (Excellent for larger format giclée prints)
                </div>
              </button>
            </div>
          </div>

          {/* Section 3: Live Print Size Calculation Summary */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 flex items-start gap-3">
            <Info className="w-4 h-4 text-purple-400 shrink-0 mt-0.5" />
            <div className="text-xs text-slate-300 leading-relaxed">
              Target output: <strong className="text-purple-300 font-mono">{targetLongEdge.toLocaleString()} px</strong> long edge at <strong className="text-purple-300 font-mono">{dpi} DPI</strong>.
              <br />
              Equivalent physical print size: approximately <strong className="text-white">{printInchesLongEdge}&quot; × {printInchesShortEdge}&quot;</strong> (for standard 3:2 landscape).
              <br />
              Exports directly to <span className="text-emerald-400 font-mono">~/Desktop/MRDarkroom_Exports/</span>.
            </div>
          </div>
        </div>

        {/* Footer: 4 Direct Destinations (Desktop, iCloud, Choose Folder, Push to Samsung TV) */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/90 flex-wrap gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isBusy}
            className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition cursor-pointer"
          >
            Cancel
          </button>

          <div className="flex items-center gap-2.5 flex-wrap">
            {/* 1. Desktop */}
            <button
              type="button"
              onClick={() => triggerExportWithDestination('desktop')}
              disabled={isBusy || !targetLongEdge}
              title="Export custom prints directly to ~/Desktop/MRDarkroom_Exports"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/60 border border-emerald-500/50 shadow-md transition cursor-pointer disabled:opacity-50"
            >
              <span className="text-sm">🖥️</span>
              <span>{isBusy ? 'Exporting...' : 'Export to Desktop'}</span>
            </button>

            {/* 2. iCloud Drive */}
            <button
              type="button"
              onClick={() => triggerExportWithDestination('icloud')}
              disabled={isBusy || !targetLongEdge}
              title="Export to iCloud Drive (Syncs across devices & Apple TV)"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-sky-300 bg-sky-950/40 hover:bg-sky-900/60 border border-sky-500/50 shadow-md transition cursor-pointer disabled:opacity-50"
            >
              <span className="text-sm">☁️</span>
              <span>{isBusy ? 'Exporting...' : 'Export to iCloud'}</span>
            </button>

            {/* 3. Choose Folder in Finder */}
            <button
              type="button"
              onClick={handlePickFolderAndExport}
              disabled={isBusy || isPickingFolder || !targetLongEdge}
              title="Choose any specific local, GDrive, or client folder in macOS Finder"
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold text-purple-300 bg-purple-950/40 hover:bg-purple-900/60 border border-purple-500/50 shadow-md transition cursor-pointer disabled:opacity-50"
            >
              <span className="text-sm">📁</span>
              <span>{isPickingFolder ? 'Opening Finder...' : 'Choose Folder...'}</span>
            </button>

            {/* 4. Push to Samsung TV + Discover More TVs */}
            <div className="flex items-center gap-1.5 bg-amber-950/30 border border-amber-500/50 rounded-xl p-1 pl-2.5 shadow-md">
              <select
                value={selectedTvIp}
                onChange={(e) => setSelectedTvIp(e.target.value)}
                disabled={isBusy || isDiscoveringTvs}
                title="Select Samsung Frame TV on local Wi-Fi"
                className="bg-transparent text-amber-200 text-xs font-bold outline-none cursor-pointer pr-1"
              >
                {samsungTvs.map((tv) => (
                  <option key={tv.ip} value={tv.ip} className="bg-slate-900 text-amber-200">
                    📺 {tv.name || 'Samsung TV'} ({tv.ip})
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={handleDiscoverSamsungTvs}
                disabled={isBusy || isDiscoveringTvs}
                title="Scan Wi-Fi network to discover additional Samsung Frame TVs"
                className="px-2 py-1.5 rounded-lg text-[11px] font-semibold text-amber-300 hover:text-white bg-amber-900/40 hover:bg-amber-800/60 border border-amber-500/30 transition cursor-pointer disabled:opacity-50"
              >
                {isDiscoveringTvs ? 'Scanning...' : '🔍 Discover'}
              </button>

              <button
                type="button"
                onClick={() =>
                  triggerExportWithDestination('samsung_tv', null, {
                    samsung_tv_ip: selectedTvIp,
                    slideshow_minutes: 15,
                  })
                }
                disabled={isBusy || !selectedTvIp || !targetLongEdge}
                title="Push directly to Samsung Frame TV internal storage & start persistent Art Mode slideshow"
                className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-black text-slate-950 bg-amber-400 hover:bg-amber-300 shadow transition cursor-pointer disabled:opacity-50"
              >
                <span>📺 Push to Samsung TV</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
