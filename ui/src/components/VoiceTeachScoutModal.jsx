import React, { useState, useEffect, useRef, useMemo } from 'react'

const API_BASE = ''

export default function VoiceTeachScoutModal({
  isOpen,
  initialMode = 'teach', // 'teach' | 'scout'
  selectedPhotos = [],
  autoStartRecording = false,
  onClearAutoStart = null,
  onClose,
  onPhotosUpdated,
  onTeachApplied,
  onScoutCompleted,
  onOpenCollection,
  onViewPhotosInGrid,
  onTriggerUndo,
}) {
  const [activeTab, setActiveTab] = useState(initialMode)
  const [instruction, setInstruction] = useState('')
  const [wipeExisting, setWipeExisting] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [speechSupported, setSpeechSupported] = useState(false)
  const [speechStatus, setSpeechStatus] = useState('')
  const [isAssessing, setIsAssessing] = useState(false)

  // Interactive Pre-Commit Review state (Teach Mode)
  const [previewData, setPreviewData] = useState(null)
  const [approvedSpokenTags, setApprovedSpokenTags] = useState([])
  const [approvedVisualTags, setApprovedVisualTags] = useState([])
  const [approvedRemoveTags, setApprovedRemoveTags] = useState([])
  const [dismissedTags, setDismissedTags] = useState([])
  const [manualTagInput, setManualTagInput] = useState('')
  const [targetCollection, setTargetCollection] = useState(null)

  // Shoot Session & Visual Orbit Propagation state
  const [orbitCandidates, setOrbitCandidates] = useState([])
  const [selectedOrbitIds, setSelectedOrbitIds] = useState(new Set())
  const [isOrbitExpanded, setIsOrbitExpanded] = useState(true)
  const [orbitFilterScope, setOrbitFilterScope] = useState('all') // 'burst' | 'window' | 'day' | 'visual' | 'all'

  // Scout state & Pre-Commit Review (Scout Mode)
  const [autoCreateCollection, setAutoCreateCollection] = useState(true)
  const [customCollectionName, setCustomCollectionName] = useState('')
  const [scoutResult, setScoutResult] = useState(null)
  const [approvedScoutTags, setApprovedScoutTags] = useState([])
  const [approvedScoutPhotos, setApprovedScoutPhotos] = useState([])
  const [manualScoutTagInput, setManualScoutTagInput] = useState('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)
  const [teachResult, setTeachResult] = useState(null)

  const recognitionRef = useRef(null)
  const baseTextBeforeSpeechRef = useRef('')
  const textareaRef = useRef(null)
  const commitBtnRef = useRef(null)
  const dismissedTagsRef = useRef([])

  useEffect(() => {
    dismissedTagsRef.current = dismissedTags
  }, [dismissedTags])

  // Stable key representing which target photos are selected
  const selectedPhotosKey = useMemo(
    () => selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean).join('|'),
    [selectedPhotos]
  )

  // Gather existing user_context_notes and user_taught_tags across selectedPhotos for the read-only reference badge
  const existingContextSummary = useMemo(() => {
    const notes = []
    const taught = []
    const seenNotes = new Set()
    const seenTaught = new Set()

    for (const p of selectedPhotos) {
      const rawNote = String(p.user_context_notes || '').trim()
      if (rawNote && rawNote !== '[CLEARED_SLATE]' && !seenNotes.has(rawNote.toLowerCase())) {
        seenNotes.add(rawNote.toLowerCase())
        notes.push(rawNote)
      }
      const utList = Array.isArray(p.user_taught_tags) ? p.user_taught_tags : []
      for (const t of utList) {
        const ts = String(t || '').trim()
        if (ts && !seenTaught.has(ts.toLowerCase())) {
          seenTaught.add(ts.toLowerCase())
          taught.push(ts)
        }
      }
    }
    return {
      hasAny: notes.length > 0 || taught.length > 0,
      notesText: notes.join(' • '),
      taughtTags: taught,
    }
  }, [selectedPhotos])

  // 1. ALWAYS OPEN WITH A 100% BLANK INPUT BOX & FRESH PREVIEW STATE
  useEffect(() => {
    if (isOpen) {
      if (selectedPhotos.length === 0 && initialMode === 'teach') {
        setActiveTab('scout')
      } else {
        setActiveTab(initialMode || (selectedPhotos.length > 0 ? 'teach' : 'scout'))
      }
      // Guarantee 100% blank input box every time modal opens or target photos change
      setInstruction('')
      baseTextBeforeSpeechRef.current = ''
      // Auto-detect if user had cleared tags on selected photo(s) prior to opening Voice Tag
      const hasClearedSeed = selectedPhotos.some(
        (p) => p.user_context_notes === '[CLEARED_SLATE]' || p.location_provenance === 'user_cleared'
      )
      setWipeExisting(hasClearedSeed)
      setPreviewData(null)
      setApprovedSpokenTags([])
      setApprovedVisualTags([])
      setApprovedRemoveTags([])
      setDismissedTags([])
      dismissedTagsRef.current = []
      setManualTagInput('')
      setTargetCollection(null)
      setOrbitCandidates([])
      setSelectedOrbitIds(new Set())
      setIsOrbitExpanded(true)
      setScoutResult(null)
      setApprovedScoutTags([])
      setApprovedScoutPhotos([])
      setManualScoutTagInput('')
      setTeachResult(null)
      setErrorMsg(null)

      if (autoStartRecording) {
        setSpeechStatus('🎙️ Listening — speak your tags or context, then press Enter to review & commit...')
        const t = setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.focus()
          }
          startMicrophone(true, true)
          if (onClearAutoStart) onClearAutoStart()
        }, 60)
        return () => clearTimeout(t)
      } else {
        const t = setTimeout(() => {
          if (textareaRef.current) {
            textareaRef.current.focus()
          }
        }, 50)
        return () => clearTimeout(t)
      }
    } else {
      stopMicrophone()
    }
  }, [isOpen, initialMode, selectedPhotosKey])

  useEffect(() => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition
    setSpeechSupported(Boolean(SpeechRec))
    return () => {
      stopMicrophone()
    }
  }, [])

  // Fetch Vector + Language Candidate Assessment (`/api/ai/teach/preview`)
  const runTeachPreviewAssessment = async (textToAssess, forceWipeFlag) => {
    const trimmed = String(textToAssess ?? instruction).trim()
    const wipeFlag = Boolean(forceWipeFlag ?? wipeExisting)
    if (!trimmed && !wipeFlag && selectedPhotos.length === 0) {
      setPreviewData(null)
      setApprovedSpokenTags([])
      setApprovedVisualTags([])
      setApprovedRemoveTags([])
      setOrbitCandidates([])
      setSelectedOrbitIds(new Set())
      return null
    }
    setIsAssessing(true)
    try {
      const photoIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
      const res = await fetch(`${API_BASE}/api/ai/teach/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instruction: trimmed,
          photo_ids: photoIds,
          wipe_existing: wipeFlag,
        }),
      })
      if (!res.ok) return null
      const data = await res.json()
      setPreviewData(data)

      // Two-Way Clean-Slate Wipe Sync (Voice -> UI Checkbox)
      if (data.clean_slate) {
        setWipeExisting(true)
      }

      // Voice-Driven Collection Routing
      if (data.target_collection) {
        setTargetCollection(data.target_collection)
      }

      const dismissedLow = new Set((dismissedTagsRef.current || []).map((t) => String(t).toLowerCase()))
      const spoken = (data.spoken_tags || data.add_tags || []).filter(
        (t) => t && !dismissedLow.has(String(t).toLowerCase())
      )
      const spokenLow = new Set(spoken.map((t) => String(t).toLowerCase()))
      const visual = (data.visual_tags || []).filter(
        (t) =>
          t &&
          !spokenLow.has(String(t).toLowerCase()) &&
          !dismissedLow.has(String(t).toLowerCase())
      )
      const rem = (data.remove_tags || data.removed_tags || []).filter(
        (t) => t && !dismissedLow.has(String(t).toLowerCase())
      )

      setApprovedSpokenTags(spoken)
      setApprovedVisualTags(visual)
      setApprovedRemoveTags(rem)

      if (Array.isArray(data.orbit_candidates)) {
        setOrbitCandidates(data.orbit_candidates)
        const candList = data.orbit_candidates
        const scope = data.sibling_scope

        // Smart Sibling / Orbit Selection Control
        if (scope === 'all' || (!scope && data.propagate_to_orbit)) {
          setOrbitFilterScope('all')
          setSelectedOrbitIds(new Set(candList.map((c) => c.file_hash || c.file_path)))
        } else if (scope === 'visual_match') {
          setOrbitFilterScope('visual')
          const vis = candList.filter((c) => c.is_visual || ((c.similarity || 0) >= 0.58))
          setSelectedOrbitIds(new Set(vis.map((c) => c.file_hash || c.file_path)))
        } else if (scope === 'burst') {
          setOrbitFilterScope('burst')
          const bst = candList.filter((c) => c.is_burst || (c.time_delta_seconds <= 300))
          setSelectedOrbitIds(new Set(bst.map((c) => c.file_hash || c.file_path)))
        } else if (scope === 'window') {
          setOrbitFilterScope('window')
          const win = candList.filter((c) => c.is_window || (c.time_delta_seconds <= 7200))
          setSelectedOrbitIds(new Set(win.map((c) => c.file_hash || c.file_path)))
        } else if (scope === 'single') {
          setSelectedOrbitIds(new Set())
        }
      } else {
        setOrbitCandidates([])
        setSelectedOrbitIds(new Set())
      }
      return data
    } catch {
      return null
    } finally {
      setIsAssessing(false)
    }
  }

  // Live debounced Vector + Language candidate assessment in Teach Mode
  useEffect(() => {
    if (!isOpen || activeTab !== 'teach') return
    const trimmed = instruction.trim()
    if (!trimmed && !wipeExisting) {
      setPreviewData(null)
      setApprovedSpokenTags([])
      setApprovedVisualTags([])
      setApprovedRemoveTags([])
      setOrbitCandidates([])
      setSelectedOrbitIds(new Set())
      return
    }
    const timer = setTimeout(() => {
      runTeachPreviewAssessment(trimmed, wipeExisting)
    }, 180)
    return () => clearTimeout(timer)
  }, [instruction, wipeExisting, isOpen, activeTab, selectedPhotosKey])

  const startMicrophone = (isAutoStart = false, forceBlankBase = false) => {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRec) {
      setSpeechStatus(
        '🎙️ Speak now (press Fn+Fn for macOS Dictation) or type below — press Enter to commit.'
      )
      return
    }
    try {
      stopMicrophone()
      const rec = new SpeechRec()
      rec.continuous = true
      rec.interimResults = true
      rec.lang = 'en-US'

      baseTextBeforeSpeechRef.current = forceBlankBase
        ? ''
        : instruction.trim()
        ? instruction.trim() + ' '
        : ''

      rec.onstart = () => {
        setIsRecording(true)
        setSpeechStatus(
          '🎙️ Listening — speak your tags or context, then press Enter to review & commit...'
        )
      }

      rec.onresult = (event) => {
        let finalChunk = ''
        let interimChunk = ''
        for (let i = 0; i < event.results.length; i += 1) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            finalChunk += transcript + ' '
          } else {
            interimChunk += transcript
          }
        }
        const combined = `${baseTextBeforeSpeechRef.current}${finalChunk}${interimChunk}`.replace(
          /\s+/g,
          ' '
        )
        setInstruction(combined)
      }

      rec.onerror = (e) => {
        setIsRecording(false)
        setSpeechStatus(
          isAutoStart
            ? '🎙️ Speak now (press Fn+Fn for macOS Dictation) or type directly below — press Enter to commit.'
            : `Mic note: ${e.error || 'stopped'} — you can also use macOS Dictation (Fn+Fn) or type directly.`
        )
      }

      rec.onend = () => {
        setIsRecording(false)
        setSpeechStatus('')
      }

      recognitionRef.current = rec
      rec.start()
    } catch {
      setIsRecording(false)
      setSpeechStatus(
        '🎙️ Speak now (press Fn+Fn for macOS Dictation) or type below — press Enter to commit.'
      )
    }
  }

  const stopMicrophone = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {
        // ignore
      }
      recognitionRef.current = null
    }
    setIsRecording(false)
    setSpeechStatus('')
  }

  const toggleMicrophone = () => {
    if (isRecording) {
      stopMicrophone()
    } else {
      startMicrophone(false, false)
    }
  }

  // Prune (`×`) handlers for Teach Mode candidate pills
  const handleDismissSpokenTag = (tagToRemove) => {
    setApprovedSpokenTags((prev) => prev.filter((t) => t !== tagToRemove))
    setDismissedTags((prev) => (prev.includes(tagToRemove) ? prev : [...prev, tagToRemove]))
  }

  const handleDismissVisualTag = (tagToRemove) => {
    setApprovedVisualTags((prev) => prev.filter((t) => t !== tagToRemove))
    setDismissedTags((prev) => (prev.includes(tagToRemove) ? prev : [...prev, tagToRemove]))
  }

  const handleDismissRemoveTag = (tagToRemove) => {
    setApprovedRemoveTags((prev) => prev.filter((t) => t !== tagToRemove))
    setDismissedTags((prev) => (prev.includes(tagToRemove) ? prev : [...prev, tagToRemove]))
  }

  const handleAddManualTag = () => {
    const clean = manualTagInput.trim()
    if (!clean) return
    setDismissedTags((prev) => prev.filter((t) => t.toLowerCase() !== clean.toLowerCase()))
    setApprovedSpokenTags((prev) =>
      prev.some((t) => t.toLowerCase() === clean.toLowerCase()) ? prev : [...prev, clean]
    )
    setManualTagInput('')
  }

  // Sibling Orbit multi-scope subsets
  const burstCandidates = useMemo(
    () => orbitCandidates.filter((c) => c.is_burst || (c.time_delta_seconds <= 300)),
    [orbitCandidates]
  );
  const windowCandidates = useMemo(
    () => orbitCandidates.filter((c) => c.is_window || (c.time_delta_seconds <= 7200)),
    [orbitCandidates]
  );
  const dayCandidates = useMemo(
    () => orbitCandidates.filter((c) => c.is_day !== false),
    [orbitCandidates]
  );
  const visualCandidates = useMemo(
    () => orbitCandidates.filter((c) => c.is_visual || ((c.similarity || 0) >= 0.58)),
    [orbitCandidates]
  );

  const visibleOrbitCandidates = useMemo(() => {
    switch (orbitFilterScope) {
      case 'burst':
        return burstCandidates;
      case 'window':
        return windowCandidates;
      case 'day':
        return dayCandidates;
      case 'visual':
        return visualCandidates;
      case 'all':
      default:
        return orbitCandidates;
    }
  }, [orbitFilterScope, burstCandidates, windowCandidates, dayCandidates, visualCandidates, orbitCandidates]);

  // Session & Visual Orbit Propagation toggles
  const handleSelectAllOrbit = () => {
    setSelectedOrbitIds((prev) => {
      const next = new Set(prev)
      visibleOrbitCandidates.forEach((c) => next.add(c.file_hash || c.file_path))
      return next
    })
  }

  const handleSelectAllDayOrbit = () => {
    setSelectedOrbitIds((prev) => {
      const next = new Set(prev)
      dayCandidates.forEach((c) => next.add(c.file_hash || c.file_path))
      return next
    })
  }

  const handleDeselectAllOrbit = () => {
    setSelectedOrbitIds(new Set())
  }

  const handleToggleOrbitCandidate = (candId) => {
    setSelectedOrbitIds((prev) => {
      const next = new Set(prev)
      if (next.has(candId)) {
        next.delete(candId)
      } else {
        next.add(candId)
      }
      return next
    })
  }

  const totalTargetCount = useMemo(() => {
    const basePhotoIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
    return new Set([...basePhotoIds, ...Array.from(selectedOrbitIds)]).size
  }, [selectedPhotos, selectedOrbitIds])

  const siblingOrbitCount = useMemo(() => {
    const basePhotoIds = new Set(selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean))
    return Array.from(selectedOrbitIds).filter((id) => !basePhotoIds.has(id)).length
  }, [selectedPhotos, selectedOrbitIds])

  // Clear existing prior notes on selected photos (from the read-only reference badge)
  const handleClearPriorNotes = async () => {
    if (selectedPhotos.length === 0 || isSubmitting) return
    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      const photoIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
      const res = await fetch(`${API_BASE}/api/ai/teach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          photo_ids: photoIds,
          clear_existing_notes: true,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to clear prior notes')
      }
      if (onTeachApplied) {
        onTeachApplied(data)
      } else if (onPhotosUpdated && Array.isArray(data.photos)) {
        onPhotosUpdated(data.photos)
      }
    } catch (err) {
      setErrorMsg(err.message || 'Could not clear prior notes')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Commit Approved Tags (Teach Mode) and close modal
  const handleApplyTeach = async (mode = 'instant', closeAfterCommit = true) => {
    if (selectedPhotos.length === 0) {
      setErrorMsg('Please select at least one photo first (or switch to Archive Scout mode).')
      return
    }
    const combinedApproved = [...approvedSpokenTags, ...approvedVisualTags]
    if (
      !instruction.trim() &&
      !wipeExisting &&
      combinedApproved.length === 0 &&
      approvedRemoveTags.length === 0
    ) {
      setErrorMsg('Please speak or type your tags or context first.')
      return
    }

    stopMicrophone()
    setIsSubmitting(true)
    setErrorMsg(null)
    setTeachResult(null)

    try {
      const basePhotoIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
      const combinedPhotoIds = Array.from(new Set([...basePhotoIds, ...Array.from(selectedOrbitIds)]))
      const res = await fetch(`${API_BASE}/api/ai/teach`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          photo_ids: combinedPhotoIds,
          instruction: instruction.trim(),
          mode,
          wipe_existing: Boolean(wipeExisting || previewData?.wipe_mode),
          wipe_mode: Boolean(wipeExisting || previewData?.wipe_mode),
          clean_slate: Boolean(wipeExisting || previewData?.wipe_mode || previewData?.clean_slate),
          approved_tags: combinedApproved,
          removed_tags: approvedRemoveTags,
          dismissed_tags: dismissedTags,
          target_collection: targetCollection,
        }),
      })
      const rawText = await res.text()
      let data = {}
      try {
        data = rawText ? JSON.parse(rawText) : {}
      } catch {
        throw new Error(rawText || `Server error (${res.status})`)
      }
      if (!res.ok) {
        throw new Error(
          data.detail || data.message || `Failed to apply AI teaching override (${res.status})`
        )
      }
      setTeachResult(data)
      if (onTeachApplied) {
        onTeachApplied(data)
      } else if (onPhotosUpdated && Array.isArray(data.photos)) {
        onPhotosUpdated(data.photos)
      }
      if (closeAfterCommit && onClose) {
        onClose()
      }
    } catch (err) {
      setErrorMsg(err.message || 'Error applying AI teaching')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Scout Mode Step 1: Preview candidate photo tiles & tags (`preview_only: true`)
  const handlePreviewScout = async (e) => {
    if (e) e.preventDefault()
    if (!instruction.trim() && selectedPhotos.length === 0) {
      setErrorMsg('Please speak or type what you want to scout across the archive.')
      return
    }

    stopMicrophone()
    setIsSubmitting(true)
    setErrorMsg(null)

    try {
      const seedIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
      const res = await fetch(`${API_BASE}/api/ai/scout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: instruction.trim(),
          seed_photo_ids: seedIds.length > 0 ? seedIds : null,
          auto_create_collection: autoCreateCollection,
          collection_name: customCollectionName.trim() || null,
          enrich_tags: true,
          preview_only: true,
        }),
      })
      const rawText = await res.text()
      let data = {}
      try {
        data = rawText ? JSON.parse(rawText) : {}
      } catch {
        throw new Error(rawText || `Server error (${res.status})`)
      }
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Failed to run Archive Scout (${res.status})`)
      }
      setScoutResult(data)
      setApprovedScoutTags(data.enriched_tags || [])
      setApprovedScoutPhotos(data.matches || [])
    } catch (err) {
      setErrorMsg(err.message || 'Error scouting archive')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Scout Mode Step 2: Commit user-pruned candidate photos & tags (`preview_only: false`)
  const handleCommitScout = async () => {
    if (!scoutResult) {
      await handlePreviewScout()
      return
    }
    if (approvedScoutPhotos.length === 0) {
      setErrorMsg('All candidate photos were removed. Keep at least 1 photo to commit.')
      return
    }

    stopMicrophone()
    setIsSubmitting(true)
    setErrorMsg(null)

    try {
      const seedIds = selectedPhotos.map((p) => p.file_hash || p.file_path).filter(Boolean)
      const approvedIds = approvedScoutPhotos
        .map((m) => m.file_hash || m.file_path)
        .filter(Boolean)
      const res = await fetch(`${API_BASE}/api/ai/scout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: instruction.trim(),
          seed_photo_ids: seedIds.length > 0 ? seedIds : null,
          auto_create_collection: autoCreateCollection,
          collection_name: customCollectionName.trim() || scoutResult.collection_name || null,
          enrich_tags: true,
          preview_only: false,
          approved_photo_ids: approvedIds,
          approved_tags: approvedScoutTags,
        }),
      })
      const rawText = await res.text()
      let data = {}
      try {
        data = rawText ? JSON.parse(rawText) : {}
      } catch {
        throw new Error(rawText || `Server error (${res.status})`)
      }
      if (!res.ok) {
        throw new Error(data.detail || data.message || `Failed to commit Scout story (${res.status})`)
      }
      setScoutResult(data)
      if (onScoutCompleted) {
        onScoutCompleted(data)
      }
      if (onPhotosUpdated && Array.isArray(data.matches)) {
        onPhotosUpdated(data.matches)
      }
      if (onViewPhotosInGrid && Array.isArray(data.matches)) {
        onViewPhotosInGrid(data.matches, `🔎 Scout: ${data.collection_name}`)
      }
      if (onClose) {
        onClose()
      }
    } catch (err) {
      setErrorMsg(err.message || 'Error committing Scout story')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDismissScoutTag = (tagToRemove) => {
    setApprovedScoutTags((prev) => prev.filter((t) => t !== tagToRemove))
  }

  const handleDismissScoutPhoto = (photoId) => {
    setApprovedScoutPhotos((prev) =>
      prev.filter((m) => (m.file_hash || m.file_path) !== photoId)
    )
  }

  const handleAddManualScoutTag = () => {
    const clean = manualScoutTagInput.trim()
    if (!clean) return
    setApprovedScoutTags((prev) =>
      prev.some((t) => t.toLowerCase() === clean.toLowerCase()) ? prev : [...prev, clean]
    )
    setManualScoutTagInput('')
  }

  // Keyboard Workflow: `Enter` (without Shift) stops recording -> previews/prunes -> commits & closes
  const handleModalKeyDown = async (e) => {
    if (e.key === 'Escape') {
      e.stopPropagation()
      stopMicrophone()
      onClose()
      return
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      // Allow inline "+ Add tag" inputs to add their tag on Enter without submitting the modal
      if (e.target?.dataset?.inlineTagInput === 'true') {
        e.preventDefault()
        e.stopPropagation()
        if (activeTab === 'teach') {
          handleAddManualTag()
        } else {
          handleAddManualScoutTag()
        }
        return
      }
      // Ignore Enter inside custom collection name input only if no scout preview yet
      e.preventDefault()
      e.stopPropagation()

      if (isSubmitting) return

      // If currently recording speech, first Enter stops recording & runs candidate assessment so user can prune (`×`)
      if (isRecording) {
        stopMicrophone()
        if (activeTab === 'teach') {
          await runTeachPreviewAssessment(instruction, wipeExisting)
        } else {
          await handlePreviewScout()
        }
        if (commitBtnRef.current) {
          commitBtnRef.current.focus()
        }
        return
      }

      if (activeTab === 'teach') {
        const hasCandidates =
          approvedSpokenTags.length > 0 ||
          approvedVisualTags.length > 0 ||
          approvedRemoveTags.length > 0 ||
          wipeExisting
        if (!hasCandidates && instruction.trim()) {
          // Assess first if preview hasn't resolved yet
          const assessed = await runTeachPreviewAssessment(instruction, wipeExisting)
          if (assessed) {
            if (commitBtnRef.current) commitBtnRef.current.focus()
            return
          }
        }
        await handleApplyTeach('instant', true)
      } else {
        // Scout mode: first Enter previews candidate tiles; second Enter commits & closes
        if (!scoutResult) {
          await handlePreviewScout()
        } else {
          await handleCommitScout()
        }
      }
    }
  }

  if (!isOpen) return null

  const totalApprovedTeachTags = approvedSpokenTags.length + approvedVisualTags.length
  const hasTeachReviewItems =
    totalApprovedTeachTags > 0 ||
    approvedRemoveTags.length > 0 ||
    wipeExisting ||
    Boolean(previewData?.wipe_mode) ||
    Boolean(targetCollection)

  return (
    <div
      onKeyDown={handleModalKeyDown}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9600,
        background: 'rgba(6, 9, 15, 0.84)',
        backdropFilter: 'blur(10px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '18px',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stopMicrophone()
          onClose()
        }
      }}
    >
      <div
        style={{
          width: '860px',
          maxWidth: '96vw',
          maxHeight: '92vh',
          overflowY: 'auto',
          background: '#0f172a',
          border: '1.5px solid rgba(148, 163, 184, 0.32)',
          borderRadius: '18px',
          boxShadow: '0 28px 80px rgba(0, 0, 0, 0.85)',
          color: '#f8fafc',
          padding: '22px 26px',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
            marginBottom: '14px',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
            paddingBottom: '12px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            <h2 style={{ margin: 0, fontSize: '21px', fontWeight: 800, color: '#ffffff' }}>
              🎙️ AI Voice Tag &amp; Archive Scout
            </h2>
            {selectedPhotos.length > 0 && (
              <span
                style={{
                  background: 'rgba(99, 102, 241, 0.22)',
                  border: '1px solid rgba(129, 140, 248, 0.5)',
                  color: '#c7d2fe',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '999px',
                }}
              >
                {selectedPhotos.length} Photo{selectedPhotos.length === 1 ? '' : 's'} Selected
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => {
              stopMicrophone()
              onClose()
            }}
            style={{
              background: 'rgba(255,255,255,0.08)',
              border: '1px solid rgba(255,255,255,0.2)',
              color: '#f1f5f9',
              fontSize: '15px',
              fontWeight: 700,
              padding: '7px 14px',
              borderRadius: '10px',
              cursor: 'pointer',
            }}
          >
            ✕ Esc
          </button>
        </div>

        {/* Compact Mode Switcher Tabs */}
        <div style={{ display: 'flex', gap: '10px', marginBottom: '14px' }}>
          <button
            type="button"
            onClick={() => {
              setActiveTab('teach')
              setErrorMsg(null)
            }}
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: '11px',
              fontSize: '14.5px',
              fontWeight: 800,
              cursor: 'pointer',
              border:
                activeTab === 'teach'
                  ? '2px solid #818cf8'
                  : '1px solid rgba(255,255,255,0.14)',
              background:
                activeTab === 'teach'
                  ? 'linear-gradient(135deg, rgba(79, 70, 229, 0.34), rgba(124, 58, 237, 0.24))'
                  : 'rgba(255,255,255,0.04)',
              color: activeTab === 'teach' ? '#ffffff' : '#94a3b8',
              textAlign: 'left',
            }}
          >
            🎓 Teach &amp; Tag Selected Photos ({selectedPhotos.length})
          </button>

          <button
            type="button"
            onClick={() => {
              setActiveTab('scout')
              setErrorMsg(null)
            }}
            style={{
              flex: 1,
              padding: '10px 14px',
              borderRadius: '11px',
              fontSize: '14.5px',
              fontWeight: 800,
              cursor: 'pointer',
              border:
                activeTab === 'scout'
                  ? '2px solid #34d399'
                  : '1px solid rgba(255,255,255,0.14)',
              background:
                activeTab === 'scout'
                  ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.28), rgba(5, 150, 105, 0.22))'
                  : 'rgba(255,255,255,0.04)',
              color: activeTab === 'scout' ? '#ffffff' : '#94a3b8',
              textAlign: 'left',
            }}
          >
            🔎 Scout Archive &amp; Build Story (All 849 Photos)
          </button>
        </div>

        {/* Read-Only Reference Line for Existing Taught Notes/Tags (Never Pre-Filled into Input Box!) */}
        {activeTab === 'teach' && existingContextSummary.hasAny && (
          <div
            style={{
              background: 'rgba(30, 41, 59, 0.75)',
              border: '1px solid rgba(148, 163, 184, 0.28)',
              borderRadius: '10px',
              padding: '8px 12px',
              marginBottom: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', fontSize: '12.5px' }}>
              <span style={{ color: '#94a3b8', fontWeight: 700 }}>📌 Prior Taught Context:</span>
              {existingContextSummary.notesText && (
                <span style={{ color: '#e2e8f0', fontStyle: 'italic' }}>
                  "{existingContextSummary.notesText}"
                </span>
              )}
              {existingContextSummary.taughtTags.map((t) => (
                <span
                  key={t}
                  style={{
                    background: 'rgba(99, 102, 241, 0.18)',
                    border: '1px solid rgba(129, 140, 248, 0.4)',
                    color: '#c7d2fe',
                    padding: '1px 8px',
                    borderRadius: '999px',
                    fontSize: '11.5px',
                    fontWeight: 700,
                  }}
                >
                  {t}
                </span>
              ))}
            </div>
            <button
              type="button"
              onClick={handleClearPriorNotes}
              disabled={isSubmitting}
              title="Clear prior taught notes from the selected photo(s)"
              style={{
                background: 'rgba(239, 68, 68, 0.14)',
                border: '1px solid rgba(248, 113, 113, 0.4)',
                color: '#fecaca',
                fontSize: '11.5px',
                fontWeight: 700,
                padding: '4px 9px',
                borderRadius: '7px',
                cursor: 'pointer',
              }}
            >
              🧹 Clear Prior Notes
            </button>
          </div>
        )}

        {/* Voice Microphone & 100% Blank Input Box */}
        <div
          style={{
            background: '#1e293b',
            border: isRecording ? '2px solid #ef4444' : '1.5px solid rgba(148, 163, 184, 0.35)',
            borderRadius: '14px',
            padding: '14px 16px',
            marginBottom: '14px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              marginBottom: '8px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
              <label style={{ fontSize: '14.5px', fontWeight: 800, color: '#f8fafc' }}>
                {activeTab === 'teach'
                  ? '1. Speak or Type New Tags / Context:'
                  : '1. Speak or Type Visual Theme to Scout:'}
              </label>
              {selectedPhotos.length > 0 && (
                <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
                  {selectedPhotos.slice(0, 6).map((p) => (
                    <img
                      key={p.file_hash || p.file_path}
                      src={p.thumb_url || p.preview_url}
                      alt={p.filename || 'thumb'}
                      style={{
                        width: '32px',
                        height: '32px',
                        minWidth: '32px',
                        minHeight: '32px',
                        flexShrink: 0,
                        borderRadius: '6px',
                        objectFit: 'cover',
                        border: '1px solid rgba(255,255,255,0.3)',
                      }}
                    />
                  ))}
                  {selectedPhotos.length > 6 && (
                    <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 700 }}>
                      +{selectedPhotos.length - 6}
                    </span>
                  )}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                type="button"
                onClick={toggleMicrophone}
                style={{
                  background: isRecording
                    ? 'linear-gradient(135deg, #dc2626, #ef4444)'
                    : 'linear-gradient(135deg, #2563eb, #4f46e5)',
                  border: isRecording ? '1.5px solid #fca5a5' : '1.5px solid #93c5fd',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 800,
                  padding: '7px 16px',
                  borderRadius: '999px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  boxShadow: isRecording
                    ? '0 0 18px rgba(239, 68, 68, 0.65)'
                    : '0 4px 12px rgba(37, 99, 235, 0.35)',
                }}
              >
                <span>{isRecording ? '⏹ Stop Mic (Enter ↵)' : '🎙️ Speak'}</span>
              </button>

              {activeTab === 'teach' && (
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: wipeExisting
                      ? 'rgba(245, 158, 11, 0.22)'
                      : 'rgba(255,255,255,0.06)',
                    border: wipeExisting
                      ? '1px solid rgba(251, 191, 36, 0.65)'
                      : '1px solid rgba(255,255,255,0.16)',
                    color: wipeExisting ? '#fde68a' : '#cbd5e1',
                    padding: '7px 11px',
                    borderRadius: '9px',
                    fontSize: '12.5px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                  title="Wipe old AI location/style guesses on selected photos and re-anchor around your prompt"
                >
                  <input
                    type="checkbox"
                    checked={wipeExisting}
                    onChange={(e) => setWipeExisting(e.target.checked)}
                    style={{ accentColor: '#f59e0b', cursor: 'pointer' }}
                  />
                  <span>🧹 Clean-Slate Wipe</span>
                </label>
              )}

              {instruction && (
                <button
                  type="button"
                  onClick={() => {
                    setInstruction('')
                    baseTextBeforeSpeechRef.current = ''
                    setWipeExisting(false)
                    setTargetCollection(null)
                    setPreviewData(null)
                    setApprovedSpokenTags([])
                    setApprovedVisualTags([])
                    setApprovedRemoveTags([])
                    setDismissedTags([])
                    if (textareaRef.current) textareaRef.current.focus()
                  }}
                  style={{
                    background: 'rgba(255,255,255,0.08)',
                    border: '1px solid rgba(255,255,255,0.18)',
                    color: '#cbd5e1',
                    fontSize: '12.5px',
                    fontWeight: 700,
                    padding: '7px 11px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {speechStatus && (
            <div
              style={{
                fontSize: '12.5px',
                color: isRecording ? '#fca5a5' : '#93c5fd',
                fontWeight: 600,
                marginBottom: '6px',
              }}
            >
              {speechStatus}
            </div>
          )}

          <textarea
            ref={textareaRef}
            rows={2}
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder={
              activeTab === 'teach'
                ? 'Speak or type fresh tags & context (e.g. "Mitch Rouse Residence and Pickles" or "Havana, Cuba, not Venice") — press Enter to commit'
                : 'Speak or type what to scout (e.g. "Find all photos of colorful doors and windows") — press Enter to preview matches'
            }
            style={{
              width: '100%',
              boxSizing: 'border-box',
              background: '#0f172a',
              border: '1px solid rgba(255,255,255,0.22)',
              borderRadius: '10px',
              color: '#ffffff',
              fontSize: '17px',
              lineHeight: 1.4,
              padding: '10px 14px',
              resize: 'vertical',
              fontFamily: 'inherit',
            }}
          />
        </div>

        {/* =====================================================================
            MODE 1: INTERACTIVE PRE-COMMIT REVIEW ("Assess -> Click × to Prune -> Press Enter to Commit")
           ===================================================================== */}
        {activeTab === 'teach' && (
          <div
            style={{
              background: 'rgba(15, 23, 42, 0.95)',
              border: hasTeachReviewItems
                ? '1.5px solid rgba(52, 211, 153, 0.55)'
                : '1px solid rgba(148, 163, 184, 0.25)',
              borderRadius: '14px',
              padding: '14px 16px',
              marginBottom: '14px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '10px',
                marginBottom: '10px',
                flexWrap: 'wrap',
              }}
            >
              <div style={{ fontSize: '13.5px', fontWeight: 800, color: '#e2e8f0' }}>
                2. Pre-Commit Tag Review{' '}
                <span style={{ fontWeight: 500, color: '#94a3b8', fontSize: '12.5px' }}>
                  (Click <strong style={{ color: '#fca5a5' }}>×</strong> on any stretched tag to drop it before pressing{' '}
                  <strong style={{ color: '#6ee7b7' }}>Enter ↵</strong>)
                </span>
              </div>
              {isAssessing && (
                <span style={{ fontSize: '12px', color: '#93c5fd', fontWeight: 600 }}>
                  ⚡ Assessing vectors &amp; phrases...
                </span>
              )}
            </div>

            {/* Interactive Dismissible (`×`) Tag Pills */}
            <div
              style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: '8px',
                alignItems: 'center',
                minHeight: '38px',
                padding: '6px 0',
              }}
            >
              {/* Voice-Routed Collection Assignment Badge */}
              {targetCollection && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    background: 'rgba(168, 85, 247, 0.22)',
                    border: '1.5px solid rgba(192, 132, 252, 0.65)',
                    color: '#f3e8ff',
                    fontSize: '13.5px',
                    fontWeight: 700,
                    padding: '6px 12px',
                    borderRadius: '999px',
                  }}
                  title="Photos will be added to this collection on commit. Click × to cancel collection assignment."
                >
                  <span>📚 Add to Collection: <strong>{targetCollection}</strong></span>
                  <button
                    type="button"
                    onClick={() => setTargetCollection(null)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#fca5a5',
                      fontWeight: 900,
                      fontSize: '15px',
                      cursor: 'pointer',
                      padding: 0,
                      lineHeight: 1,
                      marginLeft: '2px',
                    }}
                  >
                    ×
                  </button>
                </div>
              )}

              {/* 1. Spoken / Custom Tags & Locations (`🎙️`) */}
              {approvedSpokenTags.map((tag) => (
                <button
                  key={`spoken-${tag}`}
                  type="button"
                  onClick={() => handleDismissSpokenTag(tag)}
                  title="Click × to remove this tag from commit"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    background: 'rgba(16, 185, 129, 0.22)',
                    border: '1.5px solid rgba(52, 211, 153, 0.65)',
                    color: '#ecfdf5',
                    fontSize: '14px',
                    fontWeight: 700,
                    padding: '6px 12px',
                    borderRadius: '999px',
                    cursor: 'pointer',
                  }}
                >
                  <span>🎙️ {tag}</span>
                  <span
                    style={{
                      color: '#fca5a5',
                      fontWeight: 900,
                      fontSize: '15px',
                      lineHeight: 1,
                      marginLeft: '2px',
                    }}
                  >
                    ×
                  </span>
                </button>
              ))}

              {/* 2. Visual Vector-Matched Tags (`⚡`) */}
              {approvedVisualTags.map((tag) => (
                <button
                  key={`visual-${tag}`}
                  type="button"
                  onClick={() => handleDismissVisualTag(tag)}
                  title="Visual subject confirmed by OpenCLIP vector probe — click × to drop if stretched"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    background: 'rgba(59, 130, 246, 0.20)',
                    border: '1.5px solid rgba(96, 165, 250, 0.6)',
                    color: '#dbeafe',
                    fontSize: '14px',
                    fontWeight: 700,
                    padding: '6px 12px',
                    borderRadius: '999px',
                    cursor: 'pointer',
                  }}
                >
                  <span>⚡ {tag}</span>
                  <span
                    style={{
                      color: '#fca5a5',
                      fontWeight: 900,
                      fontSize: '15px',
                      lineHeight: 1,
                      marginLeft: '2px',
                    }}
                  >
                    ×
                  </span>
                </button>
              ))}

              {/* 3. Tags to Strip / Quarantine (`−`) */}
              {approvedRemoveTags.map((tag) => (
                <button
                  key={`remove-${tag}`}
                  type="button"
                  onClick={() => handleDismissRemoveTag(tag)}
                  title="Tag scheduled to be stripped & blocked — click × to cancel stripping this tag"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '7px',
                    background: 'rgba(239, 68, 68, 0.20)',
                    border: '1.5px solid rgba(248, 113, 113, 0.6)',
                    color: '#fecaca',
                    fontSize: '13.5px',
                    fontWeight: 700,
                    padding: '6px 12px',
                    borderRadius: '999px',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ textDecoration: 'line-through' }}>− {tag}</span>
                  <span
                    style={{
                      color: '#fde68a',
                      fontWeight: 900,
                      fontSize: '15px',
                      lineHeight: 1,
                      marginLeft: '2px',
                    }}
                  >
                    ×
                  </span>
                </button>
              ))}

              {!hasTeachReviewItems && !isAssessing && (
                <span style={{ fontSize: '13px', color: '#64748b', fontStyle: 'italic' }}>
                  Speak or type above — candidate spoken tags (🎙️) and OpenCLIP visual vector matches (⚡) will appear here as dismissible pills...
                </span>
              )}

              {/* Quick Inline `+ Add tag` Chip Input */}
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px dashed rgba(148, 163, 184, 0.45)',
                  borderRadius: '999px',
                  padding: '3px 6px 3px 11px',
                  gap: '4px',
                }}
              >
                <input
                  type="text"
                  data-inline-tag-input="true"
                  value={manualTagInput}
                  onChange={(e) => setManualTagInput(e.target.value)}
                  placeholder="+ Add tag..."
                  style={{
                    background: 'transparent',
                    border: 'none',
                    outline: 'none',
                    color: '#f8fafc',
                    fontSize: '13px',
                    width: '96px',
                  }}
                />
                {manualTagInput.trim() && (
                  <button
                    type="button"
                    onClick={handleAddManualTag}
                    style={{
                      background: '#10b981',
                      border: 'none',
                      color: '#052e16',
                      fontWeight: 800,
                      fontSize: '12px',
                      padding: '2px 8px',
                      borderRadius: '999px',
                      cursor: 'pointer',
                    }}
                  >
                    +
                  </button>
                )}
              </div>
            </div>

            {/* =====================================================================
                SHOOT SESSION & VISUAL ORBIT PROPAGATION CONFIRMATION PANEL
               ===================================================================== */}
            {orbitCandidates.length > 0 && (
              <div
                style={{
                  marginTop: '14px',
                  background: 'rgba(15, 23, 42, 0.75)',
                  border: selectedOrbitIds.size > 0 ? '1.5px solid rgba(16, 185, 129, 0.45)' : '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '14px',
                  padding: '12px 14px',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '10px',
                    flexWrap: 'wrap',
                    marginBottom: isOrbitExpanded ? '10px' : '0',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '14px', fontWeight: 800, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      🔭 Shoot Session &amp; Visual Orbit Propagation
                    </span>
                    <span
                      style={{
                        background: selectedOrbitIds.size > 0 ? 'rgba(16, 185, 129, 0.25)' : 'rgba(148, 163, 184, 0.2)',
                        border: selectedOrbitIds.size > 0 ? '1px solid rgba(52, 211, 153, 0.6)' : '1px solid rgba(148, 163, 184, 0.4)',
                        color: selectedOrbitIds.size > 0 ? '#a7f3d0' : '#94a3b8',
                        fontSize: '11.5px',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: '999px',
                      }}
                    >
                      {selectedOrbitIds.size} of {orbitCandidates.length} sibling photos selected
                    </span>
                    {previewData?.propagate_to_orbit && (
                      <span
                        style={{
                          background: 'rgba(139, 92, 246, 0.22)',
                          border: '1px solid rgba(167, 139, 250, 0.55)',
                          color: '#ddd6fe',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '999px',
                        }}
                        title="Your spoken instruction asked to associate tags with sibling frames"
                      >
                        ✨ Voice Directive: Associated Across Sibling Frames
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <button
                      type="button"
                      onClick={handleSelectAllOrbit}
                      style={{
                        background: 'rgba(16, 185, 129, 0.15)',
                        border: '1px solid rgba(52, 211, 153, 0.4)',
                        color: '#6ee7b7',
                        fontSize: '11.5px',
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: '8px',
                        cursor: 'pointer',
                      }}
                      title="Select all currently visible photos in the active filter scope"
                    >
                      ✓ Select Visible ({visibleOrbitCandidates.length})
                    </button>
                    {dayCandidates.length > 0 && dayCandidates.length !== visibleOrbitCandidates.length && (
                      <button
                        type="button"
                        onClick={handleSelectAllDayOrbit}
                        style={{
                          background: 'rgba(59, 130, 246, 0.15)',
                          border: '1px solid rgba(96, 165, 250, 0.4)',
                          color: '#93c5fd',
                          fontSize: '11.5px',
                          fontWeight: 700,
                          padding: '4px 10px',
                          borderRadius: '8px',
                          cursor: 'pointer',
                        }}
                        title="Select all photos taken on this shoot day"
                      >
                        ✓ Select All Day ({dayCandidates.length})
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={handleDeselectAllOrbit}
                      style={{
                        background: 'rgba(255, 255, 255, 0.06)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        color: '#cbd5e1',
                        fontSize: '11.5px',
                        fontWeight: 600,
                        padding: '4px 10px',
                        borderRadius: '8px',
                        cursor: 'pointer',
                      }}
                    >
                      Deselect All
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsOrbitExpanded((prev) => !prev)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#94a3b8',
                        fontSize: '12px',
                        fontWeight: 700,
                        padding: '4px 6px',
                        cursor: 'pointer',
                      }}
                    >
                      {isOrbitExpanded ? '▴ Collapse' : '▾ Expand'}
                    </button>
                  </div>
                </div>

                {/* Multi-Scope Shoot Orbit Filter Tabs */}
                {isOrbitExpanded && (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      flexWrap: 'wrap',
                      marginBottom: '10px',
                      padding: '4px 0',
                    }}
                  >
                    {[
                      { key: 'all', label: `🌐 All Siblings (${orbitCandidates.length})` },
                      { key: 'burst', label: `⚡ Burst (±5m) (${burstCandidates.length})` },
                      { key: 'window', label: `⏱️ Window (±2h) (${windowCandidates.length})` },
                      { key: 'day', label: `📅 Shoot Day (${dayCandidates.length})` },
                      { key: 'visual', label: `✨ Visual Match (${visualCandidates.length})` },
                    ].map((tab) => {
                      const isActive = orbitFilterScope === tab.key;
                      return (
                        <button
                          key={`orbit-scope-${tab.key}`}
                          type="button"
                          onClick={() => setOrbitFilterScope(tab.key)}
                          style={{
                            background: isActive ? 'rgba(59, 130, 246, 0.25)' : 'rgba(255, 255, 255, 0.04)',
                            border: isActive ? '1px solid rgba(96, 165, 250, 0.7)' : '1px solid rgba(255, 255, 255, 0.1)',
                            color: isActive ? '#93c5fd' : '#94a3b8',
                            fontSize: '11px',
                            fontWeight: isActive ? 700 : 500,
                            padding: '3px 10px',
                            borderRadius: '999px',
                            cursor: 'pointer',
                            transition: 'all 0.12s ease',
                          }}
                        >
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Candidate Thumbnail Strip / Grid */}
                {isOrbitExpanded && (
                  <div
                    style={{
                      maxHeight: 'min(380px, 45vh)',
                      overflowY: 'auto',
                      overscrollBehavior: 'contain',
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(135px, 1fr))',
                      gap: '8px',
                      padding: '4px',
                    }}
                  >
                    {visibleOrbitCandidates.map((cand) => {
                      const candId = cand.file_hash || cand.file_path
                      const isSelected = selectedOrbitIds.has(candId)
                      const simPercent = Math.round((cand.similarity || 0) * 100)

                      return (
                        <div
                          key={`orbit-${candId}`}
                          onClick={() => handleToggleOrbitCandidate(candId)}
                          style={{
                            position: 'relative',
                            background: isSelected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.03)',
                            border: isSelected ? '2px solid #10b981' : '1px solid rgba(255, 255, 255, 0.12)',
                            borderRadius: '10px',
                            overflow: 'hidden',
                            cursor: 'pointer',
                            display: 'flex',
                            flexDirection: 'column',
                            transition: 'all 0.12s ease-in-out',
                          }}
                        >
                          <div style={{ position: 'relative', width: '100%', height: '88px', minHeight: '88px', flexShrink: 0, background: '#020617' }}>
                            {cand.thumb_url || cand.preview_url ? (
                              <img
                                src={cand.thumb_url || cand.preview_url}
                                alt={cand.file_name}
                                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                loading="lazy"
                              />
                            ) : (
                              <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b', fontSize: '11px' }}>
                                RAW
                              </div>
                            )}

                            {/* Checkbox overlay */}
                            <div
                              style={{
                                position: 'absolute',
                                top: '5px',
                                left: '5px',
                                width: '18px',
                                height: '18px',
                                borderRadius: '4px',
                                background: isSelected ? '#10b981' : 'rgba(15, 23, 42, 0.8)',
                                border: isSelected ? '1px solid #059669' : '1.5px solid rgba(255, 255, 255, 0.6)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: '#ffffff',
                                fontSize: '12px',
                                fontWeight: 900,
                              }}
                            >
                              {isSelected ? '✓' : ''}
                            </div>

                            {/* Similarity / Target badge */}
                            <div
                              style={{
                                position: 'absolute',
                                top: '5px',
                                right: '5px',
                                background: cand.is_target ? 'rgba(59, 130, 246, 0.9)' : 'rgba(15, 23, 42, 0.85)',
                                color: cand.is_target ? '#ffffff' : '#a7f3d0',
                                fontSize: '10px',
                                fontWeight: 800,
                                padding: '1px 5px',
                                borderRadius: '4px',
                              }}
                            >
                              {cand.is_target ? 'Target' : `${simPercent}% sim`}
                            </div>
                          </div>

                          <div style={{ padding: '4px 6px', fontSize: '11px', color: '#cbd5e1', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            <div style={{ fontWeight: 700, color: isSelected ? '#6ee7b7' : '#f8fafc', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {cand.file_name}
                            </div>
                            <div style={{ fontSize: '10px', color: '#94a3b8' }}>
                              {cand.time_delta_seconds > 0 ? `+${cand.time_delta_seconds}s` : 'Selected Target'}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Error Banner */}
        {errorMsg && (
          <div
            style={{
              background: 'rgba(239, 68, 68, 0.18)',
              border: '1px solid #ef4444',
              color: '#fecaca',
              padding: '10px 14px',
              borderRadius: '10px',
              marginBottom: '12px',
              fontSize: '14px',
              fontWeight: 600,
            }}
          >
            ⚠️ {errorMsg}
          </div>
        )}

        {/* =====================================================================
            MODE 1 PRIMARY ACTIONS: `✓ Commit Approved Tags (Enter ↵)`
           ===================================================================== */}
        {activeTab === 'teach' && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '12px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                ref={commitBtnRef}
                type="button"
                disabled={isSubmitting || selectedPhotos.length === 0}
                onClick={() => handleApplyTeach('instant', true)}
                style={{
                  background: 'linear-gradient(135deg, #059669, #10b981)',
                  border: '1.5px solid #6ee7b7',
                  color: '#052e16',
                  fontSize: '15.5px',
                  fontWeight: 900,
                  padding: '12px 24px',
                  borderRadius: '12px',
                  cursor: isSubmitting ? 'wait' : 'pointer',
                  opacity: isSubmitting || selectedPhotos.length === 0 ? 0.55 : 1,
                  boxShadow: '0 6px 20px rgba(16, 185, 129, 0.35)',
                }}
              >
                {isSubmitting
                  ? 'Committing...'
                  : siblingOrbitCount > 0
                  ? `✓ Commit to ${totalTargetCount} Photos (${selectedPhotos.length} Selected + ${siblingOrbitCount} Sibling Orbit)`
                  : `✓ Commit Approved Tags (Enter ↵)${
                      totalApprovedTeachTags > 0 ? ` [${totalApprovedTeachTags}]` : ''
                    }`}
              </button>

              <button
                type="button"
                disabled={isSubmitting || selectedPhotos.length === 0}
                onClick={() => runTeachPreviewAssessment(instruction, wipeExisting)}
                style={{
                  background: 'rgba(255, 255, 255, 0.08)',
                  border: '1px solid rgba(255, 255, 255, 0.22)',
                  color: '#e2e8f0',
                  fontSize: '13.5px',
                  fontWeight: 700,
                  padding: '11px 16px',
                  borderRadius: '11px',
                  cursor: 'pointer',
                }}
              >
                🔍 Re-Assess Candidates
              </button>

              <button
                type="button"
                disabled={isSubmitting || selectedPhotos.length === 0}
                onClick={() => handleApplyTeach('deep_vlm', true)}
                style={{
                  background: 'rgba(139, 92, 246, 0.18)',
                  border: '1px solid rgba(167, 139, 250, 0.5)',
                  color: '#ddd6fe',
                  fontSize: '13.5px',
                  fontWeight: 700,
                  padding: '11px 16px',
                  borderRadius: '11px',
                  cursor: isSubmitting ? 'wait' : 'pointer',
                  opacity: isSubmitting || selectedPhotos.length === 0 ? 0.55 : 1,
                }}
                title="Commits approved tags and re-runs Qwen2.5-VL 7B vision model (~3s/photo)"
              >
                🧠 Commit + Deep VLM (~3s)
              </button>
            </div>

            {onTriggerUndo && (
              <button
                type="button"
                onClick={onTriggerUndo}
                style={{
                  background: 'rgba(245, 158, 11, 0.16)',
                  border: '1px solid rgba(251, 191, 36, 0.5)',
                  color: '#fde68a',
                  fontSize: '13px',
                  fontWeight: 700,
                  padding: '9px 14px',
                  borderRadius: '10px',
                  cursor: 'pointer',
                }}
              >
                ↩ Undo Last (Cmd+Z)
              </button>
            )}
          </div>
        )}

        {/* =====================================================================
            MODE 2: SCOUT ARCHIVE PRE-COMMIT REVIEW & COMMIT
           ===================================================================== */}
        {activeTab === 'scout' && (
          <div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                flexWrap: 'wrap',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.1)',
                padding: '11px 14px',
                borderRadius: '12px',
                marginBottom: '14px',
              }}
            >
              <label
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '13.5px',
                  fontWeight: 700,
                  color: '#e2e8f0',
                  cursor: 'pointer',
                }}
              >
                <input
                  type="checkbox"
                  checked={autoCreateCollection}
                  onChange={(e) => setAutoCreateCollection(e.target.checked)}
                  style={{ width: '16px', height: '16px', accentColor: '#10b981' }}
                />
                <span>📚 Save as Collection / Book Story</span>
              </label>

              {autoCreateCollection && (
                <input
                  type="text"
                  placeholder="Optional custom Book title (or auto-named)"
                  value={customCollectionName}
                  onChange={(e) => setCustomCollectionName(e.target.value)}
                  style={{
                    flex: 1,
                    minWidth: '200px',
                    background: '#0f172a',
                    border: '1px solid rgba(255,255,255,0.2)',
                    borderRadius: '8px',
                    color: '#fff',
                    padding: '7px 11px',
                    fontSize: '13px',
                  }}
                />
              )}

              <button
                type="button"
                disabled={isSubmitting}
                onClick={handlePreviewScout}
                style={{
                  background: scoutResult
                    ? 'rgba(255,255,255,0.1)'
                    : 'linear-gradient(135deg, #2563eb, #4f46e5)',
                  border: '1px solid rgba(147, 197, 253, 0.5)',
                  color: '#ffffff',
                  fontSize: '14px',
                  fontWeight: 800,
                  padding: '9px 18px',
                  borderRadius: '10px',
                  cursor: isSubmitting ? 'wait' : 'pointer',
                }}
              >
                {isSubmitting && !scoutResult
                  ? '🔎 Probing 849 Vectors...'
                  : '🔎 Assess & Preview Matches'}
              </button>

              {scoutResult && (
                <button
                  ref={commitBtnRef}
                  type="button"
                  disabled={isSubmitting || approvedScoutPhotos.length === 0}
                  onClick={handleCommitScout}
                  style={{
                    background: 'linear-gradient(135deg, #059669, #10b981)',
                    border: '1.5px solid #6ee7b7',
                    color: '#052e16',
                    fontSize: '14.5px',
                    fontWeight: 900,
                    padding: '9px 20px',
                    borderRadius: '10px',
                    cursor: isSubmitting ? 'wait' : 'pointer',
                    boxShadow: '0 6px 20px rgba(16, 185, 129, 0.35)',
                  }}
                >
                  {isSubmitting
                    ? 'Committing...'
                    : `✓ Commit ${approvedScoutPhotos.length} Photos & Tags (Enter ↵)`}
                </button>
              )}
            </div>

            {/* SCOUT PRE-COMMIT REVIEW: Dismissible (`×`) Tag Pills & Candidate Photo Tiles */}
            {scoutResult && (
              <div
                style={{
                  background: 'rgba(15, 23, 42, 0.95)',
                  border: '1.5px solid rgba(52, 211, 153, 0.5)',
                  borderRadius: '14px',
                  padding: '14px 16px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: '12px',
                    flexWrap: 'wrap',
                    marginBottom: '10px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: '#6ee7b7' }}>
                      2. Pre-Commit Review: {approvedScoutPhotos.length} Candidate Matches for "
                      {customCollectionName.trim() || scoutResult.collection_name}"
                    </div>
                    <div style={{ fontSize: '12.5px', color: '#cbd5e1', marginTop: '2px' }}>
                      Click <strong style={{ color: '#fca5a5' }}>×</strong> on any stretched tag or false-positive photo tile below to drop it, then press{' '}
                      <strong style={{ color: '#6ee7b7' }}>Enter ↵</strong> to commit.
                    </div>
                  </div>
                </div>

                {/* Dismissible (`×`) Enriched Tags Pill Row */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '7px',
                    flexWrap: 'wrap',
                    marginBottom: '12px',
                    paddingBottom: '10px',
                    borderBottom: '1px solid rgba(255,255,255,0.08)',
                  }}
                >
                  <span style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 700 }}>
                    Tags to Apply:
                  </span>
                  {approvedScoutTags.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => handleDismissScoutTag(t)}
                      title="Click × to drop this tag"
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: 'rgba(16, 185, 129, 0.2)',
                        border: '1px solid rgba(52, 211, 153, 0.55)',
                        color: '#ecfdf5',
                        fontSize: '12.5px',
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: '999px',
                        cursor: 'pointer',
                      }}
                    >
                      <span>🎙️ {t}</span>
                      <span style={{ color: '#fca5a5', fontWeight: 900 }}>×</span>
                    </button>
                  ))}

                  {/* Inline `+ Add tag` for Scout Mode */}
                  <div
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px dashed rgba(148, 163, 184, 0.45)',
                      borderRadius: '999px',
                      padding: '2px 6px 2px 10px',
                      gap: '4px',
                    }}
                  >
                    <input
                      type="text"
                      data-inline-tag-input="true"
                      value={manualScoutTagInput}
                      onChange={(e) => setManualScoutTagInput(e.target.value)}
                      placeholder="+ Add tag..."
                      style={{
                        background: 'transparent',
                        border: 'none',
                        outline: 'none',
                        color: '#f8fafc',
                        fontSize: '12px',
                        width: '86px',
                      }}
                    />
                    {manualScoutTagInput.trim() && (
                      <button
                        type="button"
                        onClick={handleAddManualScoutTag}
                        style={{
                          background: '#10b981',
                          border: 'none',
                          color: '#052e16',
                          fontWeight: 800,
                          fontSize: '11.5px',
                          padding: '1px 7px',
                          borderRadius: '999px',
                          cursor: 'pointer',
                        }}
                      >
                        +
                      </button>
                    )}
                  </div>
                </div>

                {/* Candidate Photo Grid with `×` Dismiss Button on Each Tile */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(124px, 1fr))',
                    gap: '10px',
                    maxHeight: '280px',
                    overflowY: 'auto',
                    paddingRight: '4px',
                  }}
                >
                  {approvedScoutPhotos.map((m) => {
                    const pid = m.file_hash || m.file_path
                    const isVisualDiscovery = m.scout_match_type === 'visual_discovery'
                    const isSeed = m.scout_match_type === 'seed'
                    return (
                      <div
                        key={pid}
                        style={{
                          background: '#1e293b',
                          border: isVisualDiscovery
                            ? '1.5px solid rgba(167, 139, 250, 0.65)'
                            : '1px solid rgba(255,255,255,0.15)',
                          borderRadius: '10px',
                          overflow: 'hidden',
                          position: 'relative',
                        }}
                      >
                        <div style={{ height: '88px', background: '#090d16', position: 'relative' }}>
                          <img
                            src={m.thumb_url || m.preview_url}
                            alt={m.filename}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                          <span
                            style={{
                              position: 'absolute',
                              top: '5px',
                              left: '5px',
                              background: isSeed
                                ? 'rgba(245, 158, 11, 0.92)'
                                : isVisualDiscovery
                                ? 'rgba(124, 58, 237, 0.92)'
                                : 'rgba(37, 99, 235, 0.9)',
                              color: '#fff',
                              fontSize: '10px',
                              fontWeight: 800,
                              padding: '2px 6px',
                              borderRadius: '6px',
                            }}
                          >
                            {isSeed ? '★ Seed' : isVisualDiscovery ? '✨ Visual AI' : '🏷️ Tagged'}
                          </span>

                          {/* Dismiss (`×`) Button on Candidate Photo Tile */}
                          <button
                            type="button"
                            onClick={() => handleDismissScoutPhoto(pid)}
                            title="Remove this photo from Scout matches"
                            style={{
                              position: 'absolute',
                              top: '4px',
                              right: '4px',
                              width: '22px',
                              height: '22px',
                              borderRadius: '999px',
                              background: 'rgba(15, 23, 42, 0.88)',
                              border: '1px solid rgba(248, 113, 113, 0.75)',
                              color: '#fca5a5',
                              fontSize: '14px',
                              fontWeight: 900,
                              lineHeight: 1,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              cursor: 'pointer',
                            }}
                          >
                            ×
                          </button>
                        </div>
                        <div style={{ padding: '5px 7px' }}>
                          <div
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              color: '#f1f5f9',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                            title={m.title || m.filename}
                          >
                            {m.title || m.filename}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
