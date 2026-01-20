import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User, Calendar, TrendingUp, ArrowUp, ArrowDown, Zap, BarChart3, Users } from 'lucide-react';
import api from '../api/client';

const ClientDashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notificationPrefs, setNotificationPrefs] = useState(null);
  const [complianceScore, setComplianceScore] = useState(null);

  useEffect(() => {
    fetchDashboard();
    fetchNotificationPrefs();
    fetchComplianceScore();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await clientAPI.getDashboard();
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const fetchNotificationPrefs = async () => {
    try {
      const response = await api.get('/profile/notifications');
      setNotificationPrefs(response.data);
    } catch (err) {
      // Silently fail - not critical for dashboard
      console.log('Could not load notification preferences');
    }
  };

  const fetchComplianceScore = async () => {
    try {
      const response = await api.get('/client/compliance-score');
      setComplianceScore(response.data);
    } catch (err) {
      console.log('Could not load compliance score');
    }
  };

  const getComplianceColor = (status) => {
    switch (status) {
      case 'GREEN': return 'bg-green-50 text-green-700 border-green-200';
      case 'AMBER': return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case 'RED': return 'bg-red-50 text-red-700 border-red-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold">Compliance Vault Pro</h1>
              <p className="text-sm text-gray-300">AI-Driven Solutions & Compliance</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
              data-testid="nav-dashboard"
            >
              <Home className="w-4 h-4 mr-2" />
              Dashboard
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/properties')}
              data-testid="nav-properties"
            >
              <Home className="w-4 h-4 mr-2" />
              Properties
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/documents')}
              data-testid="nav-documents"
            >
              <FileText className="w-4 h-4 mr-2" />
              Documents
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/calendar')}
              data-testid="nav-calendar"
            >
              <Calendar className="w-4 h-4 mr-2" />
              Calendar
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/reports')}
              data-testid="nav-reports"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Reports
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/tenants')}
              data-testid="nav-tenants"
            >
              <Users className="w-4 h-4 mr-2" />
              Tenants
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/profile')}
              data-testid="nav-profile"
            >
              <User className="w-4 h-4 mr-2" />
              Profile
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="client-dashboard">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Welcome */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold text-midnight-blue mb-2">Welcome, {data?.client?.full_name}</h2>
            <p className="text-gray-600">Here's your compliance overview</p>
          </div>
          <Button 
            onClick={() => navigate('/app/assistant')}
            className="btn-secondary flex items-center gap-2"
            data-testid="ask-assistant-btn"
          >
            <MessageSquare className="w-4 h-4" />
            Ask Assistant
          </Button>
        </div>

        {/* Compliance Score Widget */}
        {complianceScore && (
          <div className="mb-8 grid lg:grid-cols-3 gap-6" data-testid="compliance-score-widget">
            {/* Main Score Card */}
            <div className={`lg:col-span-1 rounded-2xl p-6 border-2 ${
              complianceScore.color === 'green' ? 'bg-gradient-to-br from-green-50 to-green-100 border-green-200' :
              complianceScore.color === 'amber' ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200' :
              complianceScore.color === 'red' ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200' :
              'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200'
            }`}>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">Compliance Score</h3>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className={`text-5xl font-bold ${
                      complianceScore.color === 'green' ? 'text-green-700' :
                      complianceScore.color === 'amber' ? 'text-amber-700' :
                      complianceScore.color === 'red' ? 'text-red-700' :
                      'text-gray-700'
                    }`}>
                      {complianceScore.score}
                    </span>
                    <span className="text-2xl text-gray-400">/100</span>
                  </div>
                </div>
                <div className={`w-16 h-16 rounded-full flex items-center justify-center ${
                  complianceScore.color === 'green' ? 'bg-green-200' :
                  complianceScore.color === 'amber' ? 'bg-amber-200' :
                  complianceScore.color === 'red' ? 'bg-red-200' :
                  'bg-gray-200'
                }`}>
                  <span className={`text-3xl font-bold ${
                    complianceScore.color === 'green' ? 'text-green-700' :
                    complianceScore.color === 'amber' ? 'text-amber-700' :
                    complianceScore.color === 'red' ? 'text-red-700' :
                    'text-gray-700'
                  }`}>
                    {complianceScore.grade}
                  </span>
                </div>
              </div>
              <p className={`text-sm ${
                complianceScore.color === 'green' ? 'text-green-700' :
                complianceScore.color === 'amber' ? 'text-amber-700' :
                complianceScore.color === 'red' ? 'text-red-700' :
                'text-gray-600'
              }`}>
                {complianceScore.message}
              </p>
              
              {/* Score Breakdown */}
              <div className="mt-4 pt-4 border-t border-white/50 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Status</span>
                  <span className="font-medium">{complianceScore.breakdown?.status_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Expiry Timeline</span>
                  <span className="font-medium">{complianceScore.breakdown?.expiry_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Documents</span>
                  <span className="font-medium">{complianceScore.breakdown?.document_score?.toFixed(0)}%</span>
                </div>
              </div>
            </div>

            {/* Recommendations Card */}
            <div className="lg:col-span-2 bg-white rounded-2xl p-6 border border-gray-200 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="w-5 h-5 text-electric-teal" />
                <h3 className="font-semibold text-midnight-blue">Quick Actions to Improve Your Score</h3>
              </div>
              
              {complianceScore.recommendations?.length > 0 ? (
                <div className="space-y-3">
                  {complianceScore.recommendations.map((rec, idx) => (
                    <div 
                      key={idx}
                      className={`flex items-start gap-3 p-3 rounded-lg ${
                        rec.priority === 'high' ? 'bg-red-50 border border-red-100' :
                        rec.priority === 'medium' ? 'bg-amber-50 border border-amber-100' :
                        'bg-gray-50 border border-gray-100'
                      }`}
                    >
                      <div className={`w-2 h-2 rounded-full mt-2 ${
                        rec.priority === 'high' ? 'bg-red-500' :
                        rec.priority === 'medium' ? 'bg-amber-500' :
                        'bg-gray-400'
                      }`} />
                      <div className="flex-1">
                        <p className="text-sm font-medium text-gray-800">{rec.action}</p>
                        <p className="text-xs text-gray-500 mt-0.5">Potential impact: {rec.impact}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-3 p-4 bg-green-50 rounded-lg border border-green-100">
                  <CheckCircle className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">Excellent work!</p>
                    <p className="text-sm text-green-600">Your compliance is in great shape. Keep it up!</p>
                  </div>
                </div>
              )}

              {/* Stats Row */}
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-3 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-midnight-blue">{complianceScore.stats?.total_requirements || 0}</p>
                  <p className="text-xs text-gray-500">Requirements</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{complianceScore.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-500">Compliant</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-amber-600">
                    {complianceScore.stats?.days_until_next_expiry !== null ? complianceScore.stats?.days_until_next_expiry : '—'}
                  </p>
                  <p className="text-xs text-gray-500">Days to Next Expiry</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Compliance Summary */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Total Requirements</p>
                  <p className="text-3xl font-bold text-midnight-blue">
                    {data?.compliance_summary?.total_requirements || 0}
                  </p>
                </div>
                <Shield className="w-12 h-12 text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Compliant</p>
                  <p className="text-3xl font-bold text-green-600">
                    {data?.compliance_summary?.compliant || 0}
                  </p>
                </div>
                <CheckCircle className="w-12 h-12 text-green-600" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Expiring Soon</p>
                  <p className="text-3xl font-bold text-yellow-600">
                    {data?.compliance_summary?.expiring_soon || 0}
                  </p>
                </div>
                <Clock className="w-12 h-12 text-yellow-600" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Overdue</p>
                  <p className="text-3xl font-bold text-red-600">
                    {data?.compliance_summary?.overdue || 0}
                  </p>
                </div>
                <XCircle className="w-12 h-12 text-red-600" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Properties */}
        <div className="grid lg:grid-cols-3 gap-6 mb-8">
          <div className="lg:col-span-2">
            <Card className="enterprise-card h-full">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-midnight-blue">Your Properties</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate('/app/properties/import')}
                    data-testid="bulk-import-btn"
                  >
                    <FileText className="w-4 h-4 mr-1" />
                    Bulk Import
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {data?.properties?.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-gray-600 mb-3">No properties found</p>
                    <Button 
                      onClick={() => navigate('/app/properties/import')}
                      variant="outline"
                      data-testid="import-first-property-btn"
                    >
                      Import Properties from CSV
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {data?.properties?.map((property) => (
                      <div 
                        key={property.property_id}
                        className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-smooth"
                        data-testid="property-card"
                      >
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="font-semibold text-midnight-blue mb-1">
                              {property.address_line_1}
                            </h4>
                            <p className="text-sm text-gray-600">
                              {property.city}, {property.postcode}
                            </p>
                          </div>
                          <div className={`px-3 py-1 rounded-full text-sm font-medium border ${getComplianceColor(property.compliance_status)}`}>
                            {property.compliance_status}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Notification Preferences Widget */}
          <div className="lg:col-span-1">
            <Card className="enterprise-card h-full" data-testid="notification-prefs-widget">
              <CardHeader className="pb-3">
                <CardTitle className="text-midnight-blue flex items-center gap-2 text-lg">
                  <Bell className="w-5 h-5 text-electric-teal" />
                  Notification Settings
                </CardTitle>
              </CardHeader>
              <CardContent>
                {notificationPrefs ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Status Alerts</span>
                      {notificationPrefs.status_change_alerts ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Expiry Reminders</span>
                      {notificationPrefs.expiry_reminders ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-gray-100">
                      <span className="text-sm text-gray-600">Monthly Digest</span>
                      {notificationPrefs.monthly_digest ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="w-4 h-4" /> On
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-gray-400 text-sm">
                          <BellOff className="w-4 h-4" /> Off
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-600">Reminder Timing</span>
                      <span className="text-sm font-medium text-midnight-blue">
                        {notificationPrefs.reminder_days_before} days
                      </span>
                    </div>
                    
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full mt-3 border-electric-teal text-electric-teal hover:bg-teal-50"
                      onClick={() => navigate('/app/notifications')}
                      data-testid="manage-notifications-btn"
                    >
                      <Settings className="w-4 h-4 mr-2" />
                      Manage Preferences
                    </Button>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <Bell className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                    <p className="text-sm text-gray-500 mb-3">Configure your notification preferences</p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-electric-teal text-electric-teal hover:bg-teal-50"
                      onClick={() => navigate('/app/notifications')}
                    >
                      Set Up Notifications
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ClientDashboard;
