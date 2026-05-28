import React from 'react';
import { Badge } from '../ui/badge';
import { getListGuidance } from '../../utils/operationalCognition';

/**
 * Lightweight list-row operational guidance from the same envelope authority as detail surfaces.
 */
export function ListCognitionChip({ entity, className = '' }) {
  const guidance = getListGuidance(entity);
  if (!guidance?.recommended_action_label && !guidance?.escalation_badge && !guidance?.blocker_summary) {
    return null;
  }

  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`} data-testid="list-cognition-chip">
      {guidance.recommended_action_label ? (
        <Badge variant="secondary" className="text-[10px] font-medium bg-teal-50 text-teal-900 border-teal-200">
          {guidance.recommended_action_label}
        </Badge>
      ) : null}
      {guidance.escalation_badge ? (
        <Badge variant="destructive" className="text-[10px]">
          {guidance.escalation_badge}
        </Badge>
      ) : null}
      {guidance.degraded_warning ? (
        <Badge variant="outline" className="text-[10px] border-amber-400 text-amber-800">
          Degraded
        </Badge>
      ) : null}
      {guidance.stale_warning ? (
        <Badge variant="outline" className="text-[10px] text-slate-600">
          Stale
        </Badge>
      ) : null}
      {guidance.continuation_summary ? (
        <span className="text-[10px] text-gray-500 truncate max-w-[140px]" title={guidance.continuation_summary}>
          {guidance.continuation_summary}
        </span>
      ) : null}
      {guidance.blocker_summary ? (
        <span className="text-[10px] text-amber-800 truncate max-w-[160px]" title={guidance.blocker_summary}>
          {guidance.blocker_summary}
        </span>
      ) : null}
    </div>
  );
}

export default ListCognitionChip;
