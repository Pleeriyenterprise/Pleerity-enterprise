import { deriveSupportOperatorInsights } from './supportOperatorInsights';

describe('deriveSupportOperatorInsights', () => {
  it('reads portal assistant ticket fields without inventing intent', () => {
    const ticket = {
      contact_method: 'email',
      status: 'new',
      service_area: 'cvp',
      category: 'other',
      priority: 'medium',
      ticket_source: 'portal_assistant',
      assistant_conversation_id: 'asst-abc',
      transcript_available: true,
    };
    const o = deriveSupportOperatorInsights({
      conversation: {
        channel: ticket.contact_method,
        status: ticket.status,
        service_area: ticket.service_area,
        category: ticket.category,
        urgency: null,
      },
      messages: [],
      linkedTicket: ticket,
    });
    expect(o.channel).toBe('email');
    expect(o.likelyIntent).toBe('cvp');
    expect(o.escalationReason).toContain('Portal Assistant');
    expect(o.suggestedNext.toLowerCase()).toContain('portal assistant');
  });
});
