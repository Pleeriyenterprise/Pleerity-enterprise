import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useEntitlements } from '../contexts/EntitlementsContext';
import { UpgradeRequired } from '../components/UpgradePrompt';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
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
  Lock,
  ArrowUpRight
} from 'lucide-react';
import UpgradePrompt from '../components/UpgradePrompt';

const ReportsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { hasFeature } = useEntitlements();
  const [availableReports, setAvailableReports] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(null);
  const [properties, setProperties] = useState([]);
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

  const hasReportsAccess = hasFeature('reports_pdf') || hasFeature('reports_csv');
  const hasScheduledReportsAccess = hasFeature('scheduled_reports');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setUpgradeRequiredDetail(null);
      const [reportsRes, propsRes, schedulesRes] = await Promise.all([
        api.get('/reports/available'),
        api.get('/client/properties'),
        api.get('/reports/schedules')
      ]);
      setAvailableReports(reportsRes.data.reports || []);
      setProperties(propsRes.data.properties || []);
      setSchedules(schedulesRes.data.schedules || []);
    } catch (error) {
      if (error.isPlanGateDenied && error.upgradeDetail) {
        setUpgradeRequiredDetail(error.upgradeDetail);
      } else {
        toast.error('Failed to load reports');
      }
    } finally {
      setLoading(false);
    }
  };

  const generatePDF = (reportData, reportType) => {
    const doc = new jsPDF();
    const pageWidth = doc.internal.pageSize.getWidth();
    
    // Header
    doc.setFillColor(26, 39, 68); // midnight-blue
    doc.rect(0, 0, pageWidth, 35, 'F');
    
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(20);
    doc.text('Compliance Vault Pro', 14, 15);
    doc.setFontSize(12);
    doc.text(reportData.report_type || 'Report', 14, 25);
    doc.setFontSize(10);
    doc.text(`Generated: ${new Date().toLocaleDateString()}`, pageWidth - 50, 25);
    
    // Reset text color
    doc.setTextColor(0, 0, 0);
    
    let yPosition = 45;
    
    if (reportType === 'compliance_summary' && reportData.summary) {
      // Summary section
      doc.setFontSize(14);
      doc.text('Summary', 14, yPosition);
      yPosition += 10;
      
      doc.setFontSize(10);
      const summary = reportData.summary;
      doc.text(`Total Properties: ${summary.total_properties}`, 14, yPosition);
      yPosition += 6;
      doc.text(`Compliance Rate: ${summary.compliance_rate}%`, 14, yPosition);
      yPosition += 6;
      
      // Status breakdown
      doc.setTextColor(34, 197, 94); // green
      doc.text(`Green (Compliant): ${summary.compliance_breakdown?.green || 0}`, 14, yPosition);
      yPosition += 6;
      doc.setTextColor(245, 158, 11); // amber
      doc.text(`Amber (Attention): ${summary.compliance_breakdown?.amber || 0}`, 14, yPosition);
      yPosition += 6;
      doc.setTextColor(220, 38, 38); // red
      doc.text(`Red (Action Required): ${summary.compliance_breakdown?.red || 0}`, 14, yPosition);
      yPosition += 12;
      
      doc.setTextColor(0, 0, 0);
      
      // Expiring requirements
      doc.text(`Expiring in 30 days: ${summary.expiring_next_30_days}`, 14, yPosition);
      yPosition += 6;
      doc.text(`Expiring in 60 days: ${summary.expiring_next_60_days}`, 14, yPosition);
      yPosition += 6;
      doc.text(`Expiring in 90 days: ${summary.expiring_next_90_days}`, 14, yPosition);
      yPosition += 15;
      
      // Properties table
      if (reportData.properties && reportData.properties.length > 0) {
        doc.setFontSize(14);
        doc.text('Properties', 14, yPosition);
        yPosition += 5;
        
        autoTable(doc, {
          startY: yPosition,
          head: [['Address', 'Type', 'Status', 'Requirements', 'Compliant', 'Overdue']],
          body: reportData.properties.map(p => [
            p.address,
            p.property_type,
            p.compliance_status,
            p.total_requirements,
            p.compliant,
            p.overdue
          ]),
          styles: { fontSize: 8 },
          headStyles: { fillColor: [26, 39, 68] }
        });
      }
    } else if (reportType === 'requirements' && reportData.requirements) {
      // Requirements table
      doc.setFontSize(14);
      doc.text(`Requirements Report (${reportData.requirements.length} items)`, 14, yPosition);
      yPosition += 10;
      
      autoTable(doc, {
        startY: yPosition,
        head: [['Property', 'Type', 'Description', 'Status', 'Due Date']],
        body: reportData.requirements.map(r => [
          r.property_address?.substring(0, 30) || 'N/A',
          r.requirement_type || 'N/A',
          r.description?.substring(0, 25) || 'N/A',
          r.status || 'N/A',
          r.due_date || 'N/A'
        ]),
        styles: { fontSize: 7 },
        headStyles: { fillColor: [26, 39, 68] },
        columnStyles: {
          0: { cellWidth: 40 },
          1: { cellWidth: 25 },
          2: { cellWidth: 40 },
          3: { cellWidth: 25 },
          4: { cellWidth: 25 }
        }
      });
    }
    
    // Footer
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i);
      doc.setFontSize(8);
      doc.setTextColor(128, 128, 128);
      doc.text(
        `Page ${i} of ${pageCount} | Compliance Vault Pro | Pleerity Enterprise Ltd`,
        pageWidth / 2,
        doc.internal.pageSize.getHeight() - 10,
        { align: 'center' }
      );
    }
    
    return doc;
  };

  const downloadReport = async (reportId, endpoint) => {
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
        let filename = `report_${reportId}_${new Date().toISOString().split('T')[0]}.csv`;
        if (contentDisposition) {
          const match = contentDisposition.match(/filename=([^;]+)/);
          if (match) {
            filename = match[1].replace(/"/g, '');
          }
        }
        
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        toast.success('Report downloaded successfully');
      } else {
        // Get JSON data and generate PDF client-side
        const response = await api.get(`${endpoint}?${params.toString()}`);
        const reportData = response.data.data || response.data;
        
        const doc = generatePDF(reportData, reportId);
        doc.save(`report_${reportId}_${new Date().toISOString().split('T')[0]}.pdf`);
        
        toast.success('PDF report generated successfully');
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
      <div className="min-h-screen flex items-center justify-center" data-testid="reports-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="reports-page">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/dashboard')} 
                className="text-gray-300 hover:text-white"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl font-bold">Reports</h1>
                <p className="text-sm text-gray-300">Generate and download compliance reports</p>
              </div>
            </div>
            {hasScheduledReportsAccess ? (
              <Button
                onClick={() => setShowScheduleModal(true)}
                className="bg-electric-teal hover:bg-teal-600"
                data-testid="schedule-report-btn"
              >
                <Clock className="w-4 h-4 mr-2" />
                Schedule Report
              </Button>
            ) : (
              <Button
                variant="outline"
                className="border-white/30 text-white hover:bg-white/10"
                onClick={() => navigate('/app/billing?upgrade_to=PLAN_2_PORTFOLIO')}
                data-testid="schedule-report-upgrade-btn"
              >
                <Lock className="w-4 h-4 mr-2" />
                Schedule Report
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {upgradeRequiredDetail && (
          <div className="mb-6" data-testid="reports-upgrade-required">
            <UpgradeRequired upgradeDetail={upgradeRequiredDetail} showBackToDashboard />
          </div>
        )}
        {/* Upgrade Prompt for Reports Access (no report features at all) */}
        {!hasReportsAccess && (
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
                          {schedule.report_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                        <div className="text-sm text-gray-500">
                          {getFrequencyLabel(schedule.frequency)} • {schedule.recipients?.join(', ')}
                        </div>
                        {schedule.next_scheduled && (
                          <div className="text-xs text-gray-400">
                            Next: {new Date(schedule.next_scheduled).toLocaleDateString()}
                          </div>
                        )}
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

        {/* Format Selection */}
        <Card className="mb-6" data-testid="format-selection-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Filter className="w-5 h-5" />
              Report Settings
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Format</label>
                <select
                  value={selectedFilters.format}
                  onChange={(e) => setSelectedFilters({...selectedFilters, format: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  data-testid="format-select"
                >
                  <option value="csv">CSV (Spreadsheet)</option>
                  <option value="pdf">PDF (Document)</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Property Filter</label>
                <select
                  value={selectedFilters.property_id}
                  onChange={(e) => setSelectedFilters({...selectedFilters, property_id: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  data-testid="property-filter"
                >
                  <option value="">All Properties</option>
                  {properties.map(p => (
                    <option key={p.property_id} value={p.property_id}>
                      {p.address_line_1}, {p.city}
                    </option>
                  ))}
                </select>
              </div>

              {isAdmin && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
                    <div className="flex gap-2">
                      <input
                        type="date"
                        value={selectedFilters.start_date}
                        onChange={(e) => setSelectedFilters({...selectedFilters, start_date: e.target.value})}
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-sm"
                        placeholder="Start"
                        data-testid="start-date"
                      />
                      <input
                        type="date"
                        value={selectedFilters.end_date}
                        onChange={(e) => setSelectedFilters({...selectedFilters, end_date: e.target.value})}
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-sm"
                        placeholder="End"
                        data-testid="end-date"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Available Reports */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6" data-testid="reports-grid">
          {availableReports.map((report) => (
            <Card 
              key={report.id}
              className="hover:shadow-lg transition-shadow"
              data-testid={`report-card-${report.id}`}
            >
              <CardContent className="p-6">
                <div className="flex items-start gap-4">
                  <div className="p-3 bg-gray-50 rounded-lg">
                    {getReportIcon(report.id)}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-midnight-blue text-lg">{report.name}</h3>
                    <p className="text-sm text-gray-500 mt-1 mb-4">{report.description}</p>
                    
                    <div className="flex items-center gap-2 text-xs text-gray-400 mb-4">
                      <span>Available formats:</span>
                      {report.formats.map(f => (
                        <span key={f} className="px-2 py-0.5 bg-gray-100 rounded uppercase">{f}</span>
                      ))}
                    </div>
                    
                    <Button
                      onClick={() => downloadReport(report.id, report.endpoint)}
                      disabled={generating === report.id}
                      className="w-full"
                      data-testid={`download-${report.id}-btn`}
                    >
                      {generating === report.id ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Download className="w-4 h-4 mr-2" />
                          Download {selectedFilters.format.toUpperCase()}
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Help Text */}
        <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <h4 className="font-medium text-blue-800 mb-2">About Reports</h4>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• <strong>Compliance Summary:</strong> Overall status of your properties and requirements</li>
            <li>• <strong>Requirements Report:</strong> Detailed list of all compliance requirements with due dates</li>
            {isAdmin && (
              <li>• <strong>Audit Log Extract:</strong> System activity trail for compliance auditing (Admin only)</li>
            )}
          </ul>
          <p className="text-xs text-blue-600 mt-3">
            Schedule reports to receive them automatically via email.
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
                    <option value="compliance_summary">Compliance Status Summary</option>
                    <option value="requirements">Requirements Report</option>
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
