/**
 * Client-facing asset / equipment identifiers: keep lists scannable; full value available on demand.
 */

const DEFAULT_HEAD = 8;

/**
 * @param {string|null|undefined} id
 * @param {{ head?: number }} [opts]
 * @returns {{ short: string, full: string, isTruncated: boolean }}
 */
export function assetIdParts(id, opts = {}) {
  const head = opts.head ?? DEFAULT_HEAD;
  if (id == null || id === '') {
    return { short: '—', full: '', isTruncated: false };
  }
  const full = String(id).trim();
  if (!full) {
    return { short: '—', full: '', isTruncated: false };
  }
  if (full.length <= head) {
    return { short: full, full, isTruncated: false };
  }
  return { short: `${full.slice(0, head)}…`, full, isTruncated: true };
}
