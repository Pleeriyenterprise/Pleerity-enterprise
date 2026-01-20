import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
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
  ChevronDown
} from 'lucide-react';

const ReportsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [availableReports, setAvailableReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(null);
  const [properties, setProperties] = useState([]);
  const [selectedFilters, setSelectedFilters] = useState({
    property_id: '',
    start_date: '',
    end_date: '',
    format: 'csv'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [reportsRes, propsRes] = await Promise.all([
        api.get('/reports/available'),
        api.get('/client/properties')
      ]);
      setAvailableReports(reportsRes.data.reports || []);
      setProperties(propsRes.data.properties || []);
    } catch (error) {
      toast.error('Failed to load reports');
    } finally {
      setLoading(false);
    }
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
        // Get PDF data for client-side rendering
        const response = await api.get(`${endpoint}?${params.toString()}`);
        
        // For now, show the data - in production, integrate with a PDF library
        console.log('PDF Data:', response.data);
        toast.info('PDF generation - data retrieved. Integrate with PDF library for full support.');
      }
    } catch (error) {
      toast.error('Failed to generate report');
      console.error('Report error:', error);
    } finally {
      setGenerating(null);
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
            <span className="text-sm text-gray-300">{user?.email}</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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

        {availableReports.length === 0 && (
          <div className="text-center py-12" data-testid="no-reports">
            <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No reports available</p>
          </div>
        )}

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
            Reports are generated on-demand. For scheduled reports, contact your administrator.
          </p>
        </div>
      </main>
    </div>
  );
};

export default ReportsPage;
