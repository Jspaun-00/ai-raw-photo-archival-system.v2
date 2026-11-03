import React, { useState, useEffect, useRef } from 'react';

const SUBSET_OPTIONS = [
  { id: 'all', label: 'All Photos', shortLabel: 'All', desc: 'Show every photo in current selection' },
  { id: 'top25', label: 'Top 25%', shortLabel: 'Top 25%', desc: 'Top quarter by LAION + Taste aesthetic score' },
  { id: 'top10', label: 'Top 10%', shortLabel: 'Top 10%', desc: 'Top decile portfolio candidates' },
  { id: 'top5', label: 'Top 5%', shortLabel: 'Top 5%', desc: 'Masterpiece / exhibition-grade frames only' },
];

const VIEW_MODES = [
  { id: 'grid', label: '⊞ Grid', title: 'Continuous Light-Table Grid' },
  { id: 'date', label: '📅 By Date', title: 'Collapsible Shoot Days with Smart Titles' },
  { id: 'trips', label: '🧭 Trips & Regions', title: '10,000-Foot Portfolio Regions & Multi-Day Expeditions' },
];

const PORTFOLIO_QUICK_PILLS = [
  { id: 'National Parks & Mountains', icon: '🏔️', label: 'National Parks & Mountains' },
  { id: 'Desert', icon: '🏜️', label: 'Desert' },
  { id: 'Coastline & Piers', icon: '🌊', label: 'Coastline & Piers' },
  { id: 'Palouse & Farmland', icon: '🌾', label: 'Palouse & Farmland' },
  { id: 'Oil Fields & Industrial', icon: '🛢️', label: 'Oil Fields & Industrial' },
  { id: 'Iceland', icon: '🌋', label: 'Iceland' },
  { id: 'Urban & Architecture', icon: '🏙️', label: 'Urban & Architecture' },
  { id: 'Wildlife & Animals', icon: '🐎', label: 'Wildlife & Animals' },
  { id: 'Still Life & Cultural Details', icon: '🏺', label: 'Still Life & Details' },
];

const SORT_OPTIONS = [
  { id: 'capture_desc', label: 'Date: Newest → Oldest' },
  { id: 'capture_asc', label: 'Date: Oldest → Newest' },
  { id: 'aesthetic_desc', label: 'Aesthetic Score: High → Low' },
  { id: 'stars_desc', label: 'Star Rating: 5★ → 0★' },
  { id: 'sharpness_desc', label: 'Sharpness: High → Low' },
  { id: 'filename_asc', label: 'Filename: A → Z' },
];

export default function TopRibbon({
  catalogs = [],
  activeCatalog = 'All Catalogs',
  onSelectCatalog,
  searchQuery,
  query,
  onSearchChange,
  onQueryChange,
  aestheticPercentile,
  subsetPct,
  onSelectPercentile,
  onSubsetChange,
  hideUnsharp = false,
  onToggleHideUnsharp,
  onToggleUnsharp,
  minStars = null,
  onToggleStars,
  onToggleFourFiveStars,
  collapseStrafing,
  collapseSequences,
  onToggleCollapseStrafing,
  onToggleCollapseSequences,
  viewMode = 'grid',
  onViewModeChange,
  onSelectViewMode,
  sortBy = 'capture_desc',
  onSelectSortBy,
  onSortByChange,
  totalPhotos,
  totalFiltered,
  onOpenPipelineModal,
  activePortfolioTheme = null,
  onSelectPortfolioTheme,
}) {
  const [aestheticOpen, setAestheticOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [updateInfo, setUpdateInfo] = useState(null);
  const [isUpdatingApp, setIsUpdatingApp] = useState(false);

  const aestheticRef = useRef(null);
  const filtersRef = useRef(null);

  // Unified prop bindings supporting both App.jsx and legacy aliases
  const currentQuery = searchQuery !== undefined ? searchQuery : query || '';
  const handleQueryChange = onSearchChange || onQueryChange || (() => {});

  const currentSubset = aestheticPercentile !== undefined ? aestheticPercentile : subsetPct || 'all';
  const handleSubsetChange = onSelectPercentile || onSubsetChange || (() => {});

  const normalizedSortBy =
    sortBy === 'date_desc'
      ? 'capture_desc'
      : sortBy === 'date_asc'
      ? 'capture_asc'
      : sortBy || 'capture_desc';
  const handleSortChange = onSelectSortBy || onSortByChange || (() => {});

  const handleViewChange = onViewModeChange || onSelectViewMode || (() => {});

  const handleStarsToggle = onToggleStars || onToggleFourFiveStars || (() => {});
  const handleUnsharpToggle = onToggleHideUnsharp || onToggleUnsharp || (() => {});
  const currentCollapse =
    collapseStrafing !== undefined ? collapseStrafing : Boolean(collapseSequences);
  const handleCollapseToggle =
    onToggleCollapseStrafing || onToggleCollapseSequences || (() => {});

  // Close popovers on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (aestheticRef.current && !aestheticRef.current.contains(e.target)) {
        setAestheticOpen(false);
      }
      if (filtersRef.current && !filtersRef.current.contains(e.target)) {
        setFiltersOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Check for remote Git updates on mount
  useEffect(() => {
    let cancelled = false;
    fetch('/api/system/update-check')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setUpdateInfo(data);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const handleApplyUpdate = async () => {
    if (isUpdatingApp) return;
    setIsUpdatingApp(true);
    try {
      await fetch('/api/system/update-apply', { method: 'POST' });
    } catch (_) {
      // Server restarts during update-apply
    }
    setTimeout(() => {
      window.location.reload();
    }, 3000);
  };

  // Deduplicate additional catalogs cleanly (excluding All Catalogs & Keepers which have dedicated pills)
  const seenNames = new Set();
  const cleanCatalogs = [];
  let keepersCount = null;
  for (const c of catalogs) {
    const name = (c.catalog_name || c.name || '').trim();
    if (!name) continue;
    const count =
      typeof c.photo_count === 'number'
        ? c.photo_count
        : typeof c.total_photos === 'number'
        ? c.total_photos
        : null;
    if (name.toLowerCase() === 'keepers') {
      if (typeof count === 'number') keepersCount = count;
      continue;
    }
    if (name.toLowerCase() === 'all catalogs' || name.toLowerCase() === 'all' || name.toLowerCase() === 'all photos') continue;
    if (typeof count === 'number' && count <= 0) continue; // Skip ghost / empty catalogs
    if (seenNames.has(name)) continue;
    seenNames.add(name);
    cleanCatalogs.push(c);
  }

  const isAllActive =
    !activeCatalog ||
    activeCatalog === 'All Catalogs' ||
    activeCatalog === 'ALL' ||
    activeCatalog === 'All Photos';
  const isKeepersActive =
    activeCatalog === 'Keepers' || activeCatalog === 'KEEPERS';

  const currentSubsetObj =
    SUBSET_OPTIONS.find((o) => o.id === currentSubset) || SUBSET_OPTIONS[0];
  const activeFilterCount =
    (Number(minStars) >= 4 ? 1 : 0) +
    (hideUnsharp ? 1 : 0) +
    (currentCollapse ? 1 : 0);

  return (
    <>
      {isUpdatingApp && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            background: 'rgba(8, 10, 15, 0.94)',
            backdropFilter: 'blur(12px)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#f8fafc',
            gap: '16px',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '14px',
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              color: '#090b10',
              fontWeight: 900,
              fontSize: '22px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 30px rgba(245, 158, 11, 0.45)',
            }}
          >
            MR
          </div>
          <div style={{ fontSize: '22px', fontWeight: 700, letterSpacing: '-0.01em' }}>
            Updating MR Darkroom... Reloading in 3 seconds
          </div>
          <div style={{ fontSize: '14px', color: '#94a3b8' }}>
            Your photo catalog and collections in Application Support are 100% preserved.
          </div>
        </div>
      )}

      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 40,
          background: 'rgba(11, 13, 18, 0.96)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid #1f2430',
          padding: '10px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        {/* Row 1: Primary Header: Brand Logo + Generous Search + View Switcher + Unified Catalog Dropdown + Import */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            width: '100%',
          }}
        >
          {/* Studio Identity: MR Darkroom */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '9px',
                background: 'linear-gradient(135deg, #18181b 0%, #090b10 100%)',
                border: '1.5px solid #f59e0b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '14px',
                color: '#fbbf24',
                letterSpacing: '-0.03em',
                boxShadow: '0 2px 10px rgba(245, 158, 11, 0.2)',
              }}
            >
              MR
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
              <span
                style={{
                  fontWeight: 700,
                  fontSize: '17px',
                  letterSpacing: '-0.01em',
                  color: '#f8fafc',
                  whiteSpace: 'nowrap',
                }}
              >
                MR Darkroom
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: '#94a3b8',
                  background: '#161922',
                  border: '1px solid #262b38',
                  padding: '1px 6px',
                  borderRadius: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                v{updateInfo?.version || '4.0'}
              </span>
            </div>

            {updateInfo?.update_available && (
              <button
                type="button"
                onClick={handleApplyUpdate}
                title={`Update available (${updateInfo.commits_behind} new update${updateInfo.commits_behind === 1 ? '' : 's'}). Click to update MR Darkroom automatically.`}
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  border: '1px solid #10b981',
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.28) 0%, rgba(5, 150, 105, 0.38) 100%)',
                  color: '#6ee7b7',
                  boxShadow: '0 0 12px rgba(16, 185, 129, 0.3)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>✨ Update App</span>
              </button>
            )}
          </div>

          {/* Search Input (flex: 1, generous width) */}
          <div
            style={{
              position: 'relative',
              flex: '1 1 360px',
              minWidth: '240px',
            }}
          >
            <span
              style={{
                position: 'absolute',
                left: '14px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: '#94a3b8',
                fontSize: '15px',
                pointerEvents: 'none',
              }}
            >
              🔍
            </span>
            <input
              type="text"
              value={currentQuery}
              onChange={(e) => handleQueryChange(e.target.value)}
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === 'Escape' && currentQuery) {
                  handleQueryChange('');
                }
              }}
              placeholder="Search places, landmarks, dates, cameras, breeds, subjects..."
              style={{
                width: '100%',
                padding: '9px 38px 9px 40px',
                borderRadius: '9px',
                background: '#141822',
                border: currentQuery ? '1.5px solid #f59e0b' : '1.5px solid #2d3548',
                color: '#ffffff',
                fontSize: '15px',
                fontWeight: 500,
                outline: 'none',
                userSelect: 'text',
                WebkitUserSelect: 'text',
                boxShadow: currentQuery
                  ? '0 0 0 3px rgba(245, 158, 11, 0.15)'
                  : 'inset 0 1px 2px rgba(0,0,0,0.3)',
              }}
            />
            {currentQuery && (
              <button
                type="button"
                onClick={() => handleQueryChange('')}
                title="Clear search"
                style={{
                  position: 'absolute',
                  right: '9px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: '#262b38',
                  border: '1px solid #3b4254',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  cursor: 'pointer',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '2px 7px',
                }}
              >
                ✕
              </button>
            )}
          </div>

          {/* View Switcher: [ ⊞ Grid | 📅 By Date | 🧭 Trips & Regions ] */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: '#141720',
              padding: '3px',
              borderRadius: '9px',
              border: '1px solid #2a3040',
              flexShrink: 0,
            }}
          >
            {VIEW_MODES.map((vm) => {
              const active = viewMode === vm.id;
              return (
                <button
                  type="button"
                  key={vm.id}
                  onClick={() => handleViewChange(vm.id)}
                  title={vm.title}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '7px',
                    fontSize: '13.5px',
                    fontWeight: active ? 700 : 500,
                    cursor: 'pointer',
                    border: 'none',
                    background: active ? '#3b82f6' : 'transparent',
                    color: active ? '#ffffff' : '#cbd5e1',
                    transition: 'all 0.15s',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {vm.label}
                </button>
              );
            })}
          </div>

          {/* Unified Catalog Selector Dropdown */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: '#141720',
              border: isKeepersActive ? '1.5px solid rgba(245, 158, 11, 0.7)' : '1px solid #334155',
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: isKeepersActive ? '0 0 12px rgba(245, 158, 11, 0.2)' : 'none',
              flexShrink: 0,
            }}
            title="Active Catalog Selector — Switch catalogs or create/manage catalog folders"
          >
            <button
              type="button"
              onClick={() => onOpenPipelineModal && onOpenPipelineModal('catalogs')}
              style={{
                padding: '7px 10px',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                background: isKeepersActive ? 'rgba(245, 158, 11, 0.2)' : '#1e293b',
                color: isKeepersActive ? '#fbbf24' : '#cbd5e1',
                border: 'none',
                borderRight: isKeepersActive ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid #334155',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                whiteSpace: 'nowrap',
              }}
            >
              <span>{isKeepersActive ? '★' : '🗂️'}</span>
              <span>Catalog:</span>
            </button>
            <select
              value={
                isAllActive
                  ? 'All Catalogs'
                  : isKeepersActive
                  ? 'Keepers'
                  : activeCatalog
              }
              onChange={(e) => {
                const val = e.target.value;
                if (val === '__NEW_CATALOG__') {
                  if (onOpenPipelineModal) onOpenPipelineModal('pipeline');
                  return;
                }
                if (onSelectCatalog) onSelectCatalog(val);
              }}
              style={{
                padding: '7px 11px',
                background: '#141720',
                color: isKeepersActive ? '#fbbf24' : '#f8fafc',
                border: 'none',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: 'pointer',
                outline: 'none',
                maxWidth: '180px',
              }}
            >
              <option value="All Catalogs">All Photos</option>
              <option value="Keepers">
                ★ Keepers{typeof keepersCount === 'number' && keepersCount > 0 ? ` (${keepersCount.toLocaleString()})` : ''}
              </option>
              {cleanCatalogs.map((cat) => {
                const name = cat.catalog_name || cat.name;
                const count =
                  typeof cat.photo_count === 'number'
                    ? cat.photo_count
                    : typeof cat.total_photos === 'number'
                    ? cat.total_photos
                    : null;
                return (
                  <option key={name} value={name}>
                    {name.replace(/_/g, ' ')}
                    {typeof count === 'number' ? ` (${count.toLocaleString()})` : ''}
                  </option>
                );
              })}
              <option value="__NEW_CATALOG__">＋ New Catalog / Import Folder...</option>
            </select>
          </div>

          {/* Import & AI Tag Button */}
          <button
            type="button"
            onClick={() => onOpenPipelineModal && onOpenPipelineModal('pipeline')}
            title="Browse to any photo folder, create or select a catalog, and run 1-click Import + Offline GPS & AI Tagging"
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 700,
              cursor: 'pointer',
              border: '1px solid #3b82f6',
              background: 'linear-gradient(135deg, rgba(37, 99, 235, 0.28) 0%, rgba(30, 64, 175, 0.38) 100%)',
              color: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            <span>📥</span> Import &amp; AI Tag
          </button>
        </div>

        {/* Row 2: Full-Width Portfolio Regions (Left/Center) + Sort & Filters (Right) */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '14px',
            width: '100%',
          }}
        >
          {/* Full-Width Portfolio Regions Pills Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              overflowX: 'auto',
              flex: '1 1 auto',
              minWidth: 0,
              padding: '2px 0',
              scrollbarWidth: 'thin',
            }}
          >
            <button
              type="button"
              onClick={() => onSelectPortfolioTheme && onSelectPortfolioTheme(null)}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                fontSize: '12.5px',
                fontWeight: !activePortfolioTheme ? 700 : 500,
                cursor: 'pointer',
                border: !activePortfolioTheme ? '1px solid #f59e0b' : '1px solid #262b38',
                background: !activePortfolioTheme ? 'rgba(245, 158, 11, 0.18)' : '#141720',
                color: !activePortfolioTheme ? '#fbbf24' : '#cbd5e1',
                flexShrink: 0,
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
            >
              All Regions
            </button>
            {PORTFOLIO_QUICK_PILLS.map((pill) => {
              const isSelected = activePortfolioTheme === pill.id;
              return (
                <button
                  type="button"
                  key={pill.id}
                  onClick={() =>
                    onSelectPortfolioTheme &&
                    onSelectPortfolioTheme(isSelected ? null : pill.id)
                  }
                  style={{
                    padding: '5px 10px',
                    borderRadius: '6px',
                    fontSize: '12.5px',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                    border: isSelected ? '1px solid #f59e0b' : '1px solid #262b38',
                    background: isSelected ? 'rgba(245, 158, 11, 0.2)' : '#141720',
                    color: isSelected ? '#fbbf24' : '#cbd5e1',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '5px',
                    flexShrink: 0,
                    transition: 'all 0.15s',
                    whiteSpace: 'nowrap',
                  }}
                >
                  <span>{pill.icon}</span>
                  <span>{pill.label}</span>
                </button>
              );
            })}
          </div>

          {/* Right Controls: Sort By + Aesthetic Popover + Filters Popover */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexShrink: 0,
            }}
          >
            {/* Sort By Dropdown */}
            <select
              value={normalizedSortBy}
              onChange={(e) => handleSortChange(e.target.value)}
              aria-label="Sort photos by"
              style={{
                padding: '6px 10px',
                borderRadius: '8px',
                background: '#141720',
                border: '1px solid #2a3040',
                color: '#f1f5f9',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id} style={{ background: '#141720', color: '#f1f5f9' }}>
                  {opt.label}
                </option>
              ))}
            </select>

            {/* Consolidated Aesthetic Tier Popover Dropdown */}
            <div ref={aestheticRef} style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => {
                  setAestheticOpen((prev) => !prev);
                  setFiltersOpen(false);
                }}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: currentSubset !== 'all' ? '1px solid #f59e0b' : '1px solid #2a3040',
                  background: currentSubset !== 'all' ? 'rgba(245, 158, 11, 0.16)' : '#141720',
                  color: currentSubset !== 'all' ? '#fbbf24' : '#e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>✨ Aesthetic: {currentSubsetObj.shortLabel}</span>
                <span style={{ fontSize: '11px', opacity: 0.8 }}>▾</span>
              </button>

              {aestheticOpen && (
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 8px)',
                    width: '280px',
                    background: '#11141d',
                    border: '1px solid #2e3646',
                    borderRadius: '12px',
                    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.75)',
                    padding: '8px',
                    zIndex: 100,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#94a3b8',
                      padding: '4px 10px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    Aesthetic Percentile Filter
                  </div>
                  {SUBSET_OPTIONS.map((opt) => {
                    const isSelected = currentSubset === opt.id;
                    return (
                      <button
                        type="button"
                        key={opt.id}
                        onClick={() => {
                          handleSubsetChange(opt.id);
                          setAestheticOpen(false);
                        }}
                        style={{
                          textAlign: 'left',
                          padding: '10px 12px',
                          borderRadius: '8px',
                          border: isSelected ? '1px solid #f59e0b' : '1px solid transparent',
                          background: isSelected ? 'rgba(245, 158, 11, 0.16)' : 'transparent',
                          color: isSelected ? '#fbbf24' : '#f1f5f9',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '2px',
                        }}
                      >
                        <div style={{ fontSize: '14px', fontWeight: 700, display: 'flex', justifyContent: 'space-between' }}>
                          <span>{opt.label}</span>
                          {isSelected && <span>✓</span>}
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8' }}>{opt.desc}</div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Consolidated Filters Popover Dropdown */}
            <div ref={filtersRef} style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => {
                  setFiltersOpen((prev) => !prev);
                  setAestheticOpen(false);
                }}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: activeFilterCount > 0 ? '1px solid #38bdf8' : '1px solid #2a3040',
                  background: activeFilterCount > 0 ? 'rgba(56, 189, 248, 0.14)' : '#141720',
                  color: activeFilterCount > 0 ? '#7dd3fc' : '#e2e8f0',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '5px',
                  whiteSpace: 'nowrap',
                }}
              >
                <span>🎯 Filters {activeFilterCount > 0 ? `(${activeFilterCount})` : ''}</span>
                <span style={{ fontSize: '11px', opacity: 0.8 }}>▾</span>
              </button>

              {filtersOpen && (
                <div
                  style={{
                    position: 'absolute',
                    right: 0,
                    top: 'calc(100% + 8px)',
                    width: '300px',
                    background: '#11141d',
                    border: '1px solid #2e3646',
                    borderRadius: '12px',
                    boxShadow: '0 16px 40px rgba(0, 0, 0, 0.75)',
                    padding: '10px',
                    zIndex: 100,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div
                    style={{
                      fontSize: '12px',
                      fontWeight: 700,
                      color: '#94a3b8',
                      padding: '4px 8px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em',
                    }}
                  >
                    Studio View Filters
                  </div>

                  {/* Row 1: 4-5 Stars Only */}
                  <button
                    type="button"
                    onClick={() => handleStarsToggle()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: Number(minStars) >= 4 ? 'rgba(245, 158, 11, 0.14)' : '#161a26',
                      border: Number(minStars) >= 4 ? '1px solid #f59e0b' : '1px solid #242a38',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <span
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '4px',
                        border: Number(minStars) >= 4 ? '1px solid #f59e0b' : '1px solid #475569',
                        background: Number(minStars) >= 4 ? '#f59e0b' : '#0d1017',
                        color: '#090b10',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 900,
                        flexShrink: 0,
                      }}
                    >
                      {Number(minStars) >= 4 ? '✓' : ''}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                        ★ 4–5 Stars Only
                      </span>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        Show highest-rated portfolio selects
                      </span>
                    </div>
                  </button>

                  {/* Row 2: Sharp Photos Only */}
                  <button
                    type="button"
                    onClick={() => handleUnsharpToggle()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: hideUnsharp ? 'rgba(16, 185, 129, 0.14)' : '#161a26',
                      border: hideUnsharp ? '1px solid #10b981' : '1px solid #242a38',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <span
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '4px',
                        border: hideUnsharp ? '1px solid #10b981' : '1px solid #475569',
                        background: hideUnsharp ? '#10b981' : '#0d1017',
                        color: '#090b10',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 900,
                        flexShrink: 0,
                      }}
                    >
                      {hideUnsharp ? '✓' : ''}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                        💎 Sharp Photos Only
                      </span>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        Hide soft or motion-blurred frames
                      </span>
                    </div>
                  </button>

                  {/* Row 3: Group Burst Sequences */}
                  <button
                    type="button"
                    onClick={() => handleCollapseToggle()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: currentCollapse ? 'rgba(99, 102, 241, 0.16)' : '#161a26',
                      border: currentCollapse ? '1px solid #6366f1' : '1px solid #242a38',
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                    }}
                  >
                    <span
                      style={{
                        width: '18px',
                        height: '18px',
                        borderRadius: '4px',
                        border: currentCollapse ? '1px solid #6366f1' : '1px solid #475569',
                        background: currentCollapse ? '#6366f1' : '#0d1017',
                        color: '#ffffff',
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 900,
                        flexShrink: 0,
                      }}
                    >
                      {currentCollapse ? '✓' : ''}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontSize: '14px', fontWeight: 600, color: '#f8fafc' }}>
                        ⧉ Group Burst Sequences
                      </span>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                        Stack rapid bursts under their Hero frame
                      </span>
                    </div>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>
    </>
  );
}
