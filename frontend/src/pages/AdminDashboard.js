import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import { 
  LayoutDashboard, 
  Users, 
  FileText, 
  Mail, 
  Clock, 
  Play,
  RefreshCw,
  ChevronRight,
  CheckCircle,
  XCircle,
  AlertCircle,
  LogOut,
  Search,
  Filter,
  Eye,
  Send,
  Calendar,
  Building2,
  Shield,
  Activity,
  BookOpen,
  Plus,
  Edit,
  Trash2,
  Save,
  X,
  BarChart3,
  TrendingUp,
  PieChart,
  AlertTriangle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

// Tab Components
const JobsMonitoring = () => {
  const [jobsStatus, setJobsStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(null);

  const fetchJobsStatus = async () => {
    try {
      const response = await api.get('/admin/jobs/status');
      setJobsStatus(response.data);
    } catch (error) {
      toast.error('Failed to load jobs status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobsStatus();
    const interval = setInterval(fetchJobsStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const triggerJob = async (jobType) => {
    setTriggering(jobType);
    try {
      const response = await api.post(`/admin/jobs/trigger/${jobType}`);
      toast.success(response.data.message);
      fetchJobsStatus();
    } catch (error) {
      toast.error(`Failed to trigger ${jobType} job`);
    } finally {
      setTriggering(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Background Jobs</h2>
        <button
          onClick={fetchJobsStatus}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* System Status */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className={`w-3 h-3 rounded-full ${jobsStatus?.system_status === 'operational' ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="font-medium text-midnight-blue">
            System Status: {jobsStatus?.system_status === 'operational' ? 'Operational' : 'Issues Detected'}
          </span>
        </div>

        {/* Scheduled Jobs */}
        <div className="space-y-4">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Scheduled Jobs</h3>
          {jobsStatus?.scheduled_jobs?.map((job) => (
            <div key={job.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-4">
                <Clock className="w-5 h-5 text-electric-teal" />
                <div>
                  <p className="font-medium text-midnight-blue">{job.name}</p>
                  <p className="text-sm text-gray-500">
                    Next run: {job.next_run ? new Date(job.next_run).toLocaleString() : 'Not scheduled'}
                  </p>
                </div>
              </div>
              <button
                onClick={() => triggerJob(job.id.includes('daily') ? 'daily' : 'monthly')}
                disabled={triggering !== null}
                className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors disabled:opacity-50"
              >
                {triggering === (job.id.includes('daily') ? 'daily' : 'monthly') ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Play className="w-4 h-4" />
                )}
                Run Now
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Job Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Daily Reminders</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Last Run</span>
              <span className="font-medium">
                {jobsStatus?.daily_reminders?.last_run 
                  ? new Date(jobsStatus.daily_reminders.last_run).toLocaleString() 
                  : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Pending Reminders</span>
              <span className="font-medium text-amber-600">{jobsStatus?.daily_reminders?.pending_count || 0}</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Monthly Digest</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Last Run</span>
              <span className="font-medium">
                {jobsStatus?.monthly_digest?.last_run 
                  ? new Date(jobsStatus.monthly_digest.last_run).toLocaleString() 
                  : 'Never'}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">Total Sent</span>
              <span className="font-medium text-electric-teal">{jobsStatus?.monthly_digest?.total_sent || 0}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ClientsManagement = () => {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedClient, setSelectedClient] = useState(null);
  const [clientDetails, setClientDetails] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    fetchClients();
  }, []);

  const fetchClients = async () => {
    try {
      const response = await api.get('/admin/clients?limit=100');
      setClients(response.data.clients);
    } catch (error) {
      toast.error('Failed to load clients');
    } finally {
      setLoading(false);
    }
  };

  const fetchClientDetails = async (clientId) => {
    try {
      const response = await api.get(`/admin/clients/${clientId}/full-status`);
      setClientDetails(response.data);
      setSelectedClient(clientId);
    } catch (error) {
      toast.error('Failed to load client details');
    }
  };

  const resendPasswordSetup = async (clientId) => {
    try {
      await api.post(`/admin/clients/${clientId}/resend-password-setup`);
      toast.success('Password setup email sent');
    } catch (error) {
      toast.error('Failed to send email');
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      PROVISIONED: 'bg-green-100 text-green-800',
      PENDING_PAYMENT: 'bg-amber-100 text-amber-800',
      INTAKE_COMPLETE: 'bg-blue-100 text-blue-800',
      INVITED: 'bg-purple-100 text-purple-800',
      ACTIVE: 'bg-green-100 text-green-800',
      SET: 'bg-green-100 text-green-800',
      NOT_SET: 'bg-red-100 text-red-800'
    };
    return styles[status] || 'bg-gray-100 text-gray-800';
  };

  const filteredClients = clients.filter(client => {
    const matchesSearch = client.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         client.full_name?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || client.onboarding_status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Clients ({clients.length})</h2>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
        >
          <option value="all">All Status</option>
          <option value="PROVISIONED">Provisioned</option>
          <option value="PENDING_PAYMENT">Pending Payment</option>
          <option value="INTAKE_COMPLETE">Intake Complete</option>
        </select>
      </div>

      <div className="flex gap-6">
        {/* Client List */}
        <div className="flex-1 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Subscription</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {filteredClients.map((client) => (
                  <tr 
                    key={client.client_id} 
                    className={`hover:bg-gray-50 cursor-pointer ${selectedClient === client.client_id ? 'bg-teal-50' : ''}`}
                    onClick={() => fetchClientDetails(client.client_id)}
                  >
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-midnight-blue">{client.full_name}</p>
                        <p className="text-sm text-gray-500">{client.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(client.onboarding_status)}`}>
                        {client.onboarding_status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(client.subscription_status)}`}>
                        {client.subscription_status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); fetchClientDetails(client.client_id); }}
                        className="text-electric-teal hover:text-teal-700"
                      >
                        <Eye className="w-5 h-5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Client Details Panel */}
        {clientDetails && (
          <div className="w-96 bg-white rounded-xl border border-gray-200 p-6 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-midnight-blue">Client Details</h3>
              <button onClick={() => { setSelectedClient(null); setClientDetails(null); }} className="text-gray-400 hover:text-gray-600">
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Client Info */}
            <div className="space-y-3">
              <div>
                <p className="text-sm text-gray-500">Name</p>
                <p className="font-medium">{clientDetails.client?.full_name}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Email</p>
                <p className="font-medium">{clientDetails.client?.email}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-gray-500">Onboarding</p>
                  <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(clientDetails.client?.onboarding_status)}`}>
                    {clientDetails.client?.onboarding_status}
                  </span>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Subscription</p>
                  <span className={`inline-block px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(clientDetails.client?.subscription_status)}`}>
                    {clientDetails.client?.subscription_status}
                  </span>
                </div>
              </div>
            </div>

            {/* Portal User */}
            {clientDetails.portal_users?.length > 0 && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-3">Portal Access</h4>
                {clientDetails.portal_users.map((user, idx) => (
                  <div key={idx} className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Status</span>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(user.status)}`}>
                        {user.status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Password</span>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusBadge(user.password_status)}`}>
                        {user.password_status}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Role</span>
                      <span className="text-sm font-medium">{user.role}</span>
                    </div>
                  </div>
                ))}
                {clientDetails.portal_users[0]?.password_status === 'NOT_SET' && (
                  <button
                    onClick={() => resendPasswordSetup(clientDetails.client?.client_id)}
                    className="w-full mt-3 flex items-center justify-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
                  >
                    <Send className="w-4 h-4" />
                    Resend Password Setup
                  </button>
                )}
              </div>
            )}

            {/* Readiness Check */}
            {clientDetails.readiness_check && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-500 mb-3">Readiness Check</h4>
                <div className="space-y-2">
                  {Object.entries(clientDetails.readiness_check).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">{key.replace(/_/g, ' ')}</span>
                      {value ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : (
                        <XCircle className="w-5 h-5 text-red-500" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Properties */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-500 mb-3">
                Properties ({clientDetails.properties_count || 0})
              </h4>
              {clientDetails.properties?.slice(0, 3).map((prop, idx) => (
                <div key={idx} className="flex items-center gap-2 text-sm mb-2">
                  <Building2 className="w-4 h-4 text-gray-400" />
                  <span>{prop.address_line_1}, {prop.city}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const AuditLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionFilter, setActionFilter] = useState('');
  const [totalLogs, setTotalLogs] = useState(0);
  const [page, setPage] = useState(0);
  const limit = 20;

  useEffect(() => {
    fetchLogs();
  }, [actionFilter, page]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      let url = `/admin/audit-logs?limit=${limit}&skip=${page * limit}`;
      if (actionFilter) url += `&action=${actionFilter}`;
      const response = await api.get(url);
      setLogs(response.data.logs);
      setTotalLogs(response.data.total);
    } catch (error) {
      toast.error('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const getActionIcon = (action) => {
    if (action.includes('LOGIN')) return <Shield className="w-4 h-4" />;
    if (action.includes('EMAIL')) return <Mail className="w-4 h-4" />;
    if (action.includes('PASSWORD')) return <Activity className="w-4 h-4" />;
    if (action.includes('PROVISIONING')) return <CheckCircle className="w-4 h-4" />;
    return <FileText className="w-4 h-4" />;
  };

  const getActionColor = (action) => {
    if (action.includes('SUCCESS') || action.includes('COMPLETE')) return 'text-green-600 bg-green-50';
    if (action.includes('FAILED') || action.includes('ERROR')) return 'text-red-600 bg-red-50';
    if (action.includes('SENT')) return 'text-blue-600 bg-blue-50';
    return 'text-gray-600 bg-gray-50';
  };

  const actionOptions = [
    'USER_LOGIN_SUCCESS',
    'USER_LOGIN_FAILED',
    'PASSWORD_SET_SUCCESS',
    'PASSWORD_TOKEN_GENERATED',
    'EMAIL_SENT',
    'EMAIL_FAILED',
    'PROVISIONING_COMPLETE',
    'PROVISIONING_FAILED',
    'ADMIN_ACTION',
    'INTAKE_SUBMITTED'
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Audit Logs ({totalLogs})</h2>
        <button
          onClick={fetchLogs}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-4">
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(0); }}
          className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent"
        >
          <option value="">All Actions</option>
          {actionOptions.map(action => (
            <option key={action} value={action}>{action.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Timestamp</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {logs.map((log, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${getActionColor(log.action)}`}>
                        {getActionIcon(log.action)}
                        {log.action}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {log.metadata && Object.entries(log.metadata).slice(0, 3).map(([k, v]) => (
                        v && <span key={k} className="mr-3"><strong>{k}:</strong> {String(v).substring(0, 50)}</span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Showing {page * limit + 1} to {Math.min((page + 1) * limit, totalLogs)} of {totalLogs}
        </p>
        <div className="flex gap-2">
          <button
            onClick={() => setPage(p => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={(page + 1) * limit >= totalLogs}
            className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

const MessageLogs = () => {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMessages();
  }, []);

  const fetchMessages = async () => {
    try {
      const response = await api.get('/admin/audit-logs?action=EMAIL_SENT&limit=50');
      // Also fetch failed emails
      const failedResponse = await api.get('/admin/audit-logs?action=EMAIL_FAILED&limit=50');
      
      const allMessages = [...response.data.logs, ...failedResponse.data.logs]
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      setMessages(allMessages);
    } catch (error) {
      toast.error('Failed to load message logs');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Message Logs</h2>
        <button
          onClick={fetchMessages}
          className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Time</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Recipient</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Template</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Provider ID</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {messages.map((msg, idx) => (
                <tr key={idx} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(msg.timestamp).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 text-sm font-medium text-midnight-blue">
                    {msg.metadata?.recipient || 'N/A'}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {msg.metadata?.template || 'N/A'}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
                      msg.metadata?.status === 'sent' 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {msg.metadata?.status === 'sent' ? (
                        <CheckCircle className="w-3 h-3" />
                      ) : (
                        <XCircle className="w-3 h-3" />
                      )}
                      {msg.metadata?.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                    {msg.metadata?.postmark_id ? msg.metadata.postmark_id.substring(0, 12) + '...' : 'N/A'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// Rules Management Component
const RulesManagement = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState([]);
  const [propertyTypes, setPropertyTypes] = useState([]);
  const [editingRule, setEditingRule] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    rule_type: '',
    name: '',
    description: '',
    category: 'OTHER',
    frequency_days: 365,
    warning_days: 30,
    applicable_to: 'ALL',
    is_mandatory: true,
    risk_weight: 3,
    regulatory_reference: '',
    notes: ''
  });

  useEffect(() => {
    fetchRules();
    fetchCategories();
  }, []);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/rules?active_only=false');
      setRules(response.data.rules);
    } catch (error) {
      toast.error('Failed to load rules');
    } finally {
      setLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await api.get('/admin/rules/categories');
      setCategories(response.data.categories);
      setPropertyTypes(response.data.property_types);
    } catch (error) {
      console.error('Failed to load categories');
    }
  };

  const seedDefaultRules = async () => {
    try {
      const response = await api.post('/admin/rules/seed');
      toast.success(`${response.data.created} rules created, ${response.data.skipped} skipped`);
      fetchRules();
    } catch (error) {
      toast.error('Failed to seed rules');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingRule) {
        await api.put(`/admin/rules/${editingRule.rule_id}`, formData);
        toast.success('Rule updated successfully');
      } else {
        await api.post('/admin/rules', formData);
        toast.success('Rule created successfully');
      }
      setShowCreateForm(false);
      setEditingRule(null);
      resetForm();
      fetchRules();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save rule');
    }
  };

  const handleEdit = (rule) => {
    setFormData({
      rule_type: rule.rule_type,
      name: rule.name,
      description: rule.description,
      category: rule.category,
      frequency_days: rule.frequency_days,
      warning_days: rule.warning_days,
      applicable_to: rule.applicable_to,
      is_mandatory: rule.is_mandatory,
      risk_weight: rule.risk_weight,
      regulatory_reference: rule.regulatory_reference || '',
      notes: rule.notes || ''
    });
    setEditingRule(rule);
    setShowCreateForm(true);
  };

  const handleDelete = async (ruleId) => {
    if (!window.confirm('Are you sure you want to deactivate this rule?')) return;
    try {
      await api.delete(`/admin/rules/${ruleId}`);
      toast.success('Rule deactivated');
      fetchRules();
    } catch (error) {
      toast.error('Failed to delete rule');
    }
  };

  const resetForm = () => {
    setFormData({
      rule_type: '',
      name: '',
      description: '',
      category: 'OTHER',
      frequency_days: 365,
      warning_days: 30,
      applicable_to: 'ALL',
      is_mandatory: true,
      risk_weight: 3,
      regulatory_reference: '',
      notes: ''
    });
  };

  const getCategoryColor = (category) => {
    const colors = {
      SAFETY: 'bg-red-100 text-red-800',
      ELECTRICAL: 'bg-yellow-100 text-yellow-800',
      ENERGY: 'bg-green-100 text-green-800',
      FIRE: 'bg-orange-100 text-orange-800',
      HEALTH: 'bg-blue-100 text-blue-800',
      REGULATORY: 'bg-purple-100 text-purple-800',
      OTHER: 'bg-gray-100 text-gray-800'
    };
    return colors[category] || colors.OTHER;
  };

  const getRiskColor = (weight) => {
    if (weight >= 4) return 'text-red-600';
    if (weight >= 3) return 'text-amber-600';
    return 'text-green-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Requirement Rules ({rules.length})</h2>
        <div className="flex gap-3">
          <button
            onClick={seedDefaultRules}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Seed Default Rules
          </button>
          <button
            onClick={() => { resetForm(); setEditingRule(null); setShowCreateForm(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Rule
          </button>
        </div>
      </div>

      {/* Create/Edit Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-midnight-blue">
                {editingRule ? 'Edit Rule' : 'Create New Rule'}
              </h3>
              <button onClick={() => { setShowCreateForm(false); setEditingRule(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Rule Type (ID)</label>
                  <input
                    type="text"
                    value={formData.rule_type}
                    onChange={(e) => setFormData({...formData, rule_type: e.target.value.toLowerCase().replace(/\s+/g, '_')})}
                    disabled={!!editingRule}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal disabled:bg-gray-100"
                    placeholder="e.g., gas_safety"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="e.g., Gas Safety Certificate"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  rows={2}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                  <select
                    value={formData.category}
                    onChange={(e) => setFormData({...formData, category: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  >
                    {categories.map(cat => (
                      <option key={cat.value} value={cat.value}>{cat.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Applicable To</label>
                  <select
                    value={formData.applicable_to}
                    onChange={(e) => setFormData({...formData, applicable_to: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  >
                    {propertyTypes.map(pt => (
                      <option key={pt.value} value={pt.value}>{pt.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Frequency (days)</label>
                  <input
                    type="number"
                    value={formData.frequency_days}
                    onChange={(e) => setFormData({...formData, frequency_days: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Warning (days)</label>
                  <input
                    type="number"
                    value={formData.warning_days}
                    onChange={(e) => setFormData({...formData, warning_days: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Risk Weight (1-5)</label>
                  <input
                    type="number"
                    value={formData.risk_weight}
                    onChange={(e) => setFormData({...formData, risk_weight: parseInt(e.target.value)})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    min={1}
                    max={5}
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Regulatory Reference</label>
                <input
                  type="text"
                  value={formData.regulatory_reference}
                  onChange={(e) => setFormData({...formData, regulatory_reference: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., Gas Safety Regulations 1998"
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.is_mandatory}
                    onChange={(e) => setFormData({...formData, is_mandatory: e.target.checked})}
                    className="w-4 h-4 text-electric-teal rounded"
                  />
                  <span className="text-sm text-gray-700">Mandatory</span>
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => { setShowCreateForm(false); setEditingRule(null); }}
                  className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
                >
                  <Save className="w-4 h-4" />
                  {editingRule ? 'Update Rule' : 'Create Rule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Rules Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rule</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Frequency</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Applies To</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Risk</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {rules.map((rule) => (
                <tr key={rule.rule_id} className={`hover:bg-gray-50 ${!rule.is_active ? 'opacity-50' : ''}`}>
                  <td className="px-6 py-4">
                    <div>
                      <p className="font-medium text-midnight-blue">{rule.name}</p>
                      <p className="text-sm text-gray-500">{rule.rule_type}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getCategoryColor(rule.category)}`}>
                      {rule.category}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {rule.frequency_days >= 365 
                      ? `${Math.round(rule.frequency_days / 365)} year${rule.frequency_days >= 730 ? 's' : ''}`
                      : `${rule.frequency_days} days`
                    }
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-600">
                    {rule.applicable_to}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`font-bold ${getRiskColor(rule.risk_weight)}`}>
                      {rule.risk_weight}/5
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {rule.is_active ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : (
                        <XCircle className="w-4 h-4 text-red-500" />
                      )}
                      {rule.is_mandatory && (
                        <span className="text-xs bg-red-100 text-red-800 px-2 py-0.5 rounded">Required</span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleEdit(rule)}
                        className="text-electric-teal hover:text-teal-700"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      {rule.is_active && (
                        <button
                          onClick={() => handleDelete(rule.rule_id)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {rules.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <BookOpen className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-4">No rules configured yet</p>
          <button
            onClick={seedDefaultRules}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
          >
            Load UK Default Rules
          </button>
        </div>
      )}
    </div>
  );
};

// Email Templates Management Component
const EmailTemplates = () => {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [aliases, setAliases] = useState([]);
  const [editingTemplate, setEditingTemplate] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [previewHtml, setPreviewHtml] = useState(null);
  const [formData, setFormData] = useState({
    alias: '',
    name: '',
    subject: '',
    html_body: '',
    text_body: '',
    available_variables: [],
    notes: ''
  });

  useEffect(() => {
    fetchTemplates();
    fetchAliases();
  }, []);

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const response = await api.get('/admin/templates?active_only=false');
      setTemplates(response.data.templates);
    } catch (error) {
      toast.error('Failed to load templates');
    } finally {
      setLoading(false);
    }
  };

  const fetchAliases = async () => {
    try {
      const response = await api.get('/admin/templates/aliases');
      setAliases(response.data.aliases);
    } catch (error) {
      console.error('Failed to load aliases');
    }
  };

  const seedDefaultTemplates = async () => {
    try {
      const response = await api.post('/admin/templates/seed');
      toast.success(`${response.data.created} templates created, ${response.data.skipped} skipped`);
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to seed templates');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...formData,
        available_variables: formData.available_variables.filter(v => v.trim())
      };
      
      if (editingTemplate) {
        await api.put(`/admin/templates/${editingTemplate.template_id}`, payload);
        toast.success('Template updated successfully');
      } else {
        await api.post('/admin/templates', payload);
        toast.success('Template created successfully');
      }
      setShowCreateForm(false);
      setEditingTemplate(null);
      resetForm();
      fetchTemplates();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save template');
    }
  };

  const handleEdit = (template) => {
    setFormData({
      alias: template.alias,
      name: template.name,
      subject: template.subject,
      html_body: template.html_body,
      text_body: template.text_body,
      available_variables: template.available_variables || [],
      notes: template.notes || ''
    });
    setEditingTemplate(template);
    setShowCreateForm(true);
  };

  const handlePreview = async (templateId) => {
    try {
      const response = await api.post(`/admin/templates/${templateId}/preview`, { sample_data: {} });
      setPreviewHtml(response.data);
    } catch (error) {
      toast.error('Failed to generate preview');
    }
  };

  const handleDelete = async (templateId) => {
    if (!window.confirm('Are you sure you want to deactivate this template?')) return;
    try {
      await api.delete(`/admin/templates/${templateId}`);
      toast.success('Template deactivated');
      fetchTemplates();
    } catch (error) {
      toast.error('Failed to delete template');
    }
  };

  const resetForm = () => {
    setFormData({
      alias: '',
      name: '',
      subject: '',
      html_body: '',
      text_body: '',
      available_variables: [],
      notes: ''
    });
  };

  const getAliasLabel = (alias) => {
    const found = aliases.find(a => a.value === alias);
    return found ? found.label : alias;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-midnight-blue">Email Templates ({templates.length})</h2>
        <div className="flex gap-3">
          <button
            onClick={seedDefaultTemplates}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Seed Default Templates
          </button>
          <button
            onClick={() => { resetForm(); setEditingTemplate(null); setShowCreateForm(true); }}
            className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Template
          </button>
        </div>
      </div>

      {/* Preview Modal */}
      {previewHtml && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl w-full max-w-3xl max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-midnight-blue">Email Preview</h3>
              <button onClick={() => setPreviewHtml(null)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 bg-gray-100">
              <p className="text-sm text-gray-600 mb-2"><strong>Subject:</strong> {previewHtml.subject}</p>
            </div>
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              <div dangerouslySetInnerHTML={{ __html: previewHtml.html_body }} />
            </div>
          </div>
        </div>
      )}

      {/* Create/Edit Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-midnight-blue">
                {editingTemplate ? 'Edit Template' : 'Create New Template'}
              </h3>
              <button onClick={() => { setShowCreateForm(false); setEditingTemplate(null); }} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Template Type</label>
                  <select
                    value={formData.alias}
                    onChange={(e) => setFormData({...formData, alias: e.target.value})}
                    disabled={!!editingTemplate}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal disabled:bg-gray-100"
                    required
                  >
                    <option value="">Select type...</option>
                    {aliases.map(a => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                    placeholder="e.g., Password Setup Email"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject Line</label>
                <input
                  type="text"
                  value={formData.subject}
                  onChange={(e) => setFormData({...formData, subject: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., Set Your Password - Compliance Vault Pro"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Use {"{{variable_name}}"} for dynamic content</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">HTML Body</label>
                <textarea
                  value={formData.html_body}
                  onChange={(e) => setFormData({...formData, html_body: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal font-mono text-sm"
                  rows={10}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plain Text Body</label>
                <textarea
                  value={formData.text_body}
                  onChange={(e) => setFormData({...formData, text_body: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal font-mono text-sm"
                  rows={6}
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Available Variables (comma-separated)</label>
                <input
                  type="text"
                  value={formData.available_variables.join(', ')}
                  onChange={(e) => setFormData({...formData, available_variables: e.target.value.split(',').map(v => v.trim())})}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                  placeholder="e.g., client_name, setup_link, company_name"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => { setShowCreateForm(false); setEditingTemplate(null); }}
                  className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-2 px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
                >
                  <Save className="w-4 h-4" />
                  {editingTemplate ? 'Update Template' : 'Create Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Templates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {templates.map((template) => (
          <div 
            key={template.template_id} 
            className={`bg-white rounded-xl border border-gray-200 p-6 ${!template.is_active ? 'opacity-50' : ''}`}
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-800 mb-2 inline-block">
                  {getAliasLabel(template.alias)}
                </span>
                <h3 className="text-lg font-semibold text-midnight-blue">{template.name}</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePreview(template.template_id)}
                  className="text-gray-400 hover:text-electric-teal"
                  title="Preview"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button
                  onClick={() => handleEdit(template)}
                  className="text-electric-teal hover:text-teal-700"
                  title="Edit"
                >
                  <Edit className="w-4 h-4" />
                </button>
                {template.is_active && (
                  <button
                    onClick={() => handleDelete(template.template_id)}
                    className="text-red-500 hover:text-red-700"
                    title="Delete"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            
            <p className="text-sm text-gray-600 mb-3">
              <strong>Subject:</strong> {template.subject}
            </p>
            
            {template.available_variables?.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {template.available_variables.map((v, i) => (
                  <span key={i} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                    {"{{"}{v}{"}}"}
                  </span>
                ))}
              </div>
            )}
            
            {!template.is_active && (
              <p className="text-xs text-red-500 mt-3">Inactive</p>
            )}
          </div>
        ))}
      </div>

      {templates.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl border border-gray-200">
          <Mail className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-4">No email templates configured yet</p>
          <button
            onClick={seedDefaultTemplates}
            className="px-4 py-2 bg-electric-teal text-white rounded-lg hover:bg-teal-600"
          >
            Load Default Templates
          </button>
        </div>
      )}
    </div>
  );
};

// Dashboard Overview
const DashboardOverview = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await api.get('/admin/dashboard');
      setStats(response.data);
    } catch (error) {
      toast.error('Failed to load dashboard stats');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  const statCards = [
    { label: 'Total Clients', value: stats?.stats?.total_clients || 0, icon: Users, color: 'text-blue-600 bg-blue-100' },
    { label: 'Total Properties', value: stats?.stats?.total_properties || 0, icon: Building2, color: 'text-purple-600 bg-purple-100' },
    { label: 'Active Clients', value: stats?.stats?.active_clients || 0, icon: CheckCircle, color: 'text-green-600 bg-green-100' },
    { label: 'Pending Setup', value: stats?.stats?.pending_clients || 0, icon: Clock, color: 'text-amber-600 bg-amber-100' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-midnight-blue">Dashboard Overview</h2>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat, idx) => (
          <div key={idx} className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-lg ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-midnight-blue">{stat.value}</p>
                <p className="text-sm text-gray-500">{stat.label}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Compliance Overview */}
      {stats?.compliance_overview && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-midnight-blue mb-4">Compliance Overview</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-3xl font-bold text-green-600">{stats.compliance_overview.GREEN || 0}</p>
              <p className="text-sm text-green-700">Compliant</p>
            </div>
            <div className="text-center p-4 bg-amber-50 rounded-lg">
              <p className="text-3xl font-bold text-amber-600">{stats.compliance_overview.AMBER || 0}</p>
              <p className="text-sm text-amber-700">Attention Needed</p>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <p className="text-3xl font-bold text-red-600">{stats.compliance_overview.RED || 0}</p>
              <p className="text-sm text-red-700">Non-Compliant</p>
            </div>
          </div>
        </div>
      )}

      {/* Recent Activity */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-midnight-blue mb-4">Recent Activity</h3>
        <div className="space-y-3">
          {stats?.recent_activity?.slice(0, 5).map((activity, idx) => (
            <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Activity className="w-5 h-5 text-electric-teal" />
              <div className="flex-1">
                <p className="text-sm font-medium text-midnight-blue">{activity.action}</p>
                <p className="text-xs text-gray-500">{new Date(activity.timestamp).toLocaleString()}</p>
              </div>
            </div>
          )) || (
            <p className="text-gray-500 text-sm">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
};

// Main Admin Dashboard Component
const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const tabs = [
    { id: 'overview', label: 'Overview', icon: LayoutDashboard },
    { id: 'jobs', label: 'Jobs', icon: Clock },
    { id: 'clients', label: 'Clients', icon: Users },
    { id: 'rules', label: 'Rules', icon: BookOpen },
    { id: 'templates', label: 'Templates', icon: Mail },
    { id: 'audit', label: 'Audit Logs', icon: FileText },
    { id: 'messages', label: 'Messages', icon: Activity },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'overview': return <DashboardOverview />;
      case 'jobs': return <JobsMonitoring />;
      case 'clients': return <ClientsManagement />;
      case 'rules': return <RulesManagement />;
      case 'templates': return <EmailTemplates />;
      case 'audit': return <AuditLogs />;
      case 'messages': return <MessageLogs />;
      default: return <DashboardOverview />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <Shield className="w-8 h-8 text-electric-teal" />
              <div>
                <h1 className="text-lg font-bold">Compliance Vault Pro</h1>
                <p className="text-xs text-gray-400">Admin Console</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-300">{user?.email}</span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-3 py-2 text-sm bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
                data-testid="admin-logout-btn"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-8">
          {/* Sidebar */}
          <nav className="w-64 flex-shrink-0">
            <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-2">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  data-testid={`admin-tab-${tab.id}`}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    activeTab === tab.id 
                      ? 'bg-electric-teal text-white' 
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <tab.icon className="w-5 h-5" />
                  <span className="font-medium">{tab.label}</span>
                  {activeTab === tab.id && <ChevronRight className="w-4 h-4 ml-auto" />}
                </button>
              ))}
            </div>
          </nav>

          {/* Main Content */}
          <main className="flex-1" data-testid="admin-main-content">
            {renderContent()}
          </main>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
