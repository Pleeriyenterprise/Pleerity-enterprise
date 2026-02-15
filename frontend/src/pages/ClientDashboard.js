import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User, Calendar, TrendingUp, TrendingDown, ArrowUp, ArrowDown, Zap, BarChart3, Users, Webhook, ChevronDown, ChevronUp, Info, ExternalLink, Minus, CreditCard } from 'lucide-react';
import api, { API_URL } from '../api/client';
import Sparkline from '../components/Sparkline';

const ClientDashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { hasFeature } = useEntitlements();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notificationPrefs, setNotificationPrefs] = useState(null);
  const [complianceScore, setComplianceScore] = useState(null);
  const [scoreTrend, setScoreTrend] = useState(null);
  const [showScoreExplanation, setShowScoreExplanation] = useState(false);
  // Explicit UI states instead of blank screen (Goal C)
  const [restrictReason, setRestrictReason] = useState(null); // 'plan' | 'not_provisioned' | 'provisioning_incomplete' | null
  const [redirectPath, setRedirectPath] = useState(null); // from 403 X-Redirect header
  const [networkError, setNetworkError] = useState(false); // true when no response (CORS/network)

  // Only load client dashboard data for client roles with a client_id (staff/owner have client_id null)
  const isClientUser = user && (user.role === 'ROLE_CLIENT' || user.role === 'ROLE_CLIENT_ADMIN') && user.client_id;

  useEffect(() => {
    if (!isClientUser) {
      setLoading(false);
      if (user && !user.client_id) setError('Client not found. Use the correct portal for your role.');
      return;
    }
    fetchDashboard();
    fetchNotificationPrefs();
    fetchComplianceScore();
    fetchScoreTrend();
    // Intentionally depend only on role/client_id; fetch functions are stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isClientUser, user?.role, user?.client_id]);

  const fetchDashboard = async () => {
    try {
      setRestrictReason(null);
      const response = await clientAPI.getDashboard();
      setData(response.data);
      // Defensive: detect missing plan/entitlement (test accounts not fully provisioned)
      const client = response.data?.client;
      if (client && client.billing_plan == null && client.plan_code == null) {
        setRestrictReason('not_provisioned');
      }
    } catch (err) {
      setNetworkError(!err.response);
      const detail = err.response?.data?.detail ?? '';
      const status = err.response?.status;
      const redirect = err.response?.headers?.['x-redirect'];
      if (redirect) setRedirectPath(redirect);
      if (status === 403) {
        const msg = typeof detail === 'string' ? detail.toLowerCase() : String(detail).toLowerCase();
        if (msg.includes('plan') || msg.includes('feature') || msg.includes('entitlement') || msg.includes('restricted')) {
          setRestrictReason('plan');
        } else if (msg.includes('provisioning') || msg.includes('incomplete') || msg.includes('password not set')) {
          setRestrictReason('provisioning_incomplete');
        }
      }
      if (!err.response) {
        setError(`Cannot reach server. Backend: ${API_URL || '(not set)'}`);
      } else {
        const msg = typeof detail === 'string' ? detail : (detail && typeof detail === 'object' && detail.message ? detail.message : JSON.stringify(detail));
        setError(msg || 'Failed to load dashboard');
      }
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

  const fetchScoreTrend = async () => {
    try {
      const response = await api.get('/client/compliance-score/trend?days=30');
      setScoreTrend(response.data);
    } catch (err) {
      console.log('Could not load score trend');
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
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-2xl font-bold">Compliance Vault Pro</h1>
                <p className="text-sm text-gray-300">AI-Driven Solutions & Compliance</p>
              </div>
              {data?.client?.customer_reference && (
                <span 
                  className="px-3 py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-sm"
                  data-testid="client-crn-badge"
                  title="Your Customer Reference Number"
                >
                  {data.client.customer_reference}
                </span>
              )}
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
            {(hasFeature('reports_pdf') || hasFeature('reports_csv')) && (
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/reports')}
              data-testid="nav-reports"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Reports
            </button>
            )}
            {hasFeature('tenant_portal') && (
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/tenants')}
              data-testid="nav-tenants"
            >
              <Users className="w-4 h-4 mr-2" />
              Tenants
            </button>
            )}
            {hasFeature('webhooks') && (
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/integrations')}
              data-testid="nav-integrations"
            >
              <Webhook className="w-4 h-4 mr-2" />
              Integrations
            </button>
            )}
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/profile')}
              data-testid="nav-profile"
            >
              <User className="w-4 h-4 mr-2" />
              Profile
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/billing')}
              data-testid="nav-billing"
            >
              <CreditCard className="w-4 h-4 mr-2" />
              Plans
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

        {/* Explicit "Access restricted by plan" UI (no blank screen) */}
        {restrictReason === 'plan' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-restricted-by-plan">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Access restricted by plan.</span>
              <span className="block mt-1 text-amber-800">This feature or area is not included in your current plan. Contact support or upgrade to access it.</span>
              <a href="mailto:support@pleerity.com" className="inline-block mt-2 text-sm font-medium text-electric-teal hover:underline">Contact support</a>
            </AlertDescription>
          </Alert>
        )}

        {/* Defensive: missing plan/entitlement (account not provisioned properly) */}
        {restrictReason === 'not_provisioned' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-not-provisioned">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Account not provisioned properly.</span>
              <span className="block mt-1 text-amber-800">Your account is missing plan or entitlement information. Please contact support to complete setup.</span>
              <a href="mailto:support@pleerity.com" className="inline-block mt-2 text-sm font-medium text-electric-teal hover:underline">Contact support</a>
            </AlertDescription>
          </Alert>
        )}

        {/* 403 Provisioning incomplete / Password not set — show next steps */}
        {restrictReason === 'provisioning_incomplete' && (
          <Alert className="mb-6 border-amber-200 bg-amber-50" data-testid="alert-provisioning-incomplete">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription>
              <span className="font-medium text-amber-900">Not provisioned or action required.</span>
              <span className="block mt-1 text-amber-800">{error || 'Complete onboarding or set your password to access the dashboard.'}</span>
              {redirectPath && (
                <Button
                  size="sm"
                  className="mt-3 bg-electric-teal hover:bg-electric-teal/90"
                  onClick={() => navigate(redirectPath)}
                >
                  Continue
                </Button>
              )}
              {!redirectPath && (
                <Button size="sm" className="mt-3 bg-electric-teal hover:bg-electric-teal/90" onClick={() => navigate('/onboarding-status')}>
                  Check onboarding status
                </Button>
              )}
            </AlertDescription>
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
            {/* Main Score Card - CLICKABLE */}
            <div 
              className={`lg:col-span-1 rounded-2xl p-6 border-2 cursor-pointer hover:shadow-lg transition-all group ${
                complianceScore.color === 'green' ? 'bg-gradient-to-br from-green-50 to-green-100 border-green-200 hover:border-green-400' :
                complianceScore.color === 'amber' ? 'bg-gradient-to-br from-amber-50 to-amber-100 border-amber-200 hover:border-amber-400' :
                complianceScore.color === 'red' ? 'bg-gradient-to-br from-red-50 to-red-100 border-red-200 hover:border-red-400' :
                'bg-gradient-to-br from-gray-50 to-gray-100 border-gray-200 hover:border-gray-400'
              }`}
              onClick={() => navigate('/app/compliance-score')}
              data-testid="compliance-score-card-clickable"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-medium text-gray-600 uppercase tracking-wide">Compliance Score</h3>
                    <ExternalLink className="w-3 h-3 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
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
              
              {/* Score Trending Sparkline */}
              {scoreTrend?.has_history && scoreTrend.sparkline?.length > 1 && (
                <div className="mt-4 pt-3 border-t border-white/50" data-testid="score-trend-section">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">30-Day Trend</span>
                    <div className="flex items-center gap-1">
                      {scoreTrend.trend_direction === 'up' && (
                        <span className="flex items-center text-xs text-green-600">
                          <TrendingUp className="w-3 h-3 mr-0.5" />
                          +{scoreTrend.change_7d || scoreTrend.change_30d || 0}
                        </span>
                      )}
                      {scoreTrend.trend_direction === 'down' && (
                        <span className="flex items-center text-xs text-red-600">
                          <TrendingDown className="w-3 h-3 mr-0.5" />
                          {scoreTrend.change_7d || scoreTrend.change_30d || 0}
                        </span>
                      )}
                      {scoreTrend.trend_direction === 'stable' && (
                        <span className="flex items-center text-xs text-gray-500">
                          <Minus className="w-3 h-3 mr-0.5" />
                          Stable
                        </span>
                      )}
                    </div>
                  </div>
                  <Sparkline 
                    data={scoreTrend.sparkline}
                    width={180}
                    height={40}
                    trendDirection={scoreTrend.trend_direction}
                    showArea={true}
                  />
                  <p className="text-xs text-gray-400 mt-1">
                    {scoreTrend.days_of_data} days of data • Avg: {scoreTrend.avg_score}
                  </p>
                </div>
              )}
              
              {/* Show placeholder if no trend data yet */}
              {(!scoreTrend?.has_history || !scoreTrend?.sparkline?.length) && (
                <div className="mt-4 pt-3 border-t border-white/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">30-Day Trend</span>
                  </div>
                  <div className="h-10 flex items-center justify-center bg-white/30 rounded-lg">
                    <span className="text-xs text-gray-400">Trend tracking starts tomorrow</span>
                  </div>
                </div>
              )}
              
              {/* Score Breakdown */}
              <div className="mt-4 pt-4 border-t border-white/50 space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Status (40%)</span>
                  <span className="font-medium">{complianceScore.breakdown?.status_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Timeline (30%)</span>
                  <span className="font-medium">{complianceScore.breakdown?.expiry_score?.toFixed(0)}%</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-gray-600">Documents (15%)</span>
                  <span className="font-medium">{complianceScore.breakdown?.document_score?.toFixed(0)}%</span>
                </div>
              </div>
              
              {/* Expandable Explanation Toggle */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowScoreExplanation(!showScoreExplanation);
                }}
                className="mt-3 flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 w-full justify-center"
                data-testid="toggle-score-explanation"
              >
                <Info className="w-3 h-3" />
                How is this calculated?
                {showScoreExplanation ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
              
              {/* Inline Explanation */}
              {showScoreExplanation && (
                <div className="mt-3 pt-3 border-t border-white/50 text-xs space-y-2" onClick={(e) => e.stopPropagation()}>
                  <p className="font-medium text-gray-700">Score Components:</p>
                  <ul className="space-y-1 text-gray-600">
                    <li>• <strong>Status (40%):</strong> {complianceScore.stats?.compliant || 0}/{complianceScore.stats?.total_requirements || 0} requirements valid</li>
                    <li>• <strong>Timeline (30%):</strong> {complianceScore.stats?.expiring_soon || 0} items due within 30 days</li>
                    <li>• <strong>Documents (15%):</strong> {complianceScore.stats?.document_coverage_percent?.toFixed(0) || 0}% requirement coverage</li>
                    <li>• <strong>Overdue Penalty (15%):</strong> {complianceScore.stats?.overdue || 0} overdue items</li>
                  </ul>
                  <p className="text-electric-teal pt-1">Click card for full breakdown →</p>
                </div>
              )}
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

              {/* Stats Row - Clickable */}
              <div className="mt-4 pt-4 border-t border-gray-100 grid grid-cols-3 gap-4">
                <div 
                  className="text-center cursor-pointer hover:bg-gray-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/app/requirements')}
                  data-testid="stat-requirements"
                >
                  <p className="text-2xl font-bold text-midnight-blue">{complianceScore.stats?.total_requirements || 0}</p>
                  <p className="text-xs text-gray-500">Requirements</p>
                </div>
                <div 
                  className="text-center cursor-pointer hover:bg-green-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/app/requirements?status=COMPLIANT')}
                  data-testid="stat-compliant"
                >
                  <p className="text-2xl font-bold text-green-600">{complianceScore.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-500">Compliant</p>
                </div>
                <div 
                  className="text-center cursor-pointer hover:bg-amber-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/app/requirements?window=30&status=DUE_SOON')}
                  data-testid="stat-expiry"
                >
                  <p className="text-2xl font-bold text-amber-600">
                    {complianceScore.stats?.days_until_next_expiry !== null ? complianceScore.stats?.days_until_next_expiry : '—'}
                  </p>
                  <p className="text-xs text-gray-500">Days to Next Expiry</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Compliance Summary - Clickable Tiles */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-electric-teal group"
            onClick={() => navigate('/app/requirements')}
            data-testid="tile-total-requirements"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Total Requirements</p>
                  <p className="text-3xl font-bold text-midnight-blue">
                    {data?.compliance_summary?.total_requirements || 0}
                  </p>
                  <p className="text-xs text-electric-teal opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    Click to view all →
                  </p>
                </div>
                <Shield className="w-12 h-12 text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-green-300 group"
            onClick={() => navigate('/app/properties?status=COMPLIANT')}
            data-testid="tile-compliant"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Compliant</p>
                  <p className="text-3xl font-bold text-green-600">
                    {data?.compliance_summary?.compliant || 0}
                  </p>
                  <p className="text-xs text-green-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    Click to view →
                  </p>
                </div>
                <CheckCircle className="w-12 h-12 text-green-600" />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-amber-300 group"
            onClick={() => navigate('/app/requirements?status=DUE_SOON')}
            data-testid="tile-expiring-soon"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Attention Needed</p>
                  <p className="text-3xl font-bold text-yellow-600">
                    {data?.compliance_summary?.expiring_soon || 0}
                  </p>
                  <p className="text-xs text-yellow-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    Click to view →
                  </p>
                </div>
                <Clock className="w-12 h-12 text-yellow-600" />
              </div>
            </CardContent>
          </Card>

          <Card 
            className="enterprise-card cursor-pointer hover:shadow-lg transition-shadow hover:border-red-300 group"
            onClick={() => navigate('/app/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="tile-overdue"
          >
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Action Required</p>
                  <p className="text-3xl font-bold text-red-600">
                    {data?.compliance_summary?.overdue || 0}
                  </p>
                  <p className="text-xs text-red-600 opacity-0 group-hover:opacity-100 transition-opacity mt-1">
                    Click to view →
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

      {/* Build stamp for deployment verification */}
      {process.env.REACT_APP_BUILD_SHA && (
        <footer className="text-center py-2 text-xs text-gray-400" data-testid="build-stamp">
          Build: {process.env.REACT_APP_BUILD_SHA}
        </footer>
      )}
    </div>
  );
};

export default ClientDashboard;
