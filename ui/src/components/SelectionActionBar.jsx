import React, { useState, useEffect, useRef } from 'react';

export default function SelectionActionBar({
  selectedCount = 0,
  totalVisibleCount = 0,
  totalCatalogCount = 0,
  totalPhotos = 0,
  isSelectingAll = false,
  isBatchBusy = false,
  undoStatus = null,
  onTriggerUndo,
  activeCatalog = 'All Catalogs',
  searchQuery = '',
  query = '',
  onSearchChange,
  onQueryChange,
  onSelectAll,
  onSelectAllInCatalog,
  onClearSelection,
  onBatchUpdateStar,
  onBatchClearTags,
  onBatchReassess,
  onReassessCatalog,
  onOpenVoiceTeach,
  onOpenVoiceScout,
  onOpenCollectionsModal,
  collections = [],
  collectionsCount = 0,
  onBatchAddToCollection,
  onCreateCollectionWithSelected,
  onBatchExport,
  onOpenTvCropModal,
  onOpenCustomPrintModal,
  activeShootDate = null,
  selectedPhotosArray = [],
  onOpenInLightroom,
  onSyncEdits,
  onSyncCatalog,
  viewMode = 'grid',
}) {
  const isCatalogView = !viewMode || viewMode === 'grid' || viewMode === 'date';
  const [showBookMenu, setShowBookMenu] = useState(false);
  const [newBookName, setNewBookName] = useState('');
  const [busyBook, setBusyBook] = useState(false);

  // Rate menu state
  const [rateMenuOpen, setRateMenuOpen] = useState(false);
  const rateRef = useRef(null);

  // Lightroom menu state
  const [lrMenuOpen, setLrMenuOpen] = useState(false);
  const lrRef = useRef(null);

  // Export menu state
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const exportRef = useRef(null);

  // Fast Scan dropdown state
  const [fastScanMenuOpen, setFastScanMenuOpen] = useState(false);
  const fastScanRef = useRef(null);

  // Consolidated AI Tools dropdown state
  const [aiToolsMenuOpen, setAiToolsMenuOpen] = useState(false);
  const aiToolsRef = useRef(null);

  // Deep VLM dropdown state
  const [deepVlmMenuOpen, setDeepVlmMenuOpen] = useState(false);
  const deepVlmRef = useRef(null);

  // Idle Rescan menu state
  const [rescanMenuOpen, setRescanMenuOpen] = useState(false);

  const closeAllMenus = () => {
    setShowBookMenu(false);
    setExportMenuOpen(false);
    setFastScanMenuOpen(false);
    setDeepVlmMenuOpen(false);
    setAiToolsMenuOpen(false);
    setRescanMenuOpen(false);
    setRateMenuOpen(false);
    setLrMenuOpen(false);
  };

  // Live hover cards for AI tiers
  const [hoveredCard, setHoveredCard] = useState(null);

  const formatFastEta = (count) => {
    const ms = Math.max(1, count) * 6;
    if (ms < 1000) return `~${Math.round(ms)}ms`;
    const sec = ms / 1000;
    if (sec < 60) return `~${sec.toFixed(1)}s`;
    const mins = Math.floor(sec / 60);
    const remSec = Math.round(sec % 60);
    return `~${mins}m ${remSec}s`;
  };

  const formatDeepEta = (count) => {
    const sec = Math.max(1, count) * 6.5;
    if (sec < 60) return `~${Math.round(sec)}s`;
    const mins = Math.floor(sec / 60);
    const remSec = Math.round(sec % 60);
    if (mins < 60) return `~${mins}m ${remSec}s`;
    const hours = (sec / 3600).toFixed(1);
    return `~${hours} hrs`;
  };

  const rescanRef = useRef(null);
  const bookRef = useRef(null);

  const currentQuery = searchQuery !== undefined ? searchQuery : query || '';
  const handleQueryChange = onSearchChange || onQueryChange || (() => {});

  const displayTotal =
    typeof totalCatalogCount === 'number' && totalCatalogCount > 0
      ? totalCatalogCount
      : typeof totalPhotos === 'number' && totalPhotos > 0
      ? totalPhotos
      : typeof totalVisibleCount === 'number'
      ? totalVisibleCount
      : 0;

  const displayCollectionsCount =
    typeof collectionsCount === 'number' && collectionsCount > 0
      ? collectionsCount
      : collections.length;

  // Close menus on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (rescanRef.current && !rescanRef.current.contains(e.target)) {
        setRescanMenuOpen(false);
      }
      if (bookRef.current && !bookRef.current.contains(e.target)) {
        setShowBookMenu(false);
      }
      if (exportRef.current && !exportRef.current.contains(e.target)) {
        setExportMenuOpen(false);
      }
      if (fastScanRef.current && !fastScanRef.current.contains(e.target)) {
        setFastScanMenuOpen(false);
      }
      if (deepVlmRef.current && !deepVlmRef.current.contains(e.target)) {
        setDeepVlmMenuOpen(false);
      }
      if (aiToolsRef.current && !aiToolsRef.current.contains(e.target)) {
        setAiToolsMenuOpen(false);
      }
      if (rateRef.current && !rateRef.current.contains(e.target)) {
        setRateMenuOpen(false);
      }
      if (lrRef.current && !lrRef.current.contains(e.target)) {
        setLrMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const effectiveShootDate =
    activeShootDate ||
    (selectedPhotosArray.length > 0 ? selectedPhotosArray[0].shoot_date : null);

  const effectiveCatalog =
    (activeCatalog && activeCatalog !== 'All Catalogs' && activeCatalog !== 'ALL'
      ? activeCatalog
      : (selectedPhotosArray.length > 0 ? selectedPhotosArray[0].catalog_name : null)) || 'Active Catalog';

  // Fetch People & Pets identity clusters
  const handleAddExisting = async (colId) => {
    if (!onBatchAddToCollection) return;
    setBusyBook(true);
    try {
      await onBatchAddToCollection(colId);
      setShowBookMenu(false);
    } finally {
      setBusyBook(false);
    }
  };

  const handleCreateNew = async (e) => {
    e.preventDefault();
    if (!newBookName.trim() || !onCreateCollectionWithSelected) return;
    setBusyBook(true);
    try {
      await onCreateCollectionWithSelected(newBookName.trim());
      setNewBookName('');
      setShowBookMenu(false);
    } finally {
      setBusyBook(false);
    }
  };

  const isSelectionActive = selectedCount > 0;

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '22px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9990,
        background: 'rgba(13, 18, 28, 0.96)',
        border: isSelectionActive
          ? '1.5px solid rgba(129, 140, 248, 0.75)'
          : '1px solid rgba(59, 130, 246, 0.35)',
        borderRadius: '16px',
        boxShadow: isSelectionActive
          ? '0 20px 50px rgba(0, 0, 0, 0.85), 0 0 24px rgba(99, 102, 241, 0.25)'
          : '0 20px 50px rgba(0, 0, 0, 0.8)',
        padding: '7px 14px',
        display: 'flex',
        flexWrap: 'nowrap',
        alignItems: 'center',
        justifyContent: 'center',
        width: 'max-content',
        maxWidth: 'min(1400px, 96vw)',
        overflow: 'visible',
        boxSizing: 'border-box',
        gap: '8px',
        color: '#f8fafc',
        backdropFilter: 'blur(16px)',
        whiteSpace: 'nowrap',
        transition: 'all 0.2s ease',
      }}
    >
      {/* ========================================================================= */}
      {/* IDLE DOCK: When 0 photos are selected                                     */}
      {/* Showing N photos | Select All | Undo | People & Pets | Scout | Collections | Rescan ▾ */}
      {/* ========================================================================= */}
      {!isSelectionActive && (
        <>
          {/* Showing N Photos Pill */}
          <div
            style={{
              fontSize: '13.5px',
              color: '#cbd5e1',
              fontVariantNumeric: 'tabular-nums',
              padding: '7px 12px',
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: '9px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            }}
          >
            Showing <strong style={{ color: '#ffffff' }}>{displayTotal.toLocaleString()}</strong> photos
          </div>

          {/* Select All Button */}
          {(onSelectAllInCatalog || onSelectAll) && displayTotal > 0 && (
            <button
              type="button"
              disabled={isSelectingAll}
              onClick={() => {
                if (onSelectAllInCatalog) onSelectAllInCatalog();
                else if (onSelectAll) onSelectAll();
              }}
              title={`Select all ${displayTotal.toLocaleString()} photos in current view (Cmd+A)`}
              style={{
                padding: '7px 13px',
                borderRadius: '8px',
                fontSize: '13.5px',
                fontWeight: 600,
                cursor: isSelectingAll ? 'wait' : 'pointer',
                border: '1px solid rgba(255, 255, 255, 0.18)',
                background: 'rgba(255, 255, 255, 0.06)',
                color: '#e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s',
              }}
            >
              <span>{isSelectingAll ? '⏳ Selecting...' : '☑ Select All'}</span>
            </button>
          )}

          {/* Undo Button */}
          <button
            type="button"
            disabled={!undoStatus?.available || !onTriggerUndo}
            onClick={() => onTriggerUndo && onTriggerUndo()}
            title={
              undoStatus?.available
                ? `Undo (Cmd+Z): ${undoStatus.latest?.description || 'Revert last studio change'}`
                : 'No studio actions to undo yet (Cmd+Z)'
            }
            style={{
              padding: '7px 13px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              cursor: undoStatus?.available ? 'pointer' : 'not-allowed',
              border: undoStatus?.available ? '1px solid #38bdf8' : '1px solid #262b38',
              background: undoStatus?.available
                ? 'rgba(56, 189, 248, 0.14)'
                : 'rgba(20, 23, 32, 0.6)',
              color: undoStatus?.available ? '#7dd3fc' : '#64748b',
              opacity: undoStatus?.available ? 1 : 0.65,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'all 0.15s',
            }}
          >
            <span>↩ Undo</span>
            {undoStatus?.count > 0 && (
              <span
                style={{
                  background: 'rgba(56, 189, 248, 0.25)',
                  color: '#bae6fd',
                  borderRadius: '999px',
                  padding: '1px 7px',
                  fontSize: '12px',
                  fontWeight: 800,
                }}
              >
                {undoStatus.count}
              </span>
            )}
          </button>

          {/* Collections Button */}
          {onOpenCollectionsModal && (
            <button
              type="button"
              onClick={onOpenCollectionsModal}
              title="Open Curated Collections, Panoramic Gallery & Desktop JPEG Export"
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: 'pointer',
                border: '1px solid #f59e0b',
                background: 'rgba(245, 158, 11, 0.18)',
                color: '#fbbf24',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>📚 Collections</span>
              {displayCollectionsCount > 0 && (
                <span
                  style={{
                    background: '#f59e0b',
                    color: '#090b10',
                    borderRadius: '999px',
                    padding: '1px 7px',
                    fontSize: '12px',
                    fontWeight: 800,
                  }}
                >
                  {displayCollectionsCount}
                </span>
              )}
            </button>
          )}

          {/* ⚡ Consolidated AI Catalog & Keyword Tools (UPWARD OPENING) */}
          <div ref={rescanRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setRescanMenuOpen((prev) => !prev)}
              disabled={isBatchBusy}
              title="AI Catalog & Keyword Tools: Scan Visible Day, Scan Entire Catalog, or Scout Archive with AI"
              style={{
                padding: '7px 14px',
                borderRadius: '8px',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: isBatchBusy ? 'wait' : 'pointer',
                border: rescanMenuOpen ? '1px solid #a78bfa' : '1px solid rgba(167, 139, 250, 0.5)',
                background: rescanMenuOpen ? 'rgba(124, 58, 237, 0.28)' : 'rgba(124, 58, 237, 0.18)',
                color: '#e0e7ff',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>⚡ AI Catalog &amp; Keyword Tools</span>
              <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
            </button>

            {rescanMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  right: 0,
                  width: '380px',
                  maxWidth: 'min(380px, calc(100vw - 32px))',
                  maxHeight: 'min(500px, calc(100vh - 120px))',
                  overflowY: 'auto',
                  background: '#0f172a',
                  border: '1px solid rgba(167, 139, 250, 0.45)',
                  borderRadius: '12px',
                  boxShadow: '0 20px 48px rgba(0, 0, 0, 0.9)',
                  padding: '10px',
                  zIndex: 10000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  whiteSpace: 'normal',
                  boxSizing: 'border-box',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    paddingBottom: '6px',
                  }}
                >
                  <span style={{ fontSize: '12px', fontWeight: 800, color: '#e0e7ff' }}>
                    ⚡ AI Catalog &amp; Keyword Tools
                  </span>
                  <span style={{ fontSize: '11px', color: '#a78bfa', fontWeight: 600 }}>
                    {displayTotal.toLocaleString()} in View
                  </span>
                </div>

                {/* Option 1: Fast Scan (Level 1) - Visible Day / Photos */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onBatchReassess && effectiveShootDate) {
                      onBatchReassess('fast_vectors', 'day', { shoot_date: effectiveShootDate });
                    } else if (onBatchReassess) {
                      onBatchReassess('fast_vectors', 'visible');
                    } else if (onReassessCatalog) {
                      onReassessCatalog('fast_vectors');
                    }
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    background: 'rgba(245, 158, 11, 0.1)',
                    color: '#fef3c7',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    whiteSpace: 'normal',
                  }}
                >
                  <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#fde68a', display: 'flex', justifyContent: 'space-between' }}>
                    <span>⚡ Scan This Day / Visible Photos (Fast)</span>
                    <span style={{ fontSize: '11px', color: '#f59e0b' }}>{formatFastEta(displayTotal)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#cbd5e1', lineHeight: '1.3' }}>
                    Pass 1 Macro Biome + Pass 2 Saliency + Pass 3 Subject Drill-Down (~6ms/photo).
                  </div>
                </button>

                {/* Option 2: Deep VLM (Level 2) - Visible Day / Photos */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onBatchReassess && effectiveShootDate) {
                      onBatchReassess('deep_vlm', 'day', { shoot_date: effectiveShootDate });
                    } else if (onBatchReassess) {
                      onBatchReassess('deep_vlm', 'visible');
                    } else if (onReassessCatalog) {
                      onReassessCatalog('deep_vlm');
                    }
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid rgba(56, 189, 248, 0.35)',
                    background: 'rgba(56, 189, 248, 0.1)',
                    color: '#e0f2fe',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    whiteSpace: 'normal',
                  }}
                >
                  <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#7dd3fc', display: 'flex', justifyContent: 'space-between' }}>
                    <span>🧠 Deep VLM This Day / Visible Photos</span>
                    <span style={{ fontSize: '11px', color: '#38bdf8' }}>{formatDeepEta(displayTotal)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#cbd5e1', lineHeight: '1.3' }}>
                    Generative visual reasoning + 4-Pass Cascade (~5-8s/photo).
                  </div>
                </button>

                <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '1px 0' }} />

                {/* Option 3: Fast Scan Entire Catalog */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onReassessCatalog) onReassessCatalog('fast_vectors');
                    else if (onBatchReassess) onBatchReassess('fast_vectors', 'catalog', { catalog_name: effectiveCatalog });
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    background: 'rgba(255, 255, 255, 0.04)',
                    color: '#f8fafc',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    whiteSpace: 'normal',
                  }}
                >
                  <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#f1f5f9', display: 'flex', justifyContent: 'space-between' }}>
                    <span>⚡ Scan Entire Catalog ({totalCatalogCount.toLocaleString()} photos)</span>
                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>{formatFastEta(totalCatalogCount)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', lineHeight: '1.3' }}>
                    Fast 4-Pass Cascade across all frames in "{effectiveCatalog}".
                  </div>
                </button>

                {/* Option 4: Deep VLM Entire Catalog */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onReassessCatalog) onReassessCatalog('deep_vlm');
                    else if (onBatchReassess) onBatchReassess('deep_vlm', 'catalog', { catalog_name: effectiveCatalog });
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    background: 'rgba(255, 255, 255, 0.04)',
                    color: '#f8fafc',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '2px',
                    whiteSpace: 'normal',
                  }}
                >
                  <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#f1f5f9', display: 'flex', justifyContent: 'space-between' }}>
                    <span>🧠 Deep VLM Entire Catalog ({totalCatalogCount.toLocaleString()} photos)</span>
                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>{formatDeepEta(totalCatalogCount)}</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#94a3b8', lineHeight: '1.3' }}>
                    Full generative VLM analysis across entire archive.
                  </div>
                </button>

                <div style={{ height: '1px', background: 'rgba(255,255,255,0.08)', margin: '1px 0' }} />

                {/* Option 5: Scout Full Catalog with AI */}
                {onOpenVoiceScout && (
                  <button
                    type="button"
                    onClick={() => {
                      setRescanMenuOpen(false);
                      onOpenVoiceScout();
                    }}
                    style={{
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid rgba(52, 211, 153, 0.4)',
                      background: 'rgba(16, 185, 129, 0.12)',
                      color: '#a7f3d0',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#34d399' }}>
                        🔎 Scout Full Catalog with AI
                      </div>
                      <div style={{ fontSize: '11px', color: '#cbd5e1' }}>
                        Natural-language story &amp; subject search across entire archive
                      </div>
                    </div>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Exclusive to Catalog Views: Unified Sync Catalog (Edits + New Photos) */}
          {isCatalogView && (onSyncCatalog || onSyncEdits) && (
            <>
              <div style={{ width: '1px', height: '20px', background: 'rgba(255,255,255,0.12)' }} />
              <button
                type="button"
                onClick={() => {
                  closeAllMenus();
                  if (onSyncCatalog) {
                    onSyncCatalog(activeCatalog);
                  } else if (onSyncEdits) {
                    onSyncEdits();
                  }
                }}
                disabled={isBatchBusy}
                title={`Sync ${activeCatalog && activeCatalog !== 'All Catalogs' ? `catalog "${activeCatalog}"` : 'all catalogs'}: update existing Lightroom/XMP edits and scan for newly added photos`}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  fontSize: '13.5px',
                  fontWeight: 700,
                  cursor: isBatchBusy ? 'wait' : 'pointer',
                  border: '1px solid rgba(52, 211, 153, 0.5)',
                  background: 'rgba(16, 185, 129, 0.16)',
                  color: '#6ee7b7',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.15s',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>🔄 Sync Catalog</span>
              </button>
            </>
          )}
        </>
      )}

      {/* ========================================================================= */}
      {/* ACTIVE DOCK: When 1+ photos are selected                                  */}
      {/* ✓ N Selected (Loaded / All / Clear) | Clear Tags | Fast Scan | Deep VLM | Voice Tag | Scout Similar | Add to Book | Undo */}
      {/* ========================================================================= */}
      {isSelectionActive && (
        <>
          {/* Unified Selection Capsule [ ✓ N Selected | ✕ ] */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'rgba(99, 102, 241, 0.22)',
              border: '1px solid rgba(129, 140, 248, 0.5)',
              borderRadius: '9px',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '7px 11px',
                fontWeight: 700,
                fontSize: '13px',
                color: '#e0e7ff',
                whiteSpace: 'nowrap',
              }}
            >
              ✓ {selectedCount.toLocaleString()} Selected
            </div>
            {onClearSelection && (
              <>
                <div style={{ width: '1px', height: '18px', background: 'rgba(129, 140, 248, 0.35)' }} />
                <button
                  type="button"
                  onClick={onClearSelection}
                  title="Clear selection (Esc)"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#c7d2fe',
                    fontSize: '12px',
                    fontWeight: 700,
                    padding: '7px 10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '2px',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = '#fff';
                    e.currentTarget.style.background = 'rgba(255,255,255,0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = '#c7d2fe';
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  ✕ Clear
                </button>
              </>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* Quick Star Rating (Upward popover) */}
          {onBatchUpdateStar && (
            <div ref={rateRef} style={{ position: 'relative' }}>
              <button
                type="button"
                disabled={isBatchBusy}
                onClick={() => setRateMenuOpen((prev) => !prev)}
                title="Rate selected photos 0-5 Stars (or press keys 0-5)"
                style={{
                  background: rateMenuOpen ? 'rgba(245, 158, 11, 0.28)' : 'rgba(245, 158, 11, 0.16)',
                  border: rateMenuOpen ? '1px solid #fbbf24' : '1px solid rgba(251, 191, 36, 0.45)',
                  color: '#fbbf24',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '7px 11px',
                  borderRadius: '9px',
                  cursor: isBatchBusy ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>★ Rate</span>
                <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
              </button>

              {rateMenuOpen && (
                <div
                  style={{
                    position: 'absolute',
                    bottom: 'calc(100% + 10px)',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: '#111827',
                    border: '1px solid rgba(251, 191, 36, 0.4)',
                    borderRadius: '10px',
                    padding: '6px',
                    boxShadow: '0 16px 36px rgba(0,0,0,0.85)',
                    zIndex: 10000,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      setRateMenuOpen(false);
                      onBatchUpdateStar(0);
                    }}
                    title="Clear rating (Key 0)"
                    style={{
                      background: 'rgba(239, 68, 68, 0.18)',
                      border: '1px solid rgba(248, 113, 113, 0.35)',
                      color: '#fca5a5',
                      fontSize: '12px',
                      fontWeight: 700,
                      padding: '5px 8px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    0 (Clear)
                  </button>
                  {[1, 2, 3, 4, 5].map((stars) => (
                    <button
                      key={stars}
                      type="button"
                      onClick={() => {
                        setRateMenuOpen(false);
                        onBatchUpdateStar(stars);
                      }}
                      title={`Set ${stars} Star${stars > 1 ? 's' : ''} (Key ${stars})`}
                      style={{
                        background: 'rgba(245, 158, 11, 0.18)',
                        border: '1px solid rgba(251, 191, 36, 0.35)',
                        color: '#fde68a',
                        fontSize: '12px',
                        fontWeight: 700,
                        padding: '5px 8px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {stars}★
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* ⚡ Consolidated AI Keyword & Tagging Tools (UPWARD POPUP) */}
          <div ref={aiToolsRef} style={{ position: 'relative' }}>
            <button
              type="button"
              disabled={isBatchBusy}
              onClick={() => setAiToolsMenuOpen((prev) => !prev)}
              title="AI Keyword & Inspection Tools (Fast Scan, Deep VLM, AI Voice Tag, Scout Similar, Clear Tags)"
              style={{
                background: aiToolsMenuOpen
                  ? 'rgba(124, 58, 237, 0.28)'
                  : 'rgba(124, 58, 237, 0.18)',
                border: aiToolsMenuOpen
                  ? '1px solid #a78bfa'
                  : '1px solid rgba(167, 139, 250, 0.55)',
                color: '#e0e7ff',
                fontSize: '13px',
                fontWeight: 700,
                padding: '7px 11px',
                borderRadius: '9px',
                cursor: isBatchBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>⚡ AI Tools</span>
              <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
            </button>

            {aiToolsMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '380px',
                  maxWidth: 'min(380px, calc(100vw - 32px))',
                  maxHeight: 'min(500px, calc(100vh - 120px))',
                  overflowY: 'auto',
                  background: '#0f172a',
                  border: '1px solid rgba(167, 139, 250, 0.45)',
                  borderRadius: '12px',
                  padding: '12px',
                  boxShadow: '0 20px 48px rgba(0, 0, 0, 0.9)',
                  zIndex: 10000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  whiteSpace: 'normal',
                  boxSizing: 'border-box',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid rgba(255,255,255,0.1)',
                    paddingBottom: '8px',
                  }}
                >
                  <span style={{ fontSize: '12.5px', fontWeight: 800, color: '#e0e7ff' }}>
                    ⚡ AI Keyword & Tagging Tools
                  </span>
                  <span style={{ fontSize: '11px', color: '#a78bfa', fontWeight: 600 }}>
                    {selectedCount.toLocaleString()} Selected
                  </span>
                </div>

                {/* Level 1: Fast Scan Section */}
                {onBatchReassess && (
                  <div
                    style={{
                      background: 'rgba(245, 158, 11, 0.08)',
                      border: '1px solid rgba(251, 191, 36, 0.25)',
                      borderRadius: '8px',
                      padding: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '5px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: '#fde68a' }}>
                        ⚡ Fast Scan (Level 1 — 4-Pass Cascade)
                      </span>
                      <span style={{ fontSize: '10.5px', color: '#f59e0b', fontWeight: 600 }}>
                        {formatFastEta(selectedCount)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button
                        type="button"
                        onClick={() => {
                          setAiToolsMenuOpen(false);
                          onBatchReassess('fast_vectors', 'selected');
                        }}
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(251, 191, 36, 0.35)',
                          background: 'rgba(251, 191, 36, 0.15)',
                          color: '#fef3c7',
                          fontSize: '11.5px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        Selected ({selectedCount})
                      </button>
                      {effectiveShootDate && (
                        <button
                          type="button"
                          onClick={() => {
                            setAiToolsMenuOpen(false);
                            onBatchReassess('fast_vectors', 'day', { shoot_date: effectiveShootDate });
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 8px',
                            borderRadius: '6px',
                            border: '1px solid rgba(255, 255, 255, 0.12)',
                            background: 'rgba(255, 255, 255, 0.05)',
                            color: '#cbd5e1',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Shoot Day
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setAiToolsMenuOpen(false);
                          onBatchReassess('fast_vectors', 'catalog', { catalog_name: effectiveCatalog });
                        }}
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: '#cbd5e1',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Full Catalog
                      </button>
                    </div>
                  </div>
                )}

                {/* Level 2: Deep VLM Section */}
                {onBatchReassess && (
                  <div
                    style={{
                      background: 'rgba(56, 189, 248, 0.08)',
                      border: '1px solid rgba(56, 189, 248, 0.25)',
                      borderRadius: '8px',
                      padding: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '5px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '12px', fontWeight: 700, color: '#7dd3fc' }}>
                        🧠 Deep VLM (Level 2 — Qwen2.5-VL)
                      </span>
                      <span style={{ fontSize: '10.5px', color: '#38bdf8', fontWeight: 600 }}>
                        {formatDeepEta(selectedCount)}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button
                        type="button"
                        onClick={() => {
                          setAiToolsMenuOpen(false);
                          onBatchReassess('deep_vlm', 'selected');
                        }}
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(56, 189, 248, 0.35)',
                          background: 'rgba(56, 189, 248, 0.15)',
                          color: '#e0f2fe',
                          fontSize: '11.5px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        Selected ({selectedCount})
                      </button>
                      {effectiveShootDate && (
                        <button
                          type="button"
                          onClick={() => {
                            setAiToolsMenuOpen(false);
                            onBatchReassess('deep_vlm', 'day', { shoot_date: effectiveShootDate });
                          }}
                          style={{
                            flex: 1,
                            padding: '6px 8px',
                            borderRadius: '6px',
                            border: '1px solid rgba(255, 255, 255, 0.12)',
                            background: 'rgba(255, 255, 255, 0.05)',
                            color: '#cbd5e1',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Shoot Day
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setAiToolsMenuOpen(false);
                          onBatchReassess('deep_vlm', 'catalog', { catalog_name: effectiveCatalog });
                        }}
                        style={{
                          flex: 1,
                          padding: '6px 8px',
                          borderRadius: '6px',
                          border: '1px solid rgba(255, 255, 255, 0.12)',
                          background: 'rgba(255, 255, 255, 0.05)',
                          color: '#cbd5e1',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Full Catalog
                      </button>
                    </div>
                  </div>
                )}

                {/* AI Voice Tag & Teach */}
                {onOpenVoiceTeach && (
                  <button
                    type="button"
                    onClick={() => {
                      setAiToolsMenuOpen(false);
                      onOpenVoiceTeach();
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid rgba(167, 139, 250, 0.4)',
                      background: 'rgba(124, 58, 237, 0.18)',
                      color: '#f8fafc',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#c4b5fd' }}>
                        🎙️ AI Voice Tag & Teach
                      </div>
                      <div style={{ fontSize: '11px', color: '#cbd5e1' }}>
                        Speak or type ground-truth tags (2.0x priority)
                      </div>
                    </div>
                    <span style={{ fontSize: '11px', color: '#a78bfa', fontWeight: 700 }}>Instant</span>
                  </button>
                )}

                {/* Scout Similar */}
                {onOpenVoiceScout && (
                  <button
                    type="button"
                    onClick={() => {
                      setAiToolsMenuOpen(false);
                      onOpenVoiceScout();
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid rgba(52, 211, 153, 0.35)',
                      background: 'rgba(16, 185, 129, 0.12)',
                      color: '#6ee7b7',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#a7f3d0' }}>
                        🔎 Scout Similar Photos
                      </div>
                      <div style={{ fontSize: '11px', color: '#cbd5e1' }}>
                        Hunt for visual matches across entire archive
                      </div>
                    </div>
                  </button>
                )}

                {/* Clear Tags */}
                {onBatchClearTags && (
                  <button
                    type="button"
                    onClick={() => {
                      setAiToolsMenuOpen(false);
                      onBatchClearTags();
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid rgba(248, 113, 113, 0.35)',
                      background: 'rgba(239, 68, 68, 0.12)',
                      color: '#fca5a5',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#fca5a5' }}>
                        🧹 Clear Tags (Selected Photos)
                      </div>
                      <div style={{ fontSize: '11px', color: '#cbd5e1' }}>
                        Clean-slate wipe with instant Undo (Cmd+Z)
                      </div>
                    </div>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Add Selected to Collection (UPWARD OPENING) */}
          <div ref={bookRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setShowBookMenu((prev) => !prev)}
              title="Add selected photos to a curated collection or book"
              style={{
                background: 'rgba(245, 158, 11, 0.18)',
                border: '1px solid rgba(251, 191, 36, 0.5)',
                color: '#fde68a',
                fontSize: '13px',
                fontWeight: 700,
                padding: '7px 11px',
                borderRadius: '9px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
              }}
            >
              <span>📚 Collection</span>
              <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
            </button>

            {showBookMenu && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '320px',
                  maxWidth: 'min(320px, calc(100vw - 32px))',
                  maxHeight: 'min(480px, calc(100vh - 120px))',
                  overflowY: 'auto',
                  background: '#111827',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '12px',
                  padding: '12px',
                  boxShadow: '0 16px 40px rgba(0,0,0,0.85)',
                  zIndex: 10000,
                  boxSizing: 'border-box',
                }}
              >
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#f8fafc', marginBottom: '8px' }}>
                  Add {selectedCount} Photo{selectedCount > 1 ? 's' : ''} to Collection:
                </div>

                {/* + Add New Collection Form */}
                <form onSubmit={handleCreateNew} style={{ display: 'flex', gap: '6px', marginBottom: '10px' }}>
                  <input
                    type="text"
                    placeholder="New Collection title..."
                    value={newBookName}
                    onChange={(e) => setNewBookName(e.target.value)}
                    style={{
                      flex: 1,
                      background: '#1f2937',
                      border: '1px solid rgba(255,255,255,0.25)',
                      borderRadius: '7px',
                      color: '#fff',
                      padding: '7px 9px',
                      fontSize: '12px',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={busyBook || !newBookName.trim()}
                    style={{
                      background: '#f59e0b',
                      border: '1.5px solid #fbbf24',
                      color: '#090b10',
                      fontWeight: 800,
                      fontSize: '13px',
                      padding: '8px 14px',
                      borderRadius: '8px',
                      cursor: newBookName.trim() ? 'pointer' : 'not-allowed',
                      opacity: newBookName.trim() ? 1 : 0.6,
                      whiteSpace: 'nowrap',
                      boxShadow: '0 2px 10px rgba(245, 158, 11, 0.3)',
                    }}
                  >
                    ＋ Create
                  </button>
                </form>

                {collections.length > 0 && (
                  <div
                    style={{
                      maxHeight: '160px',
                      overflowY: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '2px', textTransform: 'uppercase' }}>
                      Existing Collections ({collections.length})
                    </div>
                    {collections.map((col) => (
                      <button
                        key={col.id}
                        type="button"
                        disabled={busyBook}
                        onClick={() => handleAddExisting(col.id)}
                        style={{
                          textAlign: 'left',
                          background: 'rgba(255,255,255,0.06)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          color: '#f1f5f9',
                          padding: '7px 10px',
                          borderRadius: '7px',
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '8px' }}>
                          📚 {col.name}
                        </span>
                        <span style={{ color: '#fbbf24', fontSize: '11px', fontWeight: 700, background: 'rgba(245,158,11,0.2)', padding: '1px 6px', borderRadius: '999px' }}>
                          {col.item_count || 0}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* Sleek Lightroom Menu (UPWARD OPENING) */}
          <div ref={lrRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => {
                const next = !lrMenuOpen;
                closeAllMenus();
                setLrMenuOpen(next);
              }}
              disabled={isBatchBusy}
              title="Lightroom Classic integration (Edit in Lightroom or Sync Edits)"
              style={{
                background: lrMenuOpen
                  ? 'rgba(56, 189, 248, 0.28)'
                  : 'rgba(56, 189, 248, 0.14)',
                border: lrMenuOpen
                  ? '1px solid #38bdf8'
                  : '1px solid rgba(56, 189, 248, 0.45)',
                color: '#bae6fd',
                fontSize: '13px',
                fontWeight: 700,
                padding: '7px 11px',
                borderRadius: '9px',
                cursor: isBatchBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
              }}
            >
              <span>🎨 Lightroom</span>
              <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
            </button>

            {lrMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '260px',
                  background: '#0f172a',
                  border: '1px solid rgba(56, 189, 248, 0.45)',
                  borderRadius: '12px',
                  padding: '8px',
                  boxShadow: '0 20px 48px rgba(0, 0, 0, 0.9)',
                  zIndex: 10000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                <button
                  type="button"
                  onClick={() => {
                    closeAllMenus();
                    if (onOpenInLightroom) onOpenInLightroom('lightroom');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    background: 'rgba(56, 189, 248, 0.12)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    color: '#e0f2fe',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '15px' }}>🎨</span>
                    <div>
                      <div style={{ fontSize: '12.5px', fontWeight: 700 }}>Edit in Lightroom</div>
                      <div style={{ fontSize: '10.5px', color: '#94a3b8' }}>Open matching catalog</div>
                    </div>
                  </div>
                  <kbd style={{ fontSize: '10px', padding: '2px 5px', background: '#1e293b', borderRadius: '4px', color: '#38bdf8' }}>L</kbd>
                </button>

                {onSyncEdits && (
                  <button
                    type="button"
                    onClick={() => {
                      closeAllMenus();
                      onSyncEdits();
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      background: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                      color: '#a7f3d0',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '15px' }}>🔄</span>
                      <div>
                        <div style={{ fontSize: '12.5px', fontWeight: 700 }}>Sync Edits</div>
                        <div style={{ fontSize: '10.5px', color: '#94a3b8' }}>Read saved XMP &amp; previews</div>
                      </div>
                    </div>
                    <kbd style={{ fontSize: '10px', padding: '2px 5px', background: '#1e293b', borderRadius: '4px', color: '#34d399' }}>⇧S</kbd>
                  </button>
                )}
              </div>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* 📤 Export Dropdown Menu (UPWARD OPENING) */}
          <div ref={exportRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setExportMenuOpen((prev) => !prev)}
              disabled={isBatchBusy}
              title="Export or copy selected photos (High-Res JPEGs, Original Masters, or 65-inch TV Showcase 16:9 crop)"
              style={{
                background: exportMenuOpen
                  ? 'rgba(16, 185, 129, 0.28)'
                  : 'rgba(16, 185, 129, 0.18)',
                border: exportMenuOpen
                  ? '1px solid #10b981'
                  : '1px solid rgba(52, 211, 153, 0.55)',
                color: '#6ee7b7',
                fontSize: '13px',
                fontWeight: 700,
                padding: '7px 12px',
                borderRadius: '9px',
                cursor: isBatchBusy ? 'wait' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>📤 Export</span>
              <span style={{ fontSize: '11px', opacity: 0.85 }}>▾</span>
            </button>

            {exportMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  right: 0,
                  width: '360px',
                  maxWidth: 'min(360px, calc(100vw - 32px))',
                  maxHeight: 'min(500px, calc(100vh - 120px))',
                  overflowY: 'auto',
                  background: '#0f172a',
                  border: '1px solid rgba(52, 211, 153, 0.4)',
                  borderRadius: '12px',
                  padding: '10px',
                  boxShadow: '0 20px 48px rgba(0, 0, 0, 0.85)',
                  zIndex: 10000,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                  whiteSpace: 'normal',
                  boxSizing: 'border-box',
                }}
              >
                <div
                  style={{
                    fontSize: '11px',
                    fontWeight: 800,
                    color: '#94a3b8',
                    padding: '4px 8px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    borderBottom: '1px solid rgba(255,255,255,0.08)',
                    marginBottom: '2px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    whiteSpace: 'normal',
                    boxSizing: 'border-box',
                  }}
                >
                  <span>Export {selectedCount.toLocaleString()} Selected</span>
                  <span style={{ color: '#34d399' }}>Desktop</span>
                </div>

                {/* Option 1: Custom Print Sizing (JPEG) Modal */}
                <button
                  type="button"
                  onClick={() => {
                    setExportMenuOpen(false);
                    if (onOpenCustomPrintModal) {
                      onOpenCustomPrintModal();
                    } else if (onBatchExport) {
                      onBatchExport('jpeg', { long_edge: 6000, dpi: 300 });
                    }
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(168, 85, 247, 0.35)',
                    background: 'rgba(168, 85, 247, 0.10)',
                    color: '#f1f5f9',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                    whiteSpace: 'normal',
                    boxSizing: 'border-box',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#c084fc', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>🖨️ Custom Print Sizing (JPEG)</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#cbd5e1', lineHeight: '1.35', whiteSpace: 'normal' }}>
                    Print sizing presets (3,600px up to 12,000px) and 240/300 DPI with develop edits applied.
                  </div>
                </button>

                {/* Option 2: 65" TV Showcase & Samsung TV Push 16:9 Crop JPEGs (Always opens Crop Modal) */}
                <button
                  type="button"
                  onClick={() => {
                    setExportMenuOpen(false);
                    if (onOpenTvCropModal) {
                      onOpenTvCropModal();
                    } else if (onBatchExport) {
                      onBatchExport('tv_showcase');
                    }
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(245, 158, 11, 0.5)',
                    background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.16) 0%, rgba(16, 185, 129, 0.14) 100%)',
                    color: '#e0f2fe',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                    whiteSpace: 'normal',
                    boxSizing: 'border-box',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 800, color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>📺 Samsung TV Push &amp; 16:9 Showcase</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#f1f5f9', lineHeight: '1.35', whiteSpace: 'normal' }}>
                    Interactive 16:9 crop framing + Push directly to Samsung Frame TV over Wi-Fi (or Desktop, iCloud, Folder).
                  </div>
                </button>

                {/* Option 3: Archival Master TIFF (.tif) */}
                <button
                  type="button"
                  onClick={() => {
                    setExportMenuOpen(false);
                    if (onBatchExport) onBatchExport('tiff');
                  }}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(255, 255, 255, 0.1)',
                    background: 'rgba(255, 255, 255, 0.04)',
                    color: '#f1f5f9',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                    whiteSpace: 'normal',
                    boxSizing: 'border-box',
                  }}
                >
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>📁 Archival Master TIFF (.tif)</span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#cbd5e1', lineHeight: '1.35', whiteSpace: 'normal' }}>
                    Uncompressed archival master (.tif) with Lightroom develop edits applied and full IPTC/XMP tags embedded.
                  </div>
                </button>
              </div>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* Undo in Active Dock */}
          <button
            type="button"
            disabled={!undoStatus?.available || !onTriggerUndo}
            onClick={() => onTriggerUndo && onTriggerUndo()}
            title={
              undoStatus?.available
                ? `Undo (Cmd+Z): ${undoStatus.latest?.description || 'Revert last studio change'}`
                : 'No studio actions to undo yet (Cmd+Z)'
            }
            style={{
              padding: '6px 10px',
              borderRadius: '8px',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: undoStatus?.available ? 'pointer' : 'not-allowed',
              border: undoStatus?.available ? '1px solid #38bdf8' : '1px solid #262b38',
              background: undoStatus?.available
                ? 'rgba(56, 189, 248, 0.14)'
                : 'rgba(20, 23, 32, 0.6)',
              color: undoStatus?.available ? '#7dd3fc' : '#64748b',
              opacity: undoStatus?.available ? 1 : 0.65,
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              transition: 'all 0.15s',
            }}
          >
            <span>↩ Undo</span>
            {undoStatus?.count > 0 && (
              <span
                style={{
                  background: 'rgba(56, 189, 248, 0.25)',
                  color: '#bae6fd',
                  borderRadius: '999px',
                  padding: '1px 5px',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                {undoStatus.count}
              </span>
            )}
          </button>
        </>
      )}
    </div>
  );
}
