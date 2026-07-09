import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Loader2,
  RefreshCw,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Download,
  Activity,
  GitBranch,
  Clock,
} from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { adminAPI } from '../../api/client';
import { runGovernedAdminMutation } from '../../utils/adminGovernedMutation';
import { useStepUpApi } from '../../hooks/useStepUpApi';
import { formatDisplayValue } from '../../utils/apiErrorMessage';
import { formatAuditTimestampUtc } from '../../utils/adminAuditLabels';

const MIN_REASON = 10;

const HEALTH_STYLES = {
  Healthy: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  'Attention Required': 'bg-amber-50 text-amber-900 border-amber-200',
  Critical: 'bg-red-50 text-red-900 border-red-200',
};

const INDICATOR_STYLES = {
  healthy: 'text-emerald-700',
  warning: 'text-amber-700',
  critical: 'text-red-700',
  unknown: 'text-slate-600',
};

const CHAIN_STYLES = {
  healthy: 'border-emerald-200 bg-emerald-50/50',
  waiting: 'border-amber-200 bg-amber-50/50',
  drift_detected: 'border-orange-200 bg-orange-50/50',
  failed: 'border-red-200 bg-red-50/50',
  unknown: 'border-slate-200 bg-slate-50',
};

function StatusBadge({ ok, label }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        ok ? 'bg-emerald-50 text-emerald-800 border border-emerald-200' : 'bg-slate-100 text-slate-700 border border-slate-200'
      }`}
    >
      {ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
      {label}
    </span>
  );
}

function ActionCard({ title, description, available, blockedReason, onRun, running, testId }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 bg-white" data-testid={testId}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-midnight-blue">{title}</h3>
          <p className="text-xs text-gray-600 mt-1">{description}</p>
          {!available && blockedReason ? (
            <p className="text-xs text-amber-800 mt-2 bg-amber-50 border border-amber-200 rounded px-2 py-1">
              Blocked: {blockedReason}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          disabled={!available || running}
          onClick={onRun}
          className="shrink-0 min-h-9 px-3 py-1.5 rounded-md text-xs font-semibold bg-midnight-blue text-white disabled:opacity-50"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Run'}
        </button>
      </div>
    </div>
  );
}

function Row({ label, value, mirror = false }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-gray-100 last:border-0 text-sm">
      <span className="text-gray-600">
        {label}
        {mirror ? <span className="ml-1 text-[10px] uppercase text-slate-400">mirror</span> : null}
      </span>
      <span className="font-medium text-gray-900 text-right">{formatDisplayValue(value)}</span>
    </div>
  );
}

function CustomerHealthSummary({ health }) {
  if (!health) return null;
  const overall = health.overall || 'Attention Required';
  return (
    <section
      className={`rounded-xl border p-4 ${HEALTH_STYLES[overall] || HEALTH_STYLES['Attention Required']}`}
      data-testid="customer-health-summary"
    >
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-4 h-4" />
        <h2 className="text-sm font-semibold">Customer health: {overall}</h2>
      </div>
      <p className="text-xs mb-3">{health.headline}</p>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
        {Object.entries(health.indicators || {}).map(([key, ind]) => (
          <div key={key} className="rounded-lg border border-black/5 bg-white/60 px-2 py-1.5 text-xs">
            <span className="font-medium capitalize">{key.replace(/_/g, ' ')}</span>
            <span className={`ml-2 font-semibold uppercase ${INDICATOR_STYLES[ind.status] || ''}`}>
              {ind.status}
            </span>
            <p className="text-gray-600 mt-0.5">{ind.explanation}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function AuthorityChainPanel({ chain }) {
  if (!chain?.length) return null;
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="authority-chain">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-midnight-blue" />
        <h2 className="text-sm font-semibold text-midnight-blue">Authority chain</h2>
      </div>
      <div className="space-y-2">
        {chain.map((stage, i) => (
          <div
            key={stage.stage}
            className={`rounded-lg border px-3 py-2 text-xs ${CHAIN_STYLES[stage.status] || CHAIN_STYLES.unknown}`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-midnight-blue">
                {i > 0 ? '↓ ' : ''}
                {stage.stage}
                {stage.mirror ? ' (mirror)' : ''}
              </span>
              <span className="uppercase font-medium">{stage.status?.replace(/_/g, ' ')}</span>
            </div>
            <p className="text-gray-600 mt-1">{stage.authority}</p>
            <p className="text-gray-700 mt-0.5">{stage.explanation}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function OperationalTimeline({ events }) {
  if (!events?.length) return null;
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="operational-timeline">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-midnight-blue" />
        <h2 className="text-sm font-semibold text-midnight-blue">Operational timeline</h2>
      </div>
      <ul className="space-y-2 max-h-80 overflow-y-auto text-xs">
        {events.map((ev, i) => (
          <li key={i} className="border-b border-gray-100 pb-2 last:border-0">
            <div className="flex flex-wrap gap-2 items-baseline">
              <span className="text-gray-500">{formatAuditTimestampUtc(ev.timestamp)}</span>
              <span className="font-medium text-midnight-blue">{ev.title}</span>
              <span className="text-gray-500">· {ev.event_kind}</span>
            </div>
            <div className="text-gray-600 mt-0.5">
              Source: {ev.source} · Authority: {ev.authority} · Result: {formatDisplayValue(ev.result)}
              {ev.duration_ms != null ? ` · ${ev.duration_ms}ms` : ''}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function AdminLifecycleOperationsPanel({ clientId }) {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reason, setReason] = useState('');
  const [runningAction, setRunningAction] = useState('');
  const stepUp = useStepUpApi();

  const load = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError('');
    try {
      const { data } = await adminAPI.getClientLifecycleOperations(clientId);
      setSnapshot(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Failed to load customer operations');
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (actionId, pathSuffix, needsStepUp = false) => {
    const trimmed = reason.trim();
    if (trimmed.length < MIN_REASON) {
      toast.error(`Enter a support reason (${MIN_REASON}+ characters)`);
      return;
    }
    setRunningAction(actionId);
    try {
      const mutate = async (headers) => {
        if (needsStepUp) {
          return stepUp.request((h) =>
            adminAPI.postClientLifecycleOperation(clientId, pathSuffix, { reason: trimmed }, {
              headers: { ...headers, ...h },
            }),
          );
        }
        return runGovernedAdminMutation({
          actionId,
          reason: trimmed,
          resourceKey: clientId,
          mutate: (headers) =>
            adminAPI.postClientLifecycleOperation(clientId, pathSuffix, { reason: trimmed }, { headers }),
        });
      };
      const res = needsStepUp ? await mutate({}) : await mutate();
      toast.success(res.data?.message || 'Action completed');
      await load();
    } catch (e) {
      if (e?.message === 'step_up_cancelled') return;
      const detail = e.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : e.message || 'Action failed');
    } finally {
      setRunningAction('');
    }
  };

  const exportBundle = async () => {
    const trimmed = reason.trim();
    if (trimmed.length < MIN_REASON) {
      toast.error(`Enter a support reason (${MIN_REASON}+ characters)`);
      return;
    }
    setRunningAction('lifecycle_ops_export_support_bundle');
    try {
      const res = await runGovernedAdminMutation({
        actionId: 'lifecycle_ops_export_support_bundle',
        reason: trimmed,
        resourceKey: clientId,
        mutate: (headers) =>
          adminAPI.exportClientSupportBundle(clientId, { reason: trimmed }, { headers }),
      });
      const blob = res.data;
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `support-bundle-${clientId}.zip`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Support bundle downloaded');
    } catch (e) {
      toast.error(e.message || 'Export failed');
    } finally {
      setRunningAction('');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-600 py-8" data-testid="lifecycle-ops-loading">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading customer operations…
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900" data-testid="lifecycle-ops-error">
        {error}
        <button type="button" onClick={load} className="ml-3 underline">
          Retry
        </button>
      </div>
    );
  }

  const lc = snapshot?.lifecycle || {};
  const bill = snapshot?.billing || {};
  const wh = snapshot?.webhook_diagnostics || snapshot?.stripe_webhooks || {};
  const actions = snapshot?.actions || {};
  const diag = snapshot?.runtime_diagnostics || {};
  const bg = snapshot?.background_processing || {};
  const comms = snapshot?.communications || {};

  return (
    <div className="space-y-6" data-testid="admin-lifecycle-operations-panel">
      {stepUp.modal}

      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <Shield className="w-4 h-4 text-midnight-blue" />
          <span className="text-sm font-semibold text-midnight-blue">Customer Operations Centre</span>
          <StatusBadge ok label="Governed" />
        </div>
        <p className="text-xs text-gray-600">
          Extends Lifecycle Operations with health, authority chain, timeline, and diagnostics. Admins cannot
          manually set lifecycle state.
        </p>
        <Link
          to={`/admin/billing?client=${encodeURIComponent(clientId)}`}
          className="text-xs text-electric-teal font-medium hover:underline mt-2 inline-block"
        >
          Billing Centre (plan changes, recovery fleet) →
        </Link>
      </div>

      <CustomerHealthSummary health={snapshot?.customer_health} />
      <AuthorityChainPanel chain={snapshot?.authority_chain} />

      <div className="grid lg:grid-cols-2 gap-4">
        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-midnight-blue mb-3">Lifecycle (authority)</h2>
          <Row label="Lifecycle state" value={lc.lifecycle_state} />
          <Row label="Portal mode" value={lc.portal_mode} />
          <Row label="State reason" value={lc.state_reason} />
          <Row label="Runtime version" value={lc.runtime_version} />
          <Row label="Transition pending" value={lc.transition_pending ? 'Yes' : 'No'} />
        </section>
        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-midnight-blue mb-3">Billing mirror</h2>
          <Row label="Plan" value={bill.plan_code} />
          <Row label="Subscription status" value={bill.subscription_status} mirror />
          <Row label="Reconciliation needed" value={bill.billing_reconciliation_needed ? 'Yes' : 'No'} mirror />
          <Row label="Sync state" value={bill.billing_sync_state} mirror />
          {bill.stale_scheduled_cancellation_mirror ? (
            <p className="text-xs text-amber-800 mt-2 bg-amber-50 border border-amber-200 rounded p-2">
              Stale scheduled-cancellation mirror — run Stripe reconciliation.
            </p>
          ) : null}
        </section>
      </div>

      <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="runtime-diagnostics">
        <h2 className="text-sm font-semibold text-midnight-blue mb-3">Runtime diagnostics</h2>
        <Row label="Runtime version" value={diag.runtime_version} />
        <Row label="Resolved at" value={diag.resolved_at ? formatAuditTimestampUtc(diag.resolved_at) : '—'} />
        <Row label="Cache status" value={diag.runtime_cache?.status} />
        <Row label="Mirror age (min)" value={diag.mirror_freshness?.age_minutes ?? '—'} />
        <Row label="Mirror stale" value={diag.mirror_freshness?.is_stale ? 'Yes' : 'No'} />
        {(diag.legacy_drift?.flags || []).length > 0 ? (
          <p className="text-xs text-amber-800 mt-2 bg-amber-50 border border-amber-200 rounded p-2">
            Drift flags: {(diag.legacy_drift.flags || []).join(', ')}
          </p>
        ) : null}
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="background-processing">
        <h2 className="text-sm font-semibold text-midnight-blue mb-3">Background processing</h2>
        <p className="text-xs text-gray-600 mb-2">{bg.resume_policy}</p>
        <ul className="space-y-1 text-xs">
          {(bg.sampled_job_groups || []).map((j) => (
            <li key={j.job_type} className="flex justify-between gap-2 border-b border-gray-50 py-1">
              <span>{j.job_type}</span>
              <span className="font-medium">{j.decision}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="communications-state">
        <h2 className="text-sm font-semibold text-midnight-blue mb-3">Communications</h2>
        <Row label="Last sent" value={comms.last_sent_at ? formatAuditTimestampUtc(comms.last_sent_at) : '—'} />
        {(comms.suppressed_channels || []).length > 0 ? (
          <p className="text-xs text-amber-800 mt-2">
            Suppressed channels: {comms.suppressed_channels.join(', ')}
          </p>
        ) : null}
        <ul className="mt-2 space-y-1 text-xs">
          {(comms.template_eligibility_samples || []).map((t) => (
            <li key={t.template_key}>
              {t.label}: {t.suppressed ? `suppressed (${t.suppression_reason})` : t.allowed ? 'allowed' : '—'}
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="webhook-diagnostics">
        <h2 className="text-sm font-semibold text-midnight-blue mb-3">Webhook diagnostics</h2>
        <Row label="Overall health" value={wh.overall_health || '—'} />
        <Row label="Last received" value={wh.last_received_at ? formatAuditTimestampUtc(wh.last_received_at) : '—'} />
        <Row label="Failed events" value={wh.failed_event_count} />
        <p className="text-xs text-gray-600 mt-2 bg-slate-50 border border-slate-200 rounded p-2">
          {wh.replay_policy || 'Replay is intentionally unavailable. Use Stripe reconciliation instead.'}
        </p>
      </section>

      <OperationalTimeline events={snapshot?.operational_timeline} />

      <section className="rounded-xl border border-gray-200 bg-white p-4">
        <h2 className="text-sm font-semibold text-midnight-blue mb-3">Support reason (required for actions)</h2>
        <textarea
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm min-h-[72px]"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Document why this governed action is needed (min 10 characters)"
          data-testid="lifecycle-ops-reason"
        />
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-midnight-blue">Governed actions</h2>
          <button type="button" onClick={load} className="text-xs text-gray-600 flex items-center gap-1 hover:text-gray-900">
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <ActionCard
            testId="lifecycle-ops-action-refresh-runtime"
            title="Refresh Runtime Contract"
            description="Invalidate cache and rebuild lifecycle state from authoritative resolver."
            available={actions.refresh_runtime_contract?.available}
            blockedReason={actions.refresh_runtime_contract?.blocked_reason}
            running={runningAction === 'lifecycle_ops_refresh_runtime'}
            onRun={() => runAction('lifecycle_ops_refresh_runtime', 'refresh-runtime-contract')}
          />
          <ActionCard
            testId="lifecycle-ops-action-reconcile"
            title="Reconcile from Stripe"
            description="Pull subscription facts from Stripe and sync billing mirror + lifecycle."
            available={actions.reconcile_from_stripe?.available}
            blockedReason={actions.reconcile_from_stripe?.blocked_reason}
            running={runningAction === 'lifecycle_ops_reconcile_stripe'}
            onRun={() => runAction('lifecycle_ops_reconcile_stripe', 'reconcile-stripe')}
          />
          <ActionCard
            testId="lifecycle-ops-action-resume"
            title="Resume scheduled cancellation"
            description="Undo cancel-at-period-end via Stripe."
            available={actions.resume_scheduled_cancellation?.available}
            blockedReason={actions.resume_scheduled_cancellation?.blocked_reason}
            running={runningAction === 'lifecycle_ops_resume_subscription'}
            onRun={() => runAction('lifecycle_ops_resume_subscription', 'resume-subscription', true)}
          />
          <ActionCard
            testId="lifecycle-ops-action-support-review"
            title="Flag for billing support review"
            description="Record escalation in audit log without changing lifecycle state."
            available={actions.mark_support_review?.available}
            blockedReason={actions.mark_support_review?.blocked_reason}
            running={runningAction === 'lifecycle_ops_mark_support_review'}
            onRun={() => runAction('lifecycle_ops_mark_support_review', 'mark-support-review')}
          />
        </div>
        <button
          type="button"
          data-testid="lifecycle-ops-export-bundle"
          disabled={runningAction === 'lifecycle_ops_export_support_bundle'}
          onClick={exportBundle}
          className="inline-flex items-center gap-2 min-h-9 px-4 py-2 rounded-md text-xs font-semibold border border-midnight-blue text-midnight-blue hover:bg-slate-50 disabled:opacity-50"
        >
          {runningAction === 'lifecycle_ops_export_support_bundle' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Download className="w-4 h-4" />
          )}
          Export support bundle
        </button>
        {actions.regenerate_recovery_checkout?.available ? (
          <p className="text-xs text-gray-600">
            Recovery checkout:{' '}
            <Link to={`/admin/billing?tab=recovery&client=${encodeURIComponent(clientId)}`} className="text-electric-teal underline">
              Billing → Recovery
            </Link>
          </p>
        ) : null}
      </section>

      {snapshot?.lifecycle_audit_timeline?.length > 0 ? (
        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-midnight-blue mb-3">Recent lifecycle audit</h2>
          <ul className="space-y-2 text-xs">
            {snapshot.lifecycle_audit_timeline.map((row, i) => (
              <li key={i} className="border-b border-gray-100 pb-2 last:border-0">
                <span className="text-gray-500">{formatAuditTimestampUtc(row.timestamp)}</span>
                <span className="mx-2 font-medium">{row.metadata?.action_type || row.action}</span>
                {row.metadata?.reason ? <span className="text-gray-600">— {row.metadata.reason}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
