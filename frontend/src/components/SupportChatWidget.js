/**
 * Pleerity Support Chat Widget
 * 
 * AI-powered chatbot with:
 * - Quick Actions panel for common requests
 * - Canned responses for instant answers
 * - Live chat via Tawk.to
 * - WhatsApp continuation
 * - Email ticket creation
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  MessageCircle, X, Send, Loader2, User, Bot, Phone,
  Mail, MessageSquare, ExternalLink, Minimize2, Maximize2,
  Package, Key, FileText, CreditCard, Home, Users, ChevronDown
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import client from '../api/client';
import { TawkToAPI } from './TawkToWidget';

// Quick action icons mapping
const QUICK_ACTION_ICONS = {
  check_order_status: Package,
  reset_password: Key,
  document_packs_info: FileText,
  billing_help: CreditCard,
  cvp_info: Home,
  speak_to_human: Users,
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

// Quick Actions Panel
function QuickActionsPanel({ onAction, loading }) {
  const actions = [
    { id: 'check_order_status', label: 'Check Order Status', icon: '📦', color: 'bg-blue-50 hover:bg-blue-100 border-blue-200' },
    { id: 'reset_password', label: 'Reset Password', icon: '🔑', color: 'bg-amber-50 hover:bg-amber-100 border-amber-200' },
    { id: 'document_packs_info', label: 'Document Packs', icon: '📄', color: 'bg-green-50 hover:bg-green-100 border-green-200' },
    { id: 'billing_help', label: 'Billing Help', icon: '💳', color: 'bg-purple-50 hover:bg-purple-100 border-purple-200' },
    { id: 'cvp_info', label: 'CVP Info', icon: '🏠', color: 'bg-cyan-50 hover:bg-cyan-100 border-cyan-200' },
    { id: 'speak_to_human', label: 'Speak to Human', icon: '👤', color: 'bg-rose-50 hover:bg-rose-100 border-rose-200' },
  ];

  return (
    <div className="p-3 bg-gray-50 border-b">
      <p className="text-xs text-gray-500 mb-2 font-medium">Quick Actions</p>
      <div className="grid grid-cols-3 gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            onClick={() => onAction(action.id)}
            disabled={loading}
            className={`flex flex-col items-center p-2 rounded-lg border transition-colors text-center ${action.color} disabled:opacity-50`}
            data-testid={`quick-action-${action.id}`}
          >
            <span className="text-lg mb-1">{action.icon}</span>
            <span className="text-xs text-gray-700 leading-tight">{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// Handoff options component
function HandoffOptions({ options, onSelect, conversationId, onWhatsAppClick }) {
  return (
    <div className="bg-blue-50 rounded-lg p-4 mb-3">
      <p className="text-sm font-medium text-blue-800 mb-3">
        Choose how you&apos;d like to continue:
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
          <button
            onClick={() => onWhatsAppClick(options.whatsapp.link)}
            className="flex items-center gap-2 w-full px-4 py-2 rounded-md border bg-white hover:bg-gray-50 text-sm text-left"
            data-testid="whatsapp-handoff-btn"
          >
            <Phone className="w-4 h-4 text-green-500" />
            <span>Continue on WhatsApp</span>
            <ExternalLink className="w-3 h-3 ml-auto text-gray-400" />
          </button>
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
  const [showQuickActions, setShowQuickActions] = useState(true);
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
        ? `Hello! 👋 I'm Pleerity Support. I can see you're logged in - I can help with your account, orders, or any questions about our services.\n\nUse the quick actions below or type your question!`
        : `Hello! 👋 I'm Pleerity Support, your AI assistant.\n\nUse the **quick actions** below for instant help, or type your question!`;

      setMessages([{
        id: 'greeting',
        text: greeting,
        sender: 'bot',
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [isOpen, messages.length, isAuthenticated]);

  // Handle WhatsApp click with proper window.open and audit logging
  const handleWhatsAppClick = async (whatsappLink) => {
    // Open WhatsApp in new tab using window.open (avoids iframe blocking)
    window.open(whatsappLink, '_blank', 'noopener,noreferrer');
    
    // Log the event for audit
    try {
      await client.post('/support/audit/whatsapp-handoff', {
        conversation_id: conversationId,
        user_role: isAuthenticated ? 'authenticated' : 'anonymous',
        client_id: clientContext?.client_id || null,
        page_url: window.location.href,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.error('Failed to log WhatsApp handoff:', err);
    }
    
    // Add confirmation message
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      text: '✅ Opening WhatsApp... Your conversation reference has been included in the message.',
      sender: 'bot',
      timestamp: new Date().toISOString(),
    }]);
    setShowHandoff(false);
  };

  // Handle quick action
  const handleQuickAction = async (actionId) => {
    setLoading(true);
    setShowHandoff(false);
    setShowQuickActions(false);

    try {
      const response = await client.post(`/support/quick-action/${actionId}`, null, {
        params: { conversation_id: conversationId }
      });

      setConversationId(response.data.conversation_id);

      // Add user action as message
      const actionLabels = {
        check_order_status: '📦 Check Order Status',
        reset_password: '🔑 Reset Password',
        document_packs_info: '📄 Document Packs Info',
        billing_help: '💳 Billing Help',
        cvp_info: '🏠 CVP Info',
        speak_to_human: '👤 Speak to Human',
      };

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        text: actionLabels[actionId] || actionId,
        sender: 'user',
        timestamp: new Date().toISOString(),
      }]);

      // Add bot response
      setMessages(prev => [...prev, {
        id: Date.now().toString() + '-bot',
        text: response.data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
      }]);

      // Handle handoff if needed
      if (response.data.action === 'handoff') {
        setShowHandoff(true);
        setHandoffOptions(response.data.handoff_options);
      }
    } catch (err) {
      console.error('Quick action error:', err);
      toast.error('Failed to process. Please try again.');
    } finally {
      setLoading(false);
    }
  };

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
    setShowQuickActions(false);

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
      // Open Tawk.to widget with context
      TawkToAPI.openWithContext({
        conversationId: conversationId,
        serviceArea: 'support',
        category: 'general',
      });
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
      className={`fixed bottom-24 right-6 bg-white rounded-2xl shadow-2xl z-50 transition-all overflow-hidden ${
        isMinimized ? 'w-72 h-14' : 'w-96 h-[550px]'
      }`}
      data-testid="support-chat-widget"
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-teal-600 to-teal-500 text-white px-4 py-3 flex items-center justify-between">
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
          {/* Quick Actions Panel - Collapsible */}
          {showQuickActions && messages.length <= 1 && (
            <QuickActionsPanel onAction={handleQuickAction} loading={loading} />
          )}
          
          {/* Toggle Quick Actions button */}
          {messages.length > 1 && !showQuickActions && (
            <button
              onClick={() => setShowQuickActions(true)}
              className="w-full px-3 py-2 bg-gray-50 text-xs text-gray-600 hover:bg-gray-100 flex items-center justify-center gap-1 border-b"
            >
              <ChevronDown className="w-3 h-3" />
              Show Quick Actions
            </button>
          )}
          
          {showQuickActions && messages.length > 1 && (
            <>
              <QuickActionsPanel onAction={handleQuickAction} loading={loading} />
              <button
                onClick={() => setShowQuickActions(false)}
                className="w-full px-3 py-1 bg-gray-100 text-xs text-gray-500 hover:bg-gray-200"
              >
                Hide Quick Actions
              </button>
            </>
          )}

          {/* Messages */}
          <div className={`overflow-y-auto p-4 ${showQuickActions && messages.length <= 1 ? 'h-[280px]' : 'h-[360px]'}`}>
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
