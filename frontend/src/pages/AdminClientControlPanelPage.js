import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { adminAPI, API_URL } from '../api/client';
import { useAuth } from '../contexts/AuthContext';

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

const fmtDate = (value) => {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
};

const AdminClientControlPanelPage = () => {
  const { clientId } = useParams();
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [isBusy, setIsBusy] = useState(false);
  const [taskActivity, setTaskActivity] = useState(null);
  const [taskActivityLoading, setTaskActivityLoading] = useState(false);

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

  const identity = data?.identity || {};
  const account = data?.account_state || {};
  const billing = data?.subscription_billing || {};
  const compliance = data?.compliance_overview || {};
  const ops = data?.operations || {};

  const runAction = async (label, call) => {
    setIsBusy(true);
    try {
      const res = await call();
      toast.success(res?.data?.message || `${label} completed`);
      await loadPanel();
    } catch (err) {
      const msg = err?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : `${label} failed`);
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

  const buildReceiptDownloadUrl = (receipt) => {
    if (!clientId || !receipt) return null;
    const base = API_URL ? `${API_URL}/api` : '/api';
    if (receipt.source === 'subscription') {
      const ref = encodeURIComponent(receipt.invoice_number || receipt.stripe_checkout_session_id || '');
      return ref ? `${base}/admin/billing/clients/${clientId}/receipts/subscription/${ref}/download` : null;
    }
    const orderId = receipt.order_id;
    return orderId ? `${base}/admin/billing/clients/${clientId}/receipts/order/${encodeURIComponent(orderId)}/download` : null;
  };

  return (
    <UnifiedAdminLayout>
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">Client Control Panel</h1>
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

            <SectionCard title="Subscription & Billing">
              <Row label="Plan" value={billing.plan} />
              <Row label="Status" value={billing.status} />
              <Row label="Last payment" value={fmtDate(billing.last_payment)} />
              <Row label="Next billing date" value={fmtDate(billing.next_billing_date)} />
              <Row label="Receipts" value={`${receiptRows.length} (total ${receiptsMeta.total || receiptRows.length})`} />
              <div className="mt-3 space-y-2 max-h-52 overflow-y-auto">
                {receiptRows.slice(0, 12).map((r) => {
                  const url = buildReceiptDownloadUrl(r);
                  return (
                    <div key={r.receipt_key} className="flex items-center justify-between text-sm border border-gray-100 rounded p-2">
                      <div className="min-w-0">
                        <div className="font-medium truncate">{r.invoice_number || r.order_reference || r.receipt_key}</div>
                        <div className="text-xs text-gray-600">{r.amount_display || '-'} / {fmtDate(r.date_issued)}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        {url ? (
                          <a className="text-xs text-electric-teal hover:underline" href={url} target="_blank" rel="noreferrer">
                            Download
                          </a>
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
                  );
                })}
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
              <Row label="Work orders" value={ops.work_orders} />
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
    </UnifiedAdminLayout>
  );
};

export default AdminClientControlPanelPage;

