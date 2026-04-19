import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from '@/utils/portalNotifications';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import AccountEnvironmentBadge from '../components/admin/AccountEnvironmentBadge';
import {
  clientOrgPermanentDeleteHint,
  isNonProductionAccount,
  NON_PRODUCTION_ACCOUNT_LABEL,
  PRODUCTION_ACCOUNT_LABEL,
} from '../utils/adminAccountClassification';
import api, { adminAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useStepUpApi } from '../hooks/useStepUpApi';

const SectionCard = ({ title, children, actions = null }) => (
  <section className="bg-white border border-gray-200 rounded-xl p-4">
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-semibold text-midnight-blue">{title}</h2>
      {actions}
    </div>
    {children}
  </section>
);

const Row = ({ label, value }) => (
  <div className="flex items-center justify-between gap-4 py-2 border-b border-gray-100 last:border-0">
    <span className="text-sm text-gray-600">{label}</span>
    <span className="text-sm font-medium text-gray-900 text-right">{value ?? '-'}</span>
  </div>
);

const MIN_VALID_DATE_MS = 946684800000;

const fmtDate = (value) => {
  if (value == null || value === '') return 'Not available';
  const t = new Date(value).getTime();
  if (Number.isNaN(t) || t < MIN_VALID_DATE_MS) return 'Not available';
  return new Date(value).toLocaleString('en-GB');
};

const ACTION_HEALTH_DEFS = [
  {
    key: 'resend_activation_email',
    label: 'Resend activation email',
    actionTypes: ['resend_activation_email'],
    auditActions: ['PASSWORD_SETUP_LINK_RESENT', 'ACTIVATION_EMAIL_RESEND'],
    expectedEffect: 'Sends a fresh password setup email so the client can complete portal activation.',
  },
  {
    key: 'resend_dashboard_email',
    label: 'Resend dashboard email',
    actionTypes: ['resend_dashboard_email'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Resends dashboard-ready access guidance after password setup is complete.',
  },
  {
    key: 'password_link_status',
    label: 'Password link status check',
    actionTypes: ['password_link_status'],
    auditActions: [],
    expectedEffect: 'Checks if an active setup token exists and whether it is still valid.',
  },
  {
    key: 'new_password_link',
    label: 'Generate new password link',
    actionTypes: ['new_password_link'],
    auditActions: ['PASSWORD_SETUP_LINK_RESENT'],
    expectedEffect: 'Creates a new setup token and invalidates older links to reduce account recovery risk.',
  },
  {
    key: 'recalculate_compliance',
    label: 'Recalculate compliance',
    actionTypes: ['recalculate_compliance'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Queues compliance recalculation for the client portfolio and refreshes score/risk outputs.',
  },
  {
    key: 'run_client_job',
    label: 'Run client job',
    actionTypes: ['run_client_job', 'recalculate_compliance'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Runs the approved scoped job for this client (currently compliance recalculation).',
  },
  {
    key: 'unlock_account',
    label: 'Unlock account',
    actionTypes: ['unlock_account'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Sets client portal users back to ACTIVE and invalidates old sessions via session version bump.',
  },
  {
    key: 'impersonation_start',
    label: 'View as user (impersonation)',
    actionTypes: ['impersonation_start'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Starts a time-limited audited user session for support troubleshooting.',
  },
];

const formatTaskActivityLine = (row) => {
  const action = String(row?.action || '').toUpperCase();
  const source = row?.source || row?.task_source || 'task';
  if (action === 'SNOOZE') return `Snoozed ${source}`;
  if (action === 'DISMISS') return `Dismissed ${source}`;
  if (action === 'DONE') return `Marked ${source} as done`;
  if (action === 'RESTORE') return `Restored ${source}`;
  return row?.summary || row?.description || action || 'Task inbox activity';
};

const AdminClientControlPanelPage = () => {
  const { clientId } = useParams();
  const { user } = useAuth();
  const stepUp = useStepUpApi();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [taskActivity, setTaskActivity] = useState(null);
  const [taskActivityLoading, setTaskActivityLoading] = useState(false);
  const [lastActionRunAt, setLastActionRunAt] = useState({});

  const loadPanel = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    try {
      const res = await adminAPI.getClientControlPanel(clientId);
      setData(res.data || null);
    } catch (err) {
      const msg = err?.response?.data?.detail || 'Failed to load client control panel';
      toast.error(typeof msg === 'string' ? msg : 'Failed to load client control panel');
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    loadPanel();
  }, [loadPanel]);

  const loadTaskActivity = useCallback(async () => {
    if (!clientId) return;
    setTaskActivityLoading(true);
    try {
      const res = await adminAPI.getClientCommandCentreTaskActivity(clientId, { limit: 50 });
      setTaskActivity(res.data?.items || []);
    } catch (err) {
      setTaskActivity([]);
      const msg = err?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Failed to load command centre task activity');
    } finally {
      setTaskActivityLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    loadTaskActivity();
  }, [loadTaskActivity]);

  const identity = data?.identity || {};
  const account = data?.account_state || {};
  const billing = data?.subscription_billing || {};
  const compliance = data?.compliance_overview || {};
  const ops = data?.operations || {};
  const operationalSnapshot = data?.operational_snapshot || {};

  const runAction = async (label, call) => {
    setIsBusy(true);
    try {
      const res = await call();
      toast.success(res?.data?.message || `${label} completed`);
      setLastActionRunAt((prev) => ({ ...prev, [label]: new Date().toISOString() }));
      await loadPanel();
      await loadTaskActivity();
    } catch (err) {
      const msg = err?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : `${label} failed`);
    } finally {
      setIsBusy(false);
    }
  };

  const checkPasswordLinkStatus = async () => {
    if (!clientId) return;
    setIsBusy(true);
    try {
      const res = await adminAPI.getPasswordSetupLink(clientId, false);
      const d = res.data || {};
      if (d.setup_link) {
        try {
          await navigator.clipboard.writeText(d.setup_link);
          toast.success('Link copied to clipboard');
        } catch {
          toast.success(d.message || 'Link ready');
        }
        return;
      }
      toast.info(d.message || 'Token status', {
        description: d.note || (d.token_exists ? `Expires: ${d.expires_at || '—'}` : 'No link returned'),
      });
    } catch (err) {
      const msg = err?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Failed to load password link status');
    } finally {
      setIsBusy(false);
    }
  };

  const generatePasswordSetupLink = async () => {
    if (!clientId) return;
    setIsBusy(true);
    try {
      const res = await stepUp.request((headers) =>
        adminAPI.getPasswordSetupLink(clientId, true, { headers }),
      );
      const link = res?.data?.setup_link;
      if (link) {
        try {
          await navigator.clipboard.writeText(link);
          toast.success('New password setup link copied to clipboard');
        } catch {
          toast.success(link, { duration: 12000 });
        }
      } else {
        toast.error('No link in response');
      }
      await loadPanel();
    } catch (err) {
      if (err?.message === 'step_up_cancelled') {
        /* user closed modal */
      } else {
        const msg = err?.response?.data?.detail;
        toast.error(typeof msg === 'string' ? msg : 'Failed to generate password link');
      }
    } finally {
      setIsBusy(false);
    }
  };

  const startImpersonation = async () => {
    if (!clientId) return;
    setIsBusy(true);
    try {
      const currentToken = localStorage.getItem('auth_token');
      const currentUser = localStorage.getItem('user');
      if (!currentToken || !currentUser) {
        toast.error('Current admin session unavailable');
        setIsBusy(false);
        return;
      }
      sessionStorage.setItem('impersonation_admin_token', currentToken);
      sessionStorage.setItem('impersonation_admin_user', currentUser);

      const res = await adminAPI.startClientImpersonation(clientId, 30);
      const newToken = res?.data?.access_token;
      const newUser = res?.data?.user;
      if (!newToken || !newUser) {
        throw new Error('Invalid impersonation response');
      }
      localStorage.setItem('auth_token', newToken);
      localStorage.setItem('user', JSON.stringify(newUser));
      localStorage.setItem(
        'impersonation_context',
        JSON.stringify({
          active: true,
          client_id: clientId,
          client_name: res?.data?.client?.name || identity.name || null,
          started_at: new Date().toISOString(),
          expires_at: res?.data?.expires_at || null,
          admin_portal_user_id: user?.portal_user_id || null,
        })
      );
      window.location.href = '/dashboard';
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Unable to start impersonation';
      toast.error(typeof msg === 'string' ? msg : 'Unable to start impersonation');
    } finally {
      setIsBusy(false);
    }
  };

  const receiptRows = billing?.receipts || [];
  const receiptsMeta = billing?.receipts_meta || {};
  const activityRows = useMemo(() => {
    const timeline = data?.activity_timeline || {};
    const rows = [];
    (timeline.payments || []).forEach((p) => rows.push({
      type: 'payment',
      at: p.created_at,
      text: `${p.status || 'PAYMENT'} ${p.amount ? `(${p.amount})` : ''}`.trim(),
    }));
    (timeline.login_events || []).forEach((e) => rows.push({
      type: 'login',
      at: e.timestamp,
      text: e.action || 'LOGIN_EVENT',
    }));
    (timeline.system_actions || []).forEach((e) => rows.push({
      type: 'system',
      at: e.timestamp,
      text: e.action || 'SYSTEM_ACTION',
    }));
    return rows
      .sort((a, b) => new Date(b.at || 0).getTime() - new Date(a.at || 0).getTime())
      .slice(0, 30);
  }, [data]);

  const actionHealthRows = useMemo(() => {
    const systemActions = data?.activity_timeline?.system_actions || [];
    const byActionType = {};
    systemActions.forEach((row) => {
      const actionType = row?.metadata?.action_type;
      if (actionType && (!byActionType[actionType] || new Date(row.timestamp).getTime() > new Date(byActionType[actionType].timestamp).getTime())) {
        byActionType[actionType] = row;
      }
    });
    return ACTION_HEALTH_DEFS.map((def) => {
      const fromAudit = (def.actionTypes || [])
        .map((k) => byActionType[k])
        .filter(Boolean)
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())[0];
      const localAt = lastActionRunAt[def.label];
      const effectiveTime = fromAudit?.timestamp || localAt || null;
      const outcome = fromAudit?.metadata?.outcome || (effectiveTime ? 'success' : null);
      return {
        key: def.key,
        label: def.label,
        expectedEffect: def.expectedEffect,
        lastRunAt: effectiveTime,
        outcome: outcome || 'not_run',
      };
    });
  }, [data, lastActionRunAt]);

  const handleReceiptDownload = async (r) => {
    if (!clientId || !r?.pdf_available) return;
    try {
      let path;
      if (r.source === 'subscription') {
        const ref = encodeURIComponent(r.invoice_number || r.stripe_checkout_session_id || '');
        if (!ref) {
          toast.error('Missing receipt reference');
          return;
        }
        path = `/admin/billing/clients/${clientId}/receipts/subscription/${ref}/download`;
      } else {
        const oid = (r.order_id || '').trim();
        if (!oid) {
          toast.error('Missing order id');
          return;
        }
        path = `/admin/billing/clients/${clientId}/receipts/order/${encodeURIComponent(oid)}/download`;
      }
      const response = await api.get(path, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${r.invoice_number || r.order_reference || r.order_id || 'receipt'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Receipt downloaded');
    } catch (err) {
      const msg = err?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Download failed');
    }
  };

  return (
    <UnifiedAdminLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold text-midnight-blue">Client Control Panel</h1>
              {!loading && data?.identity ? <AccountEnvironmentBadge doc={data.identity} showLiveBadge /> : null}
            </div>
            <p className="text-sm text-gray-600">
              Unified client state, billing, compliance, operations, and controlled actions.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              disabled={isBusy || loading}
              onClick={() => runAction('Resend activation email', () => adminAPI.resendActivationEmail(clientId))}
              className="px-3 py-2 text-sm rounded-lg bg-midnight-blue text-white disabled:opacity-50"
            >
              Resend activation email
            </button>
            <button
              disabled={isBusy || loading}
              onClick={() => runAction('Resend dashboard email', () => adminAPI.resendDashboardEmail(clientId))}
              className="px-3 py-2 text-sm rounded-lg bg-gray-800 text-white disabled:opacity-50"
            >
              Resend dashboard email
            </button>
            <button
              type="button"
              disabled={isBusy || loading}
              onClick={checkPasswordLinkStatus}
              className="px-3 py-2 text-sm rounded-lg bg-gray-100 text-gray-900 border border-gray-300 disabled:opacity-50"
              title="Check whether a valid token exists (raw link only if server returns it)"
            >
              Password link status
            </button>
            <button
              type="button"
              disabled={isBusy || loading}
              onClick={generatePasswordSetupLink}
              className="px-3 py-2 text-sm rounded-lg bg-teal-700 text-white disabled:opacity-50"
              title="Creates a new token and link; requires your password"
            >
              New password link
            </button>
            <button
              disabled={isBusy || loading}
              onClick={() => runAction('Recalculate compliance', () => adminAPI.recalculateCompliance(clientId))}
              className="px-3 py-2 text-sm rounded-lg bg-gray-100 text-gray-900 border border-gray-300 disabled:opacity-50"
            >
              Recalculate compliance
            </button>
            <button
              disabled={isBusy || loading}
              onClick={() => runAction('Run client job', () => adminAPI.runClientJob(clientId))}
              className="px-3 py-2 text-sm rounded-lg bg-gray-100 text-gray-900 border border-gray-300 disabled:opacity-50"
            >
              Run client job
            </button>
            <button
              disabled={isBusy || loading}
              onClick={() => runAction('Unlock account', () => adminAPI.unlockClientAccount(clientId))}
              className="px-3 py-2 text-sm rounded-lg bg-amber-100 text-amber-900 border border-amber-300 disabled:opacity-50"
            >
              Unlock account
            </button>
            <button
              disabled={isBusy || loading}
              onClick={startImpersonation}
              className="px-3 py-2 text-sm rounded-lg bg-indigo-100 text-indigo-900 border border-indigo-300 disabled:opacity-50"
            >
              View as user
            </button>
          </div>
        </div>

        {!loading && data?.identity ? (
          <div
            className={`rounded-lg border p-4 text-sm ${
              isNonProductionAccount(data.identity)
                ? 'border-fuchsia-400 bg-fuchsia-50/90 text-fuchsia-950'
                : 'border-slate-200 bg-slate-50 text-slate-900'
            }`}
          >
            <p className="font-semibold text-base">
              {isNonProductionAccount(data.identity) ? NON_PRODUCTION_ACCOUNT_LABEL : PRODUCTION_ACCOUNT_LABEL}
            </p>
            <p className="mt-1 text-gray-700">{clientOrgPermanentDeleteHint(isNonProductionAccount(data.identity))}</p>
          </div>
        ) : null}

        {loading ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-gray-600">Loading control panel...</div>
        ) : !data ? (
          <div className="bg-white border border-red-200 rounded-xl p-6 text-red-700">Client not found or unavailable.</div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <SectionCard title="Identity">
              <Row label="Name" value={identity.name} />
              <Row label="CRN" value={identity.crn} />
              <Row label="Email" value={identity.email} />
              <Row label="Phone" value={identity.phone} />
              <Row label="Plan" value={identity.plan} />
              <Row label="Status" value={identity.status} />
            </SectionCard>

            <SectionCard title="Account State">
              <Row label="Password set" value={account.password_set ? 'Yes' : 'No'} />
              <Row label="Last login" value={fmtDate(account.last_login)} />
              <Row label="Onboarding stage" value={account.onboarding_stage} />
              <Row label="Activation email sent" value={account.activation_email_sent ? 'Yes' : 'No'} />
              <Row label="Dashboard ready sent" value={account.dashboard_ready_sent ? 'Yes' : 'No'} />
            </SectionCard>

            <SectionCard title="Operational snapshot">
              <p className="text-xs text-gray-500 mb-3">
                Onboarding progress, last monthly digest, latest admin broadcast delivery, and recent audit highlights for instant client state.
              </p>
              {operationalSnapshot.onboarding_checklist?.unavailable ? (
                <p className="text-sm text-amber-800">Onboarding checklist unavailable.</p>
              ) : (
                <div className="space-y-2 text-sm border-b border-gray-100 pb-3 mb-3">
                  <div className="font-medium text-gray-900">Onboarding</div>
                  <Row label="Status" value={operationalSnapshot.onboarding_checklist?.onboarding_status ?? '-'} />
                  <Row label="Phase" value={operationalSnapshot.onboarding_checklist?.phase_status ?? '-'} />
                  <Row
                    label="Progress"
                    value={
                      (() => {
                        const p = operationalSnapshot.onboarding_checklist?.progress;
                        if (p == null) return '-';
                        if (typeof p === 'object') {
                          return `${p.completed ?? 0}/${p.total ?? 0} (${p.percent ?? 0}%)`;
                        }
                        return `${p}%`;
                      })()
                    }
                  />
                  <Row label="Next step" value={operationalSnapshot.onboarding_checklist?.next_step?.label || operationalSnapshot.onboarding_checklist?.next_step?.id || '-'} />
                  <Row label="Completed at" value={fmtDate(operationalSnapshot.onboarding_checklist?.completed_at)} />
                </div>
              )}
              <div className="space-y-2 text-sm border-b border-gray-100 pb-3 mb-3">
                <div className="font-medium text-gray-900">Digest & broadcasts</div>
                <Row label="Last monthly digest sent" value={fmtDate(operationalSnapshot.last_monthly_digest?.sent_at)} />
                <Row label="Last broadcast delivery" value={fmtDate(operationalSnapshot.last_broadcast_delivery?.created_at)} />
                <Row label="Email status (last)" value={operationalSnapshot.last_broadcast_delivery?.email_status || '-'} />
                <Row label="In-app status (last)" value={operationalSnapshot.last_broadcast_delivery?.in_app_status || '-'} />
              </div>
              <div className="text-sm">
                <div className="font-medium text-gray-900 mb-2">Recent audit (sample)</div>
                <div className="max-h-48 overflow-y-auto space-y-2">
                  {!(operationalSnapshot.recent_audit_highlights || []).length ? (
                    <p className="text-gray-500 text-xs">No audit rows in sample window.</p>
                  ) : (
                    operationalSnapshot.recent_audit_highlights.map((ev, idx) => (
                      <div key={`${ev.action}-${idx}`} className="border-b border-gray-50 pb-2 last:border-0">
                        <div className="text-xs text-gray-500">{fmtDate(ev.timestamp)}</div>
                        <div className="text-gray-900 font-mono text-xs">{ev.action || '—'}</div>
                        {ev.metadata_preview && Object.keys(ev.metadata_preview).length > 0 && (
                          <pre className="text-[10px] text-gray-600 mt-1 whitespace-pre-wrap break-words max-h-20 overflow-hidden">
                            {JSON.stringify(ev.metadata_preview)}
                          </pre>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </SectionCard>

            <SectionCard title="Subscription & Billing">
              <Row label="Plan" value={billing.plan} />
              <Row label="Status" value={billing.status} />
              <Row label="Last payment" value={fmtDate(billing.last_payment)} />
              <Row label="Next billing date" value={fmtDate(billing.next_billing_date)} />
              <Row label="Receipts" value={`${receiptRows.length} (total ${receiptsMeta.total || receiptRows.length})`} />
              <div className="mt-3 space-y-2 max-h-52 overflow-y-auto">
                {receiptRows.slice(0, 12).map((r) => (
                    <div key={r.receipt_key} className="flex items-center justify-between text-sm border border-gray-100 rounded p-2">
                      <div className="min-w-0">
                        <div className="font-medium truncate">{r.invoice_number || r.order_reference || r.receipt_key}</div>
                        <div className="text-xs text-gray-600">{r.amount_display || '-'} / {fmtDate(r.date_issued)}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {r.pdf_available ? (
                          <button
                            type="button"
                            className="text-xs text-electric-teal hover:underline"
                            onClick={() => handleReceiptDownload(r)}
                          >
                            Download
                          </button>
                        ) : (
                          <span className="text-xs text-gray-400">No PDF</span>
                        )}
                        <button
                          className="text-xs text-gray-700 hover:underline"
                          onClick={() =>
                            runAction('Resend receipt', () =>
                              adminAPI.resendClientReceipt(clientId, { source: r.source, ref: r.source === 'subscription' ? (r.invoice_number || r.stripe_checkout_session_id) : r.order_id })
                            )
                          }
                        >
                          Resend
                        </button>
                      </div>
                    </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Compliance Overview">
              <Row label="Properties count" value={compliance.properties_count} />
              <Row label="Compliance score" value={compliance.compliance_score ?? '-'} />
              <Row label="Risk level" value={compliance.risk_level || '-'} />
              <Row label="Missing documents" value={compliance.missing_documents} />
              <Row label="Overdue items" value={compliance.overdue_items} />
            </SectionCard>

            <SectionCard title="Operations">
              <Row label="Issues" value={ops.issues} />
              <Row label="Jobs" value={ops.work_orders} />
              <Row label="Contractors" value={ops.contractors} />
              <div className="pt-2 text-xs text-gray-500">
                <Link className="text-electric-teal hover:underline" to="/admin/ops">Open Operations Dashboard</Link>
              </div>
            </SectionCard>

            <SectionCard title="Command Centre task activity (read-only)">
              <p className="text-xs text-gray-500 mb-2">Client portal Tasks inbox actions (snooze, dismiss, done, restore). For support visibility only.</p>
              <div className="max-h-60 overflow-y-auto">
                {taskActivityLoading ? (
                  <div className="text-sm text-gray-500">Loading…</div>
                ) : !taskActivity?.length ? (
                  <div className="text-sm text-gray-500">No recorded inbox activity.</div>
                ) : (
                  taskActivity.map((row) => (
                    <div key={row.event_id || `${row.task_id}-${row.created_at}`} className="py-2 border-b border-gray-100 last:border-0 text-sm">
                      <div className="text-xs text-gray-500">{fmtDate(row.created_at)}</div>
                      <div className="text-gray-900">{formatTaskActivityLine(row)}</div>
                      {row.task_id && <div className="text-xs text-gray-400 font-mono mt-0.5 truncate" title={row.task_id}>{row.task_id}</div>}
                    </div>
                  ))
                )}
              </div>
            </SectionCard>

            <SectionCard title="Action health">
              <p className="text-xs text-gray-500 mb-2">Latest verified execution status for client control actions.</p>
              <div className="max-h-72 overflow-y-auto">
                {actionHealthRows.map((row) => (
                  <div key={row.key} className="py-2 border-b border-gray-100 last:border-0 flex items-center justify-between gap-4">
                    <div>
                      <div className="text-sm text-gray-900">{row.label}</div>
                      <div className="text-xs text-gray-600">{row.expectedEffect}</div>
                      <div className="text-xs text-gray-500">{row.lastRunAt ? `Last run: ${fmtDate(row.lastRunAt)}` : 'Not run yet'}</div>
                    </div>
                    <div className="text-right">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded text-xs ${
                          row.outcome === 'success' || row.outcome === 'sent' || row.outcome === 'duplicate_ignored'
                            ? 'bg-green-100 text-green-800'
                            : row.outcome === 'not_run'
                              ? 'bg-gray-100 text-gray-700'
                              : 'bg-amber-100 text-amber-800'
                        }`}
                      >
                        {row.outcome === 'not_run' ? 'Not run' : String(row.outcome).replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Activity Timeline">
              <div className="max-h-72 overflow-y-auto">
                {activityRows.length === 0 ? (
                  <div className="text-sm text-gray-500">No activity found.</div>
                ) : (
                  activityRows.map((ev, idx) => (
                    <div key={`${ev.type}-${idx}`} className="py-2 border-b border-gray-100 last:border-0">
                      <div className="text-xs text-gray-500">{fmtDate(ev.at)}</div>
                      <div className="text-sm text-gray-900">{ev.text}</div>
                    </div>
                  ))
                )}
              </div>
            </SectionCard>
          </div>
        )}
      </div>
      {stepUp.modal}
    </UnifiedAdminLayout>
  );
};

export default AdminClientControlPanelPage;

