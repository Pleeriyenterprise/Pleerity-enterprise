import React from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { RentStatusBadge } from './RentStatusBadge';
import { formatMinorUnits } from '../../utils/rentMoney';
import { cn } from '@/lib/utils';
import ListCognitionChip from '../operational/ListCognitionChip';

export function RentAttentionList({ ledgers, onSelect, onRecordPayment }) {
  if (!ledgers.length) {
    return (
      <Card data-testid="rent-attention-empty">
        <CardContent className="py-8 text-center text-gray-500">Nothing needs attention right now.</CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-2" data-testid="rent-attention-list">
      <h2 className="text-sm font-semibold text-gray-700">Needs attention ({ledgers.length})</h2>
      {ledgers.map((row) => {
        const urgent = row.is_overdue || ['OVERDUE', 'SEVERELY_OVERDUE', 'DUE_TODAY'].includes(row.status);
        return (
          <Card
            key={row.ledger_id}
            className={cn(
              'cursor-pointer hover:border-gray-300 transition-colors',
              urgent && 'border-orange-300 bg-orange-50/40',
            )}
            onClick={() => onSelect(row)}
          >
            <CardContent className="p-4 flex flex-wrap justify-between gap-2 items-center">
              <div>
                <p className="font-medium text-midnight-blue">{row.tenant_name || 'Tenant'}</p>
                <p className="text-sm text-gray-500">
                  {row.period_key} · Due {row.due_date}
                </p>
                <ListCognitionChip entity={row} className="mt-1" />
              </div>
              <div className="text-right flex flex-col items-end gap-1">
                <RentStatusBadge status={row.status} />
                {row.is_overdue && (
                  <span className="text-xs text-orange-700 font-medium">Overdue balance</span>
                )}
                <p className="text-sm font-semibold">
                  {formatMinorUnits(row.outstanding_balance_minor, row.currency)} outstanding
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRecordPayment(row);
                  }}
                >
                  Record payment
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
