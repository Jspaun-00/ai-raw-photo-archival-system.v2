import React, { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { Calendar, Camera, Compass, ArrowRight, ArrowLeft, Search, X, RefreshCw, Zap, Cpu } from 'lucide-react';
import PhotoCard from './PhotoCard.jsx';

/**
 * Clean, Fast, Photographer-Friendly Trips Gallery View
 * Groups coherent 1–2 day shoots into visual Trip Cards with Hero cover image,
 * 3-thumbnail preview strip, capture date / 1–2 day date range, photo count,
 * camera model(s), and dominant shared subject/location tags.
 * Clicking a Trip opens the Trip Photo Grid directly inside TripsMapView
 * with a "← Back to All Trips" button and a "🔄 Re-Assess Trip" tool.
 */
export default function TripsMapView({
  trips,
  portfolioThemes = [],
  loading,
  isLoading,
  activeTrip,
  onSelectTrip,
  onClearTrip,
  onSelectPhoto,
  onOpenSequence,
  onUpdateStar,
  onTagClick,
  onRefreshTrips,
  onTripPhotosUpdated,
  collections = [],
  onTogglePhotoInCollection,
  onCreateCollectionWithPhoto,
  activeCatalog = 'All Catalogs',
  sortBy = 'capture_desc',
  aestheticPercentile = 'all',
  minStars = null,
  hideUnsharp = false,
  selectedPhotoIds = new Set(),
  onToggleSelectPhoto,
}) {
  const isBusy = loading || isLoading;
  const [selectedYear, setSelectedYear] = useState('ALL');
  const [filterText, setFilterText] = useState('');
  const [sectionMode, setSectionMode] = useState('both'); // 'both' | 'portfolio' | 'expeditions'
  const [activeSubRegion, setActiveSubRegion] = useState(null);

  // State for active Trip drill-down photo grid & spot re-assessment
  const [tripPhotos, setTripPhotos] = useState([]);
  const [loadingTripPhotos, setLoadingTripPhotos] = useState(false);
  const [reassessingTrip, setReassessingTrip] = useState(false);
  const [reassessMenuOpen, setReassessMenuOpen] = useState(false);
  const [tripBanner, setTripBanner] = useState(null);

  // Windowed progressive rendering for 50,000-photo scale
  const DRILLDOWN_BATCH_SIZE = 60;
  const EXPEDITION_BATCH_SIZE = 24;
  const [visibleDrilldownCount, setVisibleDrilldownCount] = useState(DRILLDOWN_BATCH_SIZE);
  const [visibleExpeditionCount, setVisibleExpeditionCount] = useState(EXPEDITION_BATCH_SIZE);
  const drilldownSentinelRef = useRef(null);
  const expeditionSentinelRef = useRef(null);

  // Keep parent callback in a ref so parent re-renders never re-trigger the fetch useEffect
  const onTripPhotosUpdatedRef = useRef(onTripPhotosUpdated);
  useEffect(() => {
    onTripPhotosUpdatedRef.current = onTripPhotosUpdated;
  }, [onTripPhotosUpdated]);

  // Primitive identifiers only (never depend on unstable object/array/callback references)
  const activeTripId = activeTrip?.trip_id ? String(activeTrip.trip_id) : '';
  const activeTripPortfolioCat = activeTrip?.portfolio_category
    ? String(activeTrip.portfolio_category)
    : activeTrip?.category
    ? String(activeTrip.category)
    : '';
  const activeTripInitialSubRegion = activeTrip?.initialSubRegion || null;

  const loadTripPhotos = useCallback(
    (abortSignal = null) => {
      if (!activeTripId) {
        setTripPhotos([]);
        setLoadingTripPhotos(false);
        return;
      }
      setLoadingTripPhotos(true);
      const params = new URLSearchParams();
      if (activeCatalog) params.set('catalog', activeCatalog);
      params.set('trip_id', activeTripId);
      if (activeTripPortfolioCat) {
        params.set('portfolio_theme', activeTripPortfolioCat);
      }
      if (selectedYear && selectedYear !== 'ALL') {
        params.set('year', selectedYear);
      }
      if (sortBy) params.set('sort_by', sortBy);
      if (aestheticPercentile) params.set('aesthetic_percentile', aestheticPercentile);
      if (minStars) params.set('min_stars', String(minStars));
      if (hideUnsharp) params.set('hide_unsharp', 'true');
      params.set('collapse_strafing', 'false');
      params.set('limit', '5000');

      fetch(`/api/photos?${params.toString()}`, abortSignal ? { signal: abortSignal } : undefined)
        .then((res) => {
          if (!res.ok) throw new Error('Failed to load trip photos');
          return res.json();
        })
        .then((data) => {
          const loaded = Array.isArray(data?.photos) ? data.photos : [];
          setTripPhotos(loaded);
          setLoadingTripPhotos(false);
          if (onTripPhotosUpdatedRef.current && loaded.length > 0) {
            onTripPhotosUpdatedRef.current(loaded);
          }
        })
        .catch((err) => {
          if (err?.name === 'AbortError') return;
          setLoadingTripPhotos(false);
        });
    },
    [
      activeTripId,
      activeTripPortfolioCat,
      selectedYear,
      activeCatalog,
      sortBy,
      aestheticPercentile,
      minStars,
      hideUnsharp,
    ]
  );

  // Reset sub-region selection only when switching to a different Trip/Region ID or explicit initialSubRegion
  useEffect(() => {
    if (activeTripId) {
      setActiveSubRegion(activeTripInitialSubRegion || null);
    } else {
      setActiveSubRegion(null);
    }
  }, [activeTripId, activeTripInitialSubRegion]);

  // Fetch frames once per selected Trip/Region ID (or filter change)
  useEffect(() => {
    if (!activeTripId) {
      setTripPhotos([]);
      setLoadingTripPhotos(false);
      return undefined;
    }
    const controller = new AbortController();
    loadTripPhotos(controller.signal);
    return () => {
      controller.abort();
    };
  }, [activeTripId, loadTripPhotos]);

  const handleReassessTrip = (mode) => {
    if (!activeTrip || reassessingTrip) return;
    setReassessMenuOpen(false);
    setReassessingTrip(true);
    setTripBanner(
      mode === 'deep_vlm'
        ? 'Running Deep AI Re-Tag (qwen2.5vl:7b + perspective guide) on this trip...'
        : 'Running Fast Vector & Ontology Recalibration (<1s)...'
    );

    fetch('/api/reassess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trip_id: activeTrip.trip_id,
        mode,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setReassessingTrip(false);
        if (data.photos && data.photos.length > 0) {
          setTripPhotos(data.photos);
          if (onTripPhotosUpdated) onTripPhotosUpdated(data.photos);
        } else {
          loadTripPhotos();
        }
        if (onRefreshTrips) onRefreshTrips();
        setTripBanner(
          `Re-assessed ${data.reassessed_count || 0} frames in ${data.elapsed_seconds || 0}s · Enriched ${
            data.ontology_enriched || 0
          } records (${data.centroids_indexed || 0} cross-catalog centroids)`
        );
        setTimeout(() => setTripBanner(null), 5000);
      })
      .catch((err) => {
        setReassessingTrip(false);
        setTripBanner(`Re-assess error: ${err.message}`);
      });
  };

  const handleLocalStarUpdate = (photo, newStars) => {
    setTripPhotos((prev) =>
      prev.map((item) =>
        item.file_path === photo.file_path ? { ...item, star_rating: newStars } : item
      )
    );
    if (onUpdateStar) onUpdateStar(photo, newStars);
  };

  const sortCardsByOrder = useCallback(
    (cards) => {
      if (!Array.isArray(cards) || cards.length === 0) return [];
      const mode = (sortBy || 'capture_desc').toLowerCase();
      const copy = [...cards];
      copy.sort((a, b) => {
        if (mode === 'capture_asc') {
          const sa = String(a.start_date || '9999-99-99');
          const sb = String(b.start_date || '9999-99-99');
          if (sa !== sb) return sa.localeCompare(sb);
          return (b.photo_count || 0) - (a.photo_count || 0);
        }
        if (mode === 'aesthetic_desc') {
          const diff =
            Number(b.max_aesthetic_score ?? b.avg_aesthetic_score ?? 0) -
            Number(a.max_aesthetic_score ?? a.avg_aesthetic_score ?? 0);
          if (Math.abs(diff) > 0.001) return diff;
          return (b.photo_count || 0) - (a.photo_count || 0);
        }
        if (mode === 'stars_desc') {
          const starDiff =
            Number(b.max_star_rating ?? 0) - Number(a.max_star_rating ?? 0);
          if (starDiff !== 0) return starDiff;
          const keeperDiff = Number(b.keeper_count ?? 0) - Number(a.keeper_count ?? 0);
          if (keeperDiff !== 0) return keeperDiff;
          return (
            Number(b.max_aesthetic_score ?? 0) - Number(a.max_aesthetic_score ?? 0)
          );
        }
        if (mode === 'sharpness_desc') {
          const diff =
            Number(b.max_sharpness_score ?? 0) - Number(a.max_sharpness_score ?? 0);
          if (Math.abs(diff) > 0.001) return diff;
          return (b.photo_count || 0) - (a.photo_count || 0);
        }
        if (mode === 'filename_asc') {
          const na = String(a.portfolio_category || a.trip_name || '');
          const nb = String(b.portfolio_category || b.trip_name || '');
          return na.localeCompare(nb);
        }
        // Default: capture_desc (Newest first)
        const ea = String(a.end_date || a.start_date || '');
        const eb = String(b.end_date || b.start_date || '');
        if (eb !== ea) return eb.localeCompare(ea);
        return (b.photo_count || 0) - (a.photo_count || 0);
      });
      return copy;
    },
    [sortBy]
  );

  // Compute Year pills dynamically across Portfolio Regions and Expeditions
  const years = useMemo(() => {
    const yrCounts = {};
    if (sectionMode === 'portfolio') {
      (portfolioThemes || []).forEach((pt) => {
        const yc = pt.year_counts || {};
        Object.entries(yc).forEach(([yr, cnt]) => {
          if (/^\d{4}$/.test(yr) && cnt > 0) {
            yrCounts[yr] = (yrCounts[yr] || 0) + 1;
          }
        });
      });
    } else {
      (trips || []).forEach((t) => {
        const tYears = Array.isArray(t.years) && t.years.length > 0
          ? t.years
          : [(t.start_date || '').slice(0, 4)].filter((y) => /^\d{4}$/.test(y));
        tYears.forEach((yr) => {
          yrCounts[yr] = (yrCounts[yr] || 0) + 1;
        });
      });
      if (sectionMode === 'both') {
        (portfolioThemes || []).forEach((pt) => {
          (pt.years || []).forEach((yr) => {
            if (/^\d{4}$/.test(yr) && !yrCounts[yr]) {
              yrCounts[yr] = 1;
            }
          });
        });
      }
    }
    return Object.entries(yrCounts).sort((a, b) => b[0].localeCompare(a[0]));
  }, [trips, portfolioThemes, sectionMode]);

  const visiblePortfolioThemes = useMemo(() => {
    if (!portfolioThemes) return [];
    const mapped = [];
    for (const pt of portfolioThemes) {
      let item = pt;
      if (selectedYear !== 'ALL') {
        const yrSlice = pt.year_breakdown?.[selectedYear];
        const yrCount = pt.year_counts?.[selectedYear] || yrSlice?.photo_count || 0;
        const matchesDates =
          Array.isArray(pt.shoot_dates) &&
          pt.shoot_dates.some((d) => String(d).startsWith(selectedYear));
        if (!yrCount && !matchesDates) {
          continue;
        }
        if (yrSlice) {
          item = {
            ...pt,
            ...yrSlice,
            date_range_label: `${selectedYear} (${yrSlice.photo_count} frames)`,
          };
        }
      }
      if (filterText.trim()) {
        const q = filterText.trim().toLowerCase();
        const hay = [
          item.portfolio_category,
          item.trip_name,
          item.description,
          item.location_name,
          ...(item.top_subjects || []),
          ...((item.sub_regions || []).map((sr) => sr.name)),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) continue;
      }
      mapped.push(item);
    }
    return sortCardsByOrder(mapped);
  }, [portfolioThemes, selectedYear, filterText, sortCardsByOrder]);

  const visibleTrips = useMemo(() => {
    if (!trips) return [];
    const filtered = trips.filter((t) => {
      if (selectedYear !== 'ALL') {
        const matchesYearList = Array.isArray(t.years) && t.years.includes(selectedYear);
        const matchesStart = (t.start_date || '').startsWith(selectedYear);
        const matchesEnd = (t.end_date || '').startsWith(selectedYear);
        const matchesDates =
          Array.isArray(t.shoot_dates) &&
          t.shoot_dates.some((d) => String(d).startsWith(selectedYear));
        if (!matchesYearList && !matchesStart && !matchesEnd && !matchesDates) {
          return false;
        }
      }
      if (filterText.trim()) {
        const q = filterText.trim().toLowerCase();
        const hay = [
          t.trip_name,
          t.date_range_label,
          t.location_name,
          ...(t.cameras || []),
          ...(t.top_subjects || []),
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    return sortCardsByOrder(filtered);
  }, [trips, selectedYear, filterText, sortCardsByOrder]);

  const totalTripPhotos = useMemo(
    () => visibleTrips.reduce((acc, t) => acc + (t.photo_count || 0), 0),
    [visibleTrips]
  );

  const filteredDrilldownPhotos = useMemo(() => {
    if (!activeSubRegion) return tripPhotos;
    const needle = activeSubRegion.toLowerCase();
    return tripPhotos.filter((p) => {
      const hay = [
        p.location_name,
        p.vlm_caption,
        ...(Array.isArray(p.key_subjects) ? p.key_subjects : []),
        ...(Array.isArray(p.hierarchical_keywords) ? p.hierarchical_keywords : []),
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [tripPhotos, activeSubRegion]);

  // Reset progressive render windows when switching trip/sub-region or filtering expeditions
  useEffect(() => {
    setVisibleDrilldownCount(DRILLDOWN_BATCH_SIZE);
  }, [activeTripId, activeSubRegion]);

  useEffect(() => {
    setVisibleExpeditionCount(EXPEDITION_BATCH_SIZE);
  }, [selectedYear, filterText, sectionMode]);

  // IntersectionObserver for progressive drill-down photo loading (60 frames per batch)
  useEffect(() => {
    if (!activeTripId || loadingTripPhotos) return undefined;
    if (visibleDrilldownCount >= filteredDrilldownPhotos.length) return undefined;
    const node = drilldownSentinelRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleDrilldownCount((prev) =>
            Math.min(prev + DRILLDOWN_BATCH_SIZE, filteredDrilldownPhotos.length)
          );
        }
      },
      { rootMargin: '450px' }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [activeTripId, loadingTripPhotos, visibleDrilldownCount, filteredDrilldownPhotos.length]);

  // IntersectionObserver for progressive expedition cards loading (24 cards per batch)
  useEffect(() => {
    if (activeTripId || isBusy) return undefined;
    if (visibleExpeditionCount >= visibleTrips.length) return undefined;
    const node = expeditionSentinelRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleExpeditionCount((prev) =>
            Math.min(prev + EXPEDITION_BATCH_SIZE, visibleTrips.length)
          );
        }
      },
      { rootMargin: '450px' }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [activeTripId, isBusy, visibleExpeditionCount, visibleTrips.length]);

  const windowedDrilldownPhotos = useMemo(
    () => filteredDrilldownPhotos.slice(0, visibleDrilldownCount),
    [filteredDrilldownPhotos, visibleDrilldownCount]
  );

  const windowedVisibleTrips = useMemo(
    () => visibleTrips.slice(0, visibleExpeditionCount),
    [visibleTrips, visibleExpeditionCount]
  );

  // ============================================================================
  // DRILL-DOWN VIEW: ACTIVE TRIP OR PORTFOLIO REGION PHOTO GRID
  // ============================================================================
  if (activeTrip) {
    const cameraLabel = (activeTrip.cameras || []).join(' / ');
    const subRegions = Array.isArray(activeTrip.sub_regions) ? activeTrip.sub_regions : [];
    const isPortfolioTheme = Boolean(activeTrip.is_portfolio_theme);

    return (
      <div className="flex-1 overflow-y-auto p-6 w-full bg-studio-bg">
        <div className="max-w-[1800px] mx-auto space-y-5">
          {/* Trip / Portfolio Region Drill-Down Header Bar */}
          <div className="bg-studio-panel border border-amber-500/40 rounded-lg p-4 flex flex-col gap-3 shadow-lg">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onClearTrip && onClearTrip()}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-studio-bg hover:bg-amber-500 hover:text-zinc-950 text-amber-400 border border-amber-500/40 text-xs font-mono font-semibold transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>← Back to All Regions &amp; Trips</span>
                </button>

                <div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <h2 className="text-base font-bold text-white font-mono flex items-center gap-2">
                      {activeTrip.icon && <span>{activeTrip.icon}</span>}
                      <span>{activeTrip.trip_name}</span>
                    </h2>
                    {isPortfolioTheme && (
                      <span className="px-2.5 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/40 text-xs font-mono text-amber-300 font-semibold">
                        10,000-Foot Portfolio Region
                      </span>
                    )}
                    <span className="px-2.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-700 text-xs font-mono text-amber-300 flex items-center gap-1.5">
                      <Calendar className="w-3 h-3" />
                      {activeTrip.date_range_label}
                    </span>
                    <span className="px-2.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-700 text-xs font-mono text-zinc-200">
                      {filteredDrilldownPhotos.length || activeTrip.photo_count} frames
                    </span>
                    {cameraLabel && (
                      <span className="px-2.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-700 text-xs font-mono text-zinc-300 flex items-center gap-1">
                        <Camera className="w-3 h-3 text-amber-400" />
                        {cameraLabel}
                      </span>
                    )}
                  </div>

                  {activeTrip.description && (
                    <p className="text-xs text-studio-textMuted mt-1">
                      {activeTrip.description}
                    </p>
                  )}

                  {/* Year Quick Filter Pills inside Portfolio Region Drill-Down */}
                  {isPortfolioTheme && Array.isArray(activeTrip.years) && activeTrip.years.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap mt-2">
                      <span className="text-[10px] font-mono text-studio-textDim uppercase mr-1">
                        Year Filter:
                      </span>
                      <button
                        type="button"
                        onClick={() => setSelectedYear('ALL')}
                        className={`text-[11px] font-mono px-2.5 py-0.5 rounded transition-colors ${
                          selectedYear === 'ALL'
                            ? 'bg-amber-500 text-zinc-950 font-bold'
                            : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700'
                        }`}
                      >
                        All Years
                      </button>
                      {activeTrip.years.map((yr) => {
                        const yrCnt = activeTrip.year_counts?.[yr];
                        const isYrActive = selectedYear === yr;
                        return (
                          <button
                            type="button"
                            key={yr}
                            onClick={() => setSelectedYear(isYrActive ? 'ALL' : yr)}
                            className={`text-[11px] font-mono px-2.5 py-0.5 rounded transition-colors ${
                              isYrActive
                                ? 'bg-amber-500 text-zinc-950 font-bold'
                                : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700'
                            }`}
                          >
                            {yr}
                            {yrCnt ? ` (${yrCnt})` : ''}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Sub-Region Quick Filter Pills for Portfolio Regions */}
                  {subRegions.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap mt-2">
                      <span className="text-[10px] font-mono text-studio-textDim uppercase mr-1">
                        Sub-Regions &amp; Landmarks:
                      </span>
                      <button
                        type="button"
                        onClick={() => setActiveSubRegion(null)}
                        className={`text-[11px] font-mono px-2.5 py-0.5 rounded transition-colors ${
                          !activeSubRegion
                            ? 'bg-amber-500 text-zinc-950 font-bold'
                            : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700'
                        }`}
                      >
                        All ({tripPhotos.length || activeTrip.photo_count})
                      </button>
                      {subRegions.map((sr) => {
                        const isSubActive = activeSubRegion === sr.name;
                        return (
                          <button
                            type="button"
                            key={sr.name}
                            onClick={() =>
                              setActiveSubRegion(isSubActive ? null : sr.name)
                            }
                            className={`text-[11px] font-mono px-2.5 py-0.5 rounded transition-colors ${
                              isSubActive
                                ? 'bg-amber-500 text-zinc-950 font-bold'
                                : 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700'
                            }`}
                          >
                            {sr.name} ({sr.count})
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Shared Trip Subject Tags */}
                  {!isPortfolioTheme && (activeTrip.top_subjects || []).length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap mt-1.5">
                      <span className="text-[10px] font-mono text-studio-textDim uppercase">Shared Tags:</span>
                      {(activeTrip.top_subjects || []).map((subj, idx) => (
                        <button
                          type="button"
                          key={idx}
                          onClick={() => onTagClick && onTagClick(subj)}
                          className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 hover:bg-amber-500/20 text-zinc-200 hover:text-amber-300 border border-zinc-700 transition-colors"
                        >
                          {subj}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Spot Re-Assess Trip Dropdown Button */}
              {!isPortfolioTheme && (
                <div className="relative">
                  <button
                    onClick={() => setReassessMenuOpen((prev) => !prev)}
                    disabled={reassessingTrip}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-studio-bg hover:bg-studio-hover border border-studio-borderLight text-amber-300 hover:text-white text-xs font-mono transition-colors disabled:opacity-50"
                    title="Re-assess and sync learned tags for this trip"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${reassessingTrip ? 'animate-spin' : ''}`} />
                    <span>{reassessingTrip ? 'Re-Assessing Trip...' : '🔄 Re-Assess Trip'}</span>
                  </button>

                  {reassessMenuOpen && (
                    <div className="absolute right-0 mt-1.5 w-72 bg-studio-panel border border-studio-borderLight rounded-md shadow-2xl z-40 p-1.5 font-mono text-xs space-y-1">
                      <button
                        onClick={() => handleReassessTrip('fast_vectors')}
                        className="w-full text-left px-2.5 py-2 rounded hover:bg-studio-hover flex items-start gap-2 transition-colors"
                      >
                        <Zap className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-white font-semibold">⚡ Fast Recalibrate (&lt;1s)</div>
                          <div className="text-[10px] text-studio-textDim leading-snug">
                            Applies cross-catalog learned centroids, perspective gate &amp; multi-tier ontology
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={() => handleReassessTrip('deep_vlm')}
                        className="w-full text-left px-2.5 py-2 rounded hover:bg-studio-hover flex items-start gap-2 transition-colors"
                      >
                        <Cpu className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-white font-semibold">🧠 Deep AI Re-Tag (~3s/photo)</div>
                          <div className="text-[10px] text-studio-textDim leading-snug">
                            Re-runs Qwen2.5-VL with Aerial vs. Terrestrial guide doc &amp; neighbor hints
                          </div>
                        </div>
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>

            {tripBanner && (
              <div className="px-3 py-1.5 rounded bg-amber-500/15 border border-amber-500/40 text-amber-300 text-xs font-mono">
                {tripBanner}
              </div>
            )}
          </div>

          {/* Trip Photos Grid (Windowed Progressive Rendering for 50k+ Scale) */}
          {loadingTripPhotos ? (
            <div className="py-16 flex flex-col items-center justify-center text-zinc-400 gap-3 font-mono">
              <div className="w-7 h-7 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-xs">Loading frames...</span>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
                {windowedDrilldownPhotos.map((photo) => {
                  const pKey = photo.file_hash || photo.file_path;
                  return (
                    <PhotoCard
                      key={photo.file_hash || photo.file_path}
                      photo={photo}
                      onClick={() => onSelectPhoto && onSelectPhoto(photo, filteredDrilldownPhotos)}
                      onOpenSequence={onOpenSequence}
                      onUpdateStar={handleLocalStarUpdate}
                      onTagClick={onTagClick}
                      collections={collections}
                      onTogglePhotoInCollection={onTogglePhotoInCollection}
                      onCreateCollectionWithPhoto={onCreateCollectionWithPhoto}
                      isSelected={selectedPhotoIds?.has(pKey)}
                      onToggleSelect={(clickedPhoto, event) =>
                        onToggleSelectPhoto &&
                        onToggleSelectPhoto(clickedPhoto, event, filteredDrilldownPhotos)
                      }
                    />
                  );
                })}
              </div>

              {visibleDrilldownCount < filteredDrilldownPhotos.length && (
                <div
                  ref={drilldownSentinelRef}
                  className="py-6 flex flex-col items-center justify-center gap-2 font-mono"
                >
                  <button
                    type="button"
                    onClick={() =>
                      setVisibleDrilldownCount((prev) =>
                        Math.min(prev + DRILLDOWN_BATCH_SIZE, filteredDrilldownPhotos.length)
                      )
                    }
                    className="px-4 py-2 rounded-md bg-studio-panel hover:bg-studio-hover border border-amber-500/40 text-amber-300 text-xs font-semibold transition-colors"
                  >
                    Showing {windowedDrilldownPhotos.length} of {filteredDrilldownPhotos.length} frames — Load Next {Math.min(DRILLDOWN_BATCH_SIZE, filteredDrilldownPhotos.length - visibleDrilldownCount)}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  if (isBusy) {
    return (
      <div className="flex-1 overflow-y-auto p-12 flex flex-col items-center justify-center text-zinc-400 gap-3 font-mono">
        <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-sm font-medium">Organizing 10,000-Foot Portfolio Regions &amp; Multi-Day Expeditions...</p>
      </div>
    );
  }

  const showPortfolioSection =
    (sectionMode === 'both' || sectionMode === 'portfolio') &&
    visiblePortfolioThemes.length > 0;
  const showExpeditionsSection =
    sectionMode === 'both' || sectionMode === 'expeditions';

  return (
    <div className="flex-1 overflow-y-auto p-6 w-full bg-studio-bg">
      <div className="max-w-[1800px] mx-auto space-y-6">
        {/* Top Gallery Header & Section Toggle / Year / Quick Filter Bar */}
        <div className="bg-studio-panel border border-studio-border rounded-lg p-4 flex flex-col gap-3 shadow-lg">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-md bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Compass className="w-4 h-4" />
              </div>
              <div>
                <h2 className="text-sm font-semibold text-zinc-100 flex items-center gap-2.5 font-mono flex-wrap">
                  <span>10,000-Foot Portfolio Regions &amp; Multi-Day Expeditions</span>
                  <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-zinc-800 text-amber-400 border border-zinc-700">
                    {visiblePortfolioThemes.length} Portfolio Regions · {visibleTrips.length}{' '}
                    {visibleTrips.length === 1 ? 'Expedition' : 'Expeditions'} ({totalTripPhotos} Frames)
                  </span>
                </h2>
                <p className="text-xs text-studio-textMuted mt-0.5">
                  Browse by 10,000-foot thematic regions across all years or explore consolidated multi-day expeditions
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {/* Segmented View Toggle: Both vs Portfolio Regions vs Chronological Expeditions */}
              <div className="flex items-center bg-studio-bg p-1 rounded-md border border-studio-border font-mono text-xs">
                <button
                  type="button"
                  onClick={() => setSectionMode('both')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    sectionMode === 'both'
                      ? 'bg-amber-500 text-zinc-950 font-bold'
                      : 'text-studio-textMuted hover:text-white'
                  }`}
                >
                  All View
                </button>
                <button
                  type="button"
                  onClick={() => setSectionMode('portfolio')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    sectionMode === 'portfolio'
                      ? 'bg-amber-500 text-zinc-950 font-bold'
                      : 'text-studio-textMuted hover:text-white'
                  }`}
                >
                  🏔️ Portfolio Regions ({visiblePortfolioThemes.length})
                </button>
                <button
                  type="button"
                  onClick={() => setSectionMode('expeditions')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    sectionMode === 'expeditions'
                      ? 'bg-amber-500 text-zinc-950 font-bold'
                      : 'text-studio-textMuted hover:text-white'
                  }`}
                >
                  🧭 Expeditions ({visibleTrips.length})
                </button>
              </div>

              {/* Quick Filter Input */}
              <div className="relative w-64">
                <Search className="w-3.5 h-3.5 text-studio-textDim absolute left-2.5 top-2 pointer-events-none" />
                <input
                  type="text"
                  value={filterText}
                  onChange={(e) => setFilterText(e.target.value)}
                  onKeyDown={(e) => e.stopPropagation()}
                  placeholder="Filter regions, landmarks, dates..."
                  className="w-full bg-studio-bg border border-studio-border focus:border-amber-500 focus:outline-none pl-8 pr-7 py-1 text-xs text-studio-text placeholder-studio-textDim rounded-sm font-mono select-text"
                />
                {filterText && (
                  <button
                    onClick={() => setFilterText('')}
                    className="absolute right-2 top-2 text-studio-textDim hover:text-white"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Year Pills for All Sub-Views (All View, Portfolio Regions, and Expeditions) */}
          {years.length > 0 && (
            <div className="pt-2 border-t border-studio-border/60 flex items-center gap-1.5 overflow-x-auto scrollbar-none">
              <span className="text-[11px] font-mono text-studio-textDim mr-1 shrink-0">
                {sectionMode === 'portfolio' ? 'Filter Region Year:' : 'Filter Year:'}
              </span>
              <button
                type="button"
                onClick={() => setSelectedYear('ALL')}
                className={`px-2.5 py-0.5 rounded-sm text-[11px] font-mono transition shrink-0 ${
                  selectedYear === 'ALL'
                    ? 'bg-amber-500 text-zinc-950 font-semibold'
                    : 'bg-studio-bg text-studio-textMuted hover:text-white border border-studio-border'
                }`}
              >
                All Years (
                {sectionMode === 'portfolio'
                  ? portfolioThemes?.length || 0
                  : trips?.length || 0}
                )
              </button>
              {years.map(([yr, cnt]) => (
                <button
                  type="button"
                  key={yr}
                  onClick={() => setSelectedYear(yr === selectedYear ? 'ALL' : yr)}
                  className={`px-2.5 py-0.5 rounded-sm text-[11px] font-mono transition shrink-0 ${
                    selectedYear === yr
                      ? 'bg-amber-500 text-zinc-950 font-semibold'
                      : 'bg-studio-bg text-studio-textMuted hover:text-white border border-studio-border'
                  }`}
                >
                  {yr} ({cnt})
                </button>
              ))}
            </div>
          )}
        </div>

        {/* =====================================================================
            SECTION 1: 10,000-FOOT PORTFOLIO REGIONS & THEMES
            ===================================================================== */}
        {showPortfolioSection && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-amber-400 font-mono uppercase tracking-wider">
                  🏔️ 10,000-Foot Portfolio Regions &amp; Themes
                </span>
                <span className="text-xs font-mono text-studio-textMuted">
                  — Cross-year thematic &amp; geographic collections with instant sub-region drill-down
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {visiblePortfolioThemes.map((pt) => {
                const extraThumbs = (pt.sample_thumbs || []).slice(1, 4);
                const subRegions = Array.isArray(pt.sub_regions) ? pt.sub_regions : [];

                return (
                  <div
                    key={pt.trip_id}
                    onClick={() => onSelectTrip(pt)}
                    className="group bg-zinc-900/95 hover:bg-zinc-900 border border-amber-500/30 hover:border-amber-400 rounded-xl overflow-hidden cursor-pointer transition-all duration-200 shadow-lg hover:shadow-amber-500/15 flex flex-col"
                  >
                    {/* Hero Cover Photo */}
                    <div className="relative h-48 w-full bg-zinc-950 overflow-hidden">
                      {pt.hero_photo?.thumb_url ? (
                        <img
                          src={pt.hero_photo.thumb_url}
                          alt={pt.trip_name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-zinc-600">
                          <Camera className="w-8 h-8" />
                        </div>
                      )}

                      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/35 to-transparent" />

                      {/* Top Badges: Portfolio Theme Pill + Frame & Keeper Count */}
                      <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between gap-2">
                        <span className="px-2.5 py-1 rounded-md bg-zinc-950/90 backdrop-blur-md border border-amber-500/50 text-[11px] font-mono font-semibold text-amber-300 flex items-center gap-1.5">
                          <span>{pt.icon || '🏔️'}</span>
                          <span>Portfolio Region</span>
                        </span>
                        <div className="flex items-center gap-1.5">
                          {pt.keeper_count > 0 && (
                            <span className="px-2 py-1 rounded-md bg-zinc-950/90 backdrop-blur-md border border-amber-500/40 text-[11px] font-mono font-semibold text-amber-400">
                              ★ {pt.keeper_count}
                            </span>
                          )}
                          <span className="px-2.5 py-1 rounded-md bg-zinc-950/90 backdrop-blur-md border border-zinc-700/80 text-[11px] font-mono font-semibold text-zinc-100">
                            {pt.photo_count} frames
                          </span>
                        </div>
                      </div>

                      {/* Bottom Title + Description */}
                      <div className="absolute bottom-2.5 left-3 right-3">
                        <h4 className="text-base font-bold text-white leading-snug line-clamp-1 group-hover:text-amber-300 transition flex items-center gap-1.5">
                          <span>{pt.icon}</span>
                          <span>{pt.portfolio_category || pt.trip_name}</span>
                        </h4>
                        <p className="text-[11px] text-zinc-300 line-clamp-1 mt-0.5">
                          {pt.description}
                        </p>
                      </div>
                    </div>

                    {/* 3-Thumbnail Strip + Clickable Sub-Region Pills */}
                    <div className="p-3 flex-1 flex flex-col justify-between gap-2.5">
                      {extraThumbs.length > 0 && (
                        <div className="grid grid-cols-3 gap-1.5">
                          {extraThumbs.map((tUrl, i) => (
                            <img
                              key={i}
                              src={tUrl}
                              alt=""
                              className="h-12 w-full object-cover rounded border border-zinc-800"
                              loading="lazy"
                            />
                          ))}
                        </div>
                      )}

                      <div className="flex items-center justify-between gap-2 pt-1 border-t border-zinc-800/80">
                        <div className="flex flex-wrap gap-1 min-w-0">
                          {subRegions.slice(0, 4).map((sr) => (
                            <button
                              type="button"
                              key={sr.name}
                              onClick={(e) => {
                                e.stopPropagation();
                                onSelectTrip({
                                  ...pt,
                                  initialSubRegion: sr.name,
                                });
                              }}
                              title={`Open ${pt.portfolio_category} filtered to ${sr.name} (${sr.count} photos)`}
                              className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 hover:bg-amber-500 hover:text-zinc-950 text-zinc-200 border border-zinc-700 transition-colors truncate max-w-[140px]"
                            >
                              {sr.name} ({sr.count})
                            </button>
                          ))}
                        </div>
                        <span className="text-xs font-mono font-semibold text-amber-400 group-hover:translate-x-0.5 transition-transform flex items-center gap-1 shrink-0">
                          Explore <ArrowRight className="w-3.5 h-3.5" />
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* =====================================================================
            SECTION 2: CONSOLIDATED MULTI-DAY EXPEDITIONS & TRIPS
            ===================================================================== */}
        {showExpeditionsSection && (
          <div className="space-y-3">
            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-zinc-100 font-mono uppercase tracking-wider">
                  🧭 Chronological Expeditions &amp; Multi-Day Trips ({visibleTrips.length})
                </span>
                <span className="text-xs font-mono text-studio-textMuted">
                  — Multi-day regional expeditions consolidated up to 14 days
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
              {windowedVisibleTrips.map((trip) => {
                const extraThumbs = (trip.sample_thumbs || []).slice(1, 4);
                const cameraLabel = (trip.cameras || []).slice(0, 2).join(' / ');

                return (
                  <div
                    key={trip.trip_id}
                    onClick={() => onSelectTrip(trip)}
                    className="group bg-zinc-900/90 hover:bg-zinc-900 border border-zinc-800 hover:border-amber-500/60 rounded-xl overflow-hidden cursor-pointer transition-all duration-200 shadow-lg hover:shadow-amber-500/10 flex flex-col"
                  >
                    {/* Hero Cover Photo */}
                    <div className="relative h-48 w-full bg-zinc-950 overflow-hidden">
                      {trip.hero_photo?.thumb_url ? (
                        <img
                          src={trip.hero_photo.thumb_url}
                          alt={trip.trip_name}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-zinc-600">
                          <Camera className="w-8 h-8" />
                        </div>
                      )}

                      <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/25 to-transparent" />

                      {/* Top Badges: Capture Date Range + Frame Count */}
                      <div className="absolute top-2.5 left-2.5 right-2.5 flex items-center justify-between gap-2">
                        <span className="px-2.5 py-1 rounded-md bg-zinc-950/85 backdrop-blur-md border border-zinc-700/80 text-[11px] font-mono font-medium text-amber-300 flex items-center gap-1.5">
                          <Calendar className="w-3 h-3" />
                          {trip.date_range_label}
                        </span>
                        <span className="px-2.5 py-1 rounded-md bg-zinc-950/85 backdrop-blur-md border border-zinc-700/80 text-[11px] font-mono font-semibold text-zinc-100">
                          {trip.photo_count} {trip.photo_count === 1 ? 'frame' : 'frames'}
                        </span>
                      </div>

                      {/* Bottom Title + Camera Model Overlay */}
                      <div className="absolute bottom-2.5 left-3 right-3">
                        <h4 className="text-sm font-bold text-white leading-snug line-clamp-1 group-hover:text-amber-300 transition">
                          {trip.trip_name}
                        </h4>
                        <div className="flex items-center justify-between gap-2 text-[11px] font-mono text-zinc-300 mt-0.5">
                          {cameraLabel ? (
                            <span className="flex items-center gap-1 truncate text-zinc-300">
                              <Camera className="w-3 h-3 text-amber-400 shrink-0" />
                              <span className="truncate">{cameraLabel}</span>
                            </span>
                          ) : (
                            <span className="text-zinc-400 truncate">{trip.location_name}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* 3-Thumbnail Preview Strip + Shared Subject/Location Tags */}
                    <div className="p-3 flex-1 flex flex-col justify-between gap-2.5">
                      {extraThumbs.length > 0 && (
                        <div className="grid grid-cols-3 gap-1.5">
                          {extraThumbs.map((tUrl, i) => (
                            <img
                              key={i}
                              src={tUrl}
                              alt=""
                              className="h-12 w-full object-cover rounded border border-zinc-800"
                              loading="lazy"
                            />
                          ))}
                        </div>
                      )}

                      <div className="flex items-center justify-between gap-2 pt-1 border-t border-zinc-800/80">
                        <div className="flex flex-wrap gap-1 min-w-0">
                          {(trip.top_subjects || []).slice(0, 3).map((subj, idx) => (
                            <span
                              key={idx}
                              className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 truncate max-w-[115px]"
                            >
                              {subj}
                            </span>
                          ))}
                        </div>
                        <span className="text-xs font-mono font-semibold text-amber-400 group-hover:translate-x-0.5 transition-transform flex items-center gap-1 shrink-0">
                          Open Trip <ArrowRight className="w-3.5 h-3.5" />
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {visibleExpeditionCount < visibleTrips.length && (
              <div
                ref={expeditionSentinelRef}
                className="py-6 flex flex-col items-center justify-center gap-2 font-mono"
              >
                <button
                  type="button"
                  onClick={() =>
                    setVisibleExpeditionCount((prev) =>
                      Math.min(prev + EXPEDITION_BATCH_SIZE, visibleTrips.length)
                    )
                  }
                  className="px-4 py-2 rounded-md bg-studio-panel hover:bg-studio-hover border border-amber-500/40 text-amber-300 text-xs font-semibold transition-colors"
                >
                  Showing {windowedVisibleTrips.length} of {visibleTrips.length} expeditions — Load Next {Math.min(EXPEDITION_BATCH_SIZE, visibleTrips.length - visibleExpeditionCount)}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
