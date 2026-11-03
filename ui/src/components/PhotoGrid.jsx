import React, { useMemo, useRef, useState, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Calendar, MapPin, Camera, ChevronDown, ChevronRight, X, Compass } from 'lucide-react';
import PhotoCard from './PhotoCard.jsx';

function formatReadableDate(dateStr) {
  if (!dateStr || dateStr === 'Undated') return 'Undated Archival Prints';
  try {
    const parts = dateStr.slice(0, 10).split('-');
    if (parts.length === 3) {
      const dt = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      if (!isNaN(dt.getTime())) {
        return dt.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric',
        });
      }
    }
  } catch {
    // fallback
  }
  return dateStr;
}

export default function PhotoGrid({
  photos,
  viewMode = 'grid',
  activeTrip = null,
  onClearTrip,
  activeShootDate = null,
  onClearShootDate,
  collections = [],
  onTogglePhotoInCollection,
  onCreateCollectionWithPhoto,
  onOpenCollectionsModal,
  isLoading,
  onSelectPhoto,
  onOpenSequence,
  onUpdateStar,
  onTagClick,
  onLoadMore,
  hasMore,
  selectedPhotoIds = new Set(),
  onToggleSelectPhoto,
}) {
  const parentRef = useRef(null);
  const lastScrollTopRef = useRef(0);
  const [columns, setColumns] = useState(5);
  const [collapsedDates, setCollapsedDates] = useState({});

  // Track scroll position so in-place photo updates never snap grid to top
  useEffect(() => {
    const el = parentRef.current;
    if (!el) return;
    const handleScroll = () => {
      lastScrollTopRef.current = el.scrollTop;
    };
    el.addEventListener('scroll', handleScroll, { passive: true });
    return () => el.removeEventListener('scroll', handleScroll);
  }, []);

  // Responsive column count calculation (ResizeObserver + window resize so initial mount is always measured)
  const hasPhotos = Boolean(photos && photos.length > 0);
  useEffect(() => {
    const updateColumns = () => {
      const width = parentRef.current?.clientWidth || window.innerWidth || 1440;
      let nextCols = 5;
      if (width < 640) nextCols = 2;
      else if (width < 1024) nextCols = 3;
      else if (width < 1440) nextCols = 4;
      else if (width < 1920) nextCols = 5;
      else nextCols = 6;
      setColumns((prev) => (prev === nextCols ? prev : nextCols));
    };

    updateColumns();
    window.addEventListener('resize', updateColumns);
    let resizeObserver = null;
    if (parentRef.current && typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(() => updateColumns());
      resizeObserver.observe(parentRef.current);
    }
    return () => {
      window.removeEventListener('resize', updateColumns);
      if (resizeObserver) resizeObserver.disconnect();
    };
  }, [hasPhotos]);

  const toggleDateCollapse = (dateKey) => {
    setCollapsedDates((prev) => ({
      ...prev,
      [dateKey]: !prev[dateKey],
    }));
  };

  // Build virtualized rows:
  // - viewMode === 'grid': Continuous Light-Table Grid (no date-row breaks!)
  // - viewMode === 'date': Collapsible Shoot Days with Smart Titles
  const flattenedVirtualItems = useMemo(() => {
    if (!photos || photos.length === 0) return [];

    if (viewMode === 'grid') {
      const items = [];
      for (let i = 0; i < photos.length; i += columns) {
        items.push({
          type: 'row',
          date: 'grid',
          photos: photos.slice(i, i + columns),
        });
      }
      return items;
    }

    // viewMode === 'date': Group photos by shoot_date, placing 'Undated' cleanly at the very bottom
    const dateMap = new Map();
    for (const p of photos) {
      const pDate = p.shoot_date || 'Undated';
      if (!dateMap.has(pDate)) {
        dateMap.set(pDate, []);
      }
      dateMap.get(pDate).push(p);
    }

    const orderedDateKeys = Array.from(dateMap.keys()).sort((a, b) => {
      if (a === 'Undated' && b === 'Undated') return 0;
      if (a === 'Undated') return 1;
      if (b === 'Undated') return -1;
      return b.localeCompare(a);
    });

    const items = [];
    for (const dateKey of orderedDateKeys) {
      const groupPhotos = dateMap.get(dateKey);
      const cameras = new Set();

      groupPhotos.forEach((ph) => {
        if (ph.camera_model) cameras.add(ph.camera_model);
      });

      const isCollapsed = !!collapsedDates[dateKey];

      items.push({
        type: 'header',
        date: dateKey,
        readableDate: formatReadableDate(dateKey),
        count: groupPhotos.length,
        cameras: Array.from(cameras).slice(0, 2).join(' / '),
        isCollapsed,
      });

      if (!isCollapsed) {
        for (let i = 0; i < groupPhotos.length; i += columns) {
          items.push({
            type: 'row',
            date: dateKey,
            photos: groupPhotos.slice(i, i + columns),
          });
        }
      }
    }

    return items;
  }, [photos, columns, viewMode, collapsedDates]);

  // Flattened visual order of photos so Lightbox Left/Right matches exact on-screen order in both Grid and By Date
  const orderedVisiblePhotos = useMemo(() => {
    const list = [];
    for (const item of flattenedVirtualItems) {
      if (item.type === 'row' && Array.isArray(item.photos)) {
        list.push(...item.photos);
      }
    }
    return list.length > 0 ? list : photos || [];
  }, [flattenedVirtualItems, photos]);

  // Virtualizer setup
  const rowVirtualizer = useVirtualizer({
    count: flattenedVirtualItems.length,
    getScrollElement: () => parentRef.current,
    getItemKey: (index) => {
      const item = flattenedVirtualItems[index];
      if (!item) return index;
      return item.type === 'header'
        ? `hdr-${item.date}`
        : `row-${item.date}-${item.photos?.[0]?.file_hash || index}`;
    },
    estimateSize: (index) => {
      const item = flattenedVirtualItems[index];
      if (item?.type === 'header') return 46;
      return 260;
    },
    overscan: 5,
  });

  // Re-measure row heights only when layout structure changes (NOT on in-place star/tag updates)
  useEffect(() => {
    rowVirtualizer.measure();
  }, [collapsedDates, viewMode, columns]);

  // Preserve grid scroll position across in-place photo tag updates
  useEffect(() => {
    if (parentRef.current && lastScrollTopRef.current > 0) {
      if (Math.abs(parentRef.current.scrollTop - lastScrollTopRef.current) > 10) {
        parentRef.current.scrollTop = lastScrollTopRef.current;
      }
    }
  }, [photos]);

  // Handle infinite scroll / load more trigger near bottom
  useEffect(() => {
    const virtualItems = rowVirtualizer.getVirtualItems();
    if (!virtualItems || virtualItems.length === 0) return;

    const lastItem = virtualItems[virtualItems.length - 1];
    if (lastItem && lastItem.index >= flattenedVirtualItems.length - 2 && hasMore && !isLoading) {
      if (onLoadMore) onLoadMore();
    }
  }, [rowVirtualizer.getVirtualItems(), flattenedVirtualItems.length, hasMore, isLoading, onLoadMore]);

  const handleCollapseAll = (collapseState) => {
    if (!photos) return;
    const next = {};
    photos.forEach((p) => {
      const d = p.shoot_date || 'Undated';
      next[d] = collapseState;
    });
    setCollapsedDates(next);
  };

  if (!photos || photos.length === 0) {
    if (isLoading) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center p-12 text-studio-textMuted font-mono text-sm">
          <div className="w-8 h-8 border-2 border-studio-accent border-t-transparent rounded-full animate-spin mb-3"></div>
          <span>Querying archive catalog & vectors...</span>
        </div>
      );
    }
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-studio-textMuted font-mono">
        <p className="text-base text-studio-text mb-1">No matching photos found in archive</p>
        <p className="text-xs text-studio-textDim max-w-md">
          Try broadening your search query, switching catalog tab, or toggling off the aesthetic / star filters.
        </p>
        {activeTrip && onClearTrip && (
          <button
            onClick={onClearTrip}
            className="mt-4 px-3 py-1.5 bg-amber-500 text-zinc-950 font-semibold text-xs rounded-sm"
          >
            Clear Trip Filter
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      ref={parentRef}
      className="flex-1 overflow-y-auto px-4 py-3 bg-studio-bg"
      style={{ height: 'calc(100vh - 82px)' }}
    >
      {/* Active Shoot Day Banner when jumped from Lightbox "Open Full Day in Main Grid" */}
      {activeShootDate && (
        <div className="mb-3 px-4 py-2.5 bg-amber-500/15 border border-amber-500/50 rounded-lg flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 font-mono text-xs">
            <Calendar className="w-4 h-4 text-amber-400 shrink-0" />
            <div>
              <span className="text-amber-300 font-semibold">
                📅 Viewing Shoot Day: {formatReadableDate(activeShootDate)}
              </span>
              <span className="text-zinc-400 mx-2">·</span>
              <span className="text-white font-medium">
                ({photos.length} {photos.length === 1 ? 'photo' : 'photos'})
              </span>
            </div>
          </div>
          {onClearShootDate && (
            <button
              onClick={onClearShootDate}
              className="flex items-center gap-1.5 px-3 py-1 rounded bg-zinc-900 hover:bg-zinc-800 text-amber-300 border border-amber-500/40 text-xs font-mono font-semibold transition"
            >
              <X className="w-3.5 h-3.5" />
              <span>✕ Show All Photos</span>
            </button>
          )}
        </div>
      )}

      {/* Active Trip Banner when filtering from Trips & Map */}
      {activeTrip && (
        <div className="mb-3 px-4 py-2.5 bg-amber-500/10 border border-amber-500/40 rounded-lg flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Compass className="w-4 h-4 text-amber-400 shrink-0" />
            <div className="text-xs">
              <span className="text-amber-300 font-semibold">{activeTrip.trip_name}</span>
              <span className="text-zinc-400 mx-2">·</span>
              <span className="text-zinc-300">{activeTrip.date_range_label}</span>
              <span className="text-zinc-400 mx-2">·</span>
              <span className="text-zinc-400">📍 {activeTrip.location_name}</span>
            </div>
          </div>
          {onClearTrip && (
            <button
              onClick={onClearTrip}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-zinc-900 hover:bg-zinc-800 text-amber-300 border border-amber-500/30 text-xs font-medium transition"
            >
              <X className="w-3.5 h-3.5" />
              <span>Clear Trip Filter</span>
            </button>
          )}
        </div>
      )}

      {/* Quick Expand All / Collapse All bar when in By Date mode */}
      {viewMode === 'date' && (
        <div className="mb-2.5 flex items-center justify-between px-1 text-xs font-mono text-studio-textMuted">
          <span>Click any shoot date header below to collapse or expand</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleCollapseAll(false)}
              className="px-2 py-0.5 bg-studio-panel hover:bg-studio-hover border border-studio-border rounded-sm text-zinc-300"
            >
              Expand All Days
            </button>
            <button
              onClick={() => handleCollapseAll(true)}
              className="px-2 py-0.5 bg-studio-panel hover:bg-studio-hover border border-studio-border rounded-sm text-zinc-300"
            >
              Collapse All Days
            </button>
          </div>
        </div>
      )}

      <div
        className="w-full relative"
        style={{ height: `${rowVirtualizer.getTotalSize()}px` }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const item = flattenedVirtualItems[virtualRow.index];
          if (!item) return null;

          if (item.type === 'header') {
            return (
              <div
                key={`header-${item.date}-${virtualRow.index}`}
                ref={rowVirtualizer.measureElement}
                data-index={virtualRow.index}
                onClick={() => toggleDateCollapse(item.date)}
                className="absolute top-0 left-0 w-full pb-1.5 z-10"
                style={{
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div className="flex items-center justify-between py-2 px-3 bg-studio-panel/95 hover:bg-studio-hover/90 border border-studio-border rounded-sm cursor-pointer backdrop-blur-sm transition-colors">
                  <div className="flex items-center gap-2 text-xs font-mono text-white font-medium min-w-0">
                    {item.isCollapsed ? (
                      <ChevronRight className="w-4 h-4 text-amber-400 shrink-0" />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-amber-400 shrink-0" />
                    )}
                    <span className="text-amber-300 font-semibold shrink-0">
                      📅 {item.readableDate}
                    </span>
                    <span className="text-zinc-500 shrink-0">·</span>
                    <span className="text-zinc-200 font-mono shrink-0">
                      {item.count} {item.count === 1 ? 'frame' : 'frames'}
                    </span>
                    {item.cameras && (
                      <span className="text-studio-textMuted font-mono truncate">
                        ({item.cameras})
                      </span>
                    )}
                  </div>

                  {item.cameras && (
                    <div className="hidden md:flex items-center gap-1.5 text-[11px] font-mono text-studio-textDim shrink-0">
                      <Camera className="w-3 h-3 text-studio-borderLight" />
                      <span>{item.cameras}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          }

          // Row of photo cards
          return (
            <div
              key={virtualRow.key}
              ref={rowVirtualizer.measureElement}
              data-index={virtualRow.index}
              className="absolute top-0 left-0 w-full grid gap-2.5 pb-2.5"
              style={{
                transform: `translateY(${virtualRow.start}px)`,
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
              }}
            >
              {item.photos.map((ph) => {
                const phKey = ph.file_hash || ph.file_path;
                return (
                  <PhotoCard
                    key={ph.file_path || ph.file_hash}
                    photo={ph}
                    onClick={(clickedPhoto) =>
                      onSelectPhoto && onSelectPhoto(clickedPhoto, orderedVisiblePhotos)
                    }
                    onOpenSequence={onOpenSequence}
                    onUpdateStar={onUpdateStar}
                    onTagClick={onTagClick}
                    collections={collections}
                    onTogglePhotoInCollection={onTogglePhotoInCollection}
                    onCreateCollectionWithPhoto={onCreateCollectionWithPhoto}
                    onOpenCollectionsModal={onOpenCollectionsModal}
                    isSelected={selectedPhotoIds?.has(phKey)}
                    onToggleSelect={(clickedPhoto, event) =>
                      onToggleSelectPhoto &&
                      onToggleSelectPhoto(clickedPhoto, event, orderedVisiblePhotos)
                    }
                  />
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
