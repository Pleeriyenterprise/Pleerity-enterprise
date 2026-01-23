/**
 * Admin Support Dashboard
 * 
 * Features:
 * - List tickets with filters (status, category, priority, service area)
 * - View full conversation transcripts
 * - Reply to conversations
 * - Update ticket status and assignments
 * - Audit log viewer
 * - CRN lookup
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  ArrowLeft, Search, Filter, MessageSquare, Ticket, Clock,
  User, AlertTriangle, CheckCircle2, XCircle, Send, RefreshCw,
  ChevronDown, Eye, MoreVertical, FileText, Phone, Mail
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from '../components/ui/dropdown-menu';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import client from '../api/client';

// Status colors
const STATUS_COLORS = {
  new: 'bg-blue-100 text-blue-700',
  open: 'bg-yellow-100 text-yellow-700',
  pending: 'bg-purple-100 text-purple-700',
  escalated: 'bg-orange-100 text-orange-700',
  resolved: 'bg-green-100 text-green-700',
  closed: 'bg-gray-100 text-gray-700',
};

const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-600',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
};

const SERVICE_LABELS = {
  cvp: 'Compliance Vault Pro',
  document_services: 'Document Services',
  ai_automation: 'AI Automation',
  market_research: 'Market Research',
  billing: 'Billing',
  other: 'Other',
};

// Stat card component
function StatCard({ title, value, icon: Icon, color = 'teal' }) {
  const colorClasses = {
    teal: 'bg-teal-100 text-teal-600',
    blue: 'bg-blue-100 text-blue-600',
    orange: 'bg-orange-100 text-orange-600',
    red: 'bg-red-100 text-red-600',
  };
  
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-gray-900">{value}</p>
            <p className="text-xs text-gray-500">{title}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Ticket row component
function TicketRow({ ticket, onSelect, isSelected }) {
  return (
    <div
      className={`p-4 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
        isSelected ? 'bg-teal-50 border-l-4 border-l-teal-500' : ''
      }`}
      onClick={() => onSelect(ticket)}
      data-testid={`ticket-${ticket.ticket_id}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-gray-500">{ticket.ticket_id}</span>
            <Badge className={STATUS_COLORS[ticket.status] || STATUS_COLORS.open}>
              {ticket.status}
            </Badge>
            <Badge className={PRIORITY_COLORS[ticket.priority] || PRIORITY_COLORS.medium}>
              {ticket.priority}
            </Badge>
          </div>
          <h4 className="font-medium text-gray-900 truncate">{ticket.subject}</h4>
          <p className="text-sm text-gray-500 truncate">{ticket.description}</p>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
            {ticket.email && (
              <span className="flex items-center gap-1">
                <Mail className="h-3 w-3" />
                {ticket.email}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {new Date(ticket.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        <Badge variant="secondary" className="ml-2 shrink-0">
          {SERVICE_LABELS[ticket.service_area] || ticket.service_area}
        </Badge>
      </div>
    </div>
  );
}

// Conversation row component
function ConversationRow({ conversation, onSelect, isSelected }) {
  return (
    <div
      className={`p-4 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
        isSelected ? 'bg-teal-50 border-l-4 border-l-teal-500' : ''
      }`}
      onClick={() => onSelect(conversation)}
      data-testid={`conversation-${conversation.conversation_id}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm text-gray-500">
              {conversation.conversation_id}
            </span>
            <Badge className={STATUS_COLORS[conversation.status] || STATUS_COLORS.open}>
              {conversation.status}
            </Badge>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span className="capitalize">{conversation.channel}</span>
            <span>•</span>
            <span>{conversation.message_count} messages</span>
          </div>
          <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
            <Clock className="h-3 w-3" />
            {new Date(conversation.last_message_at).toLocaleString()}
          </div>
        </div>
        {conversation.service_area && (
          <Badge variant="secondary">
            {SERVICE_LABELS[conversation.service_area] || conversation.service_area}
          </Badge>
        )}
      </div>
    </div>
  );
}

// Transcript viewer component
function TranscriptViewer({ messages, onReply }) {
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);

  const handleSend = async () => {
    if (!replyText.trim()) return;
    setSending(true);
    await onReply(replyText);
    setReplyText('');
    setSending(false);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`max-w-[80%] ${
              msg.sender === 'user' 
                ? 'bg-teal-500 text-white rounded-br-sm' 
                : msg.sender === 'human'
                  ? 'bg-blue-500 text-white rounded-bl-sm'
                  : 'bg-gray-100 text-gray-800 rounded-bl-sm'
            } rounded-2xl px-4 py-2`}>
              <div className="flex items-center gap-2 mb-1">
                <Badge variant="secondary" className="text-xs capitalize">
                  {msg.sender}
                </Badge>
                <span className="text-xs opacity-75">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{msg.message_text}</p>
            </div>
          </div>
        ))}
      </div>
      
      {/* Reply input */}
      <div className="border-t p-4">
        <div className="flex gap-2">
          <Textarea
            value={replyText}
            onChange={(e) => setReplyText(e.target.value)}
            placeholder="Type your reply..."
            rows={2}
            className="flex-1 resize-none"
          />
          <Button
            onClick={handleSend}
            disabled={!replyText.trim() || sending}
            className="bg-teal-600 hover:bg-teal-700 self-end"
          >
            {sending ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

// CRN Lookup component
function CRNLookup() {
  const [crn, setCrn] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleLookup = async () => {
    if (!crn.trim()) return;
    setLoading(true);
    setResult(null);
    
    try {
      const response = await client.post('/admin/support/lookup-by-crn', { crn });
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 404) {
        toast.error('Client not found');
      } else {
        toast.error('Lookup failed');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">CRN Lookup</CardTitle>
        <CardDescription>Search for client by Customer Reference Number</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 mb-4">
          <Input
            value={crn}
            onChange={(e) => setCrn(e.target.value.toUpperCase())}
            placeholder="PLE-CVP-2026-XXXXX"
            className="font-mono"
          />
          <Button onClick={handleLookup} disabled={loading}>
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          </Button>
        </div>
        
        {result && (
          <div className="space-y-3">
            <div className="bg-gray-50 rounded-lg p-3">
              <h4 className="font-medium text-gray-900">{result.client?.name}</h4>
              <p className="text-sm text-gray-600">{result.client?.email}</p>
              <Badge className="mt-2">{result.client?.subscription_status || 'No subscription'}</Badge>
            </div>
            
            {result.recent_orders?.length > 0 && (
              <div>
                <p className="text-sm font-medium text-gray-700 mb-2">Recent Orders</p>
                <div className="space-y-1">
                  {result.recent_orders.slice(0, 5).map((order, idx) => (
                    <div key={idx} className="text-sm flex justify-between">
                      <span className="font-mono text-gray-600">{order.order_ref}</span>
                      <Badge variant="secondary">{order.status}</Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <p className="text-sm text-gray-500">
              Properties: {result.properties_count || 0}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminSupportPage() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('tickets');
  const [stats, setStats] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [selectedItem, setSelectedItem] = useState(null);
  const [itemDetail, setItemDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: '',
    category: '',
    priority: '',
    service_area: '',
  });

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await client.get('/admin/support/stats');
      setStats(response.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  // Fetch tickets
  const fetchTickets = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });
      
      const response = await client.get(`/admin/support/tickets?${params}`);
      setTickets(response.data.tickets || []);
    } catch (err) {
      console.error('Failed to fetch tickets:', err);
      toast.error('Failed to load tickets');
    }
  }, [filters]);

  // Fetch conversations
  const fetchConversations = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.service_area) params.append('service_area', filters.service_area);
      
      const response = await client.get(`/admin/support/conversations?${params}`);
      setConversations(response.data.conversations || []);
    } catch (err) {
      console.error('Failed to fetch conversations:', err);
    }
  }, [filters]);

  // Fetch item detail
  const fetchItemDetail = useCallback(async (item, type) => {
    try {
      const endpoint = type === 'ticket' 
        ? `/admin/support/ticket/${item.ticket_id}`
        : `/admin/support/conversation/${item.conversation_id}`;
      
      const response = await client.get(endpoint);
      setItemDetail(response.data);
    } catch (err) {
      console.error('Failed to fetch detail:', err);
      toast.error('Failed to load details');
    }
  }, []);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchTickets(), fetchConversations()]);
      setLoading(false);
    };
    loadData();
  }, [fetchStats, fetchTickets, fetchConversations]);

  // Load detail when item selected
  useEffect(() => {
    if (selectedItem) {
      const type = selectedItem.ticket_id ? 'ticket' : 'conversation';
      fetchItemDetail(selectedItem, type);
    } else {
      setItemDetail(null);
    }
  }, [selectedItem, fetchItemDetail]);

  // Handle reply
  const handleReply = async (message) => {
    if (!itemDetail?.conversation?.conversation_id) return;
    
    try {
      await client.post(
        `/admin/support/conversation/${itemDetail.conversation.conversation_id}/reply`,
        { message }
      );
      toast.success('Reply sent');
      // Refresh detail
      fetchItemDetail(selectedItem, selectedItem.ticket_id ? 'ticket' : 'conversation');
    } catch (err) {
      toast.error('Failed to send reply');
    }
  };

  // Handle status update
  const handleStatusUpdate = async (ticketId, newStatus) => {
    try {
      await client.put(`/admin/support/ticket/${ticketId}/status?status=${newStatus}`);
      toast.success(`Status updated to ${newStatus}`);
      fetchTickets();
      if (selectedItem?.ticket_id === ticketId) {
        fetchItemDetail(selectedItem, 'ticket');
      }
    } catch (err) {
      toast.error('Failed to update status');
    }
  };

  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-support-page">
        {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-teal-100 rounded-lg">
                <MessageSquare className="h-6 w-6 text-teal-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Support Dashboard</h1>
                <p className="text-gray-500">Manage tickets, conversations, and customer inquiries</p>
              </div>
            </div>
            
            <Button
              onClick={() => {
                fetchStats();
                fetchTickets();
                fetchConversations();
              }}
              variant="outline"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <StatCard
              title="Open Tickets"
              value={stats.tickets?.open + stats.tickets?.new || 0}
              icon={Ticket}
              color="blue"
            />
            <StatCard
              title="High Priority"
              value={stats.tickets?.high_priority || 0}
              icon={AlertTriangle}
              color="red"
            />
            <StatCard
              title="Open Conversations"
              value={stats.conversations?.open || 0}
              icon={MessageSquare}
              color="teal"
            />
            <StatCard
              title="Escalated"
              value={stats.conversations?.escalated || 0}
              icon={AlertTriangle}
              color="orange"
            />
          </div>
        )}

        <div className="grid grid-cols-12 gap-6">
          {/* Left panel - List */}
          <div className="col-span-12 lg:col-span-5">
            <Card className="h-[600px] flex flex-col">
              <CardHeader className="pb-2">
                <Tabs value={activeTab} onValueChange={setActiveTab}>
                  <TabsList>
                    <TabsTrigger value="tickets" className="flex items-center gap-1">
                      <Ticket className="h-4 w-4" />
                      Tickets ({tickets.length})
                    </TabsTrigger>
                    <TabsTrigger value="conversations" className="flex items-center gap-1">
                      <MessageSquare className="h-4 w-4" />
                      Chats ({conversations.length})
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
                
                {/* Filters */}
                <div className="flex gap-2 mt-3">
                  <Select
                    value={filters.status || "all"}
                    onValueChange={(v) => setFilters(f => ({ ...f, status: v === "all" ? "" : v }))}
                  >
                    <SelectTrigger className="w-32 text-xs">
                      <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="new">New</SelectItem>
                      <SelectItem value="open">Open</SelectItem>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="escalated">Escalated</SelectItem>
                      <SelectItem value="resolved">Resolved</SelectItem>
                    </SelectContent>
                  </Select>
                  
                  {activeTab === 'tickets' && (
                    <Select
                      value={filters.priority || "all"}
                      onValueChange={(v) => setFilters(f => ({ ...f, priority: v === "all" ? "" : v }))}
                    >
                      <SelectTrigger className="w-32 text-xs">
                        <SelectValue placeholder="Priority" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Priority</SelectItem>
                        <SelectItem value="urgent">Urgent</SelectItem>
                        <SelectItem value="high">High</SelectItem>
                        <SelectItem value="medium">Medium</SelectItem>
                        <SelectItem value="low">Low</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </div>
              </CardHeader>
              
              <CardContent className="flex-1 overflow-y-auto p-0">
                {loading ? (
                  <div className="flex items-center justify-center h-full">
                    <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
                  </div>
                ) : activeTab === 'tickets' ? (
                  tickets.length > 0 ? (
                    tickets.map(ticket => (
                      <TicketRow
                        key={ticket.ticket_id}
                        ticket={ticket}
                        onSelect={setSelectedItem}
                        isSelected={selectedItem?.ticket_id === ticket.ticket_id}
                      />
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500">
                      <Ticket className="h-12 w-12 mb-2 opacity-50" />
                      <p>No tickets found</p>
                    </div>
                  )
                ) : (
                  conversations.length > 0 ? (
                    conversations.map(conv => (
                      <ConversationRow
                        key={conv.conversation_id}
                        conversation={conv}
                        onSelect={setSelectedItem}
                        isSelected={selectedItem?.conversation_id === conv.conversation_id}
                      />
                    ))
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500">
                      <MessageSquare className="h-12 w-12 mb-2 opacity-50" />
                      <p>No conversations found</p>
                    </div>
                  )
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right panel - Detail */}
          <div className="col-span-12 lg:col-span-7">
            {!selectedItem ? (
              <Card className="h-[600px] flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <Eye className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>Select a ticket or conversation to view details</p>
                </div>
              </Card>
            ) : itemDetail ? (
              <Card className="h-[600px] flex flex-col">
                <CardHeader className="pb-2 border-b">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {itemDetail.ticket?.subject || itemDetail.conversation?.conversation_id}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={STATUS_COLORS[
                          itemDetail.ticket?.status || itemDetail.conversation?.status
                        ]}>
                          {itemDetail.ticket?.status || itemDetail.conversation?.status}
                        </Badge>
                        {itemDetail.ticket?.priority && (
                          <Badge className={PRIORITY_COLORS[itemDetail.ticket.priority]}>
                            {itemDetail.ticket.priority}
                          </Badge>
                        )}
                      </div>
                    </div>
                    
                    {itemDetail.ticket && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => handleStatusUpdate(itemDetail.ticket.ticket_id, 'open')}>
                            Mark Open
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleStatusUpdate(itemDetail.ticket.ticket_id, 'pending')}>
                            Mark Pending
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleStatusUpdate(itemDetail.ticket.ticket_id, 'resolved')}>
                            Mark Resolved
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleStatusUpdate(itemDetail.ticket.ticket_id, 'closed')}>
                            Close Ticket
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                  
                  {/* Ticket info */}
                  {itemDetail.ticket && (
                    <div className="mt-3 text-sm text-gray-600 space-y-1">
                      <p><strong>Description:</strong> {itemDetail.ticket.description}</p>
                      {itemDetail.ticket.email && (
                        <p><strong>Email:</strong> {itemDetail.ticket.email}</p>
                      )}
                      {itemDetail.ticket.crn && (
                        <p><strong>CRN:</strong> {itemDetail.ticket.crn}</p>
                      )}
                    </div>
                  )}
                </CardHeader>
                
                <CardContent className="flex-1 p-0 overflow-hidden">
                  {itemDetail.messages?.length > 0 ? (
                    <TranscriptViewer
                      messages={itemDetail.messages}
                      onReply={handleReply}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <p>No messages in this conversation</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            ) : (
              <Card className="h-[600px] flex items-center justify-center">
                <RefreshCw className="h-6 w-6 animate-spin text-gray-400" />
              </Card>
            )}
            
            {/* CRN Lookup below detail */}
            <div className="mt-6">
              <CRNLookup />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
