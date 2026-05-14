/**
 * Pleerity Support Chat Widget
 * 
 * AI-powered chatbot with:
 * - FAQ Tab with top questions before chat
 * - Quick Actions panel for common requests
 * - Canned responses for instant answers
 * - Live chat via Tawk.to
 * - WhatsApp continuation
 * - Email ticket creation
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  MessageCircle, X, Send, Loader2, User, Bot, Phone,
  Mail, MessageSquare, ExternalLink, Minimize2, Maximize2,
  Package, Key, FileText, CreditCard, Home, Users, ChevronDown,
  Book, Search, ArrowRight
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { toast } from '@/utils/portalNotifications';
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

// Onboarding welcome (task: exact wording; module-level for stable useEffect dependency)
const WELCOME_MESSAGE = 'Hello, welcome to Pleerity. What are you trying to do today?';

// Match URLs for linkification (http/https, optional trailing punctuation stripped for display)
const URL_REGEX = /https?:\/\/[^\s<>"{}|\\^`[\]]+/gi;

function linkifyText(text) {
  if (!text || typeof text !== 'string') return [text];
  const parts = [];
  let lastIndex = 0;
  let match;
  const re = new RegExp(URL_REGEX.source, 'gi');
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: text.slice(lastIndex, match.index) });
    }
    let href = match[0];
    const trailing = /[.,;:!?)]+$/.exec(href);
    if (trailing) {
      href = href.slice(0, href.length - trailing[0].length);
      parts.push({ type: 'link', href, label: href });
      parts.push({ type: 'text', value: trailing[0] });
    } else {
      parts.push({ type: 'link', href, label: href });
    }
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push({ type: 'text', value: text.slice(lastIndex) });
  }
  return parts.length ? parts : [{ type: 'text', value: text }];
}

// Message bubble component – bot messages get linkified URLs + optional action buttons/links
function MessageBubble({ message, isUser }) {
  const content = isUser ? (
    <div className="text-sm whitespace-pre-wrap">{message.text}</div>
  ) : (
    <>
      <div className="text-sm whitespace-pre-wrap">
        {linkifyText(message.text).map((part, i) =>
          part.type === 'link' ? (
            <a
              key={i}
              href={part.href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-600 underline break-all"
            >
              {part.label}
            </a>
          ) : (
            <span key={i}>{part.value}</span>
          )
        )}
      </div>
      {!isUser && message.actions && message.actions.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3" data-testid="message-actions">
          {message.actions.map((action, i) => {
            const label = action.label ?? '';
            const url = action.url;
            if (url) {
              return (
                <a
                  key={i}
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-lg border border-teal-200 bg-teal-50 text-teal-700 text-sm font-medium hover:bg-teal-100 transition-colors"
                  data-testid={`message-action-${i}`}
                >
                  {label}
                </a>
              );
            }
            return (
              <span
                key={i}
                className="inline-flex items-center px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 text-gray-600 text-sm"
              >
                {label}
              </span>
            );
          })}
        </div>
      )}
    </>
  );

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
          {content}
          <div className={`text-xs mt-1 ${isUser ? 'text-teal-100' : 'text-gray-400'}`}>
            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Onboarding: 5 options when chat is empty (task: welcome + 5 options)
function OnboardingOptionsPanel({ options, onSelect, loading }) {
  return (
    <div className="p-3 bg-gray-50 border-b">
      <div className="grid grid-cols-1 gap-2">
        {options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            onClick={() => onSelect(opt)}
            disabled={loading}
            className="flex items-center gap-2 p-2.5 rounded-lg border border-gray-200 bg-white hover:bg-teal-50 hover:border-teal-200 text-left text-sm font-medium text-gray-800 disabled:opacity-50 transition-colors"
            data-testid={`onboarding-option-${opt.id}`}
          >
            <span className="text-teal-600">{opt.id === 'compliance' ? '🏠' : opt.id === 'documents' ? '📄' : opt.id === 'automation' ? '⚙️' : opt.id === 'research' ? '📊' : '👤'}</span>
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// Qualification: 4 user-type buttons (when backend asks "Are you a: Landlord / ...?")
function QualificationButtons({ options, onSelect, loading }) {
  if (!options || !Array.isArray(options) || options.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onSelect(opt.label)}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg border border-teal-200 bg-teal-50 hover:bg-teal-100 text-sm text-gray-800 disabled:opacity-50"
          data-testid={`qualification-${opt.id}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// Portfolio size follow-up (when backend asks "How many properties do you manage?")
function PortfolioSizeButtons({ options, onSelect, loading }) {
  if (!options || !Array.isArray(options) || options.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          type="button"
          onClick={() => onSelect(opt.label)}
          disabled={loading}
          className="px-3 py-1.5 rounded-lg border border-teal-200 bg-teal-50 hover:bg-teal-100 text-sm text-gray-800 disabled:opacity-50"
          data-testid={`portfolio-size-${opt.id}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// Lead capture: offer email and submit to /api/leads/capture/chatbot
function LeadCaptureBlock({ onSubmitted, onDismiss, conversationId, serviceInterest, loading, recentMessages = [] }) {
  const [step, setStep] = useState('offer'); // 'offer' | 'input'
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const intentToServiceInterest = {
    compliance_vault_pro: 'cvp',
    document_packs: 'document packs',
    automation: 'automation',
    market_research: 'market research',
  };
  const serviceInterestValue = intentToServiceInterest[serviceInterest] || serviceInterest;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    try {
      const contextLines = (recentMessages || [])
        .filter((m) => m.id !== 'greeting')
        .slice(-8)
        .map((m) => `${m.sender === 'user' ? 'User' : 'Assistant'}: ${(m.text || '').slice(0, 500)}`)
        .join('\n');
      await client.post('/leads/capture/chatbot', {
        email: email.trim(),
        service_interest: serviceInterestValue || undefined,
        conversation_id: conversationId || undefined,
        marketing_consent: false,
        interaction_context: contextLines || undefined,
      });
      onSubmitted();
    } catch (err) {
      console.error('Lead capture error:', err);
      toast.error('Failed to submit. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (step === 'offer') {
    return (
      <div className="flex gap-2 mt-2">
        <Button size="sm" variant="outline" onClick={() => setStep('input')} disabled={loading}>
          Yes
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onDismiss()} disabled={loading}>
          No
        </Button>
      </div>
    );
  }
  return (
    <form onSubmit={handleSubmit} className="mt-2 space-y-2">
      <Input
        type="email"
        placeholder="Your email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        className="text-sm"
        disabled={submitting}
      />
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="bg-teal-600 hover:bg-teal-700" disabled={submitting}>
          {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send me information'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => onDismiss()} disabled={submitting}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

// Quick Actions Panel (order per task: CVP, Document Packs, Pricing, Reset Password, Talk to Support, Start New Chat)
function QuickActionsPanel({ onAction, onReset, loading }) {
  const actions = [
    { id: 'cvp_info', label: 'Compliance Vault Pro', icon: '🏠', color: 'bg-cyan-50 hover:bg-cyan-100 border-cyan-200' },
    { id: 'document_packs_info', label: 'Document Packs', icon: '📄', color: 'bg-green-50 hover:bg-green-100 border-green-200' },
    { id: 'pricing', label: 'Pricing', icon: '💳', color: 'bg-purple-50 hover:bg-purple-100 border-purple-200' },
    { id: 'reset_password', label: 'Reset Password', icon: '🔑', color: 'bg-amber-50 hover:bg-amber-100 border-amber-200' },
    { id: 'speak_to_human', label: 'Talk to Support', icon: '👤', color: 'bg-rose-50 hover:bg-rose-100 border-rose-200' },
    { id: 'check_order_status', label: 'Check Order Status', icon: '📦', color: 'bg-blue-50 hover:bg-blue-100 border-blue-200' },
    { id: 'billing_help', label: 'Billing Help', icon: '💳', color: 'bg-slate-50 hover:bg-slate-100 border-slate-200' },
  ];

  return (
    <div className="p-3 bg-gray-50 border-b">
      <p className="text-xs text-gray-500 mb-2 font-medium">Quick Actions</p>
      <div className="grid grid-cols-3 gap-2">
        {actions.map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => onAction(action.id)}
            disabled={loading}
            className={`flex flex-col items-center p-2 rounded-lg border transition-colors text-center ${action.color} disabled:opacity-50`}
            data-testid={`quick-action-${action.id}`}
          >
            <span className="text-lg mb-1">{action.icon}</span>
            <span className="text-xs text-gray-700 leading-tight">{action.label}</span>
          </button>
        ))}
        {onReset && (
          <button
            type="button"
            onClick={onReset}
            disabled={loading}
            className="flex flex-col items-center p-2 rounded-lg border border-slate-200 bg-slate-50 hover:bg-slate-100 text-center disabled:opacity-50"
            data-testid="quick-action-start_new_chat"
          >
            <span className="text-lg mb-1">🔄</span>
            <span className="text-xs text-gray-700 leading-tight">Start New Chat</span>
          </button>
        )}
      </div>
    </div>
  );
}

// Handoff options component
function HandoffOptions({ options, onSelect, conversationId, onWhatsAppClick }) {
  const liveAvailable = options?.live_chat?.available;
  const notice = options?.live_chat_notice;

  return (
    <div className="bg-blue-50 rounded-lg p-4 mb-3">
      <p className="text-sm font-medium text-blue-800 mb-3">
        Choose how you&apos;d like to continue:
      </p>
      {notice && (
        <p className="text-xs text-blue-900 bg-blue-100/80 border border-blue-200 rounded-md px-3 py-2 mb-3">
          {notice}
        </p>
      )}
      <div className="space-y-2">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 bg-white hover:bg-gray-50"
          onClick={() => onSelect('livechat')}
          disabled={!liveAvailable}
          title={!liveAvailable ? 'Live chat is not configured' : undefined}
        >
          <MessageSquare className="w-4 h-4 text-green-600" />
          <span>Live Chat with Agent</span>
          <Badge variant="secondary" className="ml-auto text-xs">
            {liveAvailable ? 'Online' : 'Unavailable'}
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
function EmailTicketForm({ conversationId, onSubmit, onCancel, initialSubject = '', initialDescription = '' }) {
  const [form, setForm] = useState({
    email: '',
    subject: '',
    description: '',
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setForm((f) => ({
      ...f,
      ...(initialSubject ? { subject: initialSubject } : {}),
      ...(initialDescription ? { description: initialDescription } : {}),
    }));
  }, [initialSubject, initialDescription]);

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

// FAQ Tab Component - Shows top questions before chatting
function FAQTab({ onStartChat, onSelectArticle }) {
  const [faqArticles, setFaqArticles] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFeatured = async () => {
      try {
        const response = await client.get('/kb/featured');
        setFaqArticles(response.data.popular?.slice(0, 5) || []);
      } catch (err) {
        console.error('Failed to fetch FAQ articles:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchFeatured();
  }, []);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setSearching(true);
    try {
      const response = await client.get(`/kb/articles?search=${encodeURIComponent(searchQuery)}&limit=5`);
      setSearchResults(response.data.articles || []);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setSearching(false);
    }
  };

  const displayArticles = searchResults.length > 0 ? searchResults : faqArticles;

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {/* Search */}
      <div className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
          <Input
            placeholder="Search for answers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="pl-10 pr-16"
            data-testid="faq-search-input"
          />
          <Button
            size="sm"
            variant="ghost"
            className="absolute right-1 top-1/2 -translate-y-1/2 h-7"
            onClick={handleSearch}
            disabled={searching}
          >
            {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Search'}
          </Button>
        </div>
      </div>

      {/* Articles */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-gray-500 mb-2">
          {searchResults.length > 0 ? 'Search Results' : 'Top Questions'}
        </p>
        
        {loading ? (
          <div className="text-center py-4 text-gray-400">
            <Loader2 className="h-5 w-5 animate-spin mx-auto" />
          </div>
        ) : displayArticles.length > 0 ? (
          displayArticles.map(article => (
            <button
              key={article.article_id}
              onClick={() => onSelectArticle(article)}
              className="w-full text-left p-3 rounded-lg border bg-white hover:bg-gray-50 transition-colors"
              data-testid={`faq-article-${article.article_id}`}
            >
              <p className="text-sm font-medium text-gray-800 line-clamp-1">{article.title}</p>
              <p className="text-xs text-gray-500 line-clamp-1 mt-1">{article.excerpt}</p>
            </button>
          ))
        ) : searchQuery ? (
          <div className="text-center py-4">
            <p className="text-sm text-gray-500 mb-3">No articles found</p>
            <Button
              size="sm"
              onClick={onStartChat}
              className="bg-teal-600 hover:bg-teal-700"
            >
              <MessageCircle className="h-4 w-4 mr-2" />
              Chat with Us
            </Button>
          </div>
        ) : null}
      </div>

      {/* View All + Chat CTA */}
      <div className="mt-6 space-y-3">
        <Link
          to="/support/knowledge-base"
          className="flex items-center justify-center gap-2 text-sm text-teal-600 hover:text-teal-700"
          data-testid="view-all-kb-link"
        >
          <Book className="h-4 w-4" />
          View All Articles
          <ArrowRight className="h-4 w-4" />
        </Link>
        
        <div className="border-t pt-3">
          <p className="text-xs text-gray-500 text-center mb-2">Can not find what you need?</p>
          <Button
            onClick={onStartChat}
            className="w-full bg-teal-600 hover:bg-teal-700"
            data-testid="start-chat-from-faq-btn"
          >
            <MessageCircle className="h-4 w-4 mr-2" />
            Start a Conversation
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SupportChatWidget({ isAuthenticated = false, clientContext = null }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [activeTab, setActiveTab] = useState('faq'); // 'faq' or 'chat'
  const [showQuickActions, setShowQuickActions] = useState(true);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [showHandoff, setShowHandoff] = useState(false);
  const [handoffOptions, setHandoffOptions] = useState(null);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const [ticketPrefill, setTicketPrefill] = useState({ subject: '', description: '' });
  const [conversationContext, setConversationContext] = useState({
    intent: null,
    topic: null,
    last_action: null,
    user_type: null,
    onboarding_step: null,
    lead_capture_offered: null,
    portfolio_size: null,
    primary_goal: null,
    secondary_need: null,
    problem_intent: null,
  });
  const [leadCaptureSubmitted, setLeadCaptureSubmitted] = useState(false);
  const messagesEndRef = useRef(null);

  const resetConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setConversationContext({
      intent: null,
      topic: null,
      last_action: null,
      user_type: null,
      onboarding_step: null,
      lead_capture_offered: null,
      portfolio_size: null,
      primary_goal: null,
      secondary_need: null,
      problem_intent: null,
    });
    setLeadCaptureSubmitted(false);
    setShowHandoff(false);
    setShowQuickActions(true);
    setShowTicketForm(false);
    setTicketPrefill({ subject: '', description: '' });
  }, []);

  // Expose open function globally for external triggers
  useEffect(() => {
    window.openSupportChat = () => {
      setIsOpen(true);
      setActiveTab('chat');
    };
    return () => {
      delete window.openSupportChat;
    };
  }, []);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Add initial greeting when chat tab opens or after reset
  useEffect(() => {
    if (isOpen && activeTab === 'chat' && messages.length === 0) {
      setMessages([{
        id: 'greeting',
        text: WELCOME_MESSAGE,
        sender: 'bot',
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [isOpen, activeTab, messages.length]);

  // Onboarding options (task: 5 options that set intent)
  const ONBOARDING_OPTIONS = [
    { id: 'compliance', label: 'Manage property compliance', message: 'Manage property compliance' },
    { id: 'documents', label: 'Get landlord documents', message: 'Get landlord documents' },
    { id: 'automation', label: 'Automate workflows', message: 'Automate workflows' },
    { id: 'research', label: 'Get market research', message: 'Get market research' },
    { id: 'support', label: 'Contact support', quickAction: 'speak_to_human' },
  ];

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
      if (response.data.conversation_context) {
        setConversationContext(response.data.conversation_context);
      }

      // Add user action as message
      const actionLabels = {
        check_order_status: '📦 Check Order Status',
        reset_password: '🔑 Reset Password',
        document_packs_info: '📄 Document Packs',
        billing_help: '💳 Billing Help',
        cvp_info: '🏠 Compliance Vault Pro',
        pricing: '💳 Pricing',
        speak_to_human: '👤 Talk to Support',
      };

      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        text: actionLabels[actionId] || actionId,
        sender: 'user',
        timestamp: new Date().toISOString(),
      }]);

      // Add bot response (with metadata and actions for clickable links)
      setMessages(prev => [...prev, {
        id: Date.now().toString() + '-bot',
        text: response.data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
        metadata: response.data.metadata || null,
        actions: response.data.actions ?? null,
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

    const trimmed = input.trim();
    if (/^(reset|start over|new chat)$/i.test(trimmed)) {
      resetConversation();
      setInput('');
      return;
    }

    const userMessage = {
      id: Date.now().toString(),
      text: trimmed,
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
        conversation_context: conversationContext,
      });

      setConversationId(response.data.conversation_id);
      if (response.data.conversation_context) {
        setConversationContext(response.data.conversation_context);
      }

      const botMessage = {
        id: Date.now().toString() + '-bot',
        text: response.data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
        metadata: response.data.metadata || null,
        actions: response.data.actions ?? null,
      };

      setMessages(prev => [...prev, botMessage]);

      const hs = response.data.handoff_summary;
      if (hs) {
        setTicketPrefill({
          subject: 'Support request — Pleerity assistant',
          description: hs,
        });
      }

      // Handle handoff
      if (response.data.action === 'handoff') {
        setShowHandoff(true);
        setHandoffOptions(response.data.handoff_options);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const detail = err.response?.data?.detail;
      if (err.response?.status === 429 && typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('Failed to send message. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Send a message as the user (for onboarding/qualification button clicks)
  const sendMessageAs = async (text) => {
    if (!text.trim() || loading) return;
    const userMessage = {
      id: Date.now().toString(),
      text: text.trim(),
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
        conversation_context: conversationContext,
      });
      setConversationId(response.data.conversation_id);
      if (response.data.conversation_context) {
        setConversationContext(response.data.conversation_context);
      }
      const botMsg = {
        id: Date.now().toString() + '-bot',
        text: response.data.response,
        sender: 'bot',
        timestamp: new Date().toISOString(),
        metadata: response.data.metadata || null,
        actions: response.data.actions ?? null,
      };
      setMessages(prev => [...prev, botMsg]);
      const hs2 = response.data.handoff_summary;
      if (hs2) {
        setTicketPrefill({
          subject: 'Support request — Pleerity assistant',
          description: hs2,
        });
      }
      if (response.data.action === 'handoff') {
        setShowHandoff(true);
        setHandoffOptions(response.data.handoff_options);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const detail = err.response?.data?.detail;
      if (err.response?.status === 429 && typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('Failed to send message. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Onboarding: user picked one of the 5 options
  const handleOnboardingSelect = async (option) => {
    if (option.quickAction) {
      await handleQuickAction(option.quickAction);
      return;
    }
    await sendMessageAs(option.message);
  };

  // Handle handoff selection
  const handleHandoffSelect = (option) => {
    if (option === 'livechat') {
      if (handoffOptions && handoffOptions.live_chat && !handoffOptions.live_chat.available) {
        toast.error(
          handoffOptions.live_chat_notice
            || 'Live chat is not available right now. You can still create a ticket.'
        );
        return;
      }
      // Record handoff and create ticket so it appears in admin queue (non-blocking)
      if (conversationId) {
        client.post(`/support/conversation/${conversationId}/live-chat-handoff`)
          .then(() => {})
          .catch(() => {});
      }
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
      className={`fixed bottom-24 right-6 bg-white rounded-2xl shadow-2xl z-50 transition-all overflow-hidden flex flex-col ${
        isMinimized ? 'w-72 h-14' : 'w-96 h-[550px] max-h-[calc(100vh-6rem)]'
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
          {!isMinimized && (
            <button
              type="button"
              onClick={resetConversation}
              className="p-1.5 hover:bg-white/10 rounded-full transition-colors text-xs font-medium"
              title="Start new chat"
              data-testid="support-chat-reset"
            >
              Start new chat
            </button>
          )}
          <button
            type="button"
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
            type="button"
            onClick={() => setIsOpen(false)}
            className="p-1.5 hover:bg-white/10 rounded-full transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <div className="flex flex-col flex-1 min-h-0">
          {/* Tabs */}
          <div className="flex border-b shrink-0">
            <button
              onClick={() => setActiveTab('faq')}
              className={`flex-1 py-2 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
                activeTab === 'faq'
                  ? 'text-teal-600 border-b-2 border-teal-600 bg-teal-50/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
              data-testid="faq-tab"
            >
              <Book className="h-4 w-4" />
              FAQ
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex-1 py-2 text-sm font-medium flex items-center justify-center gap-2 transition-colors ${
                activeTab === 'chat'
                  ? 'text-teal-600 border-b-2 border-teal-600 bg-teal-50/50'
                  : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
              data-testid="chat-tab"
            >
              <MessageCircle className="h-4 w-4" />
              Chat
            </button>
          </div>

          {/* FAQ Tab Content */}
          {activeTab === 'faq' && (
            <FAQTab
              onStartChat={() => setActiveTab('chat')}
              onSelectArticle={(article) => {
                // Open article in new tab or navigate
                window.open(`/support/knowledge-base/${article.slug}`, '_blank');
              }}
            />
          )}

          {/* Chat Tab Content */}
          {activeTab === 'chat' && (
            <div className="flex flex-col flex-1 min-h-0">
              {/* Scrollable area: onboarding options + messages so nothing is cut off on short viewports */}
              <div className="flex-1 min-h-0 overflow-y-auto">
                {/* Onboarding: 5 options when only welcome is shown (task: exact 5 options) */}
                {messages.length === 1 && messages[0].sender === 'bot' && (
                  <OnboardingOptionsPanel
                    options={ONBOARDING_OPTIONS}
                    onSelect={handleOnboardingSelect}
                    loading={loading}
                  />
                )}
                {/* Quick Actions Panel - after first exchange (support options + Start New Chat) */}
                {showQuickActions && messages.length > 1 && (
                  <QuickActionsPanel onAction={handleQuickAction} onReset={resetConversation} loading={loading} />
                )}
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
                    <QuickActionsPanel onAction={handleQuickAction} onReset={resetConversation} loading={loading} />
                    <button
                      onClick={() => setShowQuickActions(false)}
                      className="w-full px-3 py-1 bg-gray-100 text-xs text-gray-500 hover:bg-gray-200"
                    >
                      Hide Quick Actions
                    </button>
                  </>
                )}

                {/* Messages */}
                <div className="p-4 min-h-[280px]">
            {messages.map((msg, idx) => (
              <div key={msg.id}>
                <MessageBubble
                  message={msg}
                  isUser={msg.sender === 'user'}
                />
                {msg.sender === 'bot' && msg.metadata?.qualification_question && idx === messages.length - 1 && (
                  <QualificationButtons
                    options={msg.metadata.user_type_options}
                    onSelect={sendMessageAs}
                    loading={loading}
                  />
                )}
                {msg.sender === 'bot' && msg.metadata?.follow_up === 'portfolio_size' && idx === messages.length - 1 && (
                  <PortfolioSizeButtons
                    options={msg.metadata.portfolio_size_options}
                    onSelect={sendMessageAs}
                    loading={loading}
                  />
                )}
              </div>
            ))}
            {/* Lead capture: show when last bot message offers it and not yet submitted */}
            {messages.length > 0 && (() => {
              const last = messages[messages.length - 1];
              return last.sender === 'bot' && last.metadata?.offer_lead_capture && !leadCaptureSubmitted;
            })() && (
              <div className="mt-2 pl-9">
                <LeadCaptureBlock
                  onSubmitted={() => {
                    setLeadCaptureSubmitted(true);
                    setMessages(prev => [...prev, {
                      id: Date.now().toString() + '-lead-confirm',
                      text: "We've sent the information to your email. Check your inbox for next steps.",
                      sender: 'bot',
                      timestamp: new Date().toISOString(),
                    }]);
                  }}
                  onDismiss={() => setLeadCaptureSubmitted(true)}
                  conversationId={conversationId}
                  serviceInterest={conversationContext?.intent}
                  loading={loading}
                  recentMessages={messages}
                />
              </div>
            )}
            
            {/* Handoff options */}
            {showHandoff && handoffOptions && (
              <HandoffOptions
                options={handoffOptions}
                onSelect={handleHandoffSelect}
                conversationId={conversationId}
                onWhatsAppClick={handleWhatsAppClick}
              />
            )}
            
            {/* Ticket form */}
            {showTicketForm && (
              <EmailTicketForm
                conversationId={conversationId}
                initialSubject={ticketPrefill.subject}
                initialDescription={ticketPrefill.description}
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
              </div>

              {/* Input */}
              <div className="p-3 border-t shrink-0">
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
            </div>
          )}
        </div>
      )}
    </div>
  );
}
