import React, { useState } from 'react';
import { Button } from '../ui/button';

const REMINDER_TYPES = [
  { value: 'due_soon', label: 'Due soon' },
  { value: 'due_today', label: 'Due today' },
  { value: 'overdue_3d', label: 'Overdue 3 days' },
  { value: 'overdue_7d', label: 'Overdue 7 days' },
  { value: 'overdue_14d', label: 'Overdue 14 days' },
];

export function MarkReminderSentModal({ open, onClose, onSubmit, saving, ledger }) {
  const [reminderType, setReminderType] = useState('overdue_7d');
  const [channel, setChannel] = useState('email');
  const [preview, setPreview] = useState('');

  if (!open || !ledger) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
      data-testid="mark-reminder-modal"
    >
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-midnight-blue mb-1">Mark reminder sent</h3>
        <p className="text-sm text-gray-500 mb-4">
          {ledger.tenant_name} · {ledger.period_key} — tracked manually until live send is enabled.
        </p>
        <div className="space-y-3">
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={reminderType}
            onChange={(e) => setReminderType(e.target.value)}
          >
            {REMINDER_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          >
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="phone">Phone</option>
            <option value="manual">Manual / in person</option>
          </select>
          <textarea
            className="w-full border rounded-md px-3 py-2 text-sm min-h-[72px]"
            placeholder="Message preview (optional)"
            value={preview}
            onChange={(e) => setPreview(e.target.value)}
          />
        </div>
        <div className="flex gap-2 justify-end mt-4">
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button
            type="button"
            disabled={saving}
            onClick={() => onSubmit({ reminder_type: reminderType, channel, message_preview: preview || undefined })}
            data-testid="mark-reminder-submit"
          >
            {saving ? 'Saving…' : 'Mark sent'}
          </Button>
        </div>
      </div>
    </div>
  );
}
