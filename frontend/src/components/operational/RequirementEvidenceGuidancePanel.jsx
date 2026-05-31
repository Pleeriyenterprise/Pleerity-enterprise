import React, { useMemo } from 'react';
import { ChevronDown } from 'lucide-react';
import NextActionHero from './NextActionHero';
import { Badge } from '../ui/badge';
import {
  getOperationalCognition,
  getRequirementGuidance,
  progressionStepsFromCognition,
} from '../../utils/operationalCognition';

function StepStatusBadge({ status }) {
  const tone =
    status === 'complete'
      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
      : status === 'current'
        ? 'bg-teal-50 text-teal-900 border-teal-200'
        : status === 'blocked'
          ? 'bg-amber-50 text-amber-900 border-amber-200'
          : 'bg-slate-50 text-slate-600 border-slate-200';
  return (
    <Badge variant="outline" className={`text-[10px] uppercase tracking-wide ${tone}`}>
      {status}
    </Badge>
  );
}

/**
 * Server-driven evidence modal guidance — dominant next action, progression, deferred truth copy.
 */
export function RequirementEvidenceGuidancePanel({
  cognitionEntity,
  onPrimaryClick,
  primaryDisabled = false,
  truthLines = [],
  componentGuidanceLines = [],
  className = '',
}) {
  const cognition = getOperationalCognition(cognitionEntity);
  const guidance = getRequirementGuidance(cognitionEntity);
  const steps = progressionStepsFromCognition(cognitionEntity);

  const remaining = useMemo(() => (guidance?.remaining_steps || []).filter(Boolean), [guidance]);
  const componentLines = useMemo(() => {
    const explicit = Array.isArray(componentGuidanceLines) ? componentGuidanceLines.filter(Boolean) : [];
    if (explicit.length > 0) return explicit;
    return Array.isArray(guidance?.missing_actions) ? guidance.missing_actions.filter(Boolean) : [];
  }, [componentGuidanceLines, guidance]);

  if (!cognition && !guidance) return null;

  return (
    <div className={`space-y-3 ${className}`} data-testid="requirement-evidence-guidance-panel">
      <NextActionHero
        entity={cognitionEntity}
        onPrimaryClick={onPrimaryClick}
        primaryDisabled={primaryDisabled}
        className="mb-0"
      />

      {componentLines.length > 0 ? (
        <div
          className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2.5 space-y-1"
          data-testid="component-guidance-lines"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">Still required</p>
          <ul className="text-sm text-amber-950 space-y-1 list-disc list-inside">
            {componentLines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {steps.length > 0 ? (
        <div
          className="rounded-lg border border-slate-200 bg-white px-3 py-2.5 space-y-2"
          data-testid="requirement-progression-steps"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Progression</p>
          <ol className="space-y-1.5">
            {steps.map((step) => (
              <li key={step.id} className="flex items-center justify-between gap-2 text-sm">
                <span className={step.status === 'current' ? 'font-medium text-midnight-blue' : 'text-gray-700'}>
                  {step.label}
                </span>
                <StepStatusBadge status={step.status} />
              </li>
            ))}
          </ol>
          {remaining.length > 0 ? (
            <p className="text-xs text-gray-500">
              Remaining: {remaining.join(' → ')}
            </p>
          ) : null}
        </div>
      ) : null}

      {(guidance?.uploaded_not_submitted || guidance?.submitted_not_verified) && (
        <div className="flex flex-wrap gap-2" data-testid="requirement-truth-flags">
          {guidance.uploaded_not_submitted ? (
            <Badge variant="outline" className="text-xs border-amber-300 text-amber-900 bg-amber-50">
              Uploaded ≠ submitted
            </Badge>
          ) : null}
          {guidance.submitted_not_verified ? (
            <Badge variant="outline" className="text-xs border-slate-300 text-slate-800 bg-slate-50">
              Submitted ≠ verified
            </Badge>
          ) : null}
        </div>
      )}

      {truthLines.length > 0 ? (
        <details
          className="rounded-lg border border-slate-200 bg-slate-50/80 px-3 py-2 group"
          data-testid="supporting-upload-truth-banner"
        >
          <summary className="text-xs font-semibold text-midnight-blue cursor-pointer list-none flex items-center justify-between gap-2">
            Supporting files vs authoritative submission
            <ChevronDown className="w-4 h-4 text-slate-500 transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <div className="mt-2 space-y-1.5">
            {truthLines.map((line) => (
              <p key={line} className="text-xs text-slate-700">
                {line}
              </p>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

export default RequirementEvidenceGuidancePanel;
