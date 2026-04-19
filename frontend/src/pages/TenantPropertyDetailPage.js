import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from '@/utils/portalNotifications';
import { CheckCircle, XCircle, Clock, Building2, ArrowLeft, Download, Wrench } from 'lucide-react';
import {
  formatCertStatusLabel,
  getCertificateResponsibilityHint,
} from '../utils/tenantPortalTrust';
import { jurisdictionSourceLabel } from '../utils/jurisdictionComplianceCopy';

function summarizePropertySafety(status) {
  switch (status) {
    case 'GREEN':
      return 'Your safety checks look up to date from what we show here.';
    case 'AMBER':
      return 'Some checks will need renewal soon. Your landlord is expected to handle this.';
    case 'RED':
      return "Some checks need attention. Renewals are your landlord's responsibility.";
    default:
      return null;
  }
}

function getCertStyles(status) {
  switch (status) {
    case 'COMPLIANT': return { color: 'text-green-600', bg: 'bg-green-100', icon: <CheckCircle className="w-4 h-4" /> };
    case 'EXPIRING_SOON': return { color: 'text-yellow-600', bg: 'bg-yellow-100', icon: <Clock className="w-4 h-4" /> };
    case 'OVERDUE': return { color: 'text-red-600', bg: 'bg-red-100', icon: <XCircle className="w-4 h-4" /> };
    default: return { color: 'text-gray-600', bg: 'bg-gray-100', icon: <Clock className="w-4 h-4" /> };
  }
}

const TenantPropertyDetailPage = () => {
  const { propertyId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reportDescription, setReportDescription] = useState('');
  const [reportCategory, setReportCategory] = useState('general');
  const [reportSeverity, setReportSeverity] = useState('Routine');
  const [reportSubmitting, setReportSubmitting] = useState(false);

  useEffect(() => {
    if (!propertyId) return;
    let cancelled = false;
    api.get(`/tenant/property/${propertyId}`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setError('Property not found or access denied'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [propertyId]);

  const handleReportIssue = async (e) => {
    e.preventDefault();
    if (!reportDescription?.trim()) {
      toast.error('Please describe the issue');
      return;
    }
    setReportSubmitting(true);
    const descriptionWithSeverity = `[Severity: ${reportSeverity}]\n\n${reportDescription.trim()}`;
    try {
      await api.post('/tenant/report-issue', {
        property_id: propertyId,
        description: descriptionWithSeverity,
        category: reportCategory || undefined,
      });
      toast.success('Issue reported. Your landlord will triage and follow up.');
      setReportDescription('');
      setReportCategory('general');
      setReportSeverity('Routine');
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to report issue');
    } finally {
      setReportSubmitting(false);
    }
  };

  const handleDownloadPack = async () => {
    try {
      const response = await api.get(`/tenant/compliance-pack/${propertyId}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `compliance_pack_${propertyId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Property safety pack downloaded.');
    } catch (err) {
      toast.error('Failed to download pack');
    }
  };

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center" data-testid="tenant-property-detail-loading">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <Button variant="outline" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/tenant/properties'))} className="mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <p className="text-red-600" data-testid="tenant-property-detail-error">{error || 'Not found'}</p>
      </div>
    );
  }

  const { property, certificates } = data;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="tenant-property-detail-page">
      <Button variant="ghost" onClick={() => (window.history.length > 2 ? navigate(-1) : navigate('/tenant/properties'))} className="mb-6 -ml-2">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back
      </Button>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h1 className="text-xl font-bold text-midnight-blue flex items-center gap-2">
          <Building2 className="w-6 h-6" />
          {property?.address}
        </h1>
        <Button onClick={handleDownloadPack} className="shrink-0">
          <Download className="w-4 h-4 mr-2" />
          Download safety pack
        </Button>
      </div>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-midnight-blue">Safety checks overview</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-700">
            {summarizePropertySafety(property?.compliance_status) || (
              <>
                <span className="font-medium">Status:</span> {property?.compliance_status}
              </>
            )}
          </p>
          <p className="text-gray-600 mt-2 capitalize">
            <span className="font-medium">Property type:</span> {property?.type}
          </p>
          {(property?.effective_jurisdiction_label || property?.jurisdiction_source) && (
            <p className="text-gray-600 mt-2">
              <span className="font-medium">Jurisdiction:</span> {property?.effective_jurisdiction_label || '—'}
              {property?.jurisdiction_source
                ? ` · Source: ${jurisdictionSourceLabel(property.jurisdiction_source)}`
                : ''}
            </p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-midnight-blue">Safety checks</CardTitle>
        </CardHeader>
        <CardContent>
          {!certificates?.length ? (
            <p className="text-gray-500">No certificates on record.</p>
          ) : (
            <ul className="space-y-3">
              {certificates.map((cert, idx) => {
                const styles = getCertStyles(cert.status);
                const statusWords = formatCertStatusLabel(cert.status);
                const respHint = getCertificateResponsibilityHint(cert.status);
                return (
                  <li key={idx} className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 py-2 border-b border-gray-100 last:border-0">
                    <div className="flex items-start gap-3">
                      <span className={`p-1.5 rounded shrink-0 ${styles.bg} ${styles.color}`}>{styles.icon}</span>
                      <div>
                        <p className="font-medium text-midnight-blue">
                          {cert.description || cert.type}
                          {' — '}
                          <span className={styles.color}>{statusWords.toUpperCase()}</span>
                        </p>
                        <p className="text-sm text-gray-500 mt-0.5">Expires: {cert.expiry_date}</p>
                        <p className="text-xs text-gray-600 mt-1">Responsibility: Landlord</p>
                        {respHint && <p className="text-xs text-gray-600 mt-1">{respHint}</p>}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-midnight-blue flex items-center gap-2">
            <Wrench className="w-5 h-5" />
            Report maintenance issue
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-3">
            Report a repair or issue for this property. Your landlord will see it in Operations and can triage and assign a contractor.
          </p>
          <form onSubmit={handleReportIssue} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select
                value={reportCategory}
                onChange={(e) => setReportCategory(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
              >
                <option value="general">General</option>
                <option value="plumbing">Plumbing</option>
                <option value="electrical">Electrical</option>
                <option value="heating">Heating</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">How urgent is this?</label>
              <select
                value={reportSeverity}
                onChange={(e) => setReportSeverity(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm"
              >
                <option value="Emergency">Emergency</option>
                <option value="Urgent">Urgent</option>
                <option value="Routine">Routine</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
              <textarea
                value={reportDescription}
                onChange={(e) => setReportDescription(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm h-24 resize-none"
                placeholder="e.g. Boiler not heating, leak under sink..."
                required
              />
              <p className="text-xs text-gray-500 mt-1.5">
                Use this to report issues like:
                <span className="block mt-0.5">— Heating not working</span>
                <span className="block">— Water leaks</span>
                <span className="block">— Electrical faults</span>
              </p>
            </div>
            <Button type="submit" disabled={reportSubmitting} className="bg-amber-600 hover:bg-amber-700">
              {reportSubmitting ? 'Submitting…' : 'Submit report'}
            </Button>
          </form>
        </CardContent>
      </Card>
      {data.note && (
        <p className="text-sm text-gray-500 mt-4">{data.note}</p>
      )}
    </div>
  );
};

export default TenantPropertyDetailPage;
