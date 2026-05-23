import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { parseMajorToMinor } from '../../utils/rentMoney';

export function RecordPaymentModal({ open, onClose, onSubmit, saving, propertyId, ledgerId }) {
  const [amount, setAmount] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = useState('');
  const [reference, setReference] = useState('');
  const [note, setNote] = useState('');

  if (!open) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    const body = {
      amount_minor: parseMajorToMinor(amount),
      payment_date: paymentDate,
      payment_method: method || undefined,
      reference: reference || undefined,
      note: note || undefined,
    };
    if (ledgerId) body.ledger_id = ledgerId;
    else body.property_id = propertyId;
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
            <Button type="submit" disabled={saving} data-testid="record-payment-submit">
              {saving ? 'Saving…' : 'Record payment'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
