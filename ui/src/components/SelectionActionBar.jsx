import React, { useState } from 'react'

export default function SelectionActionBar({
  selectedCount = 0,
  totalVisibleCount = 0,
  totalCatalogCount = 0,
  isSelectingAll = false,
  isBatchBusy = false,
  collections = [],
  onSelectAll,
  onSelectAllInCatalog,
  onClearSelection,
  onBatchClearTags,
  onBatchReassess,
  onOpenVoiceTeach,
  onOpenVoiceScout,
  onBatchAddToCollection,
  onCreateCollectionWithSelected,
}) {
  const [showBookMenu, setShowBookMenu] = useState(false)
  const [newBookName, setNewBookName] = useState('')
  const [busyBook, setBusyBook] = useState(false)

  if (!selectedCount || selectedCount <= 0) return null

  const handleAddExisting = async (colId) => {
    if (!onBatchAddToCollection) return
    setBusyBook(true)
    try {
      await onBatchAddToCollection(colId)
      setShowBookMenu(false)
    } finally {
      setBusyBook(false)
    }
  }

  const handleCreateNew = async (e) => {
    e.preventDefault()
    if (!newBookName.trim() || !onCreateCollectionWithSelected) return
    setBusyBook(true)
    try {
      await onCreateCollectionWithSelected(newBookName.trim())
      setNewBookName('')
      setShowBookMenu(false)
    } finally {
      setBusyBook(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '22px',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 9300,
        background: 'rgba(13, 18, 28, 0.97)',
        border: '1.5px solid rgba(99, 102, 241, 0.65)',
        borderRadius: '16px',
        boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8)',
        padding: '8px 16px',
        display: 'flex',
        flexWrap: 'nowrap',
        alignItems: 'center',
        justifyContent: 'center',
        width: 'max-content',
        maxWidth: '96vw',
        gap: '10px',
        color: '#f8fafc',
        backdropFilter: 'blur(16px)',
        whiteSpace: 'nowrap',
      }}
    >
      {/* Selected Count Badge */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(99, 102, 241, 0.22)',
          border: '1px solid rgba(129, 140, 248, 0.5)',
          padding: '6px 12px',
          borderRadius: '10px',
          fontWeight: 700,
          fontSize: '14px',
          color: '#e0e7ff',
        }}
      >
        <span>✓ {selectedCount.toLocaleString()} Selected</span>
      </div>

      {/* Select All / Clear */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
        {totalVisibleCount > selectedCount && (
          <button
            type="button"
            onClick={onSelectAll}
            disabled={isSelectingAll}
            title="Select all currently loaded photos on the grid (Cmd+A)"
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.18)',
              color: '#e2e8f0',
              fontSize: '13px',
              fontWeight: 600,
              padding: '7px 11px',
              borderRadius: '9px',
              cursor: 'pointer',
            }}
          >
            Select Loaded ({totalVisibleCount.toLocaleString()})
          </button>
        )}
        {onSelectAllInCatalog && totalCatalogCount > selectedCount && totalCatalogCount > totalVisibleCount && (
          <button
            type="button"
            onClick={onSelectAllInCatalog}
            disabled={isSelectingAll}
            title={`Select all ${totalCatalogCount.toLocaleString()} matching photos across the entire active catalog/filter`}
            style={{
              background: 'rgba(99, 102, 241, 0.18)',
              border: '1px solid rgba(129, 140, 248, 0.45)',
              color: '#c7d2fe',
              fontSize: '13px',
              fontWeight: 700,
              padding: '7px 11px',
              borderRadius: '9px',
              cursor: isSelectingAll ? 'wait' : 'pointer',
            }}
          >
            {isSelectingAll ? '⏳ Selecting...' : `Select All (${totalCatalogCount.toLocaleString()})`}
          </button>
        )}
        <button
          type="button"
          onClick={onClearSelection}
          title="Clear current photo selection"
          style={{
            background: 'rgba(255, 255, 255, 0.06)',
            border: '1px solid rgba(255, 255, 255, 0.16)',
            color: '#cbd5e1',
            fontSize: '13px',
            fontWeight: 600,
            padding: '7px 11px',
            borderRadius: '9px',
            cursor: 'pointer',
          }}
        >
          ✕ Clear
        </button>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.14)' }} />

      {/* Pure-Vision Bulk AI Actions + Voice Teach AI */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'nowrap' }}>
        {onBatchClearTags && (
          <button
            type="button"
            disabled={isBatchBusy}
            onClick={onBatchClearTags}
            style={{
              background: 'rgba(239, 68, 68, 0.16)',
              border: '1px solid rgba(248, 113, 113, 0.5)',
              color: '#fca5a5',
              fontSize: '13.5px',
              fontWeight: 700,
              padding: '8px 13px',
              borderRadius: '10px',
              cursor: isBatchBusy ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title={`Wipe all AI tags cleanly across ${selectedCount.toLocaleString()} selected photo(s) (Cmd+Z to Undo)`}
          >
            <span>🧹 Clear Tags</span>
          </button>
        )}

        {onBatchReassess && (
          <button
            type="button"
            disabled={isBatchBusy}
            onClick={() => onBatchReassess('fast_vectors')}
            style={{
              background: 'rgba(245, 158, 11, 0.18)',
              border: '1px solid rgba(251, 191, 36, 0.55)',
              color: '#fde68a',
              fontSize: '13.5px',
              fontWeight: 700,
              padding: '8px 13px',
              borderRadius: '10px',
              cursor: isBatchBusy ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title={`Run pure-vision OpenCLIP + 6-region spatial subject & scene tagging across ${selectedCount.toLocaleString()} selected photo(s) (no text prompt needed)`}
          >
            <span>⚡ Basic Tag</span>
          </button>
        )}

        {onBatchReassess && (
          <button
            type="button"
            disabled={isBatchBusy}
            onClick={() => onBatchReassess('deep_vlm')}
            style={{
              background: 'rgba(56, 189, 248, 0.18)',
              border: '1px solid rgba(56, 189, 248, 0.55)',
              color: '#bae6fd',
              fontSize: '13.5px',
              fontWeight: 700,
              padding: '8px 13px',
              borderRadius: '10px',
              cursor: isBatchBusy ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
            title={`Run pure-vision Deep VLM (qwen2.5vl:7b) + multi-region subject detection across ${selectedCount.toLocaleString()} selected photo(s) using ONLY the images themselves`}
          >
            <span>🧠 Deep VLM</span>
          </button>
        )}

        <button
          type="button"
          onClick={onOpenVoiceTeach}
          style={{
            background: 'linear-gradient(135deg, #4f46e5, #7c3aed)',
            border: '1px solid #a78bfa',
            color: '#ffffff',
            fontSize: '13.5px',
            fontWeight: 700,
            padding: '8px 14px',
            borderRadius: '10px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '7px',
            boxShadow: '0 4px 16px rgba(124, 58, 237, 0.45)',
          }}
          title="Speak or type context to teach custom tags or locations for the selected photos"
        >
          <span>🎙️ AI Voice Tag</span>
        </button>
      </div>

      <div style={{ width: '1px', height: '24px', background: 'rgba(255,255,255,0.14)' }} />

      {/* Voice Scout Similar / Story Button */}
      <button
        type="button"
        onClick={onOpenVoiceScout}
        style={{
          background: 'rgba(16, 185, 129, 0.2)',
          border: '1px solid rgba(52, 211, 153, 0.55)',
          color: '#6ee7b7',
          fontSize: '13px',
          fontWeight: 700,
          padding: '8px 13px',
          borderRadius: '10px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
        title="Use selected photos as visual seeds to hunt for matching photos across the archive & build a Collection/Book"
      >
        <span>🔎 Scout Similar</span>
      </button>

      {/* Add Selected to Book / Collection */}
      <div style={{ position: 'relative' }}>
        <button
          type="button"
          onClick={() => setShowBookMenu((prev) => !prev)}
          style={{
            background: 'rgba(245, 158, 11, 0.18)',
            border: '1px solid rgba(251, 191, 36, 0.5)',
            color: '#fde68a',
            fontSize: '13.5px',
            fontWeight: 700,
            padding: '8px 14px',
            borderRadius: '10px',
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
              boxShadow: '0 16px 40px rgba(0,0,0,0.8)',
              zIndex: 9500,
            }}
          >
            <div style={{ fontSize: '12.5px', fontWeight: 700, color: '#f8fafc', marginBottom: '8px' }}>
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
                      fontSize: '13px',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>📚 {col.name}</span>
                    <span style={{ color: '#94a3b8', fontSize: '11.5px' }}>{col.item_count || 0}</span>
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
                  fontSize: '12.5px',
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
                  fontSize: '12.5px',
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
    </div>
  )
}

