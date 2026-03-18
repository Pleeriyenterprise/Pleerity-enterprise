/**
 * Public page: submit admin-requested order info via magic link (no portal login).
 * URL: /order/provide-info?token=...
 */
import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function OrderProvideInfoPublicPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') || '';
  const [loading, setLoading] = useState(true);
  const [ctx, setCtx] = useState(null);
  const [error, setError] = useState(null);
  const [fields, setFields] = useState({});
  const [confirmation, setConfirmation] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('This link is missing required information. Please use the link from your email.');
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const r = await fetch(
          `${API_URL}/api/public/orders/provide-info-context?token=${encodeURIComponent(token)}`
        );
        const data = await r.json().catch(() => ({}));
        if (!r.ok) {
          setError(data.detail || 'Unable to load this page.');
          setLoading(false);
          return;
        }
        if (!data.requires_input) {
          setCtx({ notRequired: true, message: data.message });
          setLoading(false);
          return;
        }
        setCtx(data);
        const init = {};
        (data.requested_fields || []).forEach((f) => {
          init[f] = '';
        });
        if (!data.requested_fields?.length) {
          init.clarification = '';
        }
        setFields(init);
      } catch (e) {
        setError('Could not reach the server. Please try again later.');
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const fieldKeys = useMemo(() => {
    if (!ctx?.requested_fields?.length) return ['clarification'];
    return ctx.requested_fields;
  }, [ctx]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!confirmation) return;
    setSubmitting(true);
    try {
      const r = await fetch(`${API_URL}/api/public/orders/submit-provide-info`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, fields, confirmation: true }),
      });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) {
        setError(data.detail || 'Submission failed.');
        setSubmitting(false);
        return;
      }
      setDone(true);
    } catch {
      setError('Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <Loader2 className="h-8 w-8 animate-spin text-slate-500" />
      </div>
    );
  }

  if (error && !ctx) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-6 flex gap-3 text-amber-800">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <p>{typeof error === 'string' ? error : 'Something went wrong.'}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (ctx?.notRequired) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-lg w-full">
          <CardHeader>
            <CardTitle>Information not needed</CardTitle>
            <CardDescription>{ctx.message}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
        <Card className="max-w-lg w-full">
          <CardContent className="pt-8 pb-8 text-center">
            <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-slate-900">Thank you</h2>
            <p className="text-slate-600 mt-2">
              Your information has been submitted. We&apos;ll continue processing your order.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4">
      <div className="max-w-xl mx-auto">
        <Card>
          <CardHeader>
            <CardTitle>Provide information</CardTitle>
            <CardDescription>
              Order {ctx?.order_ref || ''} — {ctx?.service_name}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg bg-slate-100 p-4 mb-6 text-sm text-slate-700 whitespace-pre-wrap">
              {ctx?.request_notes}
            </div>
            {error && (
              <div className="mb-4 text-sm text-red-700 bg-red-50 p-3 rounded-md">{error}</div>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              {fieldKeys.map((key) => (
                <div key={key}>
                  <Label htmlFor={key} className="capitalize">
                    {key.replace(/_/g, ' ')}
                  </Label>
                  <Textarea
                    id={key}
                    className="mt-1 min-h-[80px]"
                    value={fields[key] || ''}
                    onChange={(e) => setFields((prev) => ({ ...prev, [key]: e.target.value }))}
                    required
                  />
                </div>
              ))}
              <div className="flex items-start gap-2 pt-2">
                <Checkbox
                  id="conf"
                  checked={confirmation}
                  onCheckedChange={(v) => setConfirmation(!!v)}
                />
                <Label htmlFor="conf" className="text-sm font-normal leading-tight cursor-pointer">
                  I confirm the information above is accurate.
                </Label>
              </div>
              <Button type="submit" className="w-full" disabled={!confirmation || submitting}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Submit'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
