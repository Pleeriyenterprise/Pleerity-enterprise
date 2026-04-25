import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
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

const SectionCard = ({ title, children, actions = null, subdued = false }) => (
  <section
    className={`rounded-xl p-4 ${
      subdued
        ? 'bg-slate-50/90 text-slate-800'
        : 'bg-white border border-gray-200 shadow-sm'
    }`}
  >
    <div className={`flex items-center justify-between ${subdued ? 'mb-2' : 'mb-3'}`}>
      <h2 className={`font-semibold text-midnight-blue ${subdued ? 'text-xs uppercase tracking-wide text-slate-600' : 'text-sm'}`}>
        {title}
      </h2>
      {actions}
    </div>
    {children}
  </section>
);

const Row = ({ label, value }) => (
  <div className="flex items-center justify-between gap-4 py-2 border-b border-gray-100/80 last:border-0">
    <span className="text-sm text-gray-600">{label}</span>
    <span className="text-sm font-medium text-gray-900 text-right">{value ?? '—'}</span>
  </div>
);

const MIN_VALID_DATE_MS = 946684800000;

const fmtDate = (value) => {
  if (value == null || value === '') return 'Not yet recorded';
  const t = new Date(value).getTime();
  if (Number.isNaN(t) || t < MIN_VALID_DATE_MS) return 'Not yet recorded';
  return new Date(value).toLocaleString('en-GB');
};

function CollapsibleBlock({ title, subtitle, defaultOpen = false, children, className = '' }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={`rounded-xl bg-white border border-gray-200/90 shadow-sm ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50/80 rounded-xl transition-colors"
        aria-expanded={open}
      >
        <div>
          <div className="text-sm font-semibold text-midnight-blue">{title}</div>
          {subtitle ? <div className="text-xs text-gray-500 mt-0.5">{subtitle}</div> : null}
        </div>
        <ChevronDown className={`h-5 w-5 shrink-0 text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open ? <div className="px-4 pb-4 pt-0 border-t border-gray-100">{children}</div> : null}
    </div>
  );
}

function deriveComplianceHeadline(compliance) {
  const risk = String(compliance?.risk_level || '').trim().toUpperCase();
  const overdue = Number(compliance?.overdue_items) || 0;
  const missing = Number(compliance?.missing_documents) || 0;
  const score = compliance?.compliance_score;
  const scoreNum = typeof score === 'number' ? score : score != null ? Number(score) : null;

  if (overdue > 0 || risk.includes('CRITICAL') || risk === 'HIGH' || risk === 'SEVERE') {
    return {
      label: 'CRITICAL',
      hint: 'Immediate portfolio attention recommended.',
      palette: 'border-red-200 bg-gradient-to-br from-red-50 to-white text-red-950',
      badge: 'bg-red-600 text-white',
    };
  }
  if (
    missing > 0 ||
    risk === 'MEDIUM' ||
    risk === 'WARNING' ||
    risk === 'ELEVATED' ||
    risk === 'MODERATE' ||
    (scoreNum != null && !Number.isNaN(scoreNum) && scoreNum < 60)
  ) {
    return {
      label: 'AT RISK',
      hint: 'Gaps or exposure need follow-up.',
      palette: 'border-amber-200 bg-gradient-to-br from-amber-50/90 to-white text-amber-950',
      badge: 'bg-amber-500 text-white',
    };
  }
  return {
    label: 'GOOD',
    hint: 'No urgent compliance flags from this snapshot.',
    palette: 'border-emerald-200 bg-gradient-to-br from-emerald-50/80 to-white text-emerald-950',
    badge: 'bg-emerald-600 text-white',
  };
}

function nextRequiredActionText(compliance, operationalSnapshot) {
  const overdue = Number(compliance?.overdue_items) || 0;
  const missing = Number(compliance?.missing_documents) || 0;
  if (overdue > 0) {
    return `Resolve ${overdue} overdue requirement${overdue === 1 ? '' : 's'}`;
  }
  if (missing > 0) {
    return `Follow up on ${missing} missing document${missing === 1 ? '' : 's'}`;
  }
  const oc = operationalSnapshot?.onboarding_checklist;
  if (oc && !oc.unavailable) {
    const step = oc.next_step?.label || oc.next_step?.id;
    if (step) return `Onboarding next step: ${step}`;
  }
  return null;
}

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
    label: 'Password link status',
    actionTypes: ['password_link_status'],
    auditActions: [],
    expectedEffect: 'Checks if an active setup token exists and whether it is still valid.',
  },
  {
    key: 'new_password_link',
    label: 'New password link',
    actionTypes: ['new_password_link'],
    auditActions: ['PASSWORD_SETUP_LINK_RESENT'],
    expectedEffect: 'Creates a new setup token and invalidates older links to reduce account recovery risk.',
  },
  {
    key: 'recalculate_compliance',
    label: 'Update compliance status',
    actionTypes: ['recalculate_compliance'],
    auditActions: ['ADMIN_ACTION'],
    expectedEffect: 'Queues compliance recalculation for the client portfolio and refreshes score/risk outputs.',
  },
  {
    key: 'run_client_job',
    label: 'Run system update',
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
    label: 'View as user',
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
  const [activeTab, setActiveTab] = useState('overview');
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

  const complianceHeadline = useMemo(() => {
    const co = data?.compliance_overview || {};
    return deriveComplianceHeadline(co);
  }, [data]);

  const nextActionLine = useMemo(() => {
    const co = data?.compliance_overview || {};
    const snap = data?.operational_snapshot || {};
    return nextRequiredActionText(co, snap);
  }, [data]);

  const tabNav = (
    <div className="flex flex-wrap gap-1 border-b border-gray-200/90 pb-px -mb-px">
      {[
        { id: 'overview', label: 'Overview' },
        { id: 'compliance', label: 'Compliance' },
        { id: 'operations', label: 'Operations' },
        { id: 'billing', label: 'Billing' },
        { id: 'activity', label: 'Activity & Audit' },
      ].map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => setActiveTab(t.id)}
          className={`px-3 py-2.5 text-sm font-medium rounded-t-lg border border-b-0 transition-colors ${
            activeTab === t.id
              ? 'bg-white text-midnight-blue border-gray-200 relative z-10 shadow-[0_-1px_0_0_white]'
              : 'bg-transparent text-gray-500 border-transparent hover:text-gray-800 hover:bg-slate-50/80'
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );

  const statusSummaryCard = !loading && data && (
    <div className={`rounded-2xl border-2 p-5 shadow-md ${complianceHeadline.palette}`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-gray-600/90">Compliance status</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <span className={`inline-flex items-center rounded-lg px-3 py-1 text-lg font-bold tracking-tight ${complianceHeadline.badge}`}>
              {complianceHeadline.label}
            </span>
            <span className="text-sm text-gray-700 max-w-xl">{complianceHeadline.hint}</span>
          </div>
        </div>
        <div className="text-right text-sm space-y-1 min-w-[10rem]">
          <div>
            <span className="text-gray-500">Risk level</span>
            <div className="font-semibold text-gray-900">{compliance.risk_level || 'Not yet recorded'}</div>
          </div>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-black/5 pt-4">
        <div>
          <div className="text-xs text-gray-600">Missing documents</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{compliance.missing_documents ?? '—'}</div>
        </div>
        <div>
          <div className="text-xs text-gray-600">Overdue items</div>
          <div className="text-2xl font-bold text-gray-900 tabular-nums">{compliance.overdue_items ?? '—'}</div>
        </div>
        <div className="col-span-2 sm:col-span-2">
          <div className="text-xs text-gray-600">Next suggested action</div>
          <div className="text-sm font-medium text-gray-900 leading-snug mt-0.5">
            {nextActionLine || 'No queued action from this snapshot — monitor as usual.'}
          </div>
        </div>
      </div>
    </div>
  );

  const primaryActionsBlock = !loading && data && (
    <div className="rounded-xl bg-white border border-gray-200 p-4 space-y-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Actions</p>
      <div>
        <p className="text-xs text-gray-500 mb-2">Primary</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={() => runAction('Update compliance status', () => adminAPI.recalculateCompliance(clientId))}
            className="px-4 py-2.5 text-sm font-semibold rounded-lg bg-midnight-blue text-white shadow-sm hover:opacity-95 disabled:opacity-50"
          >
            Update compliance status
          </button>
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={() => runAction('Run system update', () => adminAPI.runClientJob(clientId))}
            className="px-4 py-2.5 text-sm font-semibold rounded-lg bg-teal-700 text-white shadow-sm hover:opacity-95 disabled:opacity-50"
          >
            Run system update
          </button>
        </div>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-2">Secondary</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={() => runAction('Resend activation email', () => adminAPI.resendActivationEmail(clientId))}
            className="px-3 py-2 text-sm rounded-lg bg-gray-100 text-gray-900 border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
          >
            Resend activation email
          </button>
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={() => runAction('Resend dashboard email', () => adminAPI.resendDashboardEmail(clientId))}
            className="px-3 py-2 text-sm rounded-lg bg-gray-100 text-gray-900 border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
          >
            Resend dashboard email
          </button>
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={checkPasswordLinkStatus}
            className="px-3 py-2 text-sm rounded-lg bg-white text-gray-800 border border-gray-300 hover:bg-slate-50 disabled:opacity-50"
            title="Check whether a valid token exists (raw link only if server returns it)"
          >
            Password link status
          </button>
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={generatePasswordSetupLink}
            className="px-3 py-2 text-sm rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50"
            title="Creates a new token and link; requires your password"
          >
            New password link
          </button>
        </div>
      </div>
      <div className="pt-3 border-t border-dashed border-amber-200/80">
        <p className="text-xs text-amber-900/80 mb-2">Sensitive — extra care</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={() => runAction('Unlock account', () => adminAPI.unlockClientAccount(clientId))}
            className="px-3 py-2 text-sm rounded-lg bg-amber-50 text-amber-950 border border-amber-300 hover:bg-amber-100 disabled:opacity-50"
          >
            Unlock account
          </button>
          <button
            type="button"
            disabled={isBusy || loading}
            onClick={startImpersonation}
            className="px-3 py-2 text-sm rounded-lg bg-indigo-50 text-indigo-950 border border-indigo-300 hover:bg-indigo-100 disabled:opacity-50"
          >
            View as user
          </button>
        </div>
      </div>
    </div>
  );

  const identityAccountCard = !loading && data && (
    <SectionCard title="Identity & account">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">Identity</p>
          <Row label="Name" value={identity.name} />
          <Row label="CRN" value={identity.crn} />
          <Row label="Email" value={identity.email} />
          <Row label="Phone" value={identity.phone} />
          <Row label="Plan" value={identity.plan} />
          <Row label="Subscription status" value={identity.status} />
        </div>
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1">Account</p>
          <Row label="Password set" value={account.password_set ? 'Yes' : 'No'} />
          <Row label="Last login" value={fmtDate(account.last_login)} />
          <Row label="Onboarding stage" value={account.onboarding_stage} />
          <Row label="Activation email sent" value={account.activation_email_sent ? 'Yes' : 'No'} />
          <Row label="Dashboard ready sent" value={account.dashboard_ready_sent ? 'Yes' : 'No'} />
          {billing.canonical_entitlement_state ? (
            <Row label="Entitlement (billing)" value={billing.canonical_entitlement_state} />
          ) : null}
        </div>
      </div>
    </SectionCard>
  );

  const overviewMetricsCollapsible = !loading && data && (
    <CollapsibleBlock
      title="Compliance & operations snapshot"
      subtitle="Lightweight counts — open tabs below for depth."
      defaultOpen={false}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-lg bg-slate-50/80 p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Compliance</p>
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-900">{compliance.properties_count ?? '—'}</span> properties · score{' '}
            <span className="font-medium">{compliance.compliance_score ?? '—'}</span>
          </p>
        </div>
        <div className="rounded-lg bg-slate-50/80 p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Operations</p>
          <p className="text-sm text-gray-700">
            <span className="font-medium text-gray-900">{ops.issues ?? '—'}</span> issues ·{' '}
            <span className="font-medium text-gray-900">{ops.work_orders ?? '—'}</span> jobs ·{' '}
            <span className="font-medium text-gray-900">{ops.contractors ?? '—'}</span> contractors
          </p>
        </div>
      </div>
    </CollapsibleBlock>
  );

  const overviewProgressCollapsible = !loading && data && (
    <CollapsibleBlock title="Client progress & comms" subtitle="Onboarding and broadcast delivery (audit lives under Activity & Audit)." defaultOpen={false}>
      {operationalSnapshot.onboarding_checklist?.unavailable ? (
        <p className="text-sm text-amber-800">Onboarding checklist unavailable.</p>
      ) : (
        <div className="space-y-2 text-sm border-b border-gray-100 pb-3 mb-3">
          <div className="font-medium text-gray-900">Onboarding</div>
          <Row label="Status" value={operationalSnapshot.onboarding_checklist?.onboarding_status ?? '—'} />
          <Row label="Phase" value={operationalSnapshot.onboarding_checklist?.phase_status ?? '—'} />
          <Row
            label="Progress"
            value={
              (() => {
                const p = operationalSnapshot.onboarding_checklist?.progress;
                if (p == null) return '—';
                if (typeof p === 'object') {
                  return `${p.completed ?? 0}/${p.total ?? 0} (${p.percent ?? 0}%)`;
                }
                return `${p}%`;
              })()
            }
          />
          <Row
            label="Next step"
            value={
              operationalSnapshot.onboarding_checklist?.next_step?.label ||
              operationalSnapshot.onboarding_checklist?.next_step?.id ||
              '—'
            }
          />
          <Row label="Completed at" value={fmtDate(operationalSnapshot.onboarding_checklist?.completed_at)} />
        </div>
      )}
      <div className="space-y-2 text-sm">
        <div className="font-medium text-gray-900">Digest & broadcasts</div>
        <Row label="Last monthly digest sent" value={fmtDate(operationalSnapshot.last_monthly_digest?.sent_at)} />
        <Row label="Last broadcast delivery" value={fmtDate(operationalSnapshot.last_broadcast_delivery?.created_at)} />
        <Row label="Email status (last)" value={operationalSnapshot.last_broadcast_delivery?.email_status || '—'} />
        <Row label="In-app status (last)" value={operationalSnapshot.last_broadcast_delivery?.in_app_status || '—'} />
      </div>
    </CollapsibleBlock>
  );

  const complianceTab = !loading && data && (
    <div className="space-y-4 max-w-4xl">
      <SectionCard title="Compliance overview">
        <Row label="Properties count" value={compliance.properties_count} />
        <Row label="Compliance score" value={compliance.compliance_score ?? '—'} />
        <Row label="Risk level" value={compliance.risk_level || 'Not yet recorded'} />
        <Row label="Missing documents" value={compliance.missing_documents} />
        <Row label="Overdue items" value={compliance.overdue_items} />
      </SectionCard>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SectionCard title="What's wrong" subdued>
          <ul className="text-sm text-gray-700 space-y-2 list-disc pl-4">
            {(Number(compliance.overdue_items) || 0) > 0 ? (
              <li>
                <span className="font-medium text-gray-900">{compliance.overdue_items}</span> requirement
                {Number(compliance.overdue_items) === 1 ? ' is' : 's are'} overdue — client may be out of SLA on
                evidence or sign-off.
              </li>
            ) : (
              <li>No overdue requirements in this snapshot.</li>
            )}
            {(Number(compliance.missing_documents) || 0) > 0 ? (
              <li>
                <span className="font-medium text-gray-900">{compliance.missing_documents}</span> required document
                {Number(compliance.missing_documents) === 1 ? ' is' : 's are'} still pending upload or review.
              </li>
            ) : (
              <li>No pending “missing document” count reported.</li>
            )}
            {compliance.risk_level ? (
              <li>
                Modelled risk level: <span className="font-medium">{compliance.risk_level}</span>
                {compliance.compliance_score != null ? ` (score ${compliance.compliance_score})` : ''}.
              </li>
            ) : (
              <li>Risk level not yet recorded — run “Update compliance status” from Overview if needed.</li>
            )}
          </ul>
        </SectionCard>
        <SectionCard title="What needs action" subdued>
          <ul className="text-sm text-gray-700 space-y-2 list-disc pl-4">
            {(Number(compliance.overdue_items) || 0) > 0 ? (
              <li>Prioritise clearing overdue items before other hygiene work.</li>
            ) : null}
            {(Number(compliance.missing_documents) || 0) > 0 ? (
              <li>Chase missing documents or confirm exemptions with the client.</li>
            ) : null}
            {!compliance.risk_level && compliance.compliance_score == null ? (
              <li>Trigger a fresh compliance calculation if this client was recently onboarded or data changed.</li>
            ) : null}
            {(Number(compliance.overdue_items) || 0) === 0 &&
            (Number(compliance.missing_documents) || 0) === 0 &&
            (compliance.risk_level || compliance.compliance_score != null) ? (
              <li>No automatic follow-ups from counts alone — keep routine monitoring.</li>
            ) : null}
          </ul>
        </SectionCard>
      </div>
    </div>
  );

  const operationsTab = !loading && data && (
    <div className="space-y-4 max-w-4xl">
      <SectionCard title="Operations">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <div className="text-3xl font-bold text-midnight-blue tabular-nums">{ops.issues ?? '—'}</div>
            <div className="text-xs font-medium text-gray-600 uppercase tracking-wide mt-1">Issues</div>
            <Link className="text-xs text-electric-teal hover:underline mt-2 inline-block" to="/admin/ops/risk">
              Open risk & insights
            </Link>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <div className="text-3xl font-bold text-midnight-blue tabular-nums">{ops.work_orders ?? '—'}</div>
            <div className="text-xs font-medium text-gray-600 uppercase tracking-wide mt-1">Jobs</div>
            <Link className="text-xs text-electric-teal hover:underline mt-2 inline-block" to="/admin/ops/maintenance">
              Open jobs board
            </Link>
          </div>
          <div className="rounded-xl bg-slate-50 p-4 text-center">
            <div className="text-3xl font-bold text-midnight-blue tabular-nums">{ops.contractors ?? '—'}</div>
            <div className="text-xs font-medium text-gray-600 uppercase tracking-wide mt-1">Contractors</div>
            <Link className="text-xs text-electric-teal hover:underline mt-2 inline-block" to="/admin/ops/contractors">
              Open contractors
            </Link>
          </div>
        </div>
        <p className="text-xs text-gray-500">
          <Link className="text-electric-teal font-medium hover:underline" to="/admin/ops">
            Operations home
          </Link>{' '}
          — full queues and assignments live here (not filtered to this client in the UI).
        </p>
      </SectionCard>
    </div>
  );

  const billingTab = !loading && data && (
    <div className="space-y-4 max-w-4xl">
      <SectionCard title="Billing & subscription">
        <Row label="Plan" value={billing.plan} />
        <Row label="Subscription status" value={billing.status} />
        {billing.canonical_entitlement_state ? (
          <Row label="Entitlement state" value={billing.canonical_entitlement_state} />
        ) : null}
        <Row label="Last payment" value={fmtDate(billing.last_payment)} />
        <Row label="Next billing date" value={fmtDate(billing.next_billing_date)} />
        {billing.open_invoice_status ? <Row label="Open invoice status" value={billing.open_invoice_status} /> : null}
        {billing.stripe_next_payment_attempt_at ? (
          <Row label="Next payment attempt (Stripe)" value={fmtDate(billing.stripe_next_payment_attempt_at)} />
        ) : null}
      </SectionCard>
      <CollapsibleBlock
        title="Payment history & receipts"
        subtitle={`${receiptRows.length} in view (total ${receiptsMeta.total ?? receiptRows.length})`}
        defaultOpen={false}
      >
        <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
          {receiptRows.slice(0, 12).map((r) => (
            <div key={r.receipt_key} className="flex items-center justify-between text-sm border border-gray-100 rounded-lg p-2 gap-2">
              <div className="min-w-0">
                <div className="font-medium truncate">{r.invoice_number || r.order_reference || r.receipt_key}</div>
                <div className="text-xs text-gray-600">
                  {r.amount_display || '—'} / {fmtDate(r.date_issued)}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
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
                  type="button"
                  className="text-xs text-gray-700 hover:underline"
                  onClick={() =>
                    runAction('Resend receipt', () =>
                      adminAPI.resendClientReceipt(clientId, {
                        source: r.source,
                        ref: r.source === 'subscription' ? (r.invoice_number || r.stripe_checkout_session_id) : r.order_id,
                      })
                    )
                  }
                >
                  Resend
                </button>
              </div>
            </div>
          ))}
        </div>
      </CollapsibleBlock>
    </div>
  );

  const activityAuditTab = !loading && data && (
    <div className="space-y-4 max-w-4xl">
      <p className="text-xs text-gray-500">
        Support visibility: expand a section when you need depth. Nothing here runs actions by itself.
      </p>
      <CollapsibleBlock title="Activity timeline" subtitle="Payments, logins, and recent system actions." defaultOpen={false}>
        <div className="max-h-72 overflow-y-auto mt-2">
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
      </CollapsibleBlock>
      <CollapsibleBlock title="Risk signals (from this client payload)" subtitle="Derived from billing + compliance fields already loaded." defaultOpen={false}>
        <div className="mt-2 space-y-2 text-sm">
          <Row label="Compliance headline" value={complianceHeadline.label} />
          <Row label="Risk level" value={compliance.risk_level || 'Not yet recorded'} />
          <Row label="Compliance score" value={compliance.compliance_score ?? '—'} />
          <Row label="Entitlement (billing)" value={billing.canonical_entitlement_state || '—'} />
          <Row label="Subscription status" value={billing.status || identity.status || '—'} />
        </div>
      </CollapsibleBlock>
      <CollapsibleBlock title="Command centre task activity" subtitle="Client portal Tasks inbox (read-only)." defaultOpen={false}>
        <div className="max-h-60 overflow-y-auto mt-2">
          {taskActivityLoading ? (
            <div className="text-sm text-gray-500">Loading…</div>
          ) : !taskActivity?.length ? (
            <div className="text-sm text-gray-500">No recorded inbox activity.</div>
          ) : (
            taskActivity.map((row) => (
              <div key={row.event_id || `${row.task_id}-${row.created_at}`} className="py-2 border-b border-gray-100 last:border-0 text-sm">
                <div className="text-xs text-gray-500">{fmtDate(row.created_at)}</div>
                <div className="text-gray-900">{formatTaskActivityLine(row)}</div>
                {row.task_id && (
                  <div className="text-xs text-gray-400 font-mono mt-0.5 truncate" title={row.task_id}>
                    {row.task_id}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </CollapsibleBlock>
      <CollapsibleBlock title="Action history" subtitle="Last known runs for control-panel actions." defaultOpen={false}>
        <div className="max-h-72 overflow-y-auto mt-2">
          {actionHealthRows.map((row) => (
            <div key={row.key} className="py-2 border-b border-gray-100 last:border-0 flex items-center justify-between gap-4">
              <div>
                <div className="text-sm text-gray-900">{row.label}</div>
                <div className="text-xs text-gray-600">{row.expectedEffect}</div>
                <div className="text-xs text-gray-500">
                  {row.lastRunAt ? `Last run: ${fmtDate(row.lastRunAt)}` : 'No recent run recorded'}
                </div>
              </div>
              <div className="text-right shrink-0">
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
      </CollapsibleBlock>
      <CollapsibleBlock title="Recent audit (sample)" subtitle="Short window from the same payload as the control panel." defaultOpen={false}>
        <div className="max-h-56 overflow-y-auto mt-2 space-y-2 text-sm">
          {!(operationalSnapshot.recent_audit_highlights || []).length ? (
            <p className="text-gray-500 text-xs">No audit rows in sample window.</p>
          ) : (
            operationalSnapshot.recent_audit_highlights.map((ev, idx) => (
              <div key={`${ev.action}-${idx}`} className="border-b border-gray-50 pb-2 last:border-0">
                <div className="text-xs text-gray-500">{fmtDate(ev.timestamp)}</div>
                <div className="text-gray-900 font-mono text-xs">{ev.action || '—'}</div>
                {ev.metadata_preview && Object.keys(ev.metadata_preview).length > 0 && (
                  <pre className="text-[10px] text-gray-600 mt-1 whitespace-pre-wrap break-words max-h-16 overflow-hidden">
                    {JSON.stringify(ev.metadata_preview)}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>
      </CollapsibleBlock>
    </div>
  );

  const tabBody = () => {
    if (loading || !data) return null;
    if (activeTab === 'overview') {
      return (
        <div className="space-y-4 max-w-5xl">
          {statusSummaryCard}
          {primaryActionsBlock}
          {identityAccountCard}
          {overviewMetricsCollapsible}
          {overviewProgressCollapsible}
        </div>
      );
    }
    if (activeTab === 'compliance') return complianceTab;
    if (activeTab === 'operations') return operationsTab;
    if (activeTab === 'billing') return billingTab;
    if (activeTab === 'activity') return activityAuditTab;
    return null;
  };

  return (
    <UnifiedAdminLayout>
      <div className="space-y-4">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-midnight-blue">Client Control Panel</h1>
            {!loading && data?.identity ? <AccountEnvironmentBadge doc={data.identity} showLiveBadge /> : null}
          </div>
          <p className="text-sm text-gray-600 max-w-3xl">
            One place for identity, billing, compliance, and operations. Use tabs to focus; nothing here changes backend
            behaviour.
          </p>
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
          <div className="bg-white/60 rounded-xl border border-gray-200/80 p-1 sm:p-2">
            <div className="px-2 pt-2">{tabNav}</div>
            <div className="p-3 sm:p-4 bg-white rounded-b-xl min-h-[12rem]">{tabBody()}</div>
          </div>
        )}
      </div>
      {stepUp.modal}
    </UnifiedAdminLayout>
  );
};

export default AdminClientControlPanelPage;
