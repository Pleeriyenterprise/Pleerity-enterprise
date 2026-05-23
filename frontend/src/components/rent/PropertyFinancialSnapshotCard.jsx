import React, { useEffect, useState } from 'react';
import { clientAPI } from '../../api/client';
import { formatMinorUnits } from '../../utils/rentMoney';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Loader2 } from 'lucide-react';
import { useEntitlements } from '../../contexts/EntitlementsContext';

export function PropertyFinancialSnapshotCard({ propertyId }) {
  const { hasFeature } = useEntitlements();
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const enabled = hasFeature('rent_operations');

  useEffect(() => {
    if (!enabled || !propertyId) return;
    setLoading(true);
    setError(null);
    clientAPI
      .getPropertyFinancialSnapshot(propertyId)
      .then((res) => setSnapshot(res.data))
      .catch((err) => {
        if (err?.response?.status !== 403) setError('Unable to load operational snapshot');
        setSnapshot(null);
      })
      .finally(() => setLoading(false));
  }, [propertyId, enabled]);

  if (!enabled) return null;
  if (loading) {
    return (
      <Card className="mt-4" data-testid="property-financial-snapshot-loading">
        <CardContent className="py-6 flex justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
        </CardContent>
      </Card>
    );
  }
  if (!snapshot && !error) return null;

  return (
    <Card className="mt-4 border-gray-200" data-testid="property-financial-snapshot">
      <CardHeader className="pb-2">
        <CardTitle className="text-base text-midnight-blue">Operational finances</CardTitle>
        <p className="text-xs text-gray-500">
          Operational estimate only. Not accounting or tax advice.
        </p>
      </CardHeader>
      <CardContent className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
        {error ? (
          <p className="text-gray-500 col-span-full">{error}</p>
        ) : (
          <>
            <div>
              <p className="text-xs text-gray-500">Expected rent / month</p>
              <p className="font-semibold">{formatMinorUnits(snapshot.expected_monthly_rent_minor, snapshot.currency)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Collected this month</p>
              <p className="font-semibold text-emerald-700">
                {formatMinorUnits(snapshot.rent_collected_this_month_minor, snapshot.currency)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Overdue balance</p>
              <p className="font-semibold text-orange-600">
                {formatMinorUnits(snapshot.overdue_balance_minor, snapshot.currency)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Expenses this month</p>
              <p className="font-semibold">{formatMinorUnits(snapshot.total_expenses_this_month_minor, snapshot.currency)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Compliance expenses</p>
              <p className="font-semibold">{formatMinorUnits(snapshot.compliance_related_expenses_minor, snapshot.currency)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Net operational estimate</p>
              <p className="font-semibold">{formatMinorUnits(snapshot.estimated_net_operational_minor, snapshot.currency)}</p>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
