import React from 'react';
import { ArrowRight, Building2 } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import NextActionHero from '../operational/NextActionHero';
import {
  getOperationalCognition,
  heroPrimaryFromCognition,
  progressionLabel,
  getRequirementGuidance,
} from '../../utils/operationalCognition';
import { coercePortalDisplayText } from '../../utils/capabilityRuntime';
import { todayRequirementWhyItMattersLine } from '../../utils/todayRequirementWhyItMatters';
import { todayTaskOperationalGuidance } from '../../utils/todayTaskOperationalGuidance';
import { inboxTitleForDisplay } from '../../domain/presentDomain';

/**
 * Dominant execution card for Today — uses server operational_cognition when present,
 * otherwise take_action primary (no invented actions).
 */
export default function TodayExecutionHero({ entity, task, onPrimaryClick, primaryBusy = false }) {
  if (!entity && !task) return null;

  const cognition = getOperationalCognition(entity);
  const hasHeroCognition = cognition && heroPrimaryFromCognition(cognition);

  if (hasHeroCognition) {
    return (
      <div data-testid="today-execution-hero">
        <NextActionHero
          entity={entity}
          onPrimaryClick={onPrimaryClick}
          primaryBusy={primaryBusy}
          className="border-teal-300 shadow-md"
        />
        {entity?.property_display_name ? (
          <p className="text-xs text-gray-600 -mt-4 mb-6 flex items-center gap-1.5 px-1">
            <Building2 className="w-3.5 h-3.5 shrink-0" aria-hidden />
            {entity.property_display_name}
          </p>
        ) : null}
      </div>
    );
  }

  const ta = entity?.take_action?.primary || task?.metadata?.take_action?.primary;
  const label =
    String(ta?.label || task?.primary_action_label || '').trim() || 'Review next item';
  const why =
    todayRequirementWhyItMattersLine(task) ||
    todayTaskOperationalGuidance(task)?.whyMatters ||
    task?.why_matters ||
    null;
  const outcome =
    progressionLabel(cognition) ||
    getRequirementGuidance(entity)?.recommended_next_step ||
    todayTaskOperationalGuidance(task)?.whatToDo ||
    task?.recommended_action ||
    null;
  const title = coercePortalDisplayText(inboxTitleForDisplay(task), 'Task');
  const whyText = coercePortalDisplayText(why, '');
  const outcomeText = coercePortalDisplayText(outcome, '');

  return (
    <Card
      className="mb-6 border-teal-300 bg-gradient-to-br from-teal-50/95 via-white to-white shadow-md"
      data-testid="today-execution-hero"
    >
      <CardContent className="p-5 space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Do this next</p>
          <h2 className="text-xl font-bold text-midnight-blue mt-1 leading-snug">{title}</h2>
          {entity?.property_display_name ? (
            <p className="text-sm text-gray-600 mt-1 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 shrink-0" aria-hidden />
              {entity.property_display_name}
            </p>
          ) : null}
        </div>
        {whyText ? (
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-900">Why it matters: </span>
            {whyText}
          </p>
        ) : null}
        {outcomeText ? (
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-900">Expected outcome: </span>
            {outcomeText}
          </p>
        ) : null}
        {onPrimaryClick ? (
          <Button
            type="button"
            className="w-full sm:w-auto min-h-12 bg-electric-teal hover:bg-electric-teal/90 text-midnight-blue font-semibold"
            onClick={onPrimaryClick}
            disabled={primaryBusy}
            data-testid="today-execution-hero-primary"
          >
            {primaryBusy ? 'Working…' : label}
            <ArrowRight className="w-4 h-4 ml-2" aria-hidden />
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
