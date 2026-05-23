import React, { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { parseMajorToMinor } from '../../utils/rentMoney';

const CATEGORIES = [
  'REPAIRS', 'MAINTENANCE', 'COMPLIANCE_CERTIFICATE', 'INSURANCE', 'UTILITIES',
  'MANAGEMENT', 'CONTRACTOR', 'CLEANING', 'OTHER',
];

export function ExpenseFormModal({ open, onClose, onSubmit, saving, properties, initial }) {
  const [form, setForm] = useState(
    initial || {
      property_id: '',
      category: 'REPAIRS',
      amount: '',
      expense_date: new Date().toISOString().slice(0, 10),
      vendor_name: '',
      description: '',
      compliance_related: false,
    },
  );

  if (!open) return null;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      property_id: form.property_id,
      category: form.category,
      amount_minor: parseMajorToMinor(form.amount),
      expense_date: form.expense_date,
      vendor_name: form.vendor_name || undefined,
      description: form.description || undefined,
      compliance_related: !!form.compliance_related,
    });
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="expense-form-modal">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Add expense</h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={form.property_id}
            onChange={(e) => set('property_id', e.target.value)}
            required
          >
            <option value="">Select property</option>
            {(properties || []).map((p) => (
              <option key={p.property_id} value={p.property_id}>
                {p.nickname || p.address_line_1 || p.property_id}
              </option>
            ))}
          </select>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={form.category}
            onChange={(e) => set('category', e.target.value)}
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
            ))}
          </select>
          <Input placeholder="Amount (£)" value={form.amount} onChange={(e) => set('amount', e.target.value)} required />
          <Input type="date" value={form.expense_date} onChange={(e) => set('expense_date', e.target.value)} required />
          <Input placeholder="Vendor (optional)" value={form.vendor_name} onChange={(e) => set('vendor_name', e.target.value)} />
          <Input placeholder="Description (optional)" value={form.description} onChange={(e) => set('description', e.target.value)} />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.compliance_related}
              onChange={(e) => set('compliance_related', e.target.checked)}
            />
            Compliance-related expense
          </label>
          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving} data-testid="expense-form-submit">Save</Button>
          </div>
        </form>
      </div>
    </div>
  );
}
