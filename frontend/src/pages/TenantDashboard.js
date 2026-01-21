import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { toast } from 'sonner';
import { 
  Home, 
  LogOut, 
  CheckCircle, 
  XCircle, 
  Clock, 
  AlertTriangle,
  Shield,
  Building2,
  Calendar,
  RefreshCw,
  ChevronRight,
  Info,
  Download,
  MessageSquare,
  Send,
  FileText,
  X
} from 'lucide-react';

/**
 * Tenant Dashboard - Enhanced view for tenants
 * 
 * Shows:
 * ✅ Property compliance status (GREEN/AMBER/RED)
 * ✅ Certificate status and expiry dates
 * ✅ Basic summaries
 * ✅ Download compliance pack
 * ✅ Request certificate updates
 * ✅ Contact landlord
 */
const TenantDashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expandedProperty, setExpandedProperty] = useState(null);
  const [showContactModal, setShowContactModal] = useState(false);
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [contactForm, setContactForm] = useState({ subject: '', message: '' });
  const [requestForm, setRequestForm] = useState({ certificate_type: '', message: '' });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await api.get('/tenant/dashboard');
      setData(response.data);
    } catch (err) {
      setError('Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getComplianceStyles = (status) => {
    switch (status) {
      case 'GREEN':
        return {
          bg: 'bg-green-50',
          border: 'border-green-200',
          text: 'text-green-700',
          icon: <CheckCircle className="w-6 h-6 text-green-500" />,
          label: 'Fully Compliant'
        };
      case 'AMBER':
        return {
          bg: 'bg-yellow-50',
          border: 'border-yellow-200',
          text: 'text-yellow-700',
          icon: <AlertTriangle className="w-6 h-6 text-yellow-500" />,
          label: 'Attention Needed'
        };
      case 'RED':
        return {
          bg: 'bg-red-50',
          border: 'border-red-200',
          text: 'text-red-700',
          icon: <XCircle className="w-6 h-6 text-red-500" />,
          label: 'Action Required'
        };
      default:
        return {
          bg: 'bg-gray-50',
          border: 'border-gray-200',
          text: 'text-gray-700',
          icon: <Clock className="w-6 h-6 text-gray-500" />,
          label: 'Unknown'
        };
    }
  };

  const getCertStatusStyles = (status) => {
    switch (status) {
      case 'COMPLIANT':
        return { color: 'text-green-600', bg: 'bg-green-100', icon: <CheckCircle className="w-4 h-4" /> };
      case 'EXPIRING_SOON':
        return { color: 'text-yellow-600', bg: 'bg-yellow-100', icon: <Clock className="w-4 h-4" /> };
      case 'OVERDUE':
        return { color: 'text-red-600', bg: 'bg-red-100', icon: <XCircle className="w-4 h-4" /> };
      case 'PENDING':
        return { color: 'text-blue-600', bg: 'bg-blue-100', icon: <Clock className="w-4 h-4" /> };
      default:
        return { color: 'text-gray-600', bg: 'bg-gray-100', icon: <Info className="w-4 h-4" /> };
    }
  };

  const handleDownloadPack = async (propertyId) => {
    try {
      const response = await api.get(`/tenant/compliance-pack/${propertyId}`, {
        responseType: 'blob'
      });
      
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

  const handleContactLandlord = async (e) => {
    e.preventDefault();
    if (!contactForm.message.trim()) {
      toast.error('Please enter a message');
      return;
    }
    
    setSubmitting(true);
    try {
      await api.post('/tenant/contact-landlord', {
        property_id: selectedProperty.property_id,
        subject: contactForm.subject || 'Message from Tenant',
        message: contactForm.message
      });
      
      toast.success('Message sent to your landlord!');
      setShowContactModal(false);
      setContactForm({ subject: '', message: '' });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to send message');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestCertificate = async (e) => {
    e.preventDefault();
    if (!requestForm.certificate_type) {
      toast.error('Please select a certificate type');
      return;
    }
    
    setSubmitting(true);
    try {
      await api.post('/tenant/request-certificate', {
        property_id: selectedProperty.property_id,
        certificate_type: requestForm.certificate_type,
        message: requestForm.message
      });
      
      toast.success('Certificate request submitted!');
      setShowRequestModal(false);
      setRequestForm({ certificate_type: '', message: '' });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  };

  const openContactModal = (property) => {
    setSelectedProperty(property);
    setShowContactModal(true);
  };

  const openRequestModal = (property) => {
    setSelectedProperty(property);
    setShowRequestModal(true);
  };
      default:
        return { color: 'text-gray-600', bg: 'bg-gray-100', icon: <Info className="w-4 h-4" /> };
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" data-testid="tenant-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Alert className="max-w-md">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="tenant-dashboard">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-8 h-8 text-electric-teal" />
              <div>
                <h1 className="text-xl font-bold">Compliance Vault</h1>
                <p className="text-sm text-gray-300">Tenant Portal</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-300">{user?.email}</span>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={handleLogout}
                className="bg-transparent border-white/30 text-white hover:bg-white/10"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Welcome & Info Banner */}
        <div className="bg-gradient-to-r from-teal-50 to-blue-50 rounded-xl p-6 mb-8 border border-teal-200">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white rounded-lg shadow-sm">
              <Home className="w-6 h-6 text-electric-teal" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-midnight-blue">
                Welcome, {data?.tenant_name || 'Tenant'}
              </h2>
              <p className="text-gray-600 mt-1">
                View the compliance status of your rental property below. Green means fully compliant, 
                amber means attention is needed soon, and red requires immediate action by your landlord.
              </p>
              <p className="text-sm text-gray-500 mt-2">
                Last updated: {new Date(data?.last_updated).toLocaleString()}
              </p>
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <Card data-testid="stat-total-properties">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-midnight-blue">{data?.summary?.total_properties || 0}</div>
              <div className="text-sm text-gray-500">Total Properties</div>
            </CardContent>
          </Card>
          <Card className="border-green-200" data-testid="stat-fully-compliant">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">{data?.summary?.fully_compliant || 0}</div>
              <div className="text-sm text-gray-500">Fully Compliant</div>
            </CardContent>
          </Card>
          <Card className="border-yellow-200" data-testid="stat-needs-attention">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-yellow-600">{data?.summary?.needs_attention || 0}</div>
              <div className="text-sm text-gray-500">Needs Attention</div>
            </CardContent>
          </Card>
          <Card className="border-red-200" data-testid="stat-action-required">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-red-600">{data?.summary?.action_required || 0}</div>
              <div className="text-sm text-gray-500">Action Required</div>
            </CardContent>
          </Card>
        </div>

        {/* Properties List */}
        <Card data-testid="properties-list">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              Your Properties
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data?.properties?.length === 0 ? (
              <div className="text-center py-8 text-gray-500" data-testid="no-properties">
                <Building2 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
                <p>No properties assigned to you yet.</p>
                <p className="text-sm mt-1">Contact your landlord for access.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {data?.properties?.map((property) => {
                  const styles = getComplianceStyles(property.compliance_status);
                  const isExpanded = expandedProperty === property.property_id;
                  
                  return (
                    <div 
                      key={property.property_id}
                      className={`rounded-lg border-2 ${styles.border} ${styles.bg} overflow-hidden transition-all`}
                      data-testid={`property-${property.property_id}`}
                    >
                      {/* Property Header */}
                      <button
                        onClick={() => setExpandedProperty(isExpanded ? null : property.property_id)}
                        className="w-full p-4 flex items-center justify-between text-left"
                        data-testid={`toggle-property-${property.property_id}`}
                      >
                        <div className="flex items-center gap-4">
                          {styles.icon}
                          <div>
                            <h3 className="font-semibold text-midnight-blue">{property.address}</h3>
                            <p className="text-sm text-gray-500 capitalize">{property.property_type}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`text-sm font-medium ${styles.text}`}>
                            {styles.label}
                          </span>
                          <ChevronRight className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                        </div>
                      </button>
                      
                      {/* Certificates List */}
                      {isExpanded && property.certificates && (
                        <div className="border-t bg-white p-4 space-y-3" data-testid={`certificates-${property.property_id}`}>
                          <h4 className="text-sm font-medium text-gray-700 mb-2">Certificate Status</h4>
                          {property.certificates.length === 0 ? (
                            <p className="text-sm text-gray-500">No certificates on record</p>
                          ) : (
                            property.certificates.map((cert, idx) => {
                              const certStyles = getCertStatusStyles(cert.status);
                              return (
                                <div 
                                  key={idx}
                                  className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
                                  data-testid={`cert-${property.property_id}-${idx}`}
                                >
                                  <div className="flex items-center gap-3">
                                    <div className={`p-1.5 rounded ${certStyles.bg} ${certStyles.color}`}>
                                      {certStyles.icon}
                                    </div>
                                    <div>
                                      <p className="font-medium text-sm text-gray-900">{cert.description || cert.type}</p>
                                      <p className="text-xs text-gray-500">{cert.type}</p>
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <p className={`text-sm font-medium ${certStyles.color}`}>{cert.status}</p>
                                    {cert.expiry !== 'N/A' && (
                                      <p className="text-xs text-gray-500 flex items-center gap-1 justify-end">
                                        <Calendar className="w-3 h-3" />
                                        Expires: {cert.expiry}
                                      </p>
                                    )}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Info Footer */}
        <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <div className="flex items-start gap-3">
            <Info className="w-5 h-5 text-blue-600 mt-0.5" />
            <div>
              <h4 className="font-medium text-blue-800">About This Portal</h4>
              <p className="text-sm text-blue-700 mt-1">
                This tenant portal provides read-only access to your rental property's compliance status. 
                It helps you stay informed about important safety certificates. For any questions or concerns 
                about compliance items, please contact your landlord directly.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default TenantDashboard;
