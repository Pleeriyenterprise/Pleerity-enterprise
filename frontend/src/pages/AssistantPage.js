import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Send, ArrowLeft, AlertCircle, MessageSquare, Shield, ChevronDown, ChevronUp, FileText, Sparkles, RefreshCw } from 'lucide-react';
import axios from 'axios';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const AssistantPage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello! I'm your Compliance Vault Pro assistant. I can explain your compliance data and help you understand your dashboard.`,
      what_this_is_based_on: [],
      next_actions: [
        "Ask about your overall compliance status",
        "Ask which properties need attention",
        "Ask about upcoming deadlines"
      ]
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [expandedMessages, setExpandedMessages] = useState({});
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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

    // Add user message to chat
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setLoading(true);

    try {
      const token = localStorage.getItem('auth_token');
      const response = await axios.post(
        `${API_URL}/api/assistant/ask`,
        { question: userMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      const { 
        answer, 
        what_this_is_based_on, 
        next_actions, 
        refused, 
        refusal_reason,
        correlation_id 
      } = response.data;

      // Add assistant response
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: answer,
          what_this_is_based_on: what_this_is_based_on || [],
          next_actions: next_actions || [],
          refused: refused,
          refusal_reason: refusal_reason,
          correlation_id: correlation_id
        }
      ]);
    } catch (err) {
      const errorDetail = err.response?.data?.detail || 'Assistant unavailable. Please try again or refresh.';
      setError(errorDetail);
      toast.error(errorDetail);
      
      // Add error message to chat
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'Assistant unavailable. Please try again or refresh.',
          error: true,
          next_actions: ['Refresh the page', 'Contact support if the issue persists']
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickQuestion = (question) => {
    setInput(question);
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
            <strong>Important:</strong> This assistant explains your compliance data only. It does not provide legal advice.
            For legal guidance, please consult a qualified solicitor.
          </AlertDescription>
        </Alert>

        {/* Chat Container */}
        <Card className="shadow-lg">
          <CardHeader className="border-b">
            <CardTitle className="text-midnight-blue flex items-center justify-between">
              <span>Ask About Your Compliance</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => window.location.reload()}
                className="text-gray-500 hover:text-gray-700"
              >
                <RefreshCw className="w-4 h-4 mr-1" />
                Reset
              </Button>
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
                        {/* Main Answer */}
                        <div className="px-4 pt-4 pb-2">
                          <p className="text-sm whitespace-pre-wrap text-gray-800">{message.content}</p>
                        </div>
                        
                        {/* What this is based on - Expandable */}
                        {(message.what_this_is_based_on?.length > 0 || message.next_actions?.length > 0) && (
                          <div className="border-t border-gray-100">
                            <button
                              onClick={() => toggleMessageDetails(index)}
                              className="w-full px-4 py-2 flex items-center justify-between text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                            >
                              <span className="flex items-center gap-1">
                                <FileText className="w-3 h-3" />
                                {expandedMessages[index] ? 'Hide details' : 'Show details'}
                              </span>
                              {expandedMessages[index] ? (
                                <ChevronUp className="w-3 h-3" />
                              ) : (
                                <ChevronDown className="w-3 h-3" />
                              )}
                            </button>
                            
                            {expandedMessages[index] && (
                              <div className="px-4 pb-4 space-y-3 text-xs">
                                {message.what_this_is_based_on?.length > 0 && (
                                  <div>
                                    <p className="font-medium text-gray-600 mb-1">What this is based on:</p>
                                    <ul className="list-disc list-inside text-gray-500 space-y-0.5">
                                      {message.what_this_is_based_on.map((item, i) => (
                                        <li key={i}>{item}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                
                                {message.next_actions?.length > 0 && (
                                  <div>
                                    <p className="font-medium text-gray-600 mb-1">Next actions in portal:</p>
                                    <ul className="space-y-1">
                                      {message.next_actions.map((action, i) => (
                                        <li 
                                          key={i}
                                          className="flex items-center gap-1 text-electric-teal"
                                        >
                                          <span className="w-1 h-1 bg-electric-teal rounded-full" />
                                          {action}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                
                                {message.correlation_id && (
                                  <p className="text-gray-400 text-[10px] pt-2 border-t border-gray-100">
                                    Ref: {message.correlation_id}
                                  </p>
                                )}
                              </div>
                            )}
                          </div>
                        )}
                        
                        {message.refused && message.refusal_reason && (
                          <p className="text-xs px-4 pb-3 text-yellow-600">
                            Note: {message.refusal_reason}
                          </p>
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
                  disabled={loading}
                  maxLength={500}
                  data-testid="assistant-input"
                  className="flex-1"
                />
                <Button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="bg-electric-teal hover:bg-teal-600"
                  data-testid="send-question-btn"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </form>
              <p className="text-xs text-gray-500 mt-2">
                {input.length}/500 characters • Rate limited: 10 questions per 10 minutes
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
