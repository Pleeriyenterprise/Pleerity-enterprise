/**
 * Admin Intake Schema Management Page
 * Allows admins to customize intake wizard form fields without code changes.
 * Edit labels, helper text, validation rules, field order, and visibility.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  ArrowLeft, Save, RotateCcw, Eye, EyeOff, GripVertical,
  Settings2, CheckCircle, AlertCircle, Info, ChevronDown, ChevronRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Separator } from '../components/ui/separator';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '../components/ui/accordion';
import { toast } from 'sonner';
import client from '../api/client';

// Field type display config
const FIELD_TYPE_LABELS = {
  text: 'Text Input',
  textarea: 'Text Area',
  email: 'Email',
  phone: 'Phone',
  number: 'Number',
  select: 'Dropdown',
  multi_select: 'Multi-Select',
  multi_text: 'Multi-Text',
  checkbox: 'Checkbox',
  checkbox_group: 'Checkbox Group',
  date: 'Date',
  currency: 'Currency',
  address: 'Address',
  file_upload: 'File Upload',
  hidden: 'Hidden',
};

// Field group labels
const GROUP_LABELS = {
  client_identity: 'Client Identity',
  property_address: 'Property Address',
  landlord_details: 'Landlord Details',
  tenant_details: 'Tenant Details',
  tenancy_details: 'Tenancy Details',
  delivery: 'Delivery',
  consent: 'Consent',
  postal_address: 'Postal Address',
};

function FieldEditor({ field, override, onChange, onToggleHide }) {
  const [expanded, setExpanded] = useState(false);
  const isHidden = override?.hidden || false;
  
  const baseField = field.base;
  const currentOverride = override || {};
  
  const handleChange = (key, value) => {
    onChange({
      ...currentOverride,
      field_key: baseField.field_key,
      [key]: value,
    });
  };
  
  return (
    <div 
      className={`border rounded-lg p-4 ${isHidden ? 'bg-gray-50 opacity-60' : 'bg-white'}`}
      data-testid={`field-editor-${baseField.field_key}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <GripVertical className="h-5 w-5 text-gray-400 cursor-move" />
          <div>
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-900">
                {currentOverride.label || baseField.label}
              </span>
              {baseField.required && (
                <Badge variant="outline" className="text-xs">Required</Badge>
              )}
              {field.has_override && (
                <Badge className="bg-blue-100 text-blue-700 text-xs">Customized</Badge>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="secondary" className="text-xs">
                {FIELD_TYPE_LABELS[baseField.type] || baseField.type}
              </Badge>
              <span className="text-xs text-gray-500 font-mono">{baseField.field_key}</span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onToggleHide(baseField.field_key, !isHidden)}
            className={isHidden ? 'text-red-600' : 'text-gray-500'}
          >
            {isHidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </Button>
        </div>
      </div>
      
      {expanded && !isHidden && (
        <div className="mt-4 space-y-4 pl-8">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-sm text-gray-600">Custom Label</Label>
              <Input
                value={currentOverride.label || ''}
                placeholder={baseField.label}
                onChange={(e) => handleChange('label', e.target.value || null)}
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-sm text-gray-600">Placeholder</Label>
              <Input
                value={currentOverride.placeholder || ''}
                placeholder={baseField.placeholder || 'No placeholder'}
                onChange={(e) => handleChange('placeholder', e.target.value || null)}
                className="mt-1"
              />
            </div>
          </div>
          
          <div>
            <Label className="text-sm text-gray-600">Helper Text</Label>
            <Textarea
              value={currentOverride.helper_text || ''}
              placeholder={baseField.helper_text || 'No helper text'}
              onChange={(e) => handleChange('helper_text', e.target.value || null)}
              className="mt-1"
              rows={2}
            />
          </div>
          
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch
                checked={currentOverride.required ?? baseField.required}
                onCheckedChange={(checked) => handleChange('required', checked)}
              />
              <Label className="text-sm">Required</Label>
            </div>
            
            <div className="flex items-center gap-2">
              <Label className="text-sm text-gray-600">Order:</Label>
              <Input
                type="number"
                value={currentOverride.order ?? baseField.order}
                onChange={(e) => handleChange('order', parseInt(e.target.value) || null)}
                className="w-20"
              />
            </div>
          </div>
          
          {/* Options for select/multi-select fields */}
          {['select', 'multi_select', 'checkbox_group'].includes(baseField.type) && (
            <div>
              <Label className="text-sm text-gray-600">Options (one per line)</Label>
              <Textarea
                value={(currentOverride.options || baseField.options || []).join('\n')}
                onChange={(e) => {
                  const options = e.target.value.split('\n').filter(o => o.trim());
                  handleChange('options', options.length > 0 ? options : null);
                }}
                className="mt-1"
                rows={4}
                placeholder="Option 1&#10;Option 2&#10;Option 3"
              />
            </div>
          )}
          
          {/* Validation for text/number fields */}
          {['text', 'textarea', 'number'].includes(baseField.type) && (
            <div className="grid grid-cols-2 gap-4">
              {baseField.type === 'number' && (
                <>
                  <div>
                    <Label className="text-sm text-gray-600">Min Value</Label>
                    <Input
                      type="number"
                      value={currentOverride.validation?.min ?? baseField.validation?.min ?? ''}
                      onChange={(e) => handleChange('validation', {
                        ...currentOverride.validation,
                        min: e.target.value ? parseInt(e.target.value) : null
                      })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-sm text-gray-600">Max Value</Label>
                    <Input
                      type="number"
                      value={currentOverride.validation?.max ?? baseField.validation?.max ?? ''}
                      onChange={(e) => handleChange('validation', {
                        ...currentOverride.validation,
                        max: e.target.value ? parseInt(e.target.value) : null
                      })}
                      className="mt-1"
                    />
                  </div>
                </>
              )}
              {['text', 'textarea'].includes(baseField.type) && (
                <>
                  <div>
                    <Label className="text-sm text-gray-600">Min Length</Label>
                    <Input
                      type="number"
                      value={currentOverride.validation?.min_length ?? baseField.validation?.min_length ?? ''}
                      onChange={(e) => handleChange('validation', {
                        ...currentOverride.validation,
                        min_length: e.target.value ? parseInt(e.target.value) : null
                      })}
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-sm text-gray-600">Max Length</Label>
                    <Input
                      type="number"
                      value={currentOverride.validation?.max_length ?? baseField.validation?.max_length ?? ''}
                      onChange={(e) => handleChange('validation', {
                        ...currentOverride.validation,
                        max_length: e.target.value ? parseInt(e.target.value) : null
                      })}
                      className="mt-1"
                    />
                  </div>
                </>
              )}
            </div>
          )}
          
          <div className="text-xs text-gray-500 flex items-center gap-1">
            <Info className="h-3 w-3" />
            Leave fields blank to use default values
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminIntakeSchemaPage() {
  const { serviceCode } = useParams();
  const navigate = useNavigate();
  
  const [services, setServices] = useState([]);
  const [selectedService, setSelectedService] = useState(serviceCode || null);
  const [schema, setSchema] = useState(null);
  const [overrides, setOverrides] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  
  // Fetch services list
  const fetchServices = useCallback(async () => {
    try {
      const response = await client.get('/admin/intake-schema/services');
      setServices(response.data.services || []);
    } catch (error) {
      console.error('Failed to fetch services:', error);
      toast.error('Failed to load services');
    }
  }, []);
  
  // Fetch schema for selected service
  const fetchSchema = useCallback(async (code) => {
    if (!code) return;
    
    try {
      setLoading(true);
      const response = await client.get(`/admin/intake-schema/${code}`);
      setSchema(response.data);
      
      // Build overrides map from existing customizations
      const existingOverrides = {};
      response.data.fields.forEach(field => {
        if (field.override) {
          existingOverrides[field.base.field_key] = field.override;
        }
      });
      setOverrides(existingOverrides);
      setHasChanges(false);
    } catch (error) {
      console.error('Failed to fetch schema:', error);
      toast.error('Failed to load schema');
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    fetchServices();
  }, [fetchServices]);
  
  useEffect(() => {
    if (selectedService) {
      fetchSchema(selectedService);
      if (selectedService !== serviceCode) {
        navigate(`/admin/intake-schema/${selectedService}`, { replace: true });
      }
    }
  }, [selectedService, fetchSchema, navigate, serviceCode]);
  
  const handleOverrideChange = (fieldKey, override) => {
    setOverrides(prev => ({
      ...prev,
      [fieldKey]: override,
    }));
    setHasChanges(true);
  };
  
  const handleToggleHide = (fieldKey, hidden) => {
    setOverrides(prev => ({
      ...prev,
      [fieldKey]: {
        ...prev[fieldKey],
        field_key: fieldKey,
        hidden,
      },
    }));
    setHasChanges(true);
  };
  
  const handleSave = async () => {
    try {
      setSaving(true);
      
      // Convert overrides to array
      const fieldOverrides = Object.values(overrides).filter(o => 
        o.label || o.helper_text || o.placeholder || 
        o.required !== undefined || o.order !== undefined ||
        o.hidden || o.validation || o.options
      );
      
      await client.put(`/admin/intake-schema/${selectedService}`, {
        service_code: selectedService,
        field_overrides: fieldOverrides,
      });
      
      toast.success('Schema customizations saved');
      setHasChanges(false);
      fetchServices(); // Refresh list to show updated status
    } catch (error) {
      console.error('Failed to save:', error);
      toast.error('Failed to save changes');
    } finally {
      setSaving(false);
    }
  };
  
  const handleReset = async () => {
    if (!confirm('Reset all customizations for this service? This cannot be undone.')) {
      return;
    }
    
    try {
      setSaving(true);
      await client.post(`/admin/intake-schema/${selectedService}/reset`);
      toast.success('Schema reset to defaults');
      fetchSchema(selectedService);
    } catch (error) {
      console.error('Failed to reset:', error);
      toast.error('Failed to reset schema');
    } finally {
      setSaving(false);
    }
  };
  
  // Group fields by their group property
  const groupedFields = schema?.fields?.reduce((acc, field) => {
    const group = field.base.group || 'other';
    if (!acc[group]) acc[group] = [];
    acc[group].push(field);
    return acc;
  }, {}) || {};
  
  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-intake-schema-page">
        {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Settings2 className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Intake Schema Manager</h1>
                <p className="text-gray-500">
                  Customize wizard form fields without code changes
                </p>
              </div>
            </div>
            
            {selectedService && hasChanges && (
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleReset}
                  disabled={saving}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reset
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={saving}
                  className="bg-teal-600 hover:bg-teal-700"
                >
                  <Save className="h-4 w-4 mr-2" />
                  {saving ? 'Saving...' : 'Save Changes'}
                </Button>
              </div>
            )}
          </div>
        
        <div className="grid grid-cols-12 gap-6">
          {/* Service List Sidebar */}
          <div className="col-span-12 md:col-span-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Services</CardTitle>
                <CardDescription>Select a service to customize</CardDescription>
              </CardHeader>
              <CardContent className="p-0">
                <div className="divide-y max-h-[600px] overflow-y-auto">
                  {services.map((service) => (
                    <button
                      key={service.service_code}
                      onClick={() => setSelectedService(service.service_code)}
                      className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${
                        selectedService === service.service_code ? 'bg-teal-50 border-l-4 border-teal-500' : ''
                      }`}
                      data-testid={`service-${service.service_code}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-gray-900">
                          {service.service_code.replace(/_/g, ' ')}
                        </span>
                        {service.has_customizations && (
                          <CheckCircle className="h-4 w-4 text-blue-500" />
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {service.field_count} fields
                      </span>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Schema Editor */}
          <div className="col-span-12 md:col-span-8">
            {!selectedService ? (
              <Card className="h-[400px] flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <Settings2 className="h-12 w-12 mx-auto mb-3 opacity-50" />
                  <p>Select a service to customize its intake form</p>
                </div>
              </Card>
            ) : loading ? (
              <Card className="h-[400px] flex items-center justify-center">
                <div className="text-center">
                  <div className="animate-spin h-8 w-8 border-4 border-teal-500 border-t-transparent rounded-full mx-auto" />
                  <p className="mt-2 text-gray-500">Loading schema...</p>
                </div>
              </Card>
            ) : schema ? (
              <div className="space-y-4">
                {/* Schema Info */}
                <Card>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="font-semibold text-gray-900">{selectedService}</h2>
                        <p className="text-sm text-gray-500">
                          {schema.fields.length} fields • Version {schema.schema_version}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        {schema.supports_fast_track && (
                          <Badge variant="outline">Fast Track</Badge>
                        )}
                        {schema.supports_printed_copy && (
                          <Badge variant="outline">Printed Copy</Badge>
                        )}
                        {schema.supports_uploads && (
                          <Badge variant="outline">File Upload</Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* Field Groups */}
                <Accordion type="multiple" defaultValue={Object.keys(groupedFields)} className="space-y-2">
                  {Object.entries(groupedFields).map(([group, fields]) => (
                    <AccordionItem 
                      key={group} 
                      value={group}
                      className="bg-white border rounded-lg"
                    >
                      <AccordionTrigger className="px-4 py-3 hover:no-underline">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">
                            {GROUP_LABELS[group] || group.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                          </span>
                          <Badge variant="secondary" className="text-xs">
                            {fields.length} fields
                          </Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-4 pb-4">
                        <div className="space-y-3">
                          {fields.map((field) => (
                            <FieldEditor
                              key={field.base.field_key}
                              field={field}
                              override={overrides[field.base.field_key]}
                              onChange={(o) => handleOverrideChange(field.base.field_key, o)}
                              onToggleHide={handleToggleHide}
                            />
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
                
                {/* Actions */}
                {hasChanges && (
                  <div className="sticky bottom-4 flex justify-end gap-2 p-4 bg-white border rounded-lg shadow-lg">
                    <Button variant="outline" onClick={handleReset} disabled={saving}>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Reset All
                    </Button>
                    <Button onClick={handleSave} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                      <Save className="h-4 w-4 mr-2" />
                      {saving ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                )}
              </div>
            ) : null}
          </div>
    </div>
    </UnifiedAdminLayout>
  );
}
