import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { resolvePropertyPath } from '../utils/clientPortalNavigation';
import api, { clientAPI, parseApiError } from '../api/client';
import { toast } from '@/utils/portalNotifications';
import { 
  Building2, 
  Plus, 
  Search, 
  Filter,
  ChevronRight,
  CheckCircle,
  AlertTriangle,
  Clock,
  MapPin,
  Users,
  FileText,
  Calendar,
  BarChart3,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { PortalLoadingPanel, portalPageRoot } from '../components/client/ClientPortalPatterns';
import { PORTAL_COPY } from '../utils/clientPortalCopy';
import { jurisdictionSourceLabel } from '../utils/jurisdictionComplianceCopy';

const PropertiesPage = () => {
  const navigate = useNavigate();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [clientData, setClientData] = useState(null);
  const [valueInsights, setValueInsights] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [response, insightsRes] = await Promise.all([
        api.get('/client/dashboard'),
        clientAPI.getValueInsights().catch(() => null),
      ]);
      setClientData(response.data);
      setProperties(response.data.properties || []);
      if (insightsRes?.data) setValueInsights(insightsRes.data);
      else setValueInsights(null);
    } catch (error) {
      toast.error(parseApiError(error, 'Failed to load properties'));
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'GREEN':
        return { icon: CheckCircle, text: 'Valid', className: 'bg-green-100 text-green-700 border border-green-200' };
      case 'AMBER':
        return { icon: Clock, text: 'Attention needed', className: 'bg-amber-100 text-amber-700 border border-amber-200' };
      case 'RED':
        return { icon: AlertTriangle, text: 'Overdue', className: 'bg-red-100 text-red-700 border border-red-200' };
      default:
        return { icon: Clock, text: 'Missing documents', className: 'bg-gray-100 text-gray-700 border border-gray-200' };
    }
  };

  // Filter properties based on search term and status filter
  const filteredProperties = properties.filter(property => {
    const matchesSearch = searchTerm === '' || 
      (property.nickname && property.nickname.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (property.address_line_1 && property.address_line_1.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (property.postcode && property.postcode.toLowerCase().includes(searchTerm.toLowerCase()));
    
    const matchesFilter = filterStatus === 'all' || property.compliance_status === filterStatus;
    
    return matchesSearch && matchesFilter;
  });

  // Stats
  const stats = {
    total: properties.length,
    green: properties.filter(p => p.compliance_status === 'GREEN').length,
    amber: properties.filter(p => p.compliance_status === 'AMBER').length,
    red: properties.filter(p => p.compliance_status === 'RED').length
  };

  if (loading) {
    return (
      <div className={portalPageRoot}>
        <PortalLoadingPanel message={PORTAL_COPY.loadingProperties} />
      </div>
    );
  }

  return (
    <div className={portalPageRoot}>
        {/* Page Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-center mb-6">
          <div className="min-w-0">
            <h2 className="text-2xl font-bold text-midnight-blue">Properties</h2>
            <p className="text-gray-500 mt-1">Manage your property portfolio</p>
            {valueInsights?.generated_at && (
              <p className="text-xs text-gray-400 mt-1">
                Usage insights refreshed: {new Date(valueInsights.generated_at).toLocaleString()}
              </p>
            )}
          </div>
          <Button
            onClick={() => navigate('/properties/create')}
            className="bg-electric-teal hover:bg-teal-600"
            data-testid="add-property-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Property
          </Button>
        </div>

        {valueInsights &&
          (valueInsights.upgrade_nudge_reasons || []).length > 0 &&
          !valueInsights.upgrade_path?.at_highest_public_tier && (
            <div
              className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
              data-testid="properties-upgrade-nudge"
            >
              <p className="font-semibold text-amber-900">Why upgrade right now</p>
              <ul className="mt-2 list-disc pl-4 space-y-2">
                {(valueInsights.upgrade_nudge_reasons || []).map((r) => (
                  <li key={r.code}>
                    <span className="font-medium">{r.headline}</span>
                    <span className="block text-amber-900 mt-0.5">{r.why_now}</span>
                  </li>
                ))}
              </ul>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 border-amber-400 text-amber-900 hover:bg-amber-100"
                onClick={() => navigate('/settings/billing')}
              >
                Review plans and limits
              </Button>
            </div>
          )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div 
            className={`bg-white rounded-xl border p-4 cursor-pointer hover:shadow-md transition-shadow ${filterStatus === 'all' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => setFilterStatus('all')}
            data-testid="filter-all"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Building2 className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stats.total}</p>
                <p className="text-sm text-gray-500">Total Properties</p>
              </div>
            </div>
          </div>
          <div 
            className={`bg-white rounded-xl border p-4 cursor-pointer hover:shadow-md transition-shadow ${filterStatus === 'GREEN' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => setFilterStatus('GREEN')}
            data-testid="filter-green"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-600">{stats.green}</p>
                <p className="text-sm text-gray-500">Valid</p>
              </div>
            </div>
          </div>
          <div 
            className={`bg-white rounded-xl border p-4 cursor-pointer hover:shadow-md transition-shadow ${filterStatus === 'AMBER' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => setFilterStatus('AMBER')}
            data-testid="filter-amber"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-100 rounded-lg">
                <Clock className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600">{stats.amber}</p>
                <p className="text-sm text-gray-500">Attention needed</p>
              </div>
            </div>
          </div>
          <div 
            className={`bg-white rounded-xl border p-4 cursor-pointer hover:shadow-md transition-shadow ${filterStatus === 'RED' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => setFilterStatus('RED')}
            data-testid="filter-red"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-red-600">{stats.red}</p>
                <p className="text-sm text-gray-500">Overdue</p>
              </div>
            </div>
          </div>
        </div>

        <p className="text-sm text-gray-500 mb-4" data-testid="properties-status-legend">
          Valid = all requirements compliant; Attention needed = expiring soon or missing documents; Overdue = at least one overdue requirement.
        </p>

        {/* Search Bar */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search by name, address, or postcode..."
                className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                data-testid="search-input"
              />
            </div>
            <Button
              variant="outline"
              onClick={fetchData}
              className="border-gray-200"
              data-testid="refresh-btn"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Properties List */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {filteredProperties.length === 0 ? (
            <div className="p-12 text-center">
              <Building2 className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {searchTerm
                  ? 'No matching properties'
                  : filterStatus === 'all'
                    ? 'No properties yet'
                    : filterStatus === 'GREEN'
                      ? 'No valid properties'
                      : filterStatus === 'AMBER'
                        ? 'No properties needing attention'
                        : 'No overdue properties'}
              </h3>
              <p className="text-gray-500 mb-4">
                {searchTerm
                  ? 'Try adjusting your search.'
                  : filterStatus !== 'all'
                    ? 'No properties in this category. Click "Total Properties" or another tab to see your list.'
                    : 'Add your first property to get started with compliance tracking'}
              </p>
              {!searchTerm && filterStatus === 'all' && (
                <Button
                  onClick={() => navigate('/properties/create')}
                  className="bg-electric-teal hover:bg-teal-600"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Property
                </Button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredProperties.map((property) => {
                const statusBadge = getStatusBadge(property.compliance_status);
                const StatusIcon = statusBadge.icon;
                
                return (
                  <Link
                    key={property.property_id}
                    to={resolvePropertyPath(property.property_id)}
                    className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between p-4 hover:bg-gray-50 transition-colors"
                    data-testid={`property-row-${property.property_id}`}
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center shrink-0 ${
                        property.compliance_status === 'GREEN' ? 'bg-green-100' :
                        property.compliance_status === 'AMBER' ? 'bg-amber-100' : 'bg-red-100'
                      }`}>
                        <Building2 className={`w-6 h-6 ${
                          property.compliance_status === 'GREEN' ? 'text-green-600' :
                          property.compliance_status === 'AMBER' ? 'text-amber-600' : 'text-red-600'
                        }`} />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-midnight-blue truncate">
                          {property.nickname || property.address_line_1 || 'Unnamed Property'}
                        </h3>
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500 mt-1">
                          <span className="flex items-center gap-1">
                            <MapPin className="w-3 h-3" />
                            {property.postcode}
                          </span>
                          {property.property_type && (
                            <span>{property.property_type}</span>
                          )}
                          {property.is_hmo && (
                            <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded text-xs">HMO</span>
                          )}
                        </div>
                        {(property.jurisdiction_source || property.effective_jurisdiction_label) && (
                          <p className="text-xs text-gray-500 mt-1.5">
                            {property.jurisdiction_source ? (
                              <>
                                <span className="text-gray-500">Source: </span>
                                <span className="font-medium text-midnight-blue/85">
                                  {jurisdictionSourceLabel(property.jurisdiction_source)}
                                </span>
                              </>
                            ) : null}
                            {property.effective_jurisdiction_label ? (
                              <>
                                {property.jurisdiction_source ? <span className="text-gray-400"> · </span> : null}
                                <span className="text-gray-500">Region: </span>
                                <span className="font-medium text-midnight-blue/85">{property.effective_jurisdiction_label}</span>
                              </>
                            ) : null}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-4 shrink-0 self-end sm:self-auto">
                      <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${statusBadge.className}`}>
                        <StatusIcon className="w-4 h-4" />
                        {statusBadge.text}
                      </span>
                      <ChevronRight className="w-5 h-5 text-gray-400" />
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </div>

        {/* Property count footer */}
        {filteredProperties.length > 0 && (
          <div className="mt-4 text-center text-sm text-gray-500">
            Showing {filteredProperties.length} of {properties.length} properties
          </div>
        )}
    </div>
  );
};

export default PropertiesPage;
