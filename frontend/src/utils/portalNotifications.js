/**
 * Tiered portal notifications (Sonner-backed).
 *
 * Tiers:
 * - minor: small, bottom-right, short auto-dismiss (confirmations, nudges).
 * - important: larger, top-center, longer read time, close button (status updates).
 * - critical: persistent until dismissed, strong styling (blocked actions, hard failures).
 *
 * Prefer `notify.*` for explicit tiering. The default `toast` export keeps call sites working
 * with sensible defaults: success/warning → important; message/info → minor; error → important
 * unless `{ critical: true }` or `{ persist: true }`.
 */
import { toast as sonnerToast } from 'sonner';

const MINOR_BASE = {
  duration: 3800,
  position: 'bottom-right',
  closeButton: false,
  dismissible: true,
  className: 'notify-tier-minor max-w-[min(20rem,calc(100vw-2rem))] text-sm leading-snug shadow-md',
};

const IMPORTANT_BASE = {
  duration: 16000,
  position: 'top-center',
  closeButton: true,
  dismissible: true,
  className:
    'notify-tier-important w-full max-w-[min(36rem,calc(100vw-2rem))] text-base leading-snug p-4 shadow-lg',
  descriptionClassName: 'text-sm leading-relaxed opacity-95 mt-1.5 max-w-prose',
};

const CRITICAL_BASE = {
  duration: Infinity,
  position: 'top-center',
  closeButton: true,
  dismissible: true,
  className:
    'notify-tier-critical w-full max-w-[min(40rem,calc(100vw-2rem))] text-base leading-snug p-4 shadow-xl border-2 border-red-400/70 dark:border-red-600/80',
  descriptionClassName: 'text-sm leading-relaxed mt-1.5 max-w-prose font-normal',
};

/** Keys we handle ourselves and must not forward to Sonner. */
const INTERNAL_KEYS = new Set(['tier', 'critical', 'persist']);

function pickSonnerOpts(opts) {
  if (!opts || typeof opts !== 'object') return {};
  const out = { ...opts };
  for (const k of INTERNAL_KEYS) delete out[k];
  return out;
}

function mergeBase(base, opts) {
  const o = pickSonnerOpts(opts);
  const parts = [base.className, o.className].filter(Boolean);
  const descParts = [base.descriptionClassName, o.descriptionClassName].filter(Boolean);
  return {
    ...base,
    ...o,
    className: parts.join(' '),
    ...(descParts.length ? { descriptionClassName: descParts.join(' ') } : {}),
  };
}

function isLikelyMinorSuccessMessage(message) {
  const s = String(message || '').trim();
  if (!s || s.length > 36) return false;
  return /^(saved|copied|updated|done|ok|removed|deleted|sent|loaded|refreshed|dismissed)\.?$/i.test(s);
}

function callImportant(type, message, opts) {
  return sonnerToast[type](message, mergeBase(IMPORTANT_BASE, opts));
}

function callMinor(type, message, opts) {
  return sonnerToast[type](message, mergeBase(MINOR_BASE, opts));
}

function callCritical(type, message, opts) {
  return sonnerToast[type](message, mergeBase(CRITICAL_BASE, opts));
}

/** String promise results → tiered toast payloads (Sonner extended result shape). */
function promiseResultToToastPayload(val, isError) {
  if (typeof val !== 'string') return val;
  const base = isError ? CRITICAL_BASE : IMPORTANT_BASE;
  return { message: val, ...base };
}

function wrapPromiseDataFn(fn, isError) {
  if (typeof fn !== 'function') return fn;
  return (...args) => {
    const out = fn(...args);
    if (typeof out === 'string') return promiseResultToToastPayload(out, isError);
    return out;
  };
}

/** Explicit tier API (preferred for new code). */
export const notify = {
  minor: {
    success: (message, opts) => callMinor('success', message, opts),
    message: (message, opts) => callMinor('message', message, opts),
    info: (message, opts) => callMinor('info', message, opts),
    error: (message, opts) => callMinor('error', message, opts),
  },
  important: {
    success: (message, opts) => callImportant('success', message, opts),
    message: (message, opts) => callImportant('message', message, opts),
    info: (message, opts) => callImportant('info', message, opts),
    error: (message, opts) => callImportant('error', message, opts),
    warning: (message, opts) => callImportant('warning', message, opts),
  },
  critical: {
    error: (message, opts) => callCritical('error', message, opts),
    warning: (message, opts) => callCritical('warning', message, opts),
    message: (message, opts) => callCritical('message', message, opts),
  },
};

function shouldUseCriticalError(opts) {
  if (!opts || typeof opts !== 'object') return false;
  return !!(opts.critical || opts.persist || opts.tier === 'critical');
}

/**
 * Drop-in replacement for `import { toast } from 'sonner'`.
 * - success: important by default; pass `{ tier: 'minor' }` or rely on short “Saved”-style copy for minor.
 * - error: important unless `{ critical: true }`, `{ persist: true }`, or `{ tier: 'critical' }`.
 * - warning: always important (read carefully).
 * - message / info: minor (ambient feedback).
 */
function toastFn(message, opts) {
  return sonnerToast(message, mergeBase(MINOR_BASE, opts));
}

export const toast = Object.assign(toastFn, {
  success(message, opts) {
    if (opts?.tier === 'minor' || isLikelyMinorSuccessMessage(message)) {
      return callMinor('success', message, opts);
    }
    return callImportant('success', message, opts);
  },
  error(message, opts) {
    if (shouldUseCriticalError(opts)) {
      return callCritical('error', message, opts);
    }
    return callImportant('error', message, opts);
  },
  warning(message, opts) {
    if (shouldUseCriticalError(opts)) {
      return callCritical('warning', message, opts);
    }
    return callImportant('warning', message, opts);
  },
  info(message, opts) {
    if (opts?.tier === 'important') {
      return callImportant('info', message, opts);
    }
    return callMinor('info', message, opts);
  },
  message(message, opts) {
    if (opts?.tier === 'important') {
      return callImportant('message', message, opts);
    }
    return callMinor('message', message, opts);
  },
  loading(message, opts) {
    return sonnerToast.loading(message, {
      duration: Infinity,
      position: 'bottom-right',
      ...pickSonnerOpts(opts),
    });
  },
  /**
   * Promise toasts: string success → important; string error → critical (must read + dismiss).
   * Functions for success/error are wrapped so plain string returns pick up the same tiers; other returns pass through.
   */
  promise(promise, data) {
    if (!data || typeof data !== 'object') {
      return sonnerToast.promise(promise, data);
    }
    const next = { ...data };
    if (typeof next.success === 'string') {
      next.success = promiseResultToToastPayload(next.success, false);
    } else if (typeof next.success === 'function') {
      next.success = wrapPromiseDataFn(next.success, false);
    }
    if (typeof next.error === 'string') {
      next.error = promiseResultToToastPayload(next.error, true);
    } else if (typeof next.error === 'function') {
      next.error = wrapPromiseDataFn(next.error, true);
    }
    return sonnerToast.promise(promise, next);
  },
  dismiss: (...args) => sonnerToast.dismiss(...args),
  custom: (...args) => sonnerToast.custom(...args),
});

export const NOTIFY_TIERS = {
  MINOR: 'minor',
  IMPORTANT: 'important',
  CRITICAL: 'critical',
};
