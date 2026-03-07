import React, { useState, useEffect, useCallback } from 'react';
import { clientAPI } from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Briefcase, Loader2, AlertCircle, CheckCircle } from 'lucide-react';

export default function ClientContractorsPage() {
  const [contractors, setContractors] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    clientAPI
      .getContractors({ skip: 0, limit: 100 })
      .then((res) => {
        setContractors(res.data?.contractors || []);
        setTotal(res.data?.total ?? 0);
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        if (err?.response?.status === 403) {
          setError(detail || 'Contractor network is not enabled for your account.');
        } else {
          setError(detail || 'Failed to load contractors.');
        }
        setContractors([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <Briefcase className="w-7 h-7" />
          Contractors
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Contractor network not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{error}</p>
              <p className="text-sm text-amber-700 mt-2">
                Contact your account administrator or support to enable the contractor network for your account.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <Briefcase className="w-7 h-7" />
        Contractors
      </h1>
      <p className="text-gray-600 mb-6">
        Vetted contractors and preferred trades available for your account. Your admin can assign contractors to you or make system-wide contractors visible here.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Available contractors</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : contractors.length === 0 ? (
            <p className="text-gray-500 py-6">No contractors available yet. Your administrator can add and assign contractors from Operations & Compliance → Contractors.</p>
          ) : (
            <ul className="space-y-3">
              {contractors.map((c) => (
                <li
                  key={c.contractor_id}
                  className="flex flex-wrap items-center justify-between gap-2 p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div>
                    <p className="font-medium text-gray-900 flex items-center gap-2">
                      {c.name}
                      {c.vetted && (
                        <span className="inline-flex items-center gap-1 text-xs text-green-700 bg-green-100 px-1.5 py-0.5 rounded">
                          <CheckCircle className="w-3.5 h-3.5" />
                          Vetted
                        </span>
                      )}
                    </p>
                    {c.company_name && <p className="text-sm text-gray-600">{c.company_name}</p>}
                    {(c.trade_types?.length > 0) && (
                      <p className="text-xs text-gray-500 mt-1">
                        {c.trade_types.join(', ')}
                      </p>
                    )}
                    {(c.phone || c.email) && (
                      <p className="text-xs text-gray-500 mt-0.5">
                        {[c.phone, c.email].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {total > 0 && <p className="text-sm text-gray-500 mt-2">Total: {total}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
