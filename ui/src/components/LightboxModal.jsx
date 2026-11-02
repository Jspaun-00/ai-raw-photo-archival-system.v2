import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  X, ChevronLeft, ChevronRight, Star, ExternalLink, Folder, Camera,
  MapPin, Tag, Info, Layers, Sparkles, Copy, Check, Eye, RefreshCw, Zap, Cpu, Calendar, LayoutGrid, ChevronDown, RotateCcw, Mic, Trash2
} from 'lucide-react';
import CollectionPopover from './CollectionPopover.jsx';

export default function LightboxModal({
  photo,
  activeIndex = 0,
  totalCount = 1,
  onClose,
  onNavigatePrev,
  onNavigateNext,
  onUpdateStar,
  onSelectPhoto,
  onTagClick,
  onPhotoUpdated,
  onOpenFullDayInGrid,
  collections = [],
  onTogglePhotoInCollection,
  onCreateCollectionWithPhoto,
  onOpenCollectionsModal,
  onOpenVoiceTeachForPhoto,
  undoStatus = null,
  onTriggerUndo = null,
  onUndoStatusChange = null,
}) {
  const [details, setDetails] = useState(photo);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [similarityMode, setSimilarityMode] = useState('visual'); // 'visual' | 'orbit' | 'sameday'
  const [similarPhotos, setSimilarPhotos] = useState([]);
  const [sameDayPhotos, setSameDayPhotos] = useState([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const [neighbors, setNeighbors] = useState([]);
  const [loadingNeighbors, setLoadingNeighbors] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [copiedPath, setCopiedPath] = useState(false);
  const [reassessing, setReassessing] = useState(false);
  const [reassessMenuOpen, setReassessMenuOpen] = useState(false);
  const [clearingTags, setClearingTags] = useState(false);
  const [syncingEdits, setSyncingEdits] = useState(false);
  const [openInMenuOpen, setOpenInMenuOpen] = useState(false);
  const openInMenuRef = useRef(null);

  // Subject Box Overlay & Active Vector Reclassification State
  const [showSubjectBoxes, setShowSubjectBoxes] = useState(false);
  const [reclassifyTarget, setReclassifyTarget] = useState(null); // { label, bbox }
  const [customReclassifyInput, setCustomReclassifyInput] = useState('');
  const [reclassifying, setReclassifying] = useState(false);

  // Quick Location Controls State
  const [locationInput, setLocationInput] = useState('');
  const [updatingLocation, setUpdatingLocation] = useState(false);
  const [locationSuggestions, setLocationSuggestions] = useState([]);

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const photoId = photo.file_hash || encodeURIComponent(photo.file_path);

  // Load verified location autocomplete suggestions once
  useEffect(() => {
    let active = true;
    fetch('/api/locations/autocomplete')
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (active && data && Array.isArray(data.locations)) {
          setLocationSuggestions(data.locations);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  // Immediately update details when photo prop changes so arrow navigation feels instantaneous
  useEffect(() => {
    setDetails(photo);
    setReassessMenuOpen(false);
    setOpenInMenuOpen(false);
    setReclassifyTarget(null);
    setCustomReclassifyInput('');
    setLocationInput('');
  }, [photo]);

  // Close Open In dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (openInMenuRef.current && !openInMenuRef.current.contains(e.target)) {
        setOpenInMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch full metadata for active photo
  useEffect(() => {
    let isCurrent = true;
    setLoadingDetails(true);
    fetch(`/api/photo/${photoId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load photo metadata');
        return res.json();
      })
      .then((data) => {
        if (isCurrent) {
          setDetails(data);
          setLoadingDetails(false);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setDetails(photo);
          setLoadingDetails(false);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [photoId, photo]);

  // Pre-fetch all photos from this shoot day so the "📅 All From This Day ({count})" tab always shows its live count
  useEffect(() => {
    let isCurrent = true;
    fetch(`/api/photo/${photoId}/similar?mode=sameday&limit=150`)
      .then((res) => res.json())
      .then((data) => {
        if (isCurrent) {
          setSameDayPhotos(data.similar_photos || []);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSameDayPhotos([]);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [photoId]);

  // Fetch similar photos when mode or photo changes
  useEffect(() => {
    if (similarityMode === 'sameday') {
      setSimilarPhotos(sameDayPhotos);
      setLoadingSimilar(false);
      return;
    }
    let isCurrent = true;
    setLoadingSimilar(true);
    fetch(`/api/photo/${photoId}/similar?mode=${similarityMode}&limit=16`)
      .then((res) => res.json())
      .then((data) => {
        if (isCurrent) {
          setSimilarPhotos(data.similar_photos || []);
          setLoadingSimilar(false);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setSimilarPhotos([]);
          setLoadingSimilar(false);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [photoId, similarityMode, sameDayPhotos]);

  // Fetch chronological neighbors (-5 / +5)
  useEffect(() => {
    let isCurrent = true;
    setLoadingNeighbors(true);
    fetch(`/api/photo/${photoId}/neighbors`)
      .then((res) => res.json())
      .then((data) => {
        if (isCurrent) {
          setNeighbors(data.neighbors || []);
          setLoadingNeighbors(false);
        }
      })
      .catch(() => {
        if (isCurrent) {
          setNeighbors([]);
          setLoadingNeighbors(false);
        }
      });
    return () => {
      isCurrent = false;
    };
  }, [photoId]);

  // Star Rating Handler
  const handleSetRating = useCallback((newStars) => {
    fetch(`/api/photo/${photoId}/star`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ star_rating: newStars }),
    })
      .then((res) => res.json())
      .then((data) => {
        setDetails((prev) => ({ ...prev, star_rating: newStars }));
        if (onUpdateStar) {
          onUpdateStar(photo, newStars);
        }
        showToast(`Rating updated to ${newStars}★ (XMP sync in background)`);
      })
      .catch((err) => {
        showToast(`Error updating rating: ${err.message}`);
      });
  }, [photoId, photo, onUpdateStar]);

  // External App Launcher
  const handleOpenApp = (appName) => {
    fetch(`/api/photo/${photoId}/open`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ app: appName }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.status === 'ok') {
          showToast(data.message || `Opened in ${appName}`);
        } else {
          showToast(`App Launch: ${data.message || 'Unknown response'}`);
        }
      })
      .catch((err) => {
        showToast(`Error launching ${appName}: ${err.message}`);
      });
  };

  // Sync External Photoshop / Finder Edits for this photo & parent folder
  const handleSyncPhotoEdits = () => {
    if (syncingEdits) return;
    setSyncingEdits(true);
    showToast('Checking for external Photoshop saves & new derivative files...');
    fetch(`/api/photos/${photoId}/sync-edits?force=true`, {
      method: 'POST',
    })
      .then((res) => res.json())
      .then((data) => {
        setSyncingEdits(false);
        if (data.photo) {
          setDetails(data.photo);
          if (onPhotoUpdated) onPhotoUpdated(data.photo);
        }
        const modCnt = (data.modified_photos || []).length;
        const newCnt = (data.new_derivatives || []).length;
        if (modCnt > 0 || newCnt > 0) {
          showToast(
            `Synced external edits! (${modCnt} updated, ${newCnt} new derivative${newCnt === 1 ? '' : 's'})`
          );
        } else {
          showToast('Previews & OpenCLIP vector verified up-to-date');
        }
      })
      .catch((err) => {
        setSyncingEdits(false);
        showToast(`Sync edits error: ${err.message}`);
      });
  };

  // Keyboard navigation & Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Don't capture keys if focused on an input
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target?.tagName)) return;

      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        e.stopPropagation();
        if (onNavigatePrev) onNavigatePrev();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        e.stopPropagation();
        if (onNavigateNext) onNavigateNext();
      } else if (['1', '2', '3', '4', '5'].includes(e.key)) {
        handleSetRating(parseInt(e.key, 10));
      } else if (e.key === '0' || e.key === 'Backspace') {
        handleSetRating(0);
      } else if (e.key.toLowerCase() === 'l') {
        handleOpenApp('lightroom');
      } else if (e.key.toLowerCase() === 'p') {
        handleOpenApp('photoshop');
      } else if (e.key.toLowerCase() === 'f') {
        handleOpenApp('finder');
      }
    };

    window.addEventListener('keydown', handleKeyDown, true);
    return () => window.removeEventListener('keydown', handleKeyDown, true);
  }, [onClose, onNavigatePrev, onNavigateNext, handleSetRating]);

  const copyPath = () => {
    if (details.file_path) {
      navigator.clipboard.writeText(details.file_path);
      setCopiedPath(true);
      setTimeout(() => setCopiedPath(false), 2000);
      showToast('Copied file path to clipboard');
    }
  };

  const previewSrc = details.preview_url || (details.preview_1600_path ? `/previews/previews_1600/${details.preview_1600_path.split('/').pop()}` : null) || (details.thumb_url || (details.thumb_360_path ? `/previews/thumbs_360/${details.thumb_360_path.split('/').pop()}` : null));

  const filename = details.file_path ? details.file_path.split('/').pop() : 'Photo';
  const currentStars = details.star_rating || 0;

  const parseTagArray = (v) => {
    if (Array.isArray(v)) return v;
    if (typeof v === 'string' && v.trim()) {
      try {
        const parsed = JSON.parse(v);
        if (Array.isArray(parsed)) return parsed;
      } catch {
        return v.split(',').map((s) => s.trim()).filter(Boolean);
      }
    }
    return [];
  };

  const parseJsonRawArray = (v) => {
    if (Array.isArray(v)) return v;
    if (typeof v === 'string' && v.trim()) {
      try {
        const parsed = JSON.parse(v);
        if (Array.isArray(parsed)) return parsed;
      } catch {
        return [];
      }
    }
    return [];
  };

  const subjectBoxes = parseJsonRawArray(details.subject_boxes).filter(
    (b) => b && typeof b === 'object' && Array.isArray(b.bbox) && b.bbox.length === 4
  );
  const verifiedSubjects = parseJsonRawArray(details.verified_subjects).filter(
    (v) => v && typeof v === 'object' && v.label
  );

  // Active Vector Reclassification / Dismiss Handler
  const handleReclassifySubject = (oldLabel, newLabel = '', action = 'reclassify', bbox = null) => {
    if (!oldLabel || reclassifying) return;
    setReclassifying(true);
    const isDismiss = action === 'dismiss' || !newLabel;
    showToast(
      isDismiss
        ? `🧠 Dismissing "${oldLabel}" & updating OpenCLIP vector boundary...`
        : `🧠 Reclassifying "${oldLabel}" → "${newLabel}" & updating vector boundary...`
    );

    fetch(`/api/photos/${photoId}/reclassify-subject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        old_label: oldLabel,
        new_label: isDismiss ? '' : newLabel,
        action: isDismiss ? 'dismiss' : 'reclassify',
        bbox: bbox || null,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setReclassifying(false);
        setReclassifyTarget(null);
        setCustomReclassifyInput('');
        if (data.undo_status && onUndoStatusChange) {
          onUndoStatusChange(data.undo_status);
        }
        if (data.photo) {
          setDetails(data.photo);
          if (onPhotoUpdated) onPhotoUpdated(data.photo);
        }
        showToast(
          isDismiss
            ? `✓ Dismissed "${oldLabel}" (vector boundary learned — Cmd+Z to undo)`
            : `✓ Reclassified "${oldLabel}" → "${newLabel}" (vector boundary learned)`
        );
      })
      .catch((err) => {
        setReclassifying(false);
        showToast(`Reclassify error: ${err.message}`);
      });
  };

  // Clear Location (1-click wipe to "" + block false location from returning)
  const handleClearLocation = () => {
    if (updatingLocation) return;
    setUpdatingLocation(true);
    showToast('📍 Clearing location to blank & blocking false guess...');

    fetch(`/api/photos/${photoId}/location`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'clear' }),
    })
      .then((res) => res.json())
      .then((data) => {
        setUpdatingLocation(false);
        if (data.undo_status && onUndoStatusChange) {
          onUndoStatusChange(data.undo_status);
        }
        if (data.photo) {
          setDetails(data.photo);
          if (onPhotoUpdated) onPhotoUpdated(data.photo);
        }
        showToast('📍 Location cleared to blank (Cmd+Z to undo)');
      })
      .catch((err) => {
        setUpdatingLocation(false);
        showToast(`Clear location error: ${err.message}`);
      });
  };

  // Set Verified Location
  const handleSetLocation = (e) => {
    if (e) e.preventDefault();
    const locStr = (locationInput || '').trim();
    if (!locStr || updatingLocation) return;
    setUpdatingLocation(true);
    showToast(`📍 Setting verified location to "${locStr}"...`);

    fetch(`/api/photos/${photoId}/location`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: 'set',
        location: locStr,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setUpdatingLocation(false);
        setLocationInput('');
        if (data.undo_status && onUndoStatusChange) {
          onUndoStatusChange(data.undo_status);
        }
        if (data.photo) {
          setDetails(data.photo);
          if (onPhotoUpdated) onPhotoUpdated(data.photo);
        }
        showToast(`📍 Verified location saved: "${locStr}"`);
      })
      .catch((err) => {
        setUpdatingLocation(false);
        showToast(`Set location error: ${err.message}`);
      });
  };

  const handleClearPhotoTags = () => {
    if (clearingTags || reassessing) return;
    setClearingTags(true);
    showToast('🧹 Clearing tags on this photo (Undo snapshot saved)...');

    fetch('/api/ai/teach', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        photo_ids: [photo.file_hash || photo.file_path],
        instruction: '',
        mode: 'instant',
        wipe_existing: true,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setClearingTags(false);
        if (data.undo_status && onUndoStatusChange) {
          onUndoStatusChange(data.undo_status);
        }
        if (data.photos && data.photos.length > 0) {
          setDetails(data.photos[0]);
          if (onPhotoUpdated) onPhotoUpdated(data.photos[0]);
        } else {
          fetch(`/api/photo/${photoId}`)
            .then((r) => r.json())
            .then((d) => {
              setDetails(d);
              if (onPhotoUpdated) onPhotoUpdated(d);
            });
        }
        showToast('🧹 Cleared all tags (click ↩ Undo or press Cmd+Z to restore)');
      })
      .catch((err) => {
        setClearingTags(false);
        showToast(`Clear tags error: ${err.message}`);
      });
  };

  const handleReassessPhoto = (mode) => {
    if (reassessing || clearingTags) return;
    setReassessMenuOpen(false);
    setReassessing(true);
    showToast(
      mode === 'deep_vlm'
        ? 'Running Deep AI Re-Tag (qwen2.5vl:7b + perspective guide)...'
        : 'Running Basic Vector & Ontology Tagging (<1s)...'
    );

    fetch('/api/reassess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        photo_ids: [photo.file_hash || photo.file_path],
        mode,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setReassessing(false);
        if (data.undo_status && onUndoStatusChange) {
          onUndoStatusChange(data.undo_status);
        }
        if (data.photos && data.photos.length > 0) {
          setDetails(data.photos[0]);
          if (onPhotoUpdated) onPhotoUpdated(data.photos[0]);
        } else {
          fetch(`/api/photo/${photoId}`)
            .then((r) => r.json())
            .then((d) => {
              setDetails(d);
              if (onPhotoUpdated) onPhotoUpdated(d);
            });
        }
        showToast(
          `Tags refreshed in ${data.elapsed_seconds || 0}s (${
            mode === 'deep_vlm' ? 'Deep AI Re-Tag' : 'Basic Tag'
          })`
        );
      })
      .catch((err) => {
        setReassessing(false);
        showToast(`Re-assess error: ${err.message}`);
      });
  };

  const BOILERPLATE_LIGHTBOX_TAGS = new Set([
    'mitch rouse aerials',
    'mitch_rouse_aerials',
    'mitch rouse',
    'aerials',
    'msr',
    'keepers',
    'west coast imaging',
    'west coast imaging*  alice',
    'alice',
    'location_review_needed',
    'location_burst_inherited',
    'needs_review',
    'untitled',
    'unclassified',
    'none',
    'unknown',
    '[cleared_slate]',
    'national parks & mountains',
    'pets & animals',
    'portraits & people',
    'automotive & urban',
    'architecture & interiors',
    'everyday & lifestyle',
    'eye-level terrestrial',
    'eye-level',
    'terrestrial',
    'unsharp',
    'sharp',
    'bro just look',
    "what's",
    'whats',
    'united states',
    'usa',
  ]);

  const SCHEMA_ARTIFACT_SUBSTRINGS = [
    '|specific',
    '|feature',
    '|subcategory',
    '|category',
    'perspective|',
    'subjects|',
    'location|country',
    'style|',
    'lighting|',
    'residence|architecture',
  ];

  const isSchemaOrJunkTag = (tag) => {
    const raw = String(tag || '').trim();
    if (!raw) return true;
    const tl = raw.toLowerCase();
    if (BOILERPLATE_LIGHTBOX_TAGS.has(tl)) return true;
    if (
      tl.includes('mitch rouse aerials') ||
      tl.includes('mitch_rouse_aerials') ||
      tl.includes('west coast imaging')
    ) {
      return true;
    }
    for (const frag of SCHEMA_ARTIFACT_SUBSTRINGS) {
      if (tl.includes(frag)) return true;
    }
    return false;
  };

  const normalizeCleanDisplayTag = (tag) => {
    const raw = String(tag || '').trim();
    if (!raw) return '';
    // Never show raw pipe-delimited ontology strings in the UI
    if (raw.includes('|')) {
      if (isSchemaOrJunkTag(raw)) return '';
      const parts = raw
        .split('|')
        .map((p) => p.trim())
        .filter((p) => p && !['specific', 'feature', 'category', 'subcategory', 'subjects', 'location', 'perspective', 'style', 'identity'].includes(p.toLowerCase()));
      const leaf = parts[parts.length - 1] || '';
      if (!leaf || isSchemaOrJunkTag(leaf)) return '';
      return leaf;
    }
    if (isSchemaOrJunkTag(raw)) return '';
    return raw;
  };

  const isSlateCleared = String(details.user_context_notes || '').includes('[CLEARED_SLATE]');

  // 1. User-taught custom tags always come first & are never stripped as boilerplate
  const DIRECTIVE_JUNK_SET = new Set([
    'bro just look',
    "what's",
    'whats',
    'just look',
    'look at it',
    "tag what's",
    'in there',
    'tell me',
    'look closely',
  ]);
  const userTaughtTags = [];
  const userTaughtLowerSet = new Set();
  for (const ut of parseTagArray(details.user_taught_tags)) {
    const s = String(ut || '').trim();
    if (!s || s.includes('|')) continue;
    const sl = s.toLowerCase();
    if (DIRECTIVE_JUNK_SET.has(sl)) continue;
    if (!userTaughtLowerSet.has(sl)) {
      userTaughtLowerSet.add(sl);
      userTaughtTags.push(s);
    }
  }

  // Build redundant location filter set so municipal/state/county/country GPS metadata
  // stays cleanly inside Location Metadata without duplicating 5 pills in Keywords & Studio Tags
  const redundantLocLowerSet = new Set(['united states', 'usa']);
  const ctyStr = String(details.city || '').trim();
  const subStr = String(details.sub_location || '').trim();
  const stStr = String(details.state_region || '').trim();
  const ctryStr = String(details.country || '').trim();
  const specStr = String(details.specific_location || '').trim();
  for (const locVal of [ctyStr, subStr, stStr, ctryStr]) {
    if (locVal) redundantLocLowerSet.add(locVal.toLowerCase());
  }
  if (ctyStr && stStr) {
    redundantLocLowerSet.add(`${ctyStr}, ${stStr}`.toLowerCase());
  }
  if (
    specStr &&
    (Number(details.gps_ground_truth || 0) === 1 ||
      details.location_provenance === 'exif_gps' ||
      details.location_provenance === 'same_day_gps' ||
      specStr.includes(','))
  ) {
    redundantLocLowerSet.add(specStr.toLowerCase());
  }

  // 2. Clean studio & subject keywords (zero pipe strings, schema placeholders, or redundant GPS pills)
  const cleanStudioTags = [];
  const seenLower = new Set(userTaughtLowerSet);
  if (!isSlateCleared) {
    for (const src of [
      details.key_subjects,
      details.tags,
      details.existing_keywords,
      details.lrcat_keywords,
      details.all_tags,
      details.hierarchical_keywords,
    ]) {
      for (const t of parseTagArray(src)) {
        const cleaned = normalizeCleanDisplayTag(t);
        if (!cleaned) continue;
        const cl = cleaned.toLowerCase();
        if (redundantLocLowerSet.has(cl) || cl.endsWith(' county')) continue;
        if (!seenLower.has(cl)) {
          seenLower.add(cl);
          cleanStudioTags.push(cleaned);
        }
      }
    }
  }

  const totalCleanTagsCount = userTaughtTags.length + cleanStudioTags.length;
  const rawContextNote = String(details.user_context_notes || '')
    .replace('[CLEARED_SLATE]', '')
    .trim();
  const displayContextNote =
    /^(?:bro\s+just\s+look|just\s+look\s+at\s+it|look\s+closely)/i.test(rawContextNote)
      ? ''
      : rawContextNote;

  // Countable discrete subjects present on this frame (for Active Vector Reclassification)
  const COUNTABLE_SUBJECT_SET = new Set([
    'bird', 'birds', 'frog', 'frogs', 'dog', 'dogs', 'cat', 'cats', 'cat tree', 'horse', 'horses',
    'deer', 'bison', 'bear', 'bears', 'wildlife', 'person', 'people', 'man', 'men',
    'woman', 'women', 'mirror selfie', 'boat', 'boats', 'ship', 'ships', 'car', 'cars',
    'sports car', 'sedan', 'gas station', 'train', 'trains',
    'airplane', 'airplanes', 'statue', 'statues', 'sculpture', 'framed picture', 'framed art',
  ]);

  const activeSubjectTargets = [];
  const seenSubjectLower = new Set();
  for (const sb of subjectBoxes) {
    const lbl = String(sb.label || '').trim();
    if (lbl && !seenSubjectLower.has(lbl.toLowerCase())) {
      seenSubjectLower.add(lbl.toLowerCase());
      activeSubjectTargets.push({
        label: lbl,
        confidence: sb.confidence,
        margin: sb.margin,
        bbox: sb.bbox,
        hasBox: true,
      });
    }
  }
  for (const vs of verifiedSubjects) {
    const lbl = String(vs.label || '').trim();
    if (lbl && !seenSubjectLower.has(lbl.toLowerCase())) {
      seenSubjectLower.add(lbl.toLowerCase());
      activeSubjectTargets.push({
        label: lbl,
        confidence: vs.confidence,
        margin: vs.margin,
        bbox: null,
        hasBox: false,
      });
    }
  }
  for (const kw of [...userTaughtTags, ...cleanStudioTags]) {
    const kl = kw.toLowerCase();
    if (COUNTABLE_SUBJECT_SET.has(kl) && !seenSubjectLower.has(kl)) {
      seenSubjectLower.add(kl);
      activeSubjectTargets.push({
        label: kw,
        confidence: null,
        margin: null,
        bbox: null,
        hasBox: false,
      });
    }
  }

  const RECLASSIFY_PRESETS = [
    'Statue',
    'Framed Picture',
    'Rock / Log',
    'Tree / Branch',
    'Water Reflection',
    'Person',
  ];

  const hasAnyLocation = Boolean(
    (details.sub_location && details.sub_location.trim()) ||
      (details.specific_location && details.specific_location.trim()) ||
      (details.city && details.city.trim()) ||
      (details.state_region && details.state_region.trim()) ||
      (details.country && details.country.trim())
  );

  const locationProvenance = String(details.location_provenance || '').toLowerCase();
  const getProvenanceBadge = () => {
    if (!hasAnyLocation) {
      return {
        label: 'Blank (Unverified)',
        cls: 'bg-zinc-800/80 border-zinc-600/60 text-zinc-400',
      };
    }
    if (details.gps_ground_truth === 1 || locationProvenance === 'gps') {
      return {
        label: '🛰️ GPS Verified',
        cls: 'bg-emerald-950/60 border-emerald-500/50 text-emerald-300',
      };
    }
    if (locationProvenance === 'user') {
      return {
        label: '🎙️ User Verified',
        cls: 'bg-purple-950/60 border-purple-400/60 text-purple-200',
      };
    }
    if (locationProvenance === 'lrcat') {
      return {
        label: '📚 Catalog Verified',
        cls: 'bg-blue-950/60 border-blue-400/60 text-blue-200',
      };
    }
    if (locationProvenance === 'landmark' || locationProvenance === 'filename') {
      return {
        label: '🏛️ Landmark Verified',
        cls: 'bg-amber-950/60 border-amber-400/60 text-amber-200',
      };
    }
    return {
      label: 'Verified',
      cls: 'bg-emerald-950/50 border-emerald-500/40 text-emerald-300',
    };
  };
  const provBadge = getProvenanceBadge();

  return (
    <div className="fixed inset-0 z-50 bg-black/95 flex flex-col backdrop-blur-md select-none text-studio-text">
      {/* Top Header Bar */}
      <div className="h-12 bg-studio-panel border-b border-studio-border flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="p-1 hover:bg-studio-hover text-studio-textMuted hover:text-white rounded-sm transition-colors"
            title="Close Lightbox (Esc or press G for Main Grid)"
          >
            <X className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-white font-medium">{filename}</span>
            {totalCount > 0 && (
              <span className="px-1.5 py-0.5 bg-studio-bg text-studio-textMuted text-[10px] font-mono border border-studio-border rounded-sm">
                {activeIndex + 1} / {totalCount}
              </span>
            )}
            {details.sibling_path && (
              <span className="px-1.5 py-0.5 bg-blue-500/20 text-blue-300 text-[10px] font-mono border border-blue-500/40 rounded-sm">
                RAW + TIF Sibling
              </span>
            )}
            {details.is_sequence_hero === 1 && (
              <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-300 text-[10px] font-mono border border-emerald-500/40 rounded-sm">
                ★ SEQUENCE HERO
              </span>
            )}
          </div>
        </div>

        {/* Streamlined Top Action Bar: Subject Regions | Undo (Cmd+Z) | +Add to Book | Open In ▾ | Sync Edits */}
        <div className="flex items-center gap-2">
          {subjectBoxes.length > 0 && (
            <button
              type="button"
              onClick={() => setShowSubjectBoxes((prev) => !prev)}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border transition-colors cursor-pointer ${
                showSubjectBoxes
                  ? 'bg-cyan-950/70 border-cyan-400 text-cyan-200 shadow-sm'
                  : 'bg-studio-bg border-studio-border hover:border-cyan-400/70 text-cyan-300/90 hover:text-white'
              }`}
              title="Toggle localized subject verification boxes & active vector boundary controls"
            >
              <Eye className="w-3.5 h-3.5 text-cyan-400" />
              <span>
                🎯 Subject Regions ({subjectBoxes.length})
              </span>
            </button>
          )}

          <button
            type="button"
            disabled={!undoStatus?.available}
            onClick={() => onTriggerUndo && onTriggerUndo()}
            className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded-sm border transition-colors ${
              undoStatus?.available
                ? 'bg-sky-950/50 border-sky-400/70 text-sky-200 hover:bg-sky-900/60 hover:text-white cursor-pointer'
                : 'bg-studio-bg/50 border-studio-border text-studio-textDim opacity-60 cursor-not-allowed'
            }`}
            title={
              undoStatus?.available
                ? `Undo (Cmd+Z): ${undoStatus.latest?.description || 'Revert last studio action'}`
                : 'No studio actions to undo yet (Cmd+Z)'
            }
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>↩ Undo</span>
            {undoStatus?.count > 0 && (
              <span className="px-1.5 py-0.2 bg-sky-500/30 text-sky-200 rounded-full text-[10px] font-bold">
                {undoStatus.count}
              </span>
            )}
          </button>

          <CollectionPopover
            photo={details}
            collections={collections}
            onTogglePhotoInCollection={onTogglePhotoInCollection}
            onCreateCollectionWithPhoto={onCreateCollectionWithPhoto}
            onOpenCollectionsModal={onOpenCollectionsModal}
          />

          {/* Consolidated Open In ▾ Dropdown Menu */}
          <div ref={openInMenuRef} className="relative">
            <button
              type="button"
              onClick={() => setOpenInMenuOpen((prev) => !prev)}
              className="flex items-center gap-1.5 bg-studio-bg border border-studio-border hover:border-cyan-400 px-3 py-1 text-xs font-mono text-studio-text hover:text-white rounded-sm transition-colors cursor-pointer"
              title="Open this photo in Adobe Photoshop (P), Lightroom Classic (L), or macOS Finder (F)"
            >
              <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
              <span>Open In</span>
              <ChevronDown className="w-3.5 h-3.5 text-studio-textMuted" />
            </button>

            {openInMenuOpen && (
              <div className="absolute right-0 mt-1.5 w-56 bg-studio-panel border border-studio-borderLight rounded-md shadow-2xl z-50 p-1.5 font-mono text-xs space-y-1">
                <button
                  type="button"
                  onClick={() => {
                    setOpenInMenuOpen(false);
                    handleOpenApp('photoshop');
                  }}
                  className="w-full text-left px-2.5 py-2 rounded hover:bg-studio-hover flex items-center justify-between text-white transition-colors cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <span>🎨</span>
                    <span>Adobe Photoshop</span>
                  </span>
                  <span className="text-[10px] text-studio-textDim px-1.5 py-0.5 bg-studio-bg border border-studio-border rounded">
                    P
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setOpenInMenuOpen(false);
                    handleOpenApp('lightroom');
                  }}
                  className="w-full text-left px-2.5 py-2 rounded hover:bg-studio-hover flex items-center justify-between text-white transition-colors cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <span>📷</span>
                    <span>Adobe Lightroom</span>
                  </span>
                  <span className="text-[10px] text-studio-textDim px-1.5 py-0.5 bg-studio-bg border border-studio-border rounded">
                    L
                  </span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setOpenInMenuOpen(false);
                    handleOpenApp('finder');
                  }}
                  className="w-full text-left px-2.5 py-2 rounded hover:bg-studio-hover flex items-center justify-between text-white transition-colors cursor-pointer"
                >
                  <span className="flex items-center gap-2">
                    <span>📂</span>
                    <span>Reveal in Finder</span>
                  </span>
                  <span className="text-[10px] text-studio-textDim px-1.5 py-0.5 bg-studio-bg border border-studio-border rounded">
                    F
                  </span>
                </button>
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleSyncPhotoEdits}
            disabled={syncingEdits}
            className="flex items-center gap-1.5 bg-studio-bg border border-studio-border hover:border-emerald-400 px-2.5 py-1 text-xs font-mono text-emerald-300 hover:text-white rounded-sm transition-colors disabled:opacity-50 cursor-pointer"
            title="Re-sync modified TIFF/RAW previews & vector or ingest newly saved Photoshop derivatives"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${syncingEdits ? 'animate-spin' : ''}`} />
            <span>{syncingEdits ? 'Syncing...' : '🔄 Sync Edits'}</span>
          </button>
        </div>
      </div>

      {/* Main Inspection View: Left Viewer + Right Metadata Sidebar */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: High-Res 1600px Preview with Navigation Chevrons */}
        <div className="flex-1 relative flex items-center justify-center p-4 bg-black overflow-hidden">
          {/* Previous Frame Button */}
          <button
            onClick={onNavigatePrev}
            className="absolute left-4 top-1/2 -translate-y-1/2 p-2.5 bg-studio-panel/80 hover:bg-studio-panel text-white/70 hover:text-white border border-studio-border rounded-sm backdrop-blur-sm transition-all hover:scale-105 z-20"
            title="Previous Photo (Left Arrow)"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>

          {/* Main High-Res Image + Optional Localized Subject Box Overlays */}
          {previewSrc ? (
            <div className="relative inline-flex items-center justify-center max-h-full max-w-full">
              <img
                src={previewSrc}
                alt={filename}
                className="max-h-[calc(100vh-9.5rem)] max-w-full object-contain select-none shadow-2xl block"
              />
              {showSubjectBoxes &&
                subjectBoxes.map((sb, idx) => {
                  const [bx, by, bw, bh] = sb.bbox;
                  const pctLeft = `${Math.max(0, Math.min(96, bx * 100))}%`;
                  const pctTop = `${Math.max(0, Math.min(96, by * 100))}%`;
                  const pctWidth = `${Math.max(4, Math.min(100 - bx * 100, bw * 100))}%`;
                  const pctHeight = `${Math.max(4, Math.min(100 - by * 100, bh * 100))}%`;
                  const confPct = sb.confidence
                    ? `${Math.round(Number(sb.confidence) * 100)}%`
                    : '';
                  return (
                    <div
                      key={`sbox-${idx}-${sb.label}`}
                      style={{
                        left: pctLeft,
                        top: pctTop,
                        width: pctWidth,
                        height: pctHeight,
                      }}
                      className="absolute border-2 border-cyan-400 bg-cyan-500/10 rounded-sm shadow-lg z-30 pointer-events-auto transition-all"
                    >
                      <div className="absolute -top-7 left-0 flex items-center gap-1 bg-zinc-950/95 border border-cyan-400/80 px-2 py-0.5 rounded-sm font-mono text-[10px] text-cyan-200 whitespace-nowrap shadow-xl">
                        <span className="font-bold text-white">{sb.label}</span>
                        {confPct && <span className="text-cyan-400">{confPct}</span>}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setReclassifyTarget({
                              label: sb.label,
                              bbox: sb.bbox,
                            });
                          }}
                          className="ml-1 px-1 py-0.2 bg-amber-500/20 hover:bg-amber-500 text-amber-200 hover:text-zinc-950 border border-amber-400/60 rounded text-[9px] font-semibold transition-colors cursor-pointer"
                          title={`Reclassify "${sb.label}" (e.g., Statue, Framed Picture, Rock) & train vector boundary`}
                        >
                          ↻ Reclassify
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleReclassifySubject(sb.label, '', 'dismiss', sb.bbox);
                          }}
                          className="px-1 py-0.2 bg-rose-950/80 hover:bg-rose-600 text-rose-200 hover:text-white border border-rose-500/60 rounded text-[9px] font-bold transition-colors cursor-pointer"
                          title={`Dismiss false "${sb.label}" detection & penalize vector boundary`}
                        >
                          ×
                        </button>
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <div className="text-center font-mono text-sm text-studio-textDim">
              No High-Res Preview Available
            </div>
          )}

          {/* Next Frame Button */}
          <button
            onClick={onNavigateNext}
            className="absolute right-4 top-1/2 -translate-y-1/2 p-2.5 bg-studio-panel/80 hover:bg-studio-panel text-white/70 hover:text-white border border-studio-border rounded-sm backdrop-blur-sm transition-all hover:scale-105 z-20"
            title="Next Photo (Right Arrow)"
          >
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>

        {/* Right: Studio Metadata Sidebar & Similarity Tabs */}
        <div className="w-96 bg-studio-panel border-l border-studio-border flex flex-col overflow-y-auto text-xs font-sans">
          {/* Quick Rating Bar */}
          <div className="p-3 border-b border-studio-border bg-studio-bg flex items-center justify-between">
            <span className="font-mono text-studio-textDim text-[11px] uppercase tracking-wider">
              Rating (1–5 keys)
            </span>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((s) => (
                <button
                  key={s}
                  onClick={() => handleSetRating(s === currentStars ? 0 : s)}
                  className="p-1 hover:scale-110 transition-transform"
                  title={`Set ${s} stars (Press ${s})`}
                >
                  <Star
                    className={`w-4 h-4 ${
                      currentStars >= s
                        ? 'text-studio-gold fill-studio-gold'
                        : 'text-studio-borderLight hover:text-studio-gold/60'
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* Technical Quality Metrics */}
          <div className="p-3 border-b border-studio-border grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="p-2 bg-studio-bg border border-studio-border rounded-sm">
              <span className="text-studio-textDim block text-[10px]">Aesthetic Score</span>
              <span className="text-white font-medium text-xs">
                {details.aesthetic_score !== null && details.aesthetic_score !== undefined
                  ? Number(details.aesthetic_score).toFixed(2)
                  : 'N/A'}
              </span>
            </div>
            <div className="p-2 bg-studio-bg border border-studio-border rounded-sm">
              <span className="text-studio-textDim block text-[10px]">Patch Sharpness (90%)</span>
              <span className={`text-xs font-medium ${details.is_unsharp ? 'text-studio-crimson' : 'text-studio-emerald'}`}>
                {details.sharpness_score !== null && details.sharpness_score !== undefined
                  ? `${Number(details.sharpness_score).toFixed(1)} ${details.is_unsharp ? '(Unsharp)' : '(Sharp)'}`
                  : 'N/A'}
              </span>
            </div>
          </div>

          {/* Prominent Keywords & Studio Tags + 3-Button AI Tag Control Group */}
          <div className="p-3.5 border-b border-studio-border space-y-2.5 bg-studio-bg/30">
            {/* 3-Button AI Tag Control Group */}
            <div className="grid grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={handleClearPhotoTags}
                disabled={clearingTags || reassessing}
                className="flex items-center justify-center gap-1 py-2 px-2 rounded-md bg-amber-950/40 hover:bg-amber-900/60 border border-amber-500/50 hover:border-amber-400 text-amber-200 hover:text-white font-mono text-[11px] font-semibold transition-colors disabled:opacity-50 cursor-pointer shadow-sm"
                title="Clear all tags on this photo so you can start fresh (Undo snapshot saved automatically)"
              >
                <span>🧹</span>
                <span>{clearingTags ? 'Clearing...' : 'Clear Tags'}</span>
              </button>

              <button
                type="button"
                onClick={() => handleReassessPhoto('fast_vectors')}
                disabled={reassessing || clearingTags}
                className="flex items-center justify-center gap-1 py-2 px-2 rounded-md bg-blue-950/50 hover:bg-blue-900/70 border border-blue-500/50 hover:border-blue-400 text-blue-200 hover:text-white font-mono text-[11px] font-semibold transition-colors disabled:opacity-50 cursor-pointer shadow-sm"
                title="Immediately run a fast OpenCLIP vector & ontology probe on this photo (<1s)"
              >
                <span>⚡</span>
                <span>{reassessing ? 'Tagging...' : 'Basic Tag'}</span>
              </button>

              <button
                type="button"
                onClick={() =>
                  onOpenVoiceTeachForPhoto && onOpenVoiceTeachForPhoto(details, true)
                }
                disabled={clearingTags || reassessing}
                className="flex items-center justify-center gap-1 py-2 px-2 rounded-md bg-purple-900/60 hover:bg-purple-800/80 border border-purple-400/70 hover:border-purple-300 text-purple-100 hover:text-white font-mono text-[11px] font-bold transition-colors disabled:opacity-50 cursor-pointer shadow-sm"
                title="Open AI Voice Tagging & immediately start listening to your microphone"
              >
                <span>🎙️</span>
                <span>AI Voice Tag</span>
              </button>
            </div>

            {/* Verified Countable Subjects & Active Vector Boundary Controls */}
            {activeSubjectTargets.length > 0 && (
              <div className="p-2 rounded bg-cyan-950/30 border border-cyan-500/40 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-cyan-300 font-semibold">
                    🎯 Verified Subjects & Vector Learning
                  </span>
                  {subjectBoxes.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setShowSubjectBoxes((prev) => !prev)}
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono border transition-colors cursor-pointer ${
                        showSubjectBoxes
                          ? 'bg-cyan-500 text-zinc-950 border-cyan-300 font-bold'
                          : 'bg-studio-bg text-cyan-300 border-cyan-500/50 hover:border-cyan-300'
                      }`}
                      title="Toggle bounding boxes on the main photo"
                    >
                      {showSubjectBoxes ? '👁 Hide Boxes' : `👁 Show Boxes (${subjectBoxes.length})`}
                    </button>
                  )}
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {activeSubjectTargets.map((st, idx) => (
                    <div
                      key={`vst-${idx}-${st.label}`}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm bg-studio-bg border border-cyan-500/50 text-cyan-100 font-mono text-[11px]"
                    >
                      <button
                        type="button"
                        onClick={() => onTagClick && onTagClick(st.label)}
                        className="hover:text-cyan-300 font-semibold cursor-pointer"
                        title={`Filter archive by verified subject: ${st.label}`}
                      >
                        {st.label}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setReclassifyTarget(
                            reclassifyTarget?.label === st.label
                              ? null
                              : { label: st.label, bbox: st.bbox }
                          )
                        }
                        className="ml-0.5 px-1 py-0.2 rounded bg-amber-500/20 hover:bg-amber-500 text-amber-200 hover:text-zinc-950 text-[9px] font-semibold transition-colors cursor-pointer"
                        title={`Reclassify "${st.label}" (e.g., Statue, Framed Picture, Rock) & train vector boundary`}
                      >
                        ↻
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          handleReclassifySubject(st.label, '', 'dismiss', st.bbox)
                        }
                        disabled={reclassifying}
                        className="px-1 py-0.2 rounded bg-rose-950/70 hover:bg-rose-600 text-rose-300 hover:text-white text-[10px] font-bold transition-colors cursor-pointer"
                        title={`Dismiss false "${st.label}" detection & train OpenCLIP vector boundary`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Quick Reclassification Popover (Statue, Framed Picture, Rock/Log, etc.) */}
            {reclassifyTarget && (
              <div className="p-2.5 rounded bg-zinc-900/95 border border-amber-400/70 space-y-2 shadow-xl">
                <div className="flex items-center justify-between font-mono text-[11px]">
                  <span className="text-amber-200 font-semibold">
                    ↻ Reclassify <span className="text-white">"{reclassifyTarget.label}"</span> as:
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setReclassifyTarget(null);
                      setCustomReclassifyInput('');
                    }}
                    className="text-studio-textMuted hover:text-white text-xs px-1 cursor-pointer"
                  >
                    ×
                  </button>
                </div>
                <div className="flex flex-wrap gap-1">
                  {RECLASSIFY_PRESETS.map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      disabled={reclassifying}
                      onClick={() =>
                        handleReclassifySubject(
                          reclassifyTarget.label,
                          preset,
                          'reclassify',
                          reclassifyTarget.bbox
                        )
                      }
                      className="px-2 py-1 rounded bg-studio-bg hover:bg-amber-500 text-amber-100 hover:text-zinc-950 border border-amber-500/40 font-mono text-[10px] font-semibold transition-colors cursor-pointer"
                    >
                      {preset}
                    </button>
                  ))}
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!customReclassifyInput.trim()) return;
                    handleReclassifySubject(
                      reclassifyTarget.label,
                      customReclassifyInput.trim(),
                      'reclassify',
                      reclassifyTarget.bbox
                    );
                  }}
                  className="flex items-center gap-1"
                >
                  <input
                    type="text"
                    value={customReclassifyInput}
                    onChange={(e) => setCustomReclassifyInput(e.target.value)}
                    placeholder="Or type custom concept..."
                    className="flex-1 bg-studio-bg border border-studio-border focus:border-amber-400 rounded px-2 py-1 text-[11px] font-mono text-white outline-none"
                  />
                  <button
                    type="submit"
                    disabled={!customReclassifyInput.trim() || reclassifying}
                    className="px-2 py-1 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 text-zinc-950 font-mono text-[10px] font-bold rounded cursor-pointer"
                  >
                    Save
                  </button>
                </form>
              </div>
            )}

            <div className="flex items-center justify-between text-white font-medium font-mono text-xs pt-0.5">
              <div className="flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-studio-accent" />
                <span>Keywords & Studio Tags</span>
                <span className="text-[10px] text-studio-textDim">
                  ({totalCleanTagsCount})
                </span>
              </div>

              <button
                type="button"
                onClick={() => handleReassessPhoto('deep_vlm')}
                disabled={reassessing || clearingTags}
                className="flex items-center gap-1 px-2 py-0.5 rounded-sm bg-studio-bg hover:bg-studio-hover border border-studio-borderLight text-emerald-300 hover:text-white text-[10px] font-mono transition-colors disabled:opacity-50 cursor-pointer"
                title="Re-run Qwen2.5-VL 7B Deep Vision Model (~3s)"
              >
                <Cpu className={`w-2.5 h-2.5 ${reassessing ? 'animate-spin' : ''}`} />
                <span>🧠 Deep VLM</span>
              </button>
            </div>

            {totalCleanTagsCount > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {userTaughtTags.map((ut, i) => (
                  <div
                    key={`ut-${i}`}
                    className="inline-flex items-center bg-purple-950/75 border border-purple-400/80 hover:border-amber-300 text-purple-100 text-[11px] font-mono font-semibold rounded-sm transition-colors shadow-sm"
                  >
                    <button
                      type="button"
                      onClick={() => onTagClick && onTagClick(ut)}
                      className="px-2 py-1 hover:text-white flex items-center gap-1 cursor-pointer"
                      title={`Photographer-taught tag (locked): ${ut} — click to filter archive`}
                    >
                      <span className="text-[10px]">🎙️</span>
                      <span>{ut}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReclassifySubject(ut, '', 'dismiss', null)}
                      disabled={reclassifying}
                      className="pr-1.5 pl-0.5 py-1 text-purple-300/70 hover:text-rose-300 font-bold cursor-pointer"
                      title={`Remove "${ut}"`}
                    >
                      ×
                    </button>
                  </div>
                ))}
                {cleanStudioTags.map((kw, i) => (
                  <div
                    key={`f-${i}`}
                    className="group inline-flex items-center bg-studio-bg border border-studio-borderLight hover:border-studio-accent text-white text-[11px] font-mono rounded-sm transition-colors"
                  >
                    <button
                      type="button"
                      onClick={() => onTagClick && onTagClick(kw)}
                      className="px-2 py-0.5 hover:text-studio-accent cursor-pointer"
                      title={`Filter archive by tag: ${kw}`}
                    >
                      {kw}
                    </button>
                    <button
                      type="button"
                      onClick={() => handleReclassifySubject(kw, '', 'dismiss', null)}
                      disabled={reclassifying}
                      className="pr-1.5 pl-0.5 py-0.5 text-studio-textDim hover:text-rose-400 font-bold cursor-pointer"
                      title={`Dismiss tag "${kw}" & update OpenCLIP vector boundary`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[11px] font-mono text-studio-textDim py-1">
                {isSlateCleared
                  ? '🧹 Tags cleared — click ⚡ Basic Tag or 🎙️ AI Voice Tag above'
                  : 'No keywords on this frame — click ⚡ Basic Tag or 🎙️ AI Voice Tag'}
              </div>
            )}

            {/* User-taught context notes if present */}
            {displayContextNote && (
              <div className="mt-2 p-2 rounded bg-purple-950/35 border border-purple-500/40 text-[11px] font-mono text-purple-200 leading-snug">
                <div className="text-[9px] uppercase tracking-wider text-purple-300 font-bold mb-0.5">
                  🎙️ Photographer Context Note
                </div>
                <div>{displayContextNote}</div>
              </div>
            )}
          </div>

          {/* Camera & Exposure Specs */}
          <div className="p-3 border-b border-studio-border space-y-1.5">
            <div className="flex items-center gap-1.5 text-white font-medium font-mono text-xs mb-2">
              <Camera className="w-3.5 h-3.5 text-studio-accent" />
              <span>Camera & Exposure</span>
            </div>
            <div className="grid grid-cols-2 gap-x-2 gap-y-1 font-mono text-[11px] text-studio-textMuted">
              <div>Make: <span className="text-studio-text">{details.camera_make || 'Phase One / Unknown'}</span></div>
              <div>Model: <span className="text-studio-text">{details.camera_model || '—'}</span></div>
              <div>Lens: <span className="text-studio-text truncate block">{details.lens_model || '—'}</span></div>
              <div>Focal: <span className="text-studio-text">{details.focal_length || '—'}</span></div>
              <div>Shutter: <span className="text-studio-text">{details.shutter_speed || '—'}</span></div>
              <div>Aperture: <span className="text-studio-text">{details.aperture ? `f/${details.aperture}` : '—'}</span></div>
              <div>ISO: <span className="text-studio-text">{details.iso || '—'}</span></div>
              <div>Date: <span className="text-studio-text">{details.shoot_date || '—'}</span></div>
            </div>
          </div>

          {/* Strict Location Provenance & 1-Click Location Controls (Always Visible) */}
          <div className="p-3 border-b border-studio-border space-y-2 bg-studio-bg/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-white font-medium font-mono text-xs">
                <MapPin className="w-3.5 h-3.5 text-studio-gold" />
                <span>Location Metadata</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span
                  className={`px-1.5 py-0.5 text-[9px] font-mono border rounded-sm ${provBadge.cls}`}
                  title="Location Provenance — Blank by default unless verified by GPS, Catalog, Landmark, or Photographer"
                >
                  {provBadge.label}
                </span>
                {hasAnyLocation && (
                  <button
                    type="button"
                    onClick={handleClearLocation}
                    disabled={updatingLocation}
                    className="px-1.5 py-0.5 rounded-sm bg-rose-950/60 hover:bg-rose-700 border border-rose-500/50 text-rose-200 hover:text-white font-mono text-[10px] font-semibold transition-colors disabled:opacity-50 cursor-pointer"
                    title="Clear location to blank & block false location guess from returning (Cmd+Z to undo)"
                  >
                    × Clear
                  </button>
                )}
              </div>
            </div>

            {hasAnyLocation ? (
              <div className="text-xs text-studio-text space-y-0.5 pl-0.5">
                {details.sub_location && (
                  <div className="font-medium text-white">{details.sub_location}</div>
                )}
                {details.specific_location &&
                  details.specific_location !== details.sub_location && (
                    <div className="text-amber-200 font-medium">{details.specific_location}</div>
                  )}
                <div className="text-[11px] font-mono text-studio-textDim">
                  {[details.city, details.state_region, details.country]
                    .filter(Boolean)
                    .join(', ')}
                </div>
              </div>
            ) : (
              <div className="text-[11px] font-mono text-studio-textDim italic">
                No verified location assigned (strictly blank by default).
              </div>
            )}

            {/* Quick Inline Set Location Input with Verified Catalog Autocomplete */}
            <form onSubmit={handleSetLocation} className="flex items-center gap-1.5 pt-0.5">
              <input
                type="text"
                list="verified-studio-locations-datalist"
                value={locationInput}
                onChange={(e) => setLocationInput(e.target.value)}
                placeholder={
                  hasAnyLocation
                    ? 'Override location (e.g. Port of LA, California)...'
                    : 'Set verified location (e.g. Mono Lake, Cuba)...'
                }
                className="flex-1 bg-studio-bg border border-studio-border focus:border-amber-400 rounded-sm px-2 py-1 text-[11px] font-mono text-white placeholder:text-studio-textDim outline-none"
              />
              <datalist id="verified-studio-locations-datalist">
                {locationSuggestions.map((loc, i) => (
                  <option key={`loc-sug-${i}`} value={loc.label} />
                ))}
              </datalist>
              <button
                type="submit"
                disabled={!locationInput.trim() || updatingLocation}
                className="px-2.5 py-1 bg-amber-500/25 hover:bg-amber-500 border border-amber-500/60 text-amber-200 hover:text-zinc-950 font-mono text-[10px] font-semibold rounded-sm transition-colors disabled:opacity-40 cursor-pointer shrink-0"
                title="Save verified location (Enter)"
              >
                {updatingLocation ? '...' : 'Set'}
              </button>
            </form>
          </div>

          {/* Triple Similarity & "On This Day" Section */}
          <div className="p-3 border-b border-studio-border flex flex-col flex-1">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center bg-studio-bg border border-studio-border p-0.5 rounded-sm w-full justify-between">
                <button
                  onClick={() => setSimilarityMode('visual')}
                  className={`text-[10px] font-mono px-2 py-1 rounded-sm transition-colors flex-1 text-center ${
                    similarityMode === 'visual'
                      ? 'bg-studio-accent text-white font-medium'
                      : 'text-studio-textMuted hover:text-white'
                  }`}
                  title="Global cosine similarity across OpenCLIP vectors"
                >
                  Visually Similar
                </button>
                <button
                  onClick={() => setSimilarityMode('orbit')}
                  className={`text-[10px] font-mono px-2 py-1 rounded-sm transition-colors flex-1 text-center ${
                    similarityMode === 'orbit'
                      ? 'bg-studio-accent text-white font-medium'
                      : 'text-studio-textMuted hover:text-white'
                  }`}
                  title="Same-day, same-camera +-10 min shoot window (oblique + nadir angles)"
                >
                  Orbit (±10m)
                </button>
                <button
                  onClick={() => setSimilarityMode('sameday')}
                  className={`text-[10px] font-mono px-2 py-1 rounded-sm transition-colors flex-1 text-center ${
                    similarityMode === 'sameday'
                      ? 'bg-amber-500 text-zinc-950 font-semibold'
                      : 'text-amber-300/90 hover:text-white'
                  }`}
                  title="All captures from this shoot date ordered chronologically"
                >
                  📅 Same Day ({sameDayPhotos.length})
                </button>
              </div>
              {loadingSimilar && (
                <div className="w-3 h-3 ml-1.5 border border-studio-accent border-t-transparent rounded-full animate-spin shrink-0"></div>
              )}
            </div>

            {/* 1-Click "Open Full Day in Main Grid" Button when in Same Day tab */}
            {similarityMode === 'sameday' &&
              details.shoot_date &&
              details.shoot_date !== 'Undated' && (
                <button
                  type="button"
                  onClick={() =>
                    onOpenFullDayInGrid &&
                    onOpenFullDayInGrid(details.shoot_date, sameDayPhotos)
                  }
                  className="mb-2 w-full py-1.5 px-2.5 bg-amber-500/20 hover:bg-amber-500 text-amber-300 hover:text-zinc-950 border border-amber-500/50 rounded-sm font-mono text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-colors shadow-sm"
                >
                  <LayoutGrid className="w-3.5 h-3.5" />
                  <span>
                    ⊞ Open Full Day in Main Grid ({sameDayPhotos.length}{' '}
                    {sameDayPhotos.length === 1 ? 'photo' : 'photos'})
                  </span>
                </button>
              )}

            {/* Similarity / Same Day Thumbnails Grid */}
            <div className="grid grid-cols-4 gap-1.5 overflow-y-auto max-h-48 pr-1">
              {similarPhotos.length > 0 ? (
                similarPhotos.map((sim) => {
                  const sThumb = sim.thumb_url || (sim.thumb_360_path ? `/previews/thumbs_360/${sim.thumb_360_path.split('/').pop()}` : null);
                  const isCurrent = sim.file_path === details.file_path;
                  return (
                    <div
                      key={sim.file_path || sim.file_hash}
                      onClick={() => onSelectPhoto(sim, similarPhotos)}
                      className={`group relative aspect-square bg-studio-bg border cursor-pointer overflow-hidden rounded-sm ${
                        isCurrent
                          ? 'border-2 border-amber-400 ring-1 ring-amber-400/50'
                          : 'border-studio-border hover:border-studio-accent'
                      }`}
                      title={`${sim.file_path.split('/').pop()} ${
                        sim.similarity !== undefined
                          ? `(Cos Sim: ${(sim.similarity * 100).toFixed(0)}%)`
                          : sim.time_delta_seconds !== undefined
                          ? `(Δt: ${Math.round(sim.time_delta_seconds)}s)`
                          : sim.exif_time || ''
                      }`}
                    >
                      {sThumb && (
                        <img
                          src={sThumb}
                          alt="similar"
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        />
                      )}
                      {isCurrent && (
                        <div className="absolute top-0.5 left-0.5 px-1 bg-amber-500 text-zinc-950 font-mono text-[8px] font-bold rounded-sm">
                          NOW
                        </div>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="col-span-4 text-center py-4 font-mono text-[10px] text-studio-textDim">
                  {loadingSimilar ? 'Searching frames...' : 'No matching frames found'}
                </div>
              )}
            </div>
          </div>

          {/* Master File Paths */}
          <div className="p-3 border-t border-studio-border bg-studio-bg/60 font-mono text-[10px] text-studio-textDim space-y-1">
            <div className="flex items-center justify-between">
              <span className="truncate max-w-[280px]" title={details.file_path}>
                RAW: {details.file_path}
              </span>
              <button
                onClick={copyPath}
                className="text-studio-textDim hover:text-white p-1"
                title="Copy master path"
              >
                {copiedPath ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
              </button>
            </div>
            {details.sibling_path && (
              <div className="truncate text-blue-400/80" title={details.sibling_path}>
                TIF: {details.sibling_path}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Persistent Bottom -5 / +5 Chronological Neighbor Filmstrip */}
      <div className="h-20 bg-studio-panel border-t border-studio-border flex items-center px-4 gap-2 shrink-0 overflow-x-auto">
        <div className="flex items-center gap-1 shrink-0 font-mono text-[10px] text-studio-textDim uppercase tracking-wider mr-2">
          <span>Shoot Filmstrip (-5 / +5):</span>
        </div>

        <div className="flex items-center gap-2 overflow-x-auto py-1">
          {neighbors.map((nb) => {
            const isCurrent = nb.is_current;
            const nbThumb = nb.thumb_url || (nb.thumb_360_path ? `/previews/thumbs_360/${nb.thumb_360_path.split('/').pop()}` : null);
            const nbFilename = nb.file_path ? nb.file_path.split('/').pop() : '';

            return (
              <div
                key={nb.file_path || nb.file_hash}
                onClick={() => onSelectPhoto(nb, neighbors)}
                className={`relative w-16 h-14 bg-studio-bg shrink-0 rounded-sm overflow-hidden cursor-pointer transition-all ${
                  isCurrent
                    ? 'border-2 border-studio-accent ring-2 ring-studio-accent/30 scale-105 z-10'
                    : 'border border-studio-border hover:border-studio-borderLight opacity-70 hover:opacity-100'
                }`}
                title={`${nbFilename} (${nb.exif_time || ''})`}
              >
                {nbThumb && (
                  <img
                    src={nbThumb}
                    alt={nbFilename}
                    className="w-full h-full object-cover"
                  />
                )}
                {nb.star_rating > 0 && (
                  <div className="absolute bottom-0 right-0 px-1 py-0.2 bg-black/80 text-[8px] font-mono text-studio-gold">
                    ★{nb.star_rating}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Toast Feedback Notification */}
      {toastMessage && (
        <div className="fixed bottom-24 right-8 bg-studio-panel border border-studio-borderLight text-white px-3 py-2 rounded-sm shadow-2xl text-xs font-mono z-50 flex items-center gap-2">
          <span className="w-2 h-2 rounded-sm bg-studio-accent animate-ping"></span>
          <span>{toastMessage}</span>
        </div>
      )}
    </div>
  );
}

