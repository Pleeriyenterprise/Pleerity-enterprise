/**
 * Operations → Rent Operations: attention-first rent tracking and property expenses.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ScrollableUnderlineNav, scrollableNavButtonClass } from '../components/ui/scrollable-nav';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Loader2, PoundSterling, AlertTriangle } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';
import { EntitlementProtectedRoute } from '../utils/EntitlementProtectedRoute';
import { PortalFilterStack, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { RentSummaryCards } from '../components/rent/RentSummaryCards';
import { RentAttentionList } from '../components/rent/RentAttentionList';
import { RentLedgerList } from '../components/rent/RentLedgerList';
import { RentLedgerDetailDrawer } from '../components/rent/RentLedgerDetailDrawer';
import { RecordPaymentModal } from '../components/rent/RecordPaymentModal';
import { RentScheduleSetupModal } from '../components/rent/RentScheduleSetupModal';
import { MarkReminderSentModal } from '../components/rent/MarkReminderSentModal';
import { ExpenseFormModal } from '../components/rent/ExpenseFormModal';
import { PropertyExpensesPanel } from '../components/rent/PropertyExpensesPanel';
import { formatMinorUnits } from '../utils/rentMoney';
import { rentKpiCompatibleWithTab, rentKpiTargetTab, rentListCountHint } from '../utils/rentKpiCopy';
import { buildRentLedgerParams } from '../utils/rentKpiCoupling';

const TABS = [
  { id: 'attention', label: 'Attention' },
  { id: 'ledger', label: 'Ledger' },
  { id: 'expenses', label: 'Expenses' },
];

function ClientRentOperationsPageInner() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = searchParams.get('tab') || 'attention';

  const [summary, setSummary] = useState(null);
  const [ledgers, setLedgers] = useState([]);
  const [ledgerTotal, setLedgerTotal] = useState(0);
  const [expenses, setExpenses] = useState([]);
  const [expenseSummary, setExpenseSummary] = useState(null);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterProperty, setFilterProperty] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [activeKpi, setActiveKpi] = useState(null);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentLedger, setPaymentLedger] = useState(null);
  const [paymentSaving, setPaymentSaving] = useState(false);
  const [expenseOpen, setExpenseOpen] = useState(false);
  const [expenseSaving, setExpenseSaving] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [reminderLedger, setReminderLedger] = useState(null);
  const [reminderSaving, setReminderSaving] = useState(false);
  const [tenancyBackendReady, setTenancyBackendReady] = useState(null);

  const loadSummary = useCallback(() => {
    const params = filterProperty ? { property_id: filterProperty } : {};
    return clientAPI.getRentSummary(params).then((res) => setSummary(res.data)).catch(() => setSummary(null));
  }, [filterProperty]);

  const loadLedgers = useCallback(() => {
    const params = buildRentLedgerParams({
      tab,
      filterProperty,
      filterStatus,
      activeKpi,
    });
    return clientAPI
      .getRentLedgers(params)
      .then((res) => {
        setLedgers(res.data?.ledgers || []);
        setLedgerTotal(Number(res.data?.total) || 0);
      })
      .catch(() => {
        setLedgers([]);
        setLedgerTotal(0);
      });
  }, [filterProperty, filterStatus, tab, activeKpi]);

  const loadExpenses = useCallback(() => {
    const params = { limit: 100 };
    if (filterProperty) params.property_id = filterProperty;
    return Promise.all([
      clientAPI.getRentExpenses(params).then((res) => setExpenses(res.data?.expenses || [])),
      clientAPI.getRentExpensesSummary(params).then((res) => setExpenseSummary(res.data)).catch(() => setExpenseSummary(null)),
    ]);
  }, [filterProperty]);

  const refresh = useCallback(() => {
    setLoading(true);
    const jobs = [loadSummary()];
    if (tab === 'attention' || tab === 'ledger') {
      jobs.push(loadLedgers());
    }
    if (tab === 'expenses') {
      jobs.push(loadExpenses());
    }
    Promise.all(jobs)
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to load rent operations'))
      .finally(() => setLoading(false));
  }, [loadSummary, loadLedgers, loadExpenses, tab]);

  useEffect(() => {
    clientAPI.getProperties().then((res) => setProperties(res.data?.properties || res.data || [])).catch(() => setProperties([]));
    clientAPI
      .getRentCapabilities()
      .then((res) => setTenancyBackendReady(Boolean(res.data?.tenancy_authority)))
      .catch(() => setTenancyBackendReady(false));
  }, []);

  useEffect(() => {
    const pid = searchParams.get('property_id');
    if (pid) setFilterProperty(pid);
    if (searchParams.get('setup') === '1') setScheduleOpen(true);
  }, [searchParams]);

  useEffect(() => {
    refresh();
  }, [refresh, tab]);

  useEffect(() => {
    if (activeKpi && !rentKpiCompatibleWithTab(activeKpi, tab)) {
      setActiveKpi(null);
      setFilterStatus('');
    }
  }, [tab, activeKpi]);

  const listCountHint = rentListCountHint(ledgers.length, ledgerTotal);

  const openLedgerDetail = (row) => {
    setDetailLoading(true);
    setDetailData(row);
    clientAPI
      .getRentLedger(row.ledger_id)
      .then((res) => setDetailData(res.data))
      .catch(() => toast.error('Could not load ledger detail'))
      .finally(() => setDetailLoading(false));
  };

  const handleKpiFilter = (card) => {
    setActiveKpi(card);
    setFilterStatus(card.filter?.status || '');
    const targetTab = rentKpiTargetTab(card);
    if (targetTab) setSearchParams({ tab: targetTab });
  };

  const handleFilterStatusChange = (value) => {
    setFilterStatus(value);
    if (activeKpi?.filter?.status && activeKpi.filter.status !== value) {
      setActiveKpi(null);
    }
  };

  const handleRecordPayment = (body) => {
    setPaymentSaving(true);
    const req = paymentLedger
      ? clientAPI.recordRentLedgerPayment(paymentLedger.ledger_id, body)
      : clientAPI.recordRentPayment(body);
    req
      .then((res) => {
        const unalloc = res.data?.unallocated_minor || 0;
        if (unalloc > 0) {
          toast.success(
            `Payment recorded. ${formatMinorUnits(unalloc)} was not allocated to outstanding rent.`,
          );
        } else {
          toast.success('Payment recorded');
        }
        setPaymentOpen(false);
        setPaymentLedger(null);
        setDetailData(null);
        refresh();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to record payment'))
      .finally(() => setPaymentSaving(false));
  };

  const handleMarkReminder = (body) => {
    if (!reminderLedger) return;
    setReminderSaving(true);
    clientAPI
      .markRentReminderSent(reminderLedger.ledger_id, body)
      .then(() => {
        toast.success('Reminder marked as sent');
        setReminderOpen(false);
        openLedgerDetail(reminderLedger);
        refresh();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to mark reminder'))
      .finally(() => setReminderSaving(false));
  };

  const handleCreateExpense = (body) => {
    setExpenseSaving(true);
    clientAPI
      .createRentExpense(body)
      .then(() => {
        toast.success('Expense added');
        setExpenseOpen(false);
        refresh();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to add expense'))
      .finally(() => setExpenseSaving(false));
  };

  const handleScheduleCreated = async (data) => {
    const msg = data?.message || `Rent schedule created (${data?.periods_created || 0} periods).`;
    if (data?.partial_recovery) {
      toast.success(msg);
    } else if (data?.idempotent_replay) {
      toast.success('Schedule already created for this submission.');
    } else {
      toast.success(msg);
    }
    setScheduleOpen(false);
    refresh();
  };

  const hasRentTracking =
    summary &&
    ((summary.rent_collected_this_month_minor || 0) > 0 ||
      (summary.upcoming_due_count || 0) > 0 ||
      (summary.overdue_count || 0) > 0 ||
      (summary.partially_paid_count || 0) > 0 ||
      (summary.due_today_count || 0) > 0 ||
      (summary.tenancies_with_arrears_count || 0) > 0);

  const showEmptySetup = !loading && tab !== 'expenses' && ledgers.length === 0 && !hasRentTracking;

  return (
    <div className={portalPageRoot} data-testid="rent-operations-page">
      <header className="bg-midnight-blue text-white py-4 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <PoundSterling className="h-5 w-5" aria-hidden />
              Rent Operations
            </h1>
            <p className="text-sm text-white/80 mt-1">
              Monitoring, arrears, and payments — tenancy authority is set from Occupancy &amp; tenancy
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="bg-white/10 text-white border-white/20 hover:bg-white/20"
            onClick={() => setScheduleOpen(true)}
            data-testid="rent-enable-tracking"
          >
            Enable rent tracking
          </Button>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        <PortalFilterStack className="mb-4">
          <select
            className="border rounded-md px-3 py-2 text-sm"
            value={filterProperty}
            onChange={(e) => setFilterProperty(e.target.value)}
            data-testid="rent-filter-property"
          >
            <option value="">All properties</option>
            {properties.map((p) => (
              <option key={p.property_id} value={p.property_id}>
                {p.nickname || p.address_line_1 || p.property_id}
              </option>
            ))}
          </select>
          {tab === 'ledger' && (
            <select
              className="border rounded-md px-3 py-2 text-sm"
              value={filterStatus}
              onChange={(e) => handleFilterStatusChange(e.target.value)}
            >
              <option value="">All statuses</option>
              {['UPCOMING', 'DUE_TODAY', 'PAID', 'PARTIALLY_PAID', 'OVERDUE', 'SEVERELY_OVERDUE'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          )}
        </PortalFilterStack>

        {tenancyBackendReady === false && (
          <Card className="mb-4 border-amber-200 bg-amber-50/60" data-testid="rent-backend-unavailable">
            <CardContent className="py-3 text-sm text-amber-900">
              Tenancy-authority rent services are not live on this environment yet. Ledger payments on
              existing periods may still work; new schedules require a backend deploy.
            </CardContent>
          </Card>
        )}

        <RentSummaryCards summary={summary} activeFilter={activeKpi} onFilter={handleKpiFilter} />

        <ScrollableUnderlineNav ariaLabel="Rent operations sections" className="mb-4" data-testid="rent-operations-tab-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSearchParams({ tab: t.id })}
              className={scrollableNavButtonClass(tab === t.id)}
              data-testid={`rent-tab-${t.id}`}
            >
              {t.label}
            </button>
          ))}
        </ScrollableUnderlineNav>

        {loading ? (
          <div className="flex justify-center py-12" data-testid="rent-loading">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : tab === 'expenses' ? (
          <PropertyExpensesPanel
            expenses={expenses}
            expenseSummary={expenseSummary}
            onAdd={() => setExpenseOpen(true)}
          />
        ) : showEmptySetup ? (
          <Card data-testid="rent-empty-state">
            <CardContent className="py-10 text-center">
              <AlertTriangle className="h-8 w-8 text-gray-300 mx-auto mb-2" />
              <p className="text-gray-600">
                {tab === 'attention'
                  ? 'Nothing needs attention right now.'
                  : 'No ledger periods yet. Enable rent tracking from a property tenancy or here.'}
              </p>
              <Button className="mt-4" size="sm" onClick={() => setScheduleOpen(true)}>
                Enable rent tracking
              </Button>
            </CardContent>
          </Card>
        ) : tab === 'attention' ? (
          <RentAttentionList
            ledgers={ledgers}
            attentionPeriodTotal={summary?.attention_period_count ?? ledgerTotal}
            tenancyArrearsCount={summary?.tenancies_with_arrears_count}
            listCountHint={listCountHint}
            onSelect={openLedgerDetail}
            onRecordPayment={(row) => {
              setPaymentLedger(row);
              setPaymentOpen(true);
            }}
          />
        ) : (
          <>
            <RentLedgerList
              ledgers={ledgers}
              onSelect={openLedgerDetail}
              onRecordPayment={(row) => {
                setPaymentLedger(row);
                setPaymentOpen(true);
              }}
            />
            {listCountHint ? (
              <p className="text-xs text-gray-500 mt-2" data-testid="rent-list-count-hint">
                {listCountHint}
              </p>
            ) : null}
          </>
        )}
      </main>

      <RecordPaymentModal
        open={paymentOpen}
        onClose={() => {
          setPaymentOpen(false);
          setPaymentLedger(null);
        }}
        onSubmit={handleRecordPayment}
        saving={paymentSaving}
        ledger={paymentLedger}
        properties={properties}
        ledgers={ledgers}
      />

      <RentLedgerDetailDrawer
        ledger={detailLoading ? detailData : detailData}
        onClose={() => setDetailData(null)}
        onRecordPayment={(row) => {
          setPaymentLedger(row);
          setPaymentOpen(true);
        }}
        onMarkReminder={(row) => {
          setReminderLedger(row);
          setReminderOpen(true);
        }}
      />

      <MarkReminderSentModal
        open={reminderOpen}
        onClose={() => {
          setReminderOpen(false);
          setReminderLedger(null);
        }}
        onSubmit={handleMarkReminder}
        saving={reminderSaving}
        ledger={reminderLedger}
      />

      <ExpenseFormModal
        open={expenseOpen}
        onClose={() => setExpenseOpen(false)}
        onSubmit={handleCreateExpense}
        saving={expenseSaving}
        properties={properties}
      />

      <RentScheduleSetupModal
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        onCreated={handleScheduleCreated}
        onError={(err) => toast.error(err?.message || 'Failed to create schedule')}
        properties={properties}
        initialPropertyId={filterProperty}
        tenancyBackendReady={tenancyBackendReady}
      />
    </div>
  );
}

export default function ClientRentOperationsPage() {
  return (
    <EntitlementProtectedRoute requiredFeature="rent_operations">
      <ClientRentOperationsPageInner />
    </EntitlementProtectedRoute>
  );
}
