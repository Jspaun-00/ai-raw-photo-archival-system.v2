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
}) {
  const [showBookMenu, setShowBookMenu] = useState(false);
  const [newBookName, setNewBookName] = useState('');
  const [busyBook, setBusyBook] = useState(false);

  // People & Pets popover state
  const [peoplePetsOpen, setPeoplePetsOpen] = useState(false);
  const [entityClusters, setEntityClusters] = useState([]);
  const [loadingEntities, setLoadingEntities] = useState(false);
  const [editingEntityId, setEditingEntityId] = useState(null);
  const [editingNameVal, setEditingNameVal] = useState('');
  const [savingEntityId, setSavingEntityId] = useState(null);

  // Idle Rescan menu state
  const [rescanMenuOpen, setRescanMenuOpen] = useState(false);

  const peoplePetsRef = useRef(null);
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
      if (peoplePetsRef.current && !peoplePetsRef.current.contains(e.target)) {
        setPeoplePetsOpen(false);
        setEditingEntityId(null);
      }
      if (rescanRef.current && !rescanRef.current.contains(e.target)) {
        setRescanMenuOpen(false);
      }
      if (bookRef.current && !bookRef.current.contains(e.target)) {
        setShowBookMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch People & Pets identity clusters
  const fetchEntityClusters = async (catName = activeCatalog) => {
    setLoadingEntities(true);
    try {
      const r = await fetch(
        `/api/entities?catalog=${encodeURIComponent(catName || 'All Catalogs')}`
      );
      if (r.ok) {
        const data = await r.json();
        setEntityClusters(Array.isArray(data.entities) ? data.entities : []);
      }
    } catch (_) {
      // ignore
    } finally {
      setLoadingEntities(false);
    }
  };

  useEffect(() => {
    fetchEntityClusters(activeCatalog);
  }, [activeCatalog]);

  const handleRenameEntity = async (entityId, newName) => {
    const clean = (newName || '').trim();
    if (!clean) return;
    setSavingEntityId(entityId);
    try {
      const r = await fetch(
        `/api/entities/${encodeURIComponent(entityId)}/rename`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ entity_name: clean }),
        }
      );
      if (r.ok) {
        await fetchEntityClusters(activeCatalog);
        setEditingEntityId(null);
        setEditingNameVal('');
      }
    } catch (_) {
      // ignore
    } finally {
      setSavingEntityId(null);
    }
  };

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
        zIndex: 9300,
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
        maxWidth: '96vw',
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
              fontSize: '13px',
              color: '#cbd5e1',
              fontVariantNumeric: 'tabular-nums',
              padding: '6px 10px',
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
                padding: '6px 11px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isSelectingAll ? 'wait' : 'pointer',
                border: '1px solid rgba(255, 255, 255, 0.18)',
                background: 'rgba(255, 255, 255, 0.06)',
                color: '#e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
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
              padding: '6px 11px',
              borderRadius: '8px',
              fontSize: '13px',
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
                  padding: '1px 6px',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                {undoStatus.count}
              </span>
            )}
          </button>

          {/* 👥 People & Pets Popover (UPWARD OPENING) */}
          <div ref={peoplePetsRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => {
                const nextOpen = !peoplePetsOpen;
                setPeoplePetsOpen(nextOpen);
                if (nextOpen) fetchEntityClusters(activeCatalog);
              }}
              title="People & Pets — Recurring Cats, Dogs & People across months with 1-click breed & custom name filtering (e.g. Masha, Scout)"
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                border: peoplePetsOpen ? '1.5px solid #a855f7' : '1px solid #8b5cf6',
                background: peoplePetsOpen
                  ? 'rgba(168, 85, 247, 0.26)'
                  : 'rgba(139, 92, 246, 0.16)',
                color: '#ede9fe',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>👥 People &amp; Pets</span>
              {entityClusters.length > 0 && (
                <span
                  style={{
                    background: '#8b5cf6',
                    color: '#ffffff',
                    borderRadius: '999px',
                    padding: '1px 6px',
                    fontSize: '11px',
                    fontWeight: 800,
                  }}
                >
                  {entityClusters.length}
                </span>
              )}
            </button>

            {peoplePetsOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 12px)',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  width: '420px',
                  maxHeight: '480px',
                  overflowY: 'auto',
                  background: '#11141d',
                  border: '1px solid #2e364f',
                  borderRadius: '14px',
                  boxShadow: '0 20px 50px rgba(0, 0, 0, 0.85)',
                  padding: '14px',
                  zIndex: 9500,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid #1e2536',
                    paddingBottom: '8px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 800, color: '#f8fafc' }}>
                      👥 People &amp; Pets Clusters
                    </div>
                    <div style={{ fontSize: '11.5px', color: '#94a3b8' }}>
                      Click any cluster to filter photos, or name a pet/person (e.g. &quot;Masha&quot;, &quot;Scout&quot;)
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setPeoplePetsOpen(false)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      fontSize: '16px',
                      fontWeight: 700,
                      padding: '2px 6px',
                    }}
                  >
                    ✕
                  </button>
                </div>

                {loadingEntities ? (
                  <div style={{ padding: '18px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                    Loading identity clusters...
                  </div>
                ) : entityClusters.length === 0 ? (
                  <div style={{ padding: '18px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                    No recurring People or Pet clusters detected in this catalog view.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {entityClusters.map((ent) => {
                      const isEditing = editingEntityId === ent.entity_id;
                      const displayName = ent.entity_name || ent.auto_breed || ent.entity_type;
                      const filterQueryTerm = ent.entity_name || ent.auto_breed || ent.entity_type;
                      const isActiveFilter =
                        currentQuery &&
                        filterQueryTerm &&
                        currentQuery.trim().toLowerCase() === filterQueryTerm.trim().toLowerCase();

                      const thumbSrc =
                        ent.thumb_url ||
                        (ent.cover_photo_id ? `/api/thumbnail/${ent.cover_photo_id}` : null);

                      return (
                        <div
                          key={ent.entity_id}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '10px',
                            padding: '8px 10px',
                            borderRadius: '10px',
                            background: isActiveFilter ? 'rgba(139, 92, 246, 0.22)' : '#171b26',
                            border: isActiveFilter ? '1px solid #a855f7' : '1px solid #252c3d',
                          }}
                        >
                          <div
                            onClick={() => {
                              handleQueryChange(filterQueryTerm);
                              setPeoplePetsOpen(false);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '10px',
                              flex: 1,
                              cursor: 'pointer',
                              minWidth: 0,
                            }}
                            title={`Filter by ${displayName} (${ent.photo_count} photos)`}
                          >
                            {thumbSrc ? (
                              <img
                                src={thumbSrc}
                                alt={displayName}
                                style={{
                                  width: '46px',
                                  height: '46px',
                                  borderRadius: '50%',
                                  objectFit: 'cover',
                                  border: '2px solid #8b5cf6',
                                  flexShrink: 0,
                                }}
                                onError={(e) => {
                                  e.target.style.display = 'none';
                                  if (e.target.nextSibling) {
                                    e.target.nextSibling.style.display = 'flex';
                                  }
                                }}
                              />
                            ) : null}
                            <div
                              style={{
                                width: '46px',
                                height: '46px',
                                borderRadius: '50%',
                                background: '#262d40',
                                display: thumbSrc ? 'none' : 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '20px',
                                flexShrink: 0,
                              }}
                            >
                              {ent.entity_type === 'Cat' ? '🐱' : ent.entity_type === 'Dog' ? '🐶' : '🧑'}
                            </div>

                            <div style={{ minWidth: 0, flex: 1 }}>
                              <div
                                style={{
                                  fontSize: '13.5px',
                                  fontWeight: 700,
                                  color: '#f8fafc',
                                  whiteSpace: 'nowrap',
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                }}
                              >
                                {ent.entity_name ? (
                                  <>
                                    <span style={{ color: '#c084fc' }}>{ent.entity_name}</span>{' '}
                                    <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 500 }}>
                                      ({ent.auto_breed || ent.entity_type})
                                    </span>
                                  </>
                                ) : (
                                  <span>{ent.auto_breed || ent.entity_type}</span>
                                )}
                              </div>
                              <div style={{ fontSize: '11.5px', color: '#94a3b8' }}>
                                {ent.entity_type} • {ent.photo_count} photo{ent.photo_count === 1 ? '' : 's'}
                              </div>
                            </div>
                          </div>

                          {isEditing ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                              <input
                                type="text"
                                value={editingNameVal}
                                onChange={(e) => setEditingNameVal(e.target.value)}
                                onKeyDown={(e) => {
                                  e.stopPropagation();
                                  if (e.key === 'Enter') {
                                    handleRenameEntity(ent.entity_id, editingNameVal);
                                  } else if (e.key === 'Escape') {
                                    setEditingEntityId(null);
                                  }
                                }}
                                placeholder="e.g. Masha, Scout"
                                autoFocus
                                style={{
                                  width: '115px',
                                  padding: '5px 8px',
                                  borderRadius: '6px',
                                  background: '#0d1017',
                                  border: '1px solid #8b5cf6',
                                  color: '#f8fafc',
                                  fontSize: '12px',
                                  outline: 'none',
                                }}
                              />
                              <button
                                type="button"
                                disabled={savingEntityId === ent.entity_id}
                                onClick={() => handleRenameEntity(ent.entity_id, editingNameVal)}
                                style={{
                                  padding: '5px 8px',
                                  borderRadius: '6px',
                                  background: '#8b5cf6',
                                  border: 'none',
                                  color: '#ffffff',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Save
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingEntityId(ent.entity_id);
                                setEditingNameVal(ent.entity_name || '');
                              }}
                              style={{
                                padding: '4px 8px',
                                borderRadius: '6px',
                                background: '#23293a',
                                border: '1px solid #384159',
                                color: '#cbd5e1',
                                fontSize: '11.5px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                flexShrink: 0,
                              }}
                            >
                              ✎ {ent.entity_name ? 'Rename' : 'Name'}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Scout Archive Button */}
          {onOpenVoiceScout && (
            <button
              type="button"
              onClick={onOpenVoiceScout}
              title="AI Archive Scout — Describe a theme, subject, or story to hunt across the entire archive and build a curated collection"
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                border: '1px solid #38bdf8',
                background:
                  'linear-gradient(135deg, rgba(16, 185, 129, 0.18) 0%, rgba(56, 189, 248, 0.22) 100%)',
                color: '#e0f2fe',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <span>🔎 Scout Archive</span>
            </button>
          )}

          {/* Collections Button */}
          {onOpenCollectionsModal && (
            <button
              type="button"
              onClick={onOpenCollectionsModal}
              title="Open Curated Collections, Panoramic Book Preview & Desktop JPEG Export"
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                border: '1px solid #f59e0b',
                background: 'rgba(245, 158, 11, 0.16)',
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
                    padding: '1px 6px',
                    fontSize: '11px',
                    fontWeight: 800,
                  }}
                >
                  {displayCollectionsCount}
                </span>
              )}
            </button>
          )}

          {/* 🔄 Rescan Dropdown (UPWARD OPENING) */}
          <div ref={rescanRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setRescanMenuOpen((prev) => !prev)}
              disabled={isBatchBusy}
              title="Rescan catalog or current view with Fast 4-Pass Cascade or Deep VLM"
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: isBatchBusy ? 'wait' : 'pointer',
                border: rescanMenuOpen ? '1px solid #f59e0b' : '1px solid #2a3040',
                background: rescanMenuOpen ? 'rgba(245, 158, 11, 0.18)' : '#141720',
                color: rescanMenuOpen ? '#fbbf24' : '#e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
            >
              <span>🔄 Rescan</span>
              <span style={{ fontSize: '11px', opacity: 0.8 }}>▾</span>
            </button>

            {rescanMenuOpen && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  right: 0,
                  width: '340px',
                  background: '#11141d',
                  border: '1px solid #2e3646',
                  borderRadius: '12px',
                  boxShadow: '0 16px 40px rgba(0, 0, 0, 0.8)',
                  padding: '8px',
                  zIndex: 9500,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '6px',
                }}
              >
                <div
                  style={{
                    fontSize: '11.5px',
                    fontWeight: 700,
                    color: '#94a3b8',
                    padding: '4px 8px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                  }}
                >
                  Rescan Active View / Catalog
                </div>

                {/* Level 1: Fast Scan */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onReassessCatalog) onReassessCatalog('fast_vectors');
                    else if (onBatchReassess) onBatchReassess('fast_vectors');
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    background: 'rgba(245, 158, 11, 0.08)',
                    color: '#fef3c7',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                  }}
                >
                  <div style={{ fontSize: '13.5px', fontWeight: 700, color: '#fde68a' }}>
                    ⚡ Fast Scan (Level 1 — 4-Pass Cascade)
                  </div>
                  <div style={{ fontSize: '11.5px', color: '#cbd5e1', lineHeight: '1.4' }}>
                    Runs Pass 1 Macro Biome Lock + Pass 2 GPU 4-Crop Saliency Scan + Pass 3 Specialist Breed/Species Drill-Down + Pass 4 Pet/Person Clustering (~6ms/photo).
                  </div>
                </button>

                {/* Level 2: Deep VLM */}
                <button
                  type="button"
                  onClick={() => {
                    setRescanMenuOpen(false);
                    if (onReassessCatalog) onReassessCatalog('deep_vlm');
                    else if (onBatchReassess) onBatchReassess('deep_vlm');
                  }}
                  style={{
                    textAlign: 'left',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    background: 'rgba(56, 189, 248, 0.08)',
                    color: '#e0f2fe',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '3px',
                  }}
                >
                  <div style={{ fontSize: '13.5px', fontWeight: 700, color: '#7dd3fc' }}>
                    🧠 Deep VLM (Level 2 — Qwen2.5-VL + Cascade)
                  </div>
                  <div style={{ fontSize: '11.5px', color: '#cbd5e1', lineHeight: '1.4' }}>
                    Runs full generative VLM visual inspection + 4-Pass Cascade (~5–8s/photo).
                  </div>
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* ========================================================================= */}
      {/* ACTIVE DOCK: When 1+ photos are selected                                  */}
      {/* ✓ N Selected (Loaded / All / Clear) | Clear Tags | Fast Scan | Deep VLM | Voice Tag | Scout Similar | Add to Book | Undo */}
      {/* ========================================================================= */}
      {isSelectionActive && (
        <>
          {/* Selected Count Badge */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'rgba(99, 102, 241, 0.22)',
              border: '1px solid rgba(129, 140, 248, 0.5)',
              padding: '6px 11px',
              borderRadius: '9px',
              fontWeight: 700,
              fontSize: '13.5px',
              color: '#e0e7ff',
            }}
          >
            <span>✓ {selectedCount.toLocaleString()} Selected</span>
          </div>

          {/* Select All / Clear Options */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            {totalVisibleCount > selectedCount && onSelectAll && (
              <button
                type="button"
                onClick={onSelectAll}
                disabled={isSelectingAll}
                title="Select all currently loaded photos on the grid (Cmd+A)"
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.18)',
                  color: '#e2e8f0',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  padding: '6px 10px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                Loaded ({totalVisibleCount.toLocaleString()})
              </button>
            )}
            {onSelectAllInCatalog && totalCatalogCount > selectedCount && totalCatalogCount > totalVisibleCount && (
              <button
                type="button"
                onClick={onSelectAllInCatalog}
                disabled={isSelectingAll}
                title={`Select all ${totalCatalogCount.toLocaleString()} matching photos across active catalog`}
                style={{
                  background: 'rgba(99, 102, 241, 0.18)',
                  border: '1px solid rgba(129, 140, 248, 0.45)',
                  color: '#c7d2fe',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  padding: '6px 10px',
                  borderRadius: '8px',
                  cursor: isSelectingAll ? 'wait' : 'pointer',
                }}
              >
                {isSelectingAll ? '⏳...' : `All (${totalCatalogCount.toLocaleString()})`}
              </button>
            )}
            {onClearSelection && (
              <button
                type="button"
                onClick={onClearSelection}
                title="Clear current photo selection"
                style={{
                  background: 'rgba(255, 255, 255, 0.06)',
                  border: '1px solid rgba(255, 255, 255, 0.16)',
                  color: '#cbd5e1',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  padding: '6px 10px',
                  borderRadius: '8px',
                  cursor: 'pointer',
                }}
              >
                ✕ Clear
              </button>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* Batch Actions */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'nowrap' }}>
            {/* Clear Tags */}
            {onBatchClearTags && (
              <button
                type="button"
                disabled={isBatchBusy}
                onClick={onBatchClearTags}
                style={{
                  background: 'rgba(239, 68, 68, 0.16)',
                  border: '1px solid rgba(248, 113, 113, 0.5)',
                  color: '#fca5a5',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '7px 11px',
                  borderRadius: '9px',
                  cursor: isBatchBusy ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                }}
                title={`Wipe all AI tags cleanly across ${selectedCount.toLocaleString()} selected photo(s) (Cmd+Z to Undo)`}
              >
                <span>🧹 Clear Tags</span>
              </button>
            )}

            {/* Level 1: Fast Scan */}
            {onBatchReassess && (
              <button
                type="button"
                disabled={isBatchBusy}
                onClick={() => onBatchReassess('fast_vectors')}
                style={{
                  background: 'rgba(245, 158, 11, 0.18)',
                  border: '1px solid rgba(251, 191, 36, 0.55)',
                  color: '#fde68a',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '7px 12px',
                  borderRadius: '9px',
                  cursor: isBatchBusy ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                }}
                title="⚡ Fast Scan (Level 1 — 4-Pass Cascade): Runs Pass 1 Macro Biome Lock + Pass 2 GPU 4-Crop Saliency Scan + Pass 3 Specialist Breed/Species Drill-Down + Pass 4 Pet/Person Clustering (~6ms/photo)"
              >
                <span>⚡ Fast Scan (Level 1)</span>
              </button>
            )}

            {/* Level 2: Deep VLM */}
            {onBatchReassess && (
              <button
                type="button"
                disabled={isBatchBusy}
                onClick={() => onBatchReassess('deep_vlm')}
                style={{
                  background: 'rgba(56, 189, 248, 0.18)',
                  border: '1px solid rgba(56, 189, 248, 0.55)',
                  color: '#bae6fd',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '7px 12px',
                  borderRadius: '9px',
                  cursor: isBatchBusy ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                }}
                title="🧠 Deep VLM (Level 2 — Qwen2.5-VL + Cascade): Runs full generative VLM visual inspection + 4-Pass Cascade (~5–8s/photo)"
              >
                <span>🧠 Deep VLM (Level 2)</span>
              </button>
            )}

            {/* Voice Tag */}
            {onOpenVoiceTeach && (
              <button
                type="button"
                onClick={onOpenVoiceTeach}
                style={{
                  background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
                  border: '1px solid #a78bfa',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '7px 12px',
                  borderRadius: '9px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 14px rgba(124, 58, 237, 0.4)',
                }}
                title="Speak or type context to teach custom tags or locations for the selected photos"
              >
                <span>🎙️ AI Voice Tag</span>
              </button>
            )}
          </div>

          <div style={{ width: '1px', height: '22px', background: 'rgba(255,255,255,0.14)' }} />

          {/* Scout Similar Button */}
          {onOpenVoiceScout && (
            <button
              type="button"
              onClick={onOpenVoiceScout}
              style={{
                background: 'rgba(16, 185, 129, 0.2)',
                border: '1px solid rgba(52, 211, 153, 0.55)',
                color: '#6ee7b7',
                fontSize: '12.5px',
                fontWeight: 700,
                padding: '7px 11px',
                borderRadius: '9px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
              }}
              title="Use selected photos as visual seeds to hunt for matching photos across the archive & build a Collection/Book"
            >
              <span>🔎 Scout Similar</span>
            </button>
          )}

          {/* Add Selected to Book / Collection (UPWARD OPENING) */}
          <div ref={bookRef} style={{ position: 'relative' }}>
            <button
              type="button"
              onClick={() => setShowBookMenu((prev) => !prev)}
              style={{
                background: 'rgba(245, 158, 11, 0.18)',
                border: '1px solid rgba(251, 191, 36, 0.5)',
                color: '#fde68a',
                fontSize: '13px',
                fontWeight: 700,
                padding: '7px 12px',
                borderRadius: '9px',
                cursor: 'pointer',
              }}
            >
              +📚 Add to Book
            </button>

            {showBookMenu && (
              <div
                style={{
                  position: 'absolute',
                  bottom: 'calc(100% + 10px)',
                  left: 0,
                  width: '280px',
                  background: '#111827',
                  border: '1px solid rgba(255,255,255,0.2)',
                  borderRadius: '12px',
                  padding: '12px',
                  boxShadow: '0 16px 40px rgba(0,0,0,0.85)',
                  zIndex: 9500,
                }}
              >
                <div style={{ fontSize: '12px', fontWeight: 700, color: '#f8fafc', marginBottom: '8px' }}>
                  Add {selectedCount} Photo{selectedCount > 1 ? 's' : ''} to Book:
                </div>
                {collections.length > 0 && (
                  <div
                    style={{
                      maxHeight: '150px',
                      overflowY: 'auto',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      marginBottom: '10px',
                    }}
                  >
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
                          padding: '6px 10px',
                          borderRadius: '7px',
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'flex',
                          justifyContent: 'space-between',
                        }}
                      >
                        <span>📚 {col.name}</span>
                        <span style={{ color: '#94a3b8', fontSize: '11px' }}>{col.item_count || 0}</span>
                      </button>
                    ))}
                  </div>
                )}
                <form onSubmit={handleCreateNew} style={{ display: 'flex', gap: '6px' }}>
                  <input
                    type="text"
                    placeholder="New Book title..."
                    value={newBookName}
                    onChange={(e) => setNewBookName(e.target.value)}
                    style={{
                      flex: 1,
                      background: '#1f2937',
                      border: '1px solid rgba(255,255,255,0.2)',
                      borderRadius: '7px',
                      color: '#fff',
                      padding: '6px 9px',
                      fontSize: '12px',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={busyBook || !newBookName.trim()}
                    style={{
                      background: '#f59e0b',
                      border: 'none',
                      color: '#111827',
                      fontWeight: 700,
                      fontSize: '12px',
                      padding: '6px 10px',
                      borderRadius: '7px',
                      cursor: 'pointer',
                    }}
                  >
                    Create
                  </button>
                </form>
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
