import React, { useState } from 'react';

const BASE = '/images/marketing';

/**
 * Marketing screenshot image: PNG first (single source of truth), SVG fallback if PNG missing.
 * Uses absolute paths only. Dev-only: logs console warning on first load error.
 */
function MarketingImage({
  name,
  alt,
  width,
  height,
  className = '',
  fetchPriority,
  loading,
  placeholderText = 'Image unavailable',
}) {
  const [useSvg, setUseSvg] = useState(false);
  const [showPlaceholder, setShowPlaceholder] = useState(false);

  const pngSrc = `${BASE}/${name}.png`;
  const svgSrc = `${BASE}/${name}.svg`;
  const src = showPlaceholder ? '' : (useSvg ? svgSrc : pngSrc);

  const handleError = () => {
    if (!useSvg) {
      if (process.env.NODE_ENV === 'development') {
        console.warn(`[MarketingImage] PNG failed to load: ${pngSrc}, falling back to SVG`);
      }
      setUseSvg(true);
    } else {
      if (process.env.NODE_ENV === 'development') {
        console.warn(`[MarketingImage] SVG also failed: ${svgSrc}`);
      }
      setShowPlaceholder(true);
    }
  };

  if (showPlaceholder) {
    return (
      <div className="w-full min-h-[200px] flex items-center justify-center bg-gray-100 text-gray-500 text-sm rounded-lg">
        {placeholderText}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      className={className}
      fetchPriority={fetchPriority}
      loading={loading}
      onError={handleError}
    />
  );
}

export default MarketingImage;
