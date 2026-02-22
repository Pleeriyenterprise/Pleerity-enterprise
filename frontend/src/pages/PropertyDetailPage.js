import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { Button } from '../components/ui/button';
import { Alert, AlertDescription } from '../components/ui/alert';
import {
  ArrowLeft,
  Building2,
  CheckCircle,
  Clock,
  AlertTriangle,
  XCircle,
  FileText,
  Upload,
  RefreshCw,
  AlertCircle,
  Mail,
} from 'lucide-react';
import { SUPPORT_EMAIL } from '../config';

const STATUS_CONFIG = {
  VALID: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
  EXPIRING_SOON: { icon: Clock, text: 'Expiring soon', className: 'bg-amber-100 text-amber-700 border-amber-200' },
  MISSING: { icon: FileText, text: 'Missing', className: 'bg-gray-100 text-gray-700 border-gray-200' },
  OVERDUE: { icon: AlertTriangle, text: 'Overdue', className: 'bg-red-100 text-red-700 border-red-200' },
  FAILED: { icon: XCircle, text: 'Failed', className: 'bg-red-100 text-red-700 border-red-200' },
  COMPLIANT: { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border-green-200' },
};

export default function PropertyDetailPage() {
  const { propertyId } = useParams();
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [complianceDetail, setComplianceDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setError(null);
        const propsRes = await clientAPI.getProperties();
        if (cancelled) return;
        const prop = (propsRes.data.properties || []).find((p) => p.property_id === propertyId);
        setProperty(prop || null);
        try {
          const detailRes = await clientAPI.getComplianceDetail(propertyId);
          if (!cancelled && detailRes?.data) {
            setComplianceDetail(detailRes.data);
            setRequirements(detailRes.data.matrix || []);
            return;
          }
        } catch (_) {
          /* fallback to requirements list */
        }
        const reqsRes = await clientAPI.getPropertyRequirements(propertyId);
        if (!cancelled) {
          setRequirements(reqsRes.data?.requirements || []);
          setComplianceDetail(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e.response?.data?.detail || 'Failed to load property');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [propertyId]);

  const getStatus = (r) => STATUS_CONFIG[r.status] || STATUS_CONFIG.MISSING;
  const formatDate = (d) => (d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—');
  const daysLeft = (d) => {
    if (!d) return null;
    const diff = Math.ceil((new Date(d) - new Date()) / (1000 * 60 * 60 * 24));
    return diff;
  };
  const isMatrixRow = (r) => r.title != null || r.requirement_code != null;
  const rowTitle = (r) => r.title || r.requirement_type || r.description || r.name || '—';
  const rowExpiry = (r) => r.expiry_date || r.due_date;
  const rowDays = (r) => (r.days_to_expiry != null ? r.days_to_expiry : daysLeft(rowExpiry(r)));
  const rowReqId = (r) => r.requirement_id || r.id;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (error && !property) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
        <Button variant="outline" size="sm" className="mt-2" onClick={() => navigate('/properties')}>
          Back to properties
        </Button>
      </Alert>
    );
  }

  const address = property
    ? [property.address_line_1, property.address_line_2, property.postcode].filter(Boolean).join(', ') || 'Unnamed property'
    : 'Property';

  return (
    <div>
      <Button variant="ghost" size="sm" className="mb-4 -ml-2" onClick={() => navigate('/properties')}>
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to properties
      </Button>

      {/* Property header card */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 mb-6">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-midnight-blue">{address}</h1>
            <div className="flex flex-wrap gap-2 mt-2 text-sm text-gray-600">
              {property?.property_type && <span>{property.property_type}</span>}
              {property?.is_hmo && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded">HMO</span>}
              {property?.has_gas !== undefined && <span>{property.has_gas ? 'Gas' : 'No gas'}</span>}
            </div>
          </div>
        </div>
      </div>

      <p className="text-sm text-gray-500 mb-4">
        This is an evidence-based status summary. It is not legal advice.
      </p>

      {complianceDetail && (
        <div className="mb-6 flex flex-wrap gap-4 p-4 rounded-xl border border-gray-200 bg-gray-50">
          <span className="font-medium text-midnight-blue">Score: {complianceDetail.property_score}/100</span>
          <span className="font-medium text-midnight-blue">Risk level: {complianceDetail.risk_level}</span>
          {complianceDetail.risk_index != null && complianceDetail.risk_index > 0 && (
            <span className="text-gray-600">Risk index: {complianceDetail.risk_index}</span>
          )}
        </div>
      )}

      {/* Requirements matrix (from compliance-detail API when available, else requirements list) */}
      <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 font-medium text-midnight-blue">
          Requirements
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th className="p-3">Requirement</th>
                <th className="p-3">Evidence status</th>
                <th className="p-3">Expiry date</th>
                <th className="p-3">Days left</th>
                <th className="p-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {requirements.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-gray-500">
                    No requirements returned for this property.
                  </td>
                </tr>
              )}
              {requirements.map((r, idx) => {
                const status = getStatus(r);
                const Icon = status.icon;
                const days = rowDays(r);
                return (
                  <tr key={rowReqId(r) || r.requirement_code || idx} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="p-3 font-medium text-midnight-blue">{rowTitle(r)}</td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded border text-xs ${status.className}`}>
                        <Icon className="w-3.5 h-3.5" />
                        {status.text}
                      </span>
                    </td>
                    <td className="p-3 text-gray-600">{formatDate(rowExpiry(r))}</td>
                    <td className="p-3">{days != null ? (days < 0 ? `${Math.abs(days)} days overdue` : `${days} days`) : '—'}</td>
                    <td className="p-3">
                      <div className="flex gap-2">
                        {r.evidence_doc_id ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-electric-teal border-electric-teal"
                            onClick={() => navigate(`/documents?property_id=${propertyId}&requirement_id=${rowReqId(r)}`)}
                          >
                            <FileText className="w-3.5 h-3.5 mr-1" />
                            View document
                          </Button>
                        ) : (
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-electric-teal border-electric-teal"
                            onClick={() => navigate(`/documents?property_id=${propertyId}&requirement_id=${rowReqId(r)}`)}
                          >
                            <Upload className="w-3.5 h-3.5 mr-1" />
                            Upload
                          </Button>
                        )}
                        <a
                          href={`mailto:${SUPPORT_EMAIL}?subject=Support request: ${address}`}
                          className="text-sm text-gray-500 hover:text-electric-teal"
                        >
                          Request help
                        </a>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
