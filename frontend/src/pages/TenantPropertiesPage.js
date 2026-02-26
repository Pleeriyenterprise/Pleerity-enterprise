import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { CheckCircle, XCircle, Clock, AlertTriangle, Building2, ChevronRight } from 'lucide-react';

function getComplianceStyles(status) {
  switch (status) {
    case 'GREEN':
      return { bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', icon: <CheckCircle className="w-5 h-5 text-green-500" />, label: 'Fully Compliant' };
    case 'AMBER':
      return { bg: 'bg-yellow-50', border: 'border-yellow-200', text: 'text-yellow-700', icon: <AlertTriangle className="w-5 h-5 text-yellow-500" />, label: 'Attention Needed' };
    case 'RED':
      return { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: <XCircle className="w-5 h-5 text-red-500" />, label: 'Action Required' };
    default:
      return { bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-700', icon: <Clock className="w-5 h-5 text-gray-500" />, label: 'Unknown' };
  }
}

const TenantPropertiesPage = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    api.get('/tenant/dashboard')
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch(() => { if (!cancelled) setError('Failed to load properties'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center" data-testid="tenant-properties-loading">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-electric-teal border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <p className="text-red-600" data-testid="tenant-properties-error">{error}</p>
      </div>
    );
  }

  const properties = data?.properties ?? [];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="tenant-properties-page">
      <h1 className="text-xl font-bold text-midnight-blue mb-6 flex items-center gap-2">
        <Building2 className="w-6 h-6" />
        Your Properties
      </h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-midnight-blue">Assigned properties</CardTitle>
        </CardHeader>
        <CardContent>
          {properties.length === 0 ? (
            <div className="text-center py-12 text-gray-500" data-testid="no-properties">
              <Building2 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
              <p>No properties assigned to you yet.</p>
              <p className="text-sm mt-1">Contact your landlord for access.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {properties.map((property) => {
                const styles = getComplianceStyles(property.compliance_status);
                return (
                  <button
                    key={property.property_id}
                    onClick={() => navigate(`/tenant/properties/${property.property_id}`)}
                    className={`w-full rounded-lg border-2 ${styles.border} ${styles.bg} p-4 flex items-center justify-between text-left hover:opacity-90 transition-opacity`}
                    data-testid={`property-row-${property.property_id}`}
                  >
                    <div className="flex items-center gap-4">
                      {styles.icon}
                      <div>
                        <h3 className="font-semibold text-midnight-blue">{property.address}</h3>
                        <p className="text-sm text-gray-500 capitalize">{property.property_type}</p>
                      </div>
                    </div>
                    <span className={`text-sm font-medium ${styles.text}`}>{styles.label}</span>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </button>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default TenantPropertiesPage;
