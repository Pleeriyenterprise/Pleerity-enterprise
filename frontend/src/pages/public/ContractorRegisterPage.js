import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Alert, AlertDescription } from '../../components/ui/alert';
import { CheckCircle, AlertCircle, Wrench } from 'lucide-react';

function parseCommaList(text) {
  return String(text || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

const ContractorRegisterPage = () => {
  const rawBase = typeof process.env.REACT_APP_BACKEND_URL === 'string' ? process.env.REACT_APP_BACKEND_URL.trim() : '';
  const apiRoot = rawBase ? `${rawBase.replace(/\/$/, '')}/api` : '/api';
  const [registrationOpen, setRegistrationOpen] = useState(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    trade_types: '',
    postcode: '',
    credentials: '',
    insurance_details: '',
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${apiRoot}/public/contractors/registration-open`);
        const data = await res.json().catch(() => ({}));
        if (!cancelled) setRegistrationOpen(!!data.enabled);
      } catch {
        if (!cancelled) setRegistrationOpen(false);
      } finally {
        if (!cancelled) setLoadingStatus(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiRoot]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const trades = parseCommaList(form.trade_types);
    if (!form.name.trim()) {
      setError('Name or business name is required.');
      return;
    }
    if (!form.email.trim()) {
      setError('Email is required.');
      return;
    }
    if (trades.length === 0) {
      setError('Enter at least one trade or service (comma-separated).');
      return;
    }
    if (!form.postcode.trim()) {
      setError('Primary postcode or service area is required.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch(`${apiRoot}/public/contractors/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          email: form.email.trim(),
          phone: form.phone.trim() || null,
          trade_types: trades,
          postcode: form.postcode.trim(),
          credentials: parseCommaList(form.credentials),
          insurance_details: form.insurance_details.trim() || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const d = data?.detail;
        setError(typeof d === 'string' ? d : d?.message || 'Could not submit application.');
        return;
      }
      setSuccess(true);
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PublicLayout>
      <SEOHead
        title="Join the contractor network"
        description="Apply to join the Pleerity contractor network for compliance and maintenance work."
        canonicalUrl="/contractors/register"
      />
      <div className="max-w-lg mx-auto px-4 py-12">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Wrench className="h-6 w-6 text-electric-teal" />
              <CardTitle className="text-2xl text-midnight-blue">Join the contractor network</CardTitle>
            </div>
            <CardDescription>
              Apply to work with our clients on compliance and maintenance jobs. This is{' '}
              <strong>not</strong> instant access: we review every application. For employment, see{' '}
              <Link to="/careers/talent-pool" className="text-electric-teal hover:underline">
                careers / talent pool
              </Link>
              .
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {loadingStatus ? (
              <p className="text-sm text-gray-600">Checking whether applications are open…</p>
            ) : registrationOpen === false ? (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <span className="font-medium text-gray-900">Applications are not open</span>
                  <span className="block mt-2 text-gray-700">
                    Public contractor applications are disabled in this environment. If our team or a client invited you, use the link in your email to set your password, then sign in via{' '}
                    <Link to="/login" className="font-medium text-electric-teal hover:underline">
                      Portal login
                    </Link>{' '}
                    → Contractor portal. Otherwise{' '}
                    <Link to="/contact" className="font-medium text-electric-teal hover:underline">
                      contact us
                    </Link>{' '}
                    to discuss joining the network.
                  </span>
                </AlertDescription>
              </Alert>
            ) : success ? (
              <div className="text-center py-4 space-y-3">
                <CheckCircle className="h-12 w-12 text-green-600 mx-auto" />
                <p className="font-medium text-midnight-blue">Application submitted</p>
                <p className="text-sm text-gray-600 text-left">
                  We have emailed you at the address you provided to confirm receipt. Our team will review your application.
                  If you are approved, you will receive a separate email with a secure link to set your password and activate your contractor portal.
                </p>
                <p className="text-sm text-gray-600 text-left">
                  After activation, sign in anytime via{' '}
                  <Link to="/login" className="text-electric-teal font-medium hover:underline">
                    Portal login
                  </Link>{' '}
                  → Contractor portal.
                </p>
                <Button asChild variant="outline" className="mt-2">
                  <Link to="/login">Back to Portal login</Link>
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {error ? (
                  <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                ) : null}
                <p className="text-sm text-gray-600">
                  Applications are <strong>open</strong>. Submitting this form adds you to our <strong>pending approval</strong> queue; you cannot sign in until an administrator approves you and you complete the email setup link.
                </p>
                <div className="space-y-2">
                  <Label htmlFor="name">Name / business *</Label>
                  <Input
                    id="name"
                    value={form.name}
                    onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="e.g. Smith Heating Ltd"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="phone">Phone</Label>
                  <Input
                    id="phone"
                    value={form.phone}
                    onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trade_types">Trades / services *</Label>
                  <Input
                    id="trade_types"
                    value={form.trade_types}
                    onChange={(e) => setForm((f) => ({ ...f, trade_types: e.target.value }))}
                    placeholder="e.g. Gas, Plumbing, Electrical"
                    required
                  />
                  <p className="text-xs text-gray-500">Comma-separated</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="postcode">Primary postcode / base *</Label>
                  <Input
                    id="postcode"
                    value={form.postcode}
                    onChange={(e) => setForm((f) => ({ ...f, postcode: e.target.value }))}
                    placeholder="e.g. SW1A 1AA"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="credentials">Certifications (optional)</Label>
                  <Input
                    id="credentials"
                    value={form.credentials}
                    onChange={(e) => setForm((f) => ({ ...f, credentials: e.target.value }))}
                    placeholder="e.g. Gas Safe, NICEIC"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="insurance">Insurance notes (optional)</Label>
                  <Textarea
                    id="insurance"
                    rows={2}
                    value={form.insurance_details}
                    onChange={(e) => setForm((f) => ({ ...f, insurance_details: e.target.value }))}
                  />
                </div>
                <Button type="submit" className="w-full bg-electric-teal hover:bg-electric-teal/90" disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Submit application'}
                </Button>
                <p className="text-center text-sm text-gray-500">
                  Already invited and activated?{' '}
                  <Link to="/login" className="text-electric-teal hover:underline">
                    Portal login
                  </Link>{' '}
                  → Contractor portal.
                </p>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </PublicLayout>
  );
};

export default ContractorRegisterPage;
