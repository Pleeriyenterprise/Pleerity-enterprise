import React from 'react';
import { Card, CardContent } from '../ui/card';
import { RentStatusBadge } from './RentStatusBadge';
import { formatMinorUnits } from '../../utils/rentMoney';

export function RentLedgerList({ ledgers, onSelect }) {
  if (!ledgers.length) {
    return (
      <Card data-testid="rent-ledger-empty">
        <CardContent className="py-8 text-center text-gray-500">No rent periods yet.</CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2" data-testid="rent-ledger-list">
      {ledgers.map((row) => (
        <Card
          key={row.ledger_id}
          className="cursor-pointer hover:border-gray-300"
          onClick={() => onSelect(row)}
        >
          <CardContent className="p-4 flex justify-between items-center gap-2">
            <div>
              <p className="font-medium text-midnight-blue">{row.tenant_name || 'Tenant'}</p>
              <p className="text-sm text-gray-500">{row.period_key} · {row.due_date}</p>
            </div>
            <div className="text-right">
              <RentStatusBadge status={row.status} />
              <p className="text-sm font-semibold mt-1">
                {formatMinorUnits(row.outstanding_balance_minor, row.currency)}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
