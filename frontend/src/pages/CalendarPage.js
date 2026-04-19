import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  AlertCircle,
  Clock,
  Building2,
  ArrowLeft,
  List,
  Grid,
  RefreshCw,
  Wrench,
  Shield,
  Download,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import { toast } from '@/utils/portalNotifications';
import api, { openBlobApiResponse } from '../api/client';
import { buildEntityRoute, resolveClientPortalPath } from '../utils/clientPortalNavigation';
import { portalPageRoot } from '../components/client/ClientPortalPatterns';
import { cn } from '../lib/utils';

const FILTER_OPTIONS = [
  { key: 'requirement', label: 'Requirements', param: 'requirements' },
  { key: 'scheduled_job', label: 'Maintenance jobs', param: 'scheduled_jobs' },
  { key: 'compliance_job', label: 'Compliance jobs', param: 'compliance_jobs' },
];

function initialViewMode() {
  if (typeof window === 'undefined') return 'calendar';
  return window.matchMedia('(max-width: 767px)').matches ? 'list' : 'calendar';
}

function eventChipClass(event) {
  const cat = event.event_category;
  const sev = event.severity;
  if (sev === 'critical') return 'bg-red-100 text-red-800 border-red-200';
  if (sev === 'high') return 'bg-amber-100 text-amber-900 border-amber-200';
  if (cat === 'compliance_job') return 'bg-teal-50 text-teal-900 border-teal-200';
  if (cat === 'scheduled_job') return 'bg-indigo-50 text-indigo-900 border-indigo-200';
  if (event.status === 'COMPLIANT' || event.event_type === 'requirement_valid') return 'bg-green-100 text-green-800 border-green-200';
  return 'bg-slate-100 text-slate-800 border-slate-200';
}

function navigateForEvent(navigate, event) {
  const route = (event.primary_route || '').trim();
  if (route && route.startsWith('/')) {
    navigate(resolveClientPortalPath(route, '/calendar'));
    return;
  }
  const meta = event.metadata || {};
  const wid = meta.work_order_id;
  const rid = meta.requirement_id;
  const pid = meta.property_id || event.property_id;
  if (wid) {
    navigate(resolveClientPortalPath(buildEntityRoute({ work_order_id: wid, mode: 'review' }, '/operations/work-orders'), '/operations/work-orders'));
    return;
  }
  if (rid && pid) {
    navigate(
      resolveClientPortalPath(
        buildEntityRoute({ requirement_id: rid, property_id: pid, mode: 'requirement' }, '/requirements'),
        '/requirements'
      )
    );
    return;
  }
  navigate('/calendar');
}

function countDeadlineAttentionThisWeek(eventsByDate) {
  if (!eventsByDate || typeof eventsByDate !== 'object') return 0;
  const today = new Date();
  const y = today.getFullYear();
  const mo = String(today.getMonth() + 1).padStart(2, '0');
  const da = String(today.getDate()).padStart(2, '0');
  const todayKey = `${y}-${mo}-${da}`;
  const todayMs = new Date(`${todayKey}T12:00:00`).getTime();
  const weekEndMs = todayMs + 7 * 24 * 60 * 60 * 1000;
  let count = 0;
  for (const [dateKey, list] of Object.entries(eventsByDate)) {
    const dk = String(dateKey).slice(0, 10);
    if (!dk) continue;
    const dm = new Date(`${dk}T12:00:00`).getTime();
    if (Number.isNaN(dm) || dm < todayMs || dm >= weekEndMs) continue;
    for (const e of list || []) {
      const et = e?.event_type;
      if (et === 'requirement_overdue' || et === 'requirement_expiring_soon') {
        count += 1;
        continue;
      }
      const sev = String(e?.severity || '').toLowerCase();
      if (sev === 'critical' || sev === 'high') count += 1;
    }
  }
  return count;
}

function countTimelineAttentionThisWeek(events) {
  if (!Array.isArray(events)) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);
  let count = 0;
  for (const e of events) {
    let t = null;
    if (e.datetime_utc) {
      t = new Date(e.datetime_utc);
    } else if (e.date) {
      t = new Date(`${String(e.date).slice(0, 10)}T12:00:00`);
    }
    if (!t || Number.isNaN(t.getTime())) continue;
    if (t < today || t >= weekEnd) continue;
    const et = e.event_type;
    if (et === 'requirement_overdue' || et === 'requirement_expiring_soon') {
      count += 1;
      continue;
    }
    const sev = String(e.severity || '').toLowerCase();
    if (sev === 'critical' || sev === 'high') count += 1;
  }
  return count;
}

function calendarWeekWindowMs() {
  const today = new Date();
  const y = today.getFullYear();
  const mo = String(today.getMonth() + 1).padStart(2, '0');
  const da = String(today.getDate()).padStart(2, '0');
  const todayKey = `${y}-${mo}-${da}`;
  const todayMs = new Date(`${todayKey}T12:00:00`).getTime();
  const weekEndMs = todayMs + 7 * 24 * 60 * 60 * 1000;
  return { todayMs, weekEndMs };
}

function eventDecisionTier(event) {
  const et = event?.event_type;
  const cat = String(event?.event_category || '');
  if (et === 'requirement_overdue') return 0;
  if (et === 'requirement_expiring_soon') return 1;
  if (cat === 'requirement') {
    if (et === 'requirement_valid' || String(event?.status || '').toUpperCase() === 'COMPLIANT') return 10;
    const sev = String(event?.severity || '').toLowerCase();
    if (sev === 'critical' || sev === 'high') return 2;
    return 3;
  }
  if (cat === 'compliance_job') return 4;
  if (cat === 'scheduled_job') return 5;
  return 6;
}

function headlineForWeekTopEvent(event) {
  const title = String(event?.title || 'Requirement').trim() || 'Requirement';
  const et = event?.event_type;
  const cat = String(event?.event_category || '');
  if (et === 'requirement_overdue') return `${title} is overdue — act now`;
  if (et === 'requirement_expiring_soon') return `${title} is due soon — resolve before it expires`;
  if (cat === 'scheduled_job' || cat === 'compliance_job') return `${title} is scheduled this week — complete prep`;
  const sev = String(event?.severity || '').toLowerCase();
  if (sev === 'critical' || sev === 'high') return `${title} needs attention this week — resolve it next`;
  return `${title} is on your timeline this week — plan the next step`;
}

function collectCalendarGridWeekRows(eventsByDate) {
  const { todayMs, weekEndMs } = calendarWeekWindowMs();
  const rows = [];
  if (!eventsByDate || typeof eventsByDate !== 'object') return rows;
  for (const [dateKey, list] of Object.entries(eventsByDate)) {
    const dk = String(dateKey).slice(0, 10);
    if (!dk) continue;
    const dm = new Date(`${dk}T12:00:00`).getTime();
    if (Number.isNaN(dm) || dm < todayMs || dm >= weekEndMs) continue;
    for (const e of list || []) {
      rows.push({ event: e, dateKey: dk });
    }
  }
  return rows;
}

function collectTimelineWeekRows(events) {
  if (!Array.isArray(events)) return [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const rows = [];
  for (const e of events) {
    let t = null;
    if (e.datetime_utc) t = new Date(e.datetime_utc);
    else if (e.date) t = new Date(`${String(e.date).slice(0, 10)}T12:00:00`);
    if (!t || Number.isNaN(t.getTime())) continue;
    if (t < today || t >= weekEnd) continue;
    rows.push({ event: e });
  }
  return rows;
}

function sortWeekRowsByDecisionPriority(rows) {
  const sevOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  return [...rows].sort((a, b) => {
    const ta = eventDecisionTier(a.event);
    const tb = eventDecisionTier(b.event);
    if (ta !== tb) return ta - tb;
    const sa = sevOrder[String(a.event?.severity || '').toLowerCase()] ?? 4;
    const sb = sevOrder[String(b.event?.severity || '').toLowerCase()] ?? 4;
    if (sa !== sb) return sa - sb;
    return String(a.event?.title || '').localeCompare(String(b.event?.title || ''), undefined, { sensitivity: 'base' });
  });
}

function buildCalendarWeekDecisionCopy(view, eventsByDate, timelineEvents) {
  const rawRows = view === 'calendar' ? collectCalendarGridWeekRows(eventsByDate) : collectTimelineWeekRows(timelineEvents);
  if (!rawRows.length) return null;
  const sorted = sortWeekRowsByDecisionPriority(rawRows);
  const top = sorted[0]?.event;
  if (!top) return null;
  const primary = headlineForWeekTopEvent(top);
  const more = sorted.length - 1;
  const secondary = more > 0 ? `+ ${more} more ${more === 1 ? 'deadline' : 'deadlines'} this week` : null;
  return { primary, secondary };
}

/** Month cells show a capped list; sort so critical/high appear first and are not hidden behind "+N more". */
function sortEventsForMonthCell(events) {
  const order = { critical: 0, high: 1, medium: 2, low: 3 };
  return [...events].sort((a, b) => {
    const da = order[a.severity] ?? 4;
    const db = order[b.severity] ?? 4;
    if (da !== db) return da - db;
    return String(a.title || '').localeCompare(String(b.title || ''), undefined, { sensitivity: 'base' });
  });
}

function timelineCategoryLabel(category) {
  if (category === 'requirement') return 'Requirement';
  if (category === 'scheduled_job') return 'Repair';
  if (category === 'compliance_job') return 'Compliance';
  return String(category || '').replace(/_/g, ' ') || 'Event';
}

function formatEventWhen(event) {
  if (event.datetime_utc) {
    try {
      const d = new Date(event.datetime_utc);
      if (!Number.isNaN(d.getTime())) {
        const datePart = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
        const isMidnight = d.getUTCHours() === 0 && d.getUTCMinutes() === 0;
        if (isMidnight && !event.timezone) return datePart;
        return `${datePart} · ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
      }
    } catch {
      /* fall through */
    }
  }
  return event.date || '—';
}

const CalendarPage = () => {
  const navigate = useNavigate();
  const [view, setView] = useState(initialViewMode);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [calendarData, setCalendarData] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daysAhead, setDaysAhead] = useState(90);
  const [filtersEnabled, setFiltersEnabled] = useState(() => new Set(['requirement', 'scheduled_job', 'compliance_job']));
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [visiblePerDay, setVisiblePerDay] = useState(3);
  const [dayDialogOpen, setDayDialogOpen] = useState(false);
  const [dayDialogDateKey, setDayDialogDateKey] = useState(null);
  const [dayDialogEvents, setDayDialogEvents] = useState([]);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const mq = window.matchMedia('(max-width: 639px)');
    const apply = () => setVisiblePerDay(mq.matches ? 2 : 3);
    apply();
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, []);

  const openDayDetails = (dateKey, events) => {
    if (!dateKey || !events?.length) return;
    setDayDialogDateKey(dateKey);
    setDayDialogEvents(events);
    setDayDialogOpen(true);
  };

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  const filtersQuery = useMemo(() => {
    const parts = FILTER_OPTIONS.filter((f) => filtersEnabled.has(f.key)).map((f) => f.param);
    return parts.length === FILTER_OPTIONS.length || parts.length === 0 ? '' : parts.join(',');
  }, [filtersEnabled]);

  const handleDownloadIcs = useCallback(async () => {
    try {
      const params = { days: 365, lookback_days: 365 };
      if (filtersQuery) params.filters = filtersQuery;
      if (urgentOnly) params.urgent_only = true;
      const res = await api.get('/calendar/export.ics', { params, responseType: 'blob' });
      const cd = res.headers['content-disposition'];
      let fname = 'compliance_timeline.ics';
      if (cd && typeof cd === 'string') {
        const quoted = cd.match(/filename="([^"]+)"/i);
        const plain = cd.match(/filename=([^;\s]+)/i);
        const raw = quoted?.[1] || plain?.[1];
        if (raw) fname = raw.replace(/['"]/g, '').trim();
      }
      openBlobApiResponse(res, { download: true, fallbackFilename: fname });
    } catch {
      toast.error('Failed to download calendar');
    }
  }, [filtersQuery, urgentOnly]);

  const fetchCalendarData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { year: currentYear, month: currentMonth };
      if (filtersQuery) params.filters = filtersQuery;
      if (urgentOnly) params.urgent_only = true;
      const response = await api.get('/calendar/events', { params });
      const data = response.data || {};
      const eventsByDate = data.events_by_date || {};
      setCalendarData({
        events_by_date: eventsByDate,
        summary: data.summary || {},
        year: data.year,
        month: data.month,
        model_version: data.model_version,
      });
    } catch (error) {
      toast.error('Failed to load calendar data');
    } finally {
      setLoading(false);
    }
  }, [currentYear, currentMonth, filtersQuery, urgentOnly]);

  const fetchTimelineData = useCallback(async () => {
    setLoading(true);
    try {
      const params = { days: daysAhead };
      if (filtersQuery) params.filters = filtersQuery;
      if (urgentOnly) params.urgent_only = true;
      const response = await api.get('/calendar/upcoming', { params });
      const data = response.data || {};
      setTimelineData({
        events: data.timeline_events || [],
        summary: data.summary || {},
        days_ahead: data.days_ahead,
        model_version: data.model_version,
      });
    } catch (error) {
      toast.error('Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, [daysAhead, filtersQuery, urgentOnly]);

  useEffect(() => {
    if (view === 'calendar') {
      fetchCalendarData();
    } else {
      fetchTimelineData();
    }
  }, [view, fetchCalendarData, fetchTimelineData]);

  const toggleFilter = (key) => {
    setFiltersEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        if (next.size <= 1) return prev;
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const navigateMonth = (direction) => {
    const newDate = new Date(currentDate);
    newDate.setMonth(newDate.getMonth() + direction);
    setCurrentDate(newDate);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  const generateCalendarDays = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay();

    const days = [];
    for (let i = 0; i < startingDay; i += 1) {
      days.push({ day: null, date: null });
    }
    for (let day = 1; day <= daysInMonth; day += 1) {
      const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const raw = calendarData?.events_by_date?.[dateKey] || [];
      const events = sortEventsForMonthCell(raw);
      days.push({ day, date: dateKey, events });
    }
    return days;
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
  ];
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const today = new Date();
  const isToday = (dateKey) => {
    const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    return dateKey === todayKey;
  };

  const summary = view === 'calendar' ? calendarData?.summary : timelineData?.summary;

  const weekAttentionCount = useMemo(() => {
    if (view === 'calendar') return countDeadlineAttentionThisWeek(calendarData?.events_by_date);
    return countTimelineAttentionThisWeek(timelineData?.events);
  }, [view, calendarData?.events_by_date, timelineData?.events]);

  const urgentRequirementMonth = (summary?.overdue_count ?? 0) + (summary?.expiring_soon_count ?? 0);

  const weekDecisionCopy = useMemo(
    () => buildCalendarWeekDecisionCopy(view, calendarData?.events_by_date, timelineData?.events),
    [view, calendarData?.events_by_date, timelineData?.events]
  );

  const deadlineContextCalmMonth = useMemo(() => {
    if (
      view === 'calendar' &&
      summary &&
      (summary.total_events ?? 0) > 0 &&
      urgentRequirementMonth === 0 &&
      weekAttentionCount === 0
    ) {
      return 'No urgent deadlines this month.';
    }
    return null;
  }, [summary, view, urgentRequirementMonth, weekAttentionCount]);

  return (
    <div className={cn(portalPageRoot, 'bg-gray-50')} data-testid="calendar-page">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-3 sm:py-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors shrink-0"
                data-testid="back-to-dashboard"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div className="min-w-0">
                <h1 className="text-lg sm:text-xl font-semibold text-midnight-blue flex items-center gap-2">
                  <CalendarIcon className="w-5 h-5 sm:w-6 sm:h-6 text-electric-teal shrink-0" />
                  <span className="truncate">Compliance timeline</span>
                </h1>
                <p className="text-xs sm:text-sm text-gray-500 mt-0.5">
                  Upcoming compliance deadlines and scheduled visits. Requirement dates follow linked documents (confirmed,
                  then extracted, then legacy due). Visits appear when a job has a stored scheduled visit time.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 justify-end">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-[44px] gap-2 border-gray-200"
                onClick={handleDownloadIcs}
                data-testid="download-calendar-ics"
              >
                <Download className="w-4 h-4 shrink-0" />
                <span className="hidden sm:inline">Download .ics</span>
                <span className="sm:hidden">ICS</span>
              </Button>
              <div className="flex bg-gray-100 rounded-lg p-1">
                <button
                  type="button"
                  onClick={() => setView('calendar')}
                  className={`p-2 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center ${view === 'calendar' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'}`}
                  data-testid="view-calendar"
                  aria-label="Month view"
                >
                  <Grid className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setView('list')}
                  className={`p-2 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center ${view === 'list' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'}`}
                  data-testid="view-list"
                  aria-label="List view"
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="mt-3 flex flex-col sm:flex-row sm:flex-wrap gap-2 sm:items-center">
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">Show</span>
            <div className="flex flex-wrap gap-2">
              {FILTER_OPTIONS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => toggleFilter(f.key)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors min-h-[36px] ${
                    filtersEnabled.has(f.key)
                      ? 'bg-electric-teal/15 border-electric-teal text-midnight-blue'
                      : 'bg-white border-gray-200 text-gray-500'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer ml-0 sm:ml-2">
              <input
                type="checkbox"
                checked={urgentOnly}
                onChange={(e) => setUrgentOnly(e.target.checked)}
                className="rounded border-gray-300"
              />
              Urgent only
            </label>
          </div>
          {weekDecisionCopy ? (
            <div
              className="mt-3 text-sm text-midnight-blue bg-teal-50/80 border border-teal-100 rounded-lg px-3 py-2 space-y-1"
              role="status"
              data-testid="calendar-deadline-context"
            >
              <p className="font-semibold leading-snug">{weekDecisionCopy.primary}</p>
              {weekDecisionCopy.secondary ? (
                <p className="text-xs text-midnight-blue/85 font-medium">{weekDecisionCopy.secondary}</p>
              ) : null}
            </div>
          ) : deadlineContextCalmMonth ? (
            <p
              className="mt-3 text-sm text-midnight-blue font-medium bg-slate-50 border border-slate-100 rounded-lg px-3 py-2"
              role="status"
              data-testid="calendar-deadline-context-calm"
            >
              {deadlineContextCalmMonth}
            </p>
          ) : null}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
        {view === 'calendar' ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between bg-white rounded-xl p-3 sm:p-4 shadow-sm border border-gray-200 gap-2">
              <button
                type="button"
                onClick={() => navigateMonth(-1)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                data-testid="prev-month"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-4 text-center">
                <h2 className="text-lg sm:text-xl font-semibold text-midnight-blue">
                  {monthNames[currentMonth - 1]} {currentYear}
                </h2>
                <Button variant="outline" size="sm" onClick={goToToday} className="text-xs">
                  Today
                </Button>
              </div>
              <button
                type="button"
                onClick={() => navigateMonth(1)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors min-h-[44px] min-w-[44px] flex items-center justify-center"
                data-testid="next-month"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            {summary && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4">
                <div className="bg-white rounded-xl p-3 sm:p-4 border border-gray-200">
                  <p className="text-xl sm:text-2xl font-bold text-midnight-blue">{summary.total_events ?? 0}</p>
                  <p className="text-xs sm:text-sm text-gray-500">Events</p>
                </div>
                <div className="bg-red-50 rounded-xl p-3 sm:p-4 border border-red-200">
                  <p className="text-xl sm:text-2xl font-bold text-red-600">{summary.overdue_count ?? 0}</p>
                  <p className="text-xs sm:text-sm text-red-800">Overdue requirements</p>
                </div>
                <div className="bg-amber-50 rounded-xl p-3 sm:p-4 border border-amber-200">
                  <p className="text-xl sm:text-2xl font-bold text-amber-600">{summary.expiring_soon_count ?? 0}</p>
                  <p className="text-xs sm:text-sm text-amber-900">Expiring soon</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-3 sm:p-4 border border-gray-200">
                  <p className="text-xl sm:text-2xl font-bold text-gray-600">{summary.dates_with_events ?? 0}</p>
                  <p className="text-xs sm:text-sm text-gray-500">Days with events</p>
                </div>
              </div>
            )}

            {!loading && summary && summary.total_events === 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-800">No events in this range</p>
                  <p className="text-sm text-amber-800 mt-1">
                    Adjust filters or add requirement dates (confirmed or extracted) and scheduled visits on jobs.
                  </p>
                </div>
              </div>
            )}

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center h-64 sm:h-96">
                  <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-200">
                    {dayNames.map((day) => (
                      <div key={day} className="p-2 sm:p-3 text-center text-xs sm:text-sm font-medium text-gray-600">
                        {day}
                      </div>
                    ))}
                  </div>
                  <div className="grid grid-cols-7">
                    {generateCalendarDays().map((dayInfo, index) => (
                      <div
                        key={index}
                        className={`min-h-[5.5rem] sm:min-h-24 p-1 sm:p-2 border-b border-r border-gray-100 ${
                          dayInfo.day === null ? 'bg-gray-50' : ''
                        } ${isToday(dayInfo.date) ? 'bg-teal-50/60' : ''}`}
                      >
                        {dayInfo.day && (
                          <>
                            <button
                              type="button"
                              className={`text-xs sm:text-sm font-medium mb-1 w-full text-left rounded px-0.5 min-h-[28px] ${
                                isToday(dayInfo.date) ? 'text-electric-teal' : 'text-gray-600'
                              } ${dayInfo.events.length ? 'hover:bg-gray-100' : ''}`}
                              onClick={() => dayInfo.events.length && openDayDetails(dayInfo.date, dayInfo.events)}
                              aria-label={
                                dayInfo.events.length
                                  ? `Day ${dayInfo.day}, ${dayInfo.events.length} events, open list`
                                  : `Day ${dayInfo.day}`
                              }
                            >
                              {dayInfo.day}
                            </button>
                            {dayInfo.events.length > 0 && (
                              <div className="space-y-1">
                                {dayInfo.events.slice(0, visiblePerDay).map((event) => (
                                  <button
                                    key={event.event_id}
                                    type="button"
                                    onClick={() => navigateForEvent(navigate, event)}
                                    className={`w-full text-left text-[10px] sm:text-xs px-1 py-0.5 rounded border truncate cursor-pointer active:opacity-80 ${eventChipClass(event)}`}
                                    title={`${event.title} — ${event.property_name || ''}`}
                                    data-testid={`calendar-event-${event.event_id}`}
                                  >
                                    <span className="block truncate">{event.title}</span>
                                  </button>
                                ))}
                                {dayInfo.events.length > visiblePerDay && (
                                  <button
                                    type="button"
                                    className="w-full text-left text-[10px] sm:text-xs text-electric-teal font-medium py-1 px-0.5 rounded hover:bg-teal-50 min-h-[32px]"
                                    onClick={() => openDayDetails(dayInfo.date, dayInfo.events)}
                                    data-testid={`calendar-day-more-${dayInfo.date}`}
                                  >
                                    +{dayInfo.events.length - visiblePerDay} more — all events
                                  </button>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>

            <Card className="border-gray-200">
              <CardContent className="p-4 text-sm text-gray-600 flex flex-wrap gap-4 items-center">
                <span className="font-medium text-midnight-blue w-full sm:w-auto">Legend</span>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-red-500 shrink-0" />
                  <span>Overdue</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-amber-500 shrink-0" />
                  <span>Expiring / urgent</span>
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4 text-teal-600 shrink-0" />
                  <span>Compliance inspections & jobs</span>
                </div>
                <div className="flex items-center gap-2">
                  <Wrench className="w-4 h-4 text-indigo-600 shrink-0" />
                  <span>Repair visits</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full bg-green-500 shrink-0" />
                  <span>Valid requirement</span>
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white rounded-xl p-4 shadow-sm border border-gray-200">
              <h2 className="text-lg font-semibold text-midnight-blue">Upcoming timeline</h2>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-gray-500">Next</span>
                {[30, 60, 90, 180].map((days) => (
                  <button
                    key={days}
                    type="button"
                    onClick={() => setDaysAhead(days)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors min-h-[40px] ${
                      daysAhead === days ? 'bg-electric-teal text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                    data-testid={`days-filter-${days}`}
                  >
                    {days}d
                  </button>
                ))}
              </div>
            </div>

            {loading ? (
              <div className="flex items-center justify-center h-64 bg-white rounded-xl">
                <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
              </div>
            ) : !timelineData?.events?.length ? (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-200 px-4">
                <CalendarIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No events in this window</p>
              </div>
            ) : (
              <div className="space-y-3">
                {timelineData.events.map((event) => (
                  <button
                    type="button"
                    key={event.event_id}
                    onClick={() => navigateForEvent(navigate, event)}
                    className={`w-full text-left rounded-xl p-4 border-2 transition-colors hover:ring-2 hover:ring-electric-teal hover:ring-offset-2 ${eventChipClass(event)}`}
                    data-testid={`timeline-event-${event.event_id}`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                          <h3 className="font-semibold text-midnight-blue break-words">{event.title}</h3>
                          <span className="text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full bg-white/80 border border-current/20">
                            {timelineCategoryLabel(event.event_category)}
                          </span>
                        </div>
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-gray-700">
                          <span className="flex items-center gap-1 min-w-0">
                            <Building2 className="w-4 h-4 shrink-0" />
                            <span className="truncate">{event.property_name || event.property_id || '—'}</span>
                          </span>
                          <span className="flex items-center gap-1 shrink-0">
                            <Clock className="w-4 h-4" />
                            {formatEventWhen(event)}
                          </span>
                        </div>
                        {event.date_source && (
                          <p className="text-xs text-gray-500 mt-1">Date source: {event.date_source}</p>
                        )}
                      </div>
                      <div className="text-left sm:text-right shrink-0">
                        <p className="text-sm font-medium capitalize">{String(event.status || '').replace(/_/g, ' ') || '—'}</p>
                        <p className="text-xs text-gray-500 mt-1">Tap for details</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      <Dialog open={dayDialogOpen} onOpenChange={setDayDialogOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Events on {dayDialogDateKey}</DialogTitle>
            <DialogDescription>
              All events for this day. Tap an item to open details.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 mt-2">
            {dayDialogEvents.map((event) => (
              <button
                key={event.event_id}
                type="button"
                onClick={() => {
                  setDayDialogOpen(false);
                  navigateForEvent(navigate, event);
                }}
                className={`w-full text-left rounded-lg border p-3 flex flex-col gap-1 active:opacity-90 ${eventChipClass(event)}`}
              >
                <span className="font-medium text-sm break-words">{event.title}</span>
                <span className="text-xs opacity-90 truncate">{event.property_name || event.property_id || '—'}</span>
                <span className="text-xs opacity-90">{formatEventWhen(event)}</span>
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CalendarPage;
