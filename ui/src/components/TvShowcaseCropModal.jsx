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
  Info
} from 'lucide-react';

/**
 * TvShowcaseCropModal.jsx
 *
 * Interactive 16:9 crop framing modal for 65" TV Showcase JPEG exports.
 * Allows choosing where the 16:9 crop is placed (Sky/Top, Golden Horizon, Center, Ground/Bottom, or custom drag).
 * Previews every photo in selection, supports per-photo adjustment or "Apply to all",
 * and exports exact 12,500 px (12,500 × 7,031 px) JPEGs at 180 DPI with full IPTC/XMP tags embedded.
 */
export default function TvShowcaseCropModal({
  isOpen,
  onClose,
  photos = [],
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

  // Aspect ratio calculation
  const targetRatio = 16.0 / 9.0; // 1.777778
  const naturalAspect =
    imageNaturalDim.width && imageNaturalDim.height
      ? imageNaturalDim.width / imageNaturalDim.height
      : targetRatio;

  // Is image taller than 16:9? (e.g. 3:2, 4:3, Phase One, portrait) -> vertical crop adjustment
  // Is image wider than 16:9? (e.g. panoramic) -> horizontal crop adjustment
  const isTaller = naturalAspect < targetRatio;
  const isWider = naturalAspect > targetRatio;

  // Crop box percentage sizing
  // If taller: width is 100%, height is (naturalAspect / targetRatio) * 100%
  // If wider: height is 100%, width is (targetRatio / naturalAspect) * 100%
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

  // Mouse drag handlers for direct viewport dragging
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
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();

      if (isTaller) {
        const slackHeightPx = rect.height * ((100 - boxHeightPct) / 100);
        if (slackHeightPx > 0) {
          const deltaY = e.clientY - dragStartY;
          const deltaNormY = deltaY / slackHeightPx;
          updateCrop(initialNormY + deltaNormY, normX);
        }
      } else if (isWider) {
        const slackWidthPx = rect.width * ((100 - boxWidthPct) / 100);
        if (slackWidthPx > 0) {
          const deltaX = e.clientX - dragStartX;
          const deltaNormX = deltaX / slackWidthPx;
          updateCrop(normY, initialNormX + deltaNormX);
        }
      }
    },
    [
      isDragging,
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

  const handleConfirm = () => {
    if (onConfirmExport) {
      onConfirmExport(crops);
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
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        boxSizing: 'border-box',
        color: '#f8fafc',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '1120px',
          maxHeight: '94vh',
          backgroundColor: '#0c101c',
          border: '1px solid rgba(52, 211, 153, 0.35)',
          borderRadius: '16px',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.95), 0 0 40px rgba(16, 185, 129, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* ========================================================================= */}
        {/* MODAL HEADER                                                              */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(180deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0) 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div
              style={{
                width: '38px',
                height: '38px',
                borderRadius: '10px',
                background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.25) 0%, rgba(56, 189, 248, 0.25) 100%)',
                border: '1px solid rgba(52, 211, 153, 0.5)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#34d399',
              }}
            >
              <Tv style={{ width: '20px', height: '20px' }} />
            </div>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 800, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span>65" TV Showcase 16:9 Crop Placement</span>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'rgba(52, 211, 153, 0.18)',
                    color: '#6ee7b7',
                    border: '1px solid rgba(52, 211, 153, 0.35)',
                  }}
                >
                  12,500 × 7,031 px • 180 DPI
                </span>
              </div>
              <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                Position the 16:9 crop box to emphasize sky, horizon, or foreground. Full IPTC/XMP keywords & metadata will be embedded.
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={isBusy}
            style={{
              padding: '8px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              background: 'rgba(255, 255, 255, 0.05)',
              color: '#94a3b8',
              cursor: isBusy ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="Close (Esc)"
          >
            <X style={{ width: '18px', height: '18px' }} />
          </button>
        </div>

        {/* ========================================================================= */}
        {/* MODAL BODY (PREVIEW & CONTROLS)                                           */}
        {/* ========================================================================= */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            padding: '16px 20px',
            gap: '14px',
          }}
        >
          {/* Top Bar: Photo Switcher & Filename */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '13px',
              color: '#cbd5e1',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
              <span style={{ fontWeight: 700, color: '#f8fafc', whiteSpace: 'nowrap' }}>
                Photo {currentIndex + 1} of {photos.length}:
              </span>
              <span style={{ color: '#94a3b8', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '420px' }}>
                {photoTitle}
              </span>
              {imageNaturalDim.width > 0 && (
                <span style={{ fontSize: '11px', color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
                  ({imageNaturalDim.width.toLocaleString()} × {imageNaturalDim.height.toLocaleString()} px)
                </span>
              )}
            </div>

            {photos.length > 1 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <button
                  type="button"
                  onClick={() => setCurrentIndex((prev) => (prev > 0 ? prev - 1 : photos.length - 1))}
                  style={{
                    padding: '4px 8px',
                    borderRadius: '6px',
                    background: 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#cbd5e1',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                  }}
                >
                  <ChevronLeft style={{ width: '14px', height: '14px' }} />
                  <span>Prev</span>
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentIndex((prev) => (prev < photos.length - 1 ? prev + 1 : 0))}
                  style={{
                    padding: '4px 8px',
                    borderRadius: '6px',
                    background: 'rgba(255, 255, 255, 0.06)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#cbd5e1',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                  }}
                >
                  <span>Next</span>
                  <ChevronRight style={{ width: '14px', height: '14px' }} />
                </button>
              </div>
            )}
          </div>

          {/* Interactive Crop Viewport Area */}
          <div
            style={{
              position: 'relative',
              width: '100%',
              height: '460px',
              backgroundColor: '#05070d',
              borderRadius: '12px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              overflow: 'hidden',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              userSelect: 'none',
            }}
          >
            {/* The Image Container with Crop Overlays */}
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
                  maxHeight: '460px',
                  maxWidth: '100%',
                  objectFit: 'contain',
                  display: 'block',
                  pointerEvents: 'none',
                }}
              />

              {/* 16:9 Viewport Crop Box Overlay */}
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
                {/* Rule of Thirds Grid Lines */}
                <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
                  <div
                    style={{
                      position: 'absolute',
                      top: '33.333%',
                      left: 0,
                      right: 0,
                      height: '1px',
                      borderTop: '1px dashed rgba(255, 255, 255, 0.28)',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      top: '66.666%',
                      left: 0,
                      right: 0,
                      height: '1px',
                      borderTop: '1px dashed rgba(255, 255, 255, 0.28)',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      left: '33.333%',
                      top: 0,
                      bottom: 0,
                      width: '1px',
                      borderLeft: '1px dashed rgba(255, 255, 255, 0.28)',
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      left: '66.666%',
                      top: 0,
                      bottom: 0,
                      width: '1px',
                      borderLeft: '1px dashed rgba(255, 255, 255, 0.28)',
                    }}
                  />
                </div>

                {/* Floating "Drag to position" badge */}
                <div
                  style={{
                    position: 'absolute',
                    top: '8px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(15, 23, 42, 0.82)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid rgba(52, 211, 153, 0.45)',
                    padding: '3px 10px',
                    borderRadius: '999px',
                    fontSize: '11px',
                    fontWeight: 700,
                    color: '#6ee7b7',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    pointerEvents: 'none',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                  }}
                >
                  <Move style={{ width: '12px', height: '12px' }} />
                  <span>
                    {isTaller ? 'DRAG UP/DOWN TO FRAME' : isWider ? 'DRAG LEFT/RIGHT TO FRAME' : '16:9 VIEWPORT'}
                  </span>
                </div>

                {/* Corner Accents */}
                <div style={{ position: 'absolute', top: -3, left: -3, width: 10, height: 10, borderTop: '3px solid #34d399', borderLeft: '3px solid #34d399' }} />
                <div style={{ position: 'absolute', top: -3, right: -3, width: 10, height: 10, borderTop: '3px solid #34d399', borderRight: '3px solid #34d399' }} />
                <div style={{ position: 'absolute', bottom: -3, left: -3, width: 10, height: 10, borderBottom: '3px solid #34d399', borderLeft: '3px solid #34d399' }} />
                <div style={{ position: 'absolute', bottom: -3, right: -3, width: 10, height: 10, borderBottom: '3px solid #34d399', borderRight: '3px solid #34d399' }} />
              </div>
            </div>
          </div>

          {/* Controls Bar: Presets & Precision Slider */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
              padding: '12px 14px',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.07)',
            }}
          >
            {/* Presets */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Placement Presets:
              </span>
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
                      padding: '5px 11px',
                      borderRadius: '7px',
                      fontSize: '12px',
                      fontWeight: isActive ? 700 : 500,
                      border: isActive ? '1px solid #10b981' : '1px solid rgba(255, 255, 255, 0.12)',
                      background: isActive ? 'rgba(16, 185, 129, 0.22)' : 'rgba(255, 255, 255, 0.05)',
                      color: isActive ? '#6ee7b7' : '#e2e8f0',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '5px',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>{p.icon}</span>
                    <span>{p.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Precision Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Sliders style={{ width: '14px', height: '14px', color: '#94a3b8' }} />
              <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 600 }}>
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
                  width: '130px',
                  accentColor: '#10b981',
                  cursor: 'pointer',
                }}
              />
              <span style={{ fontSize: '12px', fontVariantNumeric: 'tabular-nums', color: '#34d399', fontWeight: 700, width: '36px' }}>
                {Math.round((isTaller ? normY : normX) * 100)}%
              </span>
            </div>
          </div>

          {/* Filmstrip / Thumbnail Stepper if multiple photos */}
          {photos.length > 1 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                background: 'rgba(255, 255, 255, 0.02)',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.05)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto', maxWidth: '680px', paddingBottom: '2px' }}>
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
                        width: '44px',
                        height: '32px',
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
                        <div style={{ fontSize: '10px', color: '#94a3b8' }}>{idx + 1}</div>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Apply to All Button */}
              <button
                type="button"
                onClick={handleApplyToAll}
                style={{
                  padding: '6px 12px',
                  borderRadius: '7px',
                  border: '1px solid rgba(56, 189, 248, 0.4)',
                  background: 'rgba(56, 189, 248, 0.12)',
                  color: '#7dd3fc',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  whiteSpace: 'nowrap',
                }}
              >
                <Layers style={{ width: '14px', height: '14px' }} />
                <span>{appliedToAllNotice ? '✓ Applied to all!' : 'Apply Placement to All Photos'}</span>
              </button>
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* MODAL FOOTER                                                              */}
        {/* ========================================================================= */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#090d17',
          }}
        >
          {/* Tech Specs Banner */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#94a3b8' }}>
            <Sparkles style={{ width: '15px', height: '15px', color: '#34d399' }} />
            <span>
              Target: <strong style={{ color: '#f8fafc' }}>12,500 × 7,031 px</strong> • <strong style={{ color: '#f8fafc' }}>180 DPI</strong> • sRGB Quality 96 • <span style={{ color: '#34d399' }}>Embedded IPTC/XMP Tags &amp; Location</span>
            </span>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isBusy}
              style={{
                padding: '9px 16px',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                background: 'rgba(255, 255, 255, 0.05)',
                color: '#cbd5e1',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isBusy ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleConfirm}
              disabled={isBusy}
              style={{
                padding: '9px 20px',
                borderRadius: '8px',
                border: '1px solid rgba(52, 211, 153, 0.6)',
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 700,
                cursor: isBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: '0 4px 16px rgba(16, 185, 129, 0.35)',
              }}
            >
              <Download style={{ width: '16px', height: '16px' }} />
              <span>
                {isBusy
                  ? 'Exporting...'
                  : `Export ${photos.length.toLocaleString()} 12.5k TV Showcase JPEG${photos.length > 1 ? 's' : ''}`}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
