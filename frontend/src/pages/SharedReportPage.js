/**
 * Public Shared Report Page
 * Allows viewing and downloading shared reports via time-limited links
 */
import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { FileText, Download, Clock, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SharedReportPage() {
  const { shareId } = useParams();
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [reportInfo, setReportInfo] = useState(null);
  
  useEffect(() => {
    const fetchReportInfo = async () => {
      try {
        const response = await fetch(`${API_URL}/api/public/reports/shared/${shareId}`);
        if (!response.ok) {
          const data = await response.json();
          throw new Error(data.detail || 'Failed to load report');
        }
        const data = await response.json();
        setReportInfo(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    fetchReportInfo();
  }, [shareId]);
  
  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await fetch(`${API_URL}/api/public/reports/shared/${shareId}/download`);
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Download failed');
      }
      
      const blob = await response.blob();
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `report.${reportInfo?.format || 'pdf'}`;
      if (contentDisposition) {
        const match = contentDisposition.match(/filename=(.+)/);
        if (match) filename = match[1];
      }
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Report downloaded successfully');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setDownloading(false);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading report...</p>
        </div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="bg-red-100 text-red-600 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
                <AlertCircle className="h-8 w-8" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Access Report</h2>
              <p className="text-gray-600 mb-4">{error}</p>
              <p className="text-sm text-gray-500">
                This link may have expired or been revoked. Please contact the person who shared this report.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4" data-testid="shared-report-page">
      <Card className="max-w-lg w-full">
        <CardHeader className="text-center pb-2">
          <div className="bg-blue-100 text-blue-600 p-4 rounded-full w-16 h-16 mx-auto mb-4 flex items-center justify-center">
            <FileText className="h-8 w-8" />
          </div>
          <CardTitle className="text-xl">{reportInfo?.name || 'Shared Report'}</CardTitle>
          <CardDescription>This report has been shared with you</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-gray-50 rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Report Type</span>
              <Badge variant="outline" className="capitalize">
                {reportInfo?.report_type}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Format</span>
              <Badge variant="secondary" className="uppercase">
                {reportInfo?.format}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Period</span>
              <span className="text-sm font-medium">{reportInfo?.period}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">Link Expires</span>
              <div className="flex items-center gap-1 text-sm">
                <Clock className="h-3 w-3 text-amber-500" />
                <span>{new Date(reportInfo?.expires_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
          
          <Button
            onClick={handleDownload}
            disabled={downloading}
            className="w-full"
            size="lg"
            data-testid="download-shared-report-btn"
          >
            {downloading ? (
              <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Download className="h-4 w-4 mr-2" />
            )}
            Download Report
          </Button>
          
          <p className="text-xs text-center text-gray-400">
            Powered by Pleerity Enterprise
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
