/**
 * Lead capture and activity API (unified lead engine).
 * Uses REACT_APP_BACKEND_URL for base URL.
 */

const getBaseUrl = () => process.env.REACT_APP_BACKEND_URL || '';

export async function capturePricing(data) {
  const res = await fetch(`${getBaseUrl()}/api/leads/capture/pricing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: data.name || null,
      email: data.email,
      phone: data.phone || null,
      company_name: data.company_name || null,
      message: data.message || null,
      marketing_consent: data.marketing_consent ?? false,
      utm_source: data.utm_source || null,
      utm_medium: data.utm_medium || null,
      utm_campaign: data.utm_campaign || null,
    }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Failed to submit');
  return json;
}

export async function captureAutomationEnquiry(data) {
  const res = await fetch(`${getBaseUrl()}/api/leads/capture/automation-enquiry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: data.name || null,
      email: data.email,
      phone: data.phone || null,
      company_name: data.company_name || null,
      message: data.message || null,
      marketing_consent: data.marketing_consent ?? false,
      utm_source: data.utm_source || null,
      utm_medium: data.utm_medium || null,
      utm_campaign: data.utm_campaign || null,
    }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Failed to submit');
  return json;
}

export async function captureMarketResearchEnquiry(data) {
  const res = await fetch(`${getBaseUrl()}/api/leads/capture/market-research-enquiry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: data.name || null,
      email: data.email,
      phone: data.phone || null,
      company_name: data.company_name || null,
      message: data.message || null,
      marketing_consent: data.marketing_consent ?? false,
      utm_source: data.utm_source || null,
      utm_medium: data.utm_medium || null,
      utm_campaign: data.utm_campaign || null,
    }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Failed to submit');
  return json;
}

export async function recordLeadActivity(leadId, activityType) {
  const res = await fetch(`${getBaseUrl()}/api/leads/activity`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_id: leadId, activity_type: activityType }),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.detail || 'Failed to record activity');
  return json;
}
