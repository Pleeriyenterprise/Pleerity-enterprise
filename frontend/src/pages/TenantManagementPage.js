import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { 
  Users, 
  ArrowLeft, 
  UserPlus, 
  Building2, 
  Mail, 
  RefreshCw,
  Check,
  X,
  MoreVertical,
  ChevronDown,
  ChevronUp,
  Shield,
  Clock,
  UserX,
  Send,
  Plus,
  Trash2,
  AlertTriangle
} from 'lucide-react';

const TenantManagementPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [tenants, setTenants] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [showAssignModal, setShowAssignModal] = useState(null);
  const [expandedTenant, setExpandedTenant] = useState(null);
  const [inviting, setInviting] = useState(false);
  const [inviteForm, setInviteForm] = useState({
    email: '',
    full_name: '',
    property_ids: []
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [tenantsRes, propsRes] = await Promise.all([
        api.get('/client/tenants'),
        api.get('/client/properties')
      ]);
      setTenants(tenantsRes.data.tenants || []);
      setProperties(propsRes.data.properties || []);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleInvite = async (e) => {
    e.preventDefault();
    if (!inviteForm.email) {
      toast.error('Email is required');
      return;
    }

    setInviting(true);
    try {
      await api.post('/client/tenants/invite', {
        ...inviteForm,
        base_url: window.location.origin
      });
      toast.success('Tenant invited successfully');
      setShowInviteModal(false);
      setInviteForm({ email: '', full_name: '', property_ids: [] });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to invite tenant');
    } finally {
      setInviting(false);
    }
  };

  const assignProperty = async (tenantId, propertyId) => {
    try {
      await api.post(`/client/tenants/${tenantId}/assign-property`, {
        property_id: propertyId
      });
      toast.success('Property assigned');
      fetchData();
      setShowAssignModal(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to assign property');
    }
  };

  const unassignProperty = async (tenantId, propertyId) => {
    try {
      await api.delete(`/client/tenants/${tenantId}/unassign-property/${propertyId}`);
      toast.success('Property unassigned');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to unassign property');
    }
  };

  const revokeTenant = async (tenantId) => {
    if (!window.confirm('Are you sure you want to revoke this tenant\'s access? This action cannot be undone.')) {
      return;
    }
    
    try {
      await api.delete(`/client/tenants/${tenantId}`);
      toast.success('Tenant access revoked');
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to revoke access');
    }
  };

  const resendInvite = async (tenantId) => {
    try {
      await api.post(`/client/tenants/${tenantId}/resend-invite`, {
        base_url: window.location.origin
      });
      toast.success('Invitation resent');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to resend invitation');
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-green-100 text-green-700">
            <Check className="w-3 h-3" />
            Active
          </span>
        );
      case 'INVITED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-yellow-100 text-yellow-700">
            <Clock className="w-3 h-3" />
            Pending
          </span>
        );
      case 'DISABLED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-red-100 text-red-700">
            <X className="w-3 h-3" />
            Disabled
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-gray-100 text-gray-700">
            {status}
          </span>
        );
    }
  };

  const getPropertyAddress = (propertyId) => {
    const prop = properties.find(p => p.property_id === propertyId);
    return prop ? `${prop.address_line_1}, ${prop.city}` : 'Unknown Property';
  };

  const getUnassignedProperties = (tenantAssignments) => {
    return properties.filter(p => !tenantAssignments.includes(p.property_id));
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="tenant-management-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="tenant-management-page">
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
                <h1 className="text-xl font-bold">Tenant Management</h1>
                <p className="text-sm text-gray-300">Invite and manage tenant access to your properties</p>
              </div>
            </div>
            <Button
              onClick={() => setShowInviteModal(true)}
              className="bg-electric-teal hover:bg-teal-600"
              data-testid="invite-tenant-btn"
            >
              <UserPlus className="w-4 h-4 mr-2" />
              Invite Tenant
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Info Banner */}
        <div className="bg-gradient-to-r from-teal-50 to-blue-50 rounded-xl p-6 mb-8 border border-teal-200">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-white rounded-lg shadow-sm">
              <Shield className="w-6 h-6 text-electric-teal" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-midnight-blue">About Tenant Access</h2>
              <p className="text-gray-600 mt-1">
                Tenants have <strong>read-only access</strong> to view the compliance status of assigned properties. 
                They can see certificate status (GREEN/AMBER/RED) and expiry dates, but cannot upload documents, 
                access reports, or make any changes.
              </p>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-midnight-blue">{tenants.length}</div>
              <div className="text-sm text-gray-500">Total Tenants</div>
            </CardContent>
          </Card>
          <Card className="border-green-200">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">
                {tenants.filter(t => t.status === 'ACTIVE').length}
              </div>
              <div className="text-sm text-gray-500">Active</div>
            </CardContent>
          </Card>
          <Card className="border-yellow-200">
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-yellow-600">
                {tenants.filter(t => t.status === 'INVITED').length}
              </div>
              <div className="text-sm text-gray-500">Pending Invites</div>
            </CardContent>
          </Card>
        </div>

        {/* Tenants List */}
        <Card data-testid="tenants-list-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="w-5 h-5" />
              Your Tenants ({tenants.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tenants.length === 0 ? (
              <div className="text-center py-12" data-testid="no-tenants">
                <Users className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <p className="text-gray-500">No tenants invited yet</p>
                <p className="text-sm text-gray-400 mt-2">
                  Invite tenants to give them read-only access to property compliance
                </p>
                <Button 
                  onClick={() => setShowInviteModal(true)}
                  className="mt-4"
                  data-testid="invite-first-tenant-btn"
                >
                  <UserPlus className="w-4 h-4 mr-2" />
                  Invite Your First Tenant
                </Button>
              </div>
            ) : (
              <div className="space-y-4" data-testid="tenants-list">
                {tenants.map((tenant) => {
                  const isExpanded = expandedTenant === tenant.portal_user_id;
                  const assignedProps = tenant.assigned_properties || [];
                  const unassignedProps = getUnassignedProperties(assignedProps);
                  
                  return (
                    <div 
                      key={tenant.portal_user_id}
                      className="border border-gray-200 rounded-lg overflow-hidden"
                      data-testid={`tenant-${tenant.portal_user_id}`}
                    >
                      {/* Tenant Header */}
                      <div 
                        className="p-4 flex items-center justify-between bg-gray-50 cursor-pointer"
                        onClick={() => setExpandedTenant(isExpanded ? null : tenant.portal_user_id)}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 bg-electric-teal/10 rounded-full flex items-center justify-center">
                            <span className="text-electric-teal font-medium">
                              {(tenant.full_name || tenant.email).charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-midnight-blue">
                                {tenant.full_name || 'No Name'}
                              </span>
                              {getStatusBadge(tenant.status)}
                            </div>
                            <div className="flex items-center gap-1 text-sm text-gray-500">
                              <Mail className="w-3 h-3" />
                              {tenant.email}
                            </div>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-4">
                          <div className="text-sm text-gray-500">
                            <Building2 className="w-4 h-4 inline mr-1" />
                            {assignedProps.length} propert{assignedProps.length === 1 ? 'y' : 'ies'}
                          </div>
                          {isExpanded ? (
                            <ChevronUp className="w-5 h-5 text-gray-400" />
                          ) : (
                            <ChevronDown className="w-5 h-5 text-gray-400" />
                          )}
                        </div>
                      </div>
                      
                      {/* Expanded Content */}
                      {isExpanded && (
                        <div className="p-4 border-t bg-white space-y-4">
                          {/* Assigned Properties */}
                          <div>
                            <h4 className="text-sm font-medium text-gray-700 mb-2">Assigned Properties</h4>
                            {assignedProps.length === 0 ? (
                              <p className="text-sm text-gray-400 italic">No properties assigned</p>
                            ) : (
                              <div className="space-y-2">
                                {assignedProps.map(propId => (
                                  <div 
                                    key={propId}
                                    className="flex items-center justify-between p-2 bg-gray-50 rounded"
                                  >
                                    <div className="flex items-center gap-2">
                                      <Building2 className="w-4 h-4 text-gray-400" />
                                      <span className="text-sm">{getPropertyAddress(propId)}</span>
                                    </div>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        unassignProperty(tenant.portal_user_id, propId);
                                      }}
                                      className="text-red-500 hover:text-red-700 p-1"
                                      title="Remove assignment"
                                      data-testid={`unassign-${propId}`}
                                    >
                                      <X className="w-4 h-4" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {/* Add Property Button */}
                            {unassignedProps.length > 0 && (
                              <div className="mt-2 relative">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setShowAssignModal(showAssignModal === tenant.portal_user_id ? null : tenant.portal_user_id);
                                  }}
                                  data-testid={`add-property-${tenant.portal_user_id}`}
                                >
                                  <Plus className="w-3 h-3 mr-1" />
                                  Add Property
                                </Button>
                                
                                {showAssignModal === tenant.portal_user_id && (
                                  <div className="absolute z-10 mt-1 w-64 bg-white rounded-lg shadow-lg border border-gray-200 py-2">
                                    {unassignedProps.map(prop => (
                                      <button
                                        key={prop.property_id}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          assignProperty(tenant.portal_user_id, prop.property_id);
                                        }}
                                        className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2"
                                        data-testid={`assign-option-${prop.property_id}`}
                                      >
                                        <Building2 className="w-4 h-4 text-gray-400" />
                                        {prop.address_line_1}, {prop.city}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                          
                          {/* Actions */}
                          <div className="flex items-center gap-2 pt-4 border-t">
                            {tenant.status === 'INVITED' && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  resendInvite(tenant.portal_user_id);
                                }}
                                data-testid={`resend-invite-${tenant.portal_user_id}`}
                              >
                                <Send className="w-3 h-3 mr-1" />
                                Resend Invite
                              </Button>
                            )}
                            
                            {tenant.status !== 'DISABLED' && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="text-red-600 hover:bg-red-50 hover:text-red-700 border-red-200"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  revokeTenant(tenant.portal_user_id);
                                }}
                                data-testid={`revoke-${tenant.portal_user_id}`}
                              >
                                <UserX className="w-3 h-3 mr-1" />
                                Revoke Access
                              </Button>
                            )}
                          </div>
                          
                          {/* Meta info */}
                          <div className="text-xs text-gray-400 pt-2">
                            Created: {new Date(tenant.created_at).toLocaleDateString()}
                            {tenant.invited_by && ` • Invited by: ${tenant.invited_by}`}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </main>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="invite-modal">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-midnight-blue">Invite Tenant</h2>
                <button 
                  onClick={() => setShowInviteModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                  data-testid="close-invite-modal"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
              
              <form onSubmit={handleInvite} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Email Address <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={inviteForm.email}
                    onChange={(e) => setInviteForm({...inviteForm, email: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="tenant@example.com"
                    required
                    data-testid="invite-email-input"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={inviteForm.full_name}
                    onChange={(e) => setInviteForm({...inviteForm, full_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="John Smith"
                    data-testid="invite-name-input"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Assign to Properties (Optional)
                  </label>
                  <div className="space-y-2 max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2">
                    {properties.map(prop => (
                      <label 
                        key={prop.property_id}
                        className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer"
                      >
                        <input
                          type="checkbox"
                          checked={inviteForm.property_ids.includes(prop.property_id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setInviteForm({
                                ...inviteForm,
                                property_ids: [...inviteForm.property_ids, prop.property_id]
                              });
                            } else {
                              setInviteForm({
                                ...inviteForm,
                                property_ids: inviteForm.property_ids.filter(id => id !== prop.property_id)
                              });
                            }
                          }}
                          className="rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
                          data-testid={`invite-property-${prop.property_id}`}
                        />
                        <span className="text-sm">{prop.address_line_1}, {prop.city}</span>
                      </label>
                    ))}
                  </div>
                </div>
                
                <div className="bg-blue-50 p-3 rounded-lg text-sm text-blue-700">
                  <strong>Note:</strong> An email invitation will be sent with a link to set up their account.
                </div>
                
                <div className="flex gap-3 pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowInviteModal(false)}
                    className="flex-1"
                    data-testid="cancel-invite-btn"
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    disabled={inviting}
                    className="flex-1"
                    data-testid="submit-invite-btn"
                  >
                    {inviting ? (
                      <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Send className="w-4 h-4 mr-2" />
                    )}
                    Send Invite
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

export default TenantManagementPage;
