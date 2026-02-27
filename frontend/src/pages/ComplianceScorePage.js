import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import api from '../api/client';
import { toast } from 'sonner';
import { 
  TrendingUp,
  ArrowLeft,
  Building2,
  CheckCircle,
  Clock,
  AlertTriangle,
  FileText,
  Info,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Target,
  Calendar,
  RefreshCw,
  LogOut,
  Home,
  Sparkles,
  Zap,
  HelpCircle,
  Download,
  FileDown,
  Upload,
  ExternalLink,
  X,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from '../components/ui/tooltip';
import { Skeleton } from '../components/ui/skeleton';

const ComplianceScorePage = () => {
  const { user, logout } = useAuth();
  const { hasFeature } = useEntitlements();
  const navigate = useNavigate();
  const canExportScore = hasFeature('reports_pdf'); // Portfolio and Professional only
  const [scoreData, setScoreData] = useState(null);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [clientData, setClientData] = useState(null);
  const [showMethodology, setShowMethodology] = useState(false);
  const [showDefinitionsModal, setShowDefinitionsModal] = useState(false);
  const [showAdvancedDetails, setShowAdvancedDetails] = useState(false);
  const [driversFilterPropertyId, setDriversFilterPropertyId] = useState(null);
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  const handleDownloadPdf = async () => {
    setExportingPdf(true);
    try {
      const res = await api.get('/reports/score-explanation.pdf', { responseType: 'blob' });
      const disposition = res.headers['content-disposition'];
      const filename = disposition?.match(/filename="?([^";\n]+)"?/)?.[1] || `compliance_score_summary_${new Date().toISOString().slice(0, 10)}.pdf`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(`Export generated at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('Upgrade required for PDF reports');
      } else {
        toast.error('Export failed, please try again');
      }
    } finally {
      setExportingPdf(false);
    }
  };

  const handleDownloadCsv = async () => {
    setExportingCsv(true);
    try {
      const res = await api.get('/reports/score-drivers.csv', { responseType: 'blob' });
      const disposition = res.headers['content-disposition'];
      const filename = disposition?.match(/filename="?([^";\n]+)"?/)?.[1] || `score_drivers_${new Date().toISOString().slice(0, 10)}.csv`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      toast.success(`Export generated at ${new Date().toLocaleTimeString()}`);
    } catch (err) {
      if (err.response?.status === 403) {
        toast.error('Upgrade required for CSV reports');
      } else {
        toast.error('Export failed, please try again');
      }
    } finally {
      setExportingCsv(false);
    }
  };

  const formatRelativeTime = (iso) => {
    if (!iso) return null;
    try {
      const d = new Date(iso);
      const now = new Date();
      const sec = Math.floor((now - d) / 1000);
      if (sec < 60) return 'Just now';
      const min = Math.floor(sec / 60);
      if (min < 60) return `${min} min ago`;
      const hr = Math.floor(min / 60);
      if (hr < 24) return `${hr} hour${hr !== 1 ? 's' : ''} ago`;
      const day = Math.floor(hr / 24);
      if (day < 30) return `${day} day${day !== 1 ? 's' : ''} ago`;
      return d.toLocaleDateString();
    } catch {
      return null;
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [scoreRes, dashboardRes, reqRes] = await Promise.all([
        api.get('/client/compliance-score'),
        api.get('/client/dashboard'),
        api.get('/client/requirements')
      ]);
      setScoreData(scoreRes.data);
      setClientData(dashboardRes.data);
      setProperties(dashboardRes.data.properties || []);
      setRequirements(reqRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  };

  const getPropertyScoreContribution = (propertyId) => {
    const propertyReqs = requirements.filter(r => r.property_id === propertyId);
    if (propertyReqs.length === 0) return { score: 100, count: 0, breakdown: {} };
    
    const compliant = propertyReqs.filter(r => r.status === 'COMPLIANT').length;
    const expiring = propertyReqs.filter(r => r.status === 'EXPIRING_SOON').length;
    const overdue = propertyReqs.filter(r => r.status === 'OVERDUE').length;
    const pending = propertyReqs.filter(r => r.status === 'PENDING').length;
    
    const score = Math.round(((compliant * 100) + (pending * 70) + (expiring * 40)) / propertyReqs.length);
    
    return {
      score,
      count: propertyReqs.length,
      breakdown: { compliant, expiring, overdue, pending }
    };
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <header className="bg-midnight-blue text-white shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex justify-between items-center">
              <Skeleton className="h-8 w-48 bg-white/20" />
              <Skeleton className="h-6 w-24 bg-white/20" />
            </div>
          </div>
        </header>
        <nav className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex space-x-8">
              <Skeleton className="h-10 w-24" />
              <Skeleton className="h-10 w-36" />
            </div>
          </div>
        </nav>
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-end gap-2 mb-4">
            <Skeleton className="h-9 w-48" />
            <Skeleton className="h-9 w-44" />
          </div>
          <Button variant="ghost" size="sm" className="mb-6" disabled>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <Card className="mb-6 border-2 border-gray-200">
            <CardContent className="pt-6">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
                <div className="flex items-center gap-6">
                  <Skeleton className="w-32 h-32 rounded-full shrink-0" />
                  <div className="space-y-2">
                    <Skeleton className="h-8 w-32" />
                    <Skeleton className="h-5 w-64" />
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-4 w-56" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <Skeleton className="h-20 rounded-lg" />
                  <Skeleton className="h-20 rounded-lg" />
                  <Skeleton className="h-20 rounded-lg" />
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="mb-8">
            <CardHeader className="pb-2">
              <Skeleton className="h-5 w-28" />
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-5 w-32 mt-3" />
            </CardContent>
          </Card>
          <Card className="mb-8">
            <CardHeader>
              <Skeleton className="h-6 w-56" />
            </CardHeader>
            <CardContent className="border-t">
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-32 rounded-lg" />
                ))}
              </div>
            </CardContent>
          </Card>
          <Card className="mb-8">
            <CardHeader>
              <Skeleton className="h-6 w-72" />
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-[80%]" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <Skeleton className="h-6 w-40" />
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Skeleton className="h-20 rounded-lg" />
                <Skeleton className="h-20 rounded-lg" />
                <Skeleton className="h-20 rounded-lg" />
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  const colorClass = scoreData?.color === 'green' ? 'text-green-600' :
                     scoreData?.color === 'amber' ? 'text-amber-600' :
                     scoreData?.color === 'red' ? 'text-red-600' : 'text-gray-600';
  
  const bgColorClass = scoreData?.color === 'green' ? 'bg-green-50 border-green-200' :
                       scoreData?.color === 'amber' ? 'bg-amber-50 border-amber-200' :
                       scoreData?.color === 'red' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200';

  return (
    <TooltipProvider>
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
              {clientData?.client?.customer_reference && (
                <span className="px-3 py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-sm">
                  {clientData.client.customer_reference}
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
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/dashboard')}
            >
              <Home className="w-4 h-4 mr-2" />
              Dashboard
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Compliance Score
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="compliance-score-page">
        {/* Export buttons: Portfolio and Professional only */}
        {canExportScore && (
          <div className="flex flex-wrap items-center justify-end gap-2 mb-4">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadPdf}
              disabled={exportingPdf}
            >
              {exportingPdf ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
              Download score explanation (PDF)
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadCsv}
              disabled={exportingCsv}
            >
              {exportingCsv ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <FileDown className="w-4 h-4 mr-2" />}
              Export score drivers (CSV)
            </Button>
          </div>
        )}
        {/* Back Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/dashboard')}
          className="text-gray-600 hover:text-midnight-blue mb-6"
          data-testid="back-to-dashboard"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Button>

        {/* Main Score Card */}
        <Card className={`mb-6 border-2 ${bgColorClass}`}>
          <CardContent className="pt-6">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              {/* Score Display */}
              <div className="flex items-center gap-6">
                <div className={`w-32 h-32 rounded-full border-8 flex items-center justify-center ${
                  scoreData?.color === 'green' ? 'border-green-500 bg-green-100' :
                  scoreData?.color === 'amber' ? 'border-amber-500 bg-amber-100' :
                  scoreData?.color === 'red' ? 'border-red-500 bg-red-100' : 'border-gray-300 bg-gray-100'
                }`}>
                  <div className="text-center">
                    <p className={`text-4xl font-bold ${colorClass}`}>{scoreData?.score ?? 0}</p>
                    <p className="text-sm text-gray-500">/100</p>
                  </div>
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className={`text-3xl font-bold ${colorClass}`}>Grade {scoreData?.grade}</span>
                    <Target className={`w-6 h-6 ${colorClass}`} />
                    {scoreData?.score_last_calculated_at && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-sm font-normal text-gray-500">
                            Last recalculated: {formatRelativeTime(scoreData.score_last_calculated_at)}
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>{scoreData.score_last_calculated_at}</TooltipContent>
                      </Tooltip>
                    )}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium">
                          Portfolio Score (Weighted)
                          <HelpCircle className="w-3.5 h-3.5" />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        Portfolio score is a weighted summary across properties using applicable tracked items per property.
                      </TooltipContent>
                    </Tooltip>
                    {scoreData?.data_completeness_percent != null ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-teal-50 text-teal-800 text-xs font-medium">
                            Data completeness: {scoreData.data_completeness_percent}%
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-xs">
                          Completeness is the percentage of applicable tracked items with verified evidence and dates confirmed.
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-gray-100 text-gray-500 text-xs font-medium">
                            Data completeness: —
                          </span>
                        </TooltipTrigger>
                        <TooltipContent>Not yet calculated</TooltipContent>
                      </Tooltip>
                    )}
                  </div>
                  <p className="text-lg text-gray-700">{scoreData?.message}</p>
                  <p className="text-sm text-gray-600 mt-1">
                    Informational indicator based on portal records. Not legal advice.
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    Based on {scoreData?.stats?.total_requirements ?? 0} tracked items across {scoreData?.properties_count ?? 0} {scoreData?.properties_count === 1 ? 'property' : 'properties'}.
                    {scoreData?.properties_count != null && scoreData.properties_count > 1 && (
                      <span className="block mt-0.5">Your overall score is the average of each property&apos;s score.</span>
                    )}
                  </p>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-green-600">{scoreData?.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-600">Valid</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-amber-600">{scoreData?.stats?.expiring_soon || 0}</p>
                  <p className="text-xs text-gray-600">Expiring Soon</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-red-600">{scoreData?.stats?.overdue || 0}</p>
                  <p className="text-xs text-gray-600">Overdue</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Score scope & definitions block */}
        <Card className="mb-8">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-midnight-blue">Score scope</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-700">
            <ul className="list-disc list-inside space-y-1">
              <li><strong>What&apos;s included:</strong> Applicable tracked items for each property (e.g., Gas Safety, EICR, EPC, Licence if configured).</li>
              <li><strong>What&apos;s excluded:</strong> Council-specific rules unless configured. Optional uploads not tracked. Evidence not uploaded/confirmed.</li>
              <li><strong>How &apos;tracked items&apos; are counted:</strong> An item is tracked only if marked applicable for this property.</li>
              <li><strong>How it updates:</strong> Recalculates automatically when documents, dates, applicability, or status changes.</li>
            </ul>
            <button
              type="button"
              onClick={() => setShowDefinitionsModal(true)}
              className="text-electric-teal hover:underline font-medium text-sm mt-2"
            >
              View definitions
            </button>
          </CardContent>
        </Card>

        {/* How Score is Calculated - Expandable */}
        <Card className="mb-8" data-testid="score-methodology">
          <CardHeader 
            className="cursor-pointer hover:bg-gray-50"
            onClick={() => setShowMethodology(!showMethodology)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Info className="w-5 h-5 text-electric-teal" />
                How This Score is Calculated
              </CardTitle>
              {showMethodology ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showMethodology && (
            <CardContent className="border-t">
              <div className="space-y-6">
                {scoreData?.properties_count != null && scoreData.properties_count > 1 && (
                  <p className="text-sm text-gray-600 p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <strong>Multiple properties:</strong> Your overall score is the average of each property&apos;s score. Each property has its own score from its requirements and documents; the number shown is the average across all {scoreData.properties_count} properties.
                  </p>
                )}
                {/* Weighting Model - standardised card template */}
                <div>
                  <h4 className="font-semibold text-midnight-blue mb-3">Score Weighting Model</h4>
                  <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-blue-700">Status</span>
                        <span className="text-lg font-bold text-blue-700">{scoreData?.weights?.status ?? '35%'}</span>
                      </div>
                      <p className="text-xs text-blue-600 mb-1">What it measures: weighted status of tracked items (valid, expiring, overdue).</p>
                      <p className="text-sm font-semibold text-blue-800">Your result: {scoreData?.components?.status?.score ?? scoreData?.breakdown?.status_score?.toFixed?.(0) ?? 0}%</p>
                      <p className="text-xs text-blue-700 mt-1">Why: {scoreData?.components?.status?.valid ?? scoreData?.stats?.compliant ?? 0} valid • {scoreData?.components?.status?.expiring ?? scoreData?.stats?.expiring_soon ?? 0} expiring • {scoreData?.components?.status?.overdue ?? scoreData?.stats?.overdue ?? 0} overdue</p>
                    </div>
                    <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-purple-700">Timeline</span>
                        <span className="text-lg font-bold text-purple-700">{scoreData?.weights?.expiry ?? '25%'}</span>
                      </div>
                      <p className="text-xs text-purple-600 mb-1">What it measures: days until next critical expiry.</p>
                      <p className="text-sm font-semibold text-purple-800">Your result: {scoreData?.components?.timeline?.score ?? scoreData?.breakdown?.expiry_score?.toFixed?.(0) ?? 0}%</p>
                      <p className="text-xs text-purple-700 mt-1">Why: {scoreData?.components?.timeline?.due_0_30 ?? 0} due in 30 days • {scoreData?.components?.timeline?.overdue ?? scoreData?.stats?.overdue ?? 0} overdue</p>
                    </div>
                    <div className="p-4 bg-teal-50 rounded-lg border border-teal-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-teal-700">Documents</span>
                        <span className="text-lg font-bold text-teal-700">{scoreData?.weights?.documents ?? '15%'}</span>
                      </div>
                      <p className="text-xs text-teal-600 mb-1">What it measures: percentage of tracked items with verified evidence.</p>
                      <p className="text-sm font-semibold text-teal-800">Your result: {scoreData?.components?.documents?.score ?? scoreData?.breakdown?.document_score?.toFixed?.(0) ?? 0}%</p>
                      <p className="text-xs text-teal-700 mt-1">Why: {scoreData?.components?.documents?.evidence_coverage_percent ?? scoreData?.stats?.verified_coverage_percent ?? 0}/{scoreData?.stats?.total_requirements ?? 0} items have evidence</p>
                    </div>
                    <div className="p-4 bg-red-50 rounded-lg border border-red-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-red-700">Urgency Impact</span>
                        <span className="text-lg font-bold text-red-700">{scoreData?.weights?.overdue_penalty ?? '15%'}</span>
                      </div>
                      <p className="text-xs text-red-600 mb-1">What it measures: penalty for overdue items.</p>
                      <p className="text-sm font-semibold text-red-800">Your result: {scoreData?.components?.urgency?.score ?? scoreData?.breakdown?.overdue_penalty_score?.toFixed?.(0) ?? 0}%</p>
                      <p className="text-xs text-red-700 mt-1">Why: {scoreData?.components?.urgency?.overdue ?? scoreData?.stats?.overdue ?? 0} overdue items increase urgency impact</p>
                    </div>
                  </div>
                </div>

                {/* Advanced details accordion */}
                <div className="border-t pt-4">
                  <button
                    type="button"
                    onClick={() => setShowAdvancedDetails(!showAdvancedDetails)}
                    className="flex items-center gap-2 text-sm font-medium text-midnight-blue hover:underline"
                  >
                    {showAdvancedDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    Advanced details
                  </button>
                  {showAdvancedDetails && (
                    <div className="mt-3 p-4 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700 space-y-2">
                      <p>Status: COMPLIANT (100pts), PENDING (70pts), EXPIRING_SOON (40pts), OVERDUE (0pts).</p>
                      <p>Timeline: 90+ days (100pts), 60+ (90pts), 30+ (75pts), 14+ (50pts), 7+ (30pts), past due (0–15pts).</p>
                      <p>Documents: Only verified uploads count toward coverage.</p>
                      <p>Urgency: Each overdue item reduces the penalty component score.</p>
                      {(scoreData?.score_model_version || scoreData?.model_updated_at) && (
                        <p className="pt-2 border-t border-gray-200 font-medium">
                          Model: CVP Score v{scoreData.score_model_version ?? '—'}. Model updated: {scoreData.model_updated_at ?? '—'}
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Concrete Breakdown */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold text-midnight-blue mb-3">Your Current Status</h4>
                  <div className="grid md:grid-cols-3 gap-4 text-sm">
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                      <div>
                        <p className="font-medium">Status Component</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.compliant || 0}/{scoreData?.stats?.total_requirements || 0} tracked items currently valid
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <Clock className="w-5 h-5 text-amber-600" />
                      <div>
                        <p className="font-medium">Expiry Timeline</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.expiring_soon ?? 0} items due within 30 days
                          {scoreData?.stats?.days_until_next_expiry != null && (
                            <span className="block text-xs">
                              Next expiry: {scoreData.stats.days_until_next_expiry} days
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-gray-500 mt-1">Overdue items are not counted as &apos;due soon&apos; because their due date has already passed.</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <FileText className="w-5 h-5 text-teal-600" />
                      <div>
                        <p className="font-medium">Documents</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.documents_uploaded ?? 0} documents uploaded
                          <span className="block text-xs">
                            {(scoreData?.stats?.verified_coverage_percent ?? scoreData?.stats?.document_coverage_percent) != null ? `${Number(scoreData.stats.verified_coverage_percent ?? scoreData.stats.document_coverage_percent).toFixed(0)}%` : '—'} tracked item coverage
                          </span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Score drivers */}
        <Card className="mb-8" id="score-drivers">
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-electric-teal" />
              Score drivers (what is affecting your score)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!(scoreData?.drivers?.length) ? (
              <p className="text-gray-500 py-6 text-center">No issues detected based on current portal records.</p>
            ) : (
              <>
                {scoreData.drivers.some(d => !d.property_id || !d.requirement_id) && (
                  <p className="text-sm text-gray-600 mb-3">Some drivers may be hidden until evidence is uploaded or dates are confirmed.</p>
                )}
                {/* Desktop: table */}
                <div className="hidden md:block overflow-x-auto -mx-4 sm:mx-0">
                  <div className="min-w-[640px] md:min-w-0">
                    <table className="w-full text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-gray-200 text-left text-gray-600 font-medium">
                          <th className="py-2 pr-2">Requirement</th>
                          <th className="py-2 pr-2">Property</th>
                          <th className="py-2 pr-2">Status</th>
                          <th className="py-2 pr-2">Date used</th>
                          <th className="py-2 pr-2">Evidence</th>
                          <th className="py-2 pl-2">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(driversFilterPropertyId ? scoreData.drivers.filter(d => d.property_id === driversFilterPropertyId) : scoreData.drivers).map((d, idx) => (
                          <tr key={d.requirement_id || idx} className="border-b border-gray-100 hover:bg-gray-50">
                            <td className="py-3 pr-2">{d.requirement_name || '—'}</td>
                            <td className="py-3 pr-2">{d.property_name || d.property_id || '—'}</td>
                            <td className="py-3 pr-2">
                              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                d.status === 'OVERDUE' ? 'bg-red-100 text-red-700' :
                                d.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-700' :
                                d.status === 'MISSING_EVIDENCE' ? 'bg-orange-100 text-orange-700' :
                                d.status === 'NEEDS_CONFIRMATION' ? 'bg-amber-100 text-amber-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {d.status === 'OVERDUE' ? 'Overdue' : d.status === 'EXPIRING_SOON' ? 'Expiring' : d.status === 'MISSING_EVIDENCE' ? 'Missing evidence' : d.status === 'NEEDS_CONFIRMATION' ? 'Needs confirmation' : d.status}
                              </span>
                            </td>
                            <td className="py-3 pr-2">
                              {d.date_used ? new Date(d.date_used).toLocaleDateString() : '—'}
                              {d.date_confidence && d.date_confidence !== 'UNKNOWN' && (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <span className="ml-1 text-gray-400" title={d.date_confidence}>{d.date_confidence === 'VERIFIED' ? '✓' : '?'}</span>
                                  </TooltipTrigger>
                                  <TooltipContent>{d.date_confidence}</TooltipContent>
                                </Tooltip>
                              )}
                            </td>
                            <td className="py-3 pr-2">{d.evidence_uploaded ? 'Uploaded' : 'Not uploaded'}</td>
                            <td className="py-3 pl-2">
                              {d.actions?.includes('UPLOAD') && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="mr-1"
                                  onClick={(e) => { e.stopPropagation(); navigate(`/documents?property_id=${d.property_id}&requirement_id=${d.requirement_id}`); }}
                                >
                                  <Upload className="w-3.5 h-3.5 mr-1" />
                                  Upload document
                                </Button>
                              )}
                              {d.actions?.includes('CONFIRM') && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  className="mr-1"
                                  onClick={(e) => { e.stopPropagation(); navigate(`/documents?property_id=${d.property_id}&requirement_id=${d.requirement_id}`); }}
                                >
                                  Confirm details
                                </Button>
                              )}
                              {d.actions?.includes('VIEW') && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => { e.stopPropagation(); navigate(`/properties/${d.property_id}`); }}
                                >
                                  <ExternalLink className="w-3.5 h-3.5 mr-1" />
                                  View requirement
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                {/* Mobile: stacked cards */}
                <div className="md:hidden space-y-3">
                  {(driversFilterPropertyId ? scoreData.drivers.filter(d => d.property_id === driversFilterPropertyId) : scoreData.drivers).map((d, idx) => (
                    <div key={d.requirement_id || idx} className="p-4 border rounded-lg bg-gray-50 space-y-2">
                      <p className="font-medium text-midnight-blue">{d.requirement_name || '—'}</p>
                      <p className="text-sm text-gray-600">{d.property_name || d.property_id}</p>
                      <p className="text-sm">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          d.status === 'OVERDUE' ? 'bg-red-100 text-red-700' :
                          d.status === 'EXPIRING_SOON' ? 'bg-amber-100 text-amber-700' :
                          d.status === 'MISSING_EVIDENCE' ? 'bg-orange-100 text-orange-700' :
                          d.status === 'NEEDS_CONFIRMATION' ? 'bg-amber-100 text-amber-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {d.status === 'OVERDUE' ? 'Overdue' : d.status === 'EXPIRING_SOON' ? 'Expiring' : d.status === 'MISSING_EVIDENCE' ? 'Missing evidence' : d.status === 'NEEDS_CONFIRMATION' ? 'Needs confirmation' : d.status}
                        </span>
                        {' · '}
                        {d.date_used ? new Date(d.date_used).toLocaleDateString() : '—'} · {d.evidence_uploaded ? 'Uploaded' : 'Not uploaded'}
                      </p>
                      <div className="flex flex-wrap gap-2 pt-1">
                        {d.actions?.includes('UPLOAD') && (
                          <Button variant="outline" size="sm" onClick={() => navigate(`/documents?property_id=${d.property_id}&requirement_id=${d.requirement_id}`)}>
                            <Upload className="w-3.5 h-3.5 mr-1" /> Upload document
                          </Button>
                        )}
                        {d.actions?.includes('CONFIRM') && (
                          <Button variant="outline" size="sm" onClick={() => navigate(`/documents?property_id=${d.property_id}&requirement_id=${d.requirement_id}`)}>Confirm details</Button>
                        )}
                        {d.actions?.includes('VIEW') && (
                          <Button variant="outline" size="sm" onClick={() => navigate(`/properties/${d.property_id}`)}>
                            <ExternalLink className="w-3.5 h-3.5 mr-1" /> View requirement
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-2 flex justify-end">
                  {driversFilterPropertyId && (
                    <Button variant="ghost" size="sm" onClick={() => setDriversFilterPropertyId(null)}>
                      Clear filter
                    </Button>
                  )}
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Recommendations */}
        {scoreData?.recommendations?.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Zap className="w-5 h-5 text-electric-teal" />
                Actions to Improve Your Score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {scoreData.recommendations.map((rec, idx) => (
                  <div 
                    key={idx}
                    className={`flex items-start gap-3 p-4 rounded-lg border ${
                      rec.priority === 'high' ? 'bg-red-50 border-red-200' :
                      rec.priority === 'medium' ? 'bg-amber-50 border-amber-200' :
                      'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                      rec.priority === 'high' ? 'bg-red-500' :
                      rec.priority === 'medium' ? 'bg-amber-500' :
                      'bg-gray-400'
                    }`} />
                    <div className="flex-1">
                      <p className="font-medium text-gray-800">{rec.action}</p>
                      <p className="text-sm text-gray-500 mt-1">Potential impact: {rec.impact}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      rec.priority === 'high' ? 'bg-red-100 text-red-700' :
                      rec.priority === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {rec.priority.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Per-Property Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <Building2 className="w-5 h-5 text-electric-teal" />
              Score by Property
            </CardTitle>
          </CardHeader>
          <CardContent>
            {properties.length === 0 && (!scoreData?.property_breakdown?.length) ? (
              <p className="text-gray-500 text-center py-8">No properties to display</p>
            ) : (
              <div className="space-y-4">
                {(scoreData?.property_breakdown?.length ? scoreData.property_breakdown : properties.map(p => ({
                  property_id: p.property_id,
                  name: p.nickname || p.address_line_1,
                  postcode: p.postcode,
                  score: getPropertyScoreContribution(p.property_id).score,
                  valid: getPropertyScoreContribution(p.property_id).breakdown.compliant,
                  expiring: getPropertyScoreContribution(p.property_id).breakdown.expiring,
                  overdue: getPropertyScoreContribution(p.property_id).breakdown.overdue,
                }))).map((row) => {
                  const score = row.score ?? getPropertyScoreContribution(row.property_id).score;
                  const valid = row.valid ?? getPropertyScoreContribution(row.property_id).breakdown.compliant;
                  const expiring = row.expiring ?? getPropertyScoreContribution(row.property_id).breakdown.expiring;
                  const overdue = row.overdue ?? getPropertyScoreContribution(row.property_id).breakdown.overdue;
                  const propertyColor = score >= 80 ? 'green' : score >= 40 ? 'amber' : 'red';
                  return (
                    <div
                      key={row.property_id}
                      className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 p-4 border rounded-lg hover:bg-gray-50 transition-colors"
                      data-testid={`property-score-${row.property_id}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                          propertyColor === 'green' ? 'bg-green-100' :
                          propertyColor === 'amber' ? 'bg-amber-100' : 'bg-red-100'
                        }`}>
                          <Building2 className={`w-6 h-6 ${
                            propertyColor === 'green' ? 'text-green-600' :
                            propertyColor === 'amber' ? 'text-amber-600' : 'text-red-600'
                          }`} />
                        </div>
                        <div>
                          <h4 className="font-semibold text-midnight-blue">
                            {row.name || 'Property'}
                          </h4>
                          <p className="text-sm text-gray-500">{row.postcode || ''}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-4">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs ${valid > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                            {valid} valid
                          </span>
                          {expiring > 0 && (
                            <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                              {expiring} expiring
                            </span>
                          )}
                          {overdue > 0 && (
                            <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700">
                              {overdue} overdue
                            </span>
                          )}
                        </div>
                        <div className={`text-2xl font-bold ${
                          propertyColor === 'green' ? 'text-green-600' :
                          propertyColor === 'amber' ? 'text-amber-600' : 'text-red-600'
                        }`}>
                          {score}
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => { setDriversFilterPropertyId(row.property_id); document.getElementById('score-drivers')?.scrollIntoView({ behavior: 'smooth' }); }}
                            className="text-sm text-electric-teal hover:underline"
                          >
                            View drivers
                          </button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate(`/properties/${row.property_id}`)}
                          >
                            View property dashboard
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Definitions modal */}
        {showDefinitionsModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setShowDefinitionsModal(false)}>
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-midnight-blue">Definitions</h3>
                <button type="button" onClick={() => setShowDefinitionsModal(false)} className="p-1 rounded hover:bg-gray-100">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <dl className="space-y-3 text-sm text-gray-700">
                <div>
                  <dt className="font-medium text-gray-900">Valid</dt>
                  <dd>Tracked item is current and within date; evidence verified where required.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Expiring Soon</dt>
                  <dd>Due date or expiry falls within the configured window (e.g. 30–60 days).</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Overdue</dt>
                  <dd>Due date or expiry has passed; action needed.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Applicable vs Not applicable</dt>
                  <dd>An item is applicable if it is required for this property (e.g. Gas Safety for a gas-equipped property). Not applicable items are excluded from the score.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Date confidence (Verified vs Unverified)</dt>
                  <dd>Verified: date has been confirmed from document or manual entry. Unverified: date is estimated or not yet confirmed.</dd>
                </div>
                <div>
                  <dt className="font-medium text-gray-900">Tracked item</dt>
                  <dd>A requirement type (e.g. Gas Safety, EICR) that is marked applicable for a property and counted in the score.</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
      </main>
    </div>
    </TooltipProvider>
  );
};

export default ComplianceScorePage;
