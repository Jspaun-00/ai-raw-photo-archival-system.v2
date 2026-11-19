import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Tv,
  Crop,
  ChevronLeft,
  ChevronRight,
  X,
  Check,
  Sparkles,
  Move,
  Layers,
  Sliders,
  Download,
  Info,
  Folder,
  Cloud,
  Monitor,
  ChevronDown,
  Palette,
  Globe,
  Plus,
  Maximize2
} from 'lucide-react';
import MatColorPicker, { ARCHIVAL_MAT_TONES, findMatTone } from './MatColorPicker';

/**
 * TvShowcaseCropModal.jsx
 *
 * Interactive 16:9 crop framing modal for 65" TV Showcase JPEG exports.
 * Allows choosing where the 16:9 crop is placed (Sky/Top, Golden Horizon, Center, Ground/Bottom, or custom drag).
 * Previews every photo in selection, supports per-photo adjustment or "Apply to all",
 * and exports exact 12,000 px (12,000 × 6,750 px) JPEGs at 180 DPI with full IPTC/XMP tags embedded.
 */
export default function TvShowcaseCropModal({
  isOpen,
  onClose,
  photos = [],
  collectionName = null,
  onConfirmExport,
  isBusy = false,
}) {
  if (!isOpen || !photos || photos.length === 0) return null;

  const [currentIndex, setCurrentIndex] = useState(0);
  // crops: map from photo identifier (file_hash or file_path) -> { norm_y: number, norm_x: number }
  // norm_y: 0.0 = top / sky, 0.382 = golden horizon, 0.5 = center, 1.0 = bottom / ground
  // norm_x: 0.0 = left, 0.5 = center, 1.0 = right
  const [crops, setCrops] = useState({});
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartY, setDragStartY] = useState(0);
  const [dragStartX, setDragStartX] = useState(0);
  const [initialNormY, setInitialNormY] = useState(0.5);
  const [initialNormX, setInitialNormX] = useState(0.5);
  const [imageNaturalDim, setImageNaturalDim] = useState({ width: 0, height: 0 });
  const [appliedToAllNotice, setAppliedToAllNotice] = useState(false);
  const [targetDestination, setTargetDestination] = useState('desktop'); // 'desktop' | 'icloud' | 'custom' | 'samsung_tv'
  const [customFolderPath, setCustomFolderPath] = useState('');
  const [isPickingFolder, setIsPickingFolder] = useState(false);
  const [destMenuOpen, setDestMenuOpen] = useState(false);
  const destMenuRef = useRef(null);

  // Samsung Frame TV discovery & direct Wi-Fi push state
  const [samsungTvs, setSamsungTvs] = useState([
    { name: 'TV1', ip: '192.168.68.88', model: 'QN55LS03HEFXZA', online: true },
  ]);
  const [selectedTvIp, setSelectedTvIp] = useState('192.168.68.88');
  const [slideshowMinutes, setSlideshowMinutes] = useState(15);
  const [isDiscoveringTvs, setIsDiscoveringTvs] = useState(false);

  // Fine-Art Matting & Depth options (Samsung Frame TV Style)
  const [matMode, setMatMode] = useState('studio'); // 'studio' | 'none'
  const [matPlacement, setMatPlacement] = useState('slim_optical'); // 'slim_optical' | 'modern_thin' | 'optical_center' | 'exact_center' | 'modern_wide' | 'grand_exhibition'
  const [matAspect, setMatAspect] = useState('original'); // 'original' | '16:9' | '3:1' | '2:1' | '3:2' | '4:3' | '5:4' | '1:1'
  const [matStyle, setMatStyle] = useState('single'); // 'single' | 'double'
  const [matColor, setMatColor] = useState('#F4EFE6'); // Warm Cotton
  const [innerMatColor, setInnerMatColor] = useState('#F4EFE6');

  // Add Remote TV dialog state (Internet / Tailscale / DynDNS)
  const [showAddRemoteModal, setShowAddRemoteModal] = useState(false);
  const [remoteHostInput, setRemoteHostInput] = useState('');
  const [remoteNameInput, setRemoteNameInput] = useState('');
  const [isAddingRemote, setIsAddingRemote] = useState(false);
  const [remoteAddError, setRemoteAddError] = useState('');

  const MAT_COLORS = ARCHIVAL_MAT_TONES;

  const MAT_ASPECT_RATIOS = [
    { id: 'original', label: 'Original Ratio (No Crop)', ratio: null, desc: 'Uncropped native Lightroom photo proportions' },
    { id: '16:9', label: '16:9 Crop + Mat', ratio: 16 / 9, desc: '16:9 widescreen crop inside beveled mat (drag photo to pan)' },
    { id: '3:1', label: '3:1 Pano', ratio: 3 / 1, desc: 'Ultra-wide 3:1 panoramic crop inside mat' },
    { id: '2:1', label: '2:1 Pano', ratio: 2 / 1, desc: 'Panoramic 2:1 crop inside mat' },
    { id: '3:2', label: '3:2', ratio: 3 / 2, desc: 'Classic 35mm Full Frame' },
    { id: '4:3', label: '4:3', ratio: 4 / 3, desc: 'Medium Format (Phase One)' },
    { id: '5:4', label: '5:4', ratio: 5 / 4, desc: 'Large Format 4×5 / 8×10' },
    { id: '1:1', label: '1:1 Square', ratio: 1, desc: 'Square Format' },
  ];

  const MAT_PLACEMENTS = [
    { id: 'slim_optical', label: 'Slim Optical ★', desc: '88% window • slim border with optical vertical center (Best for Panos)', icon: '📐' },
    { id: 'modern_thin', label: 'Slim Centered', desc: '88% window • slim border with 50/50 exact center', icon: '📏' },
    { id: 'optical_center', label: 'Medium Optical', desc: '78% window • classic gallery border with optical center', icon: '🏛️' },
    { id: 'exact_center', label: 'Medium Centered', desc: '78% window • classic gallery border with 50/50 center', icon: '⚖️' },
    { id: 'modern_wide', label: 'Wide Exhibition', desc: '64% window • generous museum mat border', icon: '🖼️' },
    { id: 'grand_exhibition', label: 'Extra-Large Mat', desc: '52% window • deep architectural gallery mat', icon: '✨' },
  ];

  const shadeHexColor = (hex, pct) => {
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
    return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
  };

  useEffect(() => {
    if (!isOpen) return;
    fetch('/api/samsung-tvs?rescan=false')
      .then((r) => r.json())
      .then((data) => {
        if (data && Array.isArray(data.tvs) && data.tvs.length > 0) {
          setSamsungTvs(data.tvs);
          setSelectedTvIp((prev) => prev || data.tvs[0].ip);
        }
      })
      .catch(() => {});
  }, [isOpen]);

  const handleDiscoverSamsungTvs = async () => {
    setIsDiscoveringTvs(true);
    try {
      const res = await fetch('/api/samsung-tvs/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rescan: true }),
      });
      const data = await res.json();
      if (data && Array.isArray(data.tvs) && data.tvs.length > 0) {
        setSamsungTvs(data.tvs);
        if (!data.tvs.some((t) => t.ip === selectedTvIp)) {
          setSelectedTvIp(data.tvs[0].ip);
        }
      }
    } catch (err) {
      console.error('Samsung TV discovery error:', err);
    } finally {
      setIsDiscoveringTvs(false);
    }
  };

  useEffect(() => {
    const handleOutside = (e) => {
      if (destMenuRef.current && !destMenuRef.current.contains(e.target)) {
        setDestMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const containerRef = useRef(null);
  const imageRef = useRef(null);

  const currentPhoto = photos[currentIndex] || photos[0];
  const photoId = currentPhoto.file_hash || currentPhoto.file_path || String(currentIndex);

  const currentCrop = crops[photoId] || { norm_y: 0.5, norm_x: 0.5 };
  const normY = currentCrop.norm_y ?? 0.5;
  const normX = currentCrop.norm_x ?? 0.5;

  // Reset index when modal opens with new photos
  useEffect(() => {
    if (isOpen) {
      setCurrentIndex(0);
      setAppliedToAllNotice(false);
    }
  }, [isOpen, photos]);

  // Handle ESC key to close
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !isBusy) {
        onClose();
      } else if (e.key === 'ArrowLeft' && photos.length > 1) {
        setCurrentIndex((prev) => (prev > 0 ? prev - 1 : photos.length - 1));
      } else if (e.key === 'ArrowRight' && photos.length > 1) {
        setCurrentIndex((prev) => (prev < photos.length - 1 ? prev + 1 : 0));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose, isBusy, photos.length]);

  const updateCrop = useCallback(
    (newNormY, newNormX) => {
      const clampedY = Math.max(0, Math.min(1, newNormY));
      const clampedX = Math.max(0, Math.min(1, newNormX));
      setCrops((prev) => ({
        ...prev,
        [photoId]: { norm_y: clampedY, norm_x: clampedX },
      }));
    },
    [photoId]
  );

  const handleApplyToAll = () => {
    const newCrops = {};
    photos.forEach((p) => {
      const pid = p.file_hash || p.file_path;
      if (pid) {
        newCrops[pid] = { norm_y: normY, norm_x: normX };
      }
    });
    setCrops(newCrops);
    setAppliedToAllNotice(true);
    setTimeout(() => setAppliedToAllNotice(false), 2400);
  };

  // Preview URL generator
  const getPreviewUrl = (p) => {
    if (!p) return null;
    if (p.preview_url) return p.preview_url;
    if (p.preview_1600_path) return `/previews/previews_1600/${p.preview_1600_path.split('/').pop()}`;
    if (p.thumb_url) return p.thumb_url;
    if (p.thumb_360_path) return `/previews/thumbs_360/${p.thumb_360_path.split('/').pop()}`;
    if (p.file_hash) return `/api/photos/preview/${p.file_hash}`;
    return null;
  };

  const previewSrc = getPreviewUrl(currentPhoto);

  // Aspect ratio calculation (Full 16:9 Bleed vs Fine-Art Mat Window Aspect Ratio)
  const bleedRatio = 16.0 / 9.0; // 1.777778
  const naturalAspect =
    imageNaturalDim.width && imageNaturalDim.height
      ? imageNaturalDim.width / imageNaturalDim.height
      : 4.0 / 3.0;

  const selectedMatAspectObj = MAT_ASPECT_RATIOS.find((a) => a.id === matAspect);
  const targetRatio =
    matMode === 'none'
      ? bleedRatio
      : selectedMatAspectObj && selectedMatAspectObj.ratio
      ? selectedMatAspectObj.ratio
      : naturalAspect;

  // Is image taller than target window aspect? -> vertical crop adjustment
  // Is image wider than target window aspect? -> horizontal crop adjustment
  const isTaller = naturalAspect < targetRatio - 0.005;
  const isWider = naturalAspect > targetRatio + 0.005;

  // Crop box percentage sizing (used in Full 16:9 Bleed mode and for drag sensitivity)
  let boxWidthPct = 100;
  let boxHeightPct = 100;
  let topPct = 0;
  let leftPct = 0;

  if (isTaller) {
    boxHeightPct = Math.min(100, (naturalAspect / targetRatio) * 100);
    const slackHeightPct = 100 - boxHeightPct;
    topPct = normY * slackHeightPct;
  } else if (isWider) {
    boxWidthPct = Math.min(100, (targetRatio / naturalAspect) * 100);
    const slackWidthPct = 100 - boxWidthPct;
    leftPct = normX * slackWidthPct;
  }

  // Mouse drag handlers for direct viewport dragging (both Full Bleed & Cropped Mat Window)
  const handleMouseDown = (e) => {
    e.preventDefault();
    setIsDragging(true);
    setDragStartY(e.clientY);
    setDragStartX(e.clientX);
    setInitialNormY(normY);
    setInitialNormX(normX);
  };

  const handleMouseMove = useCallback(
    (e) => {
      if (!isDragging) return;
      const sign = matMode === 'studio' ? -1 : 1;
      if (isTaller) {
        const refEl = containerRef.current;
        const rectH = refEl ? refEl.getBoundingClientRect().height : 320;
        const slackHeightPx =
          matMode === 'studio'
            ? Math.max(120, rectH * 0.65)
            : rectH * ((100 - boxHeightPct) / 100);
        if (slackHeightPx > 0) {
          const deltaY = (e.clientY - dragStartY) * sign;
          const deltaNormY = deltaY / slackHeightPx;
          updateCrop(initialNormY + deltaNormY, normX);
        }
      } else if (isWider) {
        const refEl = containerRef.current;
        const rectW = refEl ? refEl.getBoundingClientRect().width : 480;
        const slackWidthPx =
          matMode === 'studio'
            ? Math.max(140, rectW * 0.65)
            : rectW * ((100 - boxWidthPct) / 100);
        if (slackWidthPx > 0) {
          const deltaX = (e.clientX - dragStartX) * sign;
          const deltaNormX = deltaX / slackWidthPx;
          updateCrop(normY, initialNormX + deltaNormX);
        }
      }
    },
    [
      isDragging,
      matMode,
      isTaller,
      isWider,
      boxHeightPct,
      boxWidthPct,
      dragStartY,
      dragStartX,
      initialNormY,
      initialNormX,
      normY,
      normX,
      updateCrop,
    ]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Presets
  const presetsY = [
    { label: 'Sky / Top', value: 0.0, icon: '🔼' },
    { label: 'Golden Horizon', value: 0.382, icon: '🌅' },
    { label: 'Center', value: 0.5, icon: '⚖️' },
    { label: 'Ground / Bottom', value: 1.0, icon: '🔽' },
  ];

  const presetsX = [
    { label: 'Left', value: 0.0, icon: '◀️' },
    { label: 'Center', value: 0.5, icon: '⚖️' },
    { label: 'Right', value: 1.0, icon: '▶️' },
  ];

  const handleAddRemoteTv = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!remoteHostInput.trim()) return;
    setIsAddingRemote(true);
    setRemoteAddError('');
    try {
      const res = await fetch('/api/samsung-tvs/add-remote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: remoteHostInput.trim(),
          name: remoteNameInput.trim() || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to add remote TV');
      }
      if (data.tvs && Array.isArray(data.tvs)) {
        setSamsungTvs(data.tvs);
        const added = data.added_tv?.ip || remoteHostInput.trim();
        setSelectedTvIp(added);
      }
      setShowAddRemoteModal(false);
      setRemoteHostInput('');
      setRemoteNameInput('');
    } catch (err) {
      setRemoteAddError(err.message || 'Error connecting to remote TV');
    } finally {
      setIsAddingRemote(false);
    }
  };

  const triggerExportWithDestination = (dest, folderPath = null, extraOptions = {}) => {
    try {
      localStorage.setItem('mrdarkroom_export_destination', dest);
      if (folderPath) {
        localStorage.setItem('mrdarkroom_export_custom_path', folderPath);
      }
    } catch (_) {}
    setTargetDestination(dest);
    if (folderPath) setCustomFolderPath(folderPath);
    setDestMenuOpen(false);
    if (onConfirmExport) {
      onConfirmExport(crops, dest, folderPath, {
        samsung_tv_ip: selectedTvIp,
        slideshow_minutes: slideshowMinutes,
        mat_mode: matMode,
        mat_color: matColor,
        mat_placement: matPlacement,
        mat_aspect: matAspect,
        mat_style: matStyle,
        inner_mat_color: innerMatColor,
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

  const photoTitle =
    currentPhoto.title ||
    (currentPhoto.file_path ? currentPhoto.file_path.split('/').pop() : `Photo ${currentIndex + 1}`);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(5, 8, 15, 0.88)',
        backdropFilter: 'blur(16px)',
        zIndex: 10100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px',
        boxSizing: 'border-box',
        color: '#f8fafc',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '1280px',
          maxHeight: '94vh',
          backgroundColor: '#0c101c',
          border: '1px solid rgba(52, 211, 153, 0.35)',
          borderRadius: '14px',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.95), 0 0 40px rgba(16, 185, 129, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* ========================================================================= */}
        {/* COMPACT MODAL HEADER WITH INLINE FRAMING MODE SWITCHER                    */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '10px 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%)',
            flexWrap: 'wrap',
            gap: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(56, 189, 248, 0.25) 100%)',
                border: '1px solid rgba(52, 211, 153, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#34d399',
              }}
            >
              <Tv style={{ width: '17px', height: '17px' }} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>TV Showcase &amp; Frame Studio (16:9)</span>
                {collectionName && (
                  <span
                    style={{
                      fontSize: '10.5px',
                      fontWeight: 800,
                      padding: '1px 7px',
                      borderRadius: '5px',
                      background: 'rgba(245, 158, 11, 0.2)',
                      color: '#fbbf24',
                      border: '1px solid rgba(245, 158, 11, 0.4)',
                    }}
                  >
                    📁 {collectionName}
                  </span>
                )}
                <span
                  style={{
                    fontSize: '10.5px',
                    fontWeight: 700,
                    padding: '1px 7px',
                    borderRadius: '999px',
                    background: 'rgba(52, 211, 153, 0.18)',
                    color: '#6ee7b7',
                    border: '1px solid rgba(52, 211, 153, 0.35)',
                  }}
                >
                  4K Frame TV &amp; 12K Print • 180 DPI
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '10.5px', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Framing:
            </span>
            <button
              type="button"
              onClick={() => setMatMode('studio')}
              style={{
                padding: '5px 11px',
                borderRadius: '7px',
                fontSize: '11.5px',
                fontWeight: matMode === 'studio' ? 800 : 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                background: matMode === 'studio' ? 'rgba(245, 158, 11, 0.22)' : 'rgba(255, 255, 255, 0.04)',
                border: matMode === 'studio' ? '1.5px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.12)',
                color: matMode === 'studio' ? '#fbbf24' : '#cbd5e1',
              }}
            >
              <Palette style={{ width: '13px', height: '13px' }} />
              <span>Fine-Art Mat (45° Bevel)</span>
            </button>
            <button
              type="button"
              onClick={() => setMatMode('none')}
              style={{
                padding: '5px 11px',
                borderRadius: '7px',
                fontSize: '11.5px',
                fontWeight: matMode === 'none' ? 800 : 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                background: matMode === 'none' ? 'rgba(16, 185, 129, 0.22)' : 'rgba(255, 255, 255, 0.04)',
                border: matMode === 'none' ? '1.5px solid #10b981' : '1px solid rgba(255, 255, 255, 0.12)',
                color: matMode === 'none' ? '#34d399' : '#cbd5e1',
              }}
            >
              <Crop style={{ width: '13px', height: '13px' }} />
              <span>Full 16:9 Bleed</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              style={{
                padding: '6px',
                borderRadius: '7px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'rgba(255, 255, 255, 0.05)',
                color: '#94a3b8',
                cursor: isBusy ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginLeft: '4px',
              }}
              title="Close (Esc)"
            >
              <X style={{ width: '16px', height: '16px' }} />
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 2-COLUMN SIDE-BY-SIDE STUDIO BODY (LEFT: LARGE PREVIEW, RIGHT: CONTROLS)  */}
        {/* ========================================================================= */}
        <div
          className="grid grid-cols-1 lg:grid-cols-12 gap-3.5 p-3.5 overflow-y-auto flex-1 items-start"
          style={{ minHeight: 0 }}
        >
          {/* LEFT COLUMN (7 of 12 cols on laptop): Large Un-Smashed 16:9 Preview + Filmstrip */}
          <div className="lg:col-span-7 flex flex-col gap-2.5 min-w-0">
            {/* Top Bar: Photo Switcher & Filename */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
                color: '#cbd5e1',
                padding: '0 2px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden' }}>
                <span style={{ fontWeight: 700, color: '#f8fafc', whiteSpace: 'nowrap' }}>
                  Photo {currentIndex + 1} of {photos.length}:
                </span>
                <span style={{ color: '#fbbf24', fontWeight: 600, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '320px' }}>
                  {photoTitle}
                </span>
                {imageNaturalDim.width > 0 && (
                  <span style={{ fontSize: '10.5px', color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
                    ({imageNaturalDim.width.toLocaleString()} × {imageNaturalDim.height.toLocaleString()} px)
                  </span>
                )}
              </div>

              {photos.length > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <button
                    type="button"
                    onClick={() => setCurrentIndex((prev) => (prev > 0 ? prev - 1 : photos.length - 1))}
                    style={{
                      padding: '3px 7px',
                      borderRadius: '6px',
                      background: 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#cbd5e1',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px',
                      fontSize: '11px',
                    }}
                  >
                    <ChevronLeft style={{ width: '13px', height: '13px' }} />
                    <span>Prev</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setCurrentIndex((prev) => (prev < photos.length - 1 ? prev + 1 : 0))}
                    style={{
                      padding: '3px 7px',
                      borderRadius: '6px',
                      background: 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      color: '#cbd5e1',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '3px',
                      fontSize: '11px',
                    }}
                  >
                    <span>Next</span>
                    <ChevronRight style={{ width: '13px', height: '13px' }} />
                  </button>
                </div>
              )}
            </div>

            {/* VIEWPORT AREA: FINE-ART MAT VIEWPORT vs FULL 16:9 CROP VIEWPORT */}
            {matMode === 'studio' ? (
              <div
                style={{
                  position: 'relative',
                  width: '100%',
                  backgroundColor: '#05070d',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  userSelect: 'none',
                  padding: '10px',
                  boxSizing: 'border-box',
                }}
              >
                {(() => {
                  const cW = 1600;
                  const cH = 900;
                  const winAspect = targetRatio;
                  let maxWF = 0.78;
                  let maxHF = 0.76;
                  if (matPlacement === 'grand_exhibition') {
                    maxWF = 0.52;
                    maxHF = 0.52;
                  } else if (matPlacement === 'modern_wide') {
                    maxWF = 0.64;
                    maxHF = 0.64;
                  } else if (matPlacement === 'modern_thin' || matPlacement === 'slim_optical') {
                    maxWF = 0.88;
                    maxHF = 0.86;
                  }
                  const maxW = cW * maxWF;
                  const maxH = cH * maxHF;
                  let wW = maxW;
                  let wH = maxH;
                  if (maxW / maxH > winAspect) {
                    wH = maxH;
                    wW = Math.round(wH * winAspect);
                  } else {
                    wW = maxW;
                    wH = Math.round(wW / winAspect);
                  }
                  const x0 = Math.round((cW - wW) / 2);
                  let y0 = Math.round((cH - wH) / 2);
                  if (matPlacement === 'slim_optical') {
                    y0 = Math.round((cH - wH) * 0.44);
                  } else if (matPlacement === 'optical_center') {
                    y0 = Math.round((cH - wH) * 0.45);
                  } else if (matPlacement === 'modern_wide' || matPlacement === 'grand_exhibition') {
                    y0 = Math.round((cH - wH) * 0.46);
                  }
                  const x1 = x0 + wW;
                  const y1 = y0 + wH;
                  const B = 10;
                  const ox0 = x0 - B;
                  const oy0 = y0 - B;
                  const ox1 = x1 + B;
                  const oy1 = y1 + B;

                  const isDouble = matStyle === 'double';
                  const reveal = Math.max(10, Math.round(B * 2.1));
                  const BOut = Math.max(6, Math.round(B * 0.88));
                  const mx0 = ox0 - reveal;
                  const my0 = oy0 - reveal;
                  const mx1 = ox1 + reveal;
                  const my1 = oy1 + reveal;
                  const obx0 = mx0 - BOut;
                  const oby0 = my0 - BOut;
                  const obx1 = mx1 + BOut;
                  const oby1 = my1 + BOut;

                  const canPanMat = matAspect !== 'original' && (isTaller || isWider);
                  const objPosition = `${(normX * 100).toFixed(1)}% ${(normY * 100).toFixed(1)}%`;

                  return (
                    <div
                      ref={containerRef}
                      onMouseDown={canPanMat ? handleMouseDown : undefined}
                      style={{
                        position: 'relative',
                        width: '100%',
                        aspectRatio: '16 / 9',
                        backgroundColor: matColor,
                        borderRadius: '4px',
                        boxShadow: '0 20px 45px -12px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(255, 255, 255, 0.08)',
                        overflow: 'hidden',
                        transition: 'background-color 0.2s ease',
                        cursor: canPanMat ? (isDragging ? 'grabbing' : 'grab') : 'default',
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          left: `${(x0 / cW) * 100}%`,
                          top: `${(y0 / cH) * 100}%`,
                          width: `${(wW / cW) * 100}%`,
                          height: `${(wH / cH) * 100}%`,
                          overflow: 'hidden',
                          backgroundColor: '#0c0e14',
                        }}
                      >
                        <img
                          ref={imageRef}
                          src={previewSrc}
                          alt={photoTitle}
                          onLoad={(e) => {
                            setImageNaturalDim({
                              width: e.target.naturalWidth,
                              height: e.target.naturalHeight,
                            });
                          }}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                            objectPosition: objPosition,
                            display: 'block',
                            pointerEvents: 'none',
                          }}
                        />
                      </div>

                      <svg
                        viewBox={`0 0 ${cW} ${cH}`}
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
                          <linearGradient id="tvsc-top-bevel" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#c4beaf" />
                            <stop offset="100%" stopColor="#ada697" />
                          </linearGradient>
                          <linearGradient id="tvsc-bot-bevel" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#eee9de" />
                            <stop offset="100%" stopColor="#f8f6f0" />
                          </linearGradient>
                          <linearGradient id="tvsc-left-bevel" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#d2ccbe" />
                            <stop offset="100%" stopColor="#c0baab" />
                          </linearGradient>
                          <linearGradient id="tvsc-right-bevel" x1="0" y1="0" x2="1" y2="0">
                            <stop offset="0%" stopColor="#e6e1d5" />
                            <stop offset="100%" stopColor="#f0ebe0" />
                          </linearGradient>
                        </defs>

                        {isDouble && (
                          <g>
                            <rect x={mx0} y={my0} width={mx1 - mx0} height={oy0 - my0} fill={innerMatColor || '#F4EFE6'} />
                            <rect x={mx0} y={oy1} width={mx1 - mx0} height={my1 - oy1} fill={innerMatColor || '#F4EFE6'} />
                            <rect x={mx0} y={oy0} width={ox0 - mx0} height={oy1 - oy0} fill={innerMatColor || '#F4EFE6'} />
                            <rect x={ox1} y={oy0} width={mx1 - ox1} height={oy1 - oy0} fill={innerMatColor || '#F4EFE6'} />

                            <polygon points={`${obx0},${oby0} ${obx1},${oby0} ${mx1},${my0} ${mx0},${my0}`} fill="url(#tvsc-top-bevel)" />
                            <polygon points={`${mx0},${my1} ${mx1},${my1} ${obx1},${oby1} ${obx0},${oby1}`} fill="url(#tvsc-bot-bevel)" />
                            <polygon points={`${obx0},${oby0} ${mx0},${my0} ${mx0},${my1} ${obx0},${oby1}`} fill="url(#tvsc-left-bevel)" />
                            <polygon points={`${mx1},${my0} ${obx1},${oby0} ${obx1},${oby1} ${mx1},${my1}`} fill="url(#tvsc-right-bevel)" />

                            <line x1={obx0} y1={oby0} x2={mx0} y2={my0} stroke="#beb8ae" strokeWidth="1.1" />
                            <line x1={obx1} y1={oby0} x2={mx1} y2={my0} stroke="#c8c2b8" strokeWidth="1.1" />
                            <line x1={obx0} y1={oby1} x2={mx0} y2={my1} stroke="#d0cac0" strokeWidth="1.1" />
                            <line x1={obx1} y1={oby1} x2={mx1} y2={my1} stroke="#dcd7cd" strokeWidth="1.1" />
                            <rect x={mx0} y={my0} width={mx1 - mx0} height={my1 - my0} fill="none" stroke="rgba(60,56,50,0.28)" strokeWidth="0.9" />
                          </g>
                        )}

                        <polygon points={`${ox0},${oy0} ${ox1},${oy0} ${x1},${y0} ${x0},${y0}`} fill="url(#tvsc-top-bevel)" />
                        <polygon points={`${x0},${y1} ${x1},${y1} ${ox1},${oy1} ${ox0},${oy1}`} fill="url(#tvsc-bot-bevel)" />
                        <polygon points={`${ox0},${oy0} ${x0},${y0} ${x0},${y1} ${ox0},${oy1}`} fill="url(#tvsc-left-bevel)" />
                        <polygon points={`${x1},${y0} ${ox1},${oy0} ${ox1},${oy1} ${x1},${y1}`} fill="url(#tvsc-right-bevel)" />

                        <line x1={ox0} y1={oy0} x2={x0} y2={y0} stroke="#a29c90" strokeWidth="1.1" />
                        <line x1={ox1} y1={oy0} x2={x1} y2={y0} stroke="#aea89c" strokeWidth="1.1" />
                        <line x1={ox0} y1={oy1} x2={x0} y2={y1} stroke="#bab4a8" strokeWidth="1.1" />
                        <line x1={ox1} y1={oy1} x2={x1} y2={y1} stroke="#cecac0" strokeWidth="1.1" />

                        <rect x={x0} y={y0} width={wW} height={wH} fill="none" stroke="rgba(60,56,50,0.48)" strokeWidth="1.0" />
                        <line x1={x0} y1={y0} x2={x1} y2={y0} stroke="rgba(40,36,30,0.32)" strokeWidth="1.2" />
                      </svg>

                      {canPanMat && (
                        <div
                          style={{
                            position: 'absolute',
                            top: '8px',
                            left: '50%',
                            transform: 'translateX(-50%)',
                            background: 'rgba(15, 23, 42, 0.82)',
                            backdropFilter: 'blur(6px)',
                            border: '1px solid rgba(245, 158, 11, 0.45)',
                            padding: '2px 9px',
                            borderRadius: '999px',
                            fontSize: '10px',
                            fontWeight: 700,
                            color: '#fbbf24',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '5px',
                            pointerEvents: 'none',
                          }}
                        >
                          <Move style={{ width: '11px', height: '11px' }} />
                          <span>Drag photo inside {matAspect} mat window to adjust crop</span>
                        </div>
                      )}

                      <div
                        style={{
                          position: 'absolute',
                          bottom: '8px',
                          right: '10px',
                          background: 'rgba(0, 0, 0, 0.65)',
                          backdropFilter: 'blur(6px)',
                          padding: '2px 8px',
                          borderRadius: '5px',
                          fontSize: '10px',
                          fontWeight: 700,
                          color: '#f8fafc',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          pointerEvents: 'none',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                        }}
                      >
                        <span>🏛️ {matAspect === 'original' ? 'Natural Ratio' : `${matAspect} Window`}</span>
                        <span>•</span>
                        <span style={{ color: '#fbbf24' }}>
                          {MAT_COLORS.find((c) => c.hex.toLowerCase() === matColor.toLowerCase())?.name || matColor}
                        </span>
                        <span>•</span>
                        <span>{isDouble ? 'Double Mat (2× Bevel)' : 'Soft 45° Bevel'}</span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            ) : (
              <div
                style={{
                  position: 'relative',
                  width: '100%',
                  aspectRatio: '16 / 9',
                  backgroundColor: '#05070d',
                  borderRadius: '12px',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  userSelect: 'none',
                }}
              >
                <div
                  ref={containerRef}
                  style={{
                    position: 'relative',
                    maxHeight: '100%',
                    maxWidth: '100%',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <img
                    ref={imageRef}
                    src={previewSrc}
                    alt={photoTitle}
                    onLoad={(e) => {
                      setImageNaturalDim({
                        width: e.target.naturalWidth,
                        height: e.target.naturalHeight,
                      });
                    }}
                    style={{
                      maxHeight: '380px',
                      maxWidth: '100%',
                      objectFit: 'contain',
                      display: 'block',
                      pointerEvents: 'none',
                    }}
                  />

                  <div
                    onMouseDown={handleMouseDown}
                    style={{
                      position: 'absolute',
                      top: `${topPct}%`,
                      left: `${leftPct}%`,
                      width: `${boxWidthPct}%`,
                      height: `${boxHeightPct}%`,
                      border: '2px solid #10b981',
                      boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.65)',
                      cursor: isDragging ? 'grabbing' : isTaller ? 'ns-resize' : isWider ? 'ew-resize' : 'move',
                      zIndex: 20,
                      boxSizing: 'border-box',
                      pointerEvents: 'auto',
                    }}
                  >
                    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                      <div style={{ position: 'absolute', top: '33.333%', left: 0, right: 0, height: '1px', borderTop: '1px dashed rgba(255, 255, 255, 0.28)' }} />
                      <div style={{ position: 'absolute', top: '66.666%', left: 0, right: 0, height: '1px', borderTop: '1px dashed rgba(255, 255, 255, 0.28)' }} />
                      <div style={{ position: 'absolute', left: '33.333%', top: 0, bottom: 0, width: '1px', borderLeft: '1px dashed rgba(255, 255, 255, 0.28)' }} />
                      <div style={{ position: 'absolute', left: '66.666%', top: 0, bottom: 0, width: '1px', borderLeft: '1px dashed rgba(255, 255, 255, 0.28)' }} />
                    </div>

                    <div
                      style={{
                        position: 'absolute',
                        top: '8px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        background: 'rgba(15, 23, 42, 0.82)',
                        backdropFilter: 'blur(8px)',
                        border: '1px solid rgba(52, 211, 153, 0.45)',
                        padding: '2px 9px',
                        borderRadius: '999px',
                        fontSize: '10.5px',
                        fontWeight: 700,
                        color: '#6ee7b7',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '5px',
                        pointerEvents: 'none',
                      }}
                    >
                      <Move style={{ width: '11px', height: '11px' }} />
                      <span>
                        {isTaller ? 'DRAG UP/DOWN TO FRAME' : isWider ? 'DRAG LEFT/RIGHT TO FRAME' : '16:9 VIEWPORT'}
                      </span>
                    </div>

                    <div style={{ position: 'absolute', top: -3, left: -3, width: 10, height: 10, borderTop: '3px solid #34d399', borderLeft: '3px solid #34d399' }} />
                    <div style={{ position: 'absolute', top: -3, right: -3, width: 10, height: 10, borderTop: '3px solid #34d399', borderRight: '3px solid #34d399' }} />
                    <div style={{ position: 'absolute', bottom: -3, left: -3, width: 10, height: 10, borderBottom: '3px solid #34d399', borderLeft: '3px solid #34d399' }} />
                    <div style={{ position: 'absolute', bottom: -3, right: -3, width: 10, height: 10, borderBottom: '3px solid #34d399', borderRight: '3px solid #34d399' }} />
                  </div>
                </div>
              </div>
            )}

            {/* Filmstrip / Thumbnail Stepper if multiple photos */}
            {photos.length > 1 && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  background: 'rgba(255, 255, 255, 0.02)',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '5px', overflowX: 'auto', maxWidth: '420px', paddingBottom: '2px' }}>
                  {photos.map((p, idx) => {
                    const pid = p.file_hash || p.file_path || String(idx);
                    const isCurrent = idx === currentIndex;
                    const thumb = getPreviewUrl(p);
                    return (
                      <button
                        key={pid}
                        type="button"
                        onClick={() => setCurrentIndex(idx)}
                        style={{
                          position: 'relative',
                          width: '40px',
                          height: '28px',
                          borderRadius: '4px',
                          overflow: 'hidden',
                          border: isCurrent ? '2px solid #34d399' : '1px solid rgba(255, 255, 255, 0.14)',
                          background: '#1e293b',
                          cursor: 'pointer',
                          flexShrink: 0,
                          padding: 0,
                        }}
                        title={`Photo ${idx + 1}: ${p.title || p.file_path || ''}`}
                      >
                        {thumb ? (
                          <img src={thumb} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                          <div style={{ fontSize: '9px', color: '#94a3b8' }}>{idx + 1}</div>
                        )}
                      </button>
                    );
                  })}
                </div>

                <button
                  type="button"
                  onClick={handleApplyToAll}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '6px',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    background: 'rgba(56, 189, 248, 0.12)',
                    color: '#7dd3fc',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <Layers style={{ width: '12px', height: '12px' }} />
                  <span>{appliedToAllNotice ? '✓ Applied to all!' : 'Apply Placement to All'}</span>
                </button>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN (5 of 12 cols on laptop): Compact Mat, Aspect Ratio & Color Controls */}
          <div className="lg:col-span-5 flex flex-col gap-2.5 min-w-0">
            {matMode === 'studio' ? (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  padding: '10px 12px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: '10px',
                  border: '1px solid rgba(255, 255, 255, 0.07)',
                }}
              >
                {/* Section 1: Window Aspect Ratio */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      1. Photo Window Aspect Ratio
                    </span>
                    <span style={{ fontSize: '10px', color: '#94a3b8' }}>
                      {selectedMatAspectObj?.desc || 'Uncropped native proportions'}
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                    {MAT_ASPECT_RATIOS.map((ar) => {
                      const isActive = matAspect === ar.id;
                      return (
                        <button
                          key={ar.id}
                          type="button"
                          onClick={() => setMatAspect(ar.id)}
                          title={ar.desc}
                          style={{
                            padding: '4px 9px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: isActive ? 800 : 500,
                            border: isActive ? '1.5px solid #34d399' : '1px solid rgba(255, 255, 255, 0.12)',
                            background: isActive ? 'rgba(16, 185, 129, 0.22)' : 'rgba(255, 255, 255, 0.05)',
                            color: isActive ? '#6ee7b7' : '#e2e8f0',
                            cursor: 'pointer',
                          }}
                        >
                          {ar.id === 'original' ? '✨ Original' : ar.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Inline Crop Framing Controls when a cropped aspect ratio is active */}
                  {matAspect !== 'original' && (isTaller || isWider) && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '6px' }}>
                      {(isTaller ? presetsY : presetsX).map((p) => {
                        const isPresetActive = isTaller
                          ? Math.abs(normY - p.value) < 0.04
                          : Math.abs(normX - p.value) < 0.04;
                        return (
                          <button
                            key={p.label}
                            type="button"
                            onClick={() => {
                              if (isTaller) updateCrop(p.value, normX);
                              else updateCrop(normY, p.value);
                            }}
                            style={{
                              padding: '2px 7px',
                              borderRadius: '5px',
                              fontSize: '10.5px',
                              fontWeight: isPresetActive ? 700 : 500,
                              border: isPresetActive ? '1px solid #38bdf8' : '1px solid rgba(255, 255, 255, 0.12)',
                              background: isPresetActive ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                              color: isPresetActive ? '#7dd3fc' : '#cbd5e1',
                              cursor: 'pointer',
                            }}
                          >
                            {p.icon} {p.label}
                          </button>
                        );
                      })}
                      <input
                        type="range"
                        min="0"
                        max="100"
                        value={Math.round((isTaller ? normY : normX) * 100)}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value) / 100.0;
                          if (isTaller) updateCrop(val, normX);
                          else updateCrop(normY, val);
                        }}
                        style={{ width: '80px', accentColor: '#38bdf8', cursor: 'pointer' }}
                        title="Fine-tune crop offset inside mat opening"
                      />
                    </div>
                  )}
                </div>

                {/* Section 2: Border & Placement + Single/Double Mat Toggle */}
                <div style={{ paddingTop: '6px', borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginBottom: '6px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '11px', fontWeight: 800, color: '#fbbf24', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      2. Mat Border &amp; Bevel
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <button
                        type="button"
                        onClick={() => setMatStyle('single')}
                        style={{
                          padding: '3px 8px',
                          borderRadius: '5px',
                          fontSize: '10.5px',
                          fontWeight: matStyle === 'single' ? 800 : 500,
                          border: matStyle === 'single' ? '1px solid #fbbf24' : '1px solid rgba(255, 255, 255, 0.12)',
                          background: matStyle === 'single' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                          color: matStyle === 'single' ? '#fbbf24' : '#cbd5e1',
                          cursor: 'pointer',
                        }}
                      >
                        Single Mat
                      </button>
                      <button
                        type="button"
                        onClick={() => setMatStyle('double')}
                        style={{
                          padding: '3px 8px',
                          borderRadius: '5px',
                          fontSize: '10.5px',
                          fontWeight: matStyle === 'double' ? 800 : 500,
                          border: matStyle === 'double' ? '1px solid #fbbf24' : '1px solid rgba(255, 255, 255, 0.12)',
                          background: matStyle === 'double' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                          color: matStyle === 'double' ? '#fbbf24' : '#cbd5e1',
                          cursor: 'pointer',
                        }}
                      >
                        Double Mat (2×)
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {MAT_PLACEMENTS.map((pl) => {
                      const isActive = matPlacement === pl.id;
                      return (
                        <button
                          key={pl.id}
                          type="button"
                          onClick={() => setMatPlacement(pl.id)}
                          title={pl.desc}
                          style={{
                            padding: '5px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: isActive ? 800 : 500,
                            border: isActive ? '1px solid #f59e0b' : '1px solid rgba(255, 255, 255, 0.12)',
                            background: isActive ? 'rgba(245, 158, 11, 0.22)' : 'rgba(255, 255, 255, 0.05)',
                            color: isActive ? '#fbbf24' : '#e2e8f0',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                          }}
                        >
                          <span>{pl.icon}</span>
                          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{pl.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Section 3: Compact Archival Mat Color Studio */}
                <div style={{ paddingTop: '6px', borderTop: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <MatColorPicker
                    color={matColor}
                    onChange={setMatColor}
                    isDoubleMat={matStyle === 'double'}
                    innerColor={innerMatColor}
                    onInnerChange={setInnerMatColor}
                    compact={true}
                  />
                </div>
              </div>
            ) : (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  padding: '14px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: '10px',
                  border: '1px solid rgba(255, 255, 255, 0.07)',
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Full 16:9 Bleed Crop Placement
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                  {(isTaller ? presetsY : presetsX).map((p) => {
                    const isActive = isTaller
                      ? Math.abs(normY - p.value) < 0.04
                      : Math.abs(normX - p.value) < 0.04;
                    return (
                      <button
                        key={p.label}
                        type="button"
                        onClick={() => {
                          if (isTaller) updateCrop(p.value, normX);
                          else updateCrop(normY, p.value);
                        }}
                        style={{
                          padding: '6px 11px',
                          borderRadius: '7px',
                          fontSize: '11.5px',
                          fontWeight: isActive ? 700 : 500,
                          border: isActive ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.12)',
                          background: isActive ? 'rgba(16, 185, 129, 0.22)' : 'rgba(255, 255, 255, 0.05)',
                          color: isActive ? '#6ee7b7' : '#e2e8f0',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                        }}
                      >
                        <span>{p.icon}</span>
                        <span>{p.label}</span>
                      </button>
                    );
                  })}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Sliders style={{ width: '14px', height: '14px', color: '#94a3b8' }} />
                  <span style={{ fontSize: '11.5px', color: '#94a3b8', fontWeight: 600 }}>
                    {isTaller ? 'Vertical Offset:' : 'Horizontal Offset:'}
                  </span>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    value={Math.round((isTaller ? normY : normX) * 100)}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value) / 100.0;
                      if (isTaller) updateCrop(val, normX);
                      else updateCrop(normY, val);
                    }}
                    style={{
                      flex: 1,
                      accentColor: '#10b981',
                      cursor: 'pointer',
                    }}
                  />
                  <span style={{ fontSize: '12px', fontVariantNumeric: 'tabular-nums', color: '#34d399', fontWeight: 700, width: '36px' }}>
                    {Math.round((isTaller ? normY : normX) * 100)}%
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ========================================================================= */}
        {/* COMPACT MODAL FOOTER                                                      */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '10px 16px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#090d17',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          {/* Left: Cancel + File Export Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              style={{
                padding: '7px 13px',
                borderRadius: '7px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                background: 'rgba(255, 255, 255, 0.05)',
                color: '#cbd5e1',
                fontSize: '12px',
                fontWeight: 600,
                cursor: isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => triggerExportWithDestination('desktop')}
              disabled={isBusy}
              title={`Export 12K TV Showcase JPEGs directly to ~/Desktop/TV Folder/${collectionName || 'TV_Showcase'}`}
              style={{
                padding: '7px 13px',
                borderRadius: '7px',
                border: '1.5px solid #10b981',
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(5, 150, 105, 0.38) 100%)',
                color: '#34d399',
                fontSize: '12px',
                fontWeight: 800,
                cursor: isBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              <span>🖥️</span>
              <span>{isBusy ? 'Exporting...' : 'Desktop'}</span>
            </button>

            <button
              type="button"
              onClick={() => triggerExportWithDestination('icloud')}
              disabled={isBusy}
              title={`Export to iCloud Drive: TV Folder/${collectionName || 'TV_Showcase'}`}
              style={{
                padding: '7px 13px',
                borderRadius: '7px',
                border: '1.5px solid #38bdf8',
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.22) 0%, rgba(2, 132, 199, 0.35) 100%)',
                color: '#7dd3fc',
                fontSize: '12px',
                fontWeight: 800,
                cursor: isBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              <span>☁️</span>
              <span>{isBusy ? 'Exporting...' : 'iCloud'}</span>
            </button>

            <button
              type="button"
              onClick={handlePickFolderAndExport}
              disabled={isBusy || isPickingFolder}
              title="Choose any specific local, GDrive, or network folder in macOS Finder"
              style={{
                padding: '7px 13px',
                borderRadius: '7px',
                border: '1.5px solid #a855f7',
                background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.22) 0%, rgba(126, 34, 206, 0.35) 100%)',
                color: '#d8b4fe',
                fontSize: '12px',
                fontWeight: 800,
                cursor: (isBusy || isPickingFolder) ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              <span>📁</span>
              <span>{isPickingFolder ? 'Opening...' : 'Choose Folder...'}</span>
            </button>
          </div>

          {/* Right: Direct Push to Samsung Frame TV */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 6px',
              borderRadius: '9px',
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.35)',
            }}
          >
            <select
              value={selectedTvIp}
              onChange={(e) => setSelectedTvIp(e.target.value)}
              disabled={isBusy}
              title="Select target Samsung Frame TV on Wi-Fi"
              style={{
                padding: '5px 8px',
                borderRadius: '6px',
                background: '#161616',
                border: '1px solid rgba(245, 158, 11, 0.4)',
                color: '#fbbf24',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {samsungTvs.map((tv) => (
                <option key={tv.ip} value={tv.ip}>
                  📺 {tv.name} ({tv.ip})
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={handleDiscoverSamsungTvs}
              disabled={isBusy || isDiscoveringTvs}
              title="Scan Wi-Fi network to discover additional Samsung TVs"
              style={{
                padding: '5px 8px',
                borderRadius: '6px',
                background: 'rgba(255, 255, 255, 0.07)',
                border: '1px solid rgba(255, 255, 255, 0.18)',
                color: '#e2e8f0',
                fontSize: '11.5px',
                fontWeight: 700,
                cursor: (isBusy || isDiscoveringTvs) ? 'wait' : 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {isDiscoveringTvs ? 'Scanning...' : '🔍 Discover'}
            </button>

            <button
              type="button"
              onClick={() => setShowAddRemoteModal(true)}
              disabled={isBusy}
              title="Add a remote Samsung TV by IP address or hostname over the Internet (Tailscale, DynDNS, Port Forward)"
              style={{
                padding: '5px 8px',
                borderRadius: '6px',
                background: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                color: '#38bdf8',
                fontSize: '11.5px',
                fontWeight: 700,
                cursor: isBusy ? 'wait' : 'pointer',
                whiteSpace: 'nowrap',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              <Globe style={{ width: '12px', height: '12px' }} />
              <span>+ Remote IP</span>
            </button>

            <button
              type="button"
              onClick={() =>
                triggerExportWithDestination('samsung_tv', null, {
                  samsung_tv_ip: selectedTvIp,
                  slideshow_minutes: slideshowMinutes,
                })
              }
              disabled={isBusy}
              title={`Push 4K artwork directly to Samsung TV (${selectedTvIp})`}
              style={{
                padding: '6px 14px',
                borderRadius: '6px',
                border: '1.5px solid #f59e0b',
                background: '#f59e0b',
                color: '#000000',
                fontSize: '12px',
                fontWeight: 800,
                cursor: isBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)',
                whiteSpace: 'nowrap',
              }}
            >
              <span>📺</span>
              <span>{isBusy ? 'Pushing...' : 'Push to Samsung TV'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Remote Samsung TV Connection Modal (Over Internet / VPN / Tailscale) */}
      {showAddRemoteModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(2, 6, 23, 0.85)',
            backdropFilter: 'blur(12px)',
            zIndex: 10200,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '480px',
              backgroundColor: '#0c101c',
              border: '1.5px solid #38bdf8',
              borderRadius: '14px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.95), 0 0 35px rgba(56, 189, 248, 0.2)',
              padding: '20px',
              color: '#f8fafc',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Globe style={{ width: '18px', height: '18px', color: '#38bdf8' }} />
                <span style={{ fontSize: '15px', fontWeight: 800 }}>Connect Remote Samsung TV</span>
              </div>
              <button
                type="button"
                onClick={() => setShowAddRemoteModal(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                <X style={{ width: '16px', height: '16px' }} />
              </button>
            </div>

            <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '16px', lineHeight: '1.5' }}>
              Send photos directly to remote Frame TVs outside your local Wi-Fi via <strong>Tailscale</strong>, <strong>WireGuard</strong>, <strong>Dynamic DNS</strong>, or public router IP with port 8002 forwarded.
            </div>

            <form onSubmit={handleAddRemoteTv} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#cbd5e1', marginBottom: '4px', textTransform: 'uppercase' }}>
                  TV IP Address or Hostname (Required)
                </label>
                <input
                  type="text"
                  placeholder="e.g. 100.82.14.22 or cabin-frame.dyndns.org:8002"
                  value={remoteHostInput}
                  onChange={(e) => setRemoteHostInput(e.target.value)}
                  autoFocus
                  required
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '7px',
                    backgroundColor: '#161d2f',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#f8fafc',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    outline: 'none',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#cbd5e1', marginBottom: '4px', textTransform: 'uppercase' }}>
                  Friendly Name (Optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Studio 75'' Frame TV"
                  value={remoteNameInput}
                  onChange={(e) => setRemoteNameInput(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '7px',
                    backgroundColor: '#161d2f',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    color: '#f8fafc',
                    fontSize: '13px',
                    boxSizing: 'border-box',
                    outline: 'none',
                  }}
                />
              </div>

              {remoteAddError && (
                <div style={{ fontSize: '12px', color: '#f87171', padding: '6px 10px', borderRadius: '6px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.25)' }}>
                  {remoteAddError}
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setShowAddRemoteModal(false)}
                  disabled={isAddingRemote}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '7px',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    background: 'rgba(255, 255, 255, 0.05)',
                    color: '#cbd5e1',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isAddingRemote || !remoteHostInput.trim()}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '7px',
                    border: '1.5px solid #38bdf8',
                    background: '#0284c7',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 800,
                    cursor: isAddingRemote ? 'wait' : 'pointer',
                  }}
                >
                  {isAddingRemote ? 'Testing Connection...' : 'Save & Select Remote TV'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
