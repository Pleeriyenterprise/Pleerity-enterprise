/**
 * Item-aware “Why it matters / What to do” copy for Today task expandable details.
 * Uses only unified inbox task fields (no new APIs). Prefer over generic placeholders
 * when the server does not supply richer `why_matters` / `recommended_action`.
 */

/**
 * @param {Record<string, unknown> | null | undefined} task
 * @returns {{ whyMatters: string, whatToDo: string } | null}
 */
export function todayTaskOperationalGuidance(task) {
  if (!task || typeof task !== 'object') return null;
  const meta = task.metadata && typeof task.metadata === 'object' ? task.metadata : {};
  const tags = Array.isArray(task.filter_tags) ? task.filter_tags : [];
  const src = String(task.source_type || '').toLowerCase();
  const actionType = String(
    meta.action_type || task.primary_action_type || task.action_type || '',
  ).toLowerCase();
  const woKind = String(meta.work_order_kind || '').toUpperCase();
  const hasSlaBreach = Boolean(meta.sla_breached_at || task.sla_breached_at);
  const slaNear = Boolean(meta.sla_breach_risk_at || task.sla_breach_risk_at);
  const urgency = String(task.urgency || task.urgency_level || meta.urgency || '').toLowerCase();
  const overdueDays = Number(task.overdue_days || meta.overdue_days || 0);

  const isComplianceRequirement =
    src === 'requirement' || tags.map((t) => String(t).toLowerCase()).includes('compliance');

  if (isComplianceRequirement) {
    if (
      actionType === 'missing_document' ||
      actionType === 'upload_evidence' ||
      String(task.primary_action_type || '').toLowerCase() === 'upload_evidence'
    ) {
      return {
        whyMatters:
          'The requirement cannot be treated as evidenced until a suitable document is uploaded and reviewed.',
        whatToDo:
          'Open the requirement or Documents, upload the correct certificate or report, then confirm any extracted dates if prompted.',
      };
    }
    if (actionType === 'overdue_compliance' || urgency === 'overdue' || overdueDays > 0) {
      return {
        whyMatters:
          'Overdue obligations continue to affect your portfolio view until the requirement is satisfied or evidence is accepted.',
        whatToDo:
          'Open the requirement, complete the renewal or inspection, upload evidence if needed, and clear any pending confirmations.',
      };
    }
    return {
      whyMatters: 'Keeping this requirement current preserves an accurate compliance picture for the property.',
      whatToDo: 'Use the main action on this card, then open Requirements if you need the full obligation record.',
    };
  }

  if (src === 'work_order') {
    const complianceWO = woKind === 'COMPLIANCE' || tags.map((t) => String(t).toLowerCase()).includes('compliance_job');
    const slaTail = hasSlaBreach
      ? ' The job has passed its target response time and needs follow-up.'
      : slaNear || urgency === 'due_soon'
        ? ' The response window is tight—act before the SLA target passes.'
        : '';
    if (complianceWO) {
      return {
        whyMatters: `This job relates to a compliance requirement. Completing the work order alone may not close the obligation until evidence is uploaded and verified.${slaTail}`,
        whatToDo:
          'Open the job, confirm schedule or contractor steps, then upload or link the required certificate when work is complete.',
      };
    }
    const maintSla = hasSlaBreach
      ? ' Missed response targets affect tenant service, safety follow-up, and operational records.'
      : '';
    return {
      whyMatters: `This is an operational repair or maintenance job.${maintSla}`,
      whatToDo: 'Review the job, update the schedule or contractor, and close it only when the work is complete.',
    };
  }

  if (src === 'risk_signal') {
    return {
      whyMatters:
        'Predictive risk signals highlight patterns for triage; they do not replace statutory obligations by themselves.',
      whatToDo:
        'Open the risk signal, review the context, then continue in Requirements or Jobs where a concrete obligation applies.',
    };
  }

  if (src === 'issue') {
    return {
      whyMatters: 'Unresolved maintenance issues can affect tenants quickly and should be tracked to closure.',
      whatToDo: 'Open the issue, assign or create corrective work, and update status when resolved.',
    };
  }

  if (src === 'approval' || src === 'review_approval') {
    return {
      whyMatters: 'Pending approvals can block contractors, spend, or compliance-linked changes.',
      whatToDo: 'Open Approvals, review the request, and approve or decline with a short note.',
    };
  }

  return null;
}
