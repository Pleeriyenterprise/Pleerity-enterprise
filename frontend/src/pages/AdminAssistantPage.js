import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { toast } from 'sonner';
import { 
  Shield, 
  MessageSquare, 
  Search, 
  Send, 
  RefreshCw, 
  ArrowLeft,
  Building2,
  CheckCircle,
  AlertTriangle,
  Clock,
  User,
  X,
  Sparkles,
  History,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

const AdminAssistantPage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [crn, setCrn] = useState('');
  const [clientSnapshot, setClientSnapshot] = useState(null);
  const [loadingClient, setLoadingClient] = useState(false);
  const [question, setQuestion] = useState('');
  const [conversation, setConversation] = useState([]);
  const [askingQuestion, setAskingQuestion] = useState(false);
  const [queryHistory, setQueryHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

  // Load query history when client is loaded or when history panel is opened
  useEffect(() => {
    if (clientSnapshot && showHistory) {
      loadQueryHistory();
    }
  }, [clientSnapshot, showHistory]);

  const loadQueryHistory = async () => {
    if (!crn.trim()) return;
    
    setLoadingHistory(true);
    try {
      const response = await api.get(`/admin/assistant/history?crn=${encodeURIComponent(crn.trim())}&limit=20`);
      setQueryHistory(response.data.queries || []);
    } catch (error) {
      console.error('Failed to load query history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleLoadClient = async (e) => {
    e.preventDefault();
    if (!crn.trim()) {
      toast.error('Please enter a CRN');
      return;
    }

    setLoadingClient(true);
    setClientSnapshot(null);
    setConversation([]);
    setQueryHistory([]);

    try {
      const response = await api.get(`/admin/client-lookup?crn=${encodeURIComponent(crn.trim())}`);
      setClientSnapshot(response.data);
      toast.success(`Client loaded: ${response.data.client?.full_name || 'Unknown'}`);
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to load client';
      toast.error(errorMsg);
      setClientSnapshot(null);
    } finally {
      setLoadingClient(false);
    }
  };

  const handleAskQuestion = async (e) => {
    e.preventDefault();
    if (!question.trim() || !clientSnapshot) {
      return;
    }

    const userQuestion = question.trim();
    setQuestion('');
    setAskingQuestion(true);

    // Add user message to conversation
    setConversation(prev => [...prev, { role: 'user', content: userQuestion }]);

    try {
      const response = await api.post('/admin/assistant/ask', {
        crn: crn.trim(),
        question: userQuestion
      });

      // Add assistant response to conversation
      setConversation(prev => [...prev, { 
        role: 'assistant', 
        content: response.data.answer,
        compliance_summary: response.data.compliance_summary
      }]);
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to get response';
      toast.error(errorMsg);
      setConversation(prev => [...prev, { 
        role: 'error', 
        content: `Error: ${errorMsg}` 
      }]);
    } finally {
      setAskingQuestion(false);
    }
  };

  const handleClearClient = () => {
    setCrn('');
    setClientSnapshot(null);
    setConversation([]);
  };

  const suggestedQuestions = [
    "What is the overall compliance status?",
    "Which properties have overdue requirements?",
    "What documents are expiring soon?",
    "Summarize this client's portfolio",
    "Are there any HMO licensing issues?"
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/admin/dashboard')}
                className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                data-testid="back-to-dashboard"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <Shield className="w-8 h-8 text-electric-teal" />
              <div>
                <h1 className="text-lg font-bold">Admin Assistant</h1>
                <p className="text-xs text-gray-400">AI-Powered Client Analysis</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-300">{user?.email}</span>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Panel - CRN Lookup */}
          <div className="lg:col-span-1 space-y-6">
            {/* CRN Input Card */}
            <div className="bg-white rounded-xl border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-midnight-blue mb-4 flex items-center gap-2">
                <Search className="w-5 h-5 text-electric-teal" />
                Client Lookup
              </h2>
              <form onSubmit={handleLoadClient} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Customer Reference Number (CRN)
                  </label>
                  <input
                    type="text"
                    value={crn}
                    onChange={(e) => setCrn(e.target.value.toUpperCase())}
                    placeholder="PLE-CVP-2026-XXXXX"
                    className="w-full px-4 py-3 border border-gray-200 rounded-lg font-mono text-sm focus:ring-2 focus:ring-electric-teal focus:border-transparent"
                    data-testid="crn-input"
                  />
                </div>
                <button
                  type="submit"
                  disabled={loadingClient || !crn.trim()}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  data-testid="load-client-btn"
                >
                  {loadingClient ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <Search className="w-5 h-5" />
                  )}
                  Load Client
                </button>
              </form>
            </div>

            {/* Client Summary Card */}
            {clientSnapshot && (
              <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="client-summary">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-midnight-blue">Client Loaded</h3>
                  <button
                    onClick={handleClearClient}
                    className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                    data-testid="clear-client-btn"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-4">
                  {/* Client Info */}
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-midnight-blue text-white rounded-full flex items-center justify-center font-bold text-lg">
                      {clientSnapshot.client?.full_name?.charAt(0) || 'C'}
                    </div>
                    <div>
                      <p className="font-semibold text-midnight-blue">{clientSnapshot.client?.full_name}</p>
                      <p className="text-sm text-gray-500">{clientSnapshot.client?.email}</p>
                    </div>
                  </div>

                  {/* CRN Badge */}
                  <div className="bg-electric-teal/10 rounded-lg p-3">
                    <p className="text-xs text-gray-500 mb-1">Customer Reference</p>
                    <p className="font-mono text-electric-teal font-semibold">{clientSnapshot.client?.customer_reference}</p>
                  </div>

                  {/* Quick Stats */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <Building2 className="w-5 h-5 text-purple-500 mx-auto mb-1" />
                      <p className="text-xl font-bold text-midnight-blue">{clientSnapshot.property_count}</p>
                      <p className="text-xs text-gray-500">Properties</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <CheckCircle className="w-5 h-5 text-green-500 mx-auto mb-1" />
                      <p className="text-xl font-bold text-midnight-blue">{clientSnapshot.compliance_summary?.compliance_percentage}%</p>
                      <p className="text-xs text-gray-500">Compliant</p>
                    </div>
                  </div>

                  {/* Compliance Breakdown */}
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-gray-600">Total Requirements</span>
                      <span className="font-semibold">{clientSnapshot.compliance_summary?.total_requirements}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-green-600 flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" /> Compliant
                      </span>
                      <span className="font-semibold text-green-600">{clientSnapshot.compliance_summary?.compliant}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-amber-600 flex items-center gap-1">
                        <Clock className="w-4 h-4" /> Expiring Soon
                      </span>
                      <span className="font-semibold text-amber-600">{clientSnapshot.compliance_summary?.expiring_soon}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span className="text-red-600 flex items-center gap-1">
                        <AlertTriangle className="w-4 h-4" /> Overdue
                      </span>
                      <span className="font-semibold text-red-600">{clientSnapshot.compliance_summary?.overdue}</span>
                    </div>
                  </div>

                  {/* Status Badges */}
                  <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      clientSnapshot.client?.subscription_status === 'ACTIVE' 
                        ? 'bg-green-100 text-green-700' 
                        : 'bg-amber-100 text-amber-700'
                    }`}>
                      {clientSnapshot.client?.subscription_status}
                    </span>
                    <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                      {clientSnapshot.client?.billing_plan}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - Chat Interface */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-gray-200 h-[calc(100vh-12rem)] flex flex-col">
              {/* Chat Header */}
              <div className="p-4 border-b border-gray-200 flex items-center gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-electric-teal to-teal-600 rounded-full flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h3 className="font-semibold text-midnight-blue">AI Assistant</h3>
                  <p className="text-xs text-gray-500">
                    {clientSnapshot 
                      ? `Analyzing: ${clientSnapshot.client?.full_name}` 
                      : 'Load a client to start'}
                  </p>
                </div>
              </div>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4" data-testid="chat-messages">
                {!clientSnapshot ? (
                  <div className="text-center py-12">
                    <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500 mb-2">Enter a CRN to load client data</p>
                    <p className="text-sm text-gray-400">The AI assistant will analyze the client&apos;s compliance status</p>
                  </div>
                ) : conversation.length === 0 ? (
                  <div className="text-center py-8">
                    <MessageSquare className="w-12 h-12 text-electric-teal/30 mx-auto mb-4" />
                    <p className="text-gray-500 mb-4">Ask a question about this client</p>
                    
                    {/* Suggested Questions */}
                    <div className="space-y-2">
                      <p className="text-xs text-gray-400 uppercase tracking-wider">Suggested questions</p>
                      <div className="flex flex-wrap justify-center gap-2">
                        {suggestedQuestions.map((q, idx) => (
                          <button
                            key={idx}
                            onClick={() => setQuestion(q)}
                            className="px-3 py-2 bg-gray-50 hover:bg-electric-teal/10 text-gray-600 hover:text-electric-teal rounded-lg text-sm transition-colors"
                            data-testid={`suggested-question-${idx}`}
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : (
                  <>
                    {conversation.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[80%] rounded-xl p-4 ${
                            msg.role === 'user'
                              ? 'bg-electric-teal text-white'
                              : msg.role === 'error'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : 'bg-gray-100 text-midnight-blue'
                          }`}
                          data-testid={`chat-message-${idx}`}
                        >
                          {msg.role === 'assistant' && (
                            <div className="flex items-center gap-2 mb-2 pb-2 border-b border-gray-200">
                              <Sparkles className="w-4 h-4 text-electric-teal" />
                              <span className="text-xs font-medium text-electric-teal">AI Assistant</span>
                            </div>
                          )}
                          <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
                        </div>
                      </div>
                    ))}
                    {askingQuestion && (
                      <div className="flex justify-start">
                        <div className="bg-gray-100 rounded-xl p-4">
                          <RefreshCw className="w-5 h-5 animate-spin text-electric-teal" />
                        </div>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </>
                )}
              </div>

              {/* Chat Input */}
              <div className="p-4 border-t border-gray-200">
                <form onSubmit={handleAskQuestion} className="flex gap-3">
                  <input
                    type="text"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder={clientSnapshot ? "Ask about this client's compliance..." : "Load a client first"}
                    disabled={!clientSnapshot || askingQuestion}
                    className="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal focus:border-transparent disabled:bg-gray-50 disabled:cursor-not-allowed"
                    data-testid="question-input"
                  />
                  <button
                    type="submit"
                    disabled={!clientSnapshot || !question.trim() || askingQuestion}
                    className="px-6 py-3 bg-electric-teal text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    data-testid="send-question-btn"
                  >
                    {askingQuestion ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </button>
                </form>
                <p className="text-xs text-gray-400 mt-2 text-center">
                  AI analysis is for admin reference only. All queries are logged for audit purposes.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminAssistantPage;
