import React, { useState, useEffect, useRef } from 'react';
import {
  X,
  Cpu,
  FolderPlus,
  FolderOpen,
  AlertTriangle,
  HardDrive,
  Play,
  Pause,
  Square,
  RefreshCw,
  CheckCircle2,
  Sparkles,
  MapPin,
  Trash2,
} from 'lucide-react';

function formatSeconds(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec))) return '—';
  const s = Math.max(0, Math.round(Number(sec)));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return m > 0 ? `${m}m ${rem}s` : `${rem}s`;
}

export default function PipelineModal({
  isOpen,
  onClose,
  catalogs = [],
  activeCatalog = 'All Catalogs',
  onSelectCatalog,
  onRefreshCatalogs,
  initialTab = 'pipeline',
  onShowToast,
}) {
  const [activeTab, setActiveTab] = useState(initialTab || 'pipeline'); // 'pipeline' | 'catalogs' | 'errors' | 'backup'

  // Unified Destination Mode: 'new' (Create New Catalog) | 'existing' (Add to Existing Catalog)
  const [destinationMode, setDestinationMode] = useState('new');
  const [newCatalogName, setNewCatalogName] = useState('');
  const [autoFilledName, setAutoFilledName] = useState('');
  const [selectedExistingCatalog, setSelectedExistingCatalog] = useState(
    catalogs?.[0]?.catalog_name || catalogs?.[0]?.name || 'Keepers'
  );

  // Source folder + Live Pre-scan state
  const [folderPath, setFolderPath] = useState('');
  const [browsingFolder, setBrowsingFolder] = useState(false);
  const [prescanLoading, setPrescanLoading] = useState(false);
  const [prescanResult, setPrescanResult] = useState(null);

  // 1-Click AI Tagging options
  const [runAiTagging, setRunAiTagging] = useState(true);
  const [aiMode, setAiMode] = useState('fast_vectors'); // 'fast_vectors' | 'deep_vlm'

  // Pipeline execution & live progress state
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);
  const prevRunningRef = useRef(false);
  const lastStartedCatalogRef = useRef(null);

  // Ingestion errors state
  const [errors, setErrors] = useState([]);
  const [loadingErrors, setLoadingErrors] = useState(false);

  // DAS Backup state
  const [backupReport, setBackupReport] = useState(null);
  const [backingUp, setBackingUp] = useState(false);

  // Fast Re-Assess state
  const [reassessRunning, setReassessRunning] = useState(false);
  const [reassessReport, setReassessReport] = useState(null);

  // Remote Git Auto-Updater state
  const [updateInfo, setUpdateInfo] = useState(null);
  const [checkingUpdate, setCheckingUpdate] = useState(false);
  const [applyingUpdate, setApplyingUpdate] = useState(false);

  useEffect(() => {
    if (isOpen && initialTab) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

  useEffect(() => {
    if (catalogs && catalogs.length > 0) {
      const validNames = catalogs
        .map((c) => c.catalog_name || c.name)
        .filter((n) => n && n !== 'All Catalogs');
      if (
        activeCatalog &&
        activeCatalog !== 'All Catalogs' &&
        validNames.includes(activeCatalog)
      ) {
        setSelectedExistingCatalog(activeCatalog);
      } else if (!selectedExistingCatalog || !validNames.includes(selectedExistingCatalog)) {
        if (validNames.length > 0) {
          setSelectedExistingCatalog(validNames[0]);
        }
      }
    }
  }, [catalogs, activeCatalog]);

  // When switching to 'existing' catalog mode, pre-populate folderPath if that catalog has a root_path and folderPath is empty
  useEffect(() => {
    if (destinationMode === 'existing' && selectedExistingCatalog && !folderPath) {
      const matched = (catalogs || []).find(
        (c) => (c.catalog_name || c.name) === selectedExistingCatalog
      );
      if (matched?.root_path) {
        setFolderPath(matched.root_path);
      }
    }
  }, [destinationMode, selectedExistingCatalog, catalogs]);

  // Live pre-scan whenever folderPath changes
  useEffect(() => {
    if (!isOpen) return;
    const trimmed = (folderPath || '').trim();
    if (!trimmed) {
      setPrescanResult(null);
      setPrescanLoading(false);
      return;
    }

    let cancelled = false;
    setPrescanLoading(true);
    const timer = setTimeout(() => {
      fetch('/api/catalogs/prescan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: trimmed }),
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (cancelled || !data) return;
          setPrescanResult(data);
          setPrescanLoading(false);
          if (
            destinationMode === 'new' &&
            data.suggested_catalog_name &&
            (!newCatalogName.trim() || newCatalogName.trim() === autoFilledName)
          ) {
            setNewCatalogName(data.suggested_catalog_name);
            setAutoFilledName(data.suggested_catalog_name);
          }
        })
        .catch(() => {
          if (!cancelled) setPrescanLoading(false);
        });
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [folderPath, isOpen, destinationMode]);

  // Poll pipeline status while modal is open
  const fetchPipelineStatus = () => {
    fetch('/api/pipeline/status')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        setPipelineStatus(data);

        // Detect transition from running -> completed so we automatically refresh & switch view to the imported catalog
        if (prevRunningRef.current && !data.running && !data.error) {
          const targetCat = data.catalog_name || lastStartedCatalogRef.current;
          if (onRefreshCatalogs) onRefreshCatalogs();
          if (targetCat && onSelectCatalog) {
            onSelectCatalog(targetCat);
          }
          if (onShowToast && targetCat) {
            onShowToast(`✓ Imported & AI-tagged catalog "${targetCat}"`);
          }
        }
        prevRunningRef.current = Boolean(data.running);
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (!isOpen) return undefined;
    fetchPipelineStatus();
    const interval = setInterval(fetchPipelineStatus, 900);
    return () => clearInterval(interval);
  }, [isOpen]);

  // Load errors when errors tab is active
  useEffect(() => {
    if (isOpen && activeTab === 'errors') {
      setLoadingErrors(true);
      fetch('/api/errors?limit=100')
        .then((res) => res.json())
        .then((data) => {
          setErrors(data.errors || []);
          setLoadingErrors(false);
        })
        .catch(() => setLoadingErrors(false));
    }
  }, [isOpen, activeTab]);

  if (!isOpen) return null;

  const handleBrowseNativeFolder = async () => {
    if (browsingFolder) return;
    setBrowsingFolder(true);
    setActionMessage(null);
    try {
      const res = await fetch('/api/system/browse-folder', { method: 'POST' });
      const data = await res.json();
      if (data && !data.cancelled && data.path) {
        setFolderPath(data.path);
        if (data.prescan) {
          setPrescanResult(data.prescan);
        }
        const suggested = data.suggested_catalog_name || data.folder_name || '';
        if (
          destinationMode === 'new' &&
          suggested &&
          (!newCatalogName.trim() || newCatalogName.trim() === autoFilledName)
        ) {
          setNewCatalogName(suggested);
          setAutoFilledName(suggested);
        }
      }
    } catch (err) {
      setActionMessage({ type: 'error', text: `Folder browser error: ${err.message}` });
    } finally {
      setBrowsingFolder(false);
    }
  };

  const resolveTargetCatalogName = () => {
    if (destinationMode === 'new') {
      const explicit = (newCatalogName || '').trim();
      if (explicit) return explicit;
      if (prescanResult?.suggested_catalog_name) return prescanResult.suggested_catalog_name;
      const parts = (folderPath || '').trim().replace(/\/+$/, '').split('/');
      return parts[parts.length - 1] || '';
    }
    return (selectedExistingCatalog || '').trim();
  };

  const handleLaunchOneClickImport = async (stageOverride = 0) => {
    setActionMessage(null);
    const targetCatalog = resolveTargetCatalogName();
    const targetPath = (folderPath || '').trim();

    if (!targetCatalog) {
      setActionMessage({
        type: 'error',
        text: 'Please enter a Catalog Name or browse to a source folder first.',
      });
      return;
    }

    if (destinationMode === 'new' && !targetPath) {
      setActionMessage({
        type: 'error',
        text: 'Please click "📂 Browse..." or enter a source folder path to import.',
      });
      return;
    }

    try {
      lastStartedCatalogRef.current = targetCatalog;
      prevRunningRef.current = true;

      const res = await fetch('/api/pipeline/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          catalog_name: targetCatalog,
          root_path: targetPath || undefined,
          stage: stageOverride,
          run_ai_tagging: stageOverride === 0 ? runAiTagging : stageOverride === 2,
          ai_mode: aiMode,
          extract_sharpness: true,
          fast_only: false,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        prevRunningRef.current = false;
        throw new Error(data.detail || 'Failed to start import pipeline');
      }

      if (onRefreshCatalogs) onRefreshCatalogs();
      if (onSelectCatalog) onSelectCatalog(targetCatalog);
      fetchPipelineStatus();
      setActionMessage({
        type: 'success',
        text: `Started import for "${targetCatalog}". You can watch live progress below or close this window and continue working.`,
      });
    } catch (err) {
      setActionMessage({ type: 'error', text: err.message });
    }
  };

  const handlePauseResumeJob = async () => {
    const isPaused = Boolean(pipelineStatus?.paused || pipelineStatus?.job?.paused);
    const endpoint = isPaused ? '/api/jobs/resume' : '/api/jobs/pause';
    await fetch(endpoint, { method: 'POST' }).catch(() => {});
    fetchPipelineStatus();
  };

  const handleCancelJob = async () => {
    await fetch('/api/jobs/cancel', { method: 'POST' }).catch(() => {});
    fetchPipelineStatus();
  };

  const handleSaveCatalogOnly = async (e) => {
    e.preventDefault();
    const targetCatalog = resolveTargetCatalogName();
    const targetPath = (folderPath || '').trim();
    if (!targetCatalog || !targetPath) {
      setActionMessage({
        type: 'error',
        text: 'Both Catalog Name and Folder Path are required.',
      });
      return;
    }

    try {
      const res = await fetch('/api/catalogs/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: targetCatalog, root_path: targetPath }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to register catalog');
      setActionMessage({
        type: 'success',
        text: `Catalog "${data.catalog_name}" registered (${data.root_path}).`,
      });
      if (onRefreshCatalogs) onRefreshCatalogs();
      if (onSelectCatalog) onSelectCatalog(data.catalog_name);
    } catch (err) {
      setActionMessage({ type: 'error', text: err.message });
    }
  };

  const handleDeleteCatalog = async (catName) => {
    if (!catName || ['All Catalogs', 'Keepers'].includes(catName)) return;
    try {
      const res = await fetch(`/api/catalogs/${encodeURIComponent(catName)}?remove_photos=true`, {
        method: 'DELETE',
      });
      if (res.ok) {
        if (onRefreshCatalogs) onRefreshCatalogs();
        if (activeCatalog === catName && onSelectCatalog) {
          onSelectCatalog('All Catalogs');
        }
      }
    } catch (_) {}
  };

  const handleRunFastReassess = () => {
    const targetCat = resolveTargetCatalogName();
    setReassessRunning(true);
    setReassessReport(null);
    fetch('/api/reassess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        catalog_name: !targetCat || targetCat === 'All Catalogs' ? null : targetCat,
        mode: 'fast_vectors',
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setReassessReport(data);
        setReassessRunning(false);
        if (onRefreshCatalogs) onRefreshCatalogs();
      })
      .catch((err) => {
        setReassessReport({ error: err.message });
        setReassessRunning(false);
      });
  };

  const handleTriggerBackup = () => {
    setBackingUp(true);
    setBackupReport(null);
    fetch('/api/backup', { method: 'POST' })
      .then((res) => res.json())
      .then((data) => {
        setBackupReport(data.report);
        setBackingUp(false);
      })
      .catch((err) => {
        setBackupReport({ error: err.message });
        setBackingUp(false);
      });
  };

  const handleCheckForUpdates = async () => {
    setCheckingUpdate(true);
    try {
      const res = await fetch('/api/system/update-check');
      if (res.ok) {
        const data = await res.json();
        setUpdateInfo(data);
      }
    } catch (_) {
    } finally {
      setCheckingUpdate(false);
    }
  };

  const handleApplyUpdate = async () => {
    if (applyingUpdate) return;
    setApplyingUpdate(true);
    try {
      await fetch('/api/system/update-apply', { method: 'POST' });
    } catch (_) {}
    setTimeout(() => {
      window.location.reload();
    }, 3000);
  };

  const isRunning = Boolean(pipelineStatus?.running);
  const isPaused = Boolean(pipelineStatus?.paused || pipelineStatus?.job?.paused);
  const processedCount = pipelineStatus?.processed || 0;
  const totalCount = pipelineStatus?.total || 0;
  const progressPct =
    totalCount > 0
      ? Math.min(100, Math.round((processedCount / totalCount) * 100))
      : isRunning
      ? 12
      : 0;
  const elapsedSec = pipelineStatus?.elapsed_seconds ?? pipelineStatus?.job?.elapsed_seconds;
  const etaSec = pipelineStatus?.eta_seconds ?? pipelineStatus?.job?.eta_seconds;

  const selectableCatalogs = (catalogs || []).filter((c) => {
    const n = (c.catalog_name || c.name || '').trim();
    return n && n.toLowerCase() !== 'all catalogs' && n.toLowerCase() !== 'all';
  });

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4 select-none">
      <div className="w-full max-w-3xl bg-studio-panel border border-studio-border rounded-md shadow-2xl flex flex-col max-h-[88vh] text-studio-text">
        {/* Header */}
        <div className="h-12 bg-studio-bg border-b border-studio-border px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <Cpu className="w-4 h-4 text-studio-accent" />
            <span className="font-mono text-xs uppercase tracking-wider text-white font-semibold">
              MR Darkroom — Unified Catalog &amp; Photo Import Studio
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCheckForUpdates}
              disabled={checkingUpdate || applyingUpdate}
              className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-studio-panel hover:bg-studio-hover border border-studio-border text-amber-300 rounded-sm transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${checkingUpdate ? 'animate-spin' : ''}`} />
              <span>{checkingUpdate ? 'Checking...' : '🔄 Check Updates'}</span>
            </button>
            {updateInfo?.update_available && (
              <button
                type="button"
                onClick={handleApplyUpdate}
                disabled={applyingUpdate}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-sm transition-colors"
              >
                <span>
                  {applyingUpdate
                    ? 'Updating... Reloading in 3s'
                    : `✨ Update Now (${updateInfo.commits_behind})`}
                </span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 hover:bg-studio-hover text-studio-textDim hover:text-white rounded-sm"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-studio-border bg-studio-panel/50 px-4 pt-1 gap-2 shrink-0">
          {[
            { id: 'pipeline', label: '📥 Import & AI Tag', icon: Play },
            { id: 'catalogs', label: '🗂️ Manage Catalogs', icon: FolderPlus },
            { id: 'errors', label: 'Ingestion Log', icon: AlertTriangle },
            { id: 'backup', label: 'DAS Backup', icon: HardDrive },
          ].map((tab) => {
            const active = activeTab === tab.id;
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-1.5 px-3.5 py-2.5 text-xs font-mono border-b-2 transition-colors ${
                  active
                    ? 'border-studio-accent text-white font-semibold bg-studio-bg/60'
                    : 'border-transparent text-studio-textMuted hover:text-white'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 text-xs font-sans space-y-5">
          {/* TAB 1: UNIFIED IMPORT + CATALOG + AI TAG WORKFLOW */}
          {activeTab === 'pipeline' && (
            <div className="space-y-4">
              {/* Step 1: Source Folder + Native macOS Browse + Live Pre-Scan */}
              <div className="p-4 bg-studio-bg border border-studio-border rounded-md space-y-3.5">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                      Step 1 · Select Photo Folder
                    </span>
                    <h3 className="text-sm font-semibold text-white mt-1.5">
                      Choose Source Folder (Mac, iPhone Export, Fujifilm / Camera Card, or DAS)
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleBrowseNativeFolder}
                    disabled={browsingFolder}
                    className="flex items-center gap-2 px-4 py-2 rounded-md text-xs font-mono font-semibold bg-amber-500 hover:bg-amber-400 text-zinc-950 shadow-md transition-all cursor-pointer shrink-0"
                  >
                    <FolderOpen className="w-4 h-4" />
                    <span>{browsingFolder ? 'Opening Finder...' : '📂 Browse...'}</span>
                  </button>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={folderPath}
                    onChange={(e) => setFolderPath(e.target.value)}
                    placeholder="Click 📂 Browse... or paste folder path (e.g. /Users/photographer/Pictures/Trip_Photos)"
                    className="flex-1 bg-studio-panel border border-studio-border px-3 py-2 text-xs font-mono text-white rounded-sm focus:border-studio-accent focus:outline-none select-text"
                  />
                </div>

                {/* Live Pre-Scan Summary Banner */}
                {(prescanLoading || prescanResult) && (
                  <div
                    className={`p-3 rounded-sm border font-mono text-xs flex flex-col gap-2 ${
                      prescanLoading
                        ? 'bg-studio-panel/60 border-studio-border text-studio-textDim'
                        : prescanResult?.exists && prescanResult?.total_photos > 0
                        ? 'bg-emerald-950/30 border-emerald-700/60 text-emerald-300'
                        : prescanResult?.exists
                        ? 'bg-amber-950/30 border-amber-700/60 text-amber-300'
                        : 'bg-red-950/30 border-red-800/60 text-red-300'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="font-semibold">
                        {prescanLoading
                          ? 'Scanning folder for supported photos & RAWs...'
                          : prescanResult?.summary_text}
                      </span>
                      {!prescanLoading && prescanResult?.exists && (
                        <span className="text-[11px] text-studio-textDim">
                          {prescanResult.has_lrcat
                            ? `✓ Lightroom .lrcat detected`
                            : `✓ Standalone folder walk (no .lrcat required)`}
                        </span>
                      )}
                    </div>

                    {!prescanLoading &&
                      prescanResult?.extension_counts &&
                      Object.keys(prescanResult.extension_counts).length > 0 && (
                        <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                          {Object.entries(prescanResult.extension_counts).map(([ext, cnt]) => (
                            <span
                              key={ext}
                              className="px-2 py-0.5 rounded bg-black/40 border border-emerald-600/40 text-[11px] text-white font-semibold"
                            >
                              {cnt} {ext}
                            </span>
                          ))}
                          <span className="text-[11px] text-emerald-300/90 ml-auto flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            Offline GPS Reverse-Geocoding &amp; Same-Day Camera Bridging Active
                          </span>
                        </div>
                      )}
                  </div>
                )}
              </div>

              {/* Step 2: Destination Catalog (Create New vs. Add to Existing) */}
              <div className="p-4 bg-studio-bg border border-studio-border rounded-md space-y-3.5">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div>
                    <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                      Step 2 · Destination Catalog
                    </span>
                    <h3 className="text-sm font-semibold text-white mt-1.5">
                      Choose Where These Photos Belong
                    </h3>
                  </div>

                  {/* Mode Toggle Pills */}
                  <div className="flex items-center bg-studio-panel p-1 rounded border border-studio-border font-mono text-xs">
                    <button
                      type="button"
                      onClick={() => setDestinationMode('new')}
                      className={`px-3 py-1.5 rounded-sm transition-colors cursor-pointer ${
                        destinationMode === 'new'
                          ? 'bg-studio-accent text-white font-semibold'
                          : 'text-studio-textDim hover:text-white'
                      }`}
                    >
                      ＋ Create New Catalog
                    </button>
                    <button
                      type="button"
                      onClick={() => setDestinationMode('existing')}
                      className={`px-3 py-1.5 rounded-sm transition-colors cursor-pointer ${
                        destinationMode === 'existing'
                          ? 'bg-studio-accent text-white font-semibold'
                          : 'text-studio-textDim hover:text-white'
                      }`}
                    >
                      🗂️ Add to Existing Catalog
                    </button>
                  </div>
                </div>

                {destinationMode === 'new' ? (
                  <div>
                    <label className="block text-[11px] font-mono text-studio-textDim mb-1">
                      New Catalog Name (auto-filled from folder name if left blank)
                    </label>
                    <input
                      type="text"
                      value={newCatalogName}
                      onChange={(e) => setNewCatalogName(e.target.value)}
                      placeholder={
                        prescanResult?.suggested_catalog_name ||
                        'e.g. Family_iPhone_2025 or Utah_Expedition'
                      }
                      className="w-full bg-studio-panel border border-studio-border px-3 py-2 text-xs font-mono text-white rounded-sm focus:border-studio-accent focus:outline-none select-text"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-[11px] font-mono text-studio-textDim mb-1">
                      Select Existing Catalog
                    </label>
                    <select
                      value={selectedExistingCatalog}
                      onChange={(e) => {
                        const val = e.target.value;
                        setSelectedExistingCatalog(val);
                        const matched = selectableCatalogs.find(
                          (c) => (c.catalog_name || c.name) === val
                        );
                        if (matched?.root_path) {
                          setFolderPath(matched.root_path);
                        }
                      }}
                      className="w-full bg-studio-panel border border-studio-border px-3 py-2 text-xs font-mono text-white rounded-sm focus:border-studio-accent focus:outline-none"
                    >
                      {selectableCatalogs.map((c, idx) => {
                        const cname = c.catalog_name || c.name;
                        const cnt = c.photo_count ?? c.total_photos;
                        return (
                          <option key={idx} value={cname}>
                            {cname} {typeof cnt === 'number' ? `(${cnt} photos)` : ''}
                          </option>
                        );
                      })}
                    </select>
                  </div>
                )}
              </div>

              {/* Step 3: 1-Click Ingest + AI Tagging Launch Card */}
              <div className="p-4 bg-studio-bg border border-studio-border rounded-md space-y-4">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="space-y-1">
                    <span className="text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                      Step 3 · 1-Click Import &amp; AI Tagging
                    </span>
                    <h3 className="text-sm font-semibold text-white pt-1">
                      Build Previews, Resolve Offline GPS Locations &amp; Run AI Scene Tagging
                    </h3>
                    <p className="text-[11px] text-studio-textDim leading-relaxed max-w-xl">
                      Extracts 360px &amp; 1600px previews (including Apple <code className="text-zinc-300">.HEIC</code>, Fujifilm <code className="text-zinc-300">.RAF</code>, <code className="text-zinc-300">.JPG</code>, <code className="text-zinc-300">.PNG</code> &amp; RAWs), resolves EXIF GPS coordinates 100% offline into Country / State / City / Landmark ground-truth tags, bridges same-day GPS locations to non-GPS cameras, and tags subjects automatically.
                    </p>
                  </div>

                  {/* AI Tagging Mode Selector */}
                  <div className="flex flex-col gap-2 font-mono text-xs shrink-0">
                    <label className="flex items-center gap-2 text-white cursor-pointer">
                      <input
                        type="checkbox"
                        checked={runAiTagging}
                        onChange={(e) => setRunAiTagging(e.target.checked)}
                        className="accent-emerald-500"
                      />
                      <span>Run Stage 2 AI Tagging automatically</span>
                    </label>
                    {runAiTagging && (
                      <select
                        value={aiMode}
                        onChange={(e) => setAiMode(e.target.value)}
                        className="bg-studio-panel border border-studio-border px-2.5 py-1.5 rounded-sm text-xs text-white"
                      >
                        <option value="fast_vectors">
                          ⚡ Fast OpenCLIP + GPS Ground-Truth + Ontology
                        </option>
                        <option value="deep_vlm">
                          🧠 Deep Qwen2.5-VL Vision Analysis (~3s/photo)
                        </option>
                      </select>
                    )}
                  </div>
                </div>

                {/* Primary 1-Click CTA + Secondary Step Controls */}
                <div className="pt-2 border-t border-studio-border/70 flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <button
                      type="button"
                      onClick={() => handleLaunchOneClickImport(0)}
                      disabled={isRunning}
                      className="flex items-center gap-2 px-5 py-2.5 rounded-md font-mono text-xs font-bold bg-gradient-to-r from-blue-600 to-emerald-600 hover:from-blue-500 hover:to-emerald-500 disabled:opacity-50 text-white shadow-lg transition-all cursor-pointer"
                    >
                      <Sparkles className="w-4 h-4" />
                      <span>
                        {isRunning
                          ? 'Import & AI Tagging in Progress...'
                          : `🚀 Import & AI Tag ${
                              prescanResult?.total_photos
                                ? `(${prescanResult.total_photos} Photos)`
                                : 'Photos'
                            }`}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={handleRunFastReassess}
                      disabled={reassessRunning || isRunning}
                      title="Re-assess and sync learned tags, offline GPS ground-truth, and shoot-day locations across this catalog (<2s)"
                      className="flex items-center gap-1.5 px-3 py-2 rounded-md font-mono text-xs bg-studio-panel hover:bg-studio-hover border border-studio-border text-amber-300 disabled:opacity-50 transition-colors cursor-pointer"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${reassessRunning ? 'animate-spin' : ''}`} />
                      <span>{reassessRunning ? 'Syncing...' : '🔄 Re-Sync Tags & GPS (<2s)'}</span>
                    </button>
                  </div>

                  {reassessReport && !reassessReport.error && (
                    <span className="text-[11px] font-mono text-emerald-400">
                      ✓ Synced {reassessReport.reassessed_count} photos in {reassessReport.elapsed_seconds}s
                    </span>
                  )}
                </div>

                {actionMessage && (
                  <div
                    className={`p-2.5 rounded-sm font-mono text-xs ${
                      actionMessage.type === 'error'
                        ? 'bg-red-950/40 border border-red-800 text-red-300'
                        : 'bg-emerald-950/40 border border-emerald-800 text-emerald-300'
                    }`}
                  >
                    {actionMessage.text}
                  </div>
                )}
              </div>

              {/* Live Progress & Timing Box with Pause / Resume / Cancel */}
              <div className="p-3.5 bg-studio-bg border border-studio-border rounded-md font-mono text-xs space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-semibold">Live Pipeline Status</span>
                    {pipelineStatus?.catalog_name && (
                      <span className="px-2 py-0.5 rounded bg-studio-panel border border-studio-border text-[11px] text-amber-300">
                        {pipelineStatus.catalog_name}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {isRunning && (
                      <>
                        <button
                          type="button"
                          onClick={handlePauseResumeJob}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 text-amber-300 text-[11px] cursor-pointer"
                        >
                          {isPaused ? <Play className="w-3 h-3" /> : <Pause className="w-3 h-3" />}
                          <span>{isPaused ? 'Resume' : 'Pause'}</span>
                        </button>
                        <button
                          type="button"
                          onClick={handleCancelJob}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 text-red-300 text-[11px] cursor-pointer"
                        >
                          <Square className="w-3 h-3" />
                          <span>Cancel</span>
                        </button>
                      </>
                    )}
                    <span
                      className={
                        isRunning
                          ? isPaused
                            ? 'text-amber-400 font-semibold'
                            : 'text-studio-accent font-semibold'
                          : pipelineStatus?.error
                          ? 'text-red-400 font-semibold'
                          : 'text-emerald-400 font-semibold'
                      }
                    >
                      {isRunning
                        ? isPaused
                          ? 'PAUSED'
                          : 'RUNNING'
                        : pipelineStatus?.error
                        ? 'ERROR'
                        : 'READY'}
                    </span>
                  </div>
                </div>

                {pipelineStatus && (isRunning || totalCount > 0) && (
                  <div className="space-y-1.5 pt-1">
                    <div className="flex items-center justify-between text-[11px] text-studio-textMuted">
                      <span>{pipelineStatus.phase || 'Processing...'}</span>
                      <span>
                        {processedCount} / {totalCount} photos ({progressPct}%)
                      </span>
                    </div>
                    <div className="w-full h-2 bg-studio-panel border border-studio-border rounded-sm overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-blue-500 to-emerald-400 transition-all duration-300"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-studio-textDim pt-0.5">
                      <span className="truncate max-w-md">
                        {pipelineStatus.current_file
                          ? `File: ${pipelineStatus.current_file}`
                          : 'Ready'}
                      </span>
                      <span>
                        Elapsed: {formatSeconds(elapsedSec)}
                        {isRunning && etaSec !== null && etaSec !== undefined
                          ? ` · ETA: ${formatSeconds(etaSec)}`
                          : ''}
                      </span>
                    </div>
                  </div>
                )}

                {pipelineStatus?.error && (
                  <div className="text-red-400 text-[11px] bg-red-950/30 border border-red-900/50 p-2 rounded-sm">
                    Error: {pipelineStatus.error}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: MANAGE CATALOGS & FOLDERS */}
          {activeTab === 'catalogs' && (
            <div className="space-y-5">
              <div className="bg-studio-bg border border-studio-border p-4 rounded-md space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-mono text-xs text-white font-semibold flex items-center gap-1.5">
                    <FolderPlus className="w-3.5 h-3.5 text-studio-accent" />
                    <span>Register or Update a Catalog Folder</span>
                  </h3>
                  <button
                    type="button"
                    onClick={handleBrowseNativeFolder}
                    disabled={browsingFolder}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-mono font-semibold bg-amber-500 hover:bg-amber-400 text-zinc-950 cursor-pointer"
                  >
                    <FolderOpen className="w-3.5 h-3.5" />
                    <span>{browsingFolder ? 'Opening Finder...' : '📂 Browse Folder...'}</span>
                  </button>
                </div>

                <form onSubmit={handleSaveCatalogOnly} className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-mono text-studio-textDim mb-1">
                        Catalog Name
                      </label>
                      <input
                        type="text"
                        value={newCatalogName}
                        onChange={(e) => setNewCatalogName(e.target.value)}
                        placeholder="e.g. iPhone_2025 or Aerial_Working"
                        className="w-full bg-studio-panel border border-studio-border px-2.5 py-1.5 text-xs font-mono text-white rounded-sm focus:border-studio-accent focus:outline-none select-text"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-mono text-studio-textDim mb-1">
                        Folder Path (Absolute)
                      </label>
                      <input
                        type="text"
                        value={folderPath}
                        onChange={(e) => setFolderPath(e.target.value)}
                        placeholder="/Users/photographer/Pictures/..."
                        className="w-full bg-studio-panel border border-studio-border px-2.5 py-1.5 text-xs font-mono text-white rounded-sm focus:border-studio-accent focus:outline-none select-text"
                        required
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="submit"
                      className="bg-studio-accent hover:bg-blue-600 text-white font-mono text-xs px-3.5 py-1.5 rounded-sm transition-colors cursor-pointer"
                    >
                      Save Catalog Entry
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDestinationMode('new');
                        setActiveTab('pipeline');
                        handleLaunchOneClickImport(0);
                      }}
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs px-3.5 py-1.5 rounded-sm transition-colors cursor-pointer"
                    >
                      🚀 Save &amp; Import Photos Now
                    </button>
                  </div>
                </form>
              </div>

              {/* Registered Catalogs List */}
              <div>
                <h4 className="font-mono text-xs text-white font-semibold mb-2">
                  Registered Catalogs in Archive
                </h4>
                <div className="space-y-1.5 font-mono text-xs">
                  {selectableCatalogs.length > 0 ? (
                    selectableCatalogs.map((c, i) => {
                      const cname = c.name || c.catalog_name;
                      const cnt = c.photo_count ?? c.total_photos ?? 0;
                      const isCurrent = activeCatalog === cname;
                      return (
                        <div
                          key={i}
                          className="p-3 bg-studio-bg border border-studio-border rounded-sm flex items-center justify-between gap-3"
                        >
                          <div className="min-w-0">
                            <div className="text-white font-semibold flex items-center gap-2">
                              <span>{cname}</span>
                              {isCurrent && (
                                <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/40">
                                  Active View
                                </span>
                              )}
                            </div>
                            <div className="text-[11px] text-studio-textDim truncate max-w-lg">
                              {c.root_path || 'Managed archive silo'}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-[11px] text-studio-accent font-semibold">
                              {cnt} photos
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                if (onSelectCatalog) onSelectCatalog(cname);
                                onClose();
                              }}
                              className="px-2.5 py-1 rounded bg-studio-panel hover:bg-studio-hover border border-studio-border text-white text-[11px] cursor-pointer"
                            >
                              View
                            </button>
                            {cname !== 'Keepers' && (
                              <button
                                type="button"
                                onClick={() => handleDeleteCatalog(cname)}
                                title={`Remove catalog "${cname}" from database (never deletes files on disk)`}
                                className="p-1.5 rounded bg-studio-panel hover:bg-red-950/60 border border-studio-border text-studio-textDim hover:text-red-300 cursor-pointer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <div className="text-studio-textDim">No custom catalogs registered yet.</div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: Ingestion Errors */}
          {activeTab === 'errors' && (
            <div className="space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between text-studio-textDim">
                <span>Recent Ingestion Warnings &amp; File Errors</span>
                <span>{errors.length} records</span>
              </div>

              {loadingErrors ? (
                <div className="text-center py-8 text-studio-textDim">Loading error log...</div>
              ) : errors.length > 0 ? (
                <div className="space-y-1.5 max-h-96 overflow-y-auto">
                  {errors.map((err) => (
                    <div
                      key={err.id}
                      className="p-2 bg-studio-bg border border-red-900/40 rounded-sm space-y-1 text-[11px]"
                    >
                      <div className="flex items-center justify-between text-red-400 font-medium">
                        <span>
                          [{err.stage}] {err.error_type}
                        </span>
                        <span className="text-studio-textDim">{err.created_at}</span>
                      </div>
                      <div className="text-studio-text truncate">{err.file_path}</div>
                      <div className="text-studio-textDim text-[10px]">{err.error_message}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-emerald-400 flex flex-col items-center gap-2">
                  <CheckCircle2 className="w-6 h-6" />
                  <span>Zero Ingestion Errors! All catalog files parsed cleanly.</span>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: DAS Backup */}
          {activeTab === 'backup' && (
            <div className="space-y-4 font-mono text-xs">
              <div className="p-4 bg-studio-bg border border-studio-border rounded-sm space-y-3">
                <h3 className="text-white font-medium flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-studio-accent" />
                  <span>Direct-Attached Storage (DAS) Backup</span>
                </h3>
                <p className="text-studio-textDim text-[11px] leading-relaxed">
                  Safely copies the SQLite database (<code className="text-studio-text">photo_archive.db</code>) via atomic VACUUM INTO, along with the memory-mapped vector matrix (<code className="text-studio-text">vectors.npy</code>) to your DAS archive backup volume.
                </p>

                <button
                  onClick={handleTriggerBackup}
                  disabled={backingUp}
                  className="flex items-center gap-2 bg-studio-accent hover:bg-blue-600 disabled:opacity-50 text-white px-3 py-1.5 rounded-sm transition-colors"
                >
                  <HardDrive className="w-3.5 h-3.5" />
                  <span>{backingUp ? 'Backing Up...' : 'Execute Backup to DAS'}</span>
                </button>
              </div>

              {backupReport && (
                <div className="p-3 bg-studio-bg border border-studio-border rounded-sm space-y-1 text-[11px]">
                  <div className="text-emerald-400 font-medium">Backup Completed Successfully</div>
                  <pre className="text-studio-textDim overflow-x-auto p-2 bg-studio-panel rounded-sm">
                    {JSON.stringify(backupReport, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
