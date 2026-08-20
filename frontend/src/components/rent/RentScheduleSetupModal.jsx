import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import { clientAPI } from '../../api/client';
import { parseMajorToMinor } from '../../utils/rentMoney';
import {
  canConfirmRentSchedule,
  filterTenanciesForProperty,
  pickDefaultTenancyId,
  tenancyBelongsToProperty,
} from '../../utils/rentScheduleTenancy';
import { toast } from '@/utils/portalNotifications';

function makeIdempotencyKey() {
  return `rs_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function parseApiDetail(err) {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'object' && detail?.message) return { code: detail.code, message: detail.message };
  if (typeof detail === 'string') return { code: null, message: detail };
  return { code: null, message: 'Request failed' };
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
  const navigate = useNavigate();
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
  const [tenanciesLoading, setTenanciesLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [creatingTenancy, setCreatingTenancy] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(makeIdempotencyKey);

  const scopedTenancies = useMemo(
    () => filterTenanciesForProperty(tenancies, form.property_id),
    [tenancies, form.property_id],
  );

  const refreshTenancies = useCallback(async (propertyId) => {
    if (!propertyId || tenancyBackendReady === false) {
      setTenancies([]);
      return [];
    }
    setTenanciesLoading(true);
    try {
      const res = await clientAPI.getRentTenancies({ property_id: propertyId });
      const rows = res.data?.tenancies || [];
      setTenancies(rows);
      return rows;
    } catch {
      setTenancies([]);
      return [];
    } finally {
      setTenanciesLoading(false);
    }
  }, [tenancyBackendReady]);

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
    refreshTenancies(form.property_id).then((rows) => {
      const scoped = filterTenanciesForProperty(rows, form.property_id);
      const defaultId = pickDefaultTenancyId(scoped);
      setForm((f) => {
        const keep =
          f.tenancy_id && tenancyBelongsToProperty(f.tenancy_id, scoped, f.property_id)
            ? f.tenancy_id
            : defaultId;
        return { ...f, tenancy_id: keep };
      });
    });
  }, [open, form.property_id, tenancyBackendReady, refreshTenancies]);

  const canPreview = useMemo(
    () =>
      form.property_id &&
      form.expected_amount &&
      form.start_date &&
      (form.is_external_payer ? form.external_payer_name : form.tenancy_id),
    [form],
  );

  const confirmEnabled = useMemo(
    () => canConfirmRentSchedule(form, scopedTenancies, tenancyBackendReady),
    [form, scopedTenancies, tenancyBackendReady],
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

  const openOccupancySetup = useCallback(
    (propertyId) => {
      onClose();
      navigate(`/properties/${propertyId}?tab=occupancy`);
      toast.info('Link or invite a tenant for this property under Occupancy & tenancy, then return to enable rent tracking.');
    },
    [navigate, onClose],
  );

  const handleCreateFromOccupancy = async () => {
    if (creatingTenancy || saving || !form.property_id || tenancyBackendReady === false) return;
    setCreatingTenancy(true);
    try {
      let occupancyTenants = [];
      let occupancySummary = null;
      try {
        const occ = await clientAPI.getPropertyOccupancyOperationalSummary(form.property_id);
        occupancySummary = occ.data || null;
        occupancyTenants = occ.data?.active_tenants || [];
      } catch {
        occupancyTenants = [];
      }

      if (occupancyTenants.length === 0) {
        const occupancyBacked = Boolean(
          occupancySummary?.tenancy_lifecycle?.tenancy_active
            || occupancySummary?.applicability?.tenancy_active
            || occupancySummary?.tenancy_lifecycle?.rent_tenancy_ready,
        );
        if (occupancySummary && !occupancyBacked) {
          openOccupancySetup(form.property_id);
          return;
        }
      }

      const res = await clientAPI.createRentTenancy({
        property_id: form.property_id,
        rent_tracking_enabled: true,
        tenant_ids: occupancyTenants.map((t) => t.tenant_id).filter(Boolean),
        tenant_display_name:
          occupancyTenants[0]?.full_name
          || occupancyTenants[0]?.email
          || undefined,
      });
      const created = res.data;
      const rows = await refreshTenancies(form.property_id);
      const scoped = filterTenanciesForProperty(rows, form.property_id);
      const tenancyId =
        created?.tenancy_id && tenancyBelongsToProperty(created.tenancy_id, scoped, form.property_id)
          ? created.tenancy_id
          : pickDefaultTenancyId(scoped);
      setForm((f) => ({
        ...f,
        tenancy_id: tenancyId || f.tenancy_id,
      }));
      toast.success('Tenancy authority created from occupancy');
    } catch (err) {
      const { code, message } = parseApiDetail(err);
      if (code === 'NO_OCCUPANCY_FOR_TENANCY') {
        openOccupancySetup(form.property_id);
        return;
      }
      if (onError) onError(new Error(message));
      else toast.error(message);
    } finally {
      setCreatingTenancy(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (saving || !confirmEnabled) return;
    setSaving(true);
    try {
      if (!form.is_external_payer && !tenancyBelongsToProperty(form.tenancy_id, scopedTenancies, form.property_id)) {
        throw new Error('Select a tenancy that belongs to this property, or create one from occupancy.');
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
        body.tenancy_id = form.tenancy_id;
        const t = scopedTenancies.find((x) => x.tenancy_id === form.tenancy_id);
        body.tenant_name = t?.tenant_display_name;
      }
      const res = await clientAPI.createRentSchedule(body);
      await onCreated(res.data);
    } catch (err) {
      const { message } = parseApiDetail(err);
      const msg = err?.message || message || 'Failed to create schedule';
      if (onError) onError(new Error(msg));
      else toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handlePropertyChange = (propertyId) => {
    setForm((f) => ({
      ...f,
      property_id: propertyId,
      tenancy_id: '',
    }));
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      data-testid="rent-schedule-modal"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-lg font-semibold text-midnight-blue mb-1">Enable rent tracking</h3>
        <p className="text-xs text-gray-500 mb-4">
          Schedules belong to a property tenancy. Create or select tenancy authority before generating ledger periods.
        </p>
        {tenancyBackendReady === false && (
          <p
            className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-3"
            data-testid="rent-schedule-backend-unavailable"
          >
            Rent tenancy services are not available on this environment yet. Schedule creation is disabled until the
            backend deploy completes.
          </p>
        )}
        <form onSubmit={handleSubmit} className="space-y-3">
          <select
            className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
            value={form.property_id}
            onChange={(e) => handlePropertyChange(e.target.value)}
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

          <label className="flex items-center gap-2 text-sm min-h-11">
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
              className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
              placeholder="External payer name"
              value={form.external_payer_name}
              onChange={(e) => setForm((f) => ({ ...f, external_payer_name: e.target.value }))}
              required
            />
          ) : (
            <div className="space-y-2">
              <select
                className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
                value={form.tenancy_id}
                onChange={(e) => setForm((f) => ({ ...f, tenancy_id: e.target.value }))}
                disabled={!form.property_id || tenanciesLoading}
                data-testid="rent-schedule-tenancy"
              >
                <option value="">
                  {tenanciesLoading ? 'Loading tenancies…' : 'Tenancy'}
                </option>
                {scopedTenancies.map((t) => (
                  <option key={t.tenancy_id} value={t.tenancy_id}>
                    {t.tenant_display_name} ({t.status})
                  </option>
                ))}
              </select>
              {form.property_id && !tenanciesLoading && scopedTenancies.length === 0 && (
                <div className="space-y-2" data-testid="rent-schedule-no-tenancy">
                  <p className="text-xs text-gray-600">
                    No active tenancy for this property. Create one from Occupancy or use the button below before
                    confirming a schedule.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-11 w-full sm:w-auto"
                    onClick={handleCreateFromOccupancy}
                    disabled={creatingTenancy || tenancyBackendReady === false}
                    data-testid="rent-schedule-create-from-occupancy"
                  >
                    {creatingTenancy ? 'Creating tenancy…' : 'Create tenancy from occupancy'}
                  </Button>
                </div>
              )}
            </div>
          )}

          <input
            className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
            placeholder="Rent amount (£)"
            value={form.expected_amount}
            onChange={(e) => setForm((f) => ({ ...f, expected_amount: e.target.value }))}
            required
          />
          <input
            type="number"
            min={1}
            max={28}
            className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
            value={form.due_day}
            onChange={(e) => setForm((f) => ({ ...f, due_day: e.target.value }))}
          />
          <input
            type="date"
            className="w-full border rounded-md px-3 py-2 text-sm min-h-11"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
            required
          />

          {previewLoading && <p className="text-xs text-gray-500">Calculating period preview…</p>}
          {preview?.disclosure && (
            <p className="text-xs text-midnight-blue bg-slate-50 border rounded p-2" data-testid="rent-schedule-preview">
              {preview.disclosure}
            </p>
          )}

          <div className="flex flex-col-reverse sm:flex-row gap-2 justify-end pt-2">
            <Button type="button" variant="outline" className="min-h-11" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              className="min-h-11"
              disabled={saving || !confirmEnabled}
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
