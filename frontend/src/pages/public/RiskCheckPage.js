import React, { useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { getPreview, postReport, activate } from '../../api/riskCheckAPI';
import { toast } from 'sonner';

const SCORE_CAP = 97;

const STEP = { QUESTIONS: 1, PARTIAL_REVEAL: 2, EMAIL_GATE: 3, FULL_REPORT: 4 };

// Property count bands (task): map label -> number for API
const PROPERTY_BANDS = [
  { label: '1', value: 1 },
  { label: '2–5', value: 3 },
  { label: '6–10', value: 8 },
  { label: '11–25', value: 18 },
  { label: '25+', value: 30 },
];
function propertyCountToBandValue(n) {
  const num = Number(n) || 1;
  if (num <= 1) return 1;
  if (num <= 5) return 3;
  if (num <= 10) return 8;
  if (num <= 25) return 18;
  return 30;
}

// Tracking options (task-friendly labels; values match backend)
const TRACKING_OPTIONS = [
  { label: 'Manual', value: 'Manual reminders' },
  { label: 'Already use reminders', value: 'Automated system' },
  { label: 'Not sure', value: 'No structured tracking' },
];

function trackRiskCheckEvent(eventName, payload = {}) {
  const data = { event: eventName, ...payload, ts: new Date().toISOString() };
  if (typeof window !== 'undefined') {
    console.log('[risk-check]', eventName, data);
    if (window.__riskCheckTrack) window.__riskCheckTrack(eventName, data);
  }
}

function getUtm() {
  if (typeof window === 'undefined') return {};
  const p = new URLSearchParams(window.location.search);
  return {
    utm_source: p.get('utm_source') || null,
    utm_medium: p.get('utm_medium') || null,
    utm_campaign: p.get('utm_campaign') || null,
  };
}

const RiskCheckPage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(STEP.QUESTIONS);
  const [loading, setLoading] = useState(false);
  const [step1, setStep1] = useState({
    property_count: 1,
    any_hmo: false,
    gas_status: '',
    eicr_status: '',
    tracking_method: '',
  });
  const [preview, setPreview] = useState(null);
  const [firstName, setFirstName] = useState('');
  const [email, setEmail] = useState('');
  const [report, setReport] = useState(null);

  const handleCalculateRisk = useCallback(async () => {
    if (!step1.gas_status || !step1.eicr_status || !step1.tracking_method) {
      toast.error('Please answer all questions.');
      return;
    }
    setLoading(true);
    trackRiskCheckEvent('risk_check_started', { property_count: step1.property_count, any_hmo: step1.any_hmo });
    try {
      const data = await getPreview({
        property_count: Math.min(100, Math.max(1, Number(step1.property_count) || 1)),
        any_hmo: !!step1.any_hmo,
        gas_status: step1.gas_status,
        eicr_status: step1.eicr_status,
        tracking_method: step1.tracking_method,
      });
      setPreview(data);
      setStep(STEP.PARTIAL_REVEAL);
      trackRiskCheckEvent('risk_check_partial_viewed', { risk_band: data.risk_band });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not calculate risk. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [step1]);

  const handleGenerateReport = useCallback(async () => {
    const emailVal = (email || '').trim();
    if (!emailVal) {
      toast.error('Please enter your email address.');
      return;
    }
    setLoading(true);
    trackRiskCheckEvent('risk_check_email_submitted', { has_first_name: !!(firstName || '').trim() });
    try {
      const name = (firstName || '').trim() || 'Guest';
      const data = await postReport({
        ...step1,
        property_count: Math.min(100, Math.max(1, Number(step1.property_count) || 1)),
        any_hmo: !!step1.any_hmo,
        first_name: name,
        email: emailVal,
        ...getUtm(),
      });
      setReport(data);
      setStep(STEP.FULL_REPORT);
      trackRiskCheckEvent('risk_check_full_viewed', { lead_id: data.lead_id, risk_band: data.risk_band });
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not generate report. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [step1, firstName, email]);

  const handleEditResponses = () => {
    setStep(STEP.QUESTIONS);
    setPreview(null);
    setReport(null);
  };

  const riskBandLabel = (band) => {
    if (band === 'HIGH') return 'High';
    if (band === 'MODERATE') return 'Moderate–High';
    return 'Low';
  };

  return (
    <PublicLayout>
      <SEOHead
        title="UK Landlord Compliance Risk Check | Pleerity Compliance Vault Pro"
        description="Answer 5 quick questions to assess your UK landlord compliance monitoring posture. Get a structured risk snapshot and see how continuous tracking reduces renewal gaps."
        canonicalUrl="/risk-check"
      />

      <div className="max-w-2xl mx-auto px-4 py-8">
        {/* Progress */}
        <p className="text-sm text-gray-500 mb-2">
          Step {step} of 4
        </p>
        {/* Trust micro-row */}
        <p className="text-xs text-gray-500 mb-6">
          UK landlord compliance tracking · Certificate expiry reminders · Secure vault
        </p>

        {/* Header */}
        <h1 className="text-3xl font-bold text-midnight-blue mb-2">
          Check Your Compliance Risk in 60 Seconds
        </h1>
        <p className="text-gray-600 mb-2">
          Answer 5 quick questions. Get a structured risk overview. Informational only.
        </p>
        <p className="text-sm text-gray-500 mb-8">
          This is an informational monitoring indicator. It does not replace professional or legal advice.
        </p>

        {/* Step 1 – Questions */}
        {step === STEP.QUESTIONS && (
          <Card className="mb-8">
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div>
                  <Label>How many rental properties do you manage?</Label>
                  <Select
                    value={String(propertyCountToBandValue(step1.property_count))}
                    onValueChange={(v) => setStep1((s) => ({ ...s, property_count: parseInt(v, 10) }))}
                  >
                    <SelectTrigger data-testid="risk-property-count" className="mt-1">
                      <SelectValue placeholder="Select" />
                    </SelectTrigger>
                    <SelectContent>
                      {PROPERTY_BANDS.map((b) => (
                        <SelectItem key={b.value} value={String(b.value)}>{b.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Do any of your properties operate as HMOs?</Label>
                  <Select
                    value={step1.any_hmo ? 'yes' : 'no'}
                    onValueChange={(v) => setStep1((s) => ({ ...s, any_hmo: v === 'yes' }))}
                  >
                    <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="no">No</SelectItem>
                      <SelectItem value="yes">Yes</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>What is the status of your latest Gas Safety Certificate?</Label>
                  <Select
                    value={step1.gas_status}
                    onValueChange={(v) => setStep1((s) => ({ ...s, gas_status: v }))}
                  >
                    <SelectTrigger data-testid="risk-gas"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Valid">Valid</SelectItem>
                      <SelectItem value="Expired">Expired</SelectItem>
                      <SelectItem value="Not sure">I don&apos;t know</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>What is the status of your latest Electrical Installation Condition Report (EICR)?</Label>
                  <Select
                    value={step1.eicr_status}
                    onValueChange={(v) => setStep1((s) => ({ ...s, eicr_status: v }))}
                  >
                    <SelectTrigger data-testid="risk-eicr"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Valid">Valid</SelectItem>
                      <SelectItem value="Expired">Expired</SelectItem>
                      <SelectItem value="Not sure">I don&apos;t know</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>How do you currently track certificate renewals?</Label>
                  <Select
                    value={step1.tracking_method}
                    onValueChange={(v) => setStep1((s) => ({ ...s, tracking_method: v }))}
                  >
                    <SelectTrigger data-testid="risk-tracking"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>
                      {TRACKING_OPTIONS.map((o) => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button className="mt-6 w-full" onClick={handleCalculateRisk} disabled={loading}>
                {loading ? 'Calculating…' : 'Continue'}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 2 – Partial result only (no email yet) */}
        {step === STEP.PARTIAL_REVEAL && preview && (
          <Card className="mb-8">
            <CardContent className="pt-6">
              <h2 className="text-xl font-semibold text-midnight-blue mb-4">Preliminary Result</h2>
              <p className="text-lg font-medium text-gray-800 mb-2">
                Risk Level: {riskBandLabel(preview.risk_band)}
              </p>
              <p className="text-gray-700 mb-4">{preview.teaser_text}</p>
              <div className="rounded-lg bg-gray-100 p-4 mb-4 blur-sm select-none">
                <p className="font-medium">Estimated Compliance Score: {preview.blurred_score_hint}</p>
                <p className="text-sm text-gray-600 mt-1">Potential monitoring gaps identified</p>
              </div>
              <div className="rounded bg-amber-50/80 p-3 mb-6 blur-sm select-none text-sm text-gray-700">
                <p>⚠️ Certificate expiry risk detected</p>
                <p className="mt-1">⚠️ Renewal tracking gaps</p>
              </div>
              <p className="text-gray-600 mb-6">Unlock your full breakdown and suggested next steps.</p>
              <Button className="w-full" onClick={() => setStep(STEP.EMAIL_GATE)}>
                Get Full Risk Report
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 3 – Email gate */}
        {step === STEP.EMAIL_GATE && preview && (
          <Card className="mb-8">
            <CardContent className="pt-6">
              <h2 className="text-xl font-semibold text-midnight-blue mb-2">Send My Full Risk Report</h2>
              <ul className="list-disc pl-5 text-sm text-gray-700 mb-6 space-y-1">
                <li>Exact risk score estimate</li>
                <li>Expiring document reminders preview</li>
                <li>What to upload first (to improve accuracy)</li>
                <li>Recommended next steps (informational)</li>
              </ul>
              <div className="space-y-4">
                <div>
                  <Label>First name (optional)</Label>
                  <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="mt-1" placeholder="First name" />
                </div>
                <div>
                  <Label>Email address (required)</Label>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" placeholder="you@example.com" required />
                </div>
              </div>
              <Button className="mt-4 w-full" onClick={handleGenerateReport} disabled={loading}>
                {loading ? 'Generating…' : 'Generate My Report'}
              </Button>
              <p className="text-xs text-gray-500 mt-3">
                We will email you a copy of your structured report. No spam. Unsubscribe anytime.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Step 4 – Full report */}
        {step === STEP.FULL_REPORT && report && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left: Your Risk Snapshot */}
              <Card>
                <CardContent className="pt-6">
                  <h2 className="text-xl font-semibold text-midnight-blue mb-4">Your Risk Snapshot</h2>
                  <div className="text-center py-4">
                    <p className="text-4xl font-bold text-midnight-blue">Compliance Risk Score (estimate): {report.score} / {SCORE_CAP}</p>
                    <p className="text-lg text-gray-700 mt-2">Risk Level: {riskBandLabel(report.risk_band)}</p>
                    <p className="text-sm text-gray-500 mt-1">Based on structured weighting of safety and monitoring indicators.</p>
                  </div>
                  <div className="mt-6 p-4 bg-amber-50 rounded-lg">
                    <h3 className="font-semibold text-midnight-blue mb-2">Estimated exposure band</h3>
                    <p className="text-gray-700">{report.exposure_range_label}</p>
                    <p className="text-xs text-gray-500 mt-2">Typical financial exposure range can vary; informational only.</p>
                  </div>
                  {report.flags && report.flags.length > 0 && (
                    <div className="mt-6">
                      <h3 className="font-semibold text-midnight-blue mb-2">Flags detected</h3>
                      <ul className="list-disc pl-5 space-y-2 text-sm text-gray-700">
                        {report.flags.map((f, i) => (
                          <li key={i}><strong>{f.title}</strong>: {f.description}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="mt-6">
                    <h3 className="font-semibold text-midnight-blue mb-2">Recommended next steps</h3>
                    <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                      <li>Confirm certificate dates and upload evidence where possible</li>
                      <li>Set up renewal reminders for gas and electrical checks</li>
                      <li>Use a central vault so your portal reflects the evidence you upload</li>
                    </ul>
                  </div>
                  <div className="mt-6 p-3 bg-gray-100 rounded text-xs text-gray-600">
                    Informational tracking indicator only. Not legal advice. Local rules vary. Status is based on your records and dates you confirm.
                  </div>
                  <Button variant="outline" className="mt-6" onClick={handleEditResponses}>Edit My Responses</Button>
                </CardContent>
              </Card>

              {/* Right: How monitoring fixes this (locked dashboard preview) */}
              <Card>
                <CardContent className="pt-6">
                  <h3 className="text-lg font-semibold text-midnight-blue mb-4">How monitoring fixes this</h3>
                  <div className="rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 p-4 space-y-3 opacity-90">
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="font-medium">Expiry tracker</span>
                      <span className="text-xs bg-amber-100 px-2 py-0.5 rounded">Available after subscription</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="font-medium">Alerts</span>
                      <span className="text-xs bg-amber-100 px-2 py-0.5 rounded">Available after subscription</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="font-medium">Vault</span>
                      <span className="text-xs bg-amber-100 px-2 py-0.5 rounded">Available after subscription</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="font-medium">Audit trail</span>
                      <span className="text-xs bg-amber-100 px-2 py-0.5 rounded">Available after subscription</span>
                    </div>
                  </div>
                  <p className="text-gray-500 text-sm mt-4">Your portal will reflect the evidence you upload.</p>
                </CardContent>
              </Card>
            </div>

            {report.property_breakdown && report.property_breakdown.length > 0 && (
              <Card>
                <CardContent className="pt-6">
                  <h3 className="font-semibold text-midnight-blue mb-2">
                    {report.property_breakdown.length === 1 ? 'Property compliance position' : 'Portfolio score'}
                  </h3>
                  {report.property_breakdown.map((row, i) => (
                    <div key={i} className="border rounded p-3 mb-2 text-sm">
                      <span className="font-medium">{row.label}</span> – {row.score}% · Gas: {row.gas} · Electrical: {row.electrical} · Tracking: {row.tracking}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardContent className="pt-6">
                <h3 className="text-lg font-semibold text-midnight-blue mb-2">Activate Continuous Compliance Monitoring</h3>
                <p className="text-gray-600 text-sm mb-4">
                  Certificate expiry tracking · Renewal reminders · Secure document vault · Compliance score dashboard · Audit-ready reporting · Cancel anytime.
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button
                    className="flex-1"
                    onClick={() => {
                      const plan = report.recommended_plan_code || '';
                      trackRiskCheckEvent('risk_check_activate_clicked', { lead_id: report.lead_id, plan });
                      const params = new URLSearchParams();
                      if (plan) params.set('plan', plan);
                      if (report.lead_id) params.set('lead_id', report.lead_id);
                      params.set('from', 'risk-check');
                      activate(report.lead_id, plan).catch(() => {});
                      navigate(`/intake/start?${params.toString()}`);
                    }}
                  >
                    Activate Monitoring
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to="/pricing">View Full Plan Comparison</Link>
                  </Button>
                </div>
                <p className="text-sm text-gray-500 mt-4">
                  What happens next: You&apos;ll complete a short intake, then pay via Stripe. Provisioning begins after payment.
                </p>
              </CardContent>
            </Card>

            <p className="text-xs text-gray-500 border-t pt-6">
              {report.disclaimer_text}
            </p>
          </div>
        )}
      </div>
    </PublicLayout>
  );
};

export default RiskCheckPage;
