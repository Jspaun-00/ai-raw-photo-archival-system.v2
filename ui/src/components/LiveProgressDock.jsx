import React from 'react'

function formatSeconds(sec) {
  if (sec === null || sec === undefined || Number.isNaN(Number(sec)) || Number(sec) < 0) {
    return null
  }
  const totalSec = Math.round(Number(sec))
  const mins = Math.floor(totalSec / 60)
  const remSec = totalSec % 60
  return `${String(mins).padStart(2, '0')}:${String(remSec).padStart(2, '0')}`
}

export default function LiveProgressDock({
  jobStatus,
  onPause,
  onResume,
  onCancel,
  onDismiss,
  onOpenFullPipelineModal,
}) {
  if (!jobStatus) return null

  const isRunning = Boolean(jobStatus.running)
  const isPaused = Boolean(jobStatus.paused)
  const isCancelled = Boolean(jobStatus.cancelled)
  const hasError = Boolean(jobStatus.error)

  // Only show dock when running, paused, or when recently finished/cancelled and not yet dismissed
  if (!isRunning && !jobStatus._keepVisible) {
    return null
  }

  const processed = Number(jobStatus.processed || 0)
  const total = Number(jobStatus.total || 0)
  const pct = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : isRunning ? 15 : 100
  const elapsedStr = formatSeconds(jobStatus.elapsed_seconds)
  const etaStr = formatSeconds(jobStatus.eta_seconds)

  const statusColor = hasError
    ? '#f87171'
    : isCancelled
    ? '#fbbf24'
    : isPaused
    ? '#f59e0b'
    : isRunning
    ? '#60a5fa'
    : '#34d399'

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '22px',
        right: '24px',
        zIndex: 9400,
        width: '410px',
        maxWidth: 'calc(100vw - 36px)',
        background: 'rgba(15, 19, 28, 0.97)',
        border: `1.5px solid ${statusColor}`,
        borderRadius: '14px',
        boxShadow: '0 18px 48px rgba(0, 0, 0, 0.75)',
        padding: '14px 16px',
        color: '#f8fafc',
        backdropFilter: 'blur(14px)',
      }}
    >
      {/* Header Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '10px',
          marginBottom: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
          <span
            style={{
              width: '10px',
              height: '10px',
              borderRadius: '50%',
              background: statusColor,
              boxShadow: isRunning && !isPaused ? `0 0 10px ${statusColor}` : 'none',
              flexShrink: 0,
            }}
          />
          <span
            style={{
              fontSize: '14px',
              fontWeight: 700,
              color: '#ffffff',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={jobStatus.title || jobStatus.phase || 'Background Task'}
          >
            {jobStatus.title || 'Studio Background Operation'}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          {onOpenFullPipelineModal && (
            <button
              type="button"
              onClick={onOpenFullPipelineModal}
              style={{
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.18)',
                color: '#cbd5e1',
                fontSize: '11px',
                fontWeight: 600,
                padding: '3px 8px',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
              title="Open detailed status modal"
            >
              Details
            </button>
          )}
          {!isRunning && onDismiss && (
            <button
              type="button"
              onClick={onDismiss}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                fontSize: '15px',
                fontWeight: 700,
                cursor: 'pointer',
                padding: '2px 5px',
              }}
              title="Dismiss notification"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Phase & Current File */}
      <div
        style={{
          fontSize: '12.5px',
          color: '#cbd5e1',
          marginBottom: '8px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {isPaused ? '⏸ Paused — ' : ''}
        {jobStatus.phase || 'Processing...'}
      </div>

      {/* Progress Bar */}
      <div
        style={{
          width: '100%',
          height: '8px',
          background: 'rgba(255, 255, 255, 0.1)',
          borderRadius: '999px',
          overflow: 'hidden',
          marginBottom: '9px',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: hasError
              ? '#ef4444'
              : isPaused
              ? '#f59e0b'
              : 'linear-gradient(90deg, #3b82f6, #38bdf8, #34d399)',
            transition: 'width 0.25s ease',
          }}
        />
      </div>

      {/* Metrics & Controls Row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px', color: '#94a3b8' }}>
          {total > 0 && (
            <span style={{ color: '#f1f5f9', fontWeight: 700 }}>
              {processed} / {total} ({pct}%)
            </span>
          )}
          {elapsedStr && <span>Elapsed: {elapsedStr}</span>}
          {isRunning && !isPaused && etaStr && (
            <span style={{ color: '#93c5fd', fontWeight: 600 }}>ETA: ~{etaStr}</span>
          )}
        </div>

        {/* Live Action Controls */}
        {isRunning && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            {isPaused ? (
              <button
                type="button"
                onClick={onResume}
                style={{
                  background: '#10b981',
                  border: '1px solid #34d399',
                  color: '#052e16',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '4px 10px',
                  borderRadius: '7px',
                  cursor: 'pointer',
                }}
              >
                ▶ Resume
              </button>
            ) : (
              <button
                type="button"
                onClick={onPause}
                style={{
                  background: 'rgba(245, 158, 11, 0.18)',
                  border: '1px solid rgba(245, 158, 11, 0.5)',
                  color: '#fcd34d',
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '4px 10px',
                  borderRadius: '7px',
                  cursor: 'pointer',
                }}
              >
                ⏸ Pause
              </button>
            )}

            <button
              type="button"
              onClick={onCancel}
              style={{
                background: 'rgba(239, 68, 68, 0.18)',
                border: '1px solid rgba(239, 68, 68, 0.5)',
                color: '#fca5a5',
                fontSize: '12px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '7px',
                cursor: 'pointer',
              }}
              title="Stop early while keeping all items completed so far"
            >
              ✕ Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

