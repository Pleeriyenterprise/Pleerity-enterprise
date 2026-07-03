import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import api, { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from '@/utils/portalNotifications';
import { 
  FileText, 
  ArrowLeft, 
  Download, 
  RefreshCw,
  FileSpreadsheet,
  ClipboardList,
  Shield,
  Calendar,
  Building2,
  Filter,
  Clock,
  Mail,
  Plus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Bell,
  X,
  ArrowUpRight,
  Eye,
  Package,
  BarChart2,
} from 'lucide-react';
import UpgradePrompt from '../components/UpgradePrompt';
import { operationalLabelForToken } from '../utils/presentationLanguage';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { PortalModePageBanner } from '../components/lifecycle/LifecycleShell';
import { buildSafeQueryPath } from '../utils/clientPortalNavigation';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import { jurisdictionSourceLabel } from '../utils/jurisdictionComplianceCopy';
import { presentPortalAnalyticsEvent } from '../utils/timelinePresent';
import { cn } from '../lib/utils';
import { getPropertyDisplayName } from '../utils/propertyDisplayName';
import { formatMinorUnits } from '../utils/rentMoney';
import { LIVE_EXPORT_DISCLOSURE, OPERATIONAL_ZIP_DISCLOSURE } from '../utils/reportingSemanticsLabels';
import {
  REPORT_ECOSYSTEM_NOTE,
  REPORT_CATALOG,
  enrichReportFromApi,
  sortReportsForCatalog,
  isSpecialtyReport,
  filenameFromContentDisposition,
  canonicalReportFilename,
} from '../utils/reportCatalogPresentation';
import ReportCatalogCard, { ReportSpecialtyLinkCard } from '../components/reports/ReportCatalogCard';

function reportPropertyOptionLabel(p) {
  const base = getPropertyDisplayName(p) || p.property_id;
  if (!p.effective_jurisdiction_label && !p.jurisdiction_source) return base;
  const j = p.effective_jurisdiction_label ? ` · ${p.effective_jurisdiction_label}` : '';
  const src = p.jurisdiction_source ? ` (Source: ${jurisdictionSourceLabel(p.jurisdiction_source)})` : '';
  return `${base}${j}${src}`;
}

const ReportsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const [availableReports, setAvailableReports] = useState([]);
  const [previousReports, setPreviousReports] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(null);
  const [properties, setProperties] = useState([]);
  const [selectedPropertyForReport, setSelectedPropertyForReport] = useState('');
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [creatingSchedule, setCreatingSchedule] = useState(false);
  const [upgradeRequiredDetail, setUpgradeRequiredDetail] = useState(null);
  const [selectedFilters, setSelectedFilters] = useState({
    property_id: '',
    start_date: '',
    end_date: '',
    format: 'csv'
  });
  const [scheduleForm, setScheduleForm] = useState({
    report_type: 'compliance_summary',
    frequency: 'weekly',
    recipients: ''
  });
  const [digests, setDigests] = useState([]);
  const [digestView, setDigestView] = useState(null);
  const [downloadingDigestId, setDownloadingDigestId] = useState(null);
  const [rentOpsSummary, setRentOpsSummary] = useState(null);
  const [rentOpsExpenseSummary, setRentOpsExpenseSummary] = useState(null);

  const hasReportsAccess = hasFeature('reports_pdf') || hasFeature('reports_csv');
  const hasRentOperations = hasFeature('rent_operations');
  const hasReportsPdf = hasFeature('reports_pdf');
  const hasScheduledReportsAccess = hasFeature('scheduled_reports');
  const hasAuditLogExport = hasFeature('audit_log_export');
  const [evidencePackJobs, setEvidencePackJobs] = useState([]);
  const [evidencePackLoading, setEvidencePackLoading] = useState(false);
  const [evidencePackGenerating, setEvidencePackGenerating] = useState(false);
  const [evidencePeriodStart, setEvidencePeriodStart] = useState('');
  const [evidencePeriodEnd, setEvidencePeriodEnd] = useState('');
  const [analyticsSummary, setAnalyticsSummary] = useState(null);
  const [analyticsSummaryLoading, setAnalyticsSummaryLoading] = useState(false);
  const [analyticsDays, setAnalyticsDays] = useState(30);

  const fetchData = useCallback(async () => {
    try {
      setUpgradeRequiredDetail(null);
      const [reportsRes, propsRes, schedulesRes, previousRes, digestsRes] = await Promise.all([
        api.get('/reports/available'),
        api.get('/client/properties'),
        api.get('/reports/schedules'),
        hasReportsAccess ? api.get('/reports').catch(() => ({ data: { reports: [] } })) : Promise.resolve({ data: { reports: [] } }),
        api.get('/portal/digests?limit=6').catch(() => ({ data: { digests: [] } }))
      ]);
      setAvailableReports(
        sortReportsForCatalog((reportsRes.data.reports || []).map(enrichReportFromApi)),
      );
      setProperties(propsRes.data.properties || []);
      setSchedules(schedulesRes.data.schedules || []);
      setPreviousReports(previousRes?.data?.reports || []);
      setDigests(digestsRes?.data?.digests || []);
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error('Failed to load reports');
      }
    } finally {
      setLoading(false);
    }
  }, [hasReportsAccess]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const fetchEvidencePackJobs = useCallback(async () => {
    if (!hasAuditLogExport) return;
    setEvidencePackLoading(true);
    try {
      const r = await clientAPI.listEvidencePackJobs({ limit: 10 });
      setEvidencePackJobs(r.data?.jobs || []);
    } catch {
      setEvidencePackJobs([]);
    } finally {
      setEvidencePackLoading(false);
    }
  }, [hasAuditLogExport]);

  useEffect(() => {
    fetchEvidencePackJobs();
  }, [fetchEvidencePackJobs]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setAnalyticsSummaryLoading(true);
      try {
        const r = await clientAPI.getAnalyticsSummary({ days: analyticsDays });
        if (!cancelled) setAnalyticsSummary(r.data);
      } catch {
        if (!cancelled) setAnalyticsSummary(null);
      } finally {
        if (!cancelled) setAnalyticsSummaryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [analyticsDays]);

  useEffect(() => {
    if (!hasRentOperations) return;
    let cancelled = false;
    Promise.all([
      clientAPI.getRentSummary(),
      clientAPI.getRentExpensesSummary(),
    ])
      .then(([rent, exp]) => {
        if (!cancelled) {
          setRentOpsSummary(rent.data);
          setRentOpsExpenseSummary(exp.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRentOpsSummary(null);
          setRentOpsExpenseSummary(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hasRentOperations]);

  const requestNewEvidencePack = async () => {
    const ps = (evidencePeriodStart || '').trim();
    const pe = (evidencePeriodEnd || '').trim();
    if ((ps && !pe) || (!ps && pe)) {
      toast.error('Invalid period—enter both dates, otherwise clear both.');
      return;
    }
    if (ps && pe && ps > pe) {
      toast.error('End date must be on or after start date.');
      return;
    }
    setEvidencePackGenerating(true);
    try {
      const body =
        ps && pe
          ? { period_start: ps.slice(0, 10), period_end: pe.slice(0, 10), background: true }
          : { background: true };
      const res = await clientAPI.createEvidencePackJob(body);
      const jobId = res.data?.job_id;
      await clientAPI.postAnalyticsEvent({ event: 'evidence_pack_requested', path: '/reports' }).catch(() => {});
      toast.success('Evidence pack is building — download will appear below when ready.');
      await fetchEvidencePackJobs();
      if (jobId) {
        const delay = (ms) => new Promise((r) => setTimeout(r, ms));
        (async () => {
          for (let i = 0; i < 90; i += 1) {
            await delay(2000);
            try {
              const r = await clientAPI.listEvidencePackJobs({ limit: 20 });
              const jobs = r.data?.jobs || [];
              setEvidencePackJobs(jobs);
              const j = jobs.find((x) => x.job_id === jobId);
              if (j?.status === 'completed') {
                toast.success('Evidence pack ready — download from the list below.');
                return;
              }
              if (j?.status === 'failed') {
                toast.error(typeof j.error === 'string' && j.error ? j.error : 'Evidence pack generation failed.');
                return;
              }
            } catch {
              /* continue polling */
            }
          }
          toast.info('Still building—refresh shortly.');
        })();
      }
    } catch (err) {
      const st = err.response?.status;
      const det = err.response?.data?.detail;
      if (st === 429) {
        toast.error(typeof det === 'string' ? det : 'Rate limit: maximum 5 evidence packs per 24 hours.');
      } else if (st === 403 && det?.upgrade_required) {
        setUpgradeRequiredDetail(det);
      } else if (st === 400) {
        toast.error(typeof det === 'string' ? det : 'Invalid export period');
      } else {
        toast.error(typeof det === 'string' ? det : 'Failed to generate evidence pack');
      }
    } finally {
      setEvidencePackGenerating(false);
    }
  };

  const downloadEvidencePackZip = async (jobId, filenameHint) => {
    try {
      const res = await clientAPI.downloadEvidencePackFile(jobId);
      const blob = new Blob([res.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const cd = res.headers['content-disposition'];
      let fname = filenameHint || `evidence-pack_${jobId}.zip`;
      if (cd) {
        const m = cd.match(/filename="?([^";]+)"?/);
        if (m) fname = m[1];
      }
      link.download = fname;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Evidence pack downloaded');
    } catch {
      toast.error('Download failed');
    }
  };

  const downloadReport = async (reportId, endpoint) => {
    if (isSpecialtyReport(reportId)) {
      toast.info('Open the dedicated section for this report type.');
      return;
    }
    setGenerating(reportId);
    
    try {
      // Build query params
      const params = new URLSearchParams();
      params.append('format', selectedFilters.format);
      
      if (reportId === 'requirements' && selectedFilters.property_id) {
        params.append('property_id', selectedFilters.property_id);
      }
      
      if (reportId === 'audit_logs') {
        if (selectedFilters.start_date) {
          params.append('start_date', selectedFilters.start_date);
        }
        if (selectedFilters.end_date) {
          params.append('end_date', selectedFilters.end_date);
        }
      }

      if (selectedFilters.format === 'csv') {
        // Download CSV file
        const response = await api.get(`${endpoint}?${params.toString()}`, {
          responseType: 'blob'
        });
        
        // Create download link
        const blob = new Blob([response.data], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        
        // Extract filename from Content-Disposition header or use default
        const contentDisposition = response.headers['content-disposition'];
        const filename = filenameFromContentDisposition(
          contentDisposition,
          canonicalReportFilename(reportId, 'csv'),
        );
        
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        toast.success('Report ready', {
          description: 'Snapshot of your current compliance position.',
        });
      } else if (!hasReportsPdf) {
        toast.info('Professional PDF exports are included on portfolio-scale plans. CSV export remains available.', {
          tier: 'important',
        });
      } else {
        const serverPdfByReport = {
          compliance_summary: '/reports/professional/compliance-summary',
          requirements: '/reports/professional/requirements',
        };
        const serverPath = serverPdfByReport[reportId];
        if (!serverPath) {
          toast.error('PDF export is not available for this report.');
          return;
        }
        const pdfParams = new URLSearchParams();
        if (reportId === 'requirements' && selectedFilters.property_id) {
          pdfParams.append('property_id', selectedFilters.property_id);
        }
        const qs = pdfParams.toString();
        const response = await api.get(qs ? `${serverPath}?${qs}` : serverPath, {
          responseType: 'blob',
        });
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filenameFromContentDisposition(
          response.headers['content-disposition'],
          canonicalReportFilename(reportId, 'pdf'),
        );
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        toast.success('Report ready', {
          description: 'Point-in-time server export with governance presentation.',
        });
      }
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error('Failed to generate report');
      }
      console.error('Report error:', error);
    } finally {
      setGenerating(null);
    }
  };

  const downloadDigestPdf = async (digest) => {
    if (hasReportsPdf && digest.digest_id) {
      try {
        setDownloadingDigestId(digest.digest_id);
        const res = await api.get(`/portal/digests/${digest.digest_id}/pdf`, { responseType: 'blob' });
        const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
        const link = document.createElement('a');
        link.href = url;
        const periodEnd = (digest.digest_period_end || digest.content?.period_end || '').slice(0, 10);
        link.setAttribute('download', `monthly-operations-intelligence-digest-${periodEnd || 'report'}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        toast.success('Operations intelligence digest downloaded', {
          description: res.headers['x-report-engine'] === 'reportlab_server'
            ? 'Server-rendered report with governance footer.'
            : undefined,
        });
        return;
      } catch (err) {
        toast.error('Digest PDF download failed');
        console.error(err);
        return;
      } finally {
        setDownloadingDigestId(null);
      }
    }
    toast.info('Server-rendered digest PDF requires portfolio-scale PDF reports. View the digest summary in the portal.', {
      tier: 'important',
    });
  };

  const createSchedule = async (e) => {
    e.preventDefault();
    setCreatingSchedule(true);
    
    try {
      const recipients = scheduleForm.recipients
        .split(',')
        .map(r => r.trim())
        .filter(r => r.length > 0);
      
      await api.post('/reports/schedules', {
        report_type: scheduleForm.report_type,
        frequency: scheduleForm.frequency,
        recipients: recipients.length > 0 ? recipients : null
      });
      
      toast.success('Report schedule created');
      setShowScheduleModal(false);
      setScheduleForm({ report_type: 'compliance_summary', frequency: 'weekly', recipients: '' });
      fetchData();
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error(error.response?.data?.detail || 'Failed to create schedule');
      }
    } finally {
      setCreatingSchedule(false);
    }
  };

  const toggleSchedule = async (scheduleId) => {
    try {
      const response = await api.patch(`/reports/schedules/${scheduleId}/toggle`);
      toast.success(response.data.message);
      fetchData();
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error('Failed to toggle schedule');
      }
    }
  };

  const deleteSchedule = async (scheduleId) => {
    if (!window.confirm('Are you sure you want to delete this scheduled report?')) {
      return;
    }
    
    try {
      await api.delete(`/reports/schedules/${scheduleId}`);
      toast.success('Schedule deleted');
      fetchData();
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error('Failed to delete schedule');
      }
    }
  };

  const getReportIcon = (reportId) => {
    switch (reportId) {
      case 'compliance_summary':
        return <FileSpreadsheet className="w-6 h-6 text-green-600" />;
      case 'requirements':
        return <ClipboardList className="w-6 h-6 text-blue-600" />;
      case 'audit_logs':
        return <Shield className="w-6 h-6 text-purple-600" />;
      default:
        return <FileText className="w-6 h-6 text-gray-600" />;
    }
  };

  const getFrequencyLabel = (freq) => {
    const labels = {
      daily: 'Every day',
      weekly: 'Every week',
      monthly: 'Every month'
    };
    return labels[freq] || freq;
  };

  const isAdmin = user?.role === 'ROLE_ADMIN';

  if (loading) {
    return (
      <div className={portalPageRoot} data-testid="reports-loading">
        <PortalLoadingPanel message={PORTAL_COPY.loadingReports} />
      </div>
    );
  }

  return (
    <div className={cn(portalPageRoot, 'bg-gray-50')} data-testid="reports-page">
      <PortalModePageBanner />
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4 min-w-0">
              <button
                type="button"
                onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/dashboard'))}
                className="text-slate-200 hover:text-white p-2 min-h-11 min-w-11 flex items-center justify-center shrink-0 rounded-lg hover:bg-white/10"
                data-testid="back-btn"
                aria-label="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="min-w-0">
                <h1 className="text-xl font-bold">Reports</h1>
                <p className="text-sm text-slate-200">Coherent compliance reporting — choose the right export for your audience</p>
              </div>
            </div>
            {hasScheduledReportsAccess ? (
              <Button
                onClick={() => setShowScheduleModal(true)}
                className="bg-electric-teal hover:bg-teal-600 min-h-11 w-full sm:w-auto shrink-0"
                data-testid="schedule-report-btn"
              >
                <Clock className="w-4 h-4 mr-2" />
                Schedule report
              </Button>
            ) : (
              <Button
                variant="outline"
                className="min-h-11 w-full shrink-0 border-white/30 text-white hover:bg-white/10 sm:w-auto"
                onClick={() => navigate(buildSafeQueryPath('/settings/billing', { upgrade_to: 'PLAN_2_PORTFOLIO' }))}
                data-testid="schedule-report-upgrade-btn"
              >
                <Calendar className="mr-2 h-4 w-4" aria-hidden />
                Scheduling & digests — Billing
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <p className="text-sm text-gray-600 mb-4 leading-relaxed" data-testid="reports-operating-helper">
          Each report serves a distinct purpose — executive posture, operational management, audit preparedness, portfolio intelligence, or evidentiary archive.
        </p>
        <Card className="mb-6 border border-gray-200 bg-gray-50/50" data-testid="reports-ecosystem-guide">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium text-midnight-blue">How reports work together</CardTitle>
          </CardHeader>
          <CardContent className="pt-0 space-y-3">
            <p className="text-sm text-gray-600 leading-relaxed">{REPORT_ECOSYSTEM_NOTE}</p>
            <ul className="text-sm text-gray-700 grid gap-1 sm:grid-cols-2">
              <li><span className="text-gray-500">External review:</span> Audit Evidence Pack</li>
              <li><span className="text-gray-500">Executive briefing:</span> Compliance Summary Report</li>
              <li><span className="text-gray-500">Day-to-day obligations:</span> Requirements Report</li>
              <li><span className="text-gray-500">Remediation prep:</span> Evidence Readiness Report</li>
              <li><span className="text-gray-500">Monthly oversight:</span> Monthly Operations Intelligence Digest</li>
              <li><span className="text-gray-500">Structured data:</span> CSV exports where available</li>
            </ul>
          </CardContent>
        </Card>

        {hasReportsAccess && (
          <>
            <Card className="mb-6" data-testid="format-selection-card">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base font-medium">
                  <Filter className="w-4 h-4" />
                  Export settings
                </CardTitle>
                <p className="text-xs text-gray-500 mt-1 font-normal">
                  PDF — presentation and governance view · CSV — structured operational export
                </p>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
                    <select
                      value={selectedFilters.format}
                      onChange={(e) => setSelectedFilters({ ...selectedFilters, format: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-sm"
                      data-testid="format-select"
                    >
                      <option value="csv">CSV — structured data</option>
                      <option value="pdf">PDF — presentation view</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Property filter</label>
                    <select
                      value={selectedFilters.property_id}
                      onChange={(e) => setSelectedFilters({ ...selectedFilters, property_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-sm"
                      data-testid="property-filter"
                    >
                      <option value="">All properties</option>
                      {properties.map((p) => (
                        <option key={p.property_id} value={p.property_id}>
                          {reportPropertyOptionLabel(p)}
                        </option>
                      ))}
                    </select>
                  </div>
                  {isAdmin && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Date range (audit log)</label>
                      <div className="flex gap-2">
                        <input
                          type="date"
                          value={selectedFilters.start_date}
                          onChange={(e) => setSelectedFilters({ ...selectedFilters, start_date: e.target.value })}
                          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
                          data-testid="start-date"
                        />
                        <input
                          type="date"
                          value={selectedFilters.end_date}
                          onChange={(e) => setSelectedFilters({ ...selectedFilters, end_date: e.target.value })}
                          className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm"
                          data-testid="end-date"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-catalog">
              Report catalog
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-8" data-testid="reports-grid">
              {availableReports.map((report) => {
                if (report.id === 'audit_evidence_pack') {
                  return (
                    <ReportSpecialtyLinkCard
                      key={report.id}
                      report={report}
                      icon={getReportIcon(report.id)}
                      to="/reports/audit-pack"
                      label="Open Audit Evidence Pack"
                    />
                  );
                }
                if (report.id === 'evidence_readiness') {
                  return (
                    <ReportCatalogCard
                      key={report.id}
                      report={report}
                      icon={getReportIcon(report.id)}
                      selectedFormat="pdf"
                      generating={generating}
                      specialtyAction={
                        <Button
                          variant="outline"
                          className="w-full"
                          onClick={() => document.getElementById('evidence-readiness-card')?.scrollIntoView({ behavior: 'smooth' })}
                          data-testid="report-scroll-evidence-readiness"
                        >
                          Generate Evidence Readiness PDF
                        </Button>
                      }
                    />
                  );
                }
                return (
                  <ReportCatalogCard
                    key={report.id}
                    report={report}
                    icon={getReportIcon(report.id)}
                    selectedFormat={selectedFilters.format}
                    generating={generating}
                    onDownload={downloadReport}
                  />
                );
              })}
            </div>
          </>
        )}
        <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-audit-evidence-packs">
          Audit Evidence Packs
        </h2>
        {hasReportsPdf && (
          <Card className="mb-6 border border-teal-100 bg-teal-50/40" data-testid="reports-audit-evidence-pack-cta">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{REPORT_CATALOG.audit_evidence_pack.canonicalName}</CardTitle>
            </CardHeader>
            <CardContent className="pt-0 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-gray-700 max-w-2xl">
                {REPORT_CATALOG.audit_evidence_pack.purpose} Governed ZIP with manifest checksums — for external review, not tenant delivery.
              </p>
              <Button asChild className="bg-electric-teal hover:bg-teal-600 shrink-0 w-full sm:w-auto">
                <Link to="/reports/audit-pack">Open audit evidence pack</Link>
              </Button>
            </CardContent>
          </Card>
        )}
        {upgradeRequiredDetail && (
          <div className="mb-6" data-testid="reports-upgrade-required">
            <UpgradeRequired upgradeDetail={upgradeRequiredDetail} showBackToDashboard />
          </div>
        )}
        {/* One discoverability slot: contextual 403 detail OR full reports gate, not both */}
        {!hasReportsAccess && !upgradeRequiredDetail && (
          <div className="mb-6" data-testid="reports-upgrade-prompt">
            <UpgradePrompt
              featureName="Advanced Reports"
              featureDescription="Download compliance reports as PDF and CSV documents. Schedule automated reports to be sent to your email."
              requiredPlan="PLAN_2_PORTFOLIO"
              requiredPlanName="Portfolio"
              variant="card"
            />
          </div>
        )}
        {hasRentOperations && rentOpsSummary && (
          <>
            <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-operational-rent">
              Operational rent & expenses
            </h2>
            <Card className="mb-6 border border-gray-200" data-testid="reports-operational-rent-card">
              <CardHeader>
                <CardTitle className="text-base">Portfolio operational summary</CardTitle>
                <p className="text-xs text-gray-500 mt-1">
                  Operational estimates only — not accounting, tax, or bookkeeping reports.{' '}
                  <Link to="/operations/rent" className="text-electric-teal underline">Open Rent Operations</Link>
                </p>
              </CardHeader>
              <CardContent className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Rent collected (month)</p>
                  <p className="font-semibold">{formatMinorUnits(rentOpsSummary.rent_collected_this_month_minor)}</p>
                </div>
                <div>
                  <p className="text-gray-500">Overdue periods</p>
                  <p className="font-semibold text-orange-600">{rentOpsSummary.overdue_count ?? 0}</p>
                </div>
                <div>
                  <p className="text-gray-500">Outstanding balance</p>
                  <p className="font-semibold">{formatMinorUnits(rentOpsSummary.total_outstanding_minor)}</p>
                </div>
                {rentOpsExpenseSummary && (
                  <>
                    <div>
                      <p className="text-gray-500">Expenses (period)</p>
                      <p className="font-semibold">{formatMinorUnits(rentOpsExpenseSummary.total_expenses_minor)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Compliance-related expenses</p>
                      <p className="font-semibold">{formatMinorUnits(rentOpsExpenseSummary.compliance_related_total_minor)}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Net operational estimate</p>
                      <p className="font-semibold">
                        {formatMinorUnits(
                          (rentOpsSummary.rent_collected_this_month_minor || 0) -
                            (rentOpsExpenseSummary.total_expenses_minor || 0),
                        )}
                      </p>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </>
        )}
        <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-compliance-reports">
          Compliance Reports
        </h2>
        <Card className="mb-6 border border-gray-200" data-testid="portal-analytics-summary-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-electric-teal" />
              Portal activity (first-party)
            </CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Aggregated counts of allowlisted portal events for your account (not a full analytics warehouse).
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-600">Period</span>
              {[7, 30, 90].map((d) => (
                <Button
                  key={d}
                  type="button"
                  variant={analyticsDays === d ? 'default' : 'outline'}
                  size="sm"
                  className={analyticsDays === d ? 'bg-electric-teal hover:bg-teal-600' : ''}
                  onClick={() => setAnalyticsDays(d)}
                  data-testid={`analytics-summary-days-${d}`}
                >
                  {d}d
                </Button>
              ))}
            </div>
            {analyticsSummaryLoading ? (
              <p className="text-sm text-gray-500 flex items-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin" /> Loading summary…
              </p>
            ) : analyticsSummary ? (
              <div className="text-sm space-y-2">
                <p className="text-gray-700">
                  <span className="font-medium text-midnight-blue">{analyticsSummary.total_events ?? 0}</span> events
                  in the last {analyticsSummary.period_days ?? analyticsDays} days.
                </p>
                {(analyticsSummary.by_event || []).length > 0 ? (
                  <ul className="border border-gray-100 rounded-lg divide-y divide-gray-100 max-h-48 overflow-y-auto">
                    {analyticsSummary.by_event.map((row) => (
                      <li key={row.event} className="flex justify-between gap-2 px-3 py-2">
                        <span className="text-sm text-gray-800 truncate" title={row.event}>{presentPortalAnalyticsEvent(row.event)}</span>
                        <span className="text-gray-600 shrink-0">{row.count}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-gray-500">No recorded events in this window.</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500">Summary unavailable.</p>
            )}
          </CardContent>
        </Card>
        <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-scheduled-reports">
          Scheduled Reports
        </h2>
        {/* Monthly Digests - last 6 with View and Download PDF */}
        <Card className="mb-6" data-testid="digests-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="w-5 h-5 text-electric-teal" />
              Monthly Operations Intelligence Digests
            </CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Past monthly portfolio briefings sent to your email. View summary or download the digest PDF.
            </p>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500">Loading digests…</p>
            ) : digests.length === 0 ? (
              <p className="text-sm text-gray-500">No digests yet. Enable Monthly Operations Intelligence Digest in Notification Preferences to receive them.</p>
            ) : (
              <>
                <div className="md:hidden space-y-3">
                  {digests.map((d) => {
                    const periodStart = (d.digest_period_start || d.content?.period_start || '').slice(0, 10);
                    const periodEnd = (d.digest_period_end || d.content?.period_end || '').slice(0, 10);
                    const sentAt = d.sent_at ? new Date(d.sent_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—';
                    return (
                      <div key={d.digest_id} className="rounded-lg border border-gray-200 p-3 bg-white">
                        <p className="text-sm font-medium text-midnight-blue">{periodStart} – {periodEnd}</p>
                        <p className="text-xs text-gray-500 mt-1">Sent {sentAt}</p>
                        <div className="flex flex-col gap-2 mt-3">
                          <Button variant="outline" size="sm" className="min-h-11 w-full" onClick={() => setDigestView(d)} data-testid={`digest-view-${d.digest_id}`}>
                            <Eye className="w-4 h-4 mr-2" />
                            {PORTAL_COPY.viewDetails}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            className="min-h-11 w-full"
                            disabled={downloadingDigestId === d.digest_id}
                            onClick={() => {
                              setDownloadingDigestId(d.digest_id);
                              try {
                                downloadDigestPdf(d);
                                toast.success('Digest PDF downloaded');
                              } catch (err) {
                                toast.error('Failed to generate PDF');
                              } finally {
                                setDownloadingDigestId(null);
                              }
                            }}
                            data-testid={`digest-download-${d.digest_id}`}
                          >
                            {downloadingDigestId === d.digest_id ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                            Download PDF
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200">
                        <th className="text-left py-2 font-medium text-gray-700">Period</th>
                        <th className="text-left py-2 font-medium text-gray-700">Sent</th>
                        <th className="text-right py-2 font-medium text-gray-700">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {digests.map((d) => {
                        const periodStart = (d.digest_period_start || d.content?.period_start || '').slice(0, 10);
                        const periodEnd = (d.digest_period_end || d.content?.period_end || '').slice(0, 10);
                        const sentAt = d.sent_at ? new Date(d.sent_at).toLocaleDateString(undefined, { dateStyle: 'medium' }) : '—';
                        return (
                          <tr key={d.digest_id} className="border-b border-gray-100">
                            <td className="py-3 text-gray-800">{periodStart} – {periodEnd}</td>
                            <td className="py-3 text-gray-600">{sentAt}</td>
                            <td className="py-3 text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                className="mr-1"
                                onClick={() => setDigestView(d)}
                                data-testid={`digest-view-${d.digest_id}`}
                              >
                                <Eye className="w-4 h-4 mr-1" />
                                View
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={downloadingDigestId === d.digest_id}
                                onClick={() => {
                                  setDownloadingDigestId(d.digest_id);
                                  try {
                                    downloadDigestPdf(d);
                                    toast.success('Digest PDF downloaded');
                                  } catch (err) {
                                    toast.error('Failed to generate PDF');
                                  } finally {
                                    setDownloadingDigestId(null);
                                  }
                                }}
                                data-testid={`digest-download-${d.digest_id}`}
                              >
                                {downloadingDigestId === d.digest_id ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Download className="w-4 h-4 mr-1" />}
                                Download PDF
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </CardContent>
        </Card>
        <h2 className="text-lg font-semibold text-midnight-blue mb-3" data-testid="reports-section-regulatory-system-exports">
          Regulatory/System Exports
        </h2>
        {hasAuditLogExport ? (
          <Card className="mb-6 border border-gray-200" data-testid="evidence-pack-zip-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Package className="w-5 h-5 text-electric-teal" />
                Regulatory/System Export (CSV ZIP)
              </CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Structured CSV + JSON ZIP export for system handoff, accountant workflows, regulator data requests, or migration support.
                {OPERATIONAL_ZIP_DISCLOSURE}
                Limited to five exports per 24 hours. Optionally restrict rows to a UTC date range (properties CSV always lists your full portfolio for context).
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap gap-4 items-end">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Period start (optional)</label>
                  <input
                    type="date"
                    value={evidencePeriodStart}
                    onChange={(e) => setEvidencePeriodStart(e.target.value)}
                    className="border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                    data-testid="evidence-pack-period-start"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Period end (optional)</label>
                  <input
                    type="date"
                    value={evidencePeriodEnd}
                    onChange={(e) => setEvidencePeriodEnd(e.target.value)}
                    className="border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                    data-testid="evidence-pack-period-end"
                  />
                </div>
              </div>
              <Button
                onClick={requestNewEvidencePack}
                disabled={evidencePackGenerating}
                className="bg-electric-teal hover:bg-teal-600"
                data-testid="evidence-pack-generate-btn"
              >
                {evidencePackGenerating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                Generate new pack
              </Button>
              {evidencePackLoading ? (
                <p className="text-sm text-gray-500">Loading recent exports…</p>
              ) : evidencePackJobs.length === 0 ? (
                <p className="text-sm text-gray-500">No packs yet. Generate one to download.</p>
              ) : (
                <ul className="space-y-2 text-sm border border-gray-100 rounded-lg divide-y divide-gray-100">
                  {evidencePackJobs.map((j) => (
                    <li key={j.job_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                      <div>
                        <p className="font-medium text-midnight-blue">
                          {j.created_at ? new Date(j.created_at).toLocaleString() : j.job_id}
                        </p>
                        <p className="text-xs text-gray-500">
                          {j.period_start && j.period_end
                            ? `Period ${String(j.period_start).slice(0, 10)} – ${String(j.period_end).slice(0, 10)} · `
                            : 'Full snapshot · '}
                          {j.byte_size != null ? `${Math.round(Number(j.byte_size) / 1024)} KB` : ''}
                          {j.status && j.status !== 'completed' ? ` · ${j.status}` : ''}
                        </p>
                      </div>
                      {j.status === 'processing' ? (
                        <span className="text-xs text-amber-700 flex items-center gap-1">
                          <RefreshCw className="w-3 h-3 animate-spin" /> Building…
                        </span>
                      ) : null}
                      {j.status === 'completed' && j.gridfs_id ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => downloadEvidencePackZip(j.job_id, j.filename)}
                          data-testid={`evidence-pack-download-${j.job_id}`}
                        >
                          <Download className="w-4 h-4 mr-1" />
                          Download ZIP
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card className="mb-6 border border-gray-200" data-testid="reports-regulatory-export-gate-note">
            <CardContent className="pt-6">
              <p className="text-sm text-gray-600">
                Regulatory/System Exports require the regulatory export entitlement. Audit Evidence Pack remains available via Reports when PDF reports are enabled.
              </p>
            </CardContent>
          </Card>
        )}
        {digestView && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setDigestView(null)}>
            <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[min(90dvh,90vh)] overflow-hidden flex flex-col" onClick={e => e.stopPropagation()}>
              <div className="p-4 border-b border-gray-200 flex items-center justify-between">
                <h3 className="font-semibold text-midnight-blue">Monthly Operations Intelligence Digest</h3>
                <button type="button" onClick={() => setDigestView(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-4 overflow-y-auto">
                {(() => {
                  const c = digestView.content || {};
                  const periodStart = (digestView.digest_period_start || c.period_start || '').slice(0, 10);
                  const periodEnd = (digestView.digest_period_end || c.period_end || '').slice(0, 10);
                  const sentAt = digestView.sent_at ? new Date(digestView.sent_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—';
                  return (
                    <>
                      <p className="text-sm text-gray-600 mb-3">Period: {periodStart} – {periodEnd} · Sent: {sentAt}</p>
                      <ul className="list-disc list-inside space-y-1 text-sm text-gray-800">
                        <li>Properties: {c.properties_count ?? 0}</li>
                        <li>Total requirements: {c.total_requirements ?? 0}</li>
                        <li>Compliant: {c.compliant ?? 0}</li>
                        <li>Overdue: {c.overdue ?? 0}</li>
                        <li>Expiring soon: {c.expiring_soon ?? 0}</li>
                        <li>Documents uploaded (period): {c.documents_uploaded ?? 0}</li>
                      </ul>
                      <p className="text-xs text-gray-500 mt-4">This summary is for information only and does not constitute legal advice.</p>
                    </>
                  );
                })()}
              </div>
              <div className="p-4 border-t border-gray-200">
                <Button variant="outline" onClick={() => { downloadDigestPdf(digestView); setDigestView(null); toast.success('Digest PDF downloaded'); }}>
                  <Download className="w-4 h-4 mr-2" />
                  Download PDF
                </Button>
              </div>
            </div>
          </div>
        )}
        {/* Evidence Readiness PDF */}
        {hasReportsAccess && (
          <Card className="mb-6" id="evidence-readiness-card" data-testid="evidence-readiness-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 flex-wrap">
                <FileText className="w-5 h-5 text-electric-teal" />
                {REPORT_CATALOG.evidence_readiness.canonicalName}
                <span className="text-[11px] uppercase tracking-wide text-gray-500 border border-gray-200 rounded px-1.5 py-0.5 font-medium">
                  {REPORT_CATALOG.evidence_readiness.exportGrade}
                </span>
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">
                {REPORT_CATALOG.evidence_readiness.purpose}{' '}
                <span className="text-gray-500" data-testid="evidence-readiness-live-disclosure">{LIVE_EXPORT_DISCLOSURE}</span>
              </p>
              <p className="text-xs text-gray-500 mt-1">{REPORT_CATALOG.evidence_readiness.governanceNote}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  disabled={generating === 'evidence_readiness_portfolio'}
                  onClick={async () => {
                    setGenerating('evidence_readiness_portfolio');
                    try {
                      const res = await api.post('/reports/generate', { scope: 'portfolio' }, { responseType: 'blob' });
                      const url = window.URL.createObjectURL(new Blob([res.data]));
                      const link = document.createElement('a');
                      link.href = url;
                      link.setAttribute('download', `evidence_readiness_portfolio_${new Date().toISOString().slice(0, 10)}.pdf`);
                      document.body.appendChild(link);
                      link.click();
                      link.remove();
                      window.URL.revokeObjectURL(url);
                      toast.success('Evidence Readiness PDF downloaded');
                      fetchData();
                    } catch (err) {
                      if (err.response?.status === 403)
                        toast.info('PDF export is included on portfolio-scale plans. Use Billing to compare options.', {
                          tier: 'important',
                        });
                      else toast.error('Failed to generate report');
                    } finally {
                      setGenerating(null);
                    }
                  }}
                  className="bg-electric-teal hover:bg-teal-600"
                  data-testid="generate-evidence-readiness-pdf"
                >
                  {generating === 'evidence_readiness_portfolio' ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                  Generate portfolio PDF
                </Button>
                <div className="flex items-center gap-2">
                  <select
                    value={selectedPropertyForReport}
                    onChange={(e) => setSelectedPropertyForReport(e.target.value)}
                    className="px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-sm min-w-[200px]"
                    data-testid="evidence-readiness-property-select"
                  >
                    <option value="">Select property…</option>
                    {properties.map((p) => (
                      <option key={p.property_id} value={p.property_id}>
                        {reportPropertyOptionLabel(p)}
                      </option>
                    ))}
                  </select>
                  <Button
                    disabled={!selectedPropertyForReport || generating === 'evidence_readiness_property'}
                    onClick={async () => {
                      setGenerating('evidence_readiness_property');
                      try {
                        const res = await api.post('/reports/generate', { scope: 'property', property_id: selectedPropertyForReport }, { responseType: 'blob' });
                        const url = window.URL.createObjectURL(new Blob([res.data]));
                        const link = document.createElement('a');
                        link.href = url;
                        link.setAttribute('download', `evidence_readiness_property_${selectedPropertyForReport}_${new Date().toISOString().slice(0, 10)}.pdf`);
                        document.body.appendChild(link);
                        link.click();
                        link.remove();
                        window.URL.revokeObjectURL(url);
                        toast.success('Evidence Readiness PDF downloaded');
                        fetchData();
                      } catch (err) {
                        if (err.response?.status === 403)
                        toast.info('PDF export is included on portfolio-scale plans. Use Billing to compare options.', {
                          tier: 'important',
                        });
                        else toast.error('Failed to generate report');
                      } finally {
                        setGenerating(null);
                      }
                    }}
                    variant="outline"
                    data-testid="generate-evidence-readiness-property-pdf"
                  >
                    {generating === 'evidence_readiness_property' ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                    Generate property PDF
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
        {/* Previous Evidence Readiness reports */}
        {hasReportsAccess && previousReports.length > 0 && (
          <Card className="mb-6" data-testid="previous-reports-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="w-5 h-5" />
                Evidence Readiness history
              </CardTitle>
              <p className="text-sm text-gray-500 mt-1">
                Archived immutable snapshots — labels and scores reflect the generation boundary. Re-download returns the same frozen PDF. Use &quot;New snapshot&quot; for current portfolio state.
              </p>
            </CardHeader>
            <CardContent>
              <div className="md:hidden space-y-3">
                {previousReports.map((r) => (
                  <div key={r.report_id} className="rounded-lg border border-gray-200 p-3" data-testid={`previous-report-${r.report_id}`}>
                    <p className="text-sm font-medium text-midnight-blue">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      {r.scope === 'property' ? 'Property' : 'Portfolio'}
                      {r.property_id ? ` · ${properties.find((p) => p.property_id === r.property_id)?.address_line_1 || r.property_id}` : ''}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Score / risk: {r.score_at_time != null ? `${r.score_at_time}` : '—'} / {r.risk_level_at_time || '—'}
                    </p>
                    <div className="mt-3 flex flex-col gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="min-h-11 w-full"
                        disabled={generating === `download_${r.report_id}`}
                        onClick={async () => {
                          setGenerating(`download_${r.report_id}`);
                          try {
                            const res = await api.get(`/reports/${r.report_id}/download`, { responseType: 'blob' });
                            const url = window.URL.createObjectURL(new Blob([res.data]));
                            const link = document.createElement('a');
                            link.href = url;
                            link.setAttribute('download', `evidence_readiness_${r.scope}_${r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : 'report'}.pdf`);
                            document.body.appendChild(link);
                            link.click();
                            link.remove();
                            window.URL.revokeObjectURL(url);
                            toast.success('Immutable artifact downloaded', {
                              description: res.headers['x-report-determinism'] === 'immutable_artifact'
                                ? 'Same bytes as when this snapshot was created.'
                                : undefined,
                            });
                          } catch (err) {
                            toast.error('Download failed');
                          } finally {
                            setGenerating(null);
                          }
                        }}
                        data-testid={`download-report-${r.report_id}`}
                      >
                        {generating === `download_${r.report_id}` ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Download className="w-4 h-4 mr-2" />}
                        Download frozen copy
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="min-h-11 w-full text-xs"
                        disabled={generating === `new_${r.report_id}`}
                        onClick={async () => {
                          setGenerating(`new_${r.report_id}`);
                          try {
                            await api.post(
                              '/reports/generate',
                              { scope: r.scope, property_id: r.property_id || undefined },
                              { responseType: 'blob' }
                            );
                            toast.success('New immutable snapshot created', {
                              description: 'Based on current portfolio state. Prior snapshots remain downloadable unchanged.',
                            });
                            const reportsRes = await api.get('/reports/list');
                            setPreviousReports(reportsRes.data.reports || reportsRes.data || []);
                          } catch (err) {
                            toast.error('Failed to create new snapshot');
                          } finally {
                            setGenerating(null);
                          }
                        }}
                        data-testid={`new-snapshot-${r.report_id}`}
                      >
                        New snapshot (current data)
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="text-left py-2 font-medium">Date</th>
                      <th className="text-left py-2 font-medium">Scope</th>
                      <th className="text-left py-2 font-medium">Property</th>
                      <th className="text-left py-2 font-medium">Score / Risk</th>
                      <th className="text-right py-2 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previousReports.map((r) => (
                      <tr key={r.report_id} className="border-b border-gray-100" data-testid={`previous-report-${r.report_id}`}>
                        <td className="py-2">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                        <td className="py-2">{r.scope === 'property' ? 'Property' : 'Portfolio'}</td>
                        <td className="py-2">{r.property_id ? (properties.find(p => p.property_id === r.property_id)?.address_line_1 || r.property_id) : '—'}</td>
                        <td className="py-2">{r.score_at_time != null ? `${r.score_at_time}` : '—'} / {r.risk_level_at_time || '—'}</td>
                        <td className="py-2 text-right space-x-1">
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={generating === `download_${r.report_id}`}
                            onClick={async () => {
                              setGenerating(`download_${r.report_id}`);
                              try {
                                const res = await api.get(`/reports/${r.report_id}/download`, { responseType: 'blob' });
                                const url = window.URL.createObjectURL(new Blob([res.data]));
                                const link = document.createElement('a');
                                link.href = url;
                                link.setAttribute('download', `evidence_readiness_${r.scope}_${r.created_at ? new Date(r.created_at).toISOString().slice(0, 10) : 'report'}.pdf`);
                                document.body.appendChild(link);
                                link.click();
                                link.remove();
                                window.URL.revokeObjectURL(url);
                                toast.success('Immutable artifact downloaded');
                              } catch (err) {
                                toast.error('Download failed');
                              } finally {
                                setGenerating(null);
                              }
                            }}
                            data-testid={`download-report-${r.report_id}`}
                          >
                            {generating === `download_${r.report_id}` ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            title="New snapshot (current data)"
                            disabled={generating === `new_${r.report_id}`}
                            onClick={async () => {
                              setGenerating(`new_${r.report_id}`);
                              try {
                                await api.post(
                                  '/reports/generate',
                                  { scope: r.scope, property_id: r.property_id || undefined },
                                  { responseType: 'blob' }
                                );
                                toast.success('New immutable snapshot created');
                                const reportsRes = await api.get('/reports/list');
                                setPreviousReports(reportsRes.data.reports || reportsRes.data || []);
                              } catch (err) {
                                toast.error('Failed to create new snapshot');
                              } finally {
                                setGenerating(null);
                              }
                            }}
                            data-testid={`new-snapshot-${r.report_id}`}
                          >
                            {generating === `new_${r.report_id}` ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
        {/* Scheduled Reports Section */}
        {schedules.length > 0 && (
          <Card className="mb-6" data-testid="scheduled-reports-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="w-5 h-5" />
                Scheduled Reports ({schedules.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {schedules.map((schedule) => (
                  <div 
                    key={schedule.schedule_id}
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      schedule.is_active ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'
                    }`}
                    data-testid={`schedule-${schedule.schedule_id}`}
                  >
                    <div className="flex items-center gap-3">
                      <Mail className={`w-5 h-5 ${schedule.is_active ? 'text-green-600' : 'text-gray-400'}`} />
                      <div>
                        <div className="font-medium text-gray-900">
                          {operationalLabelForToken(schedule.report_type, { emptyLabel: 'Report' })}
                        </div>
                        <div className="text-sm text-gray-500">
                          {getFrequencyLabel(schedule.frequency)} • {schedule.recipients?.join(', ')}
                        </div>
                        <div className="text-xs text-gray-400 space-y-0.5">
                          {schedule.next_scheduled && (
                            <div>Next: {new Date(schedule.next_scheduled).toLocaleDateString()}</div>
                          )}
                          {schedule.last_sent && (
                            <div>Last sent: {new Date(schedule.last_sent).toLocaleString()}</div>
                          )}
                          {schedule.last_attempted_at && !schedule.last_sent && (
                            <div>Last attempted: {new Date(schedule.last_attempted_at).toLocaleString()}</div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleSchedule(schedule.schedule_id)}
                        className={`p-1 rounded ${schedule.is_active ? 'text-green-600' : 'text-gray-400'}`}
                        title={schedule.is_active ? 'Disable' : 'Enable'}
                        data-testid={`toggle-schedule-${schedule.schedule_id}`}
                      >
                        {schedule.is_active ? (
                          <ToggleRight className="w-6 h-6" />
                        ) : (
                          <ToggleLeft className="w-6 h-6" />
                        )}
                      </button>
                      <button
                        onClick={() => deleteSchedule(schedule.schedule_id)}
                        className="p-1 text-red-500 hover:text-red-700"
                        title="Delete"
                        data-testid={`delete-schedule-${schedule.schedule_id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        <div className="mt-8 p-4 bg-gray-50 rounded-lg border border-gray-200" data-testid="reports-trust-footer">
          <h4 className="font-medium text-midnight-blue text-sm mb-2">Export trust and scope</h4>
          <p className="text-xs text-gray-600 leading-relaxed">
            Server-generated PDFs are authoritative for external sharing. CSV exports are point-in-time operational data.
            Evidence Readiness history preserves immutable snapshots — re-download returns the same file.
            Audit Evidence Pack is the governed evidentiary archive; other reports support monitoring and management.
          </p>
        </div>
      </main>

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="schedule-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-midnight-blue">Schedule Report</h2>
                <button 
                  onClick={() => setShowScheduleModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="close-schedule-modal"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              <form onSubmit={createSchedule} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Report Type</label>
                  <select
                    value={scheduleForm.report_type}
                    onChange={(e) => setScheduleForm({...scheduleForm, report_type: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="schedule-report-type"
                  >
                    <option value="compliance_summary">{operationalLabelForToken('compliance_summary')}</option>
                    <option value="requirements">{operationalLabelForToken('requirements')}</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Frequency</label>
                  <select
                    value={scheduleForm.frequency}
                    onChange={(e) => setScheduleForm({...scheduleForm, frequency: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    data-testid="schedule-frequency"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Recipients (Optional)
                  </label>
                  <input
                    type="text"
                    value={scheduleForm.recipients}
                    onChange={(e) => setScheduleForm({...scheduleForm, recipients: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="email1@example.com, email2@example.com"
                    data-testid="schedule-recipients"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Comma-separated. Leave empty to send to your account email.
                  </p>
                </div>
                
                <div className="bg-blue-50 p-3 rounded-lg text-sm text-blue-700">
                  <strong>Note:</strong> Reports will be sent to the specified email addresses at the scheduled frequency.
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowScheduleModal(false)}
                    className="flex-1"
                    data-testid="cancel-schedule-btn"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={creatingSchedule}
                    className="flex-1"
                    data-testid="create-schedule-btn"
                  >
                    {creatingSchedule ? (
                      <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Clock className="w-4 h-4 mr-2" />
                    )}
                    Create Schedule
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
