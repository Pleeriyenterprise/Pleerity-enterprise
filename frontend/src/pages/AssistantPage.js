import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Send, ArrowLeft, AlertCircle, MessageSquare, Shield } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const AssistantPage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello! I'm your Compliance Vault Pro assistant. I can explain your compliance data and help you understand your dashboard.\n\n**What I can do:**\n- Explain compliance statuses and deadlines\n- Help you understand requirements\n- Answer questions about your properties\n\n**What I cannot do:**\n- Provide legal advice\n- Create or modify data\n- Predict enforcement outcomes\n\nHow can I help you today?`
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

      const { answer, refused, refusal_reason } = response.data;

      // Add assistant response
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: answer,
          refused: refused,
          refusal_reason: refusal_reason
        }
      ]);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get response');
      // Add error message to chat
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: 'I encountered an error processing your question. Please try again.',
          error: true
        }
      ]);
    } finally {
      setLoading(false);
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
                  <MessageSquare className="w-5 h-5" />
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
            <CardTitle className="text-midnight-blue">Ask About Your Compliance</CardTitle>
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
                    className={`max-w-[80%] rounded-lg px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-midnight-blue text-white'
                        : message.error
                        ? 'bg-red-50 text-red-900 border border-red-200'
                        : message.refused
                        ? 'bg-yellow-50 text-yellow-900 border border-yellow-200'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                    data-testid={`message-${message.role}`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                    {message.refused && message.refusal_reason && (
                      <p className="text-xs mt-2 opacity-75">
                        Reason: {message.refusal_reason}
                      </p>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex justify-start">
                  <div className="bg-gray-100 rounded-lg px-4 py-3">
                    <div className="flex items-center gap-2 text-gray-600">
                      <div className="loading-spinner w-4 h-4" />
                      <span className="text-sm">Thinking...</span>
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
                  className="btn-primary"
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
            <h3 className="text-sm font-semibold text-midnight-blue mb-3">Example Questions:</h3>
            <div className="space-y-2">
              {[
                "What is my overall compliance status?",
                "Which properties have overdue requirements?",
                "What does the AMBER status mean?",
                "How many documents have I uploaded?",
                "When is my next deadline?"
              ].map((example, i) => (
                <button
                  key={i}
                  onClick={() => setInput(example)}
                  className="text-sm text-electric-teal hover:underline block"
                  disabled={loading}
                >
                  • {example}
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
