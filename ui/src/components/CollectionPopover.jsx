import React, { useState, useEffect, useRef, useMemo } from 'react';

export default function CollectionPopover({
  photo,
  collections = [],
  photoCollections = [],
  onTogglePhotoInCollection,
  onToggleCollection,
  onCreateCollectionWithPhoto,
  onCreateAndAdd,
  onClose,
  compact = false,
  anchorStyle = {},
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [creating, setCreating] = useState(false);
  const containerRef = useRef(null);

  const toggleHandler = onTogglePhotoInCollection || onToggleCollection;
  const createHandler = onCreateCollectionWithPhoto || onCreateAndAdd;

  // Determine which collections contain this photo
  const memberIds = useMemo(() => {
    const ids = new Set(
      (photoCollections || []).map((c) => Number(typeof c === 'object' ? c.id : c))
    );
    const fHash = photo?.file_hash;
    const fPath = photo?.file_path;
    const fId = photo?.id;
    for (const col of collections) {
      if (Array.isArray(col.photo_ids)) {
        if (
          (fHash && col.photo_ids.includes(fHash)) ||
          (fPath && col.photo_ids.includes(fPath)) ||
          (fId && col.photo_ids.includes(fId))
        ) {
          ids.add(Number(col.id));
        }
      }
    }
    return ids;
  }, [collections, photoCollections, photo]);

  const closePopover = () => {
    setIsOpen(false);
    if (onClose) onClose();
  };

  // Attach outside-click and Escape listeners ONLY when open
  useEffect(() => {
    if (!isOpen) return undefined;

    const handleOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        closePopover();
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        closePopover();
      }
    };

    document.addEventListener('mousedown', handleOutside);
    document.addEventListener('keydown', handleKeyDown, true);
    return () => {
      document.removeEventListener('mousedown', handleOutside);
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [isOpen]);

  const handleToggle = async (e, col) => {
    e.stopPropagation();
    if (!toggleHandler || busyId !== null) return;
    setBusyId(col.id);
    try {
      await toggleHandler(col.id, photo, memberIds.has(Number(col.id)));
    } finally {
      setBusyId(null);
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    const trimmed = newName.trim();
    if (!trimmed || !createHandler || creating) return;
    setCreating(true);
    try {
      await createHandler(trimmed, photo, newDesc.trim());
      setNewName('');
      setNewDesc('');
    } finally {
      setCreating(false);
    }
  };

  const inAnyCollection = memberIds.size > 0;

  return (
    <div
      ref={containerRef}
      onClick={(e) => e.stopPropagation()}
      style={{ position: 'relative', display: 'inline-block' }}
    >
      {/* Trigger Button */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setIsOpen((prev) => !prev);
        }}
        title={
          inAnyCollection
            ? `In ${memberIds.size} Book/Collection(s) — Click to manage`
            : 'Add to Book or Curated Collection'
        }
        style={
          compact
            ? {
                padding: '3px 7px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 700,
                cursor: 'pointer',
                border: inAnyCollection
                  ? '1px solid rgba(245, 158, 11, 0.8)'
                  : '1px solid rgba(255, 255, 255, 0.2)',
                background: inAnyCollection
                  ? 'rgba(245, 158, 11, 0.88)'
                  : 'rgba(9, 11, 16, 0.78)',
                color: inAnyCollection ? '#090b10' : '#f8fafc',
                backdropFilter: 'blur(6px)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '3px',
                lineHeight: 1.2,
              }
            : {
                padding: '6px 12px',
                borderRadius: '7px',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
                border: inAnyCollection
                  ? '1px solid #f59e0b'
                  : '1px solid #334155',
                background: inAnyCollection
                  ? 'rgba(245, 158, 11, 0.2)'
                  : '#1e293b',
                color: inAnyCollection ? '#fbbf24' : '#f1f5f9',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }
        }
      >
        <span>{compact ? (inAnyCollection ? `📚✓${memberIds.size}` : '+📚') : '📚 Add to Book'}</span>
        {!compact && inAnyCollection && (
          <span
            style={{
              background: '#f59e0b',
              color: '#090b10',
              borderRadius: '999px',
              padding: '0 6px',
              fontSize: '11px',
              fontWeight: 800,
            }}
          >
            {memberIds.size}
          </span>
        )}
      </button>

      {/* Unmounted by default; only rendered when explicitly opened */}
      {isOpen && (
        <div
          onClick={(e) => e.stopPropagation()}
          onKeyDown={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: 'calc(100% + 6px)',
            right: 0,
            zIndex: 350,
            width: '320px',
            background: '#11141d',
            border: '1.5px solid #334155',
            borderRadius: '12px',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.85)',
            padding: '14px',
            color: '#f8fafc',
            userSelect: 'text',
            ...anchorStyle,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '10px',
              paddingBottom: '8px',
              borderBottom: '1px solid #1e293b',
            }}
          >
            <span style={{ fontSize: '14px', fontWeight: 800, color: '#fbbf24' }}>
              📚 Add to Book / Collection
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                closePopover();
              }}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '6px',
                color: '#cbd5e1',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 700,
                padding: '2px 7px',
              }}
            >
              ✕
            </button>
          </div>

          {/* Top High-Visibility Create New Book / Collection Form */}
          <form
            onSubmit={handleCreateSubmit}
            style={{
              background: '#171c28',
              border: '1px solid #2e3648',
              borderRadius: '10px',
              padding: '10px',
              marginBottom: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
            }}
          >
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '13px',
                  fontWeight: 700,
                  color: '#e2e8f0',
                  marginBottom: '4px',
                }}
              >
                Book or Collection Name
              </label>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.stopPropagation()}
                placeholder="e.g., Desert Panoramas Book"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '7px',
                  background: '#0d1017',
                  border: '1.5px solid #475569',
                  color: '#ffffff',
                  fontSize: '14px',
                  outline: 'none',
                  userSelect: 'text',
                }}
              />
            </div>
            <div>
              <label
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#cbd5e1',
                  marginBottom: '4px',
                }}
              >
                Notes / Subtitle (Optional)
              </label>
              <input
                type="text"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                onKeyDown={(e) => e.stopPropagation()}
                placeholder="e.g., Print selections for 2026 monograph"
                style={{
                  width: '100%',
                  padding: '7px 10px',
                  borderRadius: '7px',
                  background: '#0d1017',
                  border: '1px solid #334155',
                  color: '#f1f5f9',
                  fontSize: '13px',
                  outline: 'none',
                  userSelect: 'text',
                }}
              />
            </div>
            <button
              type="submit"
              disabled={!newName.trim() || creating}
              style={{
                width: '100%',
                padding: '9px 12px',
                borderRadius: '8px',
                border: '1px solid #f59e0b',
                background: newName.trim()
                  ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                  : '#1e293b',
                color: newName.trim() ? '#090b10' : '#64748b',
                fontSize: '13px',
                fontWeight: 800,
                cursor: newName.trim() ? 'pointer' : 'not-allowed',
              }}
            >
              {creating ? 'Creating...' : '+ Create New Book / Collection'}
            </button>
          </form>

          {/* Existing Books / Collections List */}
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', marginBottom: '6px' }}>
            EXISTING BOOKS & COLLECTIONS ({collections.length})
          </div>
          <div
            style={{
              maxHeight: '190px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '5px',
            }}
          >
            {collections.length === 0 ? (
              <div style={{ fontSize: '13px', color: '#94a3b8', padding: '8px 4px' }}>
                No collections yet. Type a name above to create your first book!
              </div>
            ) : (
              collections.map((col) => {
                const checked = memberIds.has(Number(col.id));
                const isBusy = busyId === col.id;
                const count = col.photo_count ?? col.item_count ?? 0;
                return (
                  <button
                    type="button"
                    key={col.id}
                    onClick={(e) => handleToggle(e, col)}
                    disabled={isBusy}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: checked ? '1px solid rgba(245, 158, 11, 0.55)' : '1px solid #242a38',
                      background: checked ? 'rgba(245, 158, 11, 0.16)' : '#161a24',
                      color: checked ? '#fbbf24' : '#e2e8f0',
                      cursor: 'pointer',
                      fontSize: '14px',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <span
                        style={{
                          width: '18px',
                          height: '18px',
                          borderRadius: '4px',
                          border: checked ? '1px solid #f59e0b' : '1px solid #475569',
                          background: checked ? '#f59e0b' : 'transparent',
                          color: '#090b10',
                          display: 'inline-flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          fontWeight: 900,
                          flexShrink: 0,
                        }}
                      >
                        {checked ? '✓' : ''}
                      </span>
                      <span
                        style={{
                          fontWeight: checked ? 700 : 500,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {col.name}
                      </span>
                    </span>
                    <span style={{ fontSize: '12px', color: '#94a3b8', marginLeft: '6px', flexShrink: 0 }}>
                      {count}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
