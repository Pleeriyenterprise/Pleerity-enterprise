import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { toast } from 'sonner';
import { 
  FileCheck, 
  Calendar,
  Building2,
  ArrowLeft,
  Search,
  RefreshCw,
  FileText,
  ChevronRight,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { getEvidenceStatus } from '../utils/evidenceStatus';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import EmptyState from '../components/EmptyState';

const RequirementsPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [requirements, setRequirements] = useState([]);
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [clientData, setClientData] = useState(null);
  const [groupBy, setGroupBy] = useState('property'); // 'property' | 'requirement'

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
        clientAPI.getDashboard().then((r) => r.data),
        clientAPI.getRequirements().then((r) => r.data)
      ]);
      setClientData(dashboardRes);
      setProperties(dashboardRes?.properties || []);
      setRequirements(requirementsRes?.requirements || []);
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
    const config = getEvidenceStatus(status);
    const colorMap = { green: 'green', amber: 'amber', red: 'red', gray: 'gray', blue: 'blue' };
    const color = config.className.includes('green') ? 'green' : config.className.includes('amber') ? 'amber' : config.className.includes('red') ? 'red' : config.className.includes('blue') ? 'blue' : 'gray';
    return { ...config, color };
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

  const renderRequirementRow = (req) => {
    const property = getPropertyById(req.property_id);
    const statusConfig = getStatusConfig(req.status);
    const StatusIcon = statusConfig.icon;
    const daysUntil = getDaysUntilDue(req.due_date);
    return (
      <div key={req.requirement_id} className="p-4 hover:bg-gray-50 transition-colors" data-testid={`requirement-row-${req.requirement_id}`}>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4 flex-1">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${statusConfig.color === 'green' ? 'bg-green-100' : statusConfig.color === 'amber' ? 'bg-amber-100' : statusConfig.color === 'red' ? 'bg-red-100' : statusConfig.color === 'blue' ? 'bg-blue-100' : 'bg-gray-100'}`}>
              <StatusIcon className={`w-5 h-5 ${statusConfig.color === 'green' ? 'text-green-600' : statusConfig.color === 'amber' ? 'text-amber-600' : statusConfig.color === 'red' ? 'text-red-600' : statusConfig.color === 'blue' ? 'text-blue-600' : 'text-gray-600'}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-semibold text-midnight-blue">{req.requirement_type?.replace(/_/g, ' ') || 'Unknown Requirement'}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium border ${statusConfig.className}`}>{statusConfig.text}</span>
              </div>
              <p className="text-sm text-gray-600 mt-1 line-clamp-2">{req.description || 'No description available'}</p>
              <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                <span className="flex items-center gap-1"><Building2 className="w-3.5 h-3.5" />{property.nickname || property.address_line_1 || 'Unknown Property'}</span>
                <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" />Due: {formatDate(req.due_date)}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4 ml-4">
            {daysUntil !== null && (
              <div className={`text-right ${daysUntil < 0 ? 'text-red-600' : daysUntil <= 14 ? 'text-amber-600' : daysUntil <= 30 ? 'text-yellow-600' : 'text-gray-600'}`}>
                <p className="text-lg font-bold">{daysUntil < 0 ? Math.abs(daysUntil) : daysUntil}</p>
                <p className="text-xs">{daysUntil < 0 ? 'days overdue' : 'days left'}</p>
              </div>
            )}
            <Button variant="ghost" size="sm" onClick={() => navigate(`/documents?property_id=${req.property_id}&requirement_id=${req.requirement_id}`)} className="text-electric-teal hover:text-teal-700" data-testid={`view-documents-${req.requirement_id}`}>
              View Documents <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    );
  };

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
    <div data-testid="requirements-page">
        {/* Back Button + Page Header */}
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard')}
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
            onClick={() => navigate('/requirements')}
            data-testid="filter-all"
          >
            <p className="text-2xl font-bold text-midnight-blue">{stats.total}</p>
            <p className="text-sm text-gray-500">Total</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'COMPLIANT' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=COMPLIANT')}
            data-testid="filter-compliant"
          >
            <p className="text-2xl font-bold text-green-600">{stats.compliant}</p>
            <p className="text-sm text-gray-500">Valid</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'DUE_SOON' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=DUE_SOON')}
            data-testid="filter-due-soon"
          >
            <p className="text-2xl font-bold text-amber-600">{stats.expiringSoon}</p>
            <p className="text-sm text-gray-500">Expiring Soon</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${statusFilter === 'OVERDUE_OR_MISSING' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?status=OVERDUE_OR_MISSING')}
            data-testid="filter-overdue"
          >
            <p className="text-2xl font-bold text-red-600">{stats.overdue + stats.pending}</p>
            <p className="text-sm text-gray-500">Action Required</p>
          </button>
          <button
            className={`bg-white rounded-xl border p-4 text-left hover:shadow-md transition-shadow ${windowDays === '30' ? 'border-electric-teal ring-2 ring-electric-teal/20' : 'border-gray-200'}`}
            onClick={() => navigate('/requirements?window=30&status=DUE_SOON')}
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
            <div className="flex items-center gap-2 border border-gray-200 rounded-lg p-1 bg-gray-50">
              <button
                type="button"
                onClick={() => setGroupBy('property')}
                className={`px-3 py-1.5 text-sm rounded-md ${groupBy === 'property' ? 'bg-white shadow border border-gray-200 font-medium text-midnight-blue' : 'text-gray-600'}`}
                data-testid="group-by-property"
              >
                Group by property
              </button>
              <button
                type="button"
                onClick={() => setGroupBy('requirement')}
                className={`px-3 py-1.5 text-sm rounded-md ${groupBy === 'requirement' ? 'bg-white shadow border border-gray-200 font-medium text-midnight-blue' : 'text-gray-600'}`}
                data-testid="group-by-requirement"
              >
                Group by requirement
              </button>
            </div>
          </div>
        </div>

        {/* Requirements: accordion by property or grouped by requirement */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {filteredRequirements.length === 0 ? (
            <EmptyState
              icon={FileCheck}
              title="No requirements found"
              description={searchTerm ? 'Try adjusting your search criteria' : 'No requirements match the current filter'}
              className="p-12"
            />
          ) : groupBy === 'property' ? (
            <Accordion type="multiple" className="w-full">
              {(() => {
                const byProperty = {};
                filteredRequirements.forEach((req) => {
                  const pid = req.property_id || 'unknown';
                  if (!byProperty[pid]) byProperty[pid] = [];
                  byProperty[pid].push(req);
                });
                return Object.entries(byProperty).map(([propertyId, reqs]) => {
                  const property = getPropertyById(propertyId);
                  const label = property?.nickname || property?.address_line_1 || `Property ${propertyId}`;
                  return (
                    <AccordionItem key={propertyId} value={propertyId} data-testid={`accordion-property-${propertyId}`}>
                      <AccordionTrigger className="px-4 py-3 hover:no-underline">
                        <span className="flex items-center gap-2">
                          <Building2 className="w-4 h-4 text-electric-teal" />
                          {label}
                        </span>
                        <span className="text-sm text-gray-500 font-normal ml-2">({reqs.length} requirements)</span>
                      </AccordionTrigger>
                      <AccordionContent className="px-4 pb-4">
                        <div className="divide-y divide-gray-100">
                          {reqs.map((req) => renderRequirementRow(req))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                });
              })()}
            </Accordion>
          ) : (
            <Accordion type="multiple" className="w-full">
              {(() => {
                const byReqType = {};
                filteredRequirements.forEach((req) => {
                  const type = req.requirement_type || req.requirement_code || 'Other';
                  if (!byReqType[type]) byReqType[type] = [];
                  byReqType[type].push(req);
                });
                return Object.entries(byReqType).map(([reqType, reqs]) => (
                  <AccordionItem key={reqType} value={reqType} data-testid={`accordion-requirement-${reqType}`}>
                    <AccordionTrigger className="px-4 py-3 hover:no-underline">
                      <span className="font-medium text-midnight-blue">{reqType.replace(/_/g, ' ')}</span>
                      <span className="text-sm text-gray-500 font-normal ml-2">({reqs.length})</span>
                    </AccordionTrigger>
                    <AccordionContent className="px-4 pb-4">
                      <div className="divide-y divide-gray-100">
                        {reqs.map((req) => renderRequirementRow(req))}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                ));
              })()}
            </Accordion>
          )}
        </div>

        {/* Footer count */}
        {filteredRequirements.length > 0 && (
          <div className="mt-4 text-center text-sm text-gray-500">
            Showing {filteredRequirements.length} of {requirements.length} requirements
          </div>
        )}
    </div>
  );
};

export default RequirementsPage;
