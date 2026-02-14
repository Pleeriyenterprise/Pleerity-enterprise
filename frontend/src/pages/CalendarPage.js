import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ChevronLeft, 
  ChevronRight,
  Calendar as CalendarIcon,
  AlertCircle,
  Clock,
  Building2,
  ArrowLeft,
  Filter,
  List,
  Grid,
  RefreshCw
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import api from '../api/client';

const CalendarPage = () => {
  const navigate = useNavigate();
  const [view, setView] = useState('calendar'); // 'calendar' or 'list'
  const [currentDate, setCurrentDate] = useState(new Date());
  const [calendarData, setCalendarData] = useState(null);
  const [upcomingData, setUpcomingData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [daysAhead, setDaysAhead] = useState(90);

  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  const fetchCalendarData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`/calendar/expiries?year=${currentYear}&month=${currentMonth}`);
      setCalendarData(response.data);
    } catch (error) {
      toast.error('Failed to load calendar data');
    } finally {
      setLoading(false);
    }
  }, [currentYear, currentMonth]);

  const fetchUpcomingData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.get(`/calendar/upcoming?days=${daysAhead}`);
      setUpcomingData(response.data);
    } catch (error) {
      toast.error('Failed to load upcoming expiries');
    } finally {
      setLoading(false);
    }
  }, [daysAhead]);

  useEffect(() => {
    if (view === 'calendar') {
      fetchCalendarData();
    } else {
      fetchUpcomingData();
    }
  }, [view, fetchCalendarData, fetchUpcomingData]);

  const navigateMonth = (direction) => {
    const newDate = new Date(currentDate);
    newDate.setMonth(newDate.getMonth() + direction);
    setCurrentDate(newDate);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Generate calendar days
  const generateCalendarDays = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDay = firstDay.getDay(); // 0 = Sunday
    
    const days = [];
    
    // Add empty cells for days before the first of the month
    for (let i = 0; i < startingDay; i++) {
      days.push({ day: null, date: null });
    }
    
    // Add days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
      const events = calendarData?.events_by_date?.[dateKey] || [];
      days.push({ day, date: dateKey, events });
    }
    
    return days;
  };

  const getEventDotColor = (event) => {
    switch (event.status_color) {
      case 'red': return 'bg-red-500';
      case 'amber': return 'bg-amber-500';
      case 'green': return 'bg-green-500';
      default: return 'bg-blue-500';
    }
  };

  const getUrgencyColor = (urgency) => {
    switch (urgency) {
      case 'high': return 'text-red-600 bg-red-50 border-red-200';
      case 'medium': return 'text-amber-600 bg-amber-50 border-amber-200';
      default: return 'text-blue-600 bg-blue-50 border-blue-200';
    }
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const today = new Date();
  const isToday = (dateKey) => {
    const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
    return dateKey === todayKey;
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="calendar-page">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/dashboard')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="back-to-dashboard"
              >
                <ArrowLeft className="w-5 h-5 text-gray-600" />
              </button>
              <div>
                <h1 className="text-xl font-semibold text-midnight-blue flex items-center gap-2">
                  <CalendarIcon className="w-6 h-6 text-electric-teal" />
                  Compliance Calendar
                </h1>
                <p className="text-sm text-gray-500">Track certificate expirations</p>
              </div>
            </div>
            
            {/* View Toggle */}
            <div className="flex items-center gap-2">
              <div className="flex bg-gray-100 rounded-lg p-1">
                <button
                  onClick={() => setView('calendar')}
                  className={`p-2 rounded-lg transition-colors ${view === 'calendar' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'}`}
                  data-testid="view-calendar"
                >
                  <Grid className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setView('list')}
                  className={`p-2 rounded-lg transition-colors ${view === 'list' ? 'bg-white shadow-sm' : 'hover:bg-gray-200'}`}
                  data-testid="view-list"
                >
                  <List className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {view === 'calendar' ? (
          /* Calendar View */
          <div className="space-y-4">
            {/* Calendar Navigation */}
            <div className="flex items-center justify-between bg-white rounded-xl p-4 shadow-sm border border-gray-200">
              <button
                onClick={() => navigateMonth(-1)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="prev-month"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              
              <div className="flex items-center gap-4">
                <h2 className="text-xl font-semibold text-midnight-blue">
                  {monthNames[currentMonth - 1]} {currentYear}
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToToday}
                  className="text-xs"
                >
                  Today
                </Button>
              </div>
              
              <button
                onClick={() => navigateMonth(1)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                data-testid="next-month"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>

            {/* Summary Stats */}
            {calendarData?.summary && (
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-white rounded-xl p-4 border border-gray-200">
                  <p className="text-2xl font-bold text-midnight-blue">{calendarData.summary.total_events}</p>
                  <p className="text-sm text-gray-500">Total Expiries</p>
                </div>
                <div className="bg-red-50 rounded-xl p-4 border border-red-200">
                  <p className="text-2xl font-bold text-red-600">{calendarData.summary.overdue_count}</p>
                  <p className="text-sm text-red-700">Overdue</p>
                </div>
                <div className="bg-amber-50 rounded-xl p-4 border border-amber-200">
                  <p className="text-2xl font-bold text-amber-600">{calendarData.summary.expiring_soon_count}</p>
                  <p className="text-sm text-amber-700">Expiring Soon</p>
                </div>
                <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
                  <p className="text-2xl font-bold text-gray-600">{calendarData.summary.dates_with_events}</p>
                  <p className="text-sm text-gray-500">Days with Events</p>
                </div>
              </div>
            )}

            {/* Calendar Grid */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
              {loading ? (
                <div className="flex items-center justify-center h-96">
                  <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
                </div>
              ) : (
                <>
                  {/* Day Headers */}
                  <div className="grid grid-cols-7 bg-gray-50 border-b border-gray-200">
                    {dayNames.map(day => (
                      <div key={day} className="p-3 text-center text-sm font-medium text-gray-600">
                        {day}
                      </div>
                    ))}
                  </div>
                  
                  {/* Calendar Days */}
                  <div className="grid grid-cols-7">
                    {generateCalendarDays().map((dayInfo, index) => (
                      <div
                        key={index}
                        className={`min-h-24 p-2 border-b border-r border-gray-100 ${
                          dayInfo.day === null ? 'bg-gray-50' : ''
                        } ${isToday(dayInfo.date) ? 'bg-teal-50' : ''}`}
                      >
                        {dayInfo.day && (
                          <>
                            <div className={`text-sm font-medium mb-1 ${
                              isToday(dayInfo.date) ? 'text-electric-teal' : 'text-gray-600'
                            }`}>
                              {dayInfo.day}
                            </div>
                            
                            {/* Event Dots */}
                            {dayInfo.events.length > 0 && (
                              <div className="space-y-1">
                                {dayInfo.events.slice(0, 3).map((event, idx) => (
                                  <div
                                    key={idx}
                                    className={`text-xs px-1.5 py-0.5 rounded truncate ${
                                      event.status_color === 'red' ? 'bg-red-100 text-red-700' :
                                      event.status_color === 'amber' ? 'bg-amber-100 text-amber-700' :
                                      event.status_color === 'green' ? 'bg-green-100 text-green-700' :
                                      'bg-blue-100 text-blue-700'
                                    }`}
                                    title={`${event.description} - ${event.property_address}`}
                                  >
                                    {event.description.split(' ')[0]}
                                  </div>
                                ))}
                                {dayInfo.events.length > 3 && (
                                  <div className="text-xs text-gray-500">
                                    +{dayInfo.events.length - 3} more
                                  </div>
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

            {/* Legend */}
            <div className="flex items-center gap-6 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span>Overdue</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-amber-500"></div>
                <span>Expiring Soon</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                <span>Pending</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span>Compliant</span>
              </div>
            </div>
          </div>
        ) : (
          /* List View */
          <div className="space-y-4">
            {/* Days Ahead Filter */}
            <div className="flex items-center justify-between bg-white rounded-xl p-4 shadow-sm border border-gray-200">
              <h2 className="text-lg font-semibold text-midnight-blue">Upcoming Expiries</h2>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Show next:</span>
                {[30, 60, 90, 180].map(days => (
                  <button
                    key={days}
                    onClick={() => setDaysAhead(days)}
                    className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                      daysAhead === days 
                        ? 'bg-electric-teal text-white' 
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                    data-testid={`days-filter-${days}`}
                  >
                    {days} days
                  </button>
                ))}
              </div>
            </div>

            {/* Upcoming List */}
            {loading ? (
              <div className="flex items-center justify-center h-64 bg-white rounded-xl">
                <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
              </div>
            ) : upcomingData?.upcoming?.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
                <CalendarIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No expiries in the next {daysAhead} days</p>
              </div>
            ) : (
              <div className="space-y-3">
                {upcomingData?.upcoming?.map((item) => (
                  <div
                    key={item.requirement_id}
                    className={`bg-white rounded-xl p-4 border-2 ${getUrgencyColor(item.urgency)}`}
                    data-testid={`upcoming-item-${item.requirement_id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-semibold text-midnight-blue">{item.description}</h3>
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            item.urgency === 'high' ? 'bg-red-100 text-red-700' :
                            item.urgency === 'medium' ? 'bg-amber-100 text-amber-700' :
                            'bg-blue-100 text-blue-700'
                          }`}>
                            {item.urgency === 'high' ? 'Urgent' : item.urgency === 'medium' ? 'Soon' : 'Upcoming'}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span className="flex items-center gap-1">
                            <Building2 className="w-4 h-4" />
                            {item.property_address}, {item.property_city}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock className="w-4 h-4" />
                            Due: {new Date(item.due_date).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`text-2xl font-bold ${
                          item.days_until_due <= 7 ? 'text-red-600' :
                          item.days_until_due <= 30 ? 'text-amber-600' :
                          'text-gray-600'
                        }`}>
                          {item.days_until_due}
                        </p>
                        <p className="text-xs text-gray-500">days left</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
};

export default CalendarPage;
