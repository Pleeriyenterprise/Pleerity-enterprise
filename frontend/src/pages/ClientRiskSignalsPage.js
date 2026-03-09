/**
 * Operations → Risk Signals: predictive insights with actions (create inspection / work order).
 * Gated by predictive_maintenance.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { TrendingUp, Loader2, AlertCircle, ClipboardCheck, Wrench } from 'lucide-react';
import { toast } from 'sonner';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';

function ClientRiskSignalsPageInner() {
  const navigate = useNavigate();
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    clientAPI
      .getPredictiveInsights({ limit: 100 })
      .then((res) => setInsights(res.data))
      .catch((err) => {
        if (err?.response?.status === 403) {
          setError(err?.response?.data?.detail || 'Predictive maintenance is not enabled for your account.');
        } else {
          setError('Failed to load risk signals.');
          toast.error(err?.response?.data?.detail || 'Failed to load risk signals');
        }
        setInsights(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openCreateWorkOrder = (propertyId, description) => {
    const params = new URLSearchParams();
    if (propertyId) params.set('property_id', propertyId);
    if (description) params.set('description', description);
    navigate(`/operations/work-orders?${params.toString()}`);
  };

  if (error && !loading) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-4">
          <TrendingUp className="w-7 h-7" />
          Risk Signals
        </h1>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <p className="font-medium text-amber-900">Predictive maintenance not enabled</p>
              <p className="text-sm text-amber-800 mt-1">{error}</p>
              <p className="text-sm text-amber-700 mt-2">
                Contact your account administrator or support to enable predictive maintenance for your account.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const items = [];
  if (insights?.properties?.length) {
    insights.properties.forEach((prop) => {
      (prop.insights || []).forEach((i, idx) => {
        items.push({
          key: `${prop.property_id}-${idx}`,
          propertyId: prop.property_id,
          propertyLabel: prop.nickname || prop.address_line_1 || prop.property_id,
          recommendation: i.recommendation,
          detail: i.detail,
          risk: i.risk,
        });
      });
    });
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2 mb-2">
        <TrendingUp className="w-7 h-7" />
        Risk Signals
      </h1>
      <p className="text-gray-600 mb-6">
        Predicted risks and recommended actions from your property data. Create inspections or work orders to address them.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Signals</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-2 text-gray-500 py-8">
              <Loader2 className="w-5 h-5 animate-spin" />
              Loading…
            </div>
          ) : items.length === 0 ? (
            <p className="text-gray-500 py-6">
              No risk signals yet. Add property assets (e.g. boiler, last service date) or ensure building age is set to get recommendations.
            </p>
          ) : (
            <ul className="space-y-3">
              {items.map((item) => (
                <li
                  key={item.key}
                  className="flex flex-wrap items-center justify-between gap-3 p-3 bg-gray-50 rounded-lg border border-gray-100"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-gray-900">{item.propertyLabel}</p>
                    <p className="text-sm text-gray-700">{item.recommendation}</p>
                    {item.detail && <p className="text-xs text-gray-500 mt-0.5">{item.detail}</p>}
                    <span
                      className={`inline-block mt-2 text-xs px-1.5 py-0.5 rounded ${
                        item.risk === 'high' || item.risk === 'urgent' ? 'bg-amber-100 text-amber-800' : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {item.risk || 'medium'}
                    </span>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => openCreateWorkOrder(item.propertyId, item.recommendation)}
                    >
                      <Wrench className="w-4 h-4 mr-1" />
                      Create work order
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/properties/${item.propertyId}`)}
                    >
                      <ClipboardCheck className="w-4 h-4 mr-1" />
                      View property
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ClientRiskSignalsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="predictive_maintenance">
      <ClientRiskSignalsPageInner />
    </EntitlementProtectedRoute>
  );
}
