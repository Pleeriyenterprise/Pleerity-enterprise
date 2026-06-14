import { useEffect, useState } from 'react';

/** Tailwind `sm` breakpoint — viewports at or below this width are treated as mobile. */
export const MOBILE_VIEWPORT_MAX_WIDTH_PX = 639;

export const MOBILE_VIEWPORT_MEDIA_QUERY = `(max-width: ${MOBILE_VIEWPORT_MAX_WIDTH_PX}px)`;

/**
 * @param {boolean} [matchesMobile]
 * @returns {boolean} Whether the NA governance disclosure should start expanded.
 */
export function resolveNaGovernanceDisclosureDefaultOpen(matchesMobile) {
  return !matchesMobile;
}

function readMatchesMobile() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY).matches;
}

/**
 * Tracks whether the viewport is at or below the mobile breakpoint (639px).
 */
export function useMobileViewport() {
  const [isMobile, setIsMobile] = useState(readMatchesMobile);

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_VIEWPORT_MEDIA_QUERY);
    const sync = () => setIsMobile(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  return isMobile;
}
