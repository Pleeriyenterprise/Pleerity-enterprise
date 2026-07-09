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
import {
  computeReplyPacingDelay,
  sleep,
  SUPPORT_ACTIONS_REVEAL_MS,
} from '../utils/supportChatPacing';
import { useSupportCapabilities } from '../utils/accountCapabilityAccess';

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
const WELCOME_MESSAGE = 'Hello - what are you trying to get done today?';

const SUPPORT_AVATAR_SRC = `${process.env.PUBLIC_URL || ''}/images/support-assistant-avatar.png`;

/** Branded assistant avatar with Bot icon fallback if the image fails to load. */
function SupportAssistantAvatar({ className = '', size = 'md' }) {
  const [imgError, setImgError] = useState(false);
  const box = size === 'sm' ? 'w-7 h-7' : 'w-8 h-8';
  const icon = size === 'sm' ? 'w-4 h-4' : 'w-4 h-4';

  if (imgError) {
    return (
      <div
        className={`${box} rounded-full bg-gray-200 flex items-center justify-center shrink-0 ${className}`}
        aria-hidden
      >
        <Bot className={`${icon} text-gray-600`} />
      </div>
    );
  }

  return (
    <img
      src={SUPPORT_AVATAR_SRC}
      alt=""
      role="presentation"
      onError={() => setImgError(true)}
      className={`${box} rounded-full object-cover shrink-0 ${className}`}
      data-testid="support-assistant-avatar"
    />
  );
}

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

/** Lightweight typing indicator while awaiting the assistant. */
function SupportTypingIndicator() {
  return (
    <div
      className="flex justify-start mb-3"
      aria-live="polite"
      aria-label="Assistant is typing"
      data-testid="support-typing-indicator"
    >
      <div className="flex items-start gap-2 max-w-[85%]">
        <SupportAssistantAvatar size="sm" />
        <div className="bg-gray-100 rounded-2xl rounded-tl-sm px-4 py-3">
          <div className="flex items-center gap-1 h-4">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:0ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce [animation-delay:300ms]" />
          </div>
        </div>
      </div>
    </div>
  );
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
      {!isUser && message.actions && message.actions.length > 0 && message.actionsVisible && (
        <div
          className="flex flex-wrap gap-2 mt-3 transition-opacity duration-200 ease-out"
          data-testid="message-actions"
        >
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
                  className="inline-flex items-center px-2.5 py-1 rounded-md border border-gray-200 bg-white text-gray-700 text-xs font-medium hover:bg-gray-50 transition-colors"
                  data-testid={`message-action-${i}`}
                >
                  {label}
                </a>
              );
            }
            return (
              <span
                key={i}
                className="inline-flex items-center px-2.5 py-1 rounded-md border border-gray-200 bg-gray-50 text-gray-600 text-xs"
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
        {isUser ? (
          <div className="w-7 h-7 rounded-full bg-teal-500 flex items-center justify-center shrink-0">
            <User className="w-4 h-4 text-white" />
          </div>
        ) : (
          <SupportAssistantAvatar size="sm" />
        )}
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

// Welcome-state popular tasks (same backend hooks as prior onboarding buttons)
const ONBOARDING_TASK_ITEMS = [
  { id: 'compliance', chipLabel: 'Compliance', testId: 'onboarding-option-compliance', message: 'Manage property compliance' },
  { id: 'documents', chipLabel: 'Documents', testId: 'onboarding-option-documents', message: 'Get landlord documents' },
  { id: 'automation', chipLabel: 'Workflows', testId: 'onboarding-option-automation', message: 'Automate workflows' },
  { id: 'research', chipLabel: 'Research', testId: 'onboarding-option-research', message: 'Get market research' },
  { id: 'support', chipLabel: 'Support', testId: 'onboarding-option-support', quickAction: 'speak_to_human' },
];

// Mid-conversation shortcuts (collapsed by default; same quick-action API)
const SHORTCUT_TASK_ITEMS = [
  { id: 'cvp_info', chipLabel: 'Compliance', testId: 'quick-action-cvp_info', actionId: 'cvp_info' },
  { id: 'document_packs_info', chipLabel: 'Documents', testId: 'quick-action-document_packs_info', actionId: 'document_packs_info' },
  { id: 'pricing', chipLabel: 'Pricing', testId: 'quick-action-pricing', actionId: 'pricing' },
  { id: 'speak_to_human', chipLabel: 'Support', testId: 'quick-action-speak_to_human', actionId: 'speak_to_human' },
  { id: 'reset_password', chipLabel: 'Password', testId: 'quick-action-reset_password', actionId: 'reset_password' },
  { id: 'check_order_status', chipLabel: 'Orders', testId: 'quick-action-check_order_status', actionId: 'check_order_status' },
  { id: 'billing_help', chipLabel: 'Billing', testId: 'quick-action-billing_help', actionId: 'billing_help' },
  { id: 'start_new_chat', chipLabel: 'New chat', testId: 'quick-action-start_new_chat', isReset: true },
];

/** Collapsed-by-default popular tasks — chips when expanded; conversation stays primary. */
function PopularTasksSection({ items, onSelect, onReset, loading, alignWithBot = false }) {
  const [expanded, setExpanded] = useState(false);

  const handleChipClick = (item) => {
    if (item.isReset) {
      onReset?.();
      setExpanded(false);
      return;
    }
    onSelect(item);
    setExpanded(false);
  };

  return (
    <div
      className={alignWithBot ? 'pl-9 mt-1' : ''}
      data-testid="popular-tasks-section"
    >
      <button
        type="button"
        onClick={() => setExpanded((open) => !open)}
        aria-expanded={expanded}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-teal-700 transition-colors py-0.5"
        data-testid="popular-tasks-toggle"
      >
        <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        <span>Popular tasks</span>
        {!expanded && <span className="text-gray-400 font-normal">· optional</span>}
      </button>
      {expanded && (
        <div className="flex flex-wrap gap-1.5 mt-2 max-w-full">
          {items.map((item) => (
            <button
              key={item.id}
              type="button"
              disabled={loading}
              onClick={() => handleChipClick(item)}
              className="px-2.5 py-1 rounded-full border border-gray-200 bg-white text-xs text-gray-700 hover:bg-teal-50 hover:border-teal-200 transition-colors disabled:opacity-50"
              data-testid={item.testId}
            >
              {item.chipLabel}
            </button>
          ))}
        </div>
      )}
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

// Handoff options component (live chat row hidden when Tawk is not configured)
function HandoffOptions({ options, onSelect, conversationId, onWhatsAppClick, tawkVisitorStatus }) {
  const lc = options?.live_chat || {};
  const hideLiveChat = lc.configured === false;
  const notice = options?.live_chat_notice;
  const serverAvailable = !!lc.available;
  const widgetOffline = serverAvailable && tawkVisitorStatus === 'offline';
  const liveClickable = serverAvailable && !widgetOffline;

  let liveBadge = 'Unavailable';
  if (hideLiveChat) {
    liveBadge = '';
  } else if (widgetOffline) {
    liveBadge = 'No agent online';
  } else if (serverAvailable) {
    liveBadge = 'Try live chat';
  } else if (lc.configured) {
    liveBadge = 'Outside hours';
  }

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
        {!hideLiveChat && (
          <Button
            variant="outline"
            className="w-full justify-start gap-2 bg-white hover:bg-gray-50"
            onClick={() => onSelect('livechat')}
            disabled={!liveClickable}
            title={
              !liveClickable && serverAvailable && widgetOffline
                ? 'The chat widget shows no agents online right now'
                : !serverAvailable
                  ? 'Live chat is only offered during configured support hours when Tawk is set up'
                  : undefined
            }
          >
            <MessageSquare className="w-4 h-4 text-green-600" />
            <span>Live Chat with Agent</span>
            {liveBadge ? (
              <Badge variant="secondary" className="ml-auto text-xs">
                {liveBadge}
              </Badge>
            ) : null}
          </Button>
        )}

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
      const res = await client.post('/support/ticket', {
        ...form,
        conversation_id: conversationId,
        contact_method: 'email',
      });
      const d = res.data || {};
      const tid = d.ticket_id || '';
      toast.success(
        tid
          ? `Ticket ${tid} created. We aim to reply by email within 24 hours.`
          : 'Your support ticket has been created.',
      );
      if (typeof onSubmit === 'function') onSubmit(d);
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
  const { canAccessSupport, canRequestSupport } = useSupportCapabilities();
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [activeTab, setActiveTab] = useState('faq'); // 'faq' or 'chat'
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
  const actionRevealTimersRef = useRef([]);
  const [tawkVisitorStatus, setTawkVisitorStatus] = useState(null);

  const clearActionRevealTimers = useCallback(() => {
    actionRevealTimersRef.current.forEach((timerId) => clearTimeout(timerId));
    actionRevealTimersRef.current = [];
  }, []);

  const scheduleActionsReveal = useCallback((messageId) => {
    const timerId = setTimeout(() => {
      actionRevealTimersRef.current = actionRevealTimersRef.current.filter((t) => t !== timerId);
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, actionsVisible: true } : m))
      );
    }, SUPPORT_ACTIONS_REVEAL_MS);
    actionRevealTimersRef.current.push(timerId);
  }, []);

  const buildBotMessageFromResponse = useCallback((responseData) => {
    const hasActions = Array.isArray(responseData.actions) && responseData.actions.length > 0;
    return {
      id: `${Date.now()}-bot`,
      text: responseData.response,
      sender: 'bot',
      timestamp: new Date().toISOString(),
      metadata: responseData.metadata || null,
      actions: responseData.actions ?? null,
      actionsVisible: !hasActions,
    };
  }, []);

  const applyHandoffFromResponse = useCallback((responseData) => {
    const hs = responseData.handoff_summary;
    if (hs) {
      setTicketPrefill({
        subject: 'Support request — Pleerity assistant',
        description: hs,
      });
    }
    if (responseData.action === 'handoff') {
      setShowHandoff(true);
      setHandoffOptions(responseData.handoff_options);
    }
  }, []);

  const deliverAssistantReply = useCallback(async (responseData, startedAt) => {
    await sleep(computeReplyPacingDelay(Date.now() - startedAt));
    const botMessage = buildBotMessageFromResponse(responseData);
    setMessages((prev) => [...prev, botMessage]);
    if (botMessage.actions?.length > 0 && !botMessage.actionsVisible) {
      scheduleActionsReveal(botMessage.id);
    }
    applyHandoffFromResponse(responseData);
  }, [applyHandoffFromResponse, buildBotMessageFromResponse, scheduleActionsReveal]);

  useEffect(() => () => clearActionRevealTimers(), [clearActionRevealTimers]);

  useEffect(() => {
    if (typeof TawkToAPI.getVisitorStatus === 'function') {
      setTawkVisitorStatus(TawkToAPI.getVisitorStatus());
    }
    if (typeof TawkToAPI.onVisitorStatusChange !== 'function') {
      return undefined;
    }
    return TawkToAPI.onVisitorStatusChange((status) => {
      setTawkVisitorStatus(status);
    });
  }, []);

  const resetConversation = useCallback(() => {
    clearActionRevealTimers();
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
    setShowTicketForm(false);
    setTicketPrefill({ subject: '', description: '' });
  }, [clearActionRevealTimers]);

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
    if (isAuthenticated && !canRequestSupport) return;
    setLoading(true);
    setShowHandoff(false);
    const startedAt = Date.now();

    try {
      const response = await client.post(`/support/quick-action/${actionId}`, null, {
        params: { conversation_id: conversationId }
      });

      setConversationId(response.data.conversation_id);
      if (response.data.conversation_context) {
        setConversationContext(response.data.conversation_context);
      }

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

      await deliverAssistantReply(response.data, startedAt);
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
    if (isAuthenticated && !canRequestSupport) return;

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
    const startedAt = Date.now();

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

      await deliverAssistantReply(response.data, startedAt);
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
    const startedAt = Date.now();
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
      await deliverAssistantReply(response.data, startedAt);
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

  const handlePopularTaskSelect = async (item) => {
    if (item.quickAction) {
      await handleQuickAction(item.quickAction);
      return;
    }
    if (item.actionId) {
      await handleQuickAction(item.actionId);
      return;
    }
    if (item.message) {
      await sendMessageAs(item.message);
    }
  };

  // Handle handoff selection
  const handleHandoffSelect = (option) => {
    if (option === 'livechat') {
      const widgetStatus = typeof window !== 'undefined' ? window.__PLEERITY_TAWK_STATUS : null;
      if (handoffOptions?.live_chat?.configured === false) {
        return;
      }
      if (handoffOptions?.live_chat?.available && widgetStatus === 'offline') {
        toast.error(
          handoffOptions.live_chat_notice
            || 'Live chat is not available right now. You can still create a ticket.'
        );
        return;
      }
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

  if (isAuthenticated && !canAccessSupport) {
    return null;
  }

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
        isMinimized ? 'w-72 h-14' : 'w-[min(24rem,calc(100vw-3rem))] h-[550px] max-h-[calc(100vh-6rem)]'
      }`}
      data-testid="support-chat-widget"
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-teal-600 to-teal-500 text-white px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SupportAssistantAvatar className="ring-2 ring-white/30" />
          <div>
            <h3 className="font-semibold text-sm">Pleerity Support</h3>
            {!isMinimized && (
              <p className="text-xs text-teal-100">Help assistant</p>
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
              Help articles
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
              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="p-4 pb-2 min-h-[12rem]">
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
            {messages.length === 1 && messages[0]?.sender === 'bot' && (
              <PopularTasksSection
                items={ONBOARDING_TASK_ITEMS}
                onSelect={handlePopularTaskSelect}
                onReset={resetConversation}
                loading={loading}
                alignWithBot
              />
            )}
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
                tawkVisitorStatus={tawkVisitorStatus}
              />
            )}
            
            {/* Ticket form */}
            {showTicketForm && (
              <EmailTicketForm
                conversationId={conversationId}
                initialSubject={ticketPrefill.subject}
                initialDescription={ticketPrefill.description}
                onSubmit={(ticketPayload) => {
                  setShowTicketForm(false);
                  const text =
                    (ticketPayload && ticketPayload.message) ||
                    "Your support ticket has been created. You'll receive a confirmation email shortly.";
                  setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    text,
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
            
            {loading && <SupportTypingIndicator />}
            
            <div ref={messagesEndRef} />
                </div>
              </div>

              {messages.length > 1 && (
                <div className="px-4 py-2 border-t border-gray-100 shrink-0 bg-white">
                  <PopularTasksSection
                    items={SHORTCUT_TASK_ITEMS}
                    onSelect={handlePopularTaskSelect}
                    onReset={resetConversation}
                    loading={loading}
                  />
                </div>
              )}

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
