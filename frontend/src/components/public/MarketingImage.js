import React, { useState } from 'react';

const BASE = '/images/marketing';

/**
 * Marketing screenshot image: production PNG only (absolute paths).
 * onError → neutral fallback (no external/SVG). Prevents layout shift via width/height.
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
  const [showPlaceholder, setShowPlaceholder] = useState(false);
  const pngSrc = `${BASE}/${name}.png`;

  const handleError = () => {
    if (process.env.NODE_ENV === 'development') {
      console.warn(`[MarketingImage] Failed to load: ${pngSrc}`);
    }
    setShowPlaceholder(true);
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
      src={pngSrc}
      alt={alt}
      width={width}
      height={height}
      className={className}
      fetchPriority={fetchPriority}
      loading={loading}
      decoding="async"
      onError={handleError}
    />
  );
}

export default MarketingImage;
