/**
 * AuditTimeline - Display audit trail for an order
 * 
 * Features:
 * - Chronological timeline of all order events
 * - Clickable document-related events (link to version)
 * - Shows who, what, when for each event
 * - Visual indicators for different event types
 */

import React from 'react';
import { Badge } from '../../ui/badge';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';
import {
  Clock,
  User,
  FileText,
  Check,
  X,
  RotateCcw,
  MessageSquare,
  AlertTriangle,
  Send,
  Lock,
  Play,
  ExternalLink,
} from 'lucide-react';
import { cn } from '../../../lib/utils';

/**
 * Format date for display
 */
const formatDate = (dateString) => {
  if (!dateString) return '-';
  return new Date(dateString).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * Get icon for event type
 */
const getEventIcon = (event) => {
  const action = (event.new_state || event.action || event.transition_type || '').toLowerCase();
  
  if (action.includes('approve') || action.includes('final')) return Lock;
  if (action.includes('reject') || action.includes('cancel')) return X;
  if (action.includes('regen')) return RotateCcw;
  if (action.includes('client_input') || action.includes('info')) return MessageSquare;
  if (action.includes('generated') || action.includes('document')) return FileText;
  if (action.includes('deliver') || action.includes('send')) return Send;
  if (action.includes('fail') || action.includes('error')) return AlertTriangle;
  if (action.includes('start') || action.includes('progress')) return Play;
  if (action.includes('complete') || action.includes('success')) return Check;
  
  return Clock;
};

/**
 * Get color for event type
 */
const getEventColor = (event) => {
  const action = (event.new_state || event.action || event.transition_type || '').toLowerCase();
  
  if (action.includes('approve') || action.includes('complete') || action.includes('success')) {
    return 'text-green-600 bg-green-100 border-green-200';
  }
  if (action.includes('reject') || action.includes('cancel') || action.includes('fail')) {
    return 'text-red-600 bg-red-100 border-red-200';
  }
  if (action.includes('regen')) {
    return 'text-blue-600 bg-blue-100 border-blue-200';
  }
  if (action.includes('client_input') || action.includes('info')) {
    return 'text-pink-600 bg-pink-100 border-pink-200';
  }
  if (action.includes('deliver') || action.includes('send')) {
    return 'text-cyan-600 bg-cyan-100 border-cyan-200';
  }
  if (action.includes('generated') || action.includes('document')) {
    return 'text-purple-600 bg-purple-100 border-purple-200';
  }
  
  return 'text-gray-600 bg-gray-100 border-gray-200';
};

/**
 * Check if event is document-related and clickable
 */
const isClickableEvent = (event) => {
  const action = (event.new_state || event.action || event.transition_type || '').toLowerCase();
  return (
    action.includes('generated') ||
    action.includes('approved') ||
    action.includes('regenerat') ||
    action.includes('document')
  );
};

/**
 * Extract version number from event
 */
const getVersionFromEvent = (event) => {
  const reason = event.reason || '';
  const match = reason.match(/v(\d+)/i) || reason.match(/version\s*(\d+)/i);
  return match ? parseInt(match[1]) : null;
};

/**
 * Render icon based on event type
 */
const renderEventIcon = (event) => {
  const Icon = getEventIcon(event);
  return <Icon className="h-4 w-4" />;
};

/**
 * Single timeline event component
 */
const TimelineEvent = ({ event, index, isLast, onDocumentClick }) => {
  const colorClass = getEventColor(event);
  const clickable = isClickableEvent(event);
  const version = clickable ? getVersionFromEvent(event) : null;

  const handleClick = () => {
    if (clickable && version && onDocumentClick) {
      onDocumentClick(version);
    }
  };

  return (
    <div
      className={cn(
        'flex gap-3 text-sm rounded-lg p-2 -mx-2 transition-colors',
        clickable && 'cursor-pointer hover:bg-blue-50'
      )}
      onClick={handleClick}
      data-testid={`timeline-event-${index}`}
    >
      {/* Timeline indicator */}
      <div className="flex flex-col items-center">
        <div
          className={cn(
            'w-8 h-8 rounded-full flex items-center justify-center border',
            colorClass
          )}
        >
          {renderEventIcon(event)}
        </div>
        {!isLast && <div className="w-0.5 flex-1 bg-gray-200 mt-1" />}
      </div>

      {/* Event content */}
      <div className="flex-1 pb-4">
        <div className="flex items-center gap-2 flex-wrap">
          {/* State/Action badge */}
          <Badge
            variant="outline"
            className={cn('text-xs', clickable && 'border-blue-300 text-blue-700')}
          >
            {event.new_state || event.action || event.transition_type || 'Event'}
          </Badge>

          {/* Version link indicator */}
          {clickable && version && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger>
                  <Badge
                    variant="secondary"
                    className="text-xs bg-blue-100 text-blue-700 cursor-pointer"
                  >
                    <ExternalLink className="h-3 w-3 mr-1" />
                    v{version}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent>Click to view document v{version}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}

          {/* Timestamp */}
          <span className="text-xs text-gray-500 flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(event.timestamp || event.created_at)}
          </span>
        </div>

        {/* Reason/details */}
        {event.reason && (
          <p className="text-xs text-gray-600 mt-1">{event.reason}</p>
        )}

        {/* Notes if present */}
        {event.notes && (
          <p className="text-xs text-gray-500 mt-1 italic">Note: {event.notes}</p>
        )}

        {/* Triggered by */}
        {(event.triggered_by_email || event.triggered_by) && (
          <p className="text-xs text-gray-400 mt-1 flex items-center gap-1">
            <User className="h-3 w-3" />
            {event.triggered_by_email || event.triggered_by}
          </p>
        )}

        {/* Click hint for document events */}
        {clickable && (
          <p className="text-xs text-blue-500 mt-1">Click to view document</p>
        )}
      </div>
    </div>
  );
};

/**
 * Main AuditTimeline component
 */
const AuditTimeline = ({
  timeline = [],
  onDocumentClick,
  maxHeight = '400px',
}) => {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Clock className="h-8 w-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No timeline events yet</p>
      </div>
    );
  }

  return (
    <div data-testid="audit-timeline">
      <h4 className="font-medium mb-3 flex items-center gap-2">
        <Clock className="h-4 w-4" />
        Audit Timeline
        <Badge variant="secondary" className="ml-2">
          {timeline.length} events
        </Badge>
      </h4>
      
      <ScrollArea style={{ maxHeight }}>
        <div className="space-y-0 pr-4">
          {timeline.map((event, index) => (
            <TimelineEvent
              key={event.execution_id || index}
              event={event}
              index={index}
              isLast={index === timeline.length - 1}
              onDocumentClick={onDocumentClick}
            />
          ))}
        </div>
      </ScrollArea>
    </div>
  );
};

export { AuditTimeline, TimelineEvent, formatDate, getEventIcon };
export default AuditTimeline;
