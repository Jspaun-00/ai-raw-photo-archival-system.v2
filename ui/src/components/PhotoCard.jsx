import React, { useState } from 'react';
import { Star, Layers, CheckCircle2, Image as ImageIcon } from 'lucide-react';
import CollectionPopover from './CollectionPopover.jsx';

export default function PhotoCard({
  photo,
  onClick,
  onOpenSequence,
  onUpdateStar,
  onTagClick,
  collections = [],
  onTogglePhotoInCollection,
  onCreateCollectionWithPhoto,
  onOpenCollectionsModal,
  isSelected = false,
  onToggleSelect,
}) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [hoverRating, setHoverRating] = useState(null);

  const thumbUrl = photo.thumb_url || (photo.thumb_360_path ? `/previews/thumbs_360/${photo.thumb_360_path.split('/').pop()}` : null);
  const isKeeper = photo.in_keepers === 1 || photo.star_rating >= 4;
  const isSequenceStack = (photo.sequence_length || 0) > 1;
  const hasSibling = Boolean(photo.sibling_path);
  const currentStars = photo.star_rating || 0;

  const handleStarClick = (e, rating) => {
    e.stopPropagation();
    const newRating = rating === currentStars ? 0 : rating;
    if (onUpdateStar) {
      onUpdateStar(photo, newRating);
    }
  };

  const handleSequenceClick = (e) => {
    e.stopPropagation();
    if (onOpenSequence && photo.sequence_id) {
      onOpenSequence(photo.sequence_id);
    }
  };

  // Format camera / exposure minimal tag
  const exposureParts = [];
  if (photo.shutter_speed) exposureParts.push(photo.shutter_speed);
  if (photo.aperture) exposureParts.push(`f/${photo.aperture}`);
  if (photo.iso) exposureParts.push(`ISO ${photo.iso}`);
  const exposureLine = exposureParts.join(' · ');

  // Extract up to 3 clean harvested / AI tags for card footer pills
  const parseList = (v) => {
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

  const BOILERPLATE_CARD_TAGS = new Set([
    'mitch rouse aerials',
    'mitch_rouse_aerials',
    'mitch rouse',
    'aerials',
    'msr',
    'keepers',
    'to print',
    'book',
    'phase',
    'hassy',
    'd',
    'west coast imaging',
    'west coast imaging*  alice',
    'alice',
    'staff',
    'panoframes',
    'vert pano',
    'location_review_needed',
    'location_burst_inherited',
    'needs_review',
    'unknown',
    'archival',
  ]);

  const isBoilerplateTag = (tag) => {
    const tl = String(tag || '').trim().toLowerCase();
    if (!tl || tl.length <= 1) return true;
    if (tl === 'mitch rouse (subject)' || tl === 'identity|mitch rouse' || tl === 'mitch shooting') return false;
    if (BOILERPLATE_CARD_TAGS.has(tl)) return true;
    if (tl.includes('mitch rouse aerials') || tl.includes('mitch_rouse_aerials') || tl.includes('west coast imaging')) return true;
    return false;
  };

  const allCardTags = [];
  for (const src of [photo.user_taught_tags, photo.tags, photo.lrcat_keywords, photo.existing_keywords, photo.key_subjects]) {
    for (const t of parseList(src)) {
      const clean = String(t).trim().replace(/_/g, ' ');
      if (clean && !isBoilerplateTag(clean) && !allCardTags.some((x) => x.toLowerCase() === clean.toLowerCase())) {
        allCardTags.push(clean);
      }
    }
  }
  const topCardTags = allCardTags.slice(0, 3);
  const extraTagCount = Math.max(0, allCardTags.length - topCardTags.length);

  const filename = photo.file_path ? photo.file_path.split('/').pop() : 'RAW Photo';

  return (
    <div
      onClick={(e) => {
        if ((e.shiftKey || e.metaKey || e.ctrlKey) && onToggleSelect) {
          e.preventDefault();
          e.stopPropagation();
          onToggleSelect(photo, e);
          return;
        }
        onClick(photo);
      }}
      className={`group relative flex flex-col bg-studio-card border rounded-sm overflow-hidden cursor-pointer transition-all duration-150 select-none shadow-sm hover:shadow-md ${
        isSelected
          ? 'border-amber-400 ring-2 ring-amber-400/60'
          : 'border-studio-border hover:border-studio-accent/70'
      }`}
    >
      {/* Thumbnail Aspect Ratio Box (Locked dimensions so thumbnails never expand or bleed on re-render) */}
      <div
        className="relative aspect-[4/3] bg-studio-bg overflow-hidden flex items-center justify-center"
        style={{
          position: 'relative',
          width: '100%',
          aspectRatio: '4 / 3',
          height: '196px',
          minHeight: '160px',
          maxHeight: '210px',
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        {/* Placeholder shimmer */}
        {!imgLoaded && !imgError && (
          <div className="absolute inset-0 bg-studio-panel animate-pulse flex items-center justify-center">
            <ImageIcon className="w-6 h-6 text-studio-border" />
          </div>
        )}

        {thumbUrl && !imgError ? (
          <img
            src={thumbUrl}
            alt={filename}
            loading="lazy"
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgError(true)}
            className={`w-full h-full object-cover transition-opacity duration-200 group-hover:scale-[1.02] ${
              imgLoaded ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'cover',
              display: 'block',
            }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-4 text-center">
            <ImageIcon className="w-8 h-8 text-studio-borderLight mb-1" />
            <span className="text-[10px] font-mono text-studio-textDim">Preview Pending</span>
          </div>
        )}

        {/* Multi-Photo Selection Checkbox + Minimal Subtle Status Badges */}
        <div className="absolute top-1.5 left-1.5 flex items-center gap-1.5 z-10">
          {onToggleSelect && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleSelect(photo, e);
              }}
              title="Select photo (Shift+Click to select a range)"
              className={`w-5 h-5 rounded flex items-center justify-center border transition-all cursor-pointer shadow ${
                isSelected
                  ? 'bg-amber-500 border-amber-400 text-zinc-950 opacity-100 scale-105'
                  : 'bg-black/75 hover:bg-black/90 border-white/40 text-transparent opacity-0 group-hover:opacity-100'
              }`}
            >
              <span className="text-[11px] font-black leading-none">{isSelected ? '✓' : ''}</span>
            </button>
          )}
          {isKeeper && (
            <span className="px-1.5 py-0.5 bg-black/75 backdrop-blur-sm text-studio-gold text-[10px] font-mono tracking-wider font-semibold border border-studio-gold/30 rounded-sm flex items-center gap-1 shadow-sm pointer-events-none">
              👑 KEEPERS
            </span>
          )}
          {hasSibling && (
            <span className="px-1 py-0.5 bg-black/75 backdrop-blur-sm text-blue-300 text-[9px] font-mono border border-blue-500/30 rounded-sm pointer-events-none">
              RAW+TIF
            </span>
          )}
          {photo.scout_match_source === 'visual_ai' && (
            <span className="px-1.5 py-0.5 bg-purple-950/90 backdrop-blur-sm text-purple-200 text-[9px] font-mono border border-purple-400/50 rounded-sm pointer-events-none">
              ✨ Visual AI
            </span>
          )}
        </div>

        {/* Multi-frame sequence stack indicator */}
        {isSequenceStack && (
          <button
            onClick={handleSequenceClick}
            className="absolute top-1.5 right-1.5 px-1.5 py-0.5 bg-black/80 hover:bg-studio-panel backdrop-blur-sm text-emerald-400 text-[10px] font-mono border border-emerald-500/30 rounded-sm flex items-center gap-1 shadow-sm hover:border-emerald-400 transition-colors"
            title={`Sequence stack containing ${photo.sequence_length} continuous frames. Click to expand drawer.`}
          >
            <Layers className="w-3 h-3 text-emerald-400" />
            <span>📚 {photo.sequence_length}</span>
          </button>
        )}
      </div>

      {/* Clean Bottom Info Strip */}
      <div className="p-2 bg-studio-panel border-t border-studio-border/70 flex flex-col gap-1">
        {/* Row 1: Filename & Location */}
        <div className="flex items-center justify-between text-xs font-mono">
          <span
            className="truncate text-studio-text hover:text-white font-medium max-w-[70%]"
            title={photo.file_path}
          >
            {filename}
          </span>
          <span className="text-[10px] text-studio-textDim truncate max-w-[28%] text-right">
            {photo.sub_location || photo.city || photo.camera_model || ''}
          </span>
        </div>

        {/* Row 2: Star Rating & Exposure Specs */}
        <div className="flex items-center justify-between mt-0.5">
          {/* Subtle Star Rating (Clickable, instant DB update) */}
          <div
            className="flex items-center gap-0.5"
            onMouseLeave={() => setHoverRating(null)}
          >
            {[1, 2, 3, 4, 5].map((starVal) => {
              const active = (hoverRating !== null ? hoverRating >= starVal : currentStars >= starVal);
              return (
                <button
                  key={starVal}
                  type="button"
                  onClick={(e) => handleStarClick(e, starVal)}
                  onMouseEnter={() => setHoverRating(starVal)}
                  className="p-0.5 hover:scale-110 transition-transform"
                  title={`Set rating to ${starVal} star${starVal > 1 ? 's' : ''}`}
                >
                  <Star
                    className={`w-3 h-3 ${
                      active
                        ? 'text-studio-gold fill-studio-gold'
                        : 'text-studio-borderLight hover:text-studio-gold/60'
                    }`}
                  />
                </button>
              );
            })}
          </div>

          {/* Exposure specs + Add to Collection/Book button */}
          <div className="flex items-center gap-1.5">
            {exposureLine && (
              <span className="text-[9px] font-mono text-studio-textDim tracking-tight hidden xl:inline">
                {exposureLine}
              </span>
            )}
            <CollectionPopover
              photo={photo}
              collections={collections}
              onTogglePhotoInCollection={onTogglePhotoInCollection}
              onCreateCollectionWithPhoto={onCreateCollectionWithPhoto}
              onOpenCollectionsModal={onOpenCollectionsModal}
              compact={true}
            />
          </div>
        </div>

        {/* Row 3: Harvested (.lrcat / IPTC / XMP / VLM) Tag Pills */}
        {topCardTags.length > 0 && (
          <div className="flex flex-wrap items-center gap-1 pt-1 border-t border-studio-border/40">
            {topCardTags.map((tag, idx) => (
              <button
                type="button"
                key={idx}
                onClick={(e) => {
                  e.stopPropagation();
                  if (onTagClick) onTagClick(tag);
                }}
                className="px-1.5 py-0.5 bg-studio-bg border border-studio-border hover:border-studio-accent hover:text-studio-accent text-studio-textMuted text-[9px] font-mono rounded-sm truncate max-w-[110px] transition-colors cursor-pointer"
                title={`Filter archive by tag: ${tag}`}
              >
                {tag}
              </button>
            ))}
            {extraTagCount > 0 && (
              <span className="text-[9px] font-mono text-studio-textDim px-1">
                +{extraTagCount}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

