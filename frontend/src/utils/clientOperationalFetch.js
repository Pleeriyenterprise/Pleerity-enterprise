/**
 * In-memory operational fetch cache: dedupe in-flight requests and stale-while-refresh.
 * Used for landlord portal list/summary endpoints — not for mutation or authority outcomes.
 */

const cache = new Map();
const inflight = new Map();

export const OPERATIONAL_CACHE_KEYS = {
  dashboard: 'client:dashboard',
  properties: 'client:properties',
  requirements: 'client:requirements',
  /** Full enrichment (take_action, cognition, registry copy) — Requirements workspace only. */
  requirementsOperational: 'client:requirements:operational',
  documents: 'client:documents',
  commandCenter: 'client:command-center',
  commandCenterPrimary: 'client:command-center:primary',
  commandCenterSecondary: 'client:command-center:secondary',
  complianceSummary: 'client:compliance-summary',
  todayItems: 'client:today-items',
};

const DEFAULT_STALE_MS = 45_000;

function runDeduped(key, fetcher) {
  if (inflight.has(key)) return inflight.get(key);
  const p = Promise.resolve()
    .then(() => fetcher())
    .finally(() => inflight.delete(key));
  inflight.set(key, p);
  return p;
}

/** @returns {unknown | null} */
export function peekOperationalCache(key) {
  return cache.get(key)?.data ?? null;
}

export function clearOperationalCache(key) {
  if (key) cache.delete(key);
  else cache.clear();
}

/**
 * @template T
 * @param {string} key
 * @param {() => Promise<T>} fetcher
 * @param {{ staleMs?: number, force?: boolean, onRefresh?: (data: T) => void }} [options]
 * @returns {Promise<{ data: T, fromCache: boolean, refreshing: boolean }>}
 */
export async function fetchOperational(key, fetcher, options = {}) {
  const { staleMs = DEFAULT_STALE_MS, force = false, onRefresh } = options;
  const now = Date.now();
  const hit = cache.get(key);

  if (!force && hit && now - hit.at < staleMs) {
    return { data: hit.data, fromCache: true, refreshing: false };
  }

  if (!force && hit?.data != null) {
    runDeduped(key, fetcher)
      .then((data) => {
        cache.set(key, { data, at: Date.now() });
        onRefresh?.(data);
      })
      .catch(() => {});
    return { data: hit.data, fromCache: true, refreshing: true };
  }

  const data = await runDeduped(key, fetcher);
  cache.set(key, { data, at: Date.now() });
  return { data, fromCache: false, refreshing: false };
}
