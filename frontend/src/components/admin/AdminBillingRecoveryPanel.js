import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Loader2,
  RefreshCw,
  Send,
  User,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Alert, AlertDescription } from '../ui/alert';
import { toast } from '@/utils/portalNotifications';
import api from '../../api/client';
import {
  getGovernanceConfirmationWording,
  getGovernanceRiskBadgeClass,
} from '../../utils/adminActionGovernance';

const SECTION_LABELS = {
  mode_unverified_clients: 'Billing access needs refresh',
  pending_regeneration: 'Pending secure checkout regeneration',
  orphaned_checkout_sessions: 'Orphaned checkout sessions',
  recently_remediated: 'Recently resolved',
  drift_metrics_summary: 'Recovery summary',
};

const RISK_LABEL = {
  critical: 'High operational risk',
  high: 'Elevated risk',
  medium: 'Review recommended',
  low: 'Routine',
};

const ACTION_LABEL = {
  REGENERATE_CHECKOUT_REQUIRED: 'Regenerate secure checkout',
  ADMIN_SET_MODE_REQUIRED: 'Verify billing environment (manual)',
  PORTAL_RELINK_REQUIRED: 'Regenerate billing portal link',
  CUSTOMER_RECONCILIATION_REQUIRED: 'Customer reconciliation',
  LEGACY_TEST_SUBSCRIPTION: 'Legacy subscription review',
  INVALID_SUBSCRIPTION_REFERENCE: 'Invalid subscription reference',
  NO_ACTION_IF_INACTIVE: 'No action if inactive',
};

function RecoveryClientRow({ row, onSelect, selected }) {
  const risk = row.operational_risk || 'medium';
  return (
    <button
      type="button"
      onClick={() => onSelect(row.client_id)}
      className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
        selected ? 'border-electric-teal bg-teal-50' : 'border-gray-200 hover:bg-gray-50'
      }`}
      data-testid={`recovery-row-${row.client_id}`}
    >
      <div className="flex justify-between items-start gap-2">
        <div>
          <p className="font-medium text-sm text-midnight-blue">{row.client_label || row.client_id?.slice(0, 8)}</p>
          <p className="text-xs text-gray-500">CRN: {row.crn || '—'}</p>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded ${getGovernanceRiskBadgeClass(risk)}`}>
          {RISK_LABEL[risk] || risk}
        </span>
      </div>
      <p className="text-xs text-gray-600 mt-1">
        {ACTION_LABEL[row.recommended_action] || row.recommended_action || 'Review required'}
      </p>
      <p className="text-xs text-gray-400 mt-0.5">
        State: {row.recovery_state?.replace(/_/g, ' ') || '—'}
        {row.recovery_age_days != null ? ` · ${row.recovery_age_days}d open` : ''}
      </p>
    </button>
  );
}

const AdminBillingRecoveryPanel = ({ embedded = true }) => {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedClientId, setSelectedClientId] = useState(null);
  const [caseDetail, setCaseDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [ownerInput, setOwnerInput] = useState('');
  const [bulkPreview, setBulkPreview] = useState(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/admin/billing/recovery/dashboard');
      setDashboard(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load recovery dashboard');
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCase = useCallback(async (clientId) => {
    if (!clientId) {
      setCaseDetail(null);
      return;
    }
    setDetailLoading(true);
    try {
      const res = await api.get(`/admin/billing/recovery/clients/${clientId}`);
      setCaseDetail(res.data);
      setOwnerInput(res.data?.owner || '');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to load recovery case');
      setCaseDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    loadCase(selectedClientId);
  }, [selectedClientId, loadCase]);

  const getReason = (label, actionId) => {
    const reason = window.prompt(
      `${label}\n${getGovernanceConfirmationWording(actionId)}\n\nEnter support reason (min 10 characters):`,
      '',
    );
    if (reason == null) return null;
    const trimmed = reason.trim();
    if (trimmed.length < 10) {
      toast.error('Reason must be at least 10 characters');
      return null;
    }
    return trimmed;
  };

  const handleAssign = async () => {
    if (!selectedClientId || !ownerInput.trim()) return;
    setActionLoading(true);
    try {
      await api.post(`/admin/billing/recovery/clients/${selectedClientId}/assign`, {
        owner: ownerInput.trim(),
      });
      toast.success('Owner assigned');
      await loadCase(selectedClientId);
      await loadDashboard();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Assign failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRegenerate = async () => {
    if (!selectedClientId) return;
    const reason = getReason('Regenerate secure checkout', 'billing_recovery_regenerate_checkout');
    if (!reason) return;
    const sendEmail = window.confirm('Send continuation email to customer?');
    const origin = `${window.location.origin}/admin/billing?tab=recovery`;
    setActionLoading(true);
    try {
      await api.post(`/admin/billing/recovery/clients/${selectedClientId}/regenerate-checkout`, {
        plan_code: 'PLAN_2_PORTFOLIO',
        origin_url: origin,
        send_email: sendEmail,
        reason,
      });
      toast.success('Secure checkout regenerated');
      await loadCase(selectedClientId);
      await loadDashboard();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Regeneration failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handlePortalRelink = async () => {
    if (!selectedClientId) return;
    setActionLoading(true);
    try {
      const res = await api.post(`/admin/billing/recovery/clients/${selectedClientId}/portal-relink`);
      if (res.data?.portal_url) {
        await navigator.clipboard.writeText(res.data.portal_url);
        toast.success('Portal link copied to clipboard');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Portal relink failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCloseout = async () => {
    if (!selectedClientId) return;
    const reason = getReason('Mark recovery resolved', 'billing_recovery_closeout');
    if (!reason) return;
    const summary = window.prompt('Resolution summary (min 10 characters):', '');
    if (!summary || summary.trim().length < 10) {
      toast.error('Resolution summary required');
      return;
    }
    setActionLoading(true);
    try {
      await api.post(`/admin/billing/recovery/clients/${selectedClientId}/closeout`, {
        resolution_summary: summary.trim(),
        reason,
      });
      toast.success('Recovery marked resolved');
      await loadCase(selectedClientId);
      await loadDashboard();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Closeout failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleBulkPreview = async () => {
    const section = dashboard?.sections?.mode_unverified_clients || [];
    const ids = section.slice(0, 5).map((r) => r.client_id).filter(Boolean);
    if (!ids.length) {
      toast.info('No clients in backlog for bulk preview');
      return;
    }
    const reason = getReason('Bulk resend continuation (preview)', 'billing_recovery_bulk_resend');
    if (!reason) return;
    setActionLoading(true);
    try {
      const res = await api.post('/admin/billing/recovery/bulk/resend-continuation', {
        client_ids: ids,
        preview: true,
        reason,
      });
      setBulkPreview(res.data);
      toast.success('Bulk preview ready — confirm to send');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Bulk preview failed');
    } finally {
      setActionLoading(false);
    }
  };

  const unverified = dashboard?.sections?.mode_unverified_clients || [];
  const metrics = (dashboard?.sections?.drift_metrics_summary || [])[0] || {};

  return (
    <div className="space-y-6" data-testid="billing-recovery-panel">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-midnight-blue">Billing recovery</h2>
          <p className="text-sm text-gray-500">
            Guided remediation inside Admin Billing — no silent changes. Customer-facing copy stays calm.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadDashboard} disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          <span className="ml-2">Refresh</span>
        </Button>
      </div>

      {metrics.active_recovery_count != null && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card>
            <CardContent className="pt-4">
              <p className="text-xs text-gray-500">Active recoveries</p>
              <p className="text-2xl font-semibold">{metrics.active_recovery_count ?? '—'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-xs text-gray-500">Needs refresh</p>
              <p className="text-2xl font-semibold">{metrics.mode_unverified_count ?? unverified.length}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-xs text-gray-500">Pending regeneration</p>
              <p className="text-2xl font-semibold">{metrics.pending_regeneration_count ?? '—'}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <p className="text-xs text-gray-500">Orphaned checkouts</p>
              <p className="text-2xl font-semibold">{metrics.orphaned_checkout_count ?? '—'}</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{SECTION_LABELS.mode_unverified_clients}</CardTitle>
            <CardDescription>Select a client to run guided recovery actions.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 max-h-96 overflow-y-auto">
            {loading && <Loader2 className="w-5 h-5 animate-spin text-gray-400" />}
            {!loading && unverified.length === 0 && (
              <p className="text-sm text-gray-500">No clients currently need billing refresh.</p>
            )}
            {unverified.map((row) => (
              <RecoveryClientRow
                key={row.client_id}
                row={row}
                selected={selectedClientId === row.client_id}
                onSelect={setSelectedClientId}
              />
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recovery actions</CardTitle>
            <CardDescription>
              {selectedClientId ? 'Step-by-step remediation for selected client' : 'Select a client from the list'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {!selectedClientId && (
              <Alert>
                <AlertTriangle className="w-4 h-4" />
                <AlertDescription>Choose a client to see recommended actions and customer-safe messaging.</AlertDescription>
              </Alert>
            )}
            {detailLoading && <Loader2 className="w-5 h-5 animate-spin" />}
            {caseDetail && !detailLoading && (
              <>
                <div className="text-sm space-y-1">
                  <p><strong>Recommended:</strong> {ACTION_LABEL[caseDetail.recommended_action] || caseDetail.recommended_action}</p>
                  <p><strong>Recovery state:</strong> {(caseDetail.recovery_state || '').replace(/_/g, ' ')}</p>
                  <p><strong>Escalation:</strong> {(caseDetail.escalation_state || 'normal').replace(/_/g, ' ')}</p>
                  <p className="text-gray-600 italic">{caseDetail.customer_safe_message}</p>
                </div>
                <div className="flex gap-2 items-center">
                  <User className="w-4 h-4 text-gray-400" />
                  <input
                    className="flex-1 border rounded px-2 py-1 text-sm"
                    placeholder="Assign owner email"
                    value={ownerInput}
                    onChange={(e) => setOwnerInput(e.target.value)}
                  />
                  <Button size="sm" variant="outline" onClick={handleAssign} disabled={actionLoading}>
                    Assign
                  </Button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={handleRegenerate} disabled={actionLoading}>
                    Regenerate checkout
                  </Button>
                  <Button size="sm" variant="outline" onClick={handlePortalRelink} disabled={actionLoading}>
                    Portal relink
                  </Button>
                  <Button size="sm" variant="outline" onClick={handleCloseout} disabled={actionLoading}>
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Closeout
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Bulk-safe operations</CardTitle>
          <CardDescription>Preview batch resend (max 25). Admin-set-mode and entitlement changes are not bulk-enabled.</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" size="sm" onClick={handleBulkPreview} disabled={actionLoading}>
            <Send className="w-4 h-4 mr-1" />
            Preview bulk resend continuation
          </Button>
          {bulkPreview && (
            <pre className="mt-3 text-xs bg-gray-100 p-3 rounded overflow-auto max-h-40">
              {JSON.stringify(bulkPreview, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AdminBillingRecoveryPanel;
