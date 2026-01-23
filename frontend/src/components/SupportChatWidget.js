/**
 * Pleerity Support Chat Widget
 * 
 * AI-powered chatbot with human handoff options:
 * - Live chat via Tawk.to
 * - WhatsApp continuation
 * - Email ticket creation
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle, X, Send, Loader2, User, Bot, Phone,
  Mail, MessageSquare, ExternalLink, Minimize2, Maximize2
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import client from '../api/client';

// Service area icons
const SERVICE_ICONS = {
  cvp: '🏠',
  document_services: '📄',
  ai_automation: '🤖',
  market_research: '📊',
  billing: '💳',
  other: '💬',
};

// Message bubble component
function MessageBubble({ message, isUser }) {
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`flex items-start gap-2 max-w-[85%] ${isUser ? 'flex-row-reverse' : ''}`}>
        <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
          isUser ? 'bg-teal-500' : 'bg-gray-200'
        }`}>
          {isUser ? (
            <User className="w-4 h-4 text-white" />
          ) : (
            <Bot className="w-4 h-4 text-gray-600" />
          )}
        </div>
        <div className={`px-4 py-2 rounded-2xl ${
          isUser 
            ? 'bg-teal-500 text-white rounded-tr-sm' 
            : 'bg-gray-100 text-gray-800 rounded-tl-sm'
        }`}>
          <div className="text-sm whitespace-pre-wrap">{message.text}</div>
          <div className={`text-xs mt-1 ${isUser ? 'text-teal-100' : 'text-gray-400'}`}>
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Handoff options component
function HandoffOptions({ options, onSelect, conversationId }) {
  return (
    <div className="bg-blue-50 rounded-lg p-4 mb-3">
      <p className="text-sm font-medium text-blue-800 mb-3">
        Choose how you'd like to continue:
      </p>
      <div className="space-y-2">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 bg-white hover:bg-gray-50"
          onClick={() => onSelect('livechat')}
        >
          <MessageSquare className="w-4 h-4 text-green-600" />
          <span>Live Chat with Agent</span>
          <Badge variant="secondary" className="ml-auto text-xs">
            {options?.live_chat?.available ? 'Online' : 'Offline'}
          </Badge>
        </Button>
        
        <Button
          variant="outline"
          className="w-full justify-start gap-2 bg-white hover:bg-gray-50"
          onClick={() => onSelect('email')}
        >
          <Mail className="w-4 h-4 text-blue-600" />
          <span>Email Ticket</span>
          <Badge variant="secondary" className="ml-auto text-xs">24hr response</Badge>
        </Button>
        
        {options?.whatsapp?.link && (
          <a
            href={options.whatsapp.link}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 w-full px-4 py-2 rounded-md border bg-white hover:bg-gray-50 text-sm"
          >
            <Phone className="w-4 h-4 text-green-500" />
            <span>Continue on WhatsApp</span>
            <ExternalLink className="w-3 h-3 ml-auto text-gray-400" />
          </a>
        )}
      </div>
      <p className="text-xs text-gray-500 mt-3">
        Reference: {conversationId}
      </p>
    </div>
  );
}

// Email ticket form
function EmailTicketForm({ conversationId, onSubmit, onCancel }) {
  const [form, setForm] = useState({
    email: '',
    subject: '',
    description: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    
    try {
      await client.post('/support/ticket', {
        ...form,
        conversation_id: conversationId,
        contact_method: 'email',
      });
      toast.success('Ticket created! Check your email for confirmation.');
      onSubmit();
    } catch (err) {
      toast.error('Failed to create ticket. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-50 rounded-lg p-4 mb-3 space-y-3">
      <p className="text-sm font-medium text-gray-800">Create Support Ticket</p>
      
      <Input
        type="email"
        placeholder="Your email *"
        value={form.email}
        onChange={(e) => setForm({ ...form, email: e.target.value })}
        required
        className="text-sm"
      />
      
      <Input
        placeholder="Subject *"
        value={form.subject}
        onChange={(e) => setForm({ ...form, subject: e.target.value })}
        required
        className="text-sm"
      />
      
      <textarea
        placeholder="Describe your issue *"
        value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })}
        required
        rows={3}
        className="w-full px-3 py-2 text-sm border rounded-md resize-none focus:outline-none focus:ring-2 focus:ring-teal-500"
      />
      
      <div className="flex gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          size="sm"
          className="bg-teal-600 hover:bg-teal-700"
          disabled={submitting}
        >
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Submit Ticket'}
        </Button>
      </div>
    </form>
  );
}

export default function SupportChatWidget({ isAuthenticated = false, clientContext = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [showHandoff, setShowHandoff] = useState(false);
  const [handoffOptions, setHandoffOptions] = useState(null);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Add initial greeting when chat opens
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      const greeting = isAuthenticated
        ? `Hello! 👋 I'm Pleerity Support. I can see you're logged in - I can help with your account, orders, or any questions about our services.\n\nWhat can I help you with today?`
        : `Hello! 👋 I'm Pleerity Support, your AI assistant. I can help with:\n\n• Compliance Vault Pro\n• Document Packs\n• AI Automation Services\n• Market Research\n• Account & Billing\n\nHow can I assist you today?`;

      setMessages([{
        id: 'greeting',
        text: greeting,
        sender: 'bot',
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [isOpen, messages.length, isAuthenticated]);

  // Send message
  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      id: Date.now().toString(),
      text: input.trim(),
      sender: 'user',
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    setShowHandoff(false);

    try {
      const response = await client.post('/support/chat', {
        message: userMessage.text,
        conversation_id: conversationId,
        channel: isAuthenticated ? 'portal' : 'web',
      });

      setConversationId(response.data.conversation_id);

      const botMessage = {
        id: Date.now().toString() + '-bot',
        text: response.data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
      };

      setMessages(prev => [...prev, botMessage]);

      // Handle handoff
      if (response.data.action === 'handoff') {
        setShowHandoff(true);
        setHandoffOptions(response.data.handoff_options);
      }
    } catch (err) {
      console.error('Chat error:', err);
      toast.error('Failed to send message. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle handoff selection
  const handleHandoffSelect = (option) => {
    if (option === 'livechat') {
      // Open Tawk.to widget if available
      if (window.Tawk_API) {
        window.Tawk_API.maximize();
        // Pass context to Tawk.to
        window.Tawk_API.setAttributes({
          'conversation_id': conversationId,
          'source': 'pleerity_chatbot',
        }, function(error) {});
      } else {
        toast.info('Live chat is loading. Please wait a moment and try again.');
      }
    } else if (option === 'email') {
      setShowTicketForm(true);
      setShowHandoff(false);
    }
  };

  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-24 right-6 w-14 h-14 bg-teal-600 hover:bg-teal-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all hover:scale-110 z-50"
        data-testid="support-chat-button"
      >
        <MessageCircle className="w-6 h-6" />
      </button>
    );
  }

  return (
    <div
      className={`fixed bottom-24 right-6 bg-white rounded-2xl shadow-2xl z-50 transition-all ${
        isMinimized ? 'w-72 h-14' : 'w-96 h-[500px]'
      }`}
      data-testid="support-chat-widget"
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-teal-600 to-teal-500 text-white px-4 py-3 rounded-t-2xl flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
            <MessageCircle className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-semibold text-sm">Pleerity Support</h3>
            {!isMinimized && (
              <p className="text-xs text-teal-100">AI Assistant • 24/7</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setIsMinimized(!isMinimized)}
            className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
          >
            {isMinimized ? (
              <Maximize2 className="w-4 h-4" />
            ) : (
              <Minimize2 className="w-4 h-4" />
            )}
          </button>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="h-[360px] overflow-y-auto p-4">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                isUser={msg.sender === 'user'}
              />
            ))}
            
            {/* Handoff options */}
            {showHandoff && handoffOptions && (
              <HandoffOptions
                options={handoffOptions}
                onSelect={handleHandoffSelect}
                conversationId={conversationId}
              />
            )}
            
            {/* Ticket form */}
            {showTicketForm && (
              <EmailTicketForm
                conversationId={conversationId}
                onSubmit={() => {
                  setShowTicketForm(false);
                  setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    text: "✅ Your support ticket has been created. You'll receive a confirmation email shortly.",
                    sender: 'bot',
                    timestamp: new Date().toISOString(),
                  }]);
                }}
                onCancel={() => {
                  setShowTicketForm(false);
                  setShowHandoff(true);
                }}
              />
            )}
            
            {/* Loading indicator */}
            {loading && (
              <div className="flex justify-start mb-3">
                <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-2">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your message..."
                className="flex-1 text-sm"
                disabled={loading}
                data-testid="chat-input"
              />
              <Button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                size="icon"
                className="bg-teal-600 hover:bg-teal-700 shrink-0"
                data-testid="chat-send"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-xs text-gray-400 mt-2 text-center">
              Powered by Pleerity AI • No legal advice
            </p>
          </div>
        </>
      )}
    </div>
  );
}
