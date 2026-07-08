import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Info, Lock, Eye } from 'lucide-react';
import { useLifecycleRuntime, usePortalMode } from '../../contexts/LifecycleRuntimeContext';
import { LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE } from '../../contexts/LifecycleRuntimeContext';
import { coercePortalDisplayText, formatApiErrorDetail, normalizeCustomerExperience } from '../../utils/capabilityRuntime';
import { isPathLifecycleReadOnly } from '../../utils/portalNavigationPolicy';
import { useLocation } from 'react-router-dom';

const MODE_STYLES = {
  GRACE: 'border-amber-300 bg-amber-50 text-amber-950',
  PAYMENT_REQUIRED: 'border-blue-300 bg-blue-50 text-blue-950',
  BILLING_RECOVERY: 'border-slate-400 bg-slate-50 text-slate-900',
  SUSPENDED: 'border-red-300 bg-red-50 text-red-950',
  ARCHIVED: 'border-gray-400 bg-gray-100 text-gray-900',
  ACCOUNT_DELETED: 'border-gray-500 bg-gray-200 text-gray-900',
  READ_ONLY: 'border-teal-300 bg-teal-50 text-teal-950',
  FULL_ACCESS: 'border-gray-200 bg-white text-gray-800',
};

function CtaButton({ cta, variant = 'primary' }) {
  if (!cta?.label || !cta?.route) return null;
  const className =
    variant === 'primary'
      ? 'inline-flex items-center justify-center min-h-10 px-4 py-2 rounded-md text-sm font-semibold bg-midnight-blue text-white hover:bg-midnight-blue/90'
      : 'inline-flex items-center justify-center min-h-10 px-4 py-2 rounded-md text-sm font-medium border border-gray-300 text-midnight-blue bg-white hover:bg-gray-50';
  return (
    <Link to={cta.route} className={className}>
      {cta.label}
    </Link>
  );
}

/** Portal-wide lifecycle presentation shell (no permission enforcement). */
export default function LifecycleShell() {
  const { portalMode, customerExperience } = usePortalMode();
  const { loading, error, navigationPolicy, warnings, runtimeAvailable } = useLifecycleRuntime();
  const location = useLocation();
  const cx = normalizeCustomerExperience(customerExperience);
  const heading = cx.heading.trim();
  const showBanner = Boolean(heading) || portalMode !== 'FULL_ACCESS' || !runtimeAvailable;
  const style = MODE_STYLES[portalMode] || MODE_STYLES.FULL_ACCESS;

  if (loading) return null;

  if (!showBanner && !error) return null;

  const readOnlyPath = isPathLifecycleReadOnly(location.pathname, navigationPolicy);

  return (
    <div className="mb-5 space-y-3" data-testid="lifecycle-shell">
      {!runtimeAvailable && error && (
        <div
          className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 flex gap-2"
          role="status"
          data-testid="lifecycle-runtime-fallback"
        >
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
          <span>{formatApiErrorDetail(error, LIFECYCLE_RUNTIME_UNAVAILABLE_MESSAGE)}</span>
        </div>
      )}

      {showBanner && (
        <section
          className={`rounded-lg border px-4 py-4 sm:px-5 sm:py-5 ${style}`}
          aria-label="Account status"
          data-testid={`lifecycle-shell-${portalMode}`}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2 min-w-0">
              {portalMode === 'READ_ONLY' && (
                <span className="inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-teal-800">
                  <Eye className="w-3.5 h-3.5" aria-hidden />
                  View only
                </span>
              )}
              {heading ? <h2 className="text-base sm:text-lg font-semibold">{heading}</h2> : null}
              {cx.current_state_label ? (
                <p className="text-sm font-medium opacity-90">{cx.current_state_label}</p>
              ) : null}
              {cx.explanation ? <p className="text-sm leading-relaxed">{cx.explanation}</p> : null}
              {cx.reason ? (
                <p className="text-xs opacity-80">
                  <Info className="w-3.5 h-3.5 inline mr-1 -mt-0.5" aria-hidden />
                  {cx.reason}
                </p>
              ) : null}
              {cx.recovery_guidance ? (
                <p className="text-sm">{cx.recovery_guidance}</p>
              ) : null}
              {cx.support_guidance ? (
                <p className="text-xs opacity-80">{cx.support_guidance}</p>
              ) : null}
              {cx.expected_next_step ? (
                <p className="text-xs font-medium">{cx.expected_next_step}</p>
              ) : null}
              {warnings?.length > 0 && process.env.NODE_ENV !== 'production' && (
                <p className="text-xs font-mono opacity-60" data-testid="lifecycle-shell-warnings">
                  {warnings.join(' · ')}
                </p>
              )}
            </div>
            <div className="flex flex-col sm:flex-row gap-2 shrink-0">
              <CtaButton cta={cx.primary_cta} variant="primary" />
              <CtaButton cta={cx.secondary_cta} variant="secondary" />
            </div>
          </div>
        </section>
      )}

      {readOnlyPath && portalMode !== 'READ_ONLY' && (
        <p
          className="text-xs text-teal-800 bg-teal-50 border border-teal-200 rounded-md px-3 py-2 flex items-center gap-2"
          data-testid="lifecycle-read-only-route-hint"
        >
          <Lock className="w-3.5 h-3.5 shrink-0" aria-hidden />
          This section is presented as view-only for your account status. Saving changes may still be subject to your plan and permissions.
        </p>
      )}
    </div>
  );
}

/** Compact page-level portal mode indicator (presentation only). */
export function PortalModePageBanner() {
  const { portalMode, customerExperience } = usePortalMode();
  if (!portalMode || portalMode === 'FULL_ACCESS') return null;
  const label = customerExperience?.current_state_label || portalMode?.replace(/_/g, ' ') || 'Restricted';
  return (
    <p
      className="text-xs text-gray-600 mb-3 flex items-center gap-2"
      data-testid="portal-mode-page-banner"
    >
      <Info className="w-3.5 h-3.5 text-electric-teal shrink-0" aria-hidden />
      <span>
        Account presentation: <span className="font-medium text-gray-800">{label}</span>
      </span>
    </p>
  );
}
