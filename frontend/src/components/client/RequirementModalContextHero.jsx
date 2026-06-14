import React from 'react';
import { AlertTriangle, ArrowRight } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';

/**
 * Context-aware hero for RequirementIntelligenceModal when submission/evidence is already on file.
 * Replaces server-driven NextActionHero to avoid stale pre-submission CTAs.
 */
export default function RequirementModalContextHero({
  headline,
  subline,
  primaryLabel,
  warningMessage,
  onPrimaryClick,
  primaryDisabled = false,
}) {
  if (!headline) return null;

  return (
    <Card
      className="mb-6 border-teal-200 bg-gradient-to-r from-teal-50/90 to-white shadow-sm"
      data-testid="requirement-modal-context-hero"
    >
      <CardContent className="p-5 space-y-4">
        <div className="space-y-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Current status</p>
          <p className="text-lg font-semibold text-midnight-blue" data-testid="requirement-modal-context-hero-headline">
            {headline}
          </p>
          {subline ? (
            <p className="text-sm text-gray-600" data-testid="requirement-modal-context-hero-subline">
              {subline}
            </p>
          ) : null}
        </div>

        {warningMessage ? (
          <div className="flex gap-2 text-sm text-slate-800 bg-slate-50 border border-slate-200 rounded-md p-3">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" aria-hidden />
            <p data-testid="requirement-modal-context-hero-warning">{warningMessage}</p>
          </div>
        ) : null}

        {onPrimaryClick && primaryLabel ? (
          <Button
            type="button"
            className="hidden sm:inline-flex bg-electric-teal hover:bg-electric-teal/90"
            onClick={onPrimaryClick}
            disabled={primaryDisabled}
            data-testid="requirement-modal-context-hero-primary"
          >
            {primaryLabel}
            <ArrowRight className="w-4 h-4 ml-2" aria-hidden />
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
