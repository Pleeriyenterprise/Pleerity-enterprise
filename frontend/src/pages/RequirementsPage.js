import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import { toast } from 'sonner';
import { 
  FileCheck, 
  AlertTriangle, 
  Clock, 
  CheckCircle,
  Calendar,
  Building2,
  ArrowLeft,
  Filter,
  Search,
  RefreshCw,
  LogOut,
  Home,
  FileText,
  BarChart3,
  Sparkles,
  ChevronRight,
  AlertCircle,
  XCircle
} from 'lucide-react';
import { Button } from '../components/ui/button';

const RequirementsPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [requirements, setRequirements] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [clientData, setClientData] = useState(null);

  // Get filter from URL params
  const statusFilter = searchParams.get('status') || 'all';
  const windowDays = searchParams.get('window');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [dashboardRes, requirementsRes] = await Promise.all([
        api.get('/client/dashboard'),
        api.get('/client/requirements')
      ]);
      setClientData(dashboardRes.data);
      setProperties(dashboardRes.data.properties || []);
      setRequirements(requirementsRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load requirements');
    } finally {
      setLoading(false);
    }
  };

  const getPropertyById = (propertyId) => {
    return properties.find(p => p.property_id === propertyId) || {};
  };

  const getStatusConfig = (status) => {
    switch (status) {
      case 'COMPLIANT':
        return { 
          icon: CheckCircle, 
          text: 'Compliant', 
          className: 'bg-green-100 text-green-700 border-green-200',
          color: 'green'
        };
      case 'EXPIRING_SOON':
        return { 
          icon: Clock, 
          text: 'Expiring Soon', 
          className: 'bg-amber-100 text-amber-700 border-amber-200',
          color: 'amber'
        };
      case 'OVERDUE':
        return { 
          icon: AlertTriangle, 
          text: 'Overdue', 
          className: 'bg-red-100 text-red-700 border-red-200',
          color: 'red'
        };
      case 'PENDING':
        return { 
          icon: Clock, 
          text: 'Pending', 
          className: 'bg-gray-100 text-gray-700 border-gray-200',
          color: 'gray'
        };
      default:
        return { 
          icon: AlertCircle, 
          text: status || 'Unknown', 
          className: 'bg-gray-100 text-gray-700 border-gray-200',
          color: 'gray'
        };
    }
  };

  const getDaysUntilDue = (dueDate) => {
    if (!dueDate) return null;
    const due = new Date(dueDate);
    const now = new Date();
    const diffTime = due - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Not set';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric'
    });
  };

  // Apply filters
  const filteredRequirements = requirements.filter(req => {
    // Search filter
    const property = getPropertyById(req.property_id);
    const matchesSearch = searchTerm === '' ||
      req.requirement_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      req.description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      property.nickname?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      property.address_line_1?.toLowerCase().includes(searchTerm.toLowerCase());
    
    if (!matchesSearch) return false;

    // Status filter
    if (statusFilter === 'DUE_SOON') {
      return req.status === 'EXPIRING_SOON';
    } else if (statusFilter === 'OVERDUE_OR_MISSING') {
      return req.status === 'OVERDUE' || req.status === 'PENDING';
    } else if (statusFilter !== 'all') {
      return req.status === statusFilter;
    }

    // Window filter (for "Expiring Soon" tile)
    if (windowDays) {
      const days = getDaysUntilDue(req.due_date);
      return days !== null && days >= 0 && days <= parseInt(windowDays);
    }

    return true;
  }).sort((a, b) => {
    // Sort by urgency: OVERDUE first, then EXPIRING_SOON, then by due_date
    const priorityOrder = { 'OVERDUE': 0, 'EXPIRING_SOON': 1, 'PENDING': 2, 'COMPLIANT': 3 };
    const priorityDiff = (priorityOrder[a.status] || 4) - (priorityOrder[b.status] || 4);
    if (priorityDiff !== 0) return priorityDiff;
    
    // Then sort by due date
    const dateA = a.due_date ? new Date(a.due_date) : new Date('9999-12-31');
    const dateB = b.due_date ? new Date(b.due_date) : new Date('9999-12-31');
    return dateA - dateB;
  });

  // Get page title based on filter
  const getPageTitle = () => {
    if (statusFilter === 'DUE_SOON') return 'Attention Needed';
    if (statusFilter === 'OVERDUE_OR_MISSING') return 'Action Required';
    if (windowDays) return `Expiring in Next ${windowDays} Days`;
    return 'All Requirements';
  };

  const getPageDescription = () => {
    if (statusFilter === 'DUE_SOON') return 'Requirements expiring soon that need attention';
    if (statusFilter === 'OVERDUE_OR_MISSING') return 'Overdue or missing requirements requiring immediate action';
    if (windowDays) return `Requirements with deadlines within the next ${windowDays} days`;
    return 'Manage all compliance requirements across your properties';
  };

  // Stats
  const stats = {
    total: requirements.length,
    compliant: requirements.filter(r => r.status === 'COMPLIANT').length,
    expiringSoon: requirements.filter(r => r.status === 'EXPIRING_SOON').length,
    overdue: requirements.filter(r => r.status === 'OVERDUE').length,
    pending: requirements.filter(r => r.status === 'PENDING').length
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
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/properties')}
              data-testid="nav-properties"
            >
              <Building2 className="w-4 h-4 mr-2" />
              Properties
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
              data-testid="nav-requirements"
            >
              <FileCheck className="w-4 h-4 mr-2" />
              Requirements
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
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="requirements-page">
        {/* Back Button + Page Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/app/dashboard')}
            className="text-gray-600 hover:text-midnight-blue mb-4"
            data-testid="back-to-dashboard"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Dashboard
          </Button>
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-2xl font-bold text-midnight-blue">{getPageTitle()}</h2>
              <p className="text-gray-500 mt-1">{getPageDescription()}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Showing</p>
              <p className="text-2xl font-bold text-midnight-blue">{filteredRequirements.length}</p>
              <p className="text-sm text-gray-500">requirements</p>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${!statusFilter || statusFilter === 'all' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/app/requirements')}
            data-testid="filter-all"
          >
            <p className="text-2xl font-bold text-midnight-blue">{stats.total}</p>
            <p className="text-sm text-gray-500">Total</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'COMPLIANT' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/app/requirements?status=COMPLIANT')}
            data-testid="filter-compliant"
          >
            <p className="text-2xl font-bold text-green-600">{stats.compliant}</p>
            <p className="text-sm text-gray-500">Compliant</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'DUE_SOON' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/app/requirements?status=DUE_SOON')}
            data-testid="filter-due-soon"
          >
            <p className="text-2xl font-bold text-amber-600">{stats.expiringSoon}</p>
            <p className="text-sm text-gray-500">Expiring Soon</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'OVERDUE_OR_MISSING' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/app/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="filter-overdue"
          >
            <p className="text-2xl font-bold text-red-600">{stats.overdue + stats.pending}</p>
            <p className="text-sm text-gray-500">Action Required</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${windowDays === '30' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/app/requirements?window=30&status=DUE_SOON')}
            data-testid="filter-30-days"
          >
            <p className="text-2xl font-bold text-blue-600">30</p>
            <p className="text-sm text-gray-500">Day Window</p>
          </button>
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
                placeholder="Search by requirement type, property, or description..."
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

        {/* Requirements List */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {filteredRequirements.length === 0 ? (
            <div className="p-12 text-center">
              <FileCheck className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No requirements found</h3>
              <p className="text-gray-500">
                {searchTerm ? 'Try adjusting your search criteria' : 'No requirements match the current filter'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {filteredRequirements.map((req) => {
                const property = getPropertyById(req.property_id);
                const statusConfig = getStatusConfig(req.status);
                const StatusIcon = statusConfig.icon;
                const daysUntil = getDaysUntilDue(req.due_date);

                return (
                  <div
                    key={req.requirement_id}
                    className="p-4 hover:bg-gray-50 transition-colors"
                    data-testid={`requirement-row-${req.requirement_id}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-4 flex-1">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          statusConfig.color === 'green' ? 'bg-green-100' :
                          statusConfig.color === 'amber' ? 'bg-amber-100' :
                          statusConfig.color === 'red' ? 'bg-red-100' : 'bg-gray-100'
                        }`}>
                          <StatusIcon className={`w-5 h-5 ${
                            statusConfig.color === 'green' ? 'text-green-600' :
                            statusConfig.color === 'amber' ? 'text-amber-600' :
                            statusConfig.color === 'red' ? 'text-red-600' : 'text-gray-600'
                          }`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold text-midnight-blue">
                              {req.requirement_type?.replace(/_/g, ' ') || 'Unknown Requirement'}
                            </h3>
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusConfig.className}`}>
                              {statusConfig.text}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                            {req.description || 'No description available'}
                          </p>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                            <span className="flex items-center gap-1">
                              <Building2 className="w-3.5 h-3.5" />
                              {property.nickname || property.address_line_1 || 'Unknown Property'}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3.5 h-3.5" />
                              Due: {formatDate(req.due_date)}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-4 ml-4">
                        {daysUntil !== null && (
                          <div className={`text-right ${
                            daysUntil < 0 ? 'text-red-600' :
                            daysUntil <= 14 ? 'text-amber-600' :
                            daysUntil <= 30 ? 'text-yellow-600' : 'text-gray-600'
                          }`}>
                            <p className="text-lg font-bold">
                              {daysUntil < 0 ? Math.abs(daysUntil) : daysUntil}
                            </p>
                            <p className="text-xs">
                              {daysUntil < 0 ? 'days overdue' : 'days left'}
                            </p>
                          </div>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => navigate(`/app/documents?property_id=${req.property_id}&requirement_id=${req.requirement_id}`)}
                          className="text-electric-teal hover:text-teal-700"
                          data-testid={`view-documents-${req.requirement_id}`}
                        >
                          View Documents
                          <ChevronRight className="w-4 h-4 ml-1" />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer count */}
        {filteredRequirements.length > 0 && (
          <div className="mt-4 text-center text-sm text-gray-500">
            Showing {filteredRequirements.length} of {requirements.length} requirements
          </div>
        )}
      </main>
    </div>
  );
};

export default RequirementsPage;
