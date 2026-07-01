import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '../ui/button';
import {
  buildScoreRecommendationDisplayUnits,
  groupPresentationTitle,
  prepareScoreRecommendationPresentation,
} from '../../utils/scoreRecommendationPresentation';

function toneClasses(tone, isAssurance) {
  if (isAssurance) return 'bg-gray-50 border border-gray-100';
  if (tone === 'high') return 'bg-red-50 border border-red-100';
  if (tone === 'medium') return 'bg-amber-50 border border-amber-100';
  return 'bg-gray-50 border border-gray-100';
}

function dotClasses(tone, isAssurance) {
  if (isAssurance) return 'bg-gray-400';
  if (tone === 'high') return 'bg-red-500';
  if (tone === 'medium') return 'bg-amber-500';
  return 'bg-gray-400';
}

export function ScoreRecommendationCard({
  presentation,
  onNavigate,
  testId,
  compact = false,
}) {
  const p = presentation;
  const navigate = onNavigate || (() => {});
  return (
    <div
      className={`flex flex-col sm:flex-row sm:items-start gap-3 p-3 rounded-lg ${toneClasses(p.priority.tone, p.isAssurance)}`}
      data-testid={testId}
      data-recommendation-identity={p.identityKey}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${dotClasses(p.priority.tone, p.isAssurance)}`} />
        <div className="flex-1 min-w-0 space-y-1">
          <p className={`font-medium text-gray-800 ${compact ? 'text-sm' : 'text-sm'}`}>{p.title}</p>
          <p className="text-xs font-semibold text-midnight-blue" data-testid={testId ? `${testId}-property` : undefined}>
            {p.propertyName || 'Property not specified'}
          </p>
          <p className="text-xs text-gray-600">
            <span className="font-medium">{p.requirementName}</span>
            {p.jurisdiction ? <span className="text-gray-500"> · {p.jurisdiction}</span> : null}
          </p>
          <p className="text-xs text-gray-500">{p.operationalReason}</p>
          <p className="text-xs text-gray-500">{p.expectedOutcome}</p>
          <p className="text-xs text-gray-400">{p.priority.label}</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 shrink-0">
        {p.propertyId ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={(e) => {
              e.stopPropagation();
              navigate(p.propertyCtaPath);
            }}
            data-testid={testId ? `${testId}-view-property` : undefined}
          >
            View property
          </Button>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          className="shrink-0"
          disabled={!p.hasPrimaryCta}
          onClick={(e) => {
            e.stopPropagation();
            if (p.hasPrimaryCta) navigate(p.primaryCtaPath);
          }}
          data-testid={testId ? `${testId}-primary-cta` : undefined}
        >
          {p.primaryCtaLabel}
        </Button>
      </div>
    </div>
  );
}

function ScoreRecommendationGroup({
  items,
  presentationOptions,
  onNavigate,
  testId,
}) {
  const [expanded, setExpanded] = useState(false);
  const presentations = items.map((rec) =>
    prepareScoreRecommendationPresentation(rec, presentationOptions),
  );
  const themeTitle = groupPresentationTitle(items);
  const count = items.length;
  return (
    <div className="rounded-lg border border-amber-100 bg-amber-50/60 p-3 space-y-2" data-testid={testId}>
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-midnight-blue">{themeTitle}</p>
          <p className="text-xs text-gray-600">{count} properties require attention</p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-xs shrink-0"
          onClick={() => setExpanded((v) => !v)}
          data-testid={testId ? `${testId}-toggle` : undefined}
        >
          {expanded ? (
            <>
              Collapse <ChevronUp className="w-3 h-3 ml-1 inline" />
            </>
          ) : (
            <>
              Review all <ChevronDown className="w-3 h-3 ml-1 inline" />
            </>
          )}
        </Button>
      </div>
      {expanded ? (
        <div className="space-y-2 pt-1">
          {presentations.map((p, idx) => (
            <ScoreRecommendationCard
              key={p.identityKey || idx}
              presentation={p}
              onNavigate={onNavigate}
              testId={testId ? `${testId}-item-${idx}` : undefined}
              compact
            />
          ))}
        </div>
      ) : (
        <ul className="text-xs text-gray-700 space-y-0.5 pl-1">
          {presentations.map((p) => (
            <li key={p.identityKey}>• {p.propertyName}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Renders backend-ordered recommendations with optional conditional grouping (4+ same requirement).
 */
export default function ScoreRecommendationList({
  recommendations = [],
  requirementsList = [],
  propertyLookup,
  groupThreshold,
  defaultPropertyId = null,
  onNavigate,
  testIdPrefix = 'score-recommendation',
  presentationOptions = {},
}) {
  const navigate = useNavigate();
  const go = onNavigate || ((path) => navigate(path));
  const lookup = propertyLookup || new Map();
  const prepOptions = {
    requirementsList,
    propertyLookup: lookup,
    defaultPropertyId,
    ...presentationOptions,
  };
  const units = buildScoreRecommendationDisplayUnits(recommendations, { groupThreshold });

  return (
    <div className="space-y-3">
      {units.map((unit, unitIdx) => {
        if (unit.type === 'group') {
          return (
            <ScoreRecommendationGroup
              key={`group-${unit.groupingKey}-${unit.firstIndex}`}
              items={unit.items}
              presentationOptions={prepOptions}
              onNavigate={go}
              testId={`${testIdPrefix}-group-${unitIdx}`}
            />
          );
        }
        const p = prepareScoreRecommendationPresentation(unit.rec, prepOptions);
        return (
          <ScoreRecommendationCard
            key={p.identityKey || `rec-${unit.index}`}
            presentation={p}
            onNavigate={go}
            testId={`${testIdPrefix}-${unitIdx}`}
          />
        );
      })}
    </div>
  );
}
