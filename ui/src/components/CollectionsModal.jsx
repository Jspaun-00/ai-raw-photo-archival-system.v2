import React, { useState, useEffect, useCallback } from 'react';

const BOOK_RATIOS = [
  {
    id: '2.2:1',
    label: '🖼️ Panoramic Book (2.2 : 1)',
    aspectRatio: '2.2 / 1',
    spreadAspectRatio: '2.6 / 1',
    desc: 'Wide Horizontal Panoramic Monograph (Default)',
  },
  {
    id: '16:10',
    label: '📐 Classic Landscape (16 : 10)',
    aspectRatio: '16 / 10',
    spreadAspectRatio: '2.1 / 1',
    desc: 'Traditional Exhibition Portfolio Format',
  },
  {
    id: '3:1',
    label: '📖 Full-Bleed Exhibition (3 : 1 Ultra-Pano)',
    aspectRatio: '3 / 1',
    spreadAspectRatio: '3.2 / 1',
    desc: 'Ultra-Wide Panoramic Horizon Format',
  },
];

export default function CollectionsModal({
  isOpen,
  onClose,
  collections = [],
  initialCollectionId = null,
  initialMode = 'sequence',
  onRefreshCollections,
  onCollectionsUpdated,
  onSelectPhotoInLightbox,
  onSelectPhoto,
  jobStatus = null,
  onPauseJob,
  onResumeJob,
  onCancelJob,
  onJobStarted,
}) {
  const openInLightbox = onSelectPhotoInLightbox || onSelectPhoto;
  const refreshCollections = onRefreshCollections || onCollectionsUpdated;

  const [selectedId, setSelectedId] = useState(initialCollectionId);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  // Create collection form (Top-left high visibility)
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);

  // Sub-mode: 'sequence' (Sequencing & Reordering Grid) vs 'book' (Panoramic Book Preview)
  const [mode, setMode] = useState(initialMode || 'sequence');
  const [bookSpreadMode, setBookSpreadMode] = useState('single'); // 'single' | 'spread'
  const [bookAspectRatioId, setBookAspectRatioId] = useState('2.2:1'); // Default 2.2:1 Panoramic
  const [bookPageIndex, setBookPageIndex] = useState(0);

  // Drag and drop state
  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  // Export state
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);

  const safeCollections = Array.isArray(collections) ? collections : [];

  useEffect(() => {
    if (initialMode) {
      setMode(initialMode);
    }
  }, [initialMode, isOpen]);

  useEffect(() => {
    if (initialCollectionId) {
      setSelectedId(initialCollectionId);
    } else if (!selectedId && safeCollections.length > 0) {
      setSelectedId(safeCollections[0].id);
    }
  }, [initialCollectionId, safeCollections, selectedId]);

  const fetchCollectionDetail = useCallback(async (colId) => {
    if (!colId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/collections/${colId}`);
      if (res.ok) {
        const data = await res.json();
        setDetail(data);
        setBookPageIndex(0);
      }
    } catch (err) {
      console.error('Failed to load collection detail:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen && selectedId) {
      fetchCollectionDetail(selectedId);
      setExportResult(null);
    }
  }, [isOpen, selectedId, fetchCollectionDetail]);

  const isExportJobRunning =
    Boolean(jobStatus?.running) && jobStatus?.task_type === 'collection_export';

  // When a background collection_export job finishes, populate exportResult from jobStatus.result
  useEffect(() => {
    if (
      jobStatus &&
      !jobStatus.running &&
      jobStatus.task_type === 'collection_export' &&
      jobStatus.result
    ) {
      setExporting(false);
      setExportResult({
        ...jobStatus.result,
        cancelled: jobStatus.cancelled,
      });
    }
  }, [jobStatus]);

  if (!isOpen) return null;

  const handleCreateCollection = async (e) => {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed || creating) return;
    setCreating(true);
    try {
      const res = await fetch('/api/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: trimmed, description: newDesc.trim() }),
      });
      if (res.ok) {
        const created = await res.json();
        setNewName('');
        setNewDesc('');
        refreshCollections && (await refreshCollections());
        const createdId = created?.id || created?.collection?.id;
        if (createdId) {
          setSelectedId(createdId);
        }
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteCollection = async (colId, colName) => {
    if (!window.confirm(`Delete collection "${colName}"? (Photos in your catalog will NOT be deleted.)`)) {
      return;
    }
    const res = await fetch(`/api/collections/${colId}`, { method: 'DELETE' });
    if (res.ok) {
      refreshCollections && (await refreshCollections());
      const remaining = safeCollections.filter((c) => c.id !== colId);
      setSelectedId(remaining.length > 0 ? remaining[0].id : null);
    }
  };

  const handleRemoveItem = async (fileHash) => {
    if (!selectedId || !fileHash) return;
    const res = await fetch(
      `/api/collections/${selectedId}/items/${encodeURIComponent(fileHash)}`,
      { method: 'DELETE' }
    );
    if (res.ok) {
      await fetchCollectionDetail(selectedId);
      refreshCollections && refreshCollections();
    }
  };

  const commitOrder = async (newItems) => {
    if (!selectedId) return;
    setDetail((prev) => (prev ? { ...prev, photos: newItems } : prev));
    const orderedHashes = newItems.map((p) => p.file_hash || p.file_path || p.id);
    await fetch(`/api/collections/${selectedId}/reorder`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ photo_ids: orderedHashes, file_hashes: orderedHashes }),
    });
    refreshCollections && refreshCollections();
  };

  const handleMoveItem = (idx, direction) => {
    const items = [...(Array.isArray(detail?.photos) ? detail.photos : Array.isArray(detail?.items) ? detail.items : [])];
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= items.length) return;
    const [moved] = items.splice(idx, 1);
    items.splice(targetIdx, 0, moved);
    commitOrder(items);
  };

  const handleDrop = (idx) => {
    if (dragIndex === null || dragIndex === idx) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    const items = [...(Array.isArray(detail?.photos) ? detail.photos : Array.isArray(detail?.items) ? detail.items : [])];
    const [moved] = items.splice(dragIndex, 1);
    items.splice(idx, 0, moved);
    setDragIndex(null);
    setDragOverIndex(null);
    commitOrder(items);
  };

  const handleExportDesktop = async () => {
    if (!selectedId || exporting || isExportJobRunning) return;
    setExporting(true);
    setExportResult(null);
    try {
      const res = await fetch(
        `/api/collections/${selectedId}/export?async_job=true`,
        {
          method: 'POST',
        }
      );
      const data = await res.json();
      if (res.ok) {
        if (data.status === 'started') {
          onJobStarted && onJobStarted();
        } else {
          setExportResult(data);
          setExporting(false);
        }
      } else {
        setExportResult({ error: data.detail || 'Export failed' });
        setExporting(false);
      }
    } catch (err) {
      setExportResult({ error: err.message });
      setExporting(false);
    }
  };

  const handleOpenFolderInFinder = async () => {
    if (!selectedId) return;
    await fetch(`/api/collections/${selectedId}/reveal-export`, {
      method: 'POST',
    });
  };

  const items = Array.isArray(detail?.photos)
    ? detail.photos
    : Array.isArray(detail?.items)
    ? detail.items
    : [];
  const step = bookSpreadMode === 'spread' ? 2 : 1;
  const maxPageStart = Math.max(0, items.length - step);
  const currentRatioObj = BOOK_RATIOS.find((r) => r.id === bookAspectRatioId) || BOOK_RATIOS[0];

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 120,
        background: 'rgba(5, 7, 11, 0.92)',
        backdropFilter: 'blur(12px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '96vw',
          maxWidth: '1640px',
          height: '92vh',
          background: '#0f1219',
          border: '1px solid #262c3a',
          borderRadius: '16px',
          display: 'flex',
          overflow: 'hidden',
          boxShadow: '0 30px 90px rgba(0, 0, 0, 0.85)',
        }}
      >
        {/* Left Sidebar: High-Visibility Create Form at Very Top + Saved Collections List */}
        <div
          style={{
            width: '340px',
            borderRight: '1px solid #1e2430',
            background: '#0b0d13',
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              padding: '16px 18px',
              borderBottom: '1px solid #1e2430',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#f8fafc' }}>
                📚 Books & Collections
              </h2>
              <p style={{ margin: '3px 0 0', fontSize: '13px', color: '#94a3b8' }}>
                Curate monographs, portfolios & print sets
              </p>
            </div>
          </div>

          {/* TOP-LEFT HIGH-VISIBILITY CREATE NEW BOOK / COLLECTION FORM */}
          <form
            onSubmit={handleCreateCollection}
            style={{
              padding: '16px 18px',
              borderBottom: '1.5px solid #242b3b',
              background: 'linear-gradient(180deg, #141926 0%, #0f131d 100%)',
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
            }}
          >
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 700,
                  color: '#e2e8f0',
                  marginBottom: '5px',
                }}
              >
                Book or Collection Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Desert Panoramas Book"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: '#090b10',
                  border: '1.5px solid #475569',
                  color: '#ffffff',
                  fontSize: '15px',
                  fontWeight: 500,
                  outline: 'none',
                }}
              />
            </div>

            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#e2e8f0',
                  marginBottom: '5px',
                }}
              >
                Notes / Subtitle (Optional)
              </label>
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="e.g., Print selections for 2026 monograph"
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: '#090b10',
                  border: '1px solid #334155',
                  color: '#f1f5f9',
                  fontSize: '14px',
                  outline: 'none',
                }}
              />
            </div>

            <button
              type="submit"
              disabled={!newName.trim() || creating}
              style={{
                width: '100%',
                marginTop: '2px',
                padding: '11px 14px',
                borderRadius: '9px',
                border: '1px solid #f59e0b',
                background: newName.trim()
                  ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                  : '#1e293b',
                color: newName.trim() ? '#090b10' : '#64748b',
                fontSize: '15px',
                fontWeight: 800,
                cursor: newName.trim() ? 'pointer' : 'not-allowed',
                boxShadow: newName.trim() ? '0 4px 14px rgba(245, 158, 11, 0.3)' : 'none',
              }}
            >
              {creating ? 'Creating...' : '+ Create New Book / Collection'}
            </button>
          </form>

          {/* Saved Books & Collections List */}
          <div
            style={{
              padding: '10px 18px 6px',
              fontSize: '12px',
              fontWeight: 700,
              color: '#94a3b8',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Your Saved Books & Collections ({safeCollections.length})
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '6px 12px 14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {safeCollections.length === 0 ? (
              <div style={{ padding: '20px 12px', color: '#94a3b8', fontSize: '14px', textAlign: 'center', lineHeight: 1.5 }}>
                No books or collections yet. Use the form above to create your first book!
              </div>
            ) : (
              safeCollections.map((col, colIdx) => {
                if (!col) return null;
                const active = Number(selectedId) === Number(col.id);
                return (
                  <div
                    key={col.id ?? colIdx}
                    onClick={() => setSelectedId(col.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 12px',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      border: active ? '1.5px solid #f59e0b' : '1px solid #1c2230',
                      background: active ? 'rgba(245, 158, 11, 0.14)' : '#121620',
                    }}
                  >
                    <div
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '7px',
                        background: '#090b10',
                        border: '1px solid #262c3a',
                        overflow: 'hidden',
                        flexShrink: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {col.cover_thumb_url ? (
                        <img
                          src={col.cover_thumb_url}
                          alt={col.name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      ) : (
                        <span style={{ fontSize: '20px' }}>📖</span>
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: '15px',
                          fontWeight: 700,
                          color: active ? '#fbbf24' : '#f1f5f9',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {col.name}
                      </div>
                      <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '2px' }}>
                        {col.photo_count ?? col.item_count ?? 0}{' '}
                        {(col.photo_count ?? col.item_count ?? 0) === 1 ? 'plate' : 'plates'}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteCollection(col.id, col.name);
                      }}
                      title="Delete collection"
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#64748b',
                        cursor: 'pointer',
                        fontSize: '14px',
                        padding: '4px 6px',
                      }}
                    >
                      🗑
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Main Area: Header + Sequence Grid or Panoramic Book Preview */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          {/* Top Bar */}
          <div
            style={{
              padding: '16px 24px',
              borderBottom: '1px solid #1e2430',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap',
              background: '#11151f',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h3 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: '#f8fafc' }}>
                  {detail?.name || 'Select or Create a Book'}
                </h3>
                {detail && (
                  <span
                    style={{
                      padding: '3px 10px',
                      borderRadius: '999px',
                      fontSize: '13px',
                      fontWeight: 700,
                      background: 'rgba(245, 158, 11, 0.16)',
                      color: '#fbbf24',
                      border: '1px solid rgba(245, 158, 11, 0.35)',
                    }}
                  >
                    {items.length} {items.length === 1 ? 'Plate' : 'Plates'}
                  </span>
                )}
              </div>
              {detail?.description && (
                <p style={{ margin: '4px 0 0', fontSize: '14px', color: '#94a3b8' }}>
                  {detail.description}
                </p>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              {/* Mode Switcher: Sequence Grid vs Panoramic Book Preview */}
              <div
                style={{
                  display: 'flex',
                  background: '#090b10',
                  padding: '4px',
                  borderRadius: '10px',
                  border: '1px solid #262c3a',
                }}
              >
                <button
                  onClick={() => setMode('sequence')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '7px',
                    fontSize: '14px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    border: 'none',
                    background: mode === 'sequence' ? '#3b82f6' : 'transparent',
                    color: mode === 'sequence' ? '#ffffff' : '#cbd5e1',
                  }}
                >
                  ⊞ Sequence & Order
                </button>
                <button
                  onClick={() => setMode('book')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '7px',
                    fontSize: '14px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    border: 'none',
                    background: mode === 'book' ? '#f59e0b' : 'transparent',
                    color: mode === 'book' ? '#090b10' : '#cbd5e1',
                  }}
                >
                  📖 Book Preview
                </button>
              </div>

              {/* High-Res Desktop JPEG Export Button */}
              {detail && items.length > 0 && (
                <button
                  onClick={handleExportDesktop}
                  disabled={exporting || isExportJobRunning}
                  style={{
                    padding: '9px 16px',
                    borderRadius: '9px',
                    fontSize: '14px',
                    fontWeight: 700,
                    cursor: exporting || isExportJobRunning ? 'wait' : 'pointer',
                    border: '1px solid #10b981',
                    background: 'rgba(16, 185, 129, 0.16)',
                    color: '#34d399',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '7px',
                  }}
                >
                  <span>📤</span>
                  {isExportJobRunning
                    ? `Exporting (${jobStatus?.processed || 0}/${jobStatus?.total || items.length})...`
                    : exporting
                    ? 'Starting Export...'
                    : 'Export High-Res JPEGs to Desktop'}
                </button>
              )}

              <button
                onClick={onClose}
                style={{
                  padding: '8px 14px',
                  borderRadius: '9px',
                  background: '#1e293b',
                  border: '1px solid #334155',
                  color: '#f1f5f9',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontWeight: 700,
                }}
              >
                ✕ Close
              </button>
            </div>
          </div>

          {/* Live Non-Blocking Export Progress Bar with Elapsed, ETA, Pause/Resume & Cancel */}
          {isExportJobRunning && (
            <div
              style={{
                padding: '12px 24px',
                background: 'rgba(15, 23, 42, 0.95)',
                borderBottom: '1px solid #3b82f6',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  flexWrap: 'wrap',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#e2e8f0' }}>
                  <span style={{ fontWeight: 700, color: jobStatus.paused ? '#fbbf24' : '#60a5fa' }}>
                    {jobStatus.paused ? '⏸ Paused:' : '📤 Exporting High-Res JPEGs:'}{' '}
                    {jobStatus.processed || 0} / {jobStatus.total || items.length} plates
                  </span>
                  {jobStatus.current_file && (
                    <code style={{ fontSize: '12px', color: '#94a3b8', background: '#090b10', padding: '2px 6px', borderRadius: '4px' }}>
                      {jobStatus.current_file}
                    </code>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '12px', color: '#cbd5e1', fontFamily: 'monospace' }}>
                    Elapsed: <strong>{Math.round(jobStatus.elapsed_seconds || 0)}s</strong> · Est. Remaining:{' '}
                    <strong style={{ color: '#fbbf24' }}>
                      {jobStatus.eta_seconds !== null && jobStatus.eta_seconds !== undefined
                        ? `~${Math.round(jobStatus.eta_seconds)}s`
                        : 'Calculating...'}
                    </strong>
                  </span>

                  {jobStatus.paused ? (
                    <button
                      type="button"
                      onClick={onResumeJob}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        border: '1px solid #10b981',
                        background: 'rgba(16, 185, 129, 0.2)',
                        color: '#6ee7b7',
                      }}
                    >
                      ▶ Resume
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={onPauseJob}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        border: '1px solid #f59e0b',
                        background: 'rgba(245, 158, 11, 0.2)',
                        color: '#fde68a',
                      }}
                    >
                      ⏸ Pause
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={onCancelJob}
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      border: '1px solid #ef4444',
                      background: 'rgba(239, 68, 68, 0.2)',
                      color: '#fca5a5',
                    }}
                  >
                    ⏹ Stop Early (Keep {jobStatus.processed || 0} Exported)
                  </button>
                </div>
              </div>

              <div style={{ width: '100%', height: '6px', background: '#1e293b', borderRadius: '999px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${
                      jobStatus.total > 0
                        ? Math.min(100, Math.round((jobStatus.processed / jobStatus.total) * 100))
                        : 5
                    }%`,
                    height: '100%',
                    background: jobStatus.paused ? '#f59e0b' : '#10b981',
                    transition: 'width 0.25s ease',
                  }}
                />
              </div>
            </div>
          )}

          {/* Export Status Toast Banner */}
          {exportResult && (
            <div
              style={{
                padding: '12px 24px',
                background: exportResult.error ? 'rgba(239, 68, 68, 0.16)' : 'rgba(16, 185, 129, 0.15)',
                borderBottom: exportResult.error ? '1px solid #ef4444' : '1px solid #10b981',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '12px',
              }}
            >
              {exportResult.error ? (
                <span style={{ fontSize: '14px', color: '#fca5a5' }}>⚠️ {exportResult.error}</span>
              ) : (
                <>
                  <span style={{ fontSize: '14px', color: '#6ee7b7' }}>
                    ✅ Exported <strong>{exportResult.exported_count}</strong> print-ready JPEGs to{' '}
                    <code style={{ color: '#f8fafc', background: '#090b10', padding: '2px 6px', borderRadius: '4px' }}>
                      {exportResult.export_dir}
                    </code>
                  </span>
                  <button
                    onClick={() => handleOpenFolderInFinder(exportResult.export_dir)}
                    style={{
                      padding: '6px 14px',
                      borderRadius: '7px',
                      fontSize: '13px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      border: '1px solid #10b981',
                      background: '#10b981',
                      color: '#090b10',
                    }}
                  >
                    📂 Open Folder in Finder
                  </button>
                </>
              )}
            </div>
          )}

          {/* Body Content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            {loading ? (
              <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8', fontSize: '15px' }}>
                Loading collection plates...
              </div>
            ) : !detail ? (
              <div style={{ padding: '60px', textAlign: 'center', color: '#64748b', fontSize: '15px' }}>
                Select a book on the left or create a new one using the top-left form.
              </div>
            ) : items.length === 0 ? (
              <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8', fontSize: '15px' }}>
                This book has no photos yet. Click the <strong>📚+</strong> badge on any photo card or inside the
                Lightbox to add plates here.
              </div>
            ) : mode === 'sequence' ? (
              /* SEQUENCE & DRAG-AND-DROP REORDER GRID */
              <div>
                <div
                  style={{
                    marginBottom: '16px',
                    fontSize: '14px',
                    color: '#cbd5e1',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span>
                    Drag & drop plates or use <strong>◀ / ▶</strong> to sequence your book order. Exported JPEGs are
                    numbered <code>01_</code>, <code>02_</code>, etc. in this exact sequence.
                  </span>
                </div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                    gap: '18px',
                  }}
                >
                  {items.map((photo, idx) => {
                    if (!photo) return null;
                    const isOver = dragOverIndex === idx;
                    const itemKey = photo.id || photo.file_hash || photo.file_path || `seq-${idx}`;
                    return (
                      <div
                        key={itemKey}
                        draggable
                        onDragStart={() => setDragIndex(idx)}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragOverIndex(idx);
                        }}
                        onDrop={() => handleDrop(idx)}
                        style={{
                          background: '#141822',
                          border: isOver ? '2px dashed #f59e0b' : '1px solid #262c3a',
                          borderRadius: '12px',
                          overflow: 'hidden',
                          display: 'flex',
                          flexDirection: 'column',
                          cursor: 'grab',
                          transition: 'transform 0.12s',
                        }}
                      >
                        <div
                          onClick={() => openInLightbox && openInLightbox(photo, items)}
                          style={{
                            position: 'relative',
                            aspectRatio: '16 / 10',
                            background: '#090b10',
                            cursor: 'pointer',
                          }}
                        >
                          <img
                            src={photo.thumb_url || photo.preview_url}
                            alt={photo.filename}
                            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                          />
                          <span
                            style={{
                              position: 'absolute',
                              top: '8px',
                              left: '8px',
                              padding: '3px 9px',
                              borderRadius: '6px',
                              background: 'rgba(9, 11, 16, 0.88)',
                              border: '1px solid rgba(245, 158, 11, 0.45)',
                              color: '#fbbf24',
                              fontSize: '12px',
                              fontWeight: 800,
                            }}
                          >
                            Plate #{String(idx + 1).padStart(2, '0')}
                          </span>
                        </div>
                        <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <div
                            style={{
                              fontSize: '14px',
                              fontWeight: 700,
                              color: '#f1f5f9',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                          >
                            {photo.title || photo.filename}
                          </div>
                          <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                            {photo.location_label || photo.shoot_date || photo.filename}
                          </div>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginTop: '6px',
                              paddingTop: '8px',
                              borderTop: '1px solid #1e2430',
                            }}
                          >
                            <div style={{ display: 'flex', gap: '6px' }}>
                              <button
                                onClick={() => handleMoveItem(idx, -1)}
                                disabled={idx === 0}
                                title="Move Earlier"
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #2d3548',
                                  background: '#0d1017',
                                  color: idx === 0 ? '#475569' : '#cbd5e1',
                                  cursor: idx === 0 ? 'default' : 'pointer',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                }}
                              >
                                ◀
                              </button>
                              <button
                                onClick={() => handleMoveItem(idx, 1)}
                                disabled={idx === items.length - 1}
                                title="Move Later"
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #2d3548',
                                  background: '#0d1017',
                                  color: idx === items.length - 1 ? '#475569' : '#cbd5e1',
                                  cursor: idx === items.length - 1 ? 'default' : 'pointer',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                }}
                              >
                                ▶
                              </button>
                            </div>
                            <button
                              onClick={() => handleRemoveItem(photo.file_hash || photo.file_path || photo.id)}
                              title="Remove from collection"
                              style={{
                                padding: '4px 10px',
                                borderRadius: '6px',
                                border: '1px solid rgba(239, 68, 68, 0.35)',
                                background: 'rgba(239, 68, 68, 0.12)',
                                color: '#fca5a5',
                                cursor: 'pointer',
                                fontSize: '12px',
                                fontWeight: 600,
                              }}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              /* FINE-ART HORIZONTAL PANORAMIC BOOK PREVIEW MODE */
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '20px' }}>
                {/* Book Controls Header: Page Layout + Horizontal Aspect Ratio Selector + Prev/Next */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                    maxWidth: '1320px',
                    flexWrap: 'wrap',
                    gap: '12px',
                    background: '#141822',
                    padding: '12px 18px',
                    borderRadius: '12px',
                    border: '1px solid #262c3a',
                  }}
                >
                  {/* Single Plate vs 2-Page Spread */}
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button
                      onClick={() => {
                        setBookSpreadMode('single');
                        setBookPageIndex(0);
                      }}
                      style={{
                        padding: '8px 14px',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        border: bookSpreadMode === 'single' ? '1.5px solid #f59e0b' : '1px solid #2d3548',
                        background: bookSpreadMode === 'single' ? 'rgba(245, 158, 11, 0.16)' : '#0d1017',
                        color: bookSpreadMode === 'single' ? '#fbbf24' : '#cbd5e1',
                      }}
                    >
                      📄 Single Plate
                    </button>
                    <button
                      onClick={() => {
                        setBookSpreadMode('spread');
                        setBookPageIndex(0);
                      }}
                      style={{
                        padding: '8px 14px',
                        borderRadius: '8px',
                        fontSize: '14px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        border: bookSpreadMode === 'spread' ? '1.5px solid #f59e0b' : '1px solid #2d3548',
                        background: bookSpreadMode === 'spread' ? 'rgba(245, 158, 11, 0.16)' : '#0d1017',
                        color: bookSpreadMode === 'spread' ? '#fbbf24' : '#cbd5e1',
                      }}
                    >
                      📖 2-Page Facing Spread
                    </button>
                  </div>

                  {/* Book Page Aspect Ratio Pill Selector */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      background: '#090b10',
                      padding: '4px',
                      borderRadius: '9px',
                      border: '1px solid #262c3a',
                      flexWrap: 'wrap',
                    }}
                  >
                    {BOOK_RATIOS.map((r) => {
                      const active = bookAspectRatioId === r.id;
                      return (
                        <button
                          key={r.id}
                          onClick={() => setBookAspectRatioId(r.id)}
                          title={r.desc}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            fontSize: '13px',
                            fontWeight: active ? 700 : 500,
                            cursor: 'pointer',
                            border: active ? '1px solid #f59e0b' : '1px solid transparent',
                            background: active ? 'rgba(245, 158, 11, 0.18)' : 'transparent',
                            color: active ? '#fbbf24' : '#cbd5e1',
                          }}
                        >
                          {r.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Large Prev / Next Page Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button
                      onClick={() => setBookPageIndex((p) => Math.max(0, p - step))}
                      disabled={bookPageIndex <= 0}
                      style={{
                        padding: '9px 18px',
                        borderRadius: '8px',
                        border: '1px solid #334155',
                        background: bookPageIndex <= 0 ? '#0d1017' : '#1e293b',
                        color: bookPageIndex <= 0 ? '#475569' : '#f8fafc',
                        cursor: bookPageIndex <= 0 ? 'default' : 'pointer',
                        fontSize: '14px',
                        fontWeight: 700,
                      }}
                    >
                      ← Prev Page
                    </button>
                    <span style={{ fontSize: '14px', color: '#e2e8f0', fontWeight: 700, minWidth: '110px', textAlign: 'center' }}>
                      {bookSpreadMode === 'spread'
                        ? `Plates ${bookPageIndex + 1}–${Math.min(items.length, bookPageIndex + 2)} of ${items.length}`
                        : `Plate ${bookPageIndex + 1} of ${items.length}`}
                    </span>
                    <button
                      onClick={() => setBookPageIndex((p) => Math.min(maxPageStart, p + step))}
                      disabled={bookPageIndex >= maxPageStart}
                      style={{
                        padding: '9px 18px',
                        borderRadius: '8px',
                        border: '1px solid #334155',
                        background: bookPageIndex >= maxPageStart ? '#0d1017' : '#1e293b',
                        color: bookPageIndex >= maxPageStart ? '#475569' : '#f8fafc',
                        cursor: bookPageIndex >= maxPageStart ? 'default' : 'pointer',
                        fontSize: '14px',
                        fontWeight: 700,
                      }}
                    >
                      Next Page →
                    </button>
                  </div>
                </div>

                {/* Horizontal Panoramic Monograph Spread Canvas */}
                <div
                  style={{
                    width: '100%',
                    maxWidth: '1320px',
                    aspectRatio:
                      bookSpreadMode === 'spread'
                        ? currentRatioObj.spreadAspectRatio
                        : currentRatioObj.aspectRatio,
                    maxHeight: '66vh',
                    background: '#f7f5f0',
                    borderRadius: '8px',
                    boxShadow: '0 28px 80px rgba(0, 0, 0, 0.9), inset 0 0 60px rgba(0,0,0,0.05)',
                    display: 'grid',
                    gridTemplateColumns: bookSpreadMode === 'spread' ? '1fr 1fr' : '1fr',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                >
                  {bookSpreadMode === 'spread' && (
                    /* Center Book Gutter Shadow */
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: '50%',
                        width: '32px',
                        transform: 'translateX(-50%)',
                        background:
                          'linear-gradient(90deg, rgba(0,0,0,0.0) 0%, rgba(0,0,0,0.16) 50%, rgba(0,0,0,0.0) 100%)',
                        pointerEvents: 'none',
                        zIndex: 5,
                      }}
                    />
                  )}

                  {items.slice(bookPageIndex, bookPageIndex + step).map((plate, idx) => {
                    if (!plate) return null;
                    const plateNum = bookPageIndex + idx + 1;
                    const plateKey = plate.id || plate.file_hash || plate.file_path || `book-${plateNum}`;
                    return (
                      <div
                        key={plateKey}
                        onClick={() => openInLightbox && openInLightbox(plate, items)}
                        style={{
                          padding: bookAspectRatioId === '3:1' ? '22px 32px 18px' : '28px 42px 22px',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          cursor: 'pointer',
                          minHeight: 0,
                          minWidth: 0,
                        }}
                      >
                        <div
                          style={{
                            flex: 1,
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minHeight: 0,
                          }}
                        >
                          <img
                            src={plate.preview_url || plate.thumb_url}
                            alt={plate.title || plate.filename}
                            style={{
                              maxWidth: '100%',
                              maxHeight: '100%',
                              objectFit: 'contain',
                              boxShadow: '0 10px 30px rgba(0, 0, 0, 0.22)',
                              background: '#fff',
                            }}
                          />
                        </div>
                        <div
                          style={{
                            marginTop: '14px',
                            width: '100%',
                            display: 'flex',
                            alignItems: 'baseline',
                            justifyContent: 'space-between',
                            borderTop: '1px solid #d6d3cd',
                            paddingTop: '8px',
                            color: '#292524',
                            fontFamily: 'Georgia, serif',
                            gap: '16px',
                          }}
                        >
                          <div style={{ fontSize: '14px', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            Plate {String(plateNum).padStart(2, '0')} — {plate.title || plate.filename}
                          </div>
                          <div style={{ fontSize: '12px', color: '#57534e', fontStyle: 'italic', flexShrink: 0 }}>
                            {[plate.location_label, plate.shoot_date].filter(Boolean).join(' • ')}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
