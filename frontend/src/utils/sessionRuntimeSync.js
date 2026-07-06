/**
 * Multi-tab session runtime synchronization (ILP-5).
 */
const CHANNEL_NAME = 'pleerity-session-runtime';
const INVALIDATION_KEY = 'pleerity_runtime_invalidation';
const AUTH_SYNC_KEY = 'pleerity_auth_sync';

export const SESSION_RUNTIME_SYNC_EVENT = 'pleerity:session-runtime-sync';

function safeParse(json) {
  try {
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function broadcastRuntimeInvalidation(meta = {}) {
  if (typeof window === 'undefined') return;
  const payload = { at: Date.now(), ...meta };
  try {
    localStorage.setItem(INVALIDATION_KEY, JSON.stringify(payload));
    localStorage.removeItem(INVALIDATION_KEY);
  } catch {
    /* ignore quota */
  }
  try {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage({ type: 'runtime_invalidate', ...payload });
    channel.close();
  } catch {
    /* BroadcastChannel unavailable */
  }
  window.dispatchEvent(new CustomEvent(SESSION_RUNTIME_SYNC_EVENT, { detail: payload }));
}

export function broadcastAuthSync(meta = {}) {
  if (typeof window === 'undefined') return;
  const payload = { at: Date.now(), ...meta };
  try {
    localStorage.setItem(AUTH_SYNC_KEY, JSON.stringify(payload));
    localStorage.removeItem(AUTH_SYNC_KEY);
  } catch {
    /* ignore */
  }
  try {
    const channel = new BroadcastChannel(CHANNEL_NAME);
    channel.postMessage({ type: 'auth_sync', ...payload });
    channel.close();
  } catch {
    /* ignore */
  }
}

export function subscribeSessionRuntimeSync(onInvalidate) {
  if (typeof window === 'undefined') return () => {};

  let channel;
  try {
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (event) => {
      const data = event?.data;
      if (!data) return;
      if (data.type === 'runtime_invalidate' || data.type === 'auth_sync') {
        onInvalidate(data);
      }
    };
  } catch {
    channel = null;
  }

  const onStorage = (event) => {
    if (event.key === INVALIDATION_KEY && event.newValue) {
      const parsed = safeParse(event.newValue);
      if (parsed) onInvalidate({ type: 'runtime_invalidate', ...parsed });
    }
    if (event.key === AUTH_SYNC_KEY && event.newValue) {
      const parsed = safeParse(event.newValue);
      if (parsed) onInvalidate({ type: 'auth_sync', ...parsed });
    }
  };

  const onCustom = (event) => {
    if (event?.detail) onInvalidate({ type: 'runtime_invalidate', ...event.detail });
  };

  window.addEventListener('storage', onStorage);
  window.addEventListener(SESSION_RUNTIME_SYNC_EVENT, onCustom);

  return () => {
    if (channel) channel.close();
    window.removeEventListener('storage', onStorage);
    window.removeEventListener(SESSION_RUNTIME_SYNC_EVENT, onCustom);
  };
}

export function isDocumentOnline() {
  return typeof navigator === 'undefined' ? true : navigator.onLine !== false;
}
