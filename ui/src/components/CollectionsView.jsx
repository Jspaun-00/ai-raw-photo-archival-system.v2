import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  FolderPlus,
  Trash2,
  Download,
  ChevronDown,
  MoveLeft,
  MoveRight,
  X,
  Image as ImageIcon,
  Check,
  Film,
  Sparkles,
  Lightbulb,
} from 'lucide-react';
import StudioGuideDrawer from './StudioGuideDrawer.jsx';

export default function CollectionsView({
  collections = [],
  initialCollectionId = null,
  onRefreshCollections,
  onSelectPhoto,
  onSwitchToGrid,
  onExportCustomPrint,
  onExportTvShowcase,
  onExportTiff,
  onOpenHelpGuide,
  showGlobalToast = () => {},
}) {
  const safeCollections = Array.isArray(collections) ? collections : [];

  // Active collection ID selection
  const [selectedId, setSelectedId] = useState(() => {
    if (initialCollectionId && safeCollections.some((c) => c.id === initialCollectionId)) {
      return initialCollectionId;
    }
    return safeCollections.length > 0 ? safeCollections[0].id : null;
  });

  useEffect(() => {
    if (initialCollectionId) {
      setSelectedId(initialCollectionId);
    }
  }, [initialCollectionId]);

  // Keep selectedId valid if collections change
  useEffect(() => {
    if (selectedId && !safeCollections.some((c) => c.id === selectedId)) {
      setSelectedId(safeCollections.length > 0 ? safeCollections[0].id : null);
    } else if (!selectedId && safeCollections.length > 0) {
      setSelectedId(safeCollections[0].id);
    }
  }, [safeCollections, selectedId]);

  // Active collection details (with ordered photo records)
  const [activeDetail, setActiveDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Drag and drop sequencing
  const [dragIndex, setDragIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  // Create Collection Modal
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState('');
  const [wantDescription, setWantDescription] = useState(false);
  const [createDescription, setCreateDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  // Export dropdown state
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const [isGuideOpen, setIsGuideOpen] = useState(false);
  const exportRef = useRef(null);

  // Close export dropdown on outside click
  useEffect(() => {
    const handleOutside = (e) => {
      if (exportRef.current && !exportRef.current.contains(e.target)) {
        setExportMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  // Fetch full details of the active collection
  const fetchActiveCollection = useCallback(async (colId) => {
    if (!colId) {
      setActiveDetail(null);
      return;
    }
    setLoadingDetail(true);
    try {
      const res = await fetch(`/api/collections/${colId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setActiveDetail(data);
    } catch (err) {
      console.error('Failed to load collection:', err);
      showGlobalToast(`Error loading collection: ${err.message}`);
    } finally {
      setLoadingDetail(false);
    }
  }, [showGlobalToast]);

  useEffect(() => {
    if (selectedId) {
      fetchActiveCollection(selectedId);
    } else {
      setActiveDetail(null);
    }
  }, [selectedId, fetchActiveCollection]);

  // Create New Collection
  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    const trimmed = createName.trim();
    if (!trimmed || isCreating) return;
    setIsCreating(true);
    try {
      const payload = {
        name: trimmed,
        title: trimmed,
        description: wantDescription ? createDescription.trim() : '',
      };
      const res = await fetch('/api/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `Failed to create collection (${res.status})`);

      showGlobalToast(`Created collection "${trimmed}"`);
      setCreateName('');
      setCreateDescription('');
      setWantDescription(false);
      setIsCreateModalOpen(false);

      if (onRefreshCollections) {
        await onRefreshCollections();
      }
      if (data.id) {
        setSelectedId(data.id);
      }
    } catch (err) {
      console.error('Create collection error:', err);
      showGlobalToast(`Error: ${err.message}`);
    } finally {
      setIsCreating(false);
    }
  };

  // Delete Collection
  const handleDeleteCollection = async (e, col) => {
    e.stopPropagation();
    if (!window.confirm(`Delete collection "${col.name || 'Untitled'}"?\n\nPhotos will remain safe in your catalog.`)) {
      return;
    }
    try {
      const res = await fetch(`/api/collections/${col.id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`Failed to delete (${res.status})`);
      showGlobalToast(`Deleted collection "${col.name}"`);
      if (onRefreshCollections) await onRefreshCollections();
      const remaining = safeCollections.filter((c) => c.id !== col.id);
      setSelectedId(remaining.length > 0 ? remaining[0].id : null);
    } catch (err) {
      console.error('Delete collection error:', err);
      showGlobalToast(`Delete failed: ${err.message}`);
    }
  };

  // Remove individual photo from active collection
  const handleRemovePhoto = async (photo) => {
    if (!selectedId || !photo) return;
    const photoKey = photo.file_hash || photo.file_path;
    if (!photoKey) return;

    try {
      const res = await fetch(
        `/api/collections/${selectedId}/items/${encodeURIComponent(photoKey)}`,
        { method: 'DELETE' }
      );
      if (!res.ok) throw new Error(`Failed to remove item (${res.status})`);

      // Update local state immediately for snappy response
      setActiveDetail((prev) => {
        if (!prev) return prev;
        const filtered = (prev.photos || []).filter(
          (p) => (p.file_hash || p.file_path) !== photoKey
        );
        return { ...prev, photos: filtered, item_count: filtered.length };
      });
      showGlobalToast('Removed plate from collection');
      if (onRefreshCollections) await onRefreshCollections();
      await fetchActiveCollection(selectedId);
    } catch (err) {
      console.error('Remove photo error:', err);
      showGlobalToast(`Error: ${err.message}`);
    }
  };

  // Commit reordered sequence to backend
  const commitReorder = async (newPhotos) => {
    if (!selectedId) return;
    setActiveDetail((prev) => (prev ? { ...prev, photos: newPhotos } : prev));
    const orderedKeys = newPhotos.map((p) => p.file_hash || p.file_path);
    try {
      await fetch(`/api/collections/${selectedId}/reorder`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ photo_ids: orderedKeys, file_hashes: orderedKeys }),
      });
      if (onRefreshCollections) onRefreshCollections();
    } catch (err) {
      console.error('Reorder error:', err);
      showGlobalToast(`Failed to save sequence: ${err.message}`);
    }
  };

  // Nudge photo left or right in sequence
  const handleNudge = (index, direction) => {
    const photos = [...(activeDetail?.photos || [])];
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= photos.length) return;
    const [moved] = photos.splice(index, 1);
    photos.splice(targetIndex, 0, moved);
    commitReorder(photos);
  };

  // Drag and Drop reordering
  const handleDrop = (targetIndex) => {
    if (dragIndex === null || dragIndex === targetIndex) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    const photos = [...(activeDetail?.photos || [])];
    const [moved] = photos.splice(dragIndex, 1);
    photos.splice(targetIndex, 0, moved);
    setDragIndex(null);
    setDragOverIndex(null);
    commitReorder(photos);
  };

  const activePhotos = Array.isArray(activeDetail?.photos) ? activeDetail.photos : [];
  const currentCollectionMeta = safeCollections.find((c) => c.id === selectedId) || activeDetail;

  return (
    <div className="flex-1 flex overflow-hidden bg-studio-bg text-studio-text select-none">
      {/* ===================================================================== */}
      {/* LEFT SIDEBAR: Curated Collections List & Clean + Create Action       */}
      {/* ===================================================================== */}
      <aside className="w-80 border-r border-studio-border bg-studio-panel/75 flex flex-col shrink-0">
        {/* Sidebar Header */}
        <div className="p-4 border-b border-studio-border flex flex-col gap-3 bg-studio-panel">
          <div className="flex items-center justify-between gap-2">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <span>📚</span>
              <span>Curated Collections</span>
            </h2>
            <p className="text-[11px] text-studio-textDim font-mono">
              {safeCollections.length} Collection{safeCollections.length === 1 ? '' : 's'}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setIsCreateModalOpen(true)}
            title="Create a new curated collection"
            className="w-full flex items-center justify-center gap-2 py-3.5 px-4 rounded-xl bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-sm shadow-[0_4px_20px_rgba(245,158,11,0.45)] transition-all cursor-pointer border-2 border-amber-300 uppercase tracking-wide hover:scale-[1.01]"
          >
            <FolderPlus className="w-5 h-5 text-zinc-950 stroke-[2.5]" />
            <span>＋ Create New Collection</span>
          </button>
        </div>

        {/* Collections List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
          {safeCollections.length === 0 ? (
            <div className="p-6 text-center text-xs text-studio-textDim space-y-3">
              <p>No curated collections yet.</p>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(true)}
                className="w-full px-5 py-3 rounded-xl bg-amber-400 text-zinc-950 font-black text-sm hover:bg-amber-300 transition-all cursor-pointer shadow-lg border-2 border-amber-300 uppercase tracking-wide"
              >
                ＋ Create First Collection
              </button>
            </div>
          ) : (
            safeCollections.map((col) => {
              const isSelected = col.id === selectedId;
              const count =
                typeof col.item_count === 'number'
                  ? col.item_count
                  : Array.isArray(col.photo_ids)
                  ? col.photo_ids.length
                  : 0;

              return (
                <div
                  key={col.id}
                  onClick={() => setSelectedId(col.id)}
                  className={`group flex items-center justify-between p-3 rounded-lg border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-amber-500/15 border-amber-500/60 text-white shadow-sm ring-1 ring-amber-500/30'
                      : 'bg-studio-card/60 hover:bg-studio-hover border-studio-border/60 text-studio-text hover:text-white'
                  }`}
                >
                  <div className="min-w-0 flex-1 pr-2">
                    <div className="font-bold text-sm truncate flex items-center gap-1.5">
                      <span className={isSelected ? 'text-amber-400' : 'text-studio-textDim'}>
                        {isSelected ? '★' : '📁'}
                      </span>
                      <span className="truncate">{col.name || 'Untitled Collection'}</span>
                    </div>
                    {col.description && (
                      <p className="text-xs text-studio-textDim truncate mt-0.5">
                        {col.description}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={`text-xs font-mono px-2.5 py-0.5 rounded-full font-bold ${
                        isSelected
                          ? 'bg-amber-500/30 text-amber-200 border border-amber-400/40'
                          : 'bg-studio-panel text-studio-textMuted border border-studio-border/50'
                      }`}
                    >
                      {count} {count === 1 ? 'Plate' : 'Plates'}
                    </span>

                    <button
                      type="button"
                      onClick={(e) => handleDeleteCollection(e, col)}
                      title={`Delete collection "${col.name}"`}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded hover:bg-red-500/20 text-studio-textDim hover:text-red-300 transition-opacity cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </aside>

      {/* ===================================================================== */}
      {/* RIGHT GALLERY CANVAS: Header, Export Dropdown & Light-Table Grid       */}
      {/* ===================================================================== */}
      <main className="flex-1 flex flex-col overflow-y-auto bg-studio-bg">
        {selectedId && currentCollectionMeta ? (
          <>
            {/* Gallery Canvas Header */}
            <div className="sticky top-0 z-20 bg-studio-panel/95 backdrop-blur-md border-b border-studio-border px-6 py-3.5 flex items-center justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <h1 className="text-lg font-bold text-white tracking-tight truncate">
                    {currentCollectionMeta.name || 'Untitled Collection'}
                  </h1>
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-400/40 text-amber-300 font-mono text-xs font-bold">
                    {activePhotos.length} {activePhotos.length === 1 ? 'Plate' : 'Plates'}
                  </span>
                </div>
                {currentCollectionMeta.description && (
                  <p className="text-xs text-studio-textDim mt-0.5 line-clamp-1">
                    {currentCollectionMeta.description}
                  </p>
                )}
              </div>

              {/* Header Action Buttons: Add Photos + Curating Guide + Export Collection */}
              <div className="flex items-center gap-2.5 shrink-0">
                {onSwitchToGrid && (
                  <button
                    type="button"
                    onClick={onSwitchToGrid}
                    className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#222222] hover:bg-[#2C2C2C] border border-[#3A3A3A] text-zinc-100 hover:text-white font-bold text-[13.5px] transition-all shadow cursor-pointer"
                    title="Return to Photo Grid to select and add photos to this collection"
                  >
                    <ImageIcon className="w-4 h-4 text-amber-400" />
                    <span>＋ Add Photos from Grid</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    if (onOpenHelpGuide) {
                      onOpenHelpGuide('collections');
                    } else {
                      setIsGuideOpen((prev) => !prev);
                    }
                  }}
                  className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-amber-500/15 hover:bg-amber-500/25 border border-amber-400/60 hover:border-amber-400 text-amber-300 hover:text-white font-bold text-[13.5px] transition-all shadow cursor-pointer"
                  title="Open Curating Guide (Creating collections, sequencing, cloud exports)"
                >
                  <Lightbulb className="w-4 h-4 text-amber-400" />
                  <span>💡 Curating Guide</span>
                </button>

                {/* Export Collection Menu */}
                <div ref={exportRef} className="relative shrink-0">
                  <button
                    type="button"
                    disabled={activePhotos.length === 0}
                    onClick={() => setExportMenuOpen((prev) => !prev)}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/35 border border-emerald-400/60 hover:border-emerald-400 text-emerald-200 hover:text-white font-bold text-[13.5px] transition-all shadow-md cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Export all plates in this collection"
                  >
                    <Download className="w-4 h-4 text-emerald-400" />
                    <span>Export Collection</span>
                    <ChevronDown className="w-4 h-4 opacity-80" />
                  </button>

                {exportMenuOpen && (
                  <div className="absolute right-0 top-full mt-2 w-80 bg-studio-panel border border-studio-borderLight rounded-xl shadow-2xl p-2.5 z-50 flex flex-col gap-1.5 text-xs font-mono">
                    <div className="px-2 py-1 text-[11px] font-bold text-emerald-400 border-b border-studio-border flex justify-between">
                      <span>EXPORT {activePhotos.length} PLATES</span>
                      <span className="text-studio-textDim">Full Quality</span>
                    </div>

                    {/* Option 1: Custom Print Sizing (JPEG) */}
                    <button
                      type="button"
                      onClick={() => {
                        setExportMenuOpen(false);
                        if (onExportCustomPrint) {
                          onExportCustomPrint(activePhotos, currentCollectionMeta.name);
                        }
                      }}
                      className="w-full text-left p-2.5 rounded-lg border border-purple-500/30 hover:border-purple-400 bg-purple-500/10 hover:bg-purple-500/20 transition-colors cursor-pointer space-y-1"
                    >
                      <div className="font-bold text-purple-300 flex items-center justify-between">
                        <span>🖨️ Custom Print Sizing (JPEG)</span>
                      </div>
                      <div className="text-[11px] text-studio-textMuted leading-tight">
                        Presets up to 12,000px, 240/300 DPI with Lightroom develop edits applied.
                      </div>
                    </button>

                    {/* Option 2: 65" TV Showcase & Samsung TV Push (16:9 Crop) */}
                    <button
                      type="button"
                      onClick={() => {
                        setExportMenuOpen(false);
                        if (onExportTvShowcase) {
                          onExportTvShowcase(activePhotos, currentCollectionMeta.name);
                        }
                      }}
                      className="w-full text-left p-2.5 rounded-lg border border-amber-500/45 hover:border-amber-400 bg-amber-500/10 hover:bg-amber-500/20 transition-colors cursor-pointer space-y-1"
                    >
                      <div className="font-bold text-amber-300 flex items-center justify-between">
                        <span>📺 Samsung TV Push &amp; 16:9 Showcase</span>
                        <span className="text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded text-amber-200">Wi-Fi / 12k</span>
                      </div>
                      <div className="text-[11px] text-studio-textMuted leading-tight">
                        Interactive 16:9 crop + Push directly to Samsung Frame TV (or Desktop / iCloud).
                      </div>
                    </button>

                    {/* Option 3: Archival Master TIFF (.tif) */}
                    <button
                      type="button"
                      onClick={() => {
                        setExportMenuOpen(false);
                        if (onExportTiff) {
                          onExportTiff(currentCollectionMeta.id, activePhotos, currentCollectionMeta.name);
                        }
                      }}
                      className="w-full text-left p-2.5 rounded-lg border border-studio-border hover:border-sky-400/60 bg-studio-bg hover:bg-sky-500/10 transition-colors cursor-pointer space-y-1"
                    >
                      <div className="font-bold text-sky-300 flex items-center justify-between">
                        <span>📁 Archival Master TIFF (.tif)</span>
                        <span className="text-[10px] text-sky-400">LZW · Edits</span>
                      </div>
                      <div className="text-[11px] text-studio-textMuted leading-tight">
                        Uncompressed 100% full-resolution archival master TIFFs with edits applied.
                      </div>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>

            {/* Gallery Light-Table Grid */}
            <div className="flex-1 p-6">
              {loadingDetail ? (
                <div className="h-64 flex items-center justify-center text-studio-textDim gap-2 text-sm">
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping"></span>
                  <span>Loading collection plates...</span>
                </div>
              ) : activePhotos.length === 0 ? (
                <div className="max-w-md mx-auto my-20 p-8 rounded-xl border border-dashed border-studio-border text-center space-y-4 bg-studio-panel/40">
                  <div className="text-3xl">🖼️</div>
                  <h3 className="text-sm font-bold text-white">This collection is empty</h3>
                  <p className="text-xs text-studio-textDim leading-relaxed">
                    Browse your catalog in <strong>Grid</strong> or <strong>By Date</strong> view, and click{' '}
                    <strong className="text-amber-300">📚 Add to Collection</strong> on any photo card to curate plates here.
                  </p>
                  {onSwitchToGrid && (
                    <button
                      type="button"
                      onClick={onSwitchToGrid}
                      className="px-5 py-2.5 rounded-xl bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-xs transition-all cursor-pointer shadow-md border-2 border-amber-300 uppercase tracking-wide inline-flex items-center gap-2"
                    >
                      <ImageIcon className="w-4 h-4 text-zinc-950" />
                      <span>Go to Photo Grid &amp; Add Photos</span>
                    </button>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-5">
                  {activePhotos.map((photo, index) => {
                    const thumbUrl =
                      photo.thumb_url ||
                      (photo.thumb_360_path
                        ? `/previews/thumbs_360/${photo.thumb_360_path.split('/').pop()}`
                        : null);
                    const filename = photo.file_path
                      ? photo.file_path.split('/').pop()
                      : photo.title || `Photo ${index + 1}`;
                    const plateNumber = String(index + 1).padStart(2, '0');
                    const isDraggingThis = dragIndex === index;
                    const isOverThis = dragOverIndex === index;

                    return (
                      <div
                        key={photo.file_hash || photo.file_path || index}
                        draggable
                        onDragStart={() => setDragIndex(index)}
                        onDragOver={(e) => {
                          e.preventDefault();
                          if (dragOverIndex !== index) setDragOverIndex(index);
                        }}
                        onDragLeave={() => {
                          if (dragOverIndex === index) setDragOverIndex(null);
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          handleDrop(index);
                        }}
                        className={`group relative flex flex-col bg-studio-card border rounded-lg overflow-hidden transition-all duration-150 shadow-md ${
                          isOverThis
                            ? 'border-amber-400 ring-2 ring-amber-400/70 scale-102'
                            : isDraggingThis
                            ? 'opacity-40 border-dashed border-studio-border'
                            : 'border-studio-border hover:border-studio-borderLight'
                        }`}
                      >
                        {/* Plate Number & Drag Handle Bar */}
                        <div className="flex items-center justify-between px-3 py-2 bg-studio-panel border-b border-studio-border/60 text-xs font-mono">
                          <span className="font-bold text-amber-300 flex items-center gap-1">
                            <span>Plate #{plateNumber}</span>
                          </span>

                          <span className="text-[11px] text-studio-textDim uppercase tracking-wider group-hover:text-studio-text">
                            ⠿ Drag to Reorder
                          </span>
                        </div>

                        {/* Uncropped Full Aspect Ratio Image Preview Container */}
                        <div
                          onClick={() => onSelectPhoto && onSelectPhoto(photo, activePhotos)}
                          className="relative aspect-[4/3] bg-[#090c13] flex items-center justify-center overflow-hidden cursor-pointer"
                        >
                          {thumbUrl ? (
                            <img
                              src={thumbUrl}
                              alt={filename}
                              loading="lazy"
                              className="w-full h-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
                            />
                          ) : (
                            <ImageIcon className="w-8 h-8 text-studio-border" />
                          )}

                          {/* Hover Overlay with Lightbox Indicator */}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                            <span className="px-3 py-1.5 rounded bg-black/80 border border-white/20 text-xs font-mono text-white shadow-lg">
                              🔍 Open Lightbox
                            </span>
                          </div>
                        </div>

                        {/* Plate Controls & Filename Footer */}
                        <div className="p-2.5 bg-studio-panel border-t border-studio-border/60 flex items-center justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="text-[13px] font-mono font-semibold truncate text-studio-text group-hover:text-white" title={filename}>
                              {filename}
                            </div>
                            {photo.star_rating > 0 && (
                              <div className="text-xs text-amber-400 font-bold">
                                {'★'.repeat(photo.star_rating)}
                              </div>
                            )}
                          </div>

                          {/* Sequence Nudge and Remove Buttons */}
                          <div className="flex items-center gap-1.5 shrink-0">
                            <button
                              type="button"
                              disabled={index === 0}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleNudge(index, -1);
                              }}
                              title="Move earlier in sequence (◀)"
                              className="p-1.5 rounded bg-studio-bg hover:bg-studio-hover text-studio-textDim hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer border border-studio-border/50"
                            >
                              <MoveLeft className="w-4 h-4" />
                            </button>

                            <button
                              type="button"
                              disabled={index === activePhotos.length - 1}
                              onClick={(e) => {
                                e.stopPropagation();
                                handleNudge(index, 1);
                              }}
                              title="Move later in sequence (▶)"
                              className="p-1.5 rounded bg-studio-bg hover:bg-studio-hover text-studio-textDim hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-colors cursor-pointer border border-studio-border/50"
                            >
                              <MoveRight className="w-4 h-4" />
                            </button>

                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleRemovePhoto(photo);
                              }}
                              title="Remove plate from this collection"
                              className="p-1.5 rounded bg-red-950/30 hover:bg-red-900/60 text-red-400 hover:text-red-200 border border-red-500/40 transition-colors cursor-pointer"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center p-12 text-center">
            <div className="max-w-md space-y-4">
              <div className="text-4xl">📚</div>
              <h2 className="text-lg font-bold text-white">Select or Create a Collection</h2>
              <p className="text-xs text-studio-textDim leading-relaxed">
                Curated collections let Mitch group, order, and present exhibition plates with exact sequencing for print books, TV showcases, and portfolio delivery.
              </p>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(true)}
                className="px-6 py-3 rounded-xl bg-amber-400 hover:bg-amber-300 text-zinc-950 font-black text-sm shadow-lg transition-all cursor-pointer inline-flex items-center gap-2.5 border-2 border-amber-300 uppercase tracking-wide"
              >
                <FolderPlus className="w-5 h-5 text-zinc-950 stroke-[2.5]" />
                <span>＋ Create New Collection</span>
              </button>
            </div>
          </div>
        )}
      </main>

      {/* ===================================================================== */}
      {/* SIMPLE + CLEAN CREATE COLLECTION MODAL                                */}
      {/* ===================================================================== */}
      {isCreateModalOpen && (
        <div
          onClick={() => setIsCreateModalOpen(false)}
          className="fixed inset-0 z-[10500] bg-black/85 backdrop-blur-md flex items-center justify-center p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-studio-panel border border-studio-borderLight rounded-2xl shadow-2xl p-6 text-studio-text space-y-5"
          >
            <div className="flex items-center justify-between border-b border-studio-border pb-3">
              <div className="flex items-center gap-2">
                <span className="text-xl">📁</span>
                <h3 className="text-base font-bold text-white">Create New Collection</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsCreateModalOpen(false)}
                className="p-1 rounded hover:bg-studio-hover text-studio-textDim hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-xs font-bold text-amber-300 uppercase tracking-wider font-mono">
                    Collection Name *
                  </label>
                  <span className="text-[11px] font-mono text-amber-400/90 font-semibold">
                    Required to unlock Create button
                  </span>
                </div>
                <input
                  type="text"
                  autoFocus
                  required
                  placeholder="e.g. TV 1, TV 2, Bandon Coastlines, Oregon Palouse..."
                  value={createName}
                  onChange={(e) => setCreateName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-studio-bg border-2 border-amber-400/60 focus:border-amber-400 focus:ring-2 focus:ring-amber-400/40 text-white text-sm font-semibold outline-none transition-all"
                />
                {!createName.trim() ? (
                  <p className="mt-1.5 text-[11px] text-amber-300/90 font-mono flex items-center gap-1.5">
                    <span>⚠️</span>
                    <span>Type a collection name above so the Create Collection button lights up.</span>
                  </p>
                ) : (
                  <p className="mt-1.5 text-[11px] text-emerald-400 font-mono font-bold flex items-center gap-1.5">
                    <span>✓</span>
                    <span>Name ready — click the yellow Create Collection button below!</span>
                  </p>
                )}
              </div>

              {/* Simple Toggle: Add a description? Yes / No */}
              <div>
                <div className="flex items-center justify-between text-xs text-studio-text mb-1.5">
                  <span className="font-semibold">Add a description? (Optional)</span>
                  <div className="flex rounded-md border border-studio-border overflow-hidden p-0.5 bg-studio-bg">
                    <button
                      type="button"
                      onClick={() => setWantDescription(false)}
                      className={`px-2.5 py-1 text-[11px] font-bold rounded transition-colors cursor-pointer ${
                        !wantDescription
                          ? 'bg-zinc-700 text-white'
                          : 'text-studio-textDim hover:text-white'
                      }`}
                    >
                      No
                    </button>
                    <button
                      type="button"
                      onClick={() => setWantDescription(true)}
                      className={`px-2.5 py-1 text-[11px] font-bold rounded transition-colors cursor-pointer ${
                        wantDescription
                          ? 'bg-amber-500 text-black'
                          : 'text-studio-textDim hover:text-white'
                      }`}
                    >
                      Yes
                    </button>
                  </div>
                </div>

                {wantDescription && (
                  <textarea
                    rows={3}
                    placeholder="Optional curation notes or story for this collection..."
                    value={createDescription}
                    onChange={(e) => setCreateDescription(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-studio-bg border border-studio-borderLight focus:border-amber-400 focus:ring-1 focus:ring-amber-400 text-white text-xs outline-none transition-all mt-1"
                  />
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-studio-border">
                <button
                  type="button"
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2.5 rounded-lg bg-studio-bg hover:bg-studio-hover border border-studio-border text-studio-text hover:text-white text-xs font-semibold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !createName.trim()}
                  className={`px-8 py-3 rounded-xl font-black text-sm transition-all uppercase tracking-wide flex items-center gap-2 ${
                    createName.trim()
                      ? 'bg-amber-400 hover:bg-amber-300 text-zinc-950 shadow-[0_4px_20px_rgba(245,158,11,0.55)] cursor-pointer border-2 border-amber-300 hover:scale-[1.01]'
                      : 'bg-slate-800 text-slate-500 border-2 border-slate-700 cursor-not-allowed'
                  }`}
                >
                  <FolderPlus className={`w-5 h-5 stroke-[2.5] ${createName.trim() ? 'text-zinc-950' : 'text-slate-500'}`} />
                  <span>{isCreating ? 'Creating Collection...' : '✓ Create Collection'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Visual In-App Curating Guide Drawer (Fallback when standalone) */}
      {!onOpenHelpGuide && isGuideOpen && (
        <StudioGuideDrawer
          isOpen={isGuideOpen}
          onClose={() => setIsGuideOpen(false)}
          position="right"
          initialTopic="collections"
        />
      )}
    </div>
  );
}
