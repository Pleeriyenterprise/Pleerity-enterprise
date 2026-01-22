/**
 * OrderList - List of orders for a selected pipeline stage
 * 
 * Features:
 * - Shows orders filtered by stage
 * - Sorting options
 * - Priority indicators
 * - SLA tracking
 * - Click to view details
 */

import React from 'react';
import { Card, CardContent } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../ui/select';
import { Input } from '../../ui/input';
import { Label } from '../../ui/label';
import { ScrollArea } from '../../ui/scroll-area';
import {
  Search,
  Flag,
  Clock,
  Timer,
  Zap,
  User,
  Package,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '../../../lib/utils';
import { formatPriceShort } from '../../../api/ordersApi';

// Status color mapping for badges
const STATUS_COLORS = {
  CREATED: 'bg-gray-100 text-gray-800',
  PAID: 'bg-blue-100 text-blue-800',
  QUEUED: 'bg-gray-100 text-gray-800',
  IN_PROGRESS: 'bg-yellow-100 text-yellow-800',
  DRAFT_READY: 'bg-purple-100 text-purple-800',
  INTERNAL_REVIEW: 'bg-orange-100 text-orange-800',
  REGEN_REQUESTED: 'bg-pink-100 text-pink-800',
  REGENERATING: 'bg-pink-100 text-pink-800',
  CLIENT_INPUT_REQUIRED: 'bg-pink-100 text-pink-800',
  FINALISING: 'bg-teal-100 text-teal-800',
  DELIVERING: 'bg-cyan-100 text-cyan-800',
  COMPLETED: 'bg-green-100 text-green-800',
  DELIVERY_FAILED: 'bg-red-100 text-red-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-100 text-gray-500',
};

// Sort options
const SORT_OPTIONS = [
  { value: 'entered_desc', label: 'Entered Stage (Latest First)' },
  { value: 'entered_asc', label: 'Entered Stage (Earliest First)' },
  { value: 'priority', label: 'Priority (Highest First)' },
  { value: 'sla_asc', label: 'SLA Remaining (Urgent First)' },
  { value: 'created_desc', label: 'Created (Newest First)' },
  { value: 'created_asc', label: 'Created (Oldest First)' },
];

/**
 * Calculate hours in current state
 */
const getHoursInState = (order) => {
  const updated = new Date(order.updated_at);
  const now = new Date();
  return (now - updated) / (1000 * 60 * 60);
};

/**
 * Format time in state
 */
const formatTimeInState = (order) => {
  const hours = getHoursInState(order);
  if (hours < 1) return 'Just now';
  if (hours < 24) return `${Math.floor(hours)}h`;
  return `${Math.floor(hours / 24)}d ${Math.floor(hours % 24)}h`;
};

/**
 * Format date
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
 * Single order card in the list
 */
const OrderCard = ({ order, onClick }) => {
  const hoursInState = getHoursInState(order);
  const isSLAWarning = order.sla_hours && hoursInState > order.sla_hours * 0.75;
  const isSLABreach = order.sla_hours && hoursInState > order.sla_hours;

  return (
    <Card
      data-testid={`order-card-${order.order_id}`}
      className={cn(
        'cursor-pointer hover:shadow-md transition-shadow',
        order.priority && 'ring-2 ring-orange-400',
        isSLABreach && 'border-red-300 bg-red-50/50'
      )}
      onClick={() => onClick(order)}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            {/* Order ID and Priority */}
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono font-medium text-sm">{order.order_id}</span>
              {order.priority && (
                <Badge className="bg-orange-100 text-orange-800 text-xs">
                  <Flag className="h-3 w-3 mr-1" />
                  Priority
                </Badge>
              )}
              {order.fast_track && (
                <Badge className="bg-purple-100 text-purple-800 text-xs animate-pulse">
                  <Zap className="h-3 w-3 mr-1" />
                  Fast Track
                </Badge>
              )}
              {order.requires_postal_delivery && (
                <Badge className="bg-cyan-100 text-cyan-800 text-xs">
                  <Package className="h-3 w-3 mr-1" />
                  Print Copy
                </Badge>
              )}
            </div>

            {/* Service name */}
            <p className="text-sm text-gray-600 mb-1">
              <Package className="h-3 w-3 inline mr-1" />
              {order.service_name || order.service_code}
            </p>

            {/* Customer */}
            <p className="text-sm text-gray-500">
              <User className="h-3 w-3 inline mr-1" />
              {order.customer?.full_name || order.customer?.email || 'Unknown'}
            </p>
          </div>

          <div className="text-right">
            {/* Status badge */}
            <Badge className={cn('text-xs mb-2', STATUS_COLORS[order.status])}>
              {order.status?.replace(/_/g, ' ')}
            </Badge>

            {/* Time in state */}
            <div className={cn(
              'text-xs flex items-center justify-end gap-1',
              isSLABreach ? 'text-red-600 font-semibold' : isSLAWarning ? 'text-orange-600' : 'text-gray-500'
            )}>
              {isSLABreach && <AlertTriangle className="h-3 w-3" />}
              <Timer className="h-3 w-3" />
              {formatTimeInState(order)}
            </div>

            {/* Price */}
            {order.total_amount && (
              <p className="text-sm font-medium text-gray-700 mt-1">
                {formatPriceShort(order.total_amount)}
              </p>
            )}
          </div>
        </div>

        {/* Regeneration count if applicable */}
        {order.regeneration_count > 0 && (
          <div className="mt-2 text-xs text-blue-600">
            {order.regeneration_count} revision{order.regeneration_count > 1 ? 's' : ''}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

/**
 * Main OrderList component
 */
const OrderList = ({
  orders = [],
  selectedStage,
  stageName,
  sortBy = 'priority',
  onSortChange,
  searchQuery = '',
  onSearchChange,
  onOrderClick,
  onClose,
}) => {
  // Filter and sort orders
  const filteredOrders = orders
    .filter((order) => {
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        order.order_id?.toLowerCase().includes(q) ||
        order.customer?.email?.toLowerCase().includes(q) ||
        order.customer?.full_name?.toLowerCase().includes(q) ||
        order.service_name?.toLowerCase().includes(q)
      );
    })
    .sort((a, b) => {
      // Always put priority orders first
      if (a.priority && !b.priority) return -1;
      if (!a.priority && b.priority) return 1;

      switch (sortBy) {
        case 'entered_desc':
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'entered_asc':
          return new Date(a.updated_at) - new Date(b.updated_at);
        case 'priority':
          return new Date(b.updated_at) - new Date(a.updated_at);
        case 'sla_asc':
          const slaA = a.sla_hours ? a.sla_hours - getHoursInState(a) : Infinity;
          const slaB = b.sla_hours ? b.sla_hours - getHoursInState(b) : Infinity;
          return slaA - slaB;
        case 'created_desc':
          return new Date(b.created_at) - new Date(a.created_at);
        case 'created_asc':
          return new Date(a.created_at) - new Date(b.created_at);
        default:
          return 0;
      }
    });

  return (
    <div className="space-y-4" data-testid="order-list">
      {/* Header with stage name and count */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">{stageName} Orders</h3>
          <p className="text-sm text-gray-500">
            {filteredOrders.length} order{filteredOrders.length !== 1 ? 's' : ''}
            {searchQuery && ` matching "${searchQuery}"`}
          </p>
        </div>
      </div>

      {/* Sort and Search controls */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Label className="text-sm text-gray-500 whitespace-nowrap">Sort by:</Label>
          <Select value={sortBy} onValueChange={onSortChange}>
            <SelectTrigger className="w-[200px]" data-testid="sort-select">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        
        <div className="flex-1 max-w-sm">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search orders..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              className="pl-9"
              data-testid="order-search"
            />
          </div>
        </div>
      </div>

      {/* Order cards */}
      <ScrollArea className="h-[500px]">
        <div className="space-y-3 pr-4">
          {filteredOrders.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Package className="h-12 w-12 mx-auto mb-2 opacity-40" />
              <p>No orders in this stage</p>
            </div>
          ) : (
            filteredOrders.map((order) => (
              <OrderCard
                key={order.order_id}
                order={order}
                onClick={onOrderClick}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

export { OrderList, OrderCard, STATUS_COLORS, SORT_OPTIONS, formatTimeInState, formatDate };
export default OrderList;
