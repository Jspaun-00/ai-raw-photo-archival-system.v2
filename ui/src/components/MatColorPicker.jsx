import React, { useState, useMemo } from 'react';
import { Palette, Sliders, Check, ArrowLeftRight, Sparkles, Pipette, RotateCcw } from 'lucide-react';

/**
 * ARCHIVAL_MAT_TONES
 * 20 sensible museum mat tones across 5 curated tonal families.
 * Strictly archival, muted, cotton rag, and linen values — zero garish neon.
 */
export const ARCHIVAL_MAT_TONES = [
  // 1. Museum Whites & Creams
  { id: 'polar_white', name: 'Polar Museum White', short: 'Polar White', hex: '#FAF8F5', family: 'whites', desc: 'Crisp bright exhibition white' },
  { id: 'warm_white', name: 'Warm White Rag', short: 'Warm White', hex: '#F4EFE6', family: 'whites', desc: 'Museum 8-ply warm cotton rag (Samsung default)' },
  { id: 'antique_ivory', name: 'Antique Ivory', short: 'Antique Ivory', hex: '#EADBCA', family: 'whites', desc: 'Classic warm heritage ivory board' },
  { id: 'wheat_cream', name: 'Wheat Cream', short: 'Wheat Cream', hex: '#E8DEC8', family: 'whites', desc: 'Archival warm wheat cream' },

  // 2. Warm Neutrals & Earth Tones
  { id: 'sandstone_tan', name: 'Sandstone Tan', short: 'Sandstone', hex: '#D8CBB7', family: 'warm_earth', desc: 'Warm natural linen & tan' },
  { id: 'oatmeal_tan', name: 'Oatmeal Linen', short: 'Oatmeal', hex: '#C7B8A1', family: 'warm_earth', desc: 'Mid-tone organic woven linen' },
  { id: 'desert_terracotta', name: 'Desert Terracotta', short: 'Terracotta', hex: '#A45A45', family: 'warm_earth', desc: 'Warm clay & southwestern rust' },
  { id: 'raw_umber', name: 'Raw Umber Earth', short: 'Raw Umber', hex: '#6E5244', family: 'warm_earth', desc: 'Deep warm architectural earth' },

  // 3. Archival Botanicals & Greens
  { id: 'muted_sage', name: 'Muted Sage Green', short: 'Sage Green', hex: '#7D8B79', family: 'greens', desc: 'Earthy soft botanical sage' },
  { id: 'heritage_olive', name: 'Heritage Olive', short: 'Heritage Olive', hex: '#4E5B4B', family: 'greens', desc: 'Muted heritage botanical olive' },
  { id: 'deep_forest_pine', name: 'Deep Forest Pine', short: 'Forest Pine', hex: '#28382B', family: 'greens', desc: 'Rich archival dark pine' },
  { id: 'nordic_spruce', name: 'Nordic Spruce', short: 'Nordic Spruce', hex: '#1E2C22', family: 'greens', desc: 'Shadowed evergreen spruce' },

  // 4. Heritage Blues & Wines
  { id: 'coastal_slate_blue', name: 'Coastal Blue Slate', short: 'Slate Blue', hex: '#5A6E7C', family: 'blues_wine', desc: 'Muted coastal foggy blue' },
  { id: 'french_navy', name: 'French Museum Navy', short: 'Museum Navy', hex: '#2C3E50', family: 'blues_wine', desc: 'Sophisticated deep archival navy' },
  { id: 'midnight_indigo', name: 'Midnight Indigo', short: 'Indigo', hex: '#1A2530', family: 'blues_wine', desc: 'Deep ink indigo velvet' },
  { id: 'burgundy_wine', name: 'Burgundy Wine', short: 'Burgundy', hex: '#581C25', family: 'blues_wine', desc: 'Deep museum burgundy wine' },

  // 5. Studio Grayscales & Onyx
  { id: 'chalk_dove_gray', name: 'Chalk Dove Gray', short: 'Chalk Gray', hex: '#A8A8A2', family: 'greys_black', desc: 'Cool neutral museum stone gray' },
  { id: 'gallery_slate', name: 'Gallery Slate', short: 'Gallery Slate', hex: '#454B54', family: 'greys_black', desc: 'Contemporary matte charcoal' },
  { id: 'charcoal_wool', name: 'Charcoal Graphite', short: 'Charcoal', hex: '#2A2E33', family: 'greys_black', desc: 'Dark architectural graphite' },
  { id: 'archival_onyx', name: 'Archival Onyx Black', short: 'Onyx Black', hex: '#111215', family: 'greys_black', desc: 'Deep black velvet' },
];

export const TONAL_FAMILIES = [
  { id: 'all', label: 'All 20 Tones' },
  { id: 'whites', label: 'Whites & Creams' },
  { id: 'warm_earth', label: 'Warm & Linen' },
  { id: 'greens', label: 'Botanical Greens' },
  { id: 'blues_wine', label: 'Heritage & Wine' },
  { id: 'greys_black', label: 'Greys & Onyx' },
];

/**
 * 24 Sensible Archival Spectrum Checkerboard Chips
 * 6 curated archival hues across 4 lightness levels (Highlight, Tint, Midtone, Shadow).
 * Saturation is strictly capped between 15% and 40% — zero neon.
 */
export const ARCHIVAL_SPECTRUM_CHECKERBOARD = [
  // Row 1: Light Tints / Paper Highlights
  [
    { hex: '#F7F4EE', name: 'Warm Rag Tint' },
    { hex: '#EFEAE1', name: 'Linen Tint' },
    { hex: '#EBE5DE', name: 'Terracotta Tint' },
    { hex: '#E2E6DF', name: 'Sage Tint' },
    { hex: '#DEE4E8', name: 'Slate Tint' },
    { hex: '#E6E6E4', name: 'Pewter Tint' },
  ],
  // Row 2: Soft Muted Tones
  [
    { hex: '#EDE4D4', name: 'Pale Wheat' },
    { hex: '#DFD2BE', name: 'Soft Sand' },
    { hex: '#CDB1A4', name: 'Muted Clay' },
    { hex: '#A8B4A4', name: 'Soft Lichen' },
    { hex: '#8C9DA8', name: 'Muted Fjord' },
    { hex: '#B5B5AF', name: 'Ash Gray' },
  ],
  // Row 3: Classic Museum Base Tones
  [
    { hex: '#E2D5BE', name: 'Antique Parchment' },
    { hex: '#BFAC92', name: 'Raw Linen' },
    { hex: '#A1624E', name: 'Archival Terracotta' },
    { hex: '#63725F', name: 'Archival Sage' },
    { hex: '#485C6D', name: 'Archival Marine' },
    { hex: '#686D74', name: 'Studio Slate' },
  ],
  // Row 4: Deep Architectural Shades
  [
    { hex: '#9E8D73', name: 'Dark Khaki' },
    { hex: '#7A624E', name: 'Dark Umber' },
    { hex: '#582421', name: 'Deep Rust Wine' },
    { hex: '#2A3A2C', name: 'Deep Spruce' },
    { hex: '#1E2C3A', name: 'Deep Midnight' },
    { hex: '#1F2226', name: 'Deep Charcoal' },
  ],
];

export const DOUBLE_MAT_RECOMMENDED_PAIRS = [
  { name: 'Warm White + Burgundy', outer: '#F4EFE6', inner: '#581C25' },
  { name: 'Polar White + Sage Green', outer: '#FAF8F5', inner: '#4E5B4B' },
  { name: 'Antique Ivory + French Navy', outer: '#EADBCA', inner: '#2C3E50' },
  { name: 'Sandstone + Terracotta', outer: '#D8CBB7', inner: '#A45A45' },
  { name: 'Gallery Slate + Polar White', outer: '#454B54', inner: '#FAF8F5' },
];

/**
 * Calculates a lighter or deeper shade of any hex color (-1.0 to +1.0)
 */
export function shadeHexColor(hex, pct) {
  const clean = String(hex || '#F4EFE6').replace('#', '').trim();
  const num = parseInt(clean.length === 3 ? clean.split('').map((c) => c + c).join('') : clean, 16);
  if (Number.isNaN(num)) return '#F4EFE6';
  let r = (num >> 16) & 255;
  let g = (num >> 8) & 255;
  let b = num & 255;
  if (pct < 0) {
    const f = 1 + pct;
    r = Math.round(r * f);
    g = Math.round(g * f);
    b = Math.round(b * f);
  } else {
    r = Math.round(r + (255 - r) * pct);
    g = Math.round(g + (255 - g) * pct);
    b = Math.round(b + (255 - b) * pct);
  }
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1).toUpperCase()}`;
}

export function findMatTone(hex) {
  if (!hex) return null;
  const target = hex.toLowerCase().trim();
  return ARCHIVAL_MAT_TONES.find((c) => c.hex.toLowerCase() === target) || null;
}

export default function MatColorPicker({
  color = '#F4EFE6',
  onChange,
  isDoubleMat = false,
  innerColor = '#F4EFE6',
  onInnerChange,
  compact = false,
}) {
  const [activeTab, setActiveTab] = useState('outer'); // 'outer' | 'inner'
  const [selectedFamily, setSelectedFamily] = useState('all');
  const [viewMode, setViewMode] = useState('checkerboard'); // 'checkerboard' | 'spectrum'
  const [toneDelta, setToneDelta] = useState(0);

  const currentColor = activeTab === 'inner' ? innerColor : color;
  const currentSetColor = activeTab === 'inner' ? onInnerChange : onChange;

  const activeMatchedTone = useMemo(() => findMatTone(currentColor), [currentColor]);

  // Dynamic 5-step tone shade variations for the active color
  const dynamicShades = useMemo(() => {
    return [
      { label: '-24% Deep', pct: -0.24, hex: shadeHexColor(currentColor, -0.24) },
      { label: '-12% Shade', pct: -0.12, hex: shadeHexColor(currentColor, -0.12) },
      { label: 'Base Tone ★', pct: 0, hex: currentColor },
      { label: '+12% Tint', pct: 0.12, hex: shadeHexColor(currentColor, 0.12) },
      { label: '+24% Light', pct: 0.24, hex: shadeHexColor(currentColor, 0.24) },
    ];
  }, [currentColor]);

  // Filtered list of tones
  const displayedTones = useMemo(() => {
    if (selectedFamily === 'all') return ARCHIVAL_MAT_TONES;
    return ARCHIVAL_MAT_TONES.filter((t) => t.family === selectedFamily);
  }, [selectedFamily]);

  const handleSwapDoubleColors = () => {
    if (!onChange || !onInnerChange) return;
    const tempOuter = color;
    onChange(innerColor);
    onInnerChange(tempOuter);
  };

  const handleApplyShadeDelta = (deltaPct) => {
    setToneDelta(deltaPct);
    const newHex = shadeHexColor(currentColor, deltaPct);
    currentSetColor(newHex);
  };

  const handleEyedropper = async () => {
    if (window.EyeDropper) {
      try {
        const eyeDropper = new window.EyeDropper();
        const result = await eyeDropper.open();
        if (result && result.sRGBHex) {
          currentSetColor(result.sRGBHex.toUpperCase());
        }
      } catch {
        // user canceled or not supported
      }
    }
  };

  return (
    <div className={`space-y-3 rounded-xl border border-white/10 bg-[#121316] ${compact ? 'p-2.5' : 'p-3.5'} text-xs select-none shadow-lg`}>
      {/* ---------------------------------------------------------------------- */}
      {/* DOUBLE MAT LAYER SELECTOR & SWAP BAR                                   */}
      {/* ---------------------------------------------------------------------- */}
      {isDoubleMat && (
        <div className="flex items-center justify-between gap-2 pb-2.5 border-b border-white/10 flex-wrap">
          <div className="flex items-center gap-1.5 p-1 rounded-lg bg-black/40 border border-white/10">
            <button
              type="button"
              onClick={() => setActiveTab('outer')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md font-bold transition-all ${
                activeTab === 'outer'
                  ? 'bg-amber-400 text-zinc-950 shadow-md'
                  : 'text-zinc-300 hover:text-white'
              }`}
            >
              <span
                className="w-3.5 h-3.5 rounded-full border border-black/40 shadow-sm shrink-0"
                style={{ backgroundColor: color }}
              />
              <span>1. Outer Mat Board ({findMatTone(color)?.short || color})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('inner')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md font-bold transition-all ${
                activeTab === 'inner'
                  ? 'bg-amber-400 text-zinc-950 shadow-md'
                  : 'text-zinc-300 hover:text-white'
              }`}
            >
              <span
                className="w-3.5 h-3.5 rounded-full border border-black/40 shadow-sm shrink-0"
                style={{ backgroundColor: innerColor }}
              />
              <span>2. Inner Reveal Accent ({findMatTone(innerColor)?.short || innerColor})</span>
            </button>
          </div>

          <button
            type="button"
            onClick={handleSwapDoubleColors}
            title="Swap Outer and Inner Mat Colors"
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-amber-300 border border-amber-500/30 font-semibold cursor-pointer transition active:scale-95 text-[11px]"
          >
            <ArrowLeftRight className="w-3.5 h-3.5" />
            <span>⇄ Swap Layers</span>
          </button>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* HEADER: ACTIVE COLOR PREVIEW + QUICK SHADES + HEX CONTROLS             */}
      {/* ---------------------------------------------------------------------- */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {/* Active Selected Color Badge */}
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg border-2 border-white/25 shadow-md flex items-center justify-center shrink-0 relative overflow-hidden"
            style={{ backgroundColor: currentColor }}
          >
            <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-black/20 pointer-events-none" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-[13px]">
                {activeMatchedTone?.name || 'Custom Framing Tone'}
              </span>
              <span className="font-mono text-[11px] text-amber-300 bg-amber-400/10 border border-amber-500/30 px-1.5 py-0.5 rounded">
                {currentColor}
              </span>
            </div>
            <div className="text-[10px] text-zinc-400 font-mono">
              {activeMatchedTone?.desc || 'Archival fine-art paper matting'}
            </div>
          </div>
        </div>

        {/* View Switcher: 20 Tones Checkerboard vs. Archival Spectrum */}
        <div className="flex items-center gap-1 bg-black/40 p-0.5 rounded-lg border border-white/10 text-[11px]">
          <button
            type="button"
            onClick={() => setViewMode('checkerboard')}
            className={`px-2.5 py-1 rounded font-bold transition ${
              viewMode === 'checkerboard'
                ? 'bg-amber-400 text-zinc-950'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Checkerboard (20 Tones)
          </button>
          <button
            type="button"
            onClick={() => setViewMode('spectrum')}
            className={`px-2.5 py-1 rounded font-bold transition ${
              viewMode === 'spectrum'
                ? 'bg-amber-400 text-zinc-950'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Spectrum Matrix
          </button>
        </div>

        {/* Direct Hex & System Picker Input */}
        <div className="flex items-center gap-1.5">
          {window.EyeDropper && (
            <button
              type="button"
              onClick={handleEyedropper}
              title="Pick color from photo with Eyedropper"
              className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-white/15 cursor-pointer"
            >
              <Pipette className="w-3.5 h-3.5" />
            </button>
          )}
          <input
            type="color"
            value={currentColor}
            onChange={(e) => currentSetColor(e.target.value.toUpperCase())}
            title="Custom Hex Color Wheel"
            className="w-7 h-7 rounded-lg cursor-pointer border border-white/20 bg-transparent p-0 overflow-hidden"
          />
        </div>
      </div>

      {/* ---------------------------------------------------------------------- */}
      {/* 5-STEP TONAL SHADE & TINT CHECKERBOARD (MICRO-ADJUSTMENTS)              */}
      {/* ---------------------------------------------------------------------- */}
      <div className="p-2.5 rounded-lg bg-black/35 border border-white/10 space-y-2">
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-zinc-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-amber-400" />
            <span>Tone &amp; Shade Variations (Sensible Archival Tint &harr; Shade):</span>
          </span>
          <span className="text-[10px] text-zinc-500 font-mono">
            Click any square to lighten or deepen this tone
          </span>
        </div>

        <div className="grid grid-cols-5 gap-1.5">
          {dynamicShades.map((s) => {
            const isCurrent = s.hex.toLowerCase() === currentColor.toLowerCase();
            return (
              <button
                key={s.label}
                type="button"
                onClick={() => currentSetColor(s.hex)}
                className={`relative group rounded-md p-1.5 border transition-all flex flex-col items-center justify-center gap-1 cursor-pointer ${
                  isCurrent
                    ? 'border-amber-400 ring-2 ring-amber-400/80 bg-amber-400/10 shadow-md'
                    : 'border-white/15 hover:border-white/40 bg-zinc-900/60'
                }`}
              >
                <div
                  className="w-full h-5 rounded border border-black/40 shadow-inner flex items-center justify-center"
                  style={{ backgroundColor: s.hex }}
                >
                  {isCurrent && <Check className="w-3 h-3 text-zinc-900 drop-shadow-sm stroke-[3]" />}
                </div>
                <span className="text-[10px] font-mono text-zinc-300 font-medium">
                  {s.label}
                </span>
                <span className="text-[9px] font-mono text-zinc-500">
                  {s.hex}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ---------------------------------------------------------------------- */}
      {/* VIEW A: 20 CURATED MUSEUM TONES CHECKERBOARD GRID                      */}
      {/* ---------------------------------------------------------------------- */}
      {viewMode === 'checkerboard' && (
        <div className="space-y-2">
          {/* Family Filter Pills */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-none text-[11px]">
            {TONAL_FAMILIES.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setSelectedFamily(f.id)}
                className={`px-2.5 py-1 rounded-full whitespace-nowrap font-medium transition cursor-pointer ${
                  selectedFamily === f.id
                    ? 'bg-amber-400 text-zinc-950 font-bold shadow'
                    : 'bg-zinc-800/80 text-zinc-400 hover:text-white border border-white/10'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* 20-Tone Checkerboard Swatch Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-1.5 max-h-[220px] overflow-y-auto pr-1">
            {displayedTones.map((t) => {
              const isSelected = currentColor.toLowerCase() === t.hex.toLowerCase();
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => currentSetColor(t.hex)}
                  title={`${t.name} (${t.hex}) — ${t.desc}`}
                  className={`group relative p-2 rounded-lg border text-left flex items-center gap-2 cursor-pointer transition-all ${
                    isSelected
                      ? 'border-amber-400 ring-2 ring-amber-400/80 bg-amber-400/15 shadow-md'
                      : 'border-white/10 hover:border-white/30 bg-zinc-900/60 hover:bg-zinc-900'
                  }`}
                >
                  <div
                    className="w-5 h-5 rounded-md border border-black/40 shadow-sm shrink-0 flex items-center justify-center"
                    style={{ backgroundColor: t.hex }}
                  >
                    {isSelected && <Check className="w-3 h-3 text-zinc-950 drop-shadow-sm stroke-[3]" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-[11px] font-bold text-white truncate leading-tight">
                      {t.short}
                    </div>
                    <div className="text-[9.5px] font-mono text-zinc-400 truncate">
                      {t.hex}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* VIEW B: 24 ARCHIVAL SPECTRUM CHECKERBOARD MATRIX                       */}
      {/* ---------------------------------------------------------------------- */}
      {viewMode === 'spectrum' && (
        <div className="p-2.5 rounded-lg bg-black/40 border border-white/10 space-y-2">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-zinc-300 font-bold flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span>Calibrated Non-Neon Spectrum Matrix (24 Tonal Chips):</span>
            </span>
            <span className="text-[10px] text-zinc-500 font-mono">
              Warm Buff &harr; Earth &harr; Olive &harr; Navy &harr; Charcoal
            </span>
          </div>

          <div className="space-y-1.5">
            {ARCHIVAL_SPECTRUM_CHECKERBOARD.map((row, rowIdx) => (
              <div key={`row-${rowIdx}`} className="grid grid-cols-6 gap-1.5">
                {row.map((chip) => {
                  const isSelected = currentColor.toLowerCase() === chip.hex.toLowerCase();
                  return (
                    <button
                      key={chip.hex}
                      type="button"
                      onClick={() => currentSetColor(chip.hex)}
                      title={`${chip.name} (${chip.hex})`}
                      className={`h-7 rounded border relative transition-transform hover:scale-105 cursor-pointer flex items-center justify-center ${
                        isSelected
                          ? 'border-amber-400 ring-2 ring-amber-400 shadow-md scale-102'
                          : 'border-white/20 hover:border-white/50'
                      }`}
                      style={{ backgroundColor: chip.hex }}
                    >
                      {isSelected && (
                        <span className="w-2 h-2 rounded-full bg-amber-400 ring-2 ring-black" />
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------------- */}
      {/* DOUBLE MAT RECOMMENDED COMBINATIONS BAR                                */}
      {/* ---------------------------------------------------------------------- */}
      {isDoubleMat && (
        <div className="pt-2 border-t border-white/10 flex items-center gap-1.5 flex-wrap text-[11px]">
          <span className="text-zinc-400 font-bold uppercase tracking-wider text-[10px]">
            Recommended Pairings:
          </span>
          {DOUBLE_MAT_RECOMMENDED_PAIRS.map((pair) => (
            <button
              key={pair.name}
              type="button"
              onClick={() => {
                if (onChange) onChange(pair.outer);
                if (onInnerChange) onInnerChange(pair.inner);
              }}
              className="px-2 py-0.5 rounded bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 hover:text-white border border-white/10 cursor-pointer flex items-center gap-1.5 text-[10.5px]"
            >
              <span className="flex items-center -space-x-1">
                <span className="w-2.5 h-2.5 rounded-full border border-black/40 inline-block z-10" style={{ backgroundColor: pair.outer }} />
                <span className="w-2.5 h-2.5 rounded-full border border-black/40 inline-block" style={{ backgroundColor: pair.inner }} />
              </span>
              <span>{pair.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
