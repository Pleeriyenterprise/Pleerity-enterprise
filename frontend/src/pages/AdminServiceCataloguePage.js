import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../components/admin/AdminLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
  Package,
  Plus,
  Edit,
  RefreshCw,
  Search,
  Check,
  X,
  Eye,
  FileText,
  Settings,
  DollarSign,
  Clock,
  Zap,
  Archive,
  ToggleLeft,
  ToggleRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Category colors and labels
const categoryConfig = {
  CVP_FEATURE: { label: 'CVP Feature', color: 'bg-blue-100 text-blue-800' },
  CVP_ADDON: { label: 'CVP Add-on', color: 'bg-purple-100 text-purple-800' },
  STANDALONE_REPORT: { label: 'Standalone Report', color: 'bg-green-100 text-green-800' },
  DOCUMENT_PACK: { label: 'Document Pack', color: 'bg-orange-100 text-orange-800' },
};

// Pricing model labels
const pricingModelLabels = {
  one_time: 'One-Time',
  subscription: 'Subscription',
  addon: 'Add-on',
  included: 'Included',
};

// Delivery type labels
const deliveryTypeLabels = {
  portal: 'Portal Only',
  email: 'Email Only',
  'portal+email': 'Portal + Email',
};

const AdminServiceCataloguePage = () => {
  const [services, setServices] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [showInactive, setShowInactive] = useState(false);
  
  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingService, setEditingService] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // View modal state
  const [showViewModal, setShowViewModal] = useState(false);
  const [viewingService, setViewingService] = useState(null);
  
  // Categories for dropdown
  const [categories, setCategories] = useState([]);
  const [pricingModels, setPricingModels] = useState([]);
  const [deliveryTypes, setDeliveryTypes] = useState([]);
  const [generationModes, setGenerationModes] = useState([]);

  // Fetch services
  const fetchServices = useCallback(async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `${API_URL}/api/admin/services/?include_inactive=${showInactive}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (response.ok) {
        const data = await response.json();
        setServices(data.services || []);
      }
    } catch (error) {
      console.error('Failed to fetch services:', error);
      toast.error('Failed to load services');
    } finally {
      setIsLoading(false);
    }
  }, [showInactive]);

  // Fetch categories
  const fetchCategories = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/admin/services/categories`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
        setPricingModels(data.pricing_models || []);
        setDeliveryTypes(data.delivery_types || []);
        setGenerationModes(data.generation_modes || []);
      }
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    }
  };

  useEffect(() => {
    fetchServices();
    fetchCategories();
  }, [fetchServices]);

  // Filter services
  const filteredServices = services.filter(service => {
    const matchesSearch = 
      service.service_code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      service.service_name.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesCategory = categoryFilter === 'all' || service.category === categoryFilter;
    
    return matchesSearch && matchesCategory;
  });

  // Toggle service active status
  const toggleServiceActive = async (serviceCode, currentActive) => {
    try {
      const token = localStorage.getItem('auth_token');
      const endpoint = currentActive ? 'deactivate' : 'activate';
      
      const response = await fetch(
        `${API_URL}/api/admin/services/${serviceCode}/${endpoint}`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      if (response.ok) {
        toast.success(`Service ${currentActive ? 'deactivated' : 'activated'}`);
        fetchServices();
      } else {
        toast.error('Failed to update service status');
      }
    } catch (error) {
      toast.error('Failed to update service status');
    }
  };

  // Open edit modal
  const openEditModal = (service = null) => {
    setEditingService(service || {
      service_code: '',
      service_name: '',
      description: '',
      short_description: '',
      category: 'STANDALONE_REPORT',
      pricing_model: 'one_time',
      price_amount: 0,
      price_currency: 'gbp',
      vat_rate: 0.20,
      delivery_type: 'portal+email',
      estimated_turnaround_hours: 24,
      review_required: true,
      generation_mode: 'TEMPLATE_ONLY',
      requires_cvp_subscription: false,
      active: true,
      display_order: 0,
    });
    setShowEditModal(true);
  };

  // Open view modal
  const openViewModal = (service) => {
    setViewingService(service);
    setShowViewModal(true);
  };

  // Save service
  const saveService = async () => {
    if (!editingService.service_code || !editingService.service_name) {
      toast.error('Service code and name are required');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const isNew = !services.find(s => s.service_code === editingService.service_code);
      
      const url = isNew 
        ? `${API_URL}/api/admin/services/`
        : `${API_URL}/api/admin/services/${editingService.service_code}`;
      
      const response = await fetch(url, {
        method: isNew ? 'POST' : 'PUT',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(editingService),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success(isNew ? 'Service created' : 'Service updated');
        setShowEditModal(false);
        fetchServices();
      } else {
        toast.error(data.detail || 'Failed to save service');
      }
    } catch (error) {
      toast.error('Failed to save service');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Format price
  const formatPrice = (amount, currency = 'gbp') => {
    if (amount === 0) return 'Included';
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: currency.toUpperCase(),
    }).format(amount / 100);
  };

  return (
    <AdminLayout>
      <div className="space-y-6" data-testid="service-catalogue-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Service Catalogue</h1>
            <p className="text-gray-500 text-sm">
              Manage all services, pricing, and delivery configurations
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline" onClick={() => fetchServices()}>
              <RefreshCw className={cn('h-4 w-4 mr-2', isLoading && 'animate-spin')} />
              Refresh
            </Button>
            <Button onClick={() => openEditModal()}>
              <Plus className="h-4 w-4 mr-2" />
              Add Service
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex-1 min-w-[200px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Search services..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9"
                  />
                </div>
              </div>
              
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {categories.map(cat => (
                    <SelectItem key={cat.value} value={cat.value}>
                      {cat.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <div className="flex items-center gap-2">
                <Switch
                  id="show-inactive"
                  checked={showInactive}
                  onCheckedChange={setShowInactive}
                />
                <Label htmlFor="show-inactive" className="text-sm">
                  Show Inactive
                </Label>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Services Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              Services ({filteredServices.length})
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Code</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Price</TableHead>
                  <TableHead>Delivery</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredServices.map(service => (
                  <TableRow key={service.service_code} className={!service.active ? 'opacity-50' : ''}>
                    <TableCell className="font-mono text-sm">
                      {service.service_code}
                    </TableCell>
                    <TableCell>
                      <div>
                        <p className="font-medium">{service.service_name}</p>
                        <p className="text-xs text-gray-500 line-clamp-1">
                          {service.short_description || service.description}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={categoryConfig[service.category]?.color || 'bg-gray-100'}>
                        {categoryConfig[service.category]?.label || service.category}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">
                        {formatPrice(service.price_amount, service.price_currency)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm">
                        {deliveryTypeLabels[service.delivery_type] || service.delivery_type}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant={service.active ? 'default' : 'secondary'}
                        className={service.active ? 'bg-green-100 text-green-800' : ''}
                      >
                        {service.active ? 'Active' : 'Inactive'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openViewModal(service)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditModal(service)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleServiceActive(service.service_code, service.active)}
                        >
                          {service.active ? (
                            <ToggleRight className="h-4 w-4 text-green-600" />
                          ) : (
                            <ToggleLeft className="h-4 w-4 text-gray-400" />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                
                {filteredServices.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                      No services found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Edit Modal */}
        <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
          <DialogContent className="max-w-2xl max-h-[90vh]">
            <DialogHeader>
              <DialogTitle>
                {editingService?.service_code && services.find(s => s.service_code === editingService.service_code)
                  ? 'Edit Service'
                  : 'Add New Service'}
              </DialogTitle>
              <DialogDescription>
                Configure service details, pricing, and delivery options.
              </DialogDescription>
            </DialogHeader>
            
            {editingService && (
              <ScrollArea className="max-h-[60vh]">
                <Tabs defaultValue="basic" className="w-full">
                  <TabsList className="grid w-full grid-cols-3">
                    <TabsTrigger value="basic">Basic Info</TabsTrigger>
                    <TabsTrigger value="pricing">Pricing</TabsTrigger>
                    <TabsTrigger value="delivery">Delivery</TabsTrigger>
                  </TabsList>
                  
                  <TabsContent value="basic" className="space-y-4 pt-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Service Code *</Label>
                        <Input
                          value={editingService.service_code}
                          onChange={(e) => setEditingService({
                            ...editingService,
                            service_code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, '_'),
                          })}
                          placeholder="DOC_PACK_EXAMPLE"
                          disabled={services.find(s => s.service_code === editingService.service_code)}
                        />
                        <p className="text-xs text-gray-500">Immutable after creation</p>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Category *</Label>
                        <Select
                          value={editingService.category}
                          onValueChange={(v) => setEditingService({...editingService, category: v})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {categories.map(cat => (
                              <SelectItem key={cat.value} value={cat.value}>
                                {cat.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Service Name *</Label>
                      <Input
                        value={editingService.service_name}
                        onChange={(e) => setEditingService({...editingService, service_name: e.target.value})}
                        placeholder="My Service Name"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Short Description</Label>
                      <Input
                        value={editingService.short_description || ''}
                        onChange={(e) => setEditingService({...editingService, short_description: e.target.value})}
                        placeholder="Brief description for listings"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Full Description</Label>
                      <Textarea
                        value={editingService.description}
                        onChange={(e) => setEditingService({...editingService, description: e.target.value})}
                        placeholder="Detailed service description"
                        rows={3}
                      />
                    </div>
                    
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={editingService.requires_cvp_subscription}
                          onCheckedChange={(v) => setEditingService({...editingService, requires_cvp_subscription: v})}
                        />
                        <Label>Requires CVP Subscription</Label>
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={editingService.active}
                          onCheckedChange={(v) => setEditingService({...editingService, active: v})}
                        />
                        <Label>Active</Label>
                      </div>
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="pricing" className="space-y-4 pt-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Pricing Model</Label>
                        <Select
                          value={editingService.pricing_model}
                          onValueChange={(v) => setEditingService({...editingService, pricing_model: v})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {pricingModels.map(pm => (
                              <SelectItem key={pm.value} value={pm.value}>
                                {pm.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Price (in pence)</Label>
                        <Input
                          type="number"
                          value={editingService.price_amount}
                          onChange={(e) => setEditingService({...editingService, price_amount: parseInt(e.target.value) || 0})}
                          placeholder="4999"
                        />
                        <p className="text-xs text-gray-500">
                          {formatPrice(editingService.price_amount, editingService.price_currency)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Currency</Label>
                        <Select
                          value={editingService.price_currency}
                          onValueChange={(v) => setEditingService({...editingService, price_currency: v})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="gbp">GBP (£)</SelectItem>
                            <SelectItem value="usd">USD ($)</SelectItem>
                            <SelectItem value="eur">EUR (€)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>VAT Rate</Label>
                        <Input
                          type="number"
                          step="0.01"
                          value={editingService.vat_rate}
                          onChange={(e) => setEditingService({...editingService, vat_rate: parseFloat(e.target.value) || 0})}
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>Stripe Price ID</Label>
                      <Input
                        value={editingService.stripe_price_id || ''}
                        onChange={(e) => setEditingService({...editingService, stripe_price_id: e.target.value})}
                        placeholder="price_1234..."
                      />
                    </div>
                  </TabsContent>
                  
                  <TabsContent value="delivery" className="space-y-4 pt-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Delivery Type</Label>
                        <Select
                          value={editingService.delivery_type}
                          onValueChange={(v) => setEditingService({...editingService, delivery_type: v})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {deliveryTypes.map(dt => (
                              <SelectItem key={dt.value} value={dt.value}>
                                {dt.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Turnaround (hours)</Label>
                        <Input
                          type="number"
                          value={editingService.estimated_turnaround_hours}
                          onChange={(e) => setEditingService({...editingService, estimated_turnaround_hours: parseInt(e.target.value) || 24})}
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Generation Mode</Label>
                        <Select
                          value={editingService.generation_mode}
                          onValueChange={(v) => setEditingService({...editingService, generation_mode: v})}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {generationModes.map(gm => (
                              <SelectItem key={gm.value} value={gm.value}>
                                {gm.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      
                      <div className="space-y-2">
                        <Label>Display Order</Label>
                        <Input
                          type="number"
                          value={editingService.display_order}
                          onChange={(e) => setEditingService({...editingService, display_order: parseInt(e.target.value) || 0})}
                        />
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={editingService.review_required}
                        onCheckedChange={(v) => setEditingService({...editingService, review_required: v})}
                      />
                      <Label>Review Required Before Delivery</Label>
                    </div>
                  </TabsContent>
                </Tabs>
              </ScrollArea>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowEditModal(false)}>
                Cancel
              </Button>
              <Button onClick={saveService} disabled={isSubmitting}>
                {isSubmitting ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : null}
                Save Service
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* View Modal */}
        <Dialog open={showViewModal} onOpenChange={setShowViewModal}>
          <DialogContent className="max-w-2xl">
            <DialogHeader>
              <DialogTitle>Service Details</DialogTitle>
            </DialogHeader>
            
            {viewingService && (
              <div className="space-y-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold">{viewingService.service_name}</h3>
                    <p className="text-sm text-gray-500 font-mono">{viewingService.service_code}</p>
                  </div>
                  <Badge className={categoryConfig[viewingService.category]?.color}>
                    {categoryConfig[viewingService.category]?.label}
                  </Badge>
                </div>
                
                <p className="text-gray-700">{viewingService.description}</p>
                
                <Separator />
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <DollarSign className="h-4 w-4 text-gray-400" />
                      <span className="text-gray-500">Price:</span>
                      <span className="font-medium">
                        {formatPrice(viewingService.price_amount, viewingService.price_currency)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Settings className="h-4 w-4 text-gray-400" />
                      <span className="text-gray-500">Model:</span>
                      <span>{pricingModelLabels[viewingService.pricing_model]}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-gray-400" />
                      <span className="text-gray-500">Delivery:</span>
                      <span>{deliveryTypeLabels[viewingService.delivery_type]}</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-gray-400" />
                      <span className="text-gray-500">Turnaround:</span>
                      <span>{viewingService.estimated_turnaround_hours}h</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-gray-400" />
                      <span className="text-gray-500">Generation:</span>
                      <span>{viewingService.generation_mode?.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {viewingService.review_required ? (
                        <Check className="h-4 w-4 text-green-500" />
                      ) : (
                        <X className="h-4 w-4 text-gray-400" />
                      )}
                      <span className="text-gray-500">Review Required:</span>
                      <span>{viewingService.review_required ? 'Yes' : 'No'}</span>
                    </div>
                  </div>
                </div>
                
                {viewingService.documents_generated?.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <h4 className="font-medium mb-2">Documents Generated</h4>
                      <div className="space-y-1">
                        {viewingService.documents_generated.map((doc, idx) => (
                          <div key={idx} className="flex items-center gap-2 text-sm">
                            <FileText className="h-4 w-4 text-gray-400" />
                            <span>{doc.document_name}</span>
                            <Badge variant="outline" className="text-xs">{doc.format}</Badge>
                            {doc.is_primary && <Badge className="text-xs">Primary</Badge>}
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowViewModal(false)}>
                Close
              </Button>
              <Button onClick={() => {
                setShowViewModal(false);
                openEditModal(viewingService);
              }}>
                <Edit className="h-4 w-4 mr-2" />
                Edit
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </AdminLayout>
  );
};

export default AdminServiceCataloguePage;
