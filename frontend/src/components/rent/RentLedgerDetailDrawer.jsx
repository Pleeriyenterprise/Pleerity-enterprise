import React from 'react';
import { Button } from '../ui/button';
import { RentStatusBadge } from './RentStatusBadge';
import { formatMinorUnits } from '../../utils/rentMoney';
import { cn } from '@/lib/utils';

export function RentLedgerDetailDrawer({
  ledger,
  onClose,
  onRecordPayment,
  onMarkReminder,
}) {
  if (!ledger) return null;

  const overdueHighlight = ledger.is_overdue || ['OVERDUE', 'SEVERELY_OVERDUE'].includes(ledger.status);

  return (
    <div className="fixed inset-0 z-40 flex justify-end" data-testid="rent-ledger-drawer">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} aria-hidden />
      <div className="relative bg-white w-full max-w-md h-full shadow-xl overflow-y-auto p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold text-midnight-blue">{ledger.tenant_name || 'Tenant'}</h3>
            <p className="text-sm text-gray-500">{ledger.period_key} · due {ledger.due_date}</p>
          </div>
          <button type="button" className="text-gray-400 hover:text-gray-600" onClick={onClose}>✕</button>
        </div>

        <div
          className={cn(
            'rounded-lg border p-4 mb-4',
            overdueHighlight ? 'border-orange-300 bg-orange-50/60' : 'border-gray-200',
          )}
        >
          <div className="flex justify-between items-center mb-2">
            <RentStatusBadge status={ledger.status} />
            {ledger.is_overdue && (
              <span className="text-xs font-medium text-orange-700">Operationally overdue</span>
            )}
          </div>
          <p className="text-sm">
            Outstanding: <strong>{formatMinorUnits(ledger.outstanding_balance_minor, ledger.currency)}</strong>
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Expected {formatMinorUnits(ledger.expected_amount_minor, ledger.currency)} ·
            received {formatMinorUnits(ledger.received_amount_minor, ledger.currency)}
          </p>
        </div>

        <div className="flex gap-2 mb-6">
          <Button size="sm" onClick={() => onRecordPayment(ledger)}>Record payment</Button>
          <Button size="sm" variant="outline" onClick={() => onMarkReminder(ledger)}>Mark reminder sent</Button>
        </div>

        <section className="mb-6">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Payment history</h4>
          {(ledger.payments || []).length === 0 ? (
            <p className="text-sm text-gray-500">No payments recorded yet.</p>
          ) : (
            <ul className="space-y-2">
              {ledger.payments.map((p) => (
                <li key={p.payment_id} className="text-sm border rounded-md p-2">
                  <span className="font-medium">{formatMinorUnits(p.amount_minor, p.currency)}</span>
                  <span className="text-gray-500"> · {p.payment_date}</span>
                  {p.reference && <p className="text-xs text-gray-500">{p.reference}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section>
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Reminder timeline</h4>
          {(ledger.reminders || []).length === 0 ? (
            <p className="text-sm text-gray-500">No reminders tracked yet.</p>
          ) : (
            <ul className="space-y-2">
              {ledger.reminders.map((r) => (
                <li key={r.reminder_key} className="text-sm border rounded-md p-2">
                  <span className="font-medium">{r.reminder_type?.replace(/_/g, ' ')}</span>
                  <span className="text-gray-500"> · {r.delivery_status || 'manual'}</span>
                  {r.sent_at && <p className="text-xs text-gray-500">{r.sent_at}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
