import React, { useEffect, useMemo, useState } from 'react';
import { Button } from '../ui/button';
import { clientAPI } from '../../api/client';
import { parseMajorToMinor } from '../../utils/rentMoney';

function makeIdempotencyKey() {
  return `rs_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export function RentScheduleSetupModal({
  open,
  onClose,
  onCreated,
  onError,
  properties,
  initialPropertyId = '',
  tenancyBackendReady = true,
}) {
  const [form, setForm] = useState({
    property_id: initialPropertyId || '',
    tenancy_id: '',
    expected_amount: '',
    due_day: '1',
    start_date: new Date().toISOString().slice(0, 10),
    rent_frequency: 'monthly',
    is_external_payer: false,
    external_payer_name: '',
  });
  const [tenancies, setTenancies] = useState([]);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(makeIdempotencyKey);

  useEffect(() => {
    if (!open) return;
    setIdempotencyKey(makeIdempotencyKey());
    setForm((f) => ({ ...f, property_id: initialPropertyId || f.property_id }));
  }, [open, initialPropertyId]);

  useEffect(() => {
    if (!open || !form.property_id) {
      setTenancies([]);
      return;
    }
    if (tenancyBackendReady === false) {
      setTenancies([]);
      return;
    }
    clientAPI
      .getRentTenancies({ property_id: form.property_id })
      .then((res) => setTenancies(res.data?.tenancies || []))
      .catch(() => setTenancies([]));
  }, [open, form.property_id, tenancyBackendReady]);

  const canPreview = useMemo(
    () =>
      form.property_id &&
      form.expected_amount &&
      form.start_date &&
      (form.is_external_payer ? form.external_payer_name : form.tenancy_id),
    [form],
  );

  useEffect(() => {
    if (!open || !canPreview) {
      setPreview(null);
      return;
    }
    const t = setTimeout(() => {
      setPreviewLoading(true);
      clientAPI
        .previewRentSchedule({
          property_id: form.property_id,
          expected_amount_minor: parseMajorToMinor(form.expected_amount),
          due_day: parseInt(form.due_day, 10) || 1,
          start_date: form.start_date,
          rent_frequency: form.rent_frequency,
        })
        .then((res) => setPreview(res.data))
        .catch(() => setPreview(null))
        .finally(() => setPreviewLoading(false));
    }, 400);
    return () => clearTimeout(t);
  }, [open, canPreview, form.property_id, form.expected_amount, form.due_day, form.start_date, form.rent_frequency]);

  const ensureTenancy = async () => {
    const res = await clientAPI.createRentTenancy({
      property_id: form.property_id,
      rent_tracking_enabled: true,
    });
    const t = res.data;
    setTenancies((prev) => [t, ...prev.filter((x) => x.tenancy_id !== t.tenancy_id)]);
    setForm((f) => ({ ...f, tenancy_id: t.tenancy_id }));
    return t.tenancy_id;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving) return;
    setSaving(true);
    try {
      let tenancyId = form.tenancy_id;
      if (!form.is_external_payer && !tenancyId) {
        tenancyId = await ensureTenancy();
      }
      const body = {
        property_id: form.property_id,
        expected_amount_minor: parseMajorToMinor(form.expected_amount),
        due_day: parseInt(form.due_day, 10) || 1,
        start_date: form.start_date,
        rent_frequency: form.rent_frequency,
        idempotency_key: idempotencyKey,
        is_external_payer: form.is_external_payer,
      };
      if (form.is_external_payer) {
        body.external_payer_name = form.external_payer_name;
      } else {
        body.tenancy_id = tenancyId;
        const t = tenancies.find((x) => x.tenancy_id === tenancyId);
        body.tenant_name = t?.tenant_display_name;
      }
      const res = await clientAPI.createRentSchedule(body);
      await onCreated(res.data);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg =
        typeof detail === 'object' && detail?.message
          ? detail.message
          : typeof detail === 'string'
            ? detail
            : 'Failed to create schedule';
      if (onError) onError(new Error(msg));
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      data-testid="rent-schedule-modal"
      onClick={onClose}
    >
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6" onClick={(e) => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-midnight-blue mb-1">Enable rent tracking</h3>
        <p className="text-xs text-gray-500 mb-4">
          Schedules belong to a property tenancy. Create or select tenancy authority before generating ledger periods.
        </p>
        {tenancyBackendReady === false && (
          <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-3" data-testid="rent-schedule-backend-unavailable">
            Rent tenancy services are not available on this environment yet. Schedule creation is disabled until the backend deploy completes.
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-3">
          <select
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={form.property_id}
            onChange={(e) =>
              setForm((f) => ({ ...f, property_id: e.target.value, tenancy_id: '' }))
            }
            required
            data-testid="rent-schedule-property"
          >
            <option value="">Property</option>
            {properties.map((p) => (
              <option key={p.property_id} value={p.property_id}>
                {p.nickname || p.address_line_1}
              </option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_external_payer}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  is_external_payer: e.target.checked,
                  tenancy_id: e.target.checked ? '' : f.tenancy_id,
                }))
              }
            />
            Manual external payer (non-portal)
          </label>

          {form.is_external_payer ? (
            <input
              className="w-full border rounded-md px-3 py-2 text-sm"
              placeholder="External payer name"
              value={form.external_payer_name}
              onChange={(e) => setForm((f) => ({ ...f, external_payer_name: e.target.value }))}
              required
            />
          ) : (
            <div className="space-y-2">
              <select
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={form.tenancy_id}
                onChange={(e) => setForm((f) => ({ ...f, tenancy_id: e.target.value }))}
                required={tenancies.length > 0}
                data-testid="rent-schedule-tenancy"
              >
                <option value="">Tenancy</option>
                {tenancies.map((t) => (
                  <option key={t.tenancy_id} value={t.tenancy_id}>
                    {t.tenant_display_name} ({t.status})
                  </option>
                ))}
              </select>
              {form.property_id && tenancies.length === 0 && (
                <div className="space-y-2" data-testid="rent-schedule-no-tenancy">
                  <p className="text-xs text-gray-600">
                    No active tenancy for this property. Create one from Occupancy or use the button below
                    before confirming a schedule.
                  </p>
                  <Button type="button" variant="outline" size="sm" onClick={ensureTenancy}>
                    Create tenancy from occupancy
                  </Button>
                </div>
              )}
            </div>
          )}

          <input
            className="w-full border rounded-md px-3 py-2 text-sm"
            placeholder="Rent amount (£)"
            value={form.expected_amount}
            onChange={(e) => setForm((f) => ({ ...f, expected_amount: e.target.value }))}
            required
          />
          <input
            type="number"
            min={1}
            max={28}
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={form.due_day}
            onChange={(e) => setForm((f) => ({ ...f, due_day: e.target.value }))}
          />
          <input
            type="date"
            className="w-full border rounded-md px-3 py-2 text-sm"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
            required
          />

          {previewLoading && <p className="text-xs text-gray-500">Calculating period preview…</p>}
          {previewError === 'backend_unavailable' && (
            <p className="text-xs text-amber-800" data-testid="rent-schedule-preview-unavailable">
              Period preview unavailable — backend tenancy routes not live.
            </p>
          )}
          {preview?.disclosure && (
            <p className="text-xs text-midnight-blue bg-slate-50 border rounded p-2" data-testid="rent-schedule-preview">
              {preview.disclosure}
            </p>
          )}

          <div className="flex gap-2 justify-end pt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={saving || !canPreview || tenancyBackendReady === false}
              data-testid="rent-schedule-submit"
            >
              {saving ? 'Creating…' : 'Confirm schedule'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
