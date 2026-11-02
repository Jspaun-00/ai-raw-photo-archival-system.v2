import React, { useState, useEffect } from 'react';
import { X, Layers, Star, Sparkles, CheckCircle, Image as ImageIcon } from 'lucide-react';

export default function SequenceDrawer({
  sequenceId,
  onClose,
  onSelectPhoto,
}) {
  const [sequenceData, setSequenceData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sequenceId) return;
    setLoading(true);
    fetch(`/api/sequence/${sequenceId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load sequence details');
        return res.json();
      })
      .then((data) => {
        setSequenceData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Error fetching sequence:', err);
        setLoading(false);
      });
  }, [sequenceId]);

  if (!sequenceId) return null;

  return (
    <div className="fixed inset-0 z-40 bg-black/80 backdrop-blur-sm flex justify-end select-none">
      <div className="w-full max-w-4xl bg-studio-panel border-l border-studio-border h-full flex flex-col shadow-2xl animate-in slide-in-from-right duration-200">
        {/* Header */}
        <div className="h-14 bg-studio-bg border-b border-studio-border px-5 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/30 rounded-sm text-emerald-400">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-mono font-medium text-white">
                Strafing Sequence: <span className="text-emerald-400">{sequenceId}</span>
              </h2>
              <p className="text-[11px] font-mono text-studio-textDim">
                {sequenceData ? `${sequenceData.total_frames} frames in continuous run (Sequence Heroes first)` : 'Loading frames...'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 hover:bg-studio-hover text-studio-textDim hover:text-white rounded-sm transition-colors"
            title="Close Drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 font-mono text-xs text-studio-textDim">
              <div className="w-6 h-6 border-2 border-studio-accent border-t-transparent rounded-full animate-spin mb-2"></div>
              <span>Loading sequence frames...</span>
            </div>
          ) : sequenceData && sequenceData.frames ? (
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
              {sequenceData.frames.map((frame, idx) => {
                const isHero = frame.is_sequence_hero === 1;
                const thumb = frame.thumb_url || (frame.thumb_360_path ? `/previews/thumbs_360/${frame.thumb_360_path.split('/').pop()}` : null);
                const fname = frame.file_path ? frame.file_path.split('/').pop() : `Frame #${idx + 1}`;

                return (
                  <div
                    key={frame.file_path || frame.file_hash}
                    onClick={() => {
                      onSelectPhoto(frame, sequenceData.frames);
                      onClose();
                    }}
                    className={`group relative flex flex-col bg-studio-card border rounded-sm overflow-hidden cursor-pointer transition-all ${
                      isHero
                        ? 'border-emerald-500/80 shadow-[0_0_12px_rgba(16,185,129,0.15)] ring-1 ring-emerald-500/40'
                        : 'border-studio-border hover:border-studio-borderLight'
                    }`}
                  >
                    {/* Thumbnail */}
                    <div className="relative aspect-[4/3] bg-studio-bg overflow-hidden">
                      {thumb ? (
                        <img
                          src={thumb}
                          alt={fname}
                          className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center">
                          <ImageIcon className="w-6 h-6 text-studio-borderLight" />
                        </div>
                      )}

                      {/* Hero Marker */}
                      {isHero && (
                        <div className="absolute top-1.5 left-1.5 px-1.5 py-0.5 bg-emerald-950/90 border border-emerald-500 text-emerald-300 text-[9px] font-mono font-semibold rounded-sm shadow-sm flex items-center gap-1">
                          <Star className="w-2.5 h-2.5 fill-current" />
                          <span>HERO</span>
                        </div>
                      )}

                      {/* Frame Index Marker */}
                      <div className="absolute bottom-1.5 right-1.5 px-1 py-0.5 bg-black/80 text-white/90 text-[9px] font-mono rounded-sm">
                        #{frame.sequence_frame_index !== undefined ? frame.sequence_frame_index + 1 : idx + 1}
                      </div>
                    </div>

                    {/* Frame Details Strip */}
                    <div className="p-2 font-mono text-[10px] space-y-0.5 bg-studio-panel">
                      <div className="truncate text-white font-medium" title={fname}>
                        {fname}
                      </div>
                      <div className="flex items-center justify-between text-studio-textDim">
                        <span>Aesth: {frame.aesthetic_score ? Number(frame.aesthetic_score).toFixed(1) : '—'}</span>
                        <span className={frame.is_unsharp ? 'text-studio-crimson' : 'text-studio-emerald'}>
                          Sharp: {frame.sharpness_score ? Number(frame.sharpness_score).toFixed(0) : '—'}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center font-mono text-xs text-studio-textDim py-12">
              No sequence frames found.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

