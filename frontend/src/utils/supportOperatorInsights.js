/**
 * Deterministic operator hints from existing support conversation / ticket fields.
 * Does not infer facts not present in payloads.
 */

function lastMeta(messages, predicate) {
  const list = Array.isArray(messages) ? messages : [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const m = list[i];
    const meta = m?.metadata;
    if (meta && predicate(meta)) return meta;
  }
  return null;
}

export function deriveSupportOperatorInsights({
  conversation = {},
  messages = [],
  linkedTicket = null,
}) {
  const channel = conversation.channel || '—';
  const status = conversation.status || '—';
  const serviceArea = conversation.service_area || null;
  const category = conversation.category || null;
  const urgency = conversation.urgency || null;

  const meta = lastMeta(messages, () => true);
  const likelyIntent =
    meta?.router_intent ||
    meta?.intent ||
    serviceArea ||
    (category && category !== 'other' ? category : null) ||
    '—';

  const handoffSummary =
    conversation.last_assistant_handoff_summary ||
    linkedTicket?.assistant_handoff_summary ||
    null;

  let escalationReason = null;
  if (linkedTicket?.ticket_source === 'portal_assistant' || linkedTicket?.assistant_conversation_id) {
    escalationReason = 'Portal Assistant escalation (ticket)';
  }
  if (conversation.status === 'escalated') {
    escalationReason = escalationReason
      ? `${escalationReason}; conversation marked escalated`
      : 'Conversation marked escalated';
  }
  if (handoffSummary && !escalationReason) {
    escalationReason = 'Website assistant handoff summary on record';
  } else if (handoffSummary && escalationReason && !escalationReason.includes('handoff')) {
    escalationReason = `${escalationReason}; website assistant handoff summary on record`;
  }

  let sentimentOrRisk = null;
  if (urgency === 'urgent' || urgency === 'high') {
    sentimentOrRisk = `Urgency flag: ${urgency}`;
  }
  if (meta?.legal_refusal) {
    sentimentOrRisk = sentimentOrRisk
      ? `${sentimentOrRisk}; legal-advice refusal triggered`
      : 'Legal-advice refusal triggered';
  }

  let suggestedNext = 'Review latest customer messages and reply or update ticket status.';
  if (handoffSummary) {
    suggestedNext = 'Read handoff summary, then reply with next concrete step.';
  }
  if (linkedTicket?.ticket_source === 'portal_assistant' || linkedTicket?.assistant_conversation_id) {
    suggestedNext =
      'Open Portal Assistant transcript context; confirm client identity before substantive changes.';
  }
  if (status === 'escalated' && !handoffSummary) {
    suggestedNext = 'Confirm escalation reason in transcript; assign or resolve.';
  }

  return {
    likelyIntent,
    channel,
    escalationReason,
    sentimentOrRisk,
    suggestedNext,
  };
}
