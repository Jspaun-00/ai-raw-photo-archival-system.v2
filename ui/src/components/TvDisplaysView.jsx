import React, { useState, useEffect, useCallback, useId } from 'react';
import {
  Tv,
  Plus,
  Trash2,
  RefreshCw,
  Play,
  Pause,
  Image as ImageIcon,
  Eye,
  Sliders,
  Palette,
  Sparkles,
  Clock,
  RotateCcw,
  ChevronLeft,
  ChevronRight,
  Check,
  Move,
  Wifi,
  ArrowLeft,
  ArrowRight,
  Layers,
  GripVertical,
} from 'lucide-react';
import MatColorPicker, { ARCHIVAL_MAT_TONES as MAT_COLOR_PRESETS, findMatTone } from './MatColorPicker';

const ASPECT_RATIO_OPTIONS = [
  { id: 'original', label: 'Original Ratio (No Crop)', shortLabel: 'Original (No Crop)', desc: 'Preserves 100% uncropped Lightroom/native aspect ratio inside mat', ratio: null },
  { id: '16:9', label: '16:9 Crop + Mat', shortLabel: '16:9 + Mat', desc: '16:9 widescreen crop inside beveled mat (drag photo to pan)', ratio: 16 / 9 },
  { id: '3:1', label: '3:1 Panorama', shortLabel: '3:1 Pano', desc: 'Ultra-wide 3:1 panoramic crop inside mat', ratio: 3 / 1 },
  { id: '2:1', label: '2:1 Panorama', shortLabel: '2:1 Pano', desc: 'Panoramic 2:1 crop inside mat', ratio: 2 / 1 },
  { id: '3:2', label: '3:2 Full Frame', shortLabel: '3:2', desc: 'Classic 35mm 3:2 crop inside mat', ratio: 3 / 2 },
  { id: '4:3', label: '4:3 Medium Format', shortLabel: '4:3', desc: 'Phase One 4:3 medium format crop inside mat', ratio: 4 / 3 },
  { id: '5:4', label: '5:4 Large Format', shortLabel: '5:4', desc: '4×5 / 8×10 large format crop inside mat', ratio: 5 / 4 },
  { id: '1:1', label: '1:1 Square', shortLabel: '1:1', desc: 'Square format crop inside mat', ratio: 1 },
];

const BORDER_STYLE_OPTIONS = [
  { id: 'slim_optical', label: 'Slim Optical ★', desc: 'Slim 88% border · optical vertical center (Best for Panos)' },
  { id: 'modern_thin', label: 'Slim Centered', desc: 'Slim 88% border · exact 50/50 center' },
  { id: 'optical_center', label: 'Medium Optical', desc: 'Classic 78% gallery mat · optical center' },
  { id: 'exact_center', label: 'Medium Centered', desc: 'Classic 78% gallery mat · 50/50 center' },
  { id: 'modern_wide', label: 'Wide Exhibition', desc: 'Generous 64% museum exhibition mat' },
  { id: 'grand_exhibition', label: 'Extra-Large Mat', desc: 'Deep 52% architectural gallery mat' },
  { id: 'none', label: 'Full 16:9 Bleed (No Mat)', desc: 'Edge-to-edge 16:9 screen fill without mat' },
];

const SLIDESHOW_INTERVALS = [
  { value: 5, label: '5 Mins' },
  { value: 10, label: '10 Mins' },
  { value: 15, label: '15 Mins' },
  { value: 30, label: '30 Mins' },
  { value: 60, label: '1 Hour' },
  { value: 360, label: '6 Hours' },
  { value: 720, label: '12 Hours' },
  { value: 1440, label: '24 Hours' },
];

function parseTargetRatio(aspectId, naturalRatio) {
  if (!aspectId || aspectId === 'original') return naturalRatio || 4 / 3;
  const found = ASPECT_RATIO_OPTIONS.find((a) => a.id === aspectId);
  if (found && found.ratio) return found.ratio;
  if (typeof aspectId === 'string' && aspectId.includes(':')) {
    const [w, h] = aspectId.split(':').map(Number);
    if (w > 0 && h > 0) return w / h;
  }
  return naturalRatio || 4 / 3;
}

/**
 * Renders an authentic 16:9 Samsung Frame TV canvas (`1600 x 900` coordinate system)
 * calibrated to match the user's macro reference photos of Samsung's physical Frame TV bevel:
 *  - 3/4 bevel width (`B = 10` on `1600 x 900` canvas, matching `19px` on 4K `3840 x 2160`)
 *  - Soft warm cotton-rag paper shading on the 45° chamfer (no harsh dark outer wireframe)
 *  - Supports both Single Mat (1 bevel) and Double Mat (outer bevel + inner mat reveal + inner bevel)
 */
function FrameTvMatPreview({
  thumbSrc,
  title = 'Artwork',
  matMode = 'studio',
  matColor = '#F4EFE6',
  matPlacement = 'slim_optical',
  matAspect = 'original',
  matStyle = 'single',
  innerMatColor = '#F4EFE6',
  cropX = 0.5,
  cropY = 0.5,
  interactivePan = false,
  onCropChange = null,
  bevelThickness = 10,
}) {
  const uid = useId().replace(/:/g, '');
  const [naturalAspect, setNaturalAspect] = useState(4 / 3);
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState(null);

  const isNoMat = matMode === 'none' || matPlacement === 'none';
  const effectiveAspect = isNoMat ? 16 / 9 : parseTargetRatio(matAspect, naturalAspect);
  const canPan = interactivePan && onCropChange && (isNoMat || (matAspect && matAspect !== 'original'));

  // Compute window coordinates in 1600x900 (16:9 square-pixel) SVG space
  const canvasW = 1600;
  const canvasH = 900;

  let maxWFrac = 0.78;
  let maxHFrac = 0.76;
  if (matPlacement === 'grand_exhibition') {
    maxWFrac = 0.52;
    maxHFrac = 0.52;
  } else if (matPlacement === 'modern_wide') {
    maxWFrac = 0.64;
    maxHFrac = 0.64;
  } else if (matPlacement === 'modern_thin' || matPlacement === 'slim_optical') {
    maxWFrac = 0.88;
    maxHFrac = 0.86;
  }

  const maxW = canvasW * maxWFrac;
  const maxH = canvasH * maxHFrac;

  let winW = maxW;
  let winH = maxH;
  if (maxW / maxH > effectiveAspect) {
    winH = maxH;
    winW = Math.round(winH * effectiveAspect);
  } else {
    winW = maxW;
    winH = Math.round(winW / effectiveAspect);
  }

  const x0 = Math.round((canvasW - winW) / 2);
  let y0 = Math.round((canvasH - winH) / 2);
  if (matPlacement === 'slim_optical') {
    y0 = Math.round((canvasH - winH) * 0.44);
  } else if (matPlacement === 'optical_center') {
    y0 = Math.round((canvasH - winH) * 0.45);
  } else if (matPlacement === 'modern_wide' || matPlacement === 'grand_exhibition') {
    y0 = Math.round((canvasH - winH) * 0.46);
  }
  const x1 = x0 + winW;
  const y1 = y0 + winH;

  // Inner 45° bevel (3/4 thickness = 10 units on 1600x900)
  const B = bevelThickness;
  const ox0 = x0 - B;
  const oy0 = y0 - B;
  const ox1 = x1 + B;
  const oy1 = y1 + B;

  // Optional Double Mat coordinates (inner mat reveal + outer 45° bevel)
  const isDouble = String(matStyle || 'single').toLowerCase() === 'double';
  const reveal = Math.max(10, Math.round(B * 2.1));
  const BOut = Math.max(6, Math.round(B * 0.88));
  // Inner mat outer edge (where outer bevel inner edge meets inner mat)
  const mx0 = ox0 - reveal;
  const my0 = oy0 - reveal;
  const mx1 = ox1 + reveal;
  const my1 = oy1 + reveal;
  // Outer bevel outer edge (where outer mat board begins)
  const obx0 = mx0 - BOut;
  const oby0 = my0 - BOut;
  const obx1 = mx1 + BOut;
  const oby1 = my1 + BOut;

  const handleMouseDown = (e) => {
    if (!canPan) return;
    e.preventDefault();
    setDragging(true);
    setDragStart({
      clientX: e.clientX,
      clientY: e.clientY,
      startX: cropX ?? 0.5,
      startY: cropY ?? 0.5,
    });
  };

  useEffect(() => {
    if (!dragging || !dragStart || !onCropChange) return undefined;
    const handleMove = (e) => {
      const dx = (dragStart.clientX - e.clientX) / 240;
      const dy = (dragStart.clientY - e.clientY) / 240;
      const nextX = Math.max(0, Math.min(1, Number((dragStart.startX + dx).toFixed(3))));
      const nextY = Math.max(0, Math.min(1, Number((dragStart.startY + dy).toFixed(3))));
      onCropChange(nextX, nextY);
    };
    const handleUp = () => setDragging(false);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp);
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [dragging, dragStart, onCropChange]);

  const objPos = `${((cropX ?? 0.5) * 100).toFixed(1)}% ${((cropY ?? 0.5) * 100).toFixed(1)}%`;

  if (isNoMat) {
    return (
      <div
        onMouseDown={handleMouseDown}
        style={{
          position: 'relative',
          width: '100%',
          aspectRatio: '16 / 9',
          backgroundColor: '#090b10',
          overflow: 'hidden',
          cursor: canPan ? (dragging ? 'grabbing' : 'grab') : 'default',
        }}
      >
        {thumbSrc ? (
          <img
            src={thumbSrc}
            alt={title}
            onLoad={(e) => {
              const nw = e.currentTarget.naturalWidth;
              const nh = e.currentTarget.naturalHeight;
              if (nw > 0 && nh > 0) setNaturalAspect(nw / nh);
            }}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: objPos,
              display: 'block',
              userSelect: 'none',
            }}
            draggable={false}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-studio-textDim text-xs p-3 text-center">
            <Tv className="w-7 h-7 mb-1.5 opacity-40 text-studio-accent" />
            <span className="font-mono text-[11px] text-white/90 font-bold truncate max-w-[90%]">{title}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      onMouseDown={handleMouseDown}
      style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16 / 9',
        backgroundColor: matColor || '#F4EFE6',
        overflow: 'hidden',
        cursor: canPan ? (dragging ? 'grabbing' : 'grab') : 'default',
      }}
    >
      {/* Photo Window positioned at exact aperture coordinates */}
      <div
        style={{
          position: 'absolute',
          left: `${(x0 / canvasW) * 100}%`,
          top: `${(y0 / canvasH) * 100}%`,
          width: `${(winW / canvasW) * 100}%`,
          height: `${(winH / canvasH) * 100}%`,
          overflow: 'hidden',
          backgroundColor: '#0c0e14',
        }}
      >
        {thumbSrc ? (
          <img
            src={thumbSrc}
            alt={title}
            onLoad={(e) => {
              const nw = e.currentTarget.naturalWidth;
              const nh = e.currentTarget.naturalHeight;
              if (nw > 0 && nh > 0) setNaturalAspect(nw / nh);
            }}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              objectPosition: objPos,
              display: 'block',
              userSelect: 'none',
            }}
            draggable={false}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-studio-textDim text-xs p-3 text-center">
            <ImageIcon className="w-6 h-6 mb-1 opacity-40 text-studio-accent" />
            <span className="font-mono text-[11px] text-white/80 truncate max-w-[90%]">{title}</span>
          </div>
        )}
      </div>

      {/* Soft Samsung Frame 45-Degree Angled Bevel SVG Overlay (Single or Double Mat) */}
      <svg
        viewBox={`0 0 ${canvasW} ${canvasH}`}
        preserveAspectRatio="none"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          pointerEvents: 'none',
        }}
      >
        <defs>
          {/* Soft Samsung Frame Warm Cotton-Core Bevel Gradients with subtle optical depth */}
          <linearGradient id={`top-bevel-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c4beaf" />
            <stop offset="100%" stopColor="#ada697" />
          </linearGradient>
          <linearGradient id={`bot-bevel-${uid}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#eee9de" />
            <stop offset="100%" stopColor="#f8f6f0" />
          </linearGradient>
          <linearGradient id={`left-bevel-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#d2ccbe" />
            <stop offset="100%" stopColor="#c0baab" />
          </linearGradient>
          <linearGradient id={`right-bevel-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#e6e1d5" />
            <stop offset="100%" stopColor="#f0ebe0" />
          </linearGradient>
        </defs>

        {/* Optional Double Mat: Inner Mat Reveal Strips + Outer 45° Bevel */}
        {isDouble && (
          <g>
            {/* 4 Inner Mat Reveal Strips around the inner bevel */}
            <rect x={mx0} y={my0} width={mx1 - mx0} height={oy0 - my0} fill={innerMatColor || '#F4EFE6'} />
            <rect x={mx0} y={oy1} width={mx1 - mx0} height={my1 - oy1} fill={innerMatColor || '#F4EFE6'} />
            <rect x={mx0} y={oy0} width={ox0 - mx0} height={oy1 - oy0} fill={innerMatColor || '#F4EFE6'} />
            <rect x={ox1} y={oy0} width={mx1 - ox1} height={oy1 - oy0} fill={innerMatColor || '#F4EFE6'} />

            {/* Outer 45° Bevel Facets */}
            <polygon points={`${obx0},${oby0} ${obx1},${oby0} ${mx1},${my0} ${mx0},${my0}`} fill={`url(#top-bevel-${uid})`} />
            <polygon points={`${mx0},${my1} ${mx1},${my1} ${obx1},${oby1} ${obx0},${oby1}`} fill={`url(#bot-bevel-${uid})`} />
            <polygon points={`${obx0},${oby0} ${mx0},${my0} ${mx0},${my1} ${obx0},${oby1}`} fill={`url(#left-bevel-${uid})`} />
            <polygon points={`${mx1},${my0} ${obx1},${oby0} ${obx1},${oby1} ${mx1},${my1}`} fill={`url(#right-bevel-${uid})`} />

            {/* Outer Bevel 45° Corner Miter Seams */}
            <line x1={obx0} y1={oby0} x2={mx0} y2={my0} stroke="#beb8ae" strokeWidth="1.1" />
            <line x1={obx1} y1={oby0} x2={mx1} y2={my0} stroke="#c8c2b8" strokeWidth="1.1" />
            <line x1={obx0} y1={oby1} x2={mx0} y2={my1} stroke="#d0cac0" strokeWidth="1.1" />
            <line x1={obx1} y1={oby1} x2={mx1} y2={my1} stroke="#dcd7cd" strokeWidth="1.1" />

            {/* Subtle contact edge where outer bevel meets inner mat reveal */}
            <rect
              x={mx0}
              y={my0}
              width={mx1 - mx0}
              height={my1 - my0}
              fill="none"
              stroke="rgba(60,56,50,0.28)"
              strokeWidth="0.9"
            />
          </g>
        )}

        {/* Inner 45° Trapezoidal Bevel Facets */}
        <polygon
          points={`${ox0},${oy0} ${ox1},${oy0} ${x1},${y0} ${x0},${y0}`}
          fill={`url(#top-bevel-${uid})`}
        />
        <polygon
          points={`${x0},${y1} ${x1},${y1} ${ox1},${oy1} ${ox0},${oy1}`}
          fill={`url(#bot-bevel-${uid})`}
        />
        <polygon
          points={`${ox0},${oy0} ${x0},${y0} ${x0},${y1} ${ox0},${oy1}`}
          fill={`url(#left-bevel-${uid})`}
        />
        <polygon
          points={`${x1},${y0} ${ox1},${oy0} ${ox1},${oy1} ${x1},${y1}`}
          fill={`url(#right-bevel-${uid})`}
        />

        {/* Four Subtle 45-Degree Diagonal Corner Miter Seams */}
        <line x1={ox0} y1={oy0} x2={x0} y2={y0} stroke="#a29c90" strokeWidth="1.1" />
        <line x1={ox1} y1={oy0} x2={x1} y2={y0} stroke="#aea89c" strokeWidth="1.1" />
        <line x1={ox0} y1={oy1} x2={x0} y2={y1} stroke="#bab4a8" strokeWidth="1.1" />
        <line x1={ox1} y1={oy1} x2={x1} y2={y1} stroke="#cecac0" strokeWidth="1.1" />

        {/* Subtle Inner Bevel-to-Print Contact Line & Top Shadow Crease */}
        <rect
          x={x0}
          y={y0}
          width={winW}
          height={winH}
          fill="none"
          stroke="rgba(60,56,50,0.48)"
          strokeWidth="1.0"
        />
        <line
          x1={x0}
          y1={y0}
          x2={x1}
          y2={y0}
          stroke="rgba(40,36,30,0.32)"
          strokeWidth="1.2"
        />
      </svg>
    </div>
  );
}

export default function TvDisplaysView({
  collections = [],
  onRefreshCollections,
  onSelectPhoto,
  showGlobalToast = () => {},
}) {
  const [displays, setDisplays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedIp, setSelectedIp] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);

  // Interactive TV Mat & Aspect Studio Inspector State (for editing photos already on TV)
  const [studioPhotoIdx, setStudioPhotoIdx] = useState(null);
  const [editMatMode, setEditMatMode] = useState('studio');
  const [editMatColor, setEditMatColor] = useState('#F4EFE6');
  const [editMatPlacement, setEditMatPlacement] = useState('slim_optical');
  const [editMatAspect, setEditMatAspect] = useState('original');
  const [editMatStyle, setEditMatStyle] = useState('single');
  const [editInnerMatColor, setEditInnerMatColor] = useState('#F4EFE6');
  const [editCropX, setEditCropX] = useState(0.5);
  const [editCropY, setEditCropY] = useState(0.5);
  const [isUpdatingMat, setIsUpdatingMat] = useState(false);

  // Drag-and-drop photo reordering state
  const [draggedCardIdx, setDraggedCardIdx] = useState(null);
  const [dragOverCardIdx, setDragOverCardIdx] = useState(null);

  // Sync / Add Collection Modal State
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [syncMode, setSyncMode] = useState('additive'); // 'additive' | 'overwrite'
  const [selectedColId, setSelectedColId] = useState('');
  const [syncMatMode, setSyncMatMode] = useState('studio');
  const [syncMatColor, setSyncMatColor] = useState('#F4EFE6');
  const [syncMatPlacement, setSyncMatPlacement] = useState('slim_optical');
  const [syncMatAspect, setSyncMatAspect] = useState('original');
  const [syncMatStyle, setSyncMatStyle] = useState('single');
  const [syncInnerMatColor, setSyncInnerMatColor] = useState('#F4EFE6');
  const [syncCropX, setSyncCropX] = useState(0.5);
  const [syncCropY, setSyncCropY] = useState(0.5);
  const [syncSlideshowMins, setSyncSlideshowMins] = useState(15);
  const [isSyncing, setIsSyncing] = useState(false);
  const [colPhotos, setColPhotos] = useState([]);
  const [colPreviewIdx, setColPreviewIdx] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Add / Discover TV Modal State
  const [isAddTvModalOpen, setIsAddTvModalOpen] = useState(false);
  const [manualIp, setManualIp] = useState('');
  const [tvCustomName, setTvCustomName] = useState('');
  const [isAddingTv, setIsAddingTv] = useState(false);
  const [isScanningNetwork, setIsScanningNetwork] = useState(false);
  const [discoveredTvs, setDiscoveredTvs] = useState([]);

  // Fetch sample photos for live mat preview whenever selected collection changes
  useEffect(() => {
    if (!selectedColId) {
      setColPhotos([]);
      setColPreviewIdx(0);
      return;
    }
    let isMounted = true;
    setPreviewLoading(true);
    fetch(`/api/collections/${selectedColId}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        const photos = data.photos || [];
        setColPhotos(photos);
        setColPreviewIdx(0);
      })
      .catch(() => {
        if (isMounted) setColPhotos([]);
      })
      .finally(() => {
        if (isMounted) setPreviewLoading(false);
      });
    return () => {
      isMounted = false;
    };
  }, [selectedColId]);

  const fetchDisplays = useCallback(async () => {
    try {
      const res = await fetch('/api/samsung-tvs/displays');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const list = data.displays || [];
      setDisplays(list);
      if (list.length > 0) {
        setSelectedIp((prev) => (prev && list.some((d) => d.ip === prev) ? prev : list[0].ip));
      }
    } catch (err) {
      console.error('Failed to load TV displays:', err);
      showGlobalToast(`Error fetching TV displays: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [showGlobalToast]);

  useEffect(() => {
    fetchDisplays();
  }, [fetchDisplays]);

  const activeDisplay = displays.find((d) => d.ip === selectedIp) || displays[0] || null;
  const activePhotos = activeDisplay?.photos || [];
  const curatedPhotos = activePhotos.filter((p) => !p.is_external && p.thumb_url);
  const externalPhotos = activePhotos.filter((p) => p.is_external || !p.thumb_url);

  // Open a photo in the Interactive TV Mat & Aspect Studio
  const openPhotoInMatStudio = (idx) => {
    const target = activePhotos[idx];
    if (!target) return;
    setStudioPhotoIdx(idx);
    const pPlacement = target.mat_placement || 'slim_optical';
    setEditMatMode(target.mat_mode === 'none' || pPlacement === 'none' ? 'none' : 'studio');
    setEditMatColor(target.mat_color || '#F4EFE6');
    setEditMatPlacement(pPlacement === 'none' ? 'slim_optical' : pPlacement);
    setEditMatAspect(target.mat_aspect || 'original');
    setEditMatStyle(target.mat_style || 'single');
    setEditInnerMatColor(target.inner_mat_color || '#F4EFE6');
    setEditCropX(typeof target.crop_x === 'number' ? target.crop_x : 0.5);
    setEditCropY(typeof target.crop_y === 'number' ? target.crop_y : 0.5);
  };

  // Apply updated Mat, Border, Double/Single Style, Aspect Ratio & Crop to the Samsung Frame TV
  const handleApplyMatUpdate = async (applyToAll = false) => {
    const studioPhoto = studioPhotoIdx !== null ? activePhotos[studioPhotoIdx] : null;
    if (!activeDisplay || (!studioPhoto && !applyToAll) || isUpdatingMat) return;
    setIsUpdatingMat(true);
    try {
      showGlobalToast(
        applyToAll
          ? `Rendering soft 45° beveled ${editMatStyle === 'double' ? 'double ' : ''}mats & updating all ${curatedPhotos.length} photos on Samsung TV...`
          : `Rendering soft 45° beveled ${editMatStyle === 'double' ? 'double ' : ''}mat for "${studioPhoto.title || studioPhoto.filename}" on Samsung TV...`
      );
      const effectivePlacement = editMatMode === 'none' ? 'none' : editMatPlacement;
      const res = await fetch('/api/samsung-tvs/update-art-mat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip: activeDisplay.ip,
          content_id: studioPhoto?.content_id,
          file_hash: studioPhoto?.file_hash,
          mat_mode: editMatMode,
          mat_color: editMatColor,
          mat_placement: effectivePlacement,
          mat_aspect: editMatAspect,
          mat_style: editMatStyle,
          inner_mat_color: editInnerMatColor,
          crop_x: editCropX,
          crop_y: editCropY,
          apply_to_all: applyToAll,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Update failed (${res.status})`);
      showGlobalToast(
        applyToAll
          ? `Updated all ${data.updated_count} artworks on Samsung TV!`
          : `Updated "${studioPhoto.title || studioPhoto.filename}" on Samsung TV!`
      );
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Mat update failed: ${err.message}`);
    } finally {
      setIsUpdatingMat(false);
    }
  };

  // Reorder photos on the TV and persist sequence
  const handleReorderPhotos = async (fromIdx, toIdx) => {
    if (!activeDisplay || fromIdx === toIdx || fromIdx < 0 || toIdx < 0 || fromIdx >= activePhotos.length || toIdx >= activePhotos.length) {
      return;
    }
    const nextPhotos = [...activePhotos];
    const [moved] = nextPhotos.splice(fromIdx, 1);
    nextPhotos.splice(toIdx, 0, moved);

    // Optimistic UI update
    setDisplays((prev) =>
      prev.map((d) => (d.ip === activeDisplay.ip ? { ...d, photos: nextPhotos } : d))
    );
    if (studioPhotoIdx === fromIdx) {
      setStudioPhotoIdx(toIdx);
    } else if (studioPhotoIdx !== null) {
      if (fromIdx < studioPhotoIdx && toIdx >= studioPhotoIdx) {
        setStudioPhotoIdx(studioPhotoIdx - 1);
      } else if (fromIdx > studioPhotoIdx && toIdx <= studioPhotoIdx) {
        setStudioPhotoIdx(studioPhotoIdx + 1);
      }
    }

    try {
      const orderedIds = nextPhotos.map((p) => p.content_id || p.file_hash).filter(Boolean);
      const res = await fetch('/api/samsung-tvs/reorder-art', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip: activeDisplay.ip,
          content_ids: orderedIds,
          ordered_ids: orderedIds,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showGlobalToast(`Updated TV gallery order (${moved.title || moved.filename} → #${toIdx + 1})`);
    } catch (err) {
      showGlobalToast(`Order update failed: ${err.message}`);
      await fetchDisplays();
    }
  };

  // Scan Local Wi-Fi Network for Samsung TVs (SSDP + Subnet Probe)
  const handleScanNetworkForTvs = async () => {
    if (isScanningNetwork) return;
    setIsScanningNetwork(true);
    try {
      showGlobalToast('Scanning local Wi-Fi network for Samsung Frame TVs...');
      const res = await fetch('/api/samsung-tvs/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rescan: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Scan failed (${res.status})`);
      const found = data.tvs || [];
      setDiscoveredTvs(found);
      if (found.length > 0) {
        showGlobalToast(`Discovered ${found.length} Samsung TV${found.length === 1 ? '' : 's'} on Wi-Fi!`);
        if (!manualIp && found[0]?.ip) {
          setManualIp(found[0].ip);
          if (!tvCustomName && found[0]?.name) {
            setTvCustomName(found[0].name);
          }
        }
      } else {
        showGlobalToast('No new TVs responded to scan — verify TV is powered on & on the same Wi-Fi.');
      }
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Network scan error: ${err.message}`);
    } finally {
      setIsScanningNetwork(false);
    }
  };

  // Toggle Art Mode
  const handleToggleArtMode = async () => {
    if (!activeDisplay || actionBusy) return;
    const nextMode = activeDisplay.art_mode === 'on' ? 'off' : 'on';
    setActionBusy(true);
    try {
      const res = await fetch('/api/samsung-tvs/art-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: activeDisplay.ip, mode: nextMode }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showGlobalToast(`Samsung TV Art Mode switched ${nextMode.toUpperCase()}`);
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Art Mode toggle failed: ${err.message}`);
    } finally {
      setActionBusy(false);
    }
  };

  // Toggle Slideshow
  const handleToggleSlideshow = async (dur = null) => {
    if (!activeDisplay || actionBusy) return;
    const currentOn = Boolean(activeDisplay.slideshow?.status);
    const nextStatus = dur !== null ? 'on' : currentOn ? 'off' : 'on';
    const effectiveDur = dur !== null ? dur : activeDisplay.slideshow?.duration || 60;
    setActionBusy(true);
    try {
      const res = await fetch('/api/samsung-tvs/slideshow', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ip: activeDisplay.ip,
          duration: effectiveDur,
          status: nextStatus,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showGlobalToast(`Slideshow set to ${nextStatus.toUpperCase()} (${effectiveDur}m)`);
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Slideshow control failed: ${err.message}`);
    } finally {
      setActionBusy(false);
    }
  };

  // Select Art (Display photo immediately on TV)
  const handleSelectArt = async (contentId) => {
    if (!activeDisplay || !contentId || actionBusy) return;
    setActionBusy(true);
    try {
      const res = await fetch('/api/samsung-tvs/select-art', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: activeDisplay.ip, content_id: contentId }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showGlobalToast(`Displaying artwork ${contentId} on TV`);
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Failed to select artwork: ${err.message}`);
    } finally {
      setActionBusy(false);
    }
  };

  // Remove photo from TV hardware and local sync
  const handleRemovePhoto = async (photo) => {
    if (!activeDisplay || !photo?.content_id || actionBusy) return;
    const cid = photo.content_id;
    const pTitle = photo.title || photo.filename || cid;
    if (!window.confirm(`Remove "${pTitle}" from Samsung TV Art Mode?\n\nThis will delete it from the TV display.`)) {
      return;
    }
    setActionBusy(true);
    try {
      const res = await fetch('/api/samsung-tvs/remove-art', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: activeDisplay.ip, content_id: cid }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      showGlobalToast(`Removed "${pTitle}" from Samsung Frame TV`);
      if (studioPhotoIdx !== null) setStudioPhotoIdx(null);
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Remove failed: ${err.message}`);
    } finally {
      setActionBusy(false);
    }
  };

  // Purge legacy / unsynced artwork from TV hardware
  const handlePurgeLegacy = async () => {
    if (!activeDisplay || actionBusy) return;
    const legacyCount = externalPhotos.length;
    setActionBusy(true);
    try {
      showGlobalToast(`Cleaning ${legacyCount} unsynced items from Samsung TV...`);
      const res = await fetch('/api/samsung-tvs/purge-legacy-art', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: activeDisplay.ip, content_id: 'all' }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Purge failed (${res.status})`);
      showGlobalToast(`Cleaned ${data.purged_count ?? legacyCount} unsynced items from Frame TV`);
      await fetchDisplays();
    } catch (err) {
      showGlobalToast(`Clean unsynced failed: ${err.message}`);
    } finally {
      setActionBusy(false);
    }
  };

  const openSyncModal = (mode = 'additive') => {
    setSyncMode(mode);
    if (!selectedColId && collections.length > 0) {
      setSelectedColId(collections[0].id);
    }
    setIsSyncModalOpen(true);
  };

  // Sync Collection to TV (Additive or Overwrite)
  const handleSyncSubmit = async (e) => {
    e.preventDefault();
    if (!activeDisplay || !selectedColId || isSyncing) return;
    setIsSyncing(true);
    try {
      const targetCol = collections.find((c) => String(c.id) === String(selectedColId));
      const colName = targetCol?.name || 'Collection';
      showGlobalToast(`Syncing "${colName}" to Samsung TV (${syncMode})...`);

      const effectivePlacement = syncMatMode === 'none' ? 'none' : syncMatPlacement;
      const payload = {
        ip: activeDisplay.ip,
        collection_id: selectedColId,
        mode: syncMode,
        mat_mode: syncMatMode,
        mat_color: syncMatColor,
        mat_placement: effectivePlacement,
        mat_aspect: syncMatAspect,
        mat_style: syncMatStyle,
        inner_mat_color: syncInnerMatColor,
        crop_x: syncCropX,
        crop_y: syncCropY,
        slideshow_minutes: Number(syncSlideshowMins),
      };

      const res = await fetch('/api/samsung-tvs/sync-collection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Sync failed (${res.status})`);

      showGlobalToast(
        syncMode === 'overwrite'
          ? `Replaced TV gallery with ${data.uploaded_count} matted photos from "${colName}"`
          : `Added ${data.uploaded_count} matted photos from "${colName}" to TV`
      );
      setIsSyncModalOpen(false);
      await fetchDisplays();
    } catch (err) {
      console.error('TV sync error:', err);
      showGlobalToast(`Sync Error: ${err.message}`);
    } finally {
      setIsSyncing(false);
    }
  };

  // Add / Discover TV Submit
  const handleAddTvSubmit = async (e) => {
    e.preventDefault();
    const cleanIp = manualIp.trim();
    if (!cleanIp || isAddingTv) return;
    setIsAddingTv(true);
    try {
      const res = await fetch('/api/samsung-tvs/add-remote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: cleanIp,
          name: tvCustomName.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Failed to add TV (${res.status})`);

      showGlobalToast(`Added TV: ${cleanIp}`);
      setManualIp('');
      setTvCustomName('');
      setIsAddTvModalOpen(false);
      await fetchDisplays();
      setSelectedIp(cleanIp);
    } catch (err) {
      showGlobalToast(`Failed to add TV: ${err.message}`);
    } finally {
      setIsAddingTv(false);
    }
  };

  const studioPhoto = studioPhotoIdx !== null ? activePhotos[studioPhotoIdx] : null;
  const previewPhoto = colPhotos[colPreviewIdx] || colPhotos[0] || null;

  return (
    <div className="flex-1 flex min-h-0 bg-studio-bg text-studio-text select-none overflow-hidden">
      {/* ===================================================================== */}
      {/* LEFT SIDEBAR: Configured & Discovered Samsung Frame TVs                */}
      {/* ===================================================================== */}
      <div className="w-72 flex-shrink-0 border-r border-studio-border bg-studio-panel flex flex-col min-h-0">
        <div className="p-3.5 border-b border-studio-border space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Tv className="w-5 h-5 text-studio-accent" />
              <h2 className="font-mono text-sm font-bold text-white tracking-wide">TV DISPLAYS</h2>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={fetchDisplays}
                disabled={loading || actionBusy}
                title="Refresh TV Connection Status"
                className="p-1.5 rounded-md border border-studio-border text-studio-textMuted hover:text-white hover:border-studio-accent transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                type="button"
                onClick={() => setIsAddTvModalOpen(true)}
                title="Add or Auto-Discover Samsung Frame TV"
                className="px-2.5 py-1.5 bg-studio-accent text-studio-bg rounded-md text-xs font-bold flex items-center gap-1 hover:bg-amber-400 transition-colors shadow-sm"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add TV</span>
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={handleScanNetworkForTvs}
            disabled={isScanningNetwork}
            title="Automatically scan your local Wi-Fi subnet for Samsung Frame TVs"
            className="w-full py-1.5 px-2.5 rounded-lg bg-studio-bg hover:bg-amber-500/10 border border-studio-border hover:border-amber-500/40 text-amber-300 text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all"
          >
            <Wifi className={`w-3.5 h-3.5 ${isScanningNetwork ? 'animate-ping text-amber-400' : ''}`} />
            <span>{isScanningNetwork ? 'Scanning Wi-Fi for TVs...' : 'Scan Wi-Fi Network for TVs'}</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading ? (
            <div className="p-6 text-center text-xs text-studio-textMuted animate-pulse">
              Scanning for Samsung Frame TVs on network...
            </div>
          ) : displays.length === 0 ? (
            <div className="p-6 text-center space-y-3">
              <Tv className="w-10 h-10 text-studio-textDim mx-auto opacity-50" />
              <div className="text-xs text-studio-textMuted">No Samsung TVs registered yet.</div>
              <button
                type="button"
                onClick={() => setIsAddTvModalOpen(true)}
                className="px-3 py-1.5 bg-studio-accent/20 border border-studio-accent/40 text-amber-300 rounded text-xs font-semibold"
              >
                + Discover / Add Samsung TV
              </button>
            </div>
          ) : (
            displays.map((tv) => {
              const isSelected = selectedIp === tv.ip;
              const isOnline = Boolean(tv.online);
              const photoCount = Array.isArray(tv.photos) ? tv.photos.length : 0;
              const isArtOn = tv.art_mode === 'on';

              return (
                <div
                  key={tv.ip}
                  onClick={() => {
                    setSelectedIp(tv.ip);
                    setStudioPhotoIdx(null);
                  }}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-amber-500/10 border-amber-500/60 shadow-[0_4px_16px_rgba(245,158,11,0.15)]'
                      : 'bg-studio-bg/60 border-studio-border hover:border-studio-textMuted/40 hover:bg-studio-bg'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                            isOnline ? 'bg-emerald-400 shadow-[0_0_8px_#34d399]' : 'bg-studio-textDim'
                          }`}
                        />
                        <span className="font-semibold text-sm text-white truncate">
                          {tv.name || `Samsung TV (${tv.ip})`}
                        </span>
                      </div>
                      <div className="text-[11px] font-mono text-studio-textMuted mt-1 truncate">
                        {tv.ip} {tv.model ? `· ${tv.model}` : ''}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-studio-border/60 flex items-center justify-between text-[11px]">
                    <span className="text-studio-textMuted flex items-center gap-1">
                      <ImageIcon className="w-3.5 h-3.5 text-studio-accent" />
                      <strong className="text-white">{photoCount}</strong> photos
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-mono text-[10px] font-bold ${
                        !isOnline
                          ? 'bg-studio-panel text-studio-textDim'
                          : isArtOn
                          ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-500/30'
                          : 'bg-amber-950/60 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {!isOnline ? 'OFFLINE' : isArtOn ? 'ART MODE ON' : 'TV STANDBY'}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div className="p-3.5 border-t border-studio-border bg-studio-bg/50 text-[11px] text-studio-textMuted leading-relaxed">
          <div className="font-bold text-amber-400 mb-1 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Soft 45° Bevel · Single &amp; Double Mat</span>
          </div>
          Click any photo card to open the <strong>TV Mat &amp; Aspect Studio</strong> — choose Single or Double Mat, Slim Optical or Exhibition borders, and Original or 16:9+Mat aspect ratios.
        </div>
      </div>

      {/* ===================================================================== */}
      {/* CENTER / RIGHT WORKSPACE: Active TV Gallery & Live Mat Studio          */}
      {/* ===================================================================== */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {!activeDisplay ? (
          <div className="flex-1 flex items-center justify-center p-12 text-center">
            <div className="max-w-md space-y-3">
              <Tv className="w-12 h-12 text-studio-accent mx-auto opacity-60" />
              <h3 className="text-base font-bold text-white">Select or Discover a Samsung Frame TV</h3>
              <p className="text-xs text-studio-textMuted leading-relaxed">
                Scan your Wi-Fi network or connect via IP to curate artwork, customize Single &amp; Double 45° beveled mats, reorder sequences, and control slideshows.
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Top TV Control Header */}
            <div className="px-6 py-3.5 border-b border-studio-border bg-studio-panel/80 flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2.5">
                  <h2 className="text-base font-bold text-white flex items-center gap-2">
                    <span>📺 {activeDisplay.name || `Samsung Frame TV`}</span>
                  </h2>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold flex items-center gap-1 ${
                      activeDisplay.online
                        ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/40'
                        : 'bg-red-500/15 text-red-300 border border-red-500/40'
                    }`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${activeDisplay.online ? 'bg-emerald-400' : 'bg-red-400'}`} />
                    {activeDisplay.online ? 'Online' : 'Unreachable'}
                  </span>
                </div>
                <div className="text-xs font-mono text-studio-textMuted mt-0.5">
                  IP: <span className="text-white">{activeDisplay.ip}</span>
                  {activeDisplay.model ? ` · Model: ${activeDisplay.model}` : ''}
                  {' · '}4K UHD (3840×2160)
                </div>
              </div>

              {/* Hardware Quick Controls */}
              <div className="flex items-center flex-wrap gap-2">
                <button
                  type="button"
                  onClick={handleToggleArtMode}
                  disabled={actionBusy || !activeDisplay.online}
                  title="Toggle Frame TV Art Mode ON or OFF"
                  className={`px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 transition-all ${
                    activeDisplay.art_mode === 'on'
                      ? 'bg-emerald-950/60 border-emerald-500/60 text-emerald-300'
                      : 'bg-studio-bg border-studio-border text-studio-textMuted hover:text-white'
                  }`}
                >
                  <span>🖼️</span>
                  <span>Art Mode: {activeDisplay.art_mode === 'on' ? 'ON' : 'OFF'}</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleToggleSlideshow()}
                  disabled={actionBusy || !activeDisplay.online}
                  title="Toggle Persistent Automatic Slideshow"
                  className={`px-3 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 transition-all ${
                    activeDisplay.slideshow?.status
                      ? 'bg-blue-950/60 border-blue-500/60 text-blue-300'
                      : 'bg-studio-bg border-studio-border text-studio-textMuted hover:text-white'
                  }`}
                >
                  {activeDisplay.slideshow?.status ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                  <span>Slideshow: {activeDisplay.slideshow?.status ? 'ACTIVE' : 'OFF'}</span>
                </button>

                <div className="relative flex items-center bg-studio-bg border border-studio-border rounded-lg px-2 py-1 text-xs text-studio-textMuted">
                  <Clock className="w-3.5 h-3.5 text-studio-accent mr-1.5" />
                  <select
                    value={activeDisplay.slideshow?.duration || 15}
                    onChange={(e) => handleToggleSlideshow(Number(e.target.value))}
                    disabled={actionBusy || !activeDisplay.online}
                    className="bg-transparent text-white font-mono text-xs outline-none cursor-pointer pr-3"
                  >
                    {SLIDESHOW_INTERVALS.map((intv) => (
                      <option key={intv.value} value={intv.value} className="bg-studio-panel text-white">
                        {intv.label}
                      </option>
                    ))}
                  </select>
                </div>

                {curatedPhotos.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      if (studioPhotoIdx !== null) {
                        setStudioPhotoIdx(null);
                      } else {
                        openPhotoInMatStudio(0);
                      }
                    }}
                    className={`px-3.5 py-1.5 rounded-lg border text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm ${
                      studioPhotoIdx !== null
                        ? 'bg-amber-500 text-studio-bg border-amber-400'
                        : 'bg-amber-500/15 border-amber-500/50 text-amber-300 hover:bg-amber-500/25'
                    }`}
                  >
                    <Palette className="w-3.5 h-3.5" />
                    <span>{studioPhotoIdx !== null ? 'Close Mat Studio' : '🎨 Mat, Border & Aspect Studio'}</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => openSyncModal('additive')}
                  disabled={actionBusy || !activeDisplay.online}
                  className="px-3.5 py-1.5 bg-amber-500/20 border border-amber-500/50 text-amber-300 rounded-lg text-xs font-bold flex items-center gap-1.5 hover:bg-amber-500/30 transition-all shadow-sm"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add from Collection</span>
                </button>

                <button
                  type="button"
                  onClick={() => openSyncModal('overwrite')}
                  disabled={actionBusy || !activeDisplay.online}
                  className="px-3.5 py-1.5 bg-purple-500/20 border border-purple-500/50 text-purple-300 rounded-lg text-xs font-bold flex items-center gap-1.5 hover:bg-purple-500/30 transition-all shadow-sm"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Replace Theme</span>
                </button>

                {externalPhotos.length > 0 && (
                  <button
                    type="button"
                    onClick={handlePurgeLegacy}
                    disabled={actionBusy || !activeDisplay.online}
                    title="Fast batch delete of unsynced legacy items on TV hardware"
                    className="px-3 py-1.5 bg-red-950/50 border border-red-500/40 text-red-300 rounded-lg text-xs font-bold flex items-center gap-1.5 hover:bg-red-900/50 transition-all shadow-sm"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Clean Unsynced ({externalPhotos.length})</span>
                  </button>
                )}
              </div>
            </div>

            {/* ================================================================= */}
            {/* INTERACTIVE TV MAT, BORDER & ASPECT RATIO STUDIO WORKBENCH         */}
            {/* ================================================================= */}
            {studioPhoto && (
              <div className="border-b border-amber-500/40 bg-[#0d1017] px-6 py-4 shadow-2xl">
                <div className="max-w-[1600px] w-full mx-auto flex flex-col xl:flex-row gap-6 items-stretch">
                  {/* LEFT: Live 16:9 Samsung Frame TV Canvas with Soft 3/4 45° Angled Bevel */}
                  <div className="xl:w-[48%] flex flex-col justify-between bg-black/80 p-3.5 rounded-xl border border-neutral-700 shadow-2xl">
                    <div className="flex items-center justify-between mb-2 px-1">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-amber-500/20 border border-amber-500/40 text-amber-300 font-mono text-[10px] font-bold rounded uppercase">
                          Live 4K Frame TV View
                        </span>
                        <span className="text-xs font-bold text-white truncate max-w-[260px]">
                          {studioPhoto.title || studioPhoto.filename}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openPhotoInMatStudio((studioPhotoIdx - 1 + activePhotos.length) % activePhotos.length)}
                          className="p-1 rounded bg-studio-panel border border-studio-border text-studio-textMuted hover:text-white"
                          title="Previous TV Photo"
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </button>
                        <span className="text-[11px] font-mono text-studio-textMuted px-1.5">
                          #{studioPhotoIdx + 1} of {activePhotos.length}
                        </span>
                        <button
                          type="button"
                          onClick={() => openPhotoInMatStudio((studioPhotoIdx + 1) % activePhotos.length)}
                          className="p-1 rounded bg-studio-panel border border-studio-border text-studio-textMuted hover:text-white"
                          title="Next TV Photo"
                        >
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    {/* Simulated Physical Frame TV Bezel */}
                    <div className="p-2 bg-[#14161d] rounded-lg border-2 border-neutral-800 shadow-inner">
                      <FrameTvMatPreview
                        thumbSrc={studioPhoto.thumb_url || (studioPhoto.file_hash ? `/previews_1600/${studioPhoto.file_hash}.webp` : null)}
                        title={studioPhoto.title || studioPhoto.filename}
                        matMode={editMatMode}
                        matColor={editMatColor}
                        matPlacement={editMatPlacement}
                        matAspect={editMatAspect}
                        matStyle={editMatStyle}
                        innerMatColor={editInnerMatColor}
                        cropX={editCropX}
                        cropY={editCropY}
                        interactivePan={true}
                        onCropChange={(nx, ny) => {
                          setEditCropX(nx);
                          setEditCropY(ny);
                        }}
                        bevelThickness={10}
                      />
                    </div>

                    <div className="mt-2 flex items-center justify-between text-[11px] text-studio-textMuted px-1">
                      <span className="flex items-center gap-1.5">
                        <Move className="w-3.5 h-3.5 text-amber-400" />
                        <span>
                          {editMatMode === 'none' || editMatAspect !== 'original'
                            ? 'Drag directly on the photo above to pan & position your crop underneath the mat'
                            : 'Presenting 100% uncropped Lightroom/native aspect ratio inside soft 45° beveled mat'}
                        </span>
                      </span>
                      {(editCropX !== 0.5 || editCropY !== 0.5) && (
                        <button
                          type="button"
                          onClick={() => {
                            setEditCropX(0.5);
                            setEditCropY(0.5);
                          }}
                          className="text-amber-400 hover:underline font-mono text-[10px]"
                        >
                          Reset Center
                        </button>
                      )}
                    </div>
                  </div>

                  {/* RIGHT: Expanded Full-Width Aspect Ratio, Single/Double Mat, Border & Color Controls */}
                  <div className="xl:w-[52%] flex flex-col justify-between space-y-3.5 bg-studio-panel/90 p-4 rounded-xl border border-studio-border">
                    <div className="space-y-3.5">
                      {/* 1. Window Aspect Ratio Selector (Original Ratio + Mat vs 16:9 Crop + Mat vs Panos) */}
                      <div>
                        <div className="flex items-center justify-between mb-1.5">
                          <label className="text-[11px] font-bold uppercase tracking-wider text-amber-300">
                            1. Photo Window Aspect Ratio (Keep Original Ratio or Crop Underneath Mat)
                          </label>
                          <span className="text-[10.5px] font-mono text-studio-textMuted">
                            {ASPECT_RATIO_OPTIONS.find((a) => a.id === editMatAspect)?.desc}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {ASPECT_RATIO_OPTIONS.map((opt) => {
                            const active = editMatMode !== 'none' && editMatAspect === opt.id;
                            return (
                              <button
                                key={opt.id}
                                type="button"
                                onClick={() => {
                                  setEditMatMode('studio');
                                  setEditMatAspect(opt.id);
                                }}
                                title={opt.desc}
                                className={`px-3 py-1.5 rounded-lg border text-[11px] font-mono font-bold whitespace-nowrap transition-all ${
                                  active
                                    ? 'bg-amber-500 text-studio-bg border-amber-400 shadow-sm'
                                    : 'bg-studio-bg border-studio-border text-studio-textMuted hover:text-white'
                                }`}
                              >
                                {opt.shortLabel || opt.label}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* 2. Mat Border Size, Optical Placement & Single vs Double Mat */}
                      <div>
                        <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                          <label className="text-[11px] font-bold uppercase tracking-wider text-amber-300">
                            2. Mat Border Width &amp; Bevel Style
                          </label>
                          {/* Single Mat vs Double Mat Toggle */}
                          {editMatMode !== 'none' && (
                            <div className="flex items-center gap-1 bg-studio-bg p-0.5 rounded-lg border border-studio-border">
                              <button
                                type="button"
                                onClick={() => setEditMatStyle('single')}
                                className={`px-2.5 py-1 rounded-md text-[10.5px] font-bold flex items-center gap-1 transition-all ${
                                  editMatStyle === 'single'
                                    ? 'bg-amber-500 text-studio-bg shadow-sm'
                                    : 'text-studio-textMuted hover:text-white'
                                }`}
                              >
                                <span>Single Mat (1 Bevel)</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditMatStyle('double')}
                                className={`px-2.5 py-1 rounded-md text-[10.5px] font-bold flex items-center gap-1 transition-all ${
                                  editMatStyle === 'double'
                                    ? 'bg-amber-500 text-studio-bg shadow-sm'
                                    : 'text-studio-textMuted hover:text-white'
                                }`}
                              >
                                <Layers className="w-3 h-3" />
                                <span>Double Mat (Layered 2-Bevel)</span>
                              </button>
                            </div>
                          )}
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
                          {BORDER_STYLE_OPTIONS.map((bOpt) => {
                            const isSelected =
                              (bOpt.id === 'none' && editMatMode === 'none') ||
                              (bOpt.id !== 'none' && editMatMode === 'studio' && editMatPlacement === bOpt.id);
                            return (
                              <button
                                key={bOpt.id}
                                type="button"
                                onClick={() => {
                                  if (bOpt.id === 'none') {
                                    setEditMatMode('none');
                                  } else {
                                    setEditMatMode('studio');
                                    setEditMatPlacement(bOpt.id);
                                  }
                                }}
                                title={bOpt.desc}
                                className={`p-2 rounded-lg border text-left transition-all ${
                                  isSelected
                                    ? 'bg-amber-500/20 border-amber-400 text-white font-bold ring-1 ring-amber-400'
                                    : 'bg-studio-bg border-studio-border text-studio-textMuted hover:text-white'
                                }`}
                              >
                                <div className="text-[11px] leading-tight whitespace-nowrap">{bOpt.label}</div>
                                <div className="text-[9.5px] text-studio-textDim truncate mt-0.5">{bOpt.desc}</div>
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* 3. Outer & Inner Museum Mat Board Color Studio (Checkerboard + Tone Variations) */}
                      {editMatMode === 'studio' && (
                        <div className="pt-1">
                          <MatColorPicker
                            color={editMatColor}
                            onChange={setEditMatColor}
                            isDoubleMat={editMatStyle === 'double'}
                            innerColor={editInnerMatColor}
                            onInnerChange={setEditInnerMatColor}
                            compact={false}
                          />
                        </div>
                      )}
                    </div>

                    {/* Balanced, Stretched-Out 3-Column Studio Action Footer */}
                    <div className="pt-3.5 border-t border-studio-border grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <button
                        type="button"
                        onClick={() => setStudioPhotoIdx(null)}
                        className="w-full py-2.5 px-4 bg-studio-bg border border-studio-border text-studio-textMuted rounded-xl text-xs font-bold hover:text-white hover:border-studio-textMuted transition-all flex items-center justify-center gap-1.5"
                      >
                        <span>Close Studio</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleApplyMatUpdate(true)}
                        disabled={isUpdatingMat || !activeDisplay.online}
                        className="w-full py-2.5 px-4 bg-purple-500/20 border border-purple-500/50 text-purple-200 rounded-xl text-xs font-bold hover:bg-purple-500/30 transition-all flex items-center justify-center gap-1.5"
                      >
                        <span>
                          {isUpdatingMat ? 'Updating All TV Art...' : `✨ Apply Style to All ${curatedPhotos.length} Photos`}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleApplyMatUpdate(false)}
                        disabled={isUpdatingMat || !activeDisplay.online}
                        className="w-full py-2.5 px-4 bg-studio-accent text-studio-bg rounded-xl text-xs font-bold hover:bg-amber-400 transition-all shadow-lg flex items-center justify-center gap-1.5"
                      >
                        <Check className="w-4 h-4" />
                        <span>{isUpdatingMat ? 'Rendering 4K Bevel...' : 'Update This Photo on TV'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ================================================================= */}
            {/* PHOTOS GRID AREA (With Drag-and-Drop & Button Reordering)         */}
            {/* ================================================================= */}
            <div className="flex-1 overflow-y-auto p-6">
              {activePhotos.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-studio-border/60 rounded-2xl max-w-2xl mx-auto">
                  <Tv className="w-16 h-16 text-studio-textDim opacity-40 mb-4" />
                  <h3 className="text-lg font-bold text-white mb-2">No Photos Loaded on This Frame TV</h3>
                  <p className="text-sm text-studio-textMuted max-w-md mb-6 leading-relaxed">
                    Synchronize your curated Collections with 4K 45°-beveled mats in their natural aspect ratio and persistent slideshows.
                  </p>
                  <button
                    type="button"
                    onClick={() => openSyncModal('additive')}
                    className="px-5 py-2.5 bg-studio-accent text-studio-bg rounded-xl font-bold text-sm flex items-center gap-2 hover:bg-amber-400 transition-all shadow-lg"
                  >
                    <Plus className="w-4 h-4" />
                    <span>Push a Collection to TV</span>
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-studio-textMuted px-1">
                    <span>
                      Curated Art on Display: <strong className="text-white font-mono">{curatedPhotos.length}</strong> photos
                      {externalPhotos.length > 0 ? ` (+ ${externalPhotos.length} unsynced TV items)` : ''}
                    </span>
                    <span className="text-amber-300/90 font-medium">
                      💡 Drag cards or use <strong>◀ / ▶</strong> to reorder sequence · Click any photo to open the <strong>Single/Double Mat &amp; Aspect Studio</strong>.
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                    {activePhotos.map((photo, idx) => {
                      const isCurrentlyActive = activeDisplay.current_content_id === photo.content_id;
                      const isBeingEdited = studioPhotoIdx === idx;
                      const isDragOver = dragOverCardIdx === idx && draggedCardIdx !== idx;
                      const thumbSrc = photo.thumb_url || (photo.file_hash ? `/previews_1600/${photo.file_hash}.webp` : null);
                      const pMatMode = isBeingEdited ? editMatMode : (photo.mat_mode || 'studio');
                      const pMatColor = isBeingEdited ? editMatColor : (photo.mat_color || '#F4EFE6');
                      const pMatPlacement = isBeingEdited ? editMatPlacement : (photo.mat_placement || 'slim_optical');
                      const pMatAspect = isBeingEdited ? editMatAspect : (photo.mat_aspect || 'original');
                      const pMatStyle = isBeingEdited ? editMatStyle : (photo.mat_style || 'single');
                      const pInnerMatColor = isBeingEdited ? editInnerMatColor : (photo.inner_mat_color || '#F4EFE6');
                      const pCropX = isBeingEdited ? editCropX : (photo.crop_x ?? 0.5);
                      const pCropY = isBeingEdited ? editCropY : (photo.crop_y ?? 0.5);

                      return (
                        <div
                          key={photo.content_id || idx}
                          draggable={!photo.is_external}
                          onDragStart={() => setDraggedCardIdx(idx)}
                          onDragOver={(e) => {
                            e.preventDefault();
                            if (dragOverCardIdx !== idx) setDragOverCardIdx(idx);
                          }}
                          onDragLeave={() => {
                            if (dragOverCardIdx === idx) setDragOverCardIdx(null);
                          }}
                          onDrop={(e) => {
                            e.preventDefault();
                            const from = draggedCardIdx;
                            setDraggedCardIdx(null);
                            setDragOverCardIdx(null);
                            if (from !== null && from !== idx) {
                              handleReorderPhotos(from, idx);
                            }
                          }}
                          onDragEnd={() => {
                            setDraggedCardIdx(null);
                            setDragOverCardIdx(null);
                          }}
                          onClick={() => {
                            if (!photo.is_external) openPhotoInMatStudio(idx);
                          }}
                          className={`group relative rounded-xl border overflow-hidden bg-studio-panel transition-all cursor-pointer ${
                            isDragOver
                              ? 'border-amber-300 ring-2 ring-amber-300 scale-[1.01]'
                              : isBeingEdited
                              ? 'border-amber-400 ring-2 ring-amber-400 shadow-[0_0_24px_rgba(245,158,11,0.35)]'
                              : isCurrentlyActive
                              ? 'border-emerald-400 shadow-[0_0_20px_rgba(16,185,129,0.3)] ring-2 ring-emerald-500/50'
                              : 'border-studio-border hover:border-studio-accent/60 hover:shadow-lg'
                          }`}
                        >
                          {/* 16:9 Frame TV Preview with Soft 3/4 45° Angled Bevel */}
                          <div className="relative">
                            <FrameTvMatPreview
                              thumbSrc={thumbSrc}
                              title={photo.title || photo.filename || photo.content_id}
                              matMode={pMatMode}
                              matColor={pMatColor}
                              matPlacement={pMatPlacement}
                              matAspect={pMatAspect}
                              matStyle={pMatStyle}
                              innerMatColor={pInnerMatColor}
                              cropX={pCropX}
                              cropY={pCropY}
                              bevelThickness={8}
                            />

                            {/* Sequence Index Badge + Active on TV Badge */}
                            <div className="absolute top-2 left-2 flex items-center gap-1.5 z-20">
                              <span className="bg-black/80 backdrop-blur-sm text-white/90 border border-white/15 font-mono font-bold text-[10px] px-1.5 py-0.5 rounded flex items-center gap-0.5">
                                <GripVertical className="w-2.5 h-2.5 text-studio-textMuted" />
                                <span>#{idx + 1}</span>
                              </span>
                              {isCurrentlyActive && (
                                <span className="bg-emerald-500 text-studio-bg font-bold text-[10px] uppercase px-2 py-0.5 rounded shadow-md flex items-center gap-1">
                                  <span>📺</span>
                                  <span>On TV Now</span>
                                </span>
                              )}
                            </div>

                            {/* Aspect Ratio & Mat Pill Badge */}
                            {!photo.is_external && (
                              <div className="absolute bottom-2 left-2 bg-black/75 backdrop-blur-sm text-amber-300 border border-amber-500/30 font-mono text-[9.5px] px-1.5 py-0.5 rounded z-20">
                                {pMatMode === 'none' || pMatPlacement === 'none'
                                  ? 'Full 16:9 Bleed'
                                  : `${pMatAspect === 'original' ? 'Original Ratio' : pMatAspect} · ${pMatStyle === 'double' ? 'Double Mat' : '45° Bevel'}`}
                              </div>
                            )}

                            {/* Hover Actions Overlay */}
                            <div
                              onClick={(e) => e.stopPropagation()}
                              className="absolute inset-0 bg-black/65 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2 p-3 z-30"
                            >
                              {!isCurrentlyActive && (
                                <button
                                  type="button"
                                  onClick={() => handleSelectArt(photo.content_id)}
                                  disabled={actionBusy || !activeDisplay.online}
                                  className="px-2.5 py-1.5 bg-emerald-500 text-studio-bg rounded-lg font-bold text-[11px] flex items-center gap-1 hover:bg-emerald-400 transition-transform active:scale-95 shadow-md"
                                >
                                  <Eye className="w-3.5 h-3.5" />
                                  <span>Display Now</span>
                                </button>
                              )}
                              {!photo.is_external && (
                                <button
                                  type="button"
                                  onClick={() => openPhotoInMatStudio(idx)}
                                  className="px-2.5 py-1.5 bg-amber-500 text-studio-bg rounded-lg font-bold text-[11px] flex items-center gap-1 hover:bg-amber-400 transition-transform active:scale-95 shadow-md"
                                >
                                  <Palette className="w-3.5 h-3.5" />
                                  <span>Mat &amp; Aspect</span>
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleRemovePhoto(photo)}
                                disabled={actionBusy || !activeDisplay.online}
                                className="px-2.5 py-1.5 bg-red-600/90 text-white rounded-lg font-bold text-[11px] flex items-center gap-1 hover:bg-red-500 transition-transform active:scale-95 shadow-md"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>Remove</span>
                              </button>
                            </div>
                          </div>

                          {/* Card Footer Metadata + Reorder Arrows + Direct Mat Button */}
                          <div className="p-2.5 flex items-center justify-between gap-1.5 text-xs">
                            <div className="min-w-0 flex-1">
                              <div className="font-semibold text-white truncate" title={photo.title || photo.filename}>
                                {photo.title || photo.filename || photo.content_id}
                              </div>
                              <div className="text-[10px] font-mono text-studio-textMuted flex items-center gap-2 mt-0.5">
                                <span>{photo.shoot_date || '4K Art Plate'}</span>
                                {photo.mat_color && (
                                  <span className="flex items-center gap-1">
                                    <span
                                      className="w-2.5 h-2.5 rounded-full border border-white/30 inline-block"
                                      style={{ backgroundColor: pMatColor }}
                                    />
                                    <span>{pMatStyle === 'double' ? '2× Mat' : '45° Mat'}</span>
                                  </span>
                                )}
                              </div>
                            </div>

                            {!photo.is_external && (
                              <div className="flex items-center gap-1 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
                                <button
                                  type="button"
                                  disabled={idx === 0}
                                  onClick={() => handleReorderPhotos(idx, idx - 1)}
                                  title="Move Earlier in Sequence"
                                  className="p-1 rounded bg-studio-bg border border-studio-border text-studio-textMuted hover:text-white disabled:opacity-30"
                                >
                                  <ArrowLeft className="w-3 h-3" />
                                </button>
                                <button
                                  type="button"
                                  disabled={idx === activePhotos.length - 1}
                                  onClick={() => handleReorderPhotos(idx, idx + 1)}
                                  title="Move Later in Sequence"
                                  className="p-1 rounded bg-studio-bg border border-studio-border text-studio-textMuted hover:text-white disabled:opacity-30"
                                >
                                  <ArrowRight className="w-3 h-3" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => openPhotoInMatStudio(idx)}
                                  className="px-2 py-1 rounded bg-amber-500/15 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 font-mono text-[10px] font-bold flex items-center gap-1"
                                  title="Customize Mat Color, Single/Double Bevel & Aspect Ratio"
                                >
                                  <Sliders className="w-3 h-3" />
                                  <span>Mat</span>
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* ===================================================================== */}
      {/* MODAL 1: SYNC COLLECTION TO SAMSUNG TV (Additive or Overwrite Theme)   */}
      {/* ===================================================================== */}
      {isSyncModalOpen && activeDisplay && (
        <div
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => !isSyncing && setIsSyncModalOpen(false)}
        >
          <div
            className="bg-studio-panel border border-studio-border rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-4 max-h-[92vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-studio-border pb-3">
              <div className="flex items-center gap-2.5">
                <Tv className="w-5 h-5 text-studio-accent" />
                <h3 className="text-base font-bold text-white">
                  {syncMode === 'overwrite'
                    ? `Replace Theme on ${activeDisplay.name || activeDisplay.ip}`
                    : `Add Collection to ${activeDisplay.name || activeDisplay.ip}`}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => !isSyncing && setIsSyncModalOpen(false)}
                className="text-studio-textMuted hover:text-white text-sm font-mono"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSyncSubmit} className="space-y-4 text-xs">
              {/* Sync Mode Selector */}
              <div className="grid grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => setSyncMode('additive')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    syncMode === 'additive'
                      ? 'bg-amber-500/15 border-amber-500 text-white'
                      : 'bg-studio-bg border-studio-border text-studio-textMuted'
                  }`}
                >
                  <div className="font-bold text-amber-300">➕ Additive Curate</div>
                  <div className="text-[10.5px] opacity-80">Appends photos alongside existing TV art.</div>
                </button>
                <button
                  type="button"
                  onClick={() => setSyncMode('overwrite')}
                  className={`p-2.5 rounded-xl border text-left transition-all ${
                    syncMode === 'overwrite'
                      ? 'bg-purple-500/15 border-purple-500 text-white'
                      : 'bg-studio-bg border-studio-border text-studio-textMuted'
                  }`}
                >
                  <div className="font-bold text-purple-300">🔄 Replace Theme (Overwrite)</div>
                  <div className="text-[10.5px] opacity-80">Clears old curated photos &amp; loops only this collection.</div>
                </button>
              </div>

              {/* Collection Picker */}
              <div>
                <label className="block text-studio-textMuted font-semibold mb-1 uppercase text-[11px]">
                  Select Collection to Push:
                </label>
                <select
                  value={selectedColId}
                  onChange={(e) => setSelectedColId(e.target.value)}
                  required
                  className="w-full bg-studio-bg border border-studio-border rounded-lg p-2.5 text-white text-xs outline-none focus:border-studio-accent"
                >
                  <option value="">-- Choose a Curated Collection --</option>
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      📚 {c.name} ({c.item_count || c.photo_count || 0} photos)
                    </option>
                  ))}
                </select>
              </div>

              {/* Aspect Ratio, Single/Double Mat & Border Size Controls */}
              <div className="space-y-3.5 bg-studio-bg/70 p-4 rounded-xl border border-studio-border">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[11px] font-bold text-amber-300 uppercase tracking-wider">
                      1. Photo Window Aspect Ratio:
                    </span>
                    <span className="text-[10.5px] font-mono text-studio-textMuted">
                      {ASPECT_RATIO_OPTIONS.find((a) => a.id === syncMatAspect)?.desc}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {ASPECT_RATIO_OPTIONS.map((opt) => {
                      const active = syncMatMode !== 'none' && syncMatAspect === opt.id;
                      return (
                        <button
                          key={opt.id}
                          type="button"
                          onClick={() => {
                            setSyncMatMode('studio');
                            setSyncMatAspect(opt.id);
                          }}
                          className={`px-3 py-1.5 rounded-lg border text-[11px] font-mono font-bold whitespace-nowrap transition-all ${
                            active
                              ? 'bg-amber-500 text-studio-bg border-amber-400'
                              : 'bg-studio-panel border-studio-border text-studio-textMuted hover:text-white'
                          }`}
                        >
                          {opt.shortLabel || opt.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                    <span className="text-[11px] font-bold text-amber-300 uppercase tracking-wider">
                      2. Mat Border Width &amp; Bevel Style:
                    </span>
                    {syncMatMode !== 'none' && (
                      <div className="flex items-center gap-1 bg-studio-panel p-0.5 rounded-lg border border-studio-border">
                        <button
                          type="button"
                          onClick={() => setSyncMatStyle('single')}
                          className={`px-2.5 py-1 rounded-md text-[10.5px] font-bold transition-all ${
                            syncMatStyle === 'single'
                              ? 'bg-amber-500 text-studio-bg'
                              : 'text-studio-textMuted hover:text-white'
                          }`}
                        >
                          Single Mat (1 Bevel)
                        </button>
                        <button
                          type="button"
                          onClick={() => setSyncMatStyle('double')}
                          className={`px-2.5 py-1 rounded-md text-[10.5px] font-bold transition-all ${
                            syncMatStyle === 'double'
                              ? 'bg-amber-500 text-studio-bg'
                              : 'text-studio-textMuted hover:text-white'
                          }`}
                        >
                          Double Mat (2 Bevels)
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
                    {BORDER_STYLE_OPTIONS.map((bOpt) => {
                      const isSelected =
                        (bOpt.id === 'none' && syncMatMode === 'none') ||
                        (bOpt.id !== 'none' && syncMatMode === 'studio' && syncMatPlacement === bOpt.id);
                      return (
                        <button
                          key={bOpt.id}
                          type="button"
                          onClick={() => {
                            if (bOpt.id === 'none') {
                              setSyncMatMode('none');
                            } else {
                              setSyncMatMode('studio');
                              setSyncMatPlacement(bOpt.id);
                            }
                          }}
                          className={`p-2 rounded-lg border text-left transition-all ${
                            isSelected
                              ? 'bg-amber-500/20 border-amber-400 text-white font-bold'
                              : 'bg-studio-panel border-studio-border text-studio-textMuted hover:text-white'
                          }`}
                        >
                          <div className="text-[11px] whitespace-nowrap">{bOpt.label}</div>
                          <div className="text-[9.5px] text-studio-textDim truncate">{bOpt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {syncMatMode === 'studio' && (
                  <div className="pt-1">
                    <MatColorPicker
                      color={syncMatColor}
                      onChange={setSyncMatColor}
                      isDoubleMat={syncMatStyle === 'double'}
                      innerColor={syncInnerMatColor}
                      onInnerChange={setSyncInnerMatColor}
                      compact={false}
                    />
                  </div>
                )}
              </div>

              {/* Live Pre-Push Visual Preview Card with Collection Photo Switcher */}
              <div className="space-y-2 bg-black/80 p-3 rounded-xl border border-neutral-700">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-amber-300 uppercase font-bold tracking-wider">
                    👁️ Live 4K Frame TV Preview (Soft 45° Angled Bevel)
                  </span>
                  {colPhotos.length > 1 && (
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => setColPreviewIdx((colPreviewIdx - 1 + colPhotos.length) % colPhotos.length)}
                        className="px-1.5 py-0.5 bg-studio-panel border border-studio-border rounded text-white"
                      >
                        ◀
                      </button>
                      <span className="font-mono text-[10.5px] text-studio-textMuted">
                        Photo {colPreviewIdx + 1} of {colPhotos.length}
                      </span>
                      <button
                        type="button"
                        onClick={() => setColPreviewIdx((colPreviewIdx + 1) % colPhotos.length)}
                        className="px-1.5 py-0.5 bg-studio-panel border border-studio-border rounded text-white"
                      >
                        ▶
                      </button>
                    </div>
                  )}
                </div>

                <FrameTvMatPreview
                  thumbSrc={previewPhoto?.file_hash ? `/previews_1600/${previewPhoto.file_hash}.webp` : null}
                  title={
                    previewLoading
                      ? 'Loading collection sample...'
                      : previewPhoto?.filename || previewPhoto?.title || 'Select a collection above'
                  }
                  matMode={syncMatMode}
                  matColor={syncMatColor}
                  matPlacement={syncMatPlacement}
                  matAspect={syncMatAspect}
                  matStyle={syncMatStyle}
                  innerMatColor={syncInnerMatColor}
                  cropX={syncCropX}
                  cropY={syncCropY}
                  interactivePan={true}
                  onCropChange={(nx, ny) => {
                    setSyncCropX(nx);
                    setSyncCropY(ny);
                  }}
                  bevelThickness={10}
                />
              </div>

              {/* Slideshow Interval */}
              <div>
                <label className="block text-studio-textMuted font-semibold mb-1 uppercase text-[11px]">
                  Automatic Slideshow Interval:
                </label>
                <select
                  value={syncSlideshowMins}
                  onChange={(e) => setSyncSlideshowMins(Number(e.target.value))}
                  className="w-full bg-studio-bg border border-studio-border rounded-lg p-2.5 text-white text-xs outline-none focus:border-studio-accent"
                >
                  {SLIDESHOW_INTERVALS.map((intv) => (
                    <option key={intv.value} value={intv.value}>
                      ⏱️ {intv.label} per photo
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-studio-border">
                <button
                  type="button"
                  onClick={() => setIsSyncModalOpen(false)}
                  disabled={isSyncing}
                  className="px-4 py-2 bg-studio-bg border border-studio-border text-studio-text rounded-lg text-xs font-semibold hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSyncing || !selectedColId}
                  className="px-5 py-2 bg-studio-accent text-studio-bg rounded-lg text-xs font-bold hover:bg-amber-400 transition-all shadow-md"
                >
                  {isSyncing
                    ? 'Rendering 45° Bevel & Uploading...'
                    : syncMode === 'overwrite'
                    ? '🔄 Replace & Sync to TV'
                    : '➕ Add & Sync to TV'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ===================================================================== */}
      {/* MODAL 2: ADD / DISCOVER SAMSUNG TV (Wi-Fi Auto-Scan or Manual IP)     */}
      {/* ===================================================================== */}
      {isAddTvModalOpen && (
        <div
          className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => !isAddingTv && setIsAddTvModalOpen(false)}
        >
          <div
            className="bg-studio-panel border border-studio-border rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-studio-border pb-3">
              <div className="flex items-center gap-2">
                <Tv className="w-5 h-5 text-studio-accent" />
                <h3 className="text-base font-bold text-white">Discover or Add Samsung Frame TV</h3>
              </div>
              <button
                type="button"
                onClick={() => !isAddingTv && setIsAddTvModalOpen(false)}
                className="text-studio-textMuted hover:text-white text-sm font-mono"
              >
                ✕
              </button>
            </div>

            {/* Automatic Wi-Fi Network Discovery Section */}
            <div className="p-3.5 rounded-xl bg-studio-bg/90 border border-amber-500/30 space-y-2.5 text-xs">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="font-bold text-amber-300 flex items-center gap-1.5">
                    <Wifi className="w-4 h-4" />
                    <span>Auto-Discover TVs on Local Wi-Fi</span>
                  </div>
                  <div className="text-[11px] text-studio-textMuted mt-0.5">
                    Scans your local network for Samsung Frame TVs (ports 8001/8002 &amp; UPnP).
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleScanNetworkForTvs}
                  disabled={isScanningNetwork}
                  className="px-3 py-2 rounded-lg bg-amber-500 text-studio-bg font-bold text-xs hover:bg-amber-400 transition-all flex items-center gap-1.5 flex-shrink-0 shadow-md"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isScanningNetwork ? 'animate-spin' : ''}`} />
                  <span>{isScanningNetwork ? 'Scanning...' : 'Scan Network'}</span>
                </button>
              </div>

              {discoveredTvs.length > 0 && (
                <div className="space-y-1.5 pt-2 border-t border-studio-border/60">
                  <div className="text-[10.5px] font-mono text-emerald-300 font-semibold">
                    Found {discoveredTvs.length} Samsung TV{discoveredTvs.length === 1 ? '' : 's'} on your network:
                  </div>
                  {discoveredTvs.map((dtv) => (
                    <div
                      key={dtv.ip}
                      className="flex items-center justify-between p-2 rounded-lg bg-studio-panel border border-studio-border"
                    >
                      <div>
                        <div className="font-bold text-white text-xs">{dtv.name || 'Samsung Frame TV'}</div>
                        <div className="font-mono text-[10.5px] text-studio-textMuted">
                          {dtv.ip} {dtv.model ? `· ${dtv.model}` : ''}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setManualIp(dtv.ip);
                          if (dtv.name) setTvCustomName(dtv.name);
                        }}
                        className="px-2.5 py-1 rounded bg-emerald-500/20 border border-emerald-500/50 text-emerald-300 font-bold text-[11px] hover:bg-emerald-500/30"
                      >
                        Use {dtv.ip}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <form onSubmit={handleAddTvSubmit} className="space-y-4 text-xs">
              <div>
                <label className="block text-studio-textMuted font-semibold mb-1.5">
                  Or Enter TV IP Address / Hostname Manually (Local Wi-Fi, Tailscale VPN, or WAN):
                </label>
                <input
                  type="text"
                  value={manualIp}
                  onChange={(e) => setManualIp(e.target.value)}
                  placeholder="e.g. 192.168.68.88 or 100.84.22.10:8002"
                  required
                  className="w-full bg-studio-bg border border-studio-border rounded-lg p-2.5 text-white font-mono text-xs outline-none focus:border-studio-accent"
                />
              </div>

              <div>
                <label className="block text-studio-textMuted font-semibold mb-1.5">
                  Display Name (Optional):
                </label>
                <input
                  type="text"
                  value={tvCustomName}
                  onChange={(e) => setTvCustomName(e.target.value)}
                  placeholder="e.g. Living Room Frame TV, Gallery Wall 2"
                  className="w-full bg-studio-bg border border-studio-border rounded-lg p-2.5 text-white text-xs outline-none focus:border-studio-accent"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-studio-border">
                <button
                  type="button"
                  onClick={() => setIsAddTvModalOpen(false)}
                  disabled={isAddingTv}
                  className="px-4 py-2 bg-studio-bg border border-studio-border text-studio-text rounded-lg text-xs font-semibold hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAddingTv || !manualIp.trim()}
                  className="px-5 py-2 bg-studio-accent text-studio-bg rounded-lg text-xs font-bold hover:bg-amber-400 transition-all shadow-md"
                >
                  {isAddingTv ? 'Connecting...' : '+ Connect & Save TV'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
