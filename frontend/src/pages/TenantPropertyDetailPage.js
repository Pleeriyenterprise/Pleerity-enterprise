import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { CheckCircle, XCircle, Clock, Building2, ArrowLeft, Download } from 'lucide-react';

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

  useEffect(() => {
    if (!propertyId) return;
    let cancelled = false;
    api.get(`/tenant/property/${propertyId}`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setError('Property not found or access denied'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [propertyId]);

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
      toast.success('Compliance pack downloaded!');
    } catch (err) {
      toast.error('Failed to download compliance pack');
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
        <Button variant="outline" onClick={() => navigate('/tenant/properties')} className="mb-4">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to properties
        </Button>
        <p className="text-red-600" data-testid="tenant-property-detail-error">{error || 'Not found'}</p>
      </div>
    );
  }

  const { property, certificates } = data;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="tenant-property-detail-page">
      <Button variant="ghost" onClick={() => navigate('/tenant/properties')} className="mb-6 -ml-2">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to properties
      </Button>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <h1 className="text-xl font-bold text-midnight-blue flex items-center gap-2">
          <Building2 className="w-6 h-6" />
          {property?.address}
        </h1>
        <Button onClick={handleDownloadPack} className="shrink-0">
          <Download className="w-4 h-4 mr-2" />
          Download compliance pack
        </Button>
      </div>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-midnight-blue">Compliance status</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-600 capitalize">
            <span className="font-medium">Status:</span> {property?.compliance_status}
          </p>
          <p className="text-gray-600 mt-1 capitalize">
            <span className="font-medium">Type:</span> {property?.type}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-midnight-blue">Certificates</CardTitle>
        </CardHeader>
        <CardContent>
          {!certificates?.length ? (
            <p className="text-gray-500">No certificates on record.</p>
          ) : (
            <ul className="space-y-3">
              {certificates.map((cert, idx) => {
                const styles = getCertStyles(cert.status);
                return (
                  <li key={idx} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                    <div className="flex items-center gap-3">
                      <span className={`p-1.5 rounded ${styles.bg} ${styles.color}`}>{styles.icon}</span>
                      <div>
                        <p className="font-medium text-midnight-blue">{cert.description || cert.type}</p>
                        <p className="text-sm text-gray-500">Expiry: {cert.expiry_date}</p>
                      </div>
                    </div>
                    <span className={`text-sm font-medium ${styles.color}`}>{cert.status}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
      {data.note && (
        <p className="text-sm text-gray-500 mt-4">{data.note}</p>
      )}
    </div>
  );
};

export default TenantPropertyDetailPage;
