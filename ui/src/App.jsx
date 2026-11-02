import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import TopRibbon from './components/TopRibbon.jsx';
import PhotoGrid from './components/PhotoGrid.jsx';
import TripsMapView from './components/TripsMapView.jsx';
import LightboxModal from './components/LightboxModal.jsx';
import SequenceDrawer from './components/SequenceDrawer.jsx';
import PipelineModal from './components/PipelineModal.jsx';
import CollectionsModal from './components/CollectionsModal.jsx';
import SelectionActionBar from './components/SelectionActionBar.jsx';
import VoiceTeachScoutModal from './components/VoiceTeachScoutModal.jsx';
import LiveProgressDock from './components/LiveProgressDock.jsx';

export const getPhotoKey = (p) =>
  String(p?.file_hash || p?.file_path || p?.id || p?.photo_id || '');

class ModalErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('ModalErrorBoundary caught modal error:', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            background: 'rgba(5, 7, 11, 0.88)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            style={{
              maxWidth: '520px',
              background: '#0f1219',
              border: '1px solid #ef4444',
              borderRadius: '12px',
              padding: '24px',
              color: '#f8fafc',
            }}
          >
            <h3 style={{ margin: '0 0 8px', fontSize: '18px', fontWeight: 800, color: '#fca5a5' }}>
              ⚠️ Modal Display Error
            </h3>
            <p style={{ margin: '0 0 16px', fontSize: '14px', color: '#cbd5e1', lineHeight: 1.5 }}>
              {this.state.error?.message || 'An unexpected UI error occurred inside this panel.'}
            </p>
            <button
              type="button"
              onClick={() => {
                this.setState({ hasError: false, error: null });
                if (this.props.onClose) this.props.onClose();
              }}
              style={{
                padding: '9px 18px',
                borderRadius: '8px',
                background: '#f59e0b',
                border: 'none',
                color: '#090b10',
                fontWeight: 700,
                cursor: 'pointer',
                fontSize: '14px',
              }}
            >
              ✕ Close & Return to Studio
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const PAGE_SIZE = 250;

export default function App() {
  // Catalogs & filters state
  const [catalogs, setCatalogs] = useState([]);
  const [activeCatalog, setActiveCatalog] = useState('Keepers');
  const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'date' | 'trips'
  const [searchQuery, setSearchQuery] = useState('');
  const [aestheticPercentile, setAestheticPercentile] = useState('all');
  const [sortBy, setSortBy] = useState('capture_desc');
  const [minStars, setMinStars] = useState(null);
  const [hideUnsharp, setHideUnsharp] = useState(false);
  const [collapseStrafing, setCollapseStrafing] = useState(false);

  // Trips & Geo-Map state
  const [trips, setTrips] = useState([]);
  const [portfolioThemes, setPortfolioThemes] = useState([]);
  const [activePortfolioTheme, setActivePortfolioTheme] = useState(null);
  const [isTripsLoading, setIsTripsLoading] = useState(false);
  const [activeTrip, setActiveTrip] = useState(null);
  const [activeShootDate, setActiveShootDate] = useState(null);

  // Collections & Books state
  const [collections, setCollections] = useState([]);
  const [isCollectionsModalOpen, setIsCollectionsModalOpen] = useState(false);
  const [collectionsInitialId, setCollectionsInitialId] = useState(null);
  const [collectionsInitialMode, setCollectionsInitialMode] = useState('sequence');

  // Multi-Photo Selection & Voice Teach / Scout state
  const [selectedPhotoMap, setSelectedPhotoMap] = useState(() => new Map());
  const [lastSelectedKey, setLastSelectedKey] = useState(null);
  const [isVoiceModalOpen, setIsVoiceModalOpen] = useState(false);
  const [voiceModalMode, setVoiceModalMode] = useState('teach');
  const [voiceOverridePhotos, setVoiceOverridePhotos] = useState(null);
  const [voiceAutoStart, setVoiceAutoStart] = useState(false);

  // Live Background Job Control State (Export, Deep Re-Assess, Scout, Ingest)
  const [jobStatus, setJobStatus] = useState(null);
  const [dismissedJobId, setDismissedJobId] = useState(null);

  // 1-Click Undo Stack State (Cmd+Z)
  const [undoStatus, setUndoStatus] = useState({ available: false, count: 0, latest: null });

  // Photos & pagination state
  const [photos, setPhotos] = useState([]);
  const [totalPhotos, setTotalPhotos] = useState(0);
  const [aestheticCutoff, setAestheticCutoff] = useState(0);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [searchLatencyMs, setSearchLatencyMs] = useState(null);

  // Modals & drawers state
  const [activeLightboxPhoto, setActiveLightboxPhoto] = useState(null);
  const [activeLightboxList, setActiveLightboxList] = useState([]);
  const [activeSequenceId, setActiveSequenceId] = useState(null);
  const [isPipelineModalOpen, setIsPipelineModalOpen] = useState(false);
  const [pipelineInitialTab, setPipelineInitialTab] = useState('pipeline');
  const [globalToast, setGlobalToast] = useState(null);
  const [isSelectingAll, setIsSelectingAll] = useState(false);
  const [isBatchBusy, setIsBatchBusy] = useState(false);
  const prevJobRunningRef = useRef(false);

  const showGlobalToast = (msg) => {
    setGlobalToast(msg);
    setTimeout(() => setGlobalToast(null), 3500);
  };

  // Set of selected photo keys for O(1) lookup in PhotoGrid & TripsMapView
  const selectedPhotoIds = useMemo(
    () => new Set(selectedPhotoMap.keys()),
    [selectedPhotoMap]
  );
  const selectedPhotosArray = useMemo(
    () => Array.from(selectedPhotoMap.values()),
    [selectedPhotoMap]
  );

  // Poll /api/jobs/status for Non-Blocking Live Progress Dock
  const refreshJobStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/jobs/status');
      if (!res.ok) return null;
      const data = await res.json();
      setJobStatus(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    refreshJobStatus();
  }, [refreshJobStatus]);

  useEffect(() => {
    const isNowRunning = Boolean(jobStatus?.running);
    if (prevJobRunningRef.current && !isNowRunning && !jobStatus?.error) {
      loadCatalogs();
      fetchUndoStatus();
      const importedCat = jobStatus?.extra?.catalog_name;
      if (importedCat) {
        setActiveCatalog(importedCat);
      } else {
        fetchPhotos(1, false);
      }
      if (viewMode === 'trips') {
        fetchTrips();
      }
    }
    prevJobRunningRef.current = isNowRunning;
  }, [jobStatus?.running]);

  useEffect(() => {
    if (!jobStatus?.running) return undefined;
    const interval = setInterval(() => {
      refreshJobStatus();
    }, 800);
    return () => clearInterval(interval);
  }, [jobStatus?.running, refreshJobStatus]);

  const handlePauseJob = useCallback(async () => {
    await fetch('/api/jobs/pause', { method: 'POST' });
    refreshJobStatus();
  }, [refreshJobStatus]);

  const handleResumeJob = useCallback(async () => {
    await fetch('/api/jobs/resume', { method: 'POST' });
    refreshJobStatus();
  }, [refreshJobStatus]);

  const handleCancelJob = useCallback(async () => {
    await fetch('/api/jobs/cancel', { method: 'POST' });
    refreshJobStatus();
    showGlobalToast('Stopping background task after current file (keeping completed items)...');
  }, [refreshJobStatus]);

  // Fetch registered catalogs
  const loadCatalogs = useCallback(() => {
    fetch('/api/catalogs')
      .then((res) => res.json())
      .then((data) => {
        setCatalogs(data.catalogs || []);
      })
      .catch((err) => console.error('Failed to load catalogs:', err));
  }, []);

  // Fetch curated collections & books
  const loadCollections = useCallback(() => {
    fetch('/api/collections')
      .then((res) => res.json())
      .then((data) => {
        setCollections(data.collections || []);
      })
      .catch((err) => console.error('Failed to load collections:', err));
  }, []);

  const applyUndoStatusPayload = useCallback((statusPayload) => {
    if (!statusPayload) return;
    setUndoStatus({
      available: Boolean(statusPayload?.available ?? statusPayload?.can_undo),
      count: Number(statusPayload?.count ?? statusPayload?.undo_count ?? 0),
      latest: statusPayload?.latest || null,
    });
  }, []);

  // Fetch 1-Click Undo Stack status
  const fetchUndoStatus = useCallback(() => {
    fetch('/api/undo/status')
      .then((res) => res.json())
      .then((data) => {
        applyUndoStatusPayload(data);
      })
      .catch(() => {});
  }, [applyUndoStatusPayload]);

  useEffect(() => {
    loadCatalogs();
    loadCollections();
    fetchUndoStatus();
  }, [loadCatalogs, loadCollections, fetchUndoStatus]);

  // Fetch auto-clustered trips & 10,000-foot portfolio regions
  const fetchTrips = useCallback(() => {
    setIsTripsLoading(true);
    const params = new URLSearchParams();
    if (activeCatalog) params.set('catalog', activeCatalog);
    if (hideUnsharp) params.set('hide_unsharp', 'true');
    fetch(`/api/trips?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        const loadedTrips = data.trips || [];
        const loadedThemes = data.portfolio_themes || [];
        setTrips(loadedTrips);
        setPortfolioThemes(loadedThemes);
        setActiveTrip((prevTrip) => {
          if (!prevTrip) return null;
          const allCandidates = [...loadedThemes, ...loadedTrips];
          const exact = allCandidates.find((t) => t.trip_id === prevTrip.trip_id);
          if (exact) {
            return prevTrip.initialSubRegion
              ? { ...exact, initialSubRegion: prevTrip.initialSubRegion }
              : exact;
          }
          if (Array.isArray(prevTrip.shoot_dates) && prevTrip.shoot_dates.length > 0) {
            const byDate = loadedTrips.find(
              (t) =>
                Array.isArray(t.shoot_dates) &&
                t.shoot_dates.some((d) => prevTrip.shoot_dates.includes(d))
            );
            if (byDate) return byDate;
          }
          return prevTrip;
        });
        setIsTripsLoading(false);
      })
      .catch((err) => {
        console.error('Error loading trips:', err);
        setIsTripsLoading(false);
      });
  }, [activeCatalog, hideUnsharp]);

  useEffect(() => {
    fetchTrips();
  }, [fetchTrips]);

  const gridActiveTripId = viewMode !== 'trips' ? activeTrip?.trip_id || null : null;
  const gridActiveTripDates =
    viewMode !== 'trips' && Array.isArray(activeTrip?.shoot_dates)
      ? activeTrip.shoot_dates.join(',')
      : '';

  // Main photos query function
  const fetchPhotos = useCallback(
    (targetPage = 1, append = false) => {
      setIsLoading(true);
      const startTime = performance.now();

      const params = new URLSearchParams();
      if (activeCatalog) params.set('catalog', activeCatalog);
      if (searchQuery && searchQuery.trim()) params.set('query', searchQuery.trim());
      if (activePortfolioTheme) params.set('portfolio_theme', activePortfolioTheme);
      if (aestheticPercentile) params.set('aesthetic_percentile', aestheticPercentile);
      if (sortBy) params.set('sort_by', sortBy);
      if (minStars) params.set('min_stars', minStars);
      if (hideUnsharp) params.set('hide_unsharp', 'true');
      if (gridActiveTripId) {
        params.set('trip_id', gridActiveTripId);
        if (gridActiveTripDates) {
          params.set('shoot_dates', gridActiveTripDates);
        }
      } else if (activeShootDate && viewMode !== 'trips') {
        params.set('shoot_date', activeShootDate);
      }
      params.set('collapse_strafing', collapseStrafing ? 'true' : 'false');
      params.set('page', String(targetPage));
      params.set('limit', String(PAGE_SIZE));

      fetch(`/api/photos?${params.toString()}`)
        .then((res) => {
          if (!res.ok) throw new Error('Query failed');
          return res.json();
        })
        .then((data) => {
          const elapsed = Math.round(performance.now() - startTime);
          setSearchLatencyMs(elapsed);

          const newPhotos = data.photos || [];
          setTotalPhotos(data.total || 0);
          setAestheticCutoff(data.aesthetic_cutoff || 0);
          setPage(targetPage);
          setHasMore(targetPage * PAGE_SIZE < (data.total || 0));

          if (append) {
            setPhotos((prev) => {
              const seen = new Set(prev.map(getPhotoKey));
              const deduped = newPhotos.filter((p) => !seen.has(getPhotoKey(p)));
              const combined = [...prev, ...deduped];
              if (viewMode !== 'trips') {
                setActiveLightboxList((prevList) =>
                  prevList.length > 0 ? [...prevList, ...deduped] : combined
                );
              }
              return combined;
            });
          } else {
            setPhotos(newPhotos);
          }
          setIsLoading(false);
        })
        .catch((err) => {
          console.error('Error querying photos:', err);
          setIsLoading(false);
        });
    },
    [
      activeCatalog,
      searchQuery,
      activePortfolioTheme,
      aestheticPercentile,
      sortBy,
      minStars,
      hideUnsharp,
      collapseStrafing,
      gridActiveTripId,
      gridActiveTripDates,
      activeShootDate,
      viewMode,
    ]
  );

  const handleTripPhotosUpdated = useCallback((updatedTripPhotos) => {
    if (Array.isArray(updatedTripPhotos) && updatedTripPhotos.length > 0) {
      setActiveLightboxList(updatedTripPhotos);
    }
  }, []);

  // Trigger search on filter changes
  useEffect(() => {
    fetchPhotos(1, false);
  }, [fetchPhotos]);

  // Load more / pagination
  const handleLoadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      fetchPhotos(page + 1, true);
    }
  }, [isLoading, hasMore, page, fetchPhotos]);

  // Open Lightbox with explicit context list so Left/Right works across Grid, By Date, Trips, Sequences & Similar
  const handleOpenLightbox = useCallback(
    (photo, customList = null) => {
      if (!photo) {
        setActiveLightboxPhoto(null);
        return;
      }
      const targetKey = getPhotoKey(photo);
      if (Array.isArray(customList) && customList.length > 0) {
        // If customList is a sub-strip (e.g. Similar/Neighbors) and the photo is already in our active list, keep the larger active list
        setActiveLightboxList((prevList) => {
          if (
            prevList.length > customList.length &&
            prevList.some((p) => getPhotoKey(p) === targetKey)
          ) {
            return prevList;
          }
          return customList;
        });
      } else {
        setActiveLightboxList((prevList) => {
          if (prevList.length > 0 && prevList.some((p) => getPhotoKey(p) === targetKey)) {
            return prevList;
          }
          if (photos.some((p) => getPhotoKey(p) === targetKey)) {
            return photos;
          }
          return [photo, ...photos];
        });
      }
      setActiveLightboxPhoto(photo);
    },
    [photos]
  );

  // Instant star rating override
  const handleUpdateStar = useCallback((photo, newStars) => {
    const pId = photo.file_hash || encodeURIComponent(photo.file_path);
    const key = getPhotoKey(photo);
    // Optimistically update in-place immediately so UI feels instantaneous
    const patchItem = (item) =>
      getPhotoKey(item) === key ? { ...item, star_rating: newStars } : item;
    setPhotos((prev) => prev.map(patchItem));
    setActiveLightboxList((prev) => prev.map(patchItem));
    setActiveLightboxPhoto((prev) =>
      prev && getPhotoKey(prev) === key ? { ...prev, star_rating: newStars } : prev
    );
    setSelectedPhotoMap((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Map(prev);
      next.set(key, { ...next.get(key), star_rating: newStars });
      return next;
    });

    fetch(`/api/photo/${pId}/star`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ star_rating: newStars }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data?.undo_status) {
          applyUndoStatusPayload(data.undo_status);
        } else {
          fetchUndoStatus();
        }
      })
      .catch((err) => {
        console.error('Failed to update star:', err);
        fetchUndoStatus();
      });
  }, [applyUndoStatusPayload, fetchUndoStatus]);

  // Lightbox previous/next navigation across activeLightboxList
  const handleNavigateLightbox = useCallback(
    (direction) => {
      const list =
        activeLightboxList && activeLightboxList.length > 0
          ? activeLightboxList
          : photos;
      if (!activeLightboxPhoto || list.length === 0) return;

      const activeKey = getPhotoKey(activeLightboxPhoto);
      let currentIndex = list.findIndex((p) => getPhotoKey(p) === activeKey);
      if (currentIndex === -1) {
        currentIndex = 0;
      }

      const nextIndex = (currentIndex + direction + list.length) % list.length;
      setActiveLightboxPhoto(list[nextIndex]);

      // Prefetch next page if approaching end of main grid list
      if (
        direction > 0 &&
        viewMode !== 'trips' &&
        nextIndex >= list.length - 6 &&
        hasMore &&
        !isLoading
      ) {
        handleLoadMore();
      }
    },
    [activeLightboxList, photos, activeLightboxPhoto, viewMode, hasMore, isLoading, handleLoadMore]
  );

  // Clickable tag pill filter from any card or Lightbox
  const handleTagClick = useCallback(
    (tag) => {
      if (!tag) return;
      const cleanTag = String(tag).trim();
      if (!cleanTag) return;
      setSearchQuery(cleanTag);
      setActiveShootDate(null);
      setActiveLightboxPhoto(null);
      if (viewMode === 'trips') {
        setActiveTrip(null);
        setViewMode('grid');
      }
      showGlobalToast(`Filtering archive by tag: "${cleanTag}"`);
    },
    [viewMode]
  );

  // Jump from Lightbox "On This Day" directly to main studio Grid filtered to that shoot_date
  const handleOpenFullDayInGrid = useCallback((shootDate) => {
    if (!shootDate) return;
    setActiveLightboxPhoto(null);
    setActiveTrip(null);
    setSearchQuery('');
    setViewMode('grid');
    setActiveShootDate(shootDate);
    showGlobalToast(`Viewing all captures from shoot day: ${shootDate}`);
  }, []);

  // Toggle a photo in/out of a curated collection or book
  const handleTogglePhotoInCollection = useCallback(
    async (collectionId, photo, isCurrentlyMember) => {
      const pid = photo?.file_hash || photo?.file_path;
      if (!collectionId || !pid) return;
      try {
        if (isCurrentlyMember) {
          await fetch(
            `/api/collections/${collectionId}/items/${encodeURIComponent(pid)}`,
            { method: 'DELETE' }
          );
          showGlobalToast('Removed photo from collection');
        } else {
          await fetch(`/api/collections/${collectionId}/items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ photo_id: pid }),
          });
          showGlobalToast('Added photo to collection');
        }
        loadCollections();
        fetchUndoStatus();
      } catch (err) {
        showGlobalToast(`Collection update failed: ${err.message}`);
      }
    },
    [loadCollections, fetchUndoStatus]
  );

  // Create a new collection and immediately add the selected photo
  const handleCreateCollectionWithPhoto = useCallback(
    async (name, photo, description) => {
      const pid = photo?.file_hash || photo?.file_path;
      try {
        const res = await fetch('/api/collections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            description: description || 'Fine-Art Book / Portfolio Selection',
            photo_id: pid || null,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Create failed');
        showGlobalToast(
          pid ? `Created "${name}" and added photo` : `Created collection "${name}"`
        );
        loadCollections();
      } catch (err) {
        showGlobalToast(`Failed to create collection: ${err.message}`);
      }
    },
    [loadCollections]
  );

  // Multi-photo selection with Shift+Click range support across Grid, By Date, and Trips
  const handleToggleSelectPhoto = useCallback(
    (photo, event, contextList = null) => {
      if (!photo) return;
      const targetKey = getPhotoKey(photo);
      const list = Array.isArray(contextList) && contextList.length > 0 ? contextList : photos;

      setSelectedPhotoMap((prev) => {
        const next = new Map(prev);
        if (event?.shiftKey && lastSelectedKey && list.length > 0) {
          const idxA = list.findIndex((p) => getPhotoKey(p) === lastSelectedKey);
          const idxB = list.findIndex((p) => getPhotoKey(p) === targetKey);
          if (idxA !== -1 && idxB !== -1) {
            const start = Math.min(idxA, idxB);
            const end = Math.max(idxA, idxB);
            for (let i = start; i <= end; i += 1) {
              const item = list[i];
              if (item) {
                next.set(getPhotoKey(item), item);
              }
            }
            return next;
          }
        }

        if (next.has(targetKey)) {
          next.delete(targetKey);
        } else {
          next.set(targetKey, photo);
        }
        return next;
      });
      setLastSelectedKey(targetKey);
    },
    [lastSelectedKey, photos]
  );

  const handleClearSelection = useCallback(() => {
    setSelectedPhotoMap(new Map());
    setLastSelectedKey(null);
  }, []);

  // Select all currently loaded photos on the page
  const handleSelectAllLoaded = useCallback(() => {
    setSelectedPhotoMap((prev) => {
      const next = new Map(prev);
      for (const p of photos) {
        next.set(getPhotoKey(p), p);
      }
      return next;
    });
    showGlobalToast(`✓ Selected ${photos.length.toLocaleString()} loaded photo(s)`);
  }, [photos]);

  // Select ALL matching photos across the entire active catalog/filter (even if paginated beyond PAGE_SIZE)
  const handleSelectAllInCatalog = useCallback(async () => {
    if (totalPhotos <= photos.length && photos.length > 0) {
      handleSelectAllLoaded();
      return;
    }
    setIsSelectingAll(true);
    try {
      const params = new URLSearchParams();
      if (activeCatalog) params.set('catalog', activeCatalog);
      if (searchQuery && searchQuery.trim()) params.set('query', searchQuery.trim());
      if (activePortfolioTheme) params.set('portfolio_theme', activePortfolioTheme);
      if (aestheticPercentile) params.set('aesthetic_percentile', aestheticPercentile);
      if (sortBy) params.set('sort_by', sortBy);
      if (minStars) params.set('min_stars', minStars);
      if (hideUnsharp) params.set('hide_unsharp', 'true');
      if (gridActiveTripId) {
        params.set('trip_id', gridActiveTripId);
        if (gridActiveTripDates) {
          params.set('shoot_dates', gridActiveTripDates);
        }
      } else if (activeShootDate && viewMode !== 'trips') {
        params.set('shoot_date', activeShootDate);
      }
      params.set('collapse_strafing', collapseStrafing ? 'true' : 'false');
      params.set('ids_only', 'true');
      params.set('page', '1');
      params.set('limit', '25000');

      const res = await fetch(`/api/photos?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch all matching photo IDs');
      const data = await res.json();
      const stubs = data.photos || [];
      const loadedMap = new Map(photos.map((p) => [getPhotoKey(p), p]));
      const next = new Map();
      for (const stub of stubs) {
        const k = getPhotoKey(stub);
        if (k) {
          next.set(k, loadedMap.get(k) || stub);
        }
      }
      setSelectedPhotoMap(next);
      showGlobalToast(`✓ Selected all ${next.size.toLocaleString()} photo(s) in current view`);
    } catch (err) {
      showGlobalToast(`Select All failed: ${err.message}`);
    } finally {
      setIsSelectingAll(false);
    }
  }, [
    totalPhotos,
    photos,
    handleSelectAllLoaded,
    activeCatalog,
    searchQuery,
    activePortfolioTheme,
    aestheticPercentile,
    sortBy,
    minStars,
    hideUnsharp,
    gridActiveTripId,
    gridActiveTripDates,
    activeShootDate,
    viewMode,
    collapseStrafing,
  ]);

  // Batch Clear Tags (Pure-vision Clean-Slate Wipe across all selected photos with single-step Undo)
  const handleBatchClearTags = useCallback(async () => {
    if (selectedPhotosArray.length === 0) return;
    const photoIds = selectedPhotosArray.map((p) => p.file_hash || p.file_path);
    setIsBatchBusy(true);
    showGlobalToast(`🧹 Clearing AI tags on ${photoIds.length.toLocaleString()} selected photo(s)...`);
    try {
      const res = await fetch('/api/ai/teach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          photo_ids: photoIds,
          instruction: '',
          mode: 'instant',
          wipe_existing: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      const updatedList = Array.isArray(data.photos) ? data.photos : [];
      if (updatedList.length > 0 && photoIds.length <= 500) {
        const updatedMap = new Map(updatedList.map((p) => [getPhotoKey(p), p]));
        setPhotos((prev) => prev.map((item) => updatedMap.get(getPhotoKey(item)) || item));
        setActiveLightboxList((prev) => prev.map((item) => updatedMap.get(getPhotoKey(item)) || item));
        setSelectedPhotoMap((prev) => {
          const next = new Map(prev);
          for (const [k, v] of updatedMap.entries()) {
            if (next.has(k)) next.set(k, v);
          }
          return next;
        });
      } else {
        fetchPhotos(1, false);
      }
      if (data.undo_status) {
        applyUndoStatusPayload(data.undo_status);
      } else {
        fetchUndoStatus();
      }
      showGlobalToast(`🧹 Cleared tags on ${photoIds.length.toLocaleString()} photo(s) (Cmd+Z to Undo)`);
    } catch (err) {
      showGlobalToast(`Batch Clear Tags failed: ${err.message}`);
    } finally {
      setIsBatchBusy(false);
    }
  }, [selectedPhotosArray, fetchPhotos, fetchUndoStatus, applyUndoStatusPayload]);

  // Batch add selected photos to an existing collection
  const handleBatchAddToCollection = useCallback(
    async (collectionId) => {
      if (!collectionId || selectedPhotosArray.length === 0) return;
      const photoIds = selectedPhotosArray.map((p) => p.file_hash || p.file_path);
      try {
        const res = await fetch(`/api/collections/${collectionId}/items`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ photo_ids: photoIds }),
        });
        if (res.ok) {
          showGlobalToast(`Added ${photoIds.length} selected photo(s) to collection`);
          loadCollections();
        }
      } catch (err) {
        showGlobalToast(`Batch add failed: ${err.message}`);
      }
    },
    [selectedPhotosArray, loadCollections]
  );

  // Batch create a new collection with all selected photos
  const handleBatchCreateCollectionWithSelected = useCallback(
    async (name) => {
      if (!name || selectedPhotosArray.length === 0) return;
      const photoIds = selectedPhotosArray.map((p) => p.file_hash || p.file_path);
      try {
        const res = await fetch('/api/collections', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            description: `Curated selection (${photoIds.length} plates)`,
            photo_ids: photoIds,
          }),
        });
        const data = await res.json();
        if (res.ok) {
          showGlobalToast(`Created "${name}" with ${photoIds.length} photo(s)`);
          loadCollections();
          setCollectionsInitialId(data.id);
          setCollectionsInitialMode('sequence');
          setIsCollectionsModalOpen(true);
        }
      } catch (err) {
        showGlobalToast(`Failed to create collection: ${err.message}`);
      }
    },
    [selectedPhotosArray, loadCollections]
  );

  // Batch Re-Assess selected photos (Pure-Vision Basic Tag or Deep VLM)
  const handleBatchReassessSelected = useCallback(
    async (mode = 'fast_vectors') => {
      if (selectedPhotosArray.length === 0) return;
      const photoIds = selectedPhotosArray.map((p) => p.file_hash || p.file_path);
      const isAsync = photoIds.length > 10 || (mode === 'deep_vlm' && photoIds.length > 1);
      setIsBatchBusy(true);
      showGlobalToast(
        mode === 'deep_vlm'
          ? `🧠 Running pure-vision Deep VLM on ${photoIds.length.toLocaleString()} photo(s)...`
          : `⚡ Running pure-vision Basic Tag on ${photoIds.length.toLocaleString()} photo(s)...`
      );
      try {
        const res = await fetch('/api/reassess', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            photo_ids: photoIds,
            mode,
            async_job: isAsync,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
        if (data.status === 'started') {
          refreshJobStatus();
          if (data.undo_status) {
            applyUndoStatusPayload(data.undo_status);
          } else {
            fetchUndoStatus();
          }
        } else if (data.photos) {
          const updatedMap = new Map(data.photos.map((p) => [getPhotoKey(p), p]));
          setPhotos((prev) =>
            prev.map((item) => updatedMap.get(getPhotoKey(item)) || item)
          );
          setActiveLightboxList((prev) =>
            prev.map((item) => updatedMap.get(getPhotoKey(item)) || item)
          );
          setSelectedPhotoMap((prev) => {
            const next = new Map(prev);
            for (const [k, v] of updatedMap.entries()) {
              if (next.has(k)) next.set(k, v);
            }
            return next;
          });
          if (data.undo_status) {
            applyUndoStatusPayload(data.undo_status);
          } else {
            fetchUndoStatus();
          }
          showGlobalToast(
            `${mode === 'deep_vlm' ? '🧠 Deep VLM' : '⚡ Basic Tag'} updated ${(
              data.reassessed_count || data.photos.length
            ).toLocaleString()} photo(s) (Cmd+Z to Undo)`
          );
        }
      } catch (err) {
        showGlobalToast(`Batch reassessment failed: ${err.message}`);
      } finally {
        setIsBatchBusy(false);
      }
    },
    [selectedPhotosArray, refreshJobStatus, fetchUndoStatus, applyUndoStatusPayload]
  );

  // Open Voice Teach / Scout Modal
  const handleOpenVoiceModal = useCallback(
    (initialMode = 'teach', overridePhotos = null, autoStart = false) => {
      setVoiceOverridePhotos(overridePhotos);
      const effectivePhotos = overridePhotos || selectedPhotosArray;
      const resolvedMode =
        initialMode === 'teach' && (!effectivePhotos || effectivePhotos.length === 0)
          ? 'scout'
          : initialMode;
      setVoiceModalMode(resolvedMode);
      setVoiceAutoStart(Boolean(autoStart));
      setIsVoiceModalOpen(true);
    },
    [selectedPhotosArray]
  );

  // Callback when AI Teach overrides are applied
  const handleTeachApplied = useCallback(
    (data) => {
      const updatedPhotos = data?.photos || [];
      if (updatedPhotos.length > 0) {
        const updatedByKey = new Map(updatedPhotos.map((p) => [getPhotoKey(p), p]));
        setPhotos((prev) =>
          prev.map((item) => updatedByKey.get(getPhotoKey(item)) || item)
        );
        setActiveLightboxList((prev) =>
          prev.map((item) => updatedByKey.get(getPhotoKey(item)) || item)
        );
        setActiveLightboxPhoto((prev) =>
          prev && updatedByKey.has(getPhotoKey(prev))
            ? updatedByKey.get(getPhotoKey(prev))
            : prev
        );
        setSelectedPhotoMap((prev) => {
          const next = new Map(prev);
          for (const [k, v] of updatedByKey.entries()) {
            if (next.has(k)) next.set(k, v);
          }
          return next;
        });
      }
      if (viewMode === 'trips') {
        fetchTrips();
      }
      if (data?.undo_status) {
        applyUndoStatusPayload(data.undo_status);
      } else {
        fetchUndoStatus();
      }
      showGlobalToast(
        `Applied permanent AI Teach overrides to ${data?.updated_count || updatedPhotos.length} photo(s)`
      );
    },
    [viewMode, fetchTrips, fetchUndoStatus, applyUndoStatusPayload]
  );

  // Callback when AI Archive Scout builds a story collection
  const handleScoutCompleted = useCallback(
    (scoutData, action) => {
      loadCollections();
      refreshJobStatus();
      if (scoutData?.undo_status) {
        applyUndoStatusPayload(scoutData.undo_status);
      } else {
        fetchUndoStatus();
      }
      if (!action || !scoutData) return;

      if (action === 'open_book' && scoutData.collection_id) {
        setIsVoiceModalOpen(false);
        setCollectionsInitialId(scoutData.collection_id);
        setCollectionsInitialMode('book');
        setIsCollectionsModalOpen(true);
      } else if (action === 'open_collection' && scoutData.collection_id) {
        setIsVoiceModalOpen(false);
        setCollectionsInitialId(scoutData.collection_id);
        setCollectionsInitialMode('sequence');
        setIsCollectionsModalOpen(true);
      } else if (action === 'open_grid' && Array.isArray(scoutData.photos)) {
        setIsVoiceModalOpen(false);
        setActiveLightboxPhoto(null);
        setActiveTrip(null);
        setActiveShootDate(null);
        setViewMode('grid');
        setPhotos(scoutData.photos);
        setTotalPhotos(scoutData.photos.length);
        setHasMore(false);
        showGlobalToast(
          `Showing ${scoutData.photos.length} AI Scouted frames for "${scoutData.collection_name}"`
        );
      }
    },
    [loadCollections, refreshJobStatus, fetchUndoStatus]
  );

  // 1-Click Undo (POST /api/undo) & Cmd+Z / Ctrl+Z handler
  const handleTriggerUndo = useCallback(async () => {
    try {
      const res = await fetch('/api/undo', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) {
        showGlobalToast(data.detail || 'Nothing to undo');
        fetchUndoStatus();
        return;
      }
      const restoredPhotos = Array.isArray(data.restored_photos) ? data.restored_photos : [];
      if (restoredPhotos.length > 0) {
        const restoredMap = new Map(restoredPhotos.map((p) => [getPhotoKey(p), p]));
        setPhotos((prev) =>
          prev.map((item) => restoredMap.get(getPhotoKey(item)) || item)
        );
        setActiveLightboxList((prev) =>
          prev.map((item) => restoredMap.get(getPhotoKey(item)) || item)
        );
        setActiveLightboxPhoto((prev) =>
          prev && restoredMap.has(getPhotoKey(prev))
            ? restoredMap.get(getPhotoKey(prev))
            : prev
        );
        setSelectedPhotoMap((prev) => {
          const next = new Map(prev);
          for (const [k, v] of restoredMap.entries()) {
            if (next.has(k)) next.set(k, v);
          }
          return next;
        });
      } else {
        fetchPhotos(1, false);
      }
      loadCollections();
      if (viewMode === 'trips') {
        fetchTrips();
      }
      if (data.undo_status) {
        applyUndoStatusPayload(data.undo_status);
      } else {
        fetchUndoStatus();
      }
      showGlobalToast(
        `↩ Undid: ${data.description || data.action_type || 'Last Action'} (${
          data.restored_photo_count || restoredPhotos.length
        } photo(s) restored)`
      );
    } catch (err) {
      showGlobalToast(`Undo failed: ${err.message}`);
    }
  }, [fetchPhotos, fetchTrips, fetchUndoStatus, loadCollections, viewMode]);

  // Global Cmd+Z / Ctrl+Z and 'G' (Jump to Main Grid) shortcuts when focus is not inside an input/textarea
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = document.activeElement?.tagName;
      if (
        tag === 'INPUT' ||
        tag === 'TEXTAREA' ||
        tag === 'SELECT' ||
        document.activeElement?.isContentEditable
      ) {
        return;
      }

      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key?.toLowerCase() === 'z') {
        if (undoStatus?.available) {
          e.preventDefault();
          handleTriggerUndo();
        }
        return;
      }

      if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key?.toLowerCase() === 'a') {
        if (!activeLightboxPhoto && !isVoiceModalOpen && !isCollectionsModalOpen && !isPipelineModalOpen) {
          e.preventDefault();
          if (selectedPhotosArray.length >= photos.length && totalPhotos > photos.length) {
            handleSelectAllInCatalog();
          } else {
            handleSelectAllLoaded();
          }
        }
        return;
      }

      if (!e.metaKey && !e.ctrlKey && !e.altKey && e.key?.toLowerCase() === 'g') {
        e.preventDefault();
        setActiveLightboxPhoto(null);
        setIsCollectionsModalOpen(false);
        setIsVoiceModalOpen(false);
        setActiveSequenceId(null);
        setViewMode('grid');
        showGlobalToast('⊞ Switched to Main Grid View');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    undoStatus?.available,
    handleTriggerUndo,
    activeLightboxPhoto,
    isVoiceModalOpen,
    isCollectionsModalOpen,
    isPipelineModalOpen,
    selectedPhotosArray.length,
    photos.length,
    totalPhotos,
    handleSelectAllInCatalog,
    handleSelectAllLoaded,
  ]);

  // Global Sync External Edits (Photoshop / Lightroom mtime + size check)
  const handleSyncExternalEdits = useCallback(async () => {
    showGlobalToast('Scanning catalog for external Photoshop / Lightroom edits...');
    try {
      const res = await fetch('/api/sync-edits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ re_run_vlm: false }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Sync failed');
      const count = data.changed_count || 0;
      if (count > 0) {
        showGlobalToast(`Synced ${count} modified photo(s)! Previews & embeddings updated.`);
        fetchPhotos(1, false);
        if (viewMode === 'trips') fetchTrips();
      } else {
        showGlobalToast(`Checked ${data.checked || 0} files — all previews up to date.`);
      }
    } catch (err) {
      showGlobalToast(`Sync error: ${err.message}`);
    }
  }, [fetchPhotos, fetchTrips, viewMode]);

  // Trigger DAS Backup
  const handleTriggerBackup = () => {
    showGlobalToast('Starting DAS catalog backup...');
    fetch('/api/backup', { method: 'POST' })
      .then((res) => res.json())
      .then(() => {
        showGlobalToast('Backup to DAS completed successfully!');
      })
      .catch((err) => {
        showGlobalToast(`Backup error: ${err.message}`);
      });
  };

  // Compute current index & total for Lightbox badge
  const currentLightboxList =
    activeLightboxList && activeLightboxList.length > 0 ? activeLightboxList : photos;
  const activeLightboxIndex = activeLightboxPhoto
    ? currentLightboxList.findIndex(
        (p) => getPhotoKey(p) === getPhotoKey(activeLightboxPhoto)
      )
    : -1;

  const visibleJobStatus =
    jobStatus &&
    (jobStatus.running ||
      (jobStatus.finished_at && jobStatus.job_id !== dismissedJobId))
      ? { ...jobStatus, _keepVisible: true }
      : null;

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-studio-bg select-none">
      {/* Top Studio Control Ribbon */}
      <TopRibbon
        catalogs={catalogs}
        activeCatalog={activeCatalog}
        onSelectCatalog={(cat) => {
          setActiveCatalog(cat);
          setActiveTrip(null);
          setActiveShootDate(null);
          setSelectedPhotoMap(new Map());
          setPage(1);
          window.scrollTo({ top: 0, behavior: 'instant' });
        }}
        viewMode={viewMode}
        onViewModeChange={(mode) => setViewMode(mode)}
        onSelectViewMode={(mode) => setViewMode(mode)}
        searchQuery={searchQuery}
        onSearchChange={(q) => {
          setSearchQuery(q);
          if (q && viewMode === 'trips') {
            setViewMode('grid');
          }
        }}
        aestheticPercentile={aestheticPercentile}
        onSelectPercentile={(p) => setAestheticPercentile(p)}
        sortBy={sortBy}
        onSelectSortBy={(s) => setSortBy(s)}
        minStars={minStars}
        onToggleStars={() => setMinStars((prev) => (prev === 4 ? null : 4))}
        hideUnsharp={hideUnsharp}
        onToggleHideUnsharp={() => setHideUnsharp((prev) => !prev)}
        collapseStrafing={collapseStrafing}
        onToggleCollapseStrafing={() => setCollapseStrafing((prev) => !prev)}
        totalPhotos={totalPhotos}
        aestheticCutoff={aestheticCutoff}
        searchLatencyMs={searchLatencyMs}
        onOpenPipelineModal={(tab) => {
          setPipelineInitialTab(typeof tab === 'string' ? tab : 'pipeline');
          setIsPipelineModalOpen(true);
        }}
        onOpenCollectionsModal={() => {
          setCollectionsInitialMode('sequence');
          setIsCollectionsModalOpen(true);
        }}
        onOpenVoiceTeachScout={() =>
          handleOpenVoiceModal(selectedPhotosArray.length > 0 ? 'teach' : 'scout', null, false)
        }
        collectionsCount={collections.length}
        activePortfolioTheme={activePortfolioTheme}
        onSelectPortfolioTheme={(theme) => {
          setActivePortfolioTheme(theme);
          setActiveShootDate(null);
          if (viewMode === 'trips') {
            if (theme) {
              const matchedTheme = portfolioThemes.find(
                (pt) => pt.portfolio_category === theme
              );
              if (matchedTheme) {
                setActiveTrip(matchedTheme);
              } else {
                setViewMode('grid');
              }
            } else {
              setActiveTrip(null);
            }
          }
        }}
        onSyncExternalEdits={handleSyncExternalEdits}
        onTriggerBackup={handleTriggerBackup}
        undoStatus={undoStatus}
        onTriggerUndo={handleTriggerUndo}
        selectedCount={selectedPhotosArray.length}
        isSelectingAll={isSelectingAll}
        onSelectAllInView={handleSelectAllInCatalog}
        onClearSelection={handleClearSelection}
        onRefresh={() => {
          fetchPhotos(1, false);
          loadCollections();
          fetchTrips();
          fetchUndoStatus();
        }}
      />

      {/* Main Content View: Continuous Grid, By Date, or Trips & Geo-Map */}
      {viewMode === 'trips' ? (
        <TripsMapView
          trips={trips}
          portfolioThemes={portfolioThemes}
          isLoading={isTripsLoading}
          activeTrip={activeTrip}
          onSelectTrip={(trip) => {
            setActiveTrip(trip);
          }}
          onClearTrip={() => {
            setActiveTrip(null);
            setActivePortfolioTheme(null);
          }}
          onSelectPhoto={handleOpenLightbox}
          onOpenSequence={(seqId) => setActiveSequenceId(seqId)}
          onUpdateStar={handleUpdateStar}
          onTagClick={handleTagClick}
          onRefreshTrips={fetchTrips}
          onTripPhotosUpdated={handleTripPhotosUpdated}
          activeCatalog={activeCatalog}
          sortBy={sortBy}
          aestheticPercentile={aestheticPercentile}
          minStars={minStars}
          hideUnsharp={hideUnsharp}
          collections={collections}
          onTogglePhotoInCollection={handleTogglePhotoInCollection}
          onCreateCollectionWithPhoto={handleCreateCollectionWithPhoto}
          selectedPhotoIds={selectedPhotoIds}
          onToggleSelectPhoto={handleToggleSelectPhoto}
        />
      ) : (
        <PhotoGrid
          photos={photos}
          isLoading={isLoading}
          viewMode={viewMode}
          activeTrip={activeTrip}
          onClearTrip={() => setActiveTrip(null)}
          activeShootDate={activeShootDate}
          onClearShootDate={() => setActiveShootDate(null)}
          onSelectPhoto={handleOpenLightbox}
          onOpenSequence={(seqId) => setActiveSequenceId(seqId)}
          onUpdateStar={handleUpdateStar}
          onTagClick={handleTagClick}
          collections={collections}
          onTogglePhotoInCollection={handleTogglePhotoInCollection}
          onCreateCollectionWithPhoto={handleCreateCollectionWithPhoto}
          onOpenCollectionsModal={() => setIsCollectionsModalOpen(true)}
          onLoadMore={handleLoadMore}
          hasMore={hasMore}
          selectedPhotoIds={selectedPhotoIds}
          onToggleSelectPhoto={handleToggleSelectPhoto}
        />
      )}

      {/* Floating Multi-Photo Selection Action Bar */}
      <SelectionActionBar
        selectedCount={selectedPhotosArray.length}
        totalVisibleCount={photos.length}
        totalCatalogCount={totalPhotos}
        isSelectingAll={isSelectingAll}
        isBatchBusy={isBatchBusy}
        onSelectAll={handleSelectAllLoaded}
        onSelectAllInCatalog={handleSelectAllInCatalog}
        onClearSelection={handleClearSelection}
        onBatchClearTags={handleBatchClearTags}
        onBatchReassess={handleBatchReassessSelected}
        onOpenVoiceTeach={() => handleOpenVoiceModal('teach', null, true)}
        onOpenVoiceScout={() => handleOpenVoiceModal('scout', null, false)}
        onOpenTeachModal={() => handleOpenVoiceModal('teach', null, true)}
        onOpenScoutModal={() => handleOpenVoiceModal('scout', null, false)}
        collections={collections}
        onBatchAddToCollection={handleBatchAddToCollection}
        onCreateCollectionWithSelected={handleBatchCreateCollectionWithSelected}
        onBatchCreateCollection={handleBatchCreateCollectionWithSelected}
      />

      {/* Voice / Text AI Teach & Archive Scout Modal */}
      <ModalErrorBoundary
        onClose={() => {
          setIsVoiceModalOpen(false);
          setVoiceOverridePhotos(null);
          setVoiceAutoStart(false);
        }}
      >
        <VoiceTeachScoutModal
          isOpen={isVoiceModalOpen}
          onClose={() => {
            setIsVoiceModalOpen(false);
            setVoiceOverridePhotos(null);
            setVoiceAutoStart(false);
          }}
          selectedPhotos={voiceOverridePhotos || selectedPhotosArray}
          initialMode={voiceModalMode}
          autoStartRecording={voiceAutoStart}
          onClearAutoStart={() => setVoiceAutoStart(false)}
          onPhotosUpdated={(updatedList) => {
            handleTeachApplied({ photos: updatedList, updated_count: updatedList?.length || 0 });
            loadCollections();
          }}
          onOpenCollection={(collectionId, targetMode = 'sequence') => {
            loadCollections();
            setCollectionsInitialId(collectionId);
            setCollectionsInitialMode(targetMode === 'book' ? 'book' : 'sequence');
            setIsCollectionsModalOpen(true);
          }}
          onViewPhotosInGrid={(matchedPhotos, label) => {
            loadCollections();
            if (Array.isArray(matchedPhotos) && matchedPhotos.length > 0) {
              setActiveLightboxPhoto(null);
              setActiveTrip(null);
              setActiveShootDate(null);
              setViewMode('grid');
              setPhotos(matchedPhotos);
              setTotalPhotos(matchedPhotos.length);
              setHasMore(false);
              showGlobalToast(label || `Showing ${matchedPhotos.length} AI Scouted frames`);
            }
          }}
          onTeachApplied={handleTeachApplied}
          onScoutCompleted={handleScoutCompleted}
          onTriggerUndo={handleTriggerUndo}
        />
      </ModalErrorBoundary>

      {/* Non-Blocking Live Progress Dock (Export, Deep AI Re-Assess, Scout, Ingest) */}
      <LiveProgressDock
        jobStatus={visibleJobStatus}
        job={visibleJobStatus}
        onPause={handlePauseJob}
        onResume={handleResumeJob}
        onCancel={handleCancelJob}
        onDismiss={() => {
          if (jobStatus?.job_id) {
            setDismissedJobId(jobStatus.job_id);
          } else {
            setJobStatus(null);
          }
        }}
        onOpenFullPipelineModal={() => setIsPipelineModalOpen(true)}
      />

      {/* Inspection Lightbox Modal */}
      {activeLightboxPhoto && (
        <ModalErrorBoundary onClose={() => setActiveLightboxPhoto(null)}>
          <LightboxModal
            photo={activeLightboxPhoto}
            activeIndex={activeLightboxIndex >= 0 ? activeLightboxIndex : 0}
            totalCount={currentLightboxList.length}
            onClose={() => setActiveLightboxPhoto(null)}
            onNavigatePrev={() => handleNavigateLightbox(-1)}
            onNavigateNext={() => handleNavigateLightbox(1)}
            onUpdateStar={handleUpdateStar}
            onSelectPhoto={handleOpenLightbox}
            onTagClick={handleTagClick}
            onOpenFullDayInGrid={handleOpenFullDayInGrid}
            collections={collections}
            onTogglePhotoInCollection={handleTogglePhotoInCollection}
            onCreateCollectionWithPhoto={handleCreateCollectionWithPhoto}
            onOpenCollectionsModal={() => setIsCollectionsModalOpen(true)}
            onOpenVoiceTeachForPhoto={(targetPhoto, autoStart = true) =>
              handleOpenVoiceModal('teach', [targetPhoto], autoStart)
            }
            undoStatus={undoStatus}
            onTriggerUndo={handleTriggerUndo}
            onUndoStatusChange={applyUndoStatusPayload}
            onPhotoUpdated={(updatedPhoto) => {
              const key = getPhotoKey(updatedPhoto);
              setPhotos((prev) =>
                prev.map((item) => (getPhotoKey(item) === key ? updatedPhoto : item))
              );
              setActiveLightboxList((prev) =>
                prev.map((item) => (getPhotoKey(item) === key ? updatedPhoto : item))
              );
              setActiveLightboxPhoto(updatedPhoto);
              if (viewMode === 'trips') {
                fetchTrips();
              }
            }}
          />
        </ModalErrorBoundary>
      )}

      {/* Curated Collections & Book Mode Modal */}
      <ModalErrorBoundary onClose={() => setIsCollectionsModalOpen(false)}>
        <CollectionsModal
          isOpen={isCollectionsModalOpen}
          onClose={() => setIsCollectionsModalOpen(false)}
          collections={collections}
          initialCollectionId={collectionsInitialId}
          initialMode={collectionsInitialMode}
          onRefreshCollections={loadCollections}
          onSelectPhoto={handleOpenLightbox}
          onShowToast={showGlobalToast}
          jobStatus={jobStatus}
          onPauseJob={handlePauseJob}
          onResumeJob={handleResumeJob}
          onCancelJob={handleCancelJob}
          onJobStarted={refreshJobStatus}
        />
      </ModalErrorBoundary>

      {/* Strafing Run / Sequence Expansion Drawer */}
      {activeSequenceId && (
        <SequenceDrawer
          sequenceId={activeSequenceId}
          onClose={() => setActiveSequenceId(null)}
          onSelectPhoto={handleOpenLightbox}
        />
      )}

      {/* Pipeline Management Modal */}
      <ModalErrorBoundary onClose={() => setIsPipelineModalOpen(false)}>
        <PipelineModal
          isOpen={isPipelineModalOpen}
          onClose={() => setIsPipelineModalOpen(false)}
          catalogs={catalogs}
          activeCatalog={activeCatalog}
          initialTab={pipelineInitialTab}
          onSelectCatalog={(cat) => {
            setActiveCatalog(cat);
            setActiveTrip(null);
            setActiveShootDate(null);
          }}
          onShowToast={showGlobalToast}
          onRefreshCatalogs={() => {
            loadCatalogs();
            fetchPhotos(1, false);
            if (viewMode === 'trips') fetchTrips();
            refreshJobStatus();
          }}
        />
      </ModalErrorBoundary>

      {/* Global Studio Toast */}
      {globalToast && (
        <div className="fixed bottom-6 right-6 bg-studio-panel border border-studio-borderLight text-white px-3.5 py-2 rounded-sm shadow-2xl text-xs font-mono z-50 flex items-center gap-2">
          <span className="w-2 h-2 rounded-sm bg-studio-accent animate-ping"></span>
          <span>{globalToast}</span>
        </div>
      )}
    </div>
  );
}

