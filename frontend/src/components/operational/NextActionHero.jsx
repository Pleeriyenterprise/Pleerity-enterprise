import React from 'react';
import { AlertTriangle, ArrowRight, Lock, ShieldAlert } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
  getOperationalCognition,
  heroPrimaryFromCognition,
  progressionLabel,
  truthWarningsFromCognition,
} from '../../utils/operationalCognition';
import { coercePortalDisplayText } from '../../utils/capabilityRuntime';

/**
 * Server-driven next-action hero — ONE dominant action, ONE blocker, ONE progression/escalation lane.
 * Driven exclusively by operational_cognition envelope from API.
 */
export function NextActionHero({
  entity,
  onPrimaryClick,
  primaryBusy = false,
  primaryDisabled = false,
  primaryLocked = false,
  className = '',
}) {
  const cognition = getOperationalCognition(entity);
  const primary = heroPrimaryFromCognition(cognition);
  if (!cognition || !primary) return null;

  const blocker = (cognition.blockers || [])[0];
  const escalation = cognition.escalation_state || {};
  const degraded = cognition.degraded_state || {};
  const stale = cognition.stale_state || {};
  const progression = coercePortalDisplayText(progressionLabel(cognition), '');
  const truthWarnings = truthWarningsFromCognition(cognition);
  const warning = truthWarnings[0] || (cognition.warnings || [])[0];
  const primaryLabel = coercePortalDisplayText(primary.label, 'Continue');
  const primaryHint = coercePortalDisplayText(primary.hint, '');

  return (
    <Card
      className={`mb-6 border-teal-200 bg-gradient-to-r from-teal-50/90 to-white shadow-sm ${className}`}
      data-testid="next-action-hero"
    >
      <CardContent className="p-5 space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1 min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Next action</p>
            <p className="text-lg font-semibold text-midnight-blue">{primaryLabel}</p>
            {primaryHint ? <p className="text-sm text-gray-600">{primaryHint}</p> : null}
            {cognition.user_safe_summary ? (
              <p className="text-xs text-gray-500">{coercePortalDisplayText(cognition.user_safe_summary)}</p>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2 shrink-0">
            {escalation.active && escalation.label ? (
              <Badge variant="destructive" className="text-xs">
                {escalation.label}
              </Badge>
            ) : null}
            {degraded.active ? (
              <Badge variant="outline" className="text-xs border-amber-400 text-amber-800 bg-amber-50">
                Degraded data
              </Badge>
            ) : null}
            {stale.active ? (
              <Badge variant="outline" className="text-xs border-slate-400 text-slate-700">
                Stale
              </Badge>
            ) : null}
          </div>
        </div>

        {progression ? (
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-800">Progression: </span>
            {progression}
          </p>
        ) : null}

        {blocker ? (
          <div className="flex gap-2 text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-md p-3">
            <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
            <div>
              <p className="font-medium">Blocker</p>
              <p>{coercePortalDisplayText(blocker.message)}</p>
              {blocker.truth_note ? (
                <p className="text-xs mt-1 text-amber-800">{coercePortalDisplayText(blocker.truth_note)}</p>
              ) : null}
            </div>
          </div>
        ) : null}

        {warning && !blocker ? (
          <div className="flex gap-2 text-sm text-slate-800 bg-slate-50 border border-slate-200 rounded-md p-3">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
            <p>{coercePortalDisplayText(warning.message)}</p>
          </div>
        ) : null}

        {degraded.active && degraded.disclosure ? (
          <p className="text-xs text-amber-800">{degraded.disclosure}</p>
        ) : null}

        {onPrimaryClick ? (
          primaryLocked ? (
            <Button
              type="button"
              variant="outline"
              className="border-slate-300 bg-white text-midnight-blue hover:bg-slate-50"
              onClick={onPrimaryClick}
              disabled={primaryBusy}
              data-testid="next-action-hero-primary-locked"
            >
              {primaryBusy ? 'Working…' : primaryLabel}
              <Lock className="w-4 h-4 ml-2 shrink-0" aria-hidden />
            </Button>
          ) : (
            <Button
              type="button"
              className="bg-electric-teal hover:bg-electric-teal/90"
              onClick={onPrimaryClick}
              disabled={primaryBusy || primaryDisabled}
              data-testid="next-action-hero-primary"
            >
              {primaryBusy ? 'Working…' : primaryLabel}
              <ArrowRight className="w-4 h-4 ml-2" aria-hidden />
            </Button>
          )
        ) : null}
      </CardContent>
    </Card>
  );
}

export default NextActionHero;
