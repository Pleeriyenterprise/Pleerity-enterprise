/**
 * OrderPipelineView - Pipeline/Kanban view with clickable stage columns
 * 
 * Features:
 * - Clickable tabs/columns with live counts (badge)
 * - Visual highlighting for stages with orders (active indicator + count badge)
 * - Real-time updates via polling (WebSocket fallback planned)
 * - No drag-and-drop - state transitions via guarded actions only
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '../../ui/tooltip';
import {
  Package,
  RefreshCw,
  Play,
  Pause,
  Clock,
} from 'lucide-react';
import { cn } from '../../../lib/utils';

// Pipeline columns configuration with visual styling
const PIPELINE_COLUMNS = [
  { status: 'PAID', label: 'Paid', color: 'blue', bgActive: 'bg-blue-50', borderActive: 'border-blue-500', textActive: 'text-blue-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'QUEUED', label: 'Queued', color: 'slate', bgActive: 'bg-slate-100', borderActive: 'border-slate-500', textActive: 'text-slate-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'IN_PROGRESS', label: 'In Progress', color: 'yellow', bgActive: 'bg-yellow-50', borderActive: 'border-yellow-500', textActive: 'text-yellow-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'DRAFT_READY', label: 'Draft Ready', color: 'purple', bgActive: 'bg-purple-50', borderActive: 'border-purple-500', textActive: 'text-purple-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'INTERNAL_REVIEW', label: 'Review', color: 'orange', bgActive: 'bg-orange-50', borderActive: 'border-orange-500', textActive: 'text-orange-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'CLIENT_INPUT_REQUIRED', label: 'Awaiting Client', color: 'pink', bgActive: 'bg-pink-50', borderActive: 'border-pink-500', textActive: 'text-pink-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'FINALISING', label: 'Finalising', color: 'teal', bgActive: 'bg-teal-50', borderActive: 'border-teal-500', textActive: 'text-teal-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'DELIVERING', label: 'Delivering', color: 'cyan', bgActive: 'bg-cyan-50', borderActive: 'border-cyan-500', textActive: 'text-cyan-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'COMPLETED', label: 'Completed', color: 'green', bgActive: 'bg-green-50', borderActive: 'border-green-500', textActive: 'text-green-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
  { status: 'FAILED', label: 'Failed', color: 'red', bgActive: 'bg-red-100', borderActive: 'border-red-600', textActive: 'text-red-700', bgMuted: 'bg-gray-50', borderMuted: 'border-gray-200', textMuted: 'text-gray-400' },
];

/**
 * Single pipeline column component
 */
const PipelineColumn = ({ column, count, isSelected, onClick }) => {
  const hasOrders = count > 0;
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            data-testid={`pipeline-column-${column.status.toLowerCase().replace(/_/g, '-')}`}
            onClick={() => hasOrders && onClick(column.status)}
            className={cn(
              'flex flex-col items-center justify-center p-3 rounded-lg border-2 transition-all min-w-[100px] relative',
              hasOrders ? column.bgActive : column.bgMuted,
              hasOrders ? column.borderActive : column.borderMuted,
              isSelected && 'ring-2 ring-offset-2 ring-blue-500',
              hasOrders && 'cursor-pointer hover:scale-105 hover:shadow-md',
              !hasOrders && 'opacity-60'
            )}
          >
            {/* Active indicator dot */}
            {hasOrders && (
              <div className={cn(
                'absolute -top-1 -right-1 w-3 h-3 rounded-full animate-pulse',
                `bg-${column.color}-500`
              )} style={{ backgroundColor: hasOrders ? `var(--${column.color}-500, #3b82f6)` : undefined }} />
            )}
            
            {/* Count badge */}
            <span className={cn(
              'text-2xl font-bold',
              hasOrders ? column.textActive : column.textMuted
            )}>
              {count}
            </span>
            
            {/* Label */}
            <span className={cn(
              'text-xs font-medium text-center',
              hasOrders ? column.textActive : column.textMuted
            )}>
              {column.label}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>{count} order{count !== 1 ? 's' : ''} in {column.label}</p>
          {hasOrders && <p className="text-xs text-gray-400">Click to view</p>}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

/**
 * Main OrderPipelineView component
 */
const OrderPipelineView = ({
  counts = {},
  selectedStage = null,
  onStageClick,
  lastUpdated = null,
  autoRefresh = true,
  onAutoRefreshToggle,
  onRefresh,
  isLoading = false,
}) => {
  const formatLastUpdated = (date) => {
    if (!date) return '-';
    return new Date(date).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  // Calculate total orders in pipeline
  const totalOrders = Object.values(counts).reduce((sum, count) => sum + count, 0);

  return (
    <Card data-testid="pipeline-view">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg flex items-center gap-2">
            <Package className="h-5 w-5" />
            Pipeline Overview
            <Badge variant="secondary" className="ml-2">
              {totalOrders} total
            </Badge>
          </CardTitle>
          
          <div className="flex items-center gap-3">
            {/* Last updated indicator */}
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Clock className="h-4 w-4" />
              <span>Updated: {formatLastUpdated(lastUpdated)}</span>
            </div>
            
            {/* Auto-refresh toggle */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onAutoRefreshToggle}
                    className={autoRefresh ? 'text-green-600' : 'text-gray-500'}
                    data-testid="auto-refresh-toggle"
                  >
                    {autoRefresh ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {autoRefresh ? 'Auto-refresh ON (15s)' : 'Auto-refresh OFF'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            
            {/* Manual refresh */}
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRefresh}
                    disabled={isLoading}
                    data-testid="refresh-btn"
                  >
                    <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Refresh now
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </CardHeader>
      
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {PIPELINE_COLUMNS.map((column) => (
            <PipelineColumn
              key={column.status}
              column={column}
              count={counts[column.status] || 0}
              isSelected={selectedStage === column.status}
              onClick={onStageClick}
            />
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export { OrderPipelineView, PIPELINE_COLUMNS };
export default OrderPipelineView;
