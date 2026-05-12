import React from 'react';
import { Layers } from 'lucide-react';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';

/**
 * Governed upgrade / tier discoverability — presentation only.
 * Use after hasFeature / API truth checks. Anti-fatigue: one primary card per viewport where possible;
 * use DiscoverabilityHint in dense or tabbed flows.
 */

export function ScaleAutomationCallout({ headline, body, className = '' }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-slate-200 bg-slate-50/90 px-3 py-2.5 text-sm text-slate-700',
        className,
      )}
      data-testid="scale-automation-callout"
    >
      <p className="font-medium text-midnight-blue">{headline}</p>
      {body ? <p className="mt-1 text-xs text-slate-600 leading-relaxed">{body}</p> : null}
    </div>
  );
}

/** Governance doc alias — same as ScaleAutomationCallout. */
export function OperationalScaleCallout(props) {
  return <ScaleAutomationCallout {...props} />;
}

/**
 * Passive / contextual discoverability — low vertical weight, one text CTA max.
 * Prefer in property tabs, notification settings, or under operational blocks.
 */
export function DiscoverabilityHint({
  title,
  body,
  ctaLabel = 'View plans in Billing',
  onCta,
  className = '',
  dataTestId = 'discoverability-hint',
}) {
  return (
    <div
      className={cn('rounded-lg border border-slate-200 bg-white px-3 py-3 text-sm shadow-sm', className)}
      data-testid={dataTestId}
    >
      <p className="font-medium leading-snug text-midnight-blue">{title}</p>
      {body ? <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{body}</p> : null}
      {typeof onCta === 'function' && ctaLabel ? (
        <button
          type="button"
          className="mt-2 text-left text-sm font-semibold text-electric-teal underline decoration-electric-teal/30 underline-offset-2 hover:text-electric-teal/90"
          onClick={onCta}
        >
          {ctaLabel}
        </button>
      ) : null}
    </div>
  );
}

/**
 * Expansion / maturity framing — informational bullets, optional single CTA.
 * No “unlock” language; no lock icons; no warning colours.
 */
export function ExpansionCapabilityCard({
  title,
  description,
  children,
  ctaLabel,
  onCta,
  className = '',
  dataTestId = 'expansion-capability-card',
}) {
  return (
    <div
      className={cn('rounded-xl border border-slate-200 bg-slate-50/50 p-4 text-sm text-slate-700', className)}
      data-testid={dataTestId}
    >
      <p className="font-semibold text-midnight-blue">{title}</p>
      {description ? <p className="mt-1 text-xs leading-relaxed text-slate-600">{description}</p> : null}
      {children ? <div className="mt-3 space-y-2">{children}</div> : null}
      {typeof onCta === 'function' && ctaLabel ? (
        <Button type="button" variant="outline" size="sm" className="mt-3 border-slate-200 text-midnight-blue" onClick={onCta}>
          {ctaLabel}
        </Button>
      ) : null}
    </div>
  );
}

/** Optional grouped expansion panel — collapsible to save vertical space on mobile. */
export function GrowthCapabilityPanel({ title, children, className = '' }) {
  return (
    <details className={cn('rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm', className)} data-testid="growth-capability-panel">
      <summary className="cursor-pointer font-medium text-midnight-blue">{title}</summary>
      <div className="mt-2 border-t border-slate-100 pt-2 text-slate-600">{children}</div>
    </details>
  );
}

export function GovernedUpgradeDiscoverCard({
  title,
  children,
  primaryCtaLabel = 'View plans in Billing',
  onPrimaryCta,
  secondaryAction = null,
  className = '',
  'data-testid': dataTestId = 'governed-upgrade-discover-card',
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-5 shadow-sm',
        className,
      )}
      data-testid={dataTestId}
    >
      <div className="flex gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-100 bg-white"
          aria-hidden
        >
          <Layers className="h-5 w-5 text-midnight-blue/70" />
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <h3 className="text-sm font-semibold leading-snug text-midnight-blue">{title}</h3>
          {children}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Button
              type="button"
              size="sm"
              className="bg-electric-teal text-white hover:bg-electric-teal/90"
              onClick={onPrimaryCta}
            >
              {primaryCtaLabel}
            </Button>
            {secondaryAction ? (
              <Button type="button" variant="ghost" size="sm" className="text-midnight-blue" onClick={secondaryAction.onClick}>
                {secondaryAction.label}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
