/**
 * Operations → Rent Operations: attention-first rent tracking and property expenses.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
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
import { MarkReminderSentModal } from '../components/rent/MarkReminderSentModal';
import { ExpenseFormModal } from '../components/rent/ExpenseFormModal';
import { PropertyExpensesPanel } from '../components/rent/PropertyExpensesPanel';
import { formatMinorUnits, parseMajorToMinor } from '../utils/rentMoney';

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
  const [scheduleForm, setScheduleForm] = useState({
    property_id: '',
    tenant_name: '',
    expected_amount: '',
    due_day: '1',
    start_date: new Date().toISOString().slice(0, 10),
    rent_frequency: 'monthly',
  });
  const [scheduleSaving, setScheduleSaving] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [reminderLedger, setReminderLedger] = useState(null);
  const [reminderSaving, setReminderSaving] = useState(false);

  const loadSummary = useCallback(() => {
    const params = filterProperty ? { property_id: filterProperty } : {};
    return clientAPI.getRentSummary(params).then((res) => setSummary(res.data)).catch(() => setSummary(null));
  }, [filterProperty]);

  const loadLedgers = useCallback(() => {
    const params = { limit: 200 };
    if (filterProperty) params.property_id = filterProperty;
    if (filterStatus && tab === 'ledger') params.status = filterStatus;
    if (activeKpi?.filter?.overdue_only) params.overdue_only = true;
    else if (tab === 'attention' || activeKpi?.filter?.attention_only) params.attention_only = true;
    else if (activeKpi?.filter?.status) params.status = activeKpi.filter.status;
    return clientAPI.getRentLedgers(params).then((res) => setLedgers(res.data?.ledgers || [])).catch(() => setLedgers([]));
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
    Promise.all([loadSummary(), loadLedgers(), loadExpenses()])
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to load rent operations'))
      .finally(() => setLoading(false));
  }, [loadSummary, loadLedgers, loadExpenses]);

  useEffect(() => {
    clientAPI.getProperties().then((res) => setProperties(res.data?.properties || res.data || [])).catch(() => setProperties([]));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, tab]);

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
    if (card.filter?.attention_only) setSearchParams({ tab: 'attention' });
    else if (card.key !== 'collected') setSearchParams({ tab: 'ledger' });
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

  const handleCreateSchedule = (e) => {
    e.preventDefault();
    setScheduleSaving(true);
    clientAPI
      .createRentSchedule({
        property_id: scheduleForm.property_id,
        tenant_name: scheduleForm.tenant_name,
        expected_amount_minor: parseMajorToMinor(scheduleForm.expected_amount),
        due_day: parseInt(scheduleForm.due_day, 10) || 1,
        start_date: scheduleForm.start_date,
        rent_frequency: scheduleForm.rent_frequency,
      })
      .then((res) => {
        toast.success(`Rent schedule created (${res.data?.periods_created || 0} periods generated)`);
        setScheduleOpen(false);
        refresh();
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Failed to create schedule'))
      .finally(() => setScheduleSaving(false));
  };

  const showEmptySetup = !loading && tab !== 'expenses' && ledgers.length === 0;

  return (
    <div className={portalPageRoot} data-testid="rent-operations-page">
      <header className="bg-midnight-blue text-white py-4 px-4 sm:px-6">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-2">
              <PoundSterling className="h-5 w-5" aria-hidden />
              Rent Operations
            </h1>
            <p className="text-sm text-white/80 mt-1">Operational rent tracking — not accounting or tax software</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="bg-white/10 text-white border-white/20 hover:bg-white/20"
              onClick={() => setScheduleOpen(true)}
            >
              Set up rent
            </Button>
            <Button
              size="sm"
              className="bg-electric-teal text-midnight-blue hover:bg-electric-teal/90"
              onClick={() => {
                setPaymentLedger(null);
                setPaymentOpen(true);
              }}
            >
              Record payment
            </Button>
          </div>
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
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="">All statuses</option>
              {['UPCOMING', 'DUE_TODAY', 'PAID', 'PARTIALLY_PAID', 'OVERDUE', 'SEVERELY_OVERDUE'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          )}
        </PortalFilterStack>

        <RentSummaryCards summary={summary} activeFilter={activeKpi} onFilter={handleKpiFilter} />

        <div className="flex gap-2 border-b border-gray-200 mb-4">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSearchParams({ tab: t.id })}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === t.id ? 'border-electric-teal text-midnight-blue' : 'border-transparent text-gray-500'
              }`}
              data-testid={`rent-tab-${t.id}`}
            >
              {t.label}
            </button>
          ))}
        </div>

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
                  : 'No rent periods yet. Set up rent for a property.'}
              </p>
              <Button className="mt-4" size="sm" onClick={() => setScheduleOpen(true)}>
                Set up rent
              </Button>
            </CardContent>
          </Card>
        ) : tab === 'attention' ? (
          <RentAttentionList
            ledgers={ledgers}
            onSelect={openLedgerDetail}
            onRecordPayment={(row) => {
              setPaymentLedger(row);
              setPaymentOpen(true);
            }}
          />
        ) : (
          <RentLedgerList ledgers={ledgers} onSelect={openLedgerDetail} />
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
        propertyId={paymentLedger?.property_id || filterProperty}
        ledgerId={paymentLedger?.ledger_id}
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

      {scheduleOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="rent-schedule-modal">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4">Set up rent schedule</h3>
            <form onSubmit={handleCreateSchedule} className="space-y-3">
              <select
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={scheduleForm.property_id}
                onChange={(e) => setScheduleForm((f) => ({ ...f, property_id: e.target.value }))}
                required
              >
                <option value="">Property</option>
                {properties.map((p) => (
                  <option key={p.property_id} value={p.property_id}>
                    {p.nickname || p.address_line_1}
                  </option>
                ))}
              </select>
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="Tenant name"
                value={scheduleForm.tenant_name}
                onChange={(e) => setScheduleForm((f) => ({ ...f, tenant_name: e.target.value }))}
                required
              />
              <input
                className="w-full border rounded-md px-3 py-2 text-sm"
                placeholder="Monthly rent (£)"
                value={scheduleForm.expected_amount}
                onChange={(e) => setScheduleForm((f) => ({ ...f, expected_amount: e.target.value }))}
                required
              />
              <input
                type="number"
                min={1}
                max={28}
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={scheduleForm.due_day}
                onChange={(e) => setScheduleForm((f) => ({ ...f, due_day: e.target.value }))}
              />
              <input
                type="date"
                className="w-full border rounded-md px-3 py-2 text-sm"
                value={scheduleForm.start_date}
                onChange={(e) => setScheduleForm((f) => ({ ...f, start_date: e.target.value }))}
                required
              />
              <div className="flex gap-2 justify-end">
                <Button type="button" variant="outline" onClick={() => setScheduleOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={scheduleSaving}>Create schedule</Button>
              </div>
            </form>
          </div>
        </div>
      )}
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
