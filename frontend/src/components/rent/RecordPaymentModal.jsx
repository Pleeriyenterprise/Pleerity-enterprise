import React, { useEffect, useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { formatMinorUnits, parseMajorToMinor } from '../../utils/rentMoney';

function makeIdempotencyKey() {
  return `rp_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function RecordPaymentModal({
  open,
  onClose,
  onSubmit,
  saving,
  ledger,
  properties = [],
  ledgers = [],
}) {
  const [amount, setAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState('');
  const [reference, setReference] = useState('');
  const [note, setNote] = useState('');
  const [fallbackProperty, setFallbackProperty] = useState('');
  const [fallbackTenancy, setFallbackTenancy] = useState('');
  const [fallbackLedger, setFallbackLedger] = useState('');
  const [idempotencyKey, setIdempotencyKey] = useState(makeIdempotencyKey);

  const hasLedgerContext = Boolean(ledger?.ledger_id);
  const outstanding = ledger?.outstanding_balance_minor ?? 0;

  useEffect(() => {
    if (!open) return;
    setIdempotencyKey(makeIdempotencyKey());
    setAmount('');
    setPaymentDate(new Date().toISOString().slice(0, 10));
    setMethod('');
    setReference('');
    setNote('');
    setFallbackProperty(ledger?.property_id || '');
    setFallbackTenancy(ledger?.tenancy_id || '');
    setFallbackLedger(ledger?.ledger_id || '');
  }, [open, ledger]);

  if (!open) return null;

  const filteredLedgers = ledgers.filter(
    (l) =>
      (!fallbackProperty || l.property_id === fallbackProperty) &&
      (!fallbackTenancy || l.tenancy_id === fallbackTenancy) &&
      (l.outstanding_balance_minor || 0) > 0,
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    const ledgerId = hasLedgerContext ? ledger.ledger_id : fallbackLedger;
    if (!ledgerId) return;
    const body = {
      amount_minor: parseMajorToMinor(amount),
      payment_date: paymentDate,
      payment_method: method || undefined,
      reference: reference || undefined,
      note: note || undefined,
      ledger_id: ledgerId,
      idempotency_key: idempotencyKey,
    };
    if (!hasLedgerContext && fallbackProperty) {
      body.property_id = fallbackProperty;
      body.tenancy_id = fallbackTenancy;
    }
    onSubmit(body);
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
      data-testid="record-payment-modal"
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Record payment</h3>

        {hasLedgerContext ? (
          <div className="text-xs text-gray-600 bg-slate-50 border rounded p-3 mb-4 space-y-1" data-testid="payment-authority-context">
            <p>
              <span className="font-medium">Tenant:</span> {ledger.tenant_name || '—'}
            </p>
            <p>
              <span className="font-medium">Period:</span> {ledger.period_key} (due {ledger.due_date})
            </p>
            <p>
              <span className="font-medium">Outstanding:</span> {formatMinorUnits(outstanding)}
            </p>
            <p>
              <span className="font-medium">Status:</span> {ledger.status}
            </p>
          </div>
        ) : (
          <div className="space-y-2 mb-4">
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
              Select property, tenancy, and ledger period. Amount-only payments without authority are not permitted.
            </p>
            <select
              className="w-full border rounded-md px-3 py-2 text-sm"
              value={fallbackProperty}
              onChange={(e) => {
                setFallbackProperty(e.target.value);
                setFallbackLedger('');
              }}
              required
            >
              <option value="">Property</option>
              {properties.map((p) => (
                <option key={p.property_id} value={p.property_id}>
                  {p.nickname || p.address_line_1}
                </option>
              ))}
            </select>
            <select
              className="w-full border rounded-md px-3 py-2 text-sm"
              value={fallbackLedger}
              onChange={(e) => {
                setFallbackLedger(e.target.value);
                const row = ledgers.find((l) => l.ledger_id === e.target.value);
                if (row) setFallbackTenancy(row.tenancy_id || '');
              }}
              required
            >
              <option value="">Ledger period (outstanding)</option>
              {filteredLedgers.map((l) => (
                <option key={l.ledger_id} value={l.ledger_id}>
                  {l.period_key} — {formatMinorUnits(l.outstanding_balance_minor)} due {l.due_date}
                </option>
              ))}
            </select>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs text-gray-500">Amount (£)</label>
            <Input value={amount} onChange={(e) => setAmount(e.target.value)} required placeholder="1200.00" />
          </div>
          <div>
            <label className="text-xs text-gray-500">Payment date</label>
            <Input type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} required />
          </div>
          <Input placeholder="Payment method (optional)" value={method} onChange={(e) => setMethod(e.target.value)} />
          <Input placeholder="Reference (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
          <Input placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving || !(hasLedgerContext || fallbackLedger)}
              data-testid="record-payment-submit"
            >
              {saving ? 'Saving…' : 'Record payment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
