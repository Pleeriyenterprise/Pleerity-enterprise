import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
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
  LogOut,
  Home,
  Calendar,
  BarChart3,
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { Button } from '../components/ui/button';

const PropertiesPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [clientData, setClientData] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await api.get('/client/dashboard');
      setClientData(response.data);
      setProperties(response.data.properties || []);
    } catch (error) {
      toast.error('Failed to load properties');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'GREEN':
        return { 
          icon: CheckCircle, 
          text: 'Compliant', 
          className: 'bg-green-100 text-green-700 border border-green-200' 
        };
      case 'AMBER':
        return { 
          icon: Clock, 
          text: 'Attention Needed', 
          className: 'bg-amber-100 text-amber-700 border border-amber-200' 
        };
      case 'RED':
        return { 
          icon: AlertTriangle, 
          text: 'Action Required', 
          className: 'bg-red-100 text-red-700 border border-red-200' 
        };
      default:
        return { 
          icon: Clock, 
          text: 'Pending', 
          className: 'bg-gray-100 text-gray-700 border border-gray-200' 
        };
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
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-2xl font-bold">Compliance Vault Pro</h1>
                <p className="text-sm text-gray-300">AI-Driven Solutions & Compliance</p>
              </div>
              {clientData?.client?.customer_reference && (
                <span 
                  className="px-3 py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-sm"
                  data-testid="client-crn-badge"
                >
                  {clientData.client.customer_reference}
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/dashboard')}
              data-testid="nav-dashboard"
            >
              <Home className="w-4 h-4 mr-2" />
              Dashboard
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
              data-testid="nav-properties"
            >
              <Building2 className="w-4 h-4 mr-2" />
              Properties
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/documents')}
              data-testid="nav-documents"
            >
              <FileText className="w-4 h-4 mr-2" />
              Documents
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/calendar')}
              data-testid="nav-calendar"
            >
              <Calendar className="w-4 h-4 mr-2" />
              Calendar
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/reports')}
              data-testid="nav-reports"
            >
              <BarChart3 className="w-4 h-4 mr-2" />
              Reports
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/assistant')}
              data-testid="nav-assistant"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              AI Assistant
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Page Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-midnight-blue">Properties</h2>
            <p className="text-gray-500 mt-1">Manage your property portfolio</p>
          </div>
          <Button
            onClick={() => navigate('/app/properties/create')}
            className="bg-electric-teal hover:bg-teal-600"
            data-testid="add-property-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Property
          </Button>
        </div>

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
                <p className="text-sm text-gray-500">Compliant</p>
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
                <p className="text-sm text-gray-500">Attention Needed</p>
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
                <p className="text-sm text-gray-500">Action Required</p>
              </div>
            </div>
          </div>
        </div>

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
                {searchTerm || filterStatus !== 'all' ? 'No matching properties' : 'No properties yet'}
              </h3>
              <p className="text-gray-500 mb-4">
                {searchTerm || filterStatus !== 'all' 
                  ? 'Try adjusting your search or filter criteria' 
                  : 'Add your first property to get started with compliance tracking'}
              </p>
              {!searchTerm && filterStatus === 'all' && (
                <Button
                  onClick={() => navigate('/app/properties/create')}
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
                    to={`/app/property/${property.property_id}`}
                    className="flex items-center justify-between p-4 hover:bg-gray-50 transition-colors"
                    data-testid={`property-row-${property.property_id}`}
                  >
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                        property.compliance_status === 'GREEN' ? 'bg-green-100' :
                        property.compliance_status === 'AMBER' ? 'bg-amber-100' : 'bg-red-100'
                      }`}>
                        <Building2 className={`w-6 h-6 ${
                          property.compliance_status === 'GREEN' ? 'text-green-600' :
                          property.compliance_status === 'AMBER' ? 'text-amber-600' : 'text-red-600'
                        }`} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-midnight-blue">
                          {property.nickname || property.address_line_1 || 'Unnamed Property'}
                        </h3>
                        <div className="flex items-center gap-4 text-sm text-gray-500 mt-1">
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
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
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
      </main>
    </div>
  );
};

export default PropertiesPage;
