/**
 * Client portal — Today (priorities inbox). Aggregated server-side tasks with sections,
 * urgency, deep links, and selective inline actions (risk → issue / work order).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { inboxTitleForDisplay } from '../domain/presentDomain';
import { useNavigate, Link } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Loader2, LayoutList, Info, ExternalLink, Bell, EyeOff, CheckCircle, RotateCcw, History } from 'lucide-react';
import { toast } from 'sonner';
import { UrgencyRow } from '../components/client/UrgencyDisplay';

const FILTER_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'operations', label: 'Operations' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'risks', label: 'Risks' },
  { id: 'overdue', label: 'Overdue' },
];

function formatMoney(amount, currency = 'GBP') {
  if (amount == null || Number.isNaN(Number(amount))) return '\u2014';
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency: currency || 'GBP' }).format(Number(amount));
}

function formatWhen(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return null;
  }
}

function sourceTypeLabel(st) {
  const map = {
    requirement: 'Compliance',
    risk_signal: 'Risk',
    work_order: 'Work order',
    approval: 'Approval',
    issue: 'Issue',
    priority_action: 'Action',
  };
  return map[st] || st || 'Task';
}

function actionLabel(act) {
  const m = { snooze: 'Snoozed', dismiss: 'Dismissed', done: 'Marked done', restore: 'Restored' };
  return m[act] || act || '—';
}

function TaskCard({
  task,
  navigate,
  onRiskAction,
  riskLoading,
  showRiskInline,
  onTaskOverride,
  overrideBusy,
}) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const meta = task.metadata || {};
  const sid = meta.related_risk_signal_id;
  const busy = overrideBusy === task.id;
  const displayTitle = inboxTitleForDisplay(task);
  const hasLongContext = Boolean(task.why_matters || task.recommended_action);

  return (
    <Card className="border border-gray-200 shadow-sm overflow-hidden">
      <CardContent className="p-4 client-portal-prose">
        <div className="flex flex-col gap-4 min-w-0">
          <div className="min-w-0 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="text-xs font-normal shrink-0">
                {sourceTypeLabel(task.source_type)}
              </Badge>
              <UrgencyRow urgencyLevel={task.urgency_level} timingLabel={meta.timing_label} />
            </div>
            <h3 className="font-semibold text-midnight-blue text-base leading-snug break-words">{displayTitle}</h3>
            {task.property_label && (
              <p className="text-sm text-gray-600 break-words">{task.property_label}</p>
            )}
            {task.description && (
              <p className="text-sm text-gray-700 line-clamp-3 break-words">{task.description}</p>
            )}
            {hasLongContext && (
              <button
                type="button"
                className="text-left text-xs font-medium text-electric-teal hover:underline py-1 min-h-[44px] sm:min-h-0 flex items-center"
                onClick={() => setDetailsOpen((o) => !o)}
                aria-expanded={detailsOpen}
              >
                {detailsOpen ? 'Hide details' : 'Why this matters & next steps'}
              </button>
            )}
            {detailsOpen && hasLongContext && (
              <div className="rounded-lg bg-gray-50 border border-gray-100 p-3 text-xs text-gray-600 space-y-2 break-words">
                {task.why_matters && (
                  <p>
                    <span className="font-medium text-gray-800">Why it matters:</span> {task.why_matters}
                  </p>
                )}
                {task.recommended_action && (
                  <p>
                    <span className="font-medium text-gray-800">Recommended:</span> {task.recommended_action}
                  </p>
                )}
              </div>
            )}
            {task.freshness_timestamp && (
              <p className="text-xs text-gray-400">Updated {formatWhen(task.freshness_timestamp)}</p>
            )}
          </div>

          <div className="flex flex-col gap-3 pt-2 border-t border-gray-100 min-w-0">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <Button
                type="button"
                variant="outline"
                className="h-11 text-xs justify-center"
                disabled={busy}
                title="Hide for 1 day"
                onClick={() => onTaskOverride('snooze', task, 1)}
              >
                <Bell className="w-3.5 h-3.5 mr-1 shrink-0" />
                1 day
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-11 text-xs justify-center"
                disabled={busy}
                title="Hide for 7 days"
                onClick={() => onTaskOverride('snooze', task, 7)}
              >
                7 days
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-11 text-xs justify-center"
                disabled={busy}
                title="Hide until you restore (does not fix underlying compliance or work)"
                onClick={() => onTaskOverride('dismiss', task)}
              >
                <EyeOff className="w-3.5 h-3.5 mr-1 shrink-0" />
                Dismiss
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-11 text-xs justify-center"
                disabled={busy}
                title="Mark handled in your inbox (does not close work orders or approvals)"
                onClick={() => onTaskOverride('done', task)}
              >
                <CheckCircle className="w-3.5 h-3.5 mr-1 shrink-0" />
                Done
              </Button>
            </div>
            <Button
              className="w-full min-h-11 h-11 text-sm justify-center bg-midnight-blue hover:bg-midnight-blue/90"
              onClick={() => navigate(task.primary_action_url || '/dashboard')}
            >
              {task.primary_action_label || 'Open'}
            </Button>
            {showRiskInline && task.primary_action_type === 'risk_follow_up' && sid && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  className="min-h-11 h-11 w-full justify-center"
                  disabled={riskLoading === `issue:${sid}`}
                  onClick={() => onRiskAction('issue', sid)}
                >
                  {riskLoading === `issue:${sid}` ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create issue'}
                </Button>
                <Button
                  variant="outline"
                  className="min-h-11 h-11 w-full justify-center"
                  disabled={riskLoading === `wo:${sid}`}
                  onClick={() => onRiskAction('work_order', sid)}
                >
                  {riskLoading === `wo:${sid}` ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create work order'}
                </Button>
              </div>
            )}
            {busy && (
              <div className="flex justify-center py-1">
                <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
              </div>
            )}
            {task.secondary_action_url && task.secondary_action_label && (
              <Button
                variant="ghost"
                className="w-full min-h-11 h-11 text-electric-teal justify-center"
                onClick={() => navigate(task.secondary_action_url)}
              >
                {task.secondary_action_label}
                <ExternalLink className="w-3.5 h-3.5 ml-1 shrink-0" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HiddenTaskCard({ item, onRestore, busy }) {
  const kind = item.user_override === 'dismiss' ? 'Dismissed' : 'Marked done';
  return (
    <Card className="border border-gray-200 bg-gray-50/60 shadow-sm">
      <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <Badge variant="outline" className="text-xs mb-1">{kind}</Badge>
          <p className="font-medium text-midnight-blue text-sm">{item.title || item.task_id}</p>
          <p className="text-xs text-gray-500 mt-1">Hidden {formatWhen(item.hidden_at) || '—'}</p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(item)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Restore
        </Button>
      </CardContent>
    </Card>
  );
}

function SnoozedTaskCard({ task, onRestore, busy }) {
  return (
    <Card className="border border-amber-200 bg-amber-50/40 shadow-sm">
      <CardContent className="p-4 flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="font-medium text-midnight-blue text-sm">{task.title}</p>
          {task.property_label && <p className="text-xs text-gray-600">{task.property_label}</p>}
          <p className="text-xs text-amber-900 mt-1">
            Snoozed until {formatWhen(task.snoozed_until) || task.snoozed_until || '—'}
          </p>
        </div>
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onRestore(task)}>
          <RotateCcw className="w-3 h-3 mr-1" />
          Restore
        </Button>
      </CardContent>
    </Card>
  );
}

function SectionBlock({
  title,
  tasks,
  navigate,
  onRiskAction,
  riskLoading,
  showRiskInline,
  onTaskOverride,
  overrideBusy,
  emptyHint,
}) {
  if (!tasks?.length) {
    return (
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">{title}</h2>
        <p className="text-sm text-gray-500">{emptyHint}</p>
      </div>
    );
  }
  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">{title}</h2>
      <div className="space-y-3">
        {tasks.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            navigate={navigate}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onTaskOverride={onTaskOverride}
            overrideBusy={overrideBusy}
          />
        ))}
      </div>
    </div>
  );
}

export default function ClientTasksPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);
  const [filter, setFilter] = useState('all');
  const [riskLoading, setRiskLoading] = useState(null);
  const [overrideBusyId, setOverrideBusyId] = useState(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [propertyFilter, setPropertyFilter] = useState('');
  const [propertyOptions, setPropertyOptions] = useState([]);

  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  useEffect(() => {
    if (!isClientUser) return;
    clientAPI
      .getComplianceSummary()
      .then((res) => setPropertyOptions(res.data?.properties || []))
      .catch(() => setPropertyOptions([]));
  }, [isClientUser]);

  useEffect(() => {
    if (!isClientUser || typeof sessionStorage === 'undefined') return;
    if (sessionStorage.getItem('pleerity_today_opened')) return;
    sessionStorage.setItem('pleerity_today_opened', '1');
    clientAPI.postAnalyticsEvent({ event: 'today_opened', path: '/today' }).catch(() => {});
  }, [isClientUser]);

  const load = useCallback(() => {
    if (!isClientUser) return;
    setLoading(true);
    setError('');
    const params = propertyFilter ? { property_id: propertyFilter } : {};
    clientAPI
      .getTasks(params)
      .then((res) => setPayload(res.data))
      .catch((err) => {
        setError(err?.response?.data?.detail || 'Failed to load tasks');
        setPayload(null);
      })
      .finally(() => setLoading(false));
  }, [isClientUser, propertyFilter]);

  useEffect(() => {
    load();
  }, [load]);

  // Keep Today inbox aligned with real-time Action -> Outcome events.
  useEffect(() => {
    if (!isClientUser) return undefined;
    const onOutcome = (evt) => {
      const outcomePropertyId = evt?.detail?.property_id;
      if (propertyFilter && outcomePropertyId && outcomePropertyId !== propertyFilter) return;
      load();
    };
    window.addEventListener('compliance-outcome', onOutcome);
    return () => window.removeEventListener('compliance-outcome', onOutcome);
  }, [isClientUser, propertyFilter, load]);

  const filterTask = useCallback(
    (t) => {
      if (filter === 'all') return true;
      const tags = t.filter_tags || [];
      if (filter === 'overdue') return (t.overdue_days ?? 0) > 0 || tags.includes('overdue');
      if (filter === 'compliance') return tags.includes('compliance');
      if (filter === 'operations') return tags.includes('operations');
      if (filter === 'approvals') return tags.includes('approvals');
      if (filter === 'risks') return tags.includes('risks');
      return true;
    },
    [filter]
  );

  const applyFilter = (list) => (list || []).filter(filterTask);

  const sections = payload?.tasks || {};
  const urgent = applyFilter(sections.urgent);
  const upcoming = applyFilter(sections.upcoming);
  const inProgress = applyFilter(sections.in_progress);
  const recent = applyFilter(sections.recently_completed);
  const snoozed = applyFilter(sections.snoozed || []);
  const hidden = sections.hidden || [];

  const summary = payload?.summary;
  const freshness = payload?.freshness;
  const spend = payload?.spend_this_month;

  const spendDisplay = useMemo(() => {
    if (!hasFeature('invoicing')) return null;
    if (!spend || spend.has_any_invoices === false) return null;
    return {
      amount: formatMoney(spend.total_amount, spend.currency),
      hint: spend.calculation_summary,
      count: spend.invoice_count,
    };
  }, [spend, hasFeature]);

  const showRiskInline = hasFeature('predictive_maintenance') && hasFeature('maintenance_workflows');

  const onTaskOverride = async (action, task, snoozeDays) => {
    const tid = task?.id || task?.task_id;
    if (!tid) return;
    setOverrideBusyId(tid);
    try {
      await clientAPI.postTaskOverride({
        task_id: tid,
        action,
        snooze_days: snoozeDays,
        title: task.title,
        source_type: task.source_type,
        property_id: task.property_id,
      });
      const labels = {
        snooze: snoozeDays ? `Snoozed ${snoozeDays} day${snoozeDays !== 1 ? 's' : ''}` : 'Snoozed',
        dismiss: 'Hidden (dismissed)',
        done: 'Marked done in inbox',
        restore: 'Restored to inbox',
      };
      toast.success(labels[action] || 'Updated');
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Could not update task');
    } finally {
      setOverrideBusyId(null);
    }
  };

  const onRiskAction = async (kind, signalId) => {
    if (!signalId) return;
    const key = `${kind}:${signalId}`;
    setRiskLoading(key);
    try {
      if (kind === 'issue') {
        await clientAPI.createIssueFromRiskSignal(signalId, {});
        toast.success('Issue created from risk signal');
        navigate('/operations/issues');
      } else {
        await clientAPI.createWorkOrderFromRiskSignal(signalId, {});
        toast.success('Work order created from risk signal');
        navigate('/operations/work-orders');
      }
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Action failed');
    } finally {
      setRiskLoading(null);
    }
  };

  if (!isClientUser) {
    return (
      <div className="p-6">
        <p className="text-gray-600">Today is available to client users only.</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto" data-testid="client-tasks-page">
      <div className="mb-6">
        <div className="flex items-center gap-2 text-midnight-blue mb-1">
          <LayoutList className="w-7 h-7" />
          <h1 className="text-2xl md:text-3xl font-bold">Today</h1>
        </div>
        <p className="text-gray-600 text-sm md:text-base">
          Your open priorities across compliance, maintenance, approvals, and risk—ranked for you.
        </p>
        <p className="text-xs text-gray-500 mt-2">
          <Link
            to="/help?article=command-centre-tasks-inbox"
            className="text-electric-teal hover:underline font-medium"
          >
            How Snooze, Dismiss, and Done work
          </Link>
          <span className="text-gray-400"> — inbox actions do not replace real approvals or compliance updates.</span>
        </p>
      </div>

      {summary?.habit &&
        (summary.habit.urgent_open_total > 0 ||
          summary.habit.items_due_or_expiring_in_7_days > 0 ||
          (summary.habit.tasks_acknowledged_last_7_days ?? 0) > 0) && (
        <Alert className="mb-4 border-teal-200 bg-teal-50/80">
          <Info className="h-4 w-4 text-teal-700" />
          <AlertDescription className="text-teal-900 text-sm">
            {summary.habit.urgent_open_total > 0 && (
              <span className="block">
                You have <strong>{summary.habit.urgent_open_total}</strong> urgent item
                {summary.habit.urgent_open_total !== 1 ? 's' : ''} right now.
              </span>
            )}
            {summary.habit.items_due_or_expiring_in_7_days > 0 && (
              <span className="block mt-1">
                <strong>{summary.habit.items_due_or_expiring_in_7_days}</strong> open item
                {summary.habit.items_due_or_expiring_in_7_days !== 1 ? 's' : ''} with a due date in the next 7 days.
              </span>
            )}
            {(summary.habit.tasks_acknowledged_last_7_days ?? 0) > 0 && (
              <span className="block mt-1 text-teal-800">
                This week you cleared or dismissed <strong>{summary.habit.tasks_acknowledged_last_7_days}</strong> inbox item
                {summary.habit.tasks_acknowledged_last_7_days !== 1 ? 's' : ''} (Done/Dismiss).
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-6 border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Summary</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-gray-500">Urgent</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.urgent_count ?? 0}</p>
          </div>
          <div>
            <span className="text-gray-500">Upcoming</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.upcoming_count ?? 0}</p>
          </div>
          <div>
            <span className="text-gray-500">In progress</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.in_progress_count ?? 0}</p>
          </div>
          <div title="Tasks you snoozed; they return after the snooze date">
            <span className="text-gray-500">Snoozed</span>
            <p className="text-xl font-semibold text-midnight-blue">{summary?.snoozed_count ?? 0}</p>
          </div>
          {spendDisplay && (
            <div className="min-w-[10rem]" title={spendDisplay.hint}>
              <span className="text-gray-500">This month&apos;s spend (paid invoices)</span>
              <p className="text-xl font-semibold text-midnight-blue">{spendDisplay.amount}</p>
              <p className="text-xs text-gray-500 mt-0.5">{spend.invoice_count ?? 0} paid invoice(s) this month · UTC month</p>
            </div>
          )}
          <div className="w-full text-xs text-gray-500 space-y-1 mt-2 border-t border-gray-100 pt-3">
            {freshness?.score_updated_at && (
              <p>Compliance score updated: {formatWhen(freshness.score_updated_at)}</p>
            )}
            {freshness?.risk_signals_updated_at && (
              <p>Risk signals updated: {formatWhen(freshness.risk_signals_updated_at)}</p>
            )}
            {freshness?.last_automation_score_recalc_at && (
              <p>Last automated score recalc: {formatWhen(freshness.last_automation_score_recalc_at)}</p>
            )}
            {freshness?.last_automation_risk_refresh_at && (
              <p>Last automated risk refresh: {formatWhen(freshness.last_automation_risk_refresh_at)}</p>
            )}
            {freshness?.tasks_refreshed_at && <p>Tasks refreshed: {formatWhen(freshness.tasks_refreshed_at)}</p>}
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between mb-6">
        <div className="flex flex-wrap gap-2">
          {FILTER_CHIPS.map((c) => (
            <Button
              key={c.id}
              type="button"
              size="sm"
              variant={filter === c.id ? 'default' : 'outline'}
              className={`min-h-11 px-3 ${filter === c.id ? 'bg-midnight-blue' : ''}`}
              onClick={() => setFilter(c.id)}
            >
              {c.label}
            </Button>
          ))}
        </div>
        {propertyOptions.length > 0 && (
          <div className="flex flex-col gap-1 text-sm w-full sm:w-auto sm:min-w-[14rem]">
            <label htmlFor="tasks-property-filter" className="text-gray-600">
              Property
            </label>
            <select
              id="tasks-property-filter"
              value={propertyFilter}
              onChange={(e) => setPropertyFilter(e.target.value)}
              className="border border-gray-200 rounded-lg px-3 py-2.5 text-sm bg-white w-full max-w-full min-h-11"
            >
              <option value="">All properties</option>
              {propertyOptions.map((p) => (
                <option key={p.property_id} value={p.property_id}>
                  {p.nickname || p.name || p.address_line_1 || p.property_id}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 className="w-10 h-10 animate-spin text-electric-teal" />
        </div>
      )}

      {!loading && !error && (
        <>
          <SectionBlock
            title="Urgent"
            tasks={urgent}
            navigate={navigate}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onTaskOverride={onTaskOverride}
            overrideBusy={overrideBusyId}
            emptyHint="Nothing in the urgent queue. Good standing, or try another filter."
          />
          <SectionBlock
            title="Upcoming"
            tasks={upcoming}
            navigate={navigate}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onTaskOverride={onTaskOverride}
            overrideBusy={overrideBusyId}
            emptyHint="No upcoming items in this view."
          />
          <SectionBlock
            title="In progress"
            tasks={inProgress}
            navigate={navigate}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onTaskOverride={onTaskOverride}
            overrideBusy={overrideBusyId}
            emptyHint="No in-progress items here — pending approvals and open issues appear in this section."
          />
          {snoozed.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Snoozed</h2>
              <p className="text-sm text-gray-500 mb-3">
                These stay out of your open lists until the date shown. Restore anytime to bring them back.
              </p>
              <div className="space-y-3">
                {snoozed.map((t) => (
                  <SnoozedTaskCard
                    key={t.id}
                    task={t}
                    busy={overrideBusyId === t.id}
                    onRestore={(tk) => onTaskOverride('restore', tk)}
                  />
                ))}
              </div>
            </div>
          )}
          {hidden.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">Hidden (dismiss or done)</h2>
              <p className="text-sm text-gray-500 mb-3">
                You removed these from open lists. Underlying work or compliance is unchanged — restore when you want them visible again.
              </p>
              <div className="space-y-3">
                {hidden.map((h) => (
                  <HiddenTaskCard
                    key={h.task_id}
                    item={h}
                    busy={overrideBusyId === h.task_id}
                    onRestore={(it) =>
                      onTaskOverride('restore', {
                        id: it.task_id,
                        title: it.title,
                        source_type: it.source_type,
                        property_id: it.property_id,
                      })
                    }
                  />
                ))}
              </div>
            </div>
          )}
          <SectionBlock
            title="Recently completed"
            tasks={recent}
            navigate={navigate}
            onRiskAction={onRiskAction}
            riskLoading={riskLoading}
            showRiskInline={showRiskInline}
            onTaskOverride={onTaskOverride}
            overrideBusy={overrideBusyId}
            emptyHint="Recent requirement and invoice milestones will show here."
          />
          {payload?.activity_feed?.length > 0 && (
            <Card className="mb-8 border-gray-200">
              <CardHeader className="pb-2">
                <button
                  type="button"
                  className="flex items-center gap-2 text-left w-full"
                  onClick={() => setActivityOpen((o) => !o)}
                >
                  <History className="w-4 h-4 text-gray-600" />
                  <CardTitle className="text-base">Inbox activity</CardTitle>
                  <span className="text-xs text-gray-500 ml-auto">{activityOpen ? 'Hide' : 'Show'}</span>
                </button>
              </CardHeader>
              {activityOpen && (
                <CardContent className="pt-0">
                  <ul className="text-sm text-gray-700 space-y-2 border-t border-gray-100 pt-3">
                    {payload.activity_feed.map((row) => (
                      <li key={row.event_id || `${row.task_id}-${row.created_at}`} className="flex flex-wrap gap-x-2 gap-y-0.5">
                        <span className="font-medium text-midnight-blue">{actionLabel(row.action)}</span>
                        <span className="text-gray-500 font-mono text-xs truncate max-w-[12rem]" title={row.task_id}>
                          {row.task_id}
                        </span>
                        <span className="text-gray-400 text-xs">{formatWhen(row.created_at)}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  );
}
