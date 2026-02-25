import React, { useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
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
import client from '../../api/client';
import { toast } from 'sonner';

const STEP = { QUESTIONS: 1, PARTIAL_REVEAL: 2, FULL_REPORT: 3 };

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
    try {
      const res = await client.post('/risk-check/preview', {
        property_count: Math.min(100, Math.max(1, Number(step1.property_count) || 1)),
        any_hmo: !!step1.any_hmo,
        gas_status: step1.gas_status,
        eicr_status: step1.eicr_status,
        tracking_method: step1.tracking_method,
      });
      setPreview(res.data);
      setStep(STEP.PARTIAL_REVEAL);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not calculate risk. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [step1]);

  const handleGenerateReport = useCallback(async () => {
    const name = (firstName || '').trim();
    const emailVal = (email || '').trim();
    if (!name || !emailVal) {
      toast.error('Please enter your first name and email.');
      return;
    }
    setLoading(true);
    try {
      const res = await client.post('/risk-check/report', {
        ...step1,
        property_count: Math.min(100, Math.max(1, Number(step1.property_count) || 1)),
        any_hmo: !!step1.any_hmo,
        first_name: name,
        email: emailVal,
        ...getUtm(),
      });
      setReport(res.data);
      setStep(STEP.FULL_REPORT);
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
        <p className="text-sm text-gray-500 mb-6">
          Step {step} of 3
        </p>

        {/* Header */}
        <h1 className="text-3xl font-bold text-midnight-blue mb-2">
          Are You Fully Compliant as a UK Landlord?
        </h1>
        <p className="text-gray-600 mb-8">
          Answer five quick questions and receive a structured compliance risk snapshot based on your responses.
          <br />
          <span className="text-sm text-gray-500">
            This is an informational monitoring indicator. It does not replace professional or legal advice.
          </span>
        </p>

        {/* Step 1 – Questions */}
        {step === STEP.QUESTIONS && (
          <Card className="mb-8">
            <CardContent className="pt-6">
              <h2 className="text-xl font-semibold text-midnight-blue mb-4">Compliance Monitoring Snapshot</h2>
              <div className="space-y-4">
                <div>
                  <Label>How many rental properties do you manage?</Label>
                  <Input
                    type="number"
                    min={1}
                    max={100}
                    value={step1.property_count}
                    onChange={(e) => setStep1((s) => ({ ...s, property_count: e.target.value ? parseInt(e.target.value, 10) : 1 }))}
                    className="mt-1"
                  />
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
                      <SelectItem value="Not sure">Not sure</SelectItem>
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
                      <SelectItem value="Not sure">Not sure</SelectItem>
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
                      <SelectItem value="Manual reminders">Manual reminders</SelectItem>
                      <SelectItem value="Spreadsheet">Spreadsheet</SelectItem>
                      <SelectItem value="No structured tracking">No structured tracking</SelectItem>
                      <SelectItem value="Automated system">Automated system</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Button className="mt-6 w-full" onClick={handleCalculateRisk} disabled={loading}>
                {loading ? 'Calculating…' : 'Calculate Risk'}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Step 2 – Partial reveal + email gate */}
        {step === STEP.PARTIAL_REVEAL && preview && (
          <Card className="mb-8">
            <CardContent className="pt-6">
              <h2 className="text-xl font-semibold text-midnight-blue mb-4">Preliminary Risk Assessment</h2>
              <p className="text-gray-700 mb-4">{preview.teaser_text}</p>
              <div className="rounded-lg bg-gray-100 p-4 mb-6 blur-sm select-none">
                <p className="font-medium">Estimated Compliance Score: {preview.blurred_score_hint}</p>
                <p className="text-sm text-gray-600 mt-1">Potential Monitoring Gaps Identified</p>
              </div>
              <p className="text-gray-600 mb-6">Unlock your full compliance risk breakdown.</p>

              <h3 className="text-lg font-semibold text-midnight-blue mb-2">Get Your Full Compliance Risk Report</h3>
              <p className="text-sm text-gray-600 mb-4">
                Your report includes: estimated monitoring exposure level; expiring or unconfirmed safety indicators; portfolio risk overview; monitoring improvement pathway.
              </p>
              <div className="space-y-4">
                <div>
                  <Label>First Name</Label>
                  <Input value={firstName} onChange={(e) => setFirstName(e.target.value)} className="mt-1" placeholder="First name" />
                </div>
                <div>
                  <Label>Email Address</Label>
                  <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" placeholder="you@example.com" />
                </div>
              </div>
              <Button className="mt-4 w-full" onClick={handleGenerateReport} disabled={loading}>
                {loading ? 'Generating…' : 'Generate My Risk Report'}
              </Button>
              <p className="text-xs text-gray-500 mt-3">
                We will email you a copy of your structured report. No spam. Unsubscribe anytime.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Step 3 – Full report */}
        {step === STEP.FULL_REPORT && report && (
          <div className="space-y-8">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-semibold text-midnight-blue mb-4">Your Compliance Monitoring Snapshot</h2>
                <div className="text-center py-4">
                  <p className="text-4xl font-bold text-midnight-blue">Compliance Score: {report.score}%</p>
                  <p className="text-lg text-gray-700 mt-2">Risk Level: {riskBandLabel(report.risk_band)}</p>
                  <p className="text-sm text-gray-500 mt-1">Based on structured weighting of safety and monitoring indicators.</p>
                </div>
                {report.property_breakdown && report.property_breakdown.length > 0 && (
                  <div className="mt-6">
                    <h3 className="font-semibold text-midnight-blue mb-2">
                      {report.property_breakdown.length === 1 ? 'Property Compliance Position' : 'Portfolio Score'}
                    </h3>
                    {report.property_breakdown.map((row, i) => (
                      <div key={i} className="border rounded p-3 mb-2 text-sm">
                        <span className="font-medium">{row.label}</span> – {row.score}% · Gas: {row.gas} · Electrical: {row.electrical} · Tracking: {row.tracking}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-6 p-4 bg-amber-50 rounded-lg">
                  <h3 className="font-semibold text-midnight-blue mb-2">Estimated Monitoring Exposure</h3>
                  <p className="text-gray-700">{report.exposure_range_label}</p>
                </div>
                {report.flags && report.flags.length > 0 && (
                  <div className="mt-6">
                    <h3 className="font-semibold text-midnight-blue mb-2">Flagged areas</h3>
                    <ul className="list-disc pl-5 space-y-2 text-sm text-gray-700">
                      {report.flags.map((f, i) => (
                        <li key={i}><strong>{f.title}</strong>: {f.description}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <Button variant="outline" className="mt-6" onClick={handleEditResponses}>Edit My Responses</Button>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <h3 className="text-lg font-semibold text-midnight-blue mb-4">What Continuous Monitoring Changes</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="font-medium text-gray-700 mb-2">Without Structured Monitoring</p>
                    <ul className="list-disc pl-5 text-gray-600 space-y-1">
                      <li>Manual renewal tracking</li>
                      <li>Risk of missed expiry dates</li>
                      <li>No centralised audit trail</li>
                      <li>Reactive compliance management</li>
                    </ul>
                  </div>
                  <div>
                    <p className="font-medium text-gray-700 mb-2">With Compliance Vault Pro</p>
                    <ul className="list-disc pl-5 text-gray-600 space-y-1">
                      <li>Automated expiry alerts</li>
                      <li>Centralised certificate vault</li>
                      <li>Portfolio risk visibility</li>
                      <li>Structured audit history</li>
                      <li>Continuous monitoring updates</li>
                    </ul>
                  </div>
                </div>
                <p className="text-gray-500 text-sm mt-4">Monitoring activates across your entire portfolio.</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <h3 className="text-lg font-semibold text-midnight-blue mb-2">Activate Continuous Compliance Monitoring</h3>
                <p className="text-gray-600 text-sm mb-4">
                  Certificate expiry tracking · Renewal reminders · Secure document vault · Compliance score dashboard · Audit-ready reporting · Cancel anytime.
                </p>
                <div className="flex flex-col sm:flex-row gap-3">
                  <Button asChild className="flex-1">
                    <Link to="/intake/start">Activate Monitoring</Link>
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to="/pricing">View Full Plan Comparison</Link>
                  </Button>
                </div>
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
