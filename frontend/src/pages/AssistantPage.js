import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Send, ArrowLeft, AlertCircle, Shield, ChevronDown, ChevronUp, FileText, Sparkles, RefreshCw, Building2, UserCircle } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const AssistantPage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello! I'm your Compliance Vault Pro assistant. I can explain what your portal shows and suggest actions. Ask about missing or expired items, expiry dates, or where to upload documents.`,
      citations: [],
      safety_flags: {},
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedMessages, setExpandedMessages] = useState({});
  const [conversationId, setConversationId] = useState(null);
  const [propertyId, setPropertyId] = useState('');
  const [properties, setProperties] = useState([]);
  const [escalationStatus, setEscalationStatus] = useState(null);
  const [handoverSuggested, setHandoverSuggested] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const messagesEndRef = useRef(null);

  const fetchProperties = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await axios.get(`${API_URL}/client/properties`, { headers: { Authorization: `Bearer ${token}` } });
      setProperties(res.data?.properties || []);
    } catch {
      setProperties([]);
    }
  }, []);

  useEffect(() => {
    fetchProperties();
  }, [fetchProperties]);

  const fetchEscalationStatus = useCallback(async () => {
    if (!conversationId) return;
    try {
      const token = localStorage.getItem('auth_token');
      const res = await axios.get(
        `${API_URL}/api/assistant/conversation/${conversationId}/status`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setEscalationStatus(res.data);
    } catch {
      setEscalationStatus(null);
    }
  }, [conversationId]);

  useEffect(() => {
    fetchEscalationStatus();
  }, [fetchEscalationStatus]);

  const scrollToBottom = () => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleMessageDetails = (index) => {
    setExpandedMessages(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setError('');

    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.post(
        `${API_URL}/api/assistant/chat`,
        {
          message: userMessage,
          conversation_id: conversationId || undefined,
          property_id: propertyId || undefined,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      const { conversation_id, answer, citations, safety_flags, handover_suggested } = response.data;
      if (conversation_id) setConversationId(conversation_id);
      setHandoverSuggested(Boolean(handover_suggested));

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: answer,
          citations: citations || [],
          safety_flags: safety_flags || {},
        }
      ]);
    } catch (err) {
      const errorDetail = err.response?.data?.detail || 'Assistant unavailable. Please try again or refresh.';
      setError(errorDetail);
      toast.error(errorDetail);
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Assistant unavailable. Please try again or refresh.',
          error: true,
          citations: [],
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickQuestion = (question) => {
    setInput(question);
  };

  const handleEscalate = async () => {
    if (!conversationId || escalating) return;
    setEscalating(true);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await axios.post(
        `${API_URL}/api/assistant/escalate`,
        { conversation_id: conversationId, reason: 'User requested human' },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      setEscalationStatus({
        conversation_id: conversationId,
        escalated: true,
        escalation_reason: res.data?.message,
        escalated_at: new Date().toISOString(),
      });
      setHandoverSuggested(false);
      toast.success(res.data?.message || 'Support has been notified.');
    } catch (err) {
      const detail = err.response?.data?.detail || 'Escalation failed.';
      toast.error(detail);
    } finally {
      setEscalating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/app/dashboard')}
                className="text-white hover:text-electric-teal"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="border-l border-gray-600 pl-4">
                <h1 className="text-xl font-bold flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-electric-teal" />
                  Compliance Assistant
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
              >
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Disclaimer */}
        <Alert className="mb-6 bg-yellow-50 border-yellow-200" data-testid="assistant-disclaimer">
          <Shield className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-sm text-yellow-800">
            Information only. Not legal advice.
          </AlertDescription>
        </Alert>

        {/* Escalated to human */}
        {escalationStatus?.escalated && (
          <Alert className="mb-6 bg-green-50 border-green-200" data-testid="assistant-escalated-banner">
            <UserCircle className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-sm text-green-800">
              <strong>Escalated to human.</strong> Support has been notified with this conversation. We&apos;ll be in touch shortly.
            </AlertDescription>
          </Alert>
        )}

        {/* Suggest handover when API flagged */}
        {handoverSuggested && !escalationStatus?.escalated && conversationId && (
          <Alert className="mb-6 bg-blue-50 border-blue-200" data-testid="assistant-handover-suggested">
            <UserCircle className="h-4 w-4 text-blue-600" />
            <AlertDescription className="text-sm text-blue-800 flex flex-wrap items-center gap-2">
              <span>Need to speak with someone? We can transfer this conversation to support.</span>
              <Button
                size="sm"
                variant="outline"
                onClick={handleEscalate}
                disabled={escalating}
                className="border-blue-300 text-blue-800 hover:bg-blue-100"
                data-testid="assistant-request-human-btn"
              >
                {escalating ? 'Sending…' : 'Talk to a human'}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        {/* Chat Container */}
        <Card className="shadow-lg">
          <CardHeader className="border-b">
            <CardTitle className="text-midnight-blue flex items-center justify-between flex-wrap gap-2">
              <span>Ask About Your Compliance</span>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-normal text-gray-600 flex items-center gap-1">
                  <Building2 className="w-4 h-4" />
                  Scope:
                </span>
                <select
                  value={propertyId}
                  onChange={(e) => setPropertyId(e.target.value)}
                  className="text-sm border rounded px-2 py-1 bg-white"
                  data-testid="assistant-scope"
                >
                  <option value="">All properties</option>
                  {properties.map((p) => (
                    <option key={p.property_id} value={p.property_id}>
                      {p.nickname || p.address_line_1 || p.property_id}
                    </option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.location.reload()}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <RefreshCw className="w-4 h-4 mr-1" />
                  Reset
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {/* Messages */}
            <div 
              className="h-[500px] overflow-y-auto p-6 space-y-4"
              data-testid="chat-messages"
            >
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg ${
                      message.role === 'user'
                        ? 'bg-midnight-blue text-white px-4 py-3'
                        : message.error
                        ? 'bg-red-50 text-red-900 border border-red-200 px-4 py-3'
                        : message.refused
                        ? 'bg-yellow-50 text-yellow-900 border border-yellow-200 px-4 py-3'
                        : 'bg-white border border-gray-200 shadow-sm'
                    }`}
                    data-testid={`message-${message.role}`}
                  >
                    {message.role === 'assistant' && !message.error ? (
                      <div className="space-y-3">
                        {message.safety_flags?.legal_advice_request && (
                          <div className="px-4 pt-2 pb-1 rounded bg-amber-50 border border-amber-200" data-testid="assistant-legal-banner">
                            <p className="text-xs text-amber-800">
                              I can&apos;t provide legal advice. I can show what your portal currently has and what you can do next.
                            </p>
                          </div>
                        )}
                        <div className="px-4 pt-4 pb-2">
                          <p className="text-sm whitespace-pre-wrap text-gray-800">{message.content}</p>
                        </div>
                        {/* Sources (citations) */}
                        {message.citations?.length > 0 && (
                          <div className="border-t border-gray-100">
                            <button
                              onClick={() => toggleMessageDetails(index)}
                              className="w-full px-4 py-2 flex items-center justify-between text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                            >
                              <span className="flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                {expandedMessages[index] ? 'Hide sources' : 'Sources'}
                              </span>
                              {expandedMessages[index] ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            </button>
                            {expandedMessages[index] && (
                              <ul className="px-4 pb-4 text-xs space-y-1" data-testid="assistant-sources">
                                {message.citations.map((c, i) => (
                                  <li key={i} className="text-gray-600">
                                    <span className="font-medium">{c.title || c.source_id}</span>
                                    <span className="text-gray-400 ml-1">({c.source_type})</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 text-gray-600">
                      <div className="w-2 h-2 bg-electric-teal rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <div className="w-2 h-2 bg-electric-teal rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-2 h-2 bg-electric-teal rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      <span className="text-sm ml-1">Thinking...</span>
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t p-4 bg-white">
              {error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
              <form onSubmit={handleSubmit} className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask about your compliance status..."
                  disabled={loading || escalationStatus?.escalated}
                  maxLength={500}
                  data-testid="assistant-input"
                  className="flex-1"
                />
                <Button
                  type="submit"
                  disabled={loading || !input.trim() || escalationStatus?.escalated}
                  className="bg-electric-teal hover:bg-teal-600"
                  data-testid="send-question-btn"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </form>
              {conversationId && !escalationStatus?.escalated && (
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleEscalate}
                    disabled={escalating || loading}
                    className="text-gray-600"
                    data-testid="assistant-talk-to-human-btn"
                  >
                    <UserCircle className="w-3.5 h-3.5 mr-1" />
                    {escalating ? 'Sending…' : 'Talk to a human'}
                  </Button>
                </div>
              )}
              <p className="text-xs text-gray-500 mt-2">
                Information only. Not legal advice. Rate limited.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Example Questions */}
        <Card className="mt-6">
          <CardContent className="pt-6">
            <h3 className="text-sm font-semibold text-midnight-blue mb-3">Quick Questions:</h3>
            <div className="flex flex-wrap gap-2">
              {[
                "What is my overall compliance status?",
                "Which properties need attention?",
                "What are my upcoming deadlines?",
                "How many documents have I uploaded?",
                "What does my compliance score mean?"
              ].map((example, i) => (
                <button
                  key={i}
                  onClick={() => handleQuickQuestion(example)}
                  className="text-sm px-3 py-1.5 bg-gray-100 hover:bg-electric-teal/10 text-gray-700 hover:text-electric-teal rounded-full transition-colors"
                  disabled={loading}
                  data-testid={`quick-question-${i}`}
                >
                  {example}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default AssistantPage;
