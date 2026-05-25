import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { RentStatusBadge } from './RentStatusBadge';
import { formatMinorUnits } from '../../utils/rentMoney';

const PAYABLE_STATUSES = new Set(['UPCOMING', 'DUE_TODAY', 'PARTIALLY_PAID', 'OVERDUE', 'SEVERELY_OVERDUE', 'DISPUTED']);

function isPayable(row) {
  if (!row || (row.status || '') === 'PAID' || (row.status || '') === 'WAIVED') return false;
  const outstanding = parseInt(row.outstanding_balance_minor, 10) || 0;
  return outstanding > 0 || PAYABLE_STATUSES.has(row.status);
}

export function RentLedgerList({ ledgers, onSelect, onRecordPayment }) {
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
            <div className="text-right flex flex-col items-end gap-1">
              <RentStatusBadge status={row.status} />
              {row.legacy_rent_authority && (
                <span className="text-[10px] text-amber-700 font-medium">Legacy period</span>
              )}
              <p className="text-sm font-semibold">
                {formatMinorUnits(row.outstanding_balance_minor, row.currency)}
              </p>
              {onRecordPayment && isPayable(row) && (
                <Button
                  size="sm"
                  variant="outline"
                  data-testid="ledger-record-payment"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRecordPayment(row);
                  }}
                >
                  Record payment
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
