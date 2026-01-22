import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Checkbox } from '../components/ui/checkbox';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Upload,
  Clock,
  Send,
  RefreshCw,
  ArrowLeft,
  Info,
  File,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Field type configurations
const fieldConfig = {
  tenant_name: { label: 'Tenant Full Name', type: 'text', placeholder: 'Enter tenant full name' },
  property_address: { label: 'Property Address', type: 'textarea', placeholder: 'Enter full property address' },
  tenancy_start_date: { label: 'Tenancy Start Date', type: 'date' },
  tenancy_end_date: { label: 'Tenancy End Date', type: 'date' },
  notice_date: { label: 'Notice Date', type: 'date' },
  deposit_amount: { label: 'Deposit Amount (£)', type: 'number', placeholder: '0.00' },
  monthly_rent: { label: 'Monthly Rent (£)', type: 'number', placeholder: '0.00' },
  eicr_date: { label: 'EICR Certificate Date', type: 'date' },
  gas_cert_date: { label: 'Gas Safety Certificate Date', type: 'date' },
  epc_rating: { label: 'EPC Rating', type: 'select', options: ['A', 'B', 'C', 'D', 'E', 'F', 'G'] },
  landlord_details: { label: 'Landlord Details', type: 'textarea', placeholder: 'Enter landlord name, address, and contact details' },
  clarification: { label: 'Additional Clarification', type: 'textarea', placeholder: 'Provide any additional information requested' },
};

const ClientProvideInfoPage = () => {
  const { orderId } = useParams();
  const navigate = useNavigate();
  
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestData, setRequestData] = useState(null);
  const [error, setError] = useState(null);
  
  // Form state
  const [fieldValues, setFieldValues] = useState({});
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [confirmation, setConfirmation] = useState(false);
  
  // Fetch the input request details
  useEffect(() => {
    const fetchRequest = async () => {
      try {
        const token = localStorage.getItem('auth_token');
        const response = await fetch(`${API_URL}/api/client/orders/${orderId}/input-required`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        
        if (response.ok) {
          const data = await response.json();
          if (!data.requires_input) {
            setError('No information is currently required for this order.');
          } else {
            setRequestData(data);
            // Initialize field values
            const initialValues = {};
            (data.requested_fields || []).forEach(f => {
              initialValues[f] = '';
            });
            setFieldValues(initialValues);
          }
        } else if (response.status === 403) {
          setError('You do not have permission to view this order.');
        } else if (response.status === 404) {
          setError('Order not found.');
        } else {
          setError('Failed to load request details.');
        }
      } catch (err) {
        console.error('Failed to fetch request:', err);
        setError('Failed to connect to server.');
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchRequest();
  }, [orderId]);
  
  const handleFieldChange = (fieldId, value) => {
    setFieldValues(prev => ({ ...prev, [fieldId]: value }));
  };
  
  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    
    for (const file of files) {
      // Validate file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`${file.name} is too large. Maximum size is 10MB.`);
        continue;
      }
      
      // Upload file
      try {
        const token = localStorage.getItem('auth_token');
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${API_URL}/api/client/orders/${orderId}/upload-file`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        
        if (response.ok) {
          const data = await response.json();
          setUploadedFiles(prev => [...prev, {
            file_id: data.file_id,
            filename: data.filename,
            size_bytes: data.size_bytes,
          }]);
          toast.success(`${file.name} uploaded successfully`);
        } else {
          const data = await response.json();
          toast.error(data.detail || `Failed to upload ${file.name}`);
        }
      } catch (err) {
        toast.error(`Failed to upload ${file.name}`);
      }
    }
    
    // Reset file input
    e.target.value = '';
  };
  
  const removeFile = (fileId) => {
    setUploadedFiles(prev => prev.filter(f => f.file_id !== fileId));
  };
  
  const handleSubmit = async () => {
    if (!confirmation) {
      toast.error('Please confirm the information is accurate');
      return;
    }
    
    setIsSubmitting(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_URL}/api/client/orders/${orderId}/submit-input`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fields: fieldValues,
          confirmation: true,
        }),
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toast.success('Information submitted successfully!');
        // Redirect to dashboard after short delay
        setTimeout(() => navigate('/app/dashboard'), 2000);
      } else {
        toast.error(data.detail || 'Failed to submit information');
      }
    } catch (err) {
      toast.error('Failed to submit information');
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };
  
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <RefreshCw className="h-8 w-8 animate-spin mx-auto text-blue-600" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  
  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardContent className="pt-6">
            <div className="text-center">
              <AlertCircle className="h-12 w-12 mx-auto text-red-500 mb-4" />
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Unable to Load</h2>
              <p className="text-gray-600 mb-4">{error}</p>
              <Button onClick={() => navigate('/app/dashboard')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Return to Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/app/dashboard')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back
          </Button>
        </div>
        
        {/* Action Required Banner */}
        <Card className="border-orange-200 bg-orange-50">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-orange-100 rounded-full">
                <AlertCircle className="h-6 w-6 text-orange-600" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-orange-900">
                  Action Required: Additional Information Needed
                </h2>
                <p className="text-orange-700 text-sm mt-1">
                  Order Reference: <span className="font-mono font-medium">{orderId}</span>
                </p>
                <p className="text-orange-700 text-sm">
                  Service: {requestData?.service_name}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        {/* Main Form */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Provide Information
            </CardTitle>
            <CardDescription>
              Please provide the requested information to continue processing your order.
            </CardDescription>
          </CardHeader>
          
          <CardContent className="space-y-6">
            {/* Admin Request Notes */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                <div>
                  <p className="font-medium text-blue-900">What we need from you:</p>
                  <p className="text-blue-800 mt-2 whitespace-pre-wrap">
                    {requestData?.request_notes}
                  </p>
                  {requestData?.deadline && (
                    <div className="flex items-center gap-2 mt-3 text-blue-700">
                      <Clock className="h-4 w-4" />
                      <span className="text-sm">
                        Please respond by: <strong>{formatDate(requestData.deadline)}</strong>
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            
            <Separator />
            
            {/* Requested Fields */}
            {requestData?.requested_fields?.length > 0 && (
              <div className="space-y-4">
                <h3 className="font-medium text-gray-900">Requested Information</h3>
                
                {requestData.requested_fields.map(fieldId => {
                  const config = fieldConfig[fieldId] || { 
                    label: fieldId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
                    type: 'text',
                  };
                  
                  return (
                    <div key={fieldId} className="space-y-2">
                      <Label htmlFor={fieldId}>{config.label}</Label>
                      
                      {config.type === 'text' && (
                        <Input
                          id={fieldId}
                          value={fieldValues[fieldId] || ''}
                          onChange={(e) => handleFieldChange(fieldId, e.target.value)}
                          placeholder={config.placeholder}
                        />
                      )}
                      
                      {config.type === 'textarea' && (
                        <Textarea
                          id={fieldId}
                          value={fieldValues[fieldId] || ''}
                          onChange={(e) => handleFieldChange(fieldId, e.target.value)}
                          placeholder={config.placeholder}
                          rows={3}
                        />
                      )}
                      
                      {config.type === 'date' && (
                        <Input
                          id={fieldId}
                          type="date"
                          value={fieldValues[fieldId] || ''}
                          onChange={(e) => handleFieldChange(fieldId, e.target.value)}
                        />
                      )}
                      
                      {config.type === 'number' && (
                        <Input
                          id={fieldId}
                          type="number"
                          value={fieldValues[fieldId] || ''}
                          onChange={(e) => handleFieldChange(fieldId, e.target.value)}
                          placeholder={config.placeholder}
                          step="0.01"
                        />
                      )}
                      
                      {config.type === 'select' && (
                        <select
                          id={fieldId}
                          value={fieldValues[fieldId] || ''}
                          onChange={(e) => handleFieldChange(fieldId, e.target.value)}
                          className="w-full px-3 py-2 border rounded-md"
                        >
                          <option value="">Select...</option>
                          {config.options.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            
            {/* Additional Notes (always shown) */}
            <div className="space-y-2">
              <Label htmlFor="additional_notes">Additional Notes</Label>
              <Textarea
                id="additional_notes"
                value={fieldValues.additional_notes || ''}
                onChange={(e) => handleFieldChange('additional_notes', e.target.value)}
                placeholder="Any other information you'd like to provide..."
                rows={3}
              />
            </div>
            
            {/* File Upload */}
            {requestData?.request_attachments && (
              <div className="space-y-4">
                <Separator />
                
                <div className="space-y-2">
                  <Label>Upload Documents</Label>
                  <p className="text-sm text-gray-500">
                    Upload any certificates or documents requested. Max file size: 10MB.
                  </p>
                  
                  <div className="border-2 border-dashed rounded-lg p-6 text-center">
                    <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                    <p className="text-sm text-gray-600 mb-2">
                      Drag and drop files here, or click to browse
                    </p>
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                      onChange={handleFileUpload}
                      className="hidden"
                      id="file-upload"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => document.getElementById('file-upload').click()}
                    >
                      Choose Files
                    </Button>
                    <p className="text-xs text-gray-400 mt-2">
                      Supported: PDF, JPG, PNG, DOC, DOCX
                    </p>
                  </div>
                  
                  {/* Uploaded files list */}
                  {uploadedFiles.length > 0 && (
                    <div className="space-y-2 mt-4">
                      <p className="text-sm font-medium">Uploaded Files:</p>
                      {uploadedFiles.map(file => (
                        <div
                          key={file.file_id}
                          className="flex items-center justify-between bg-gray-50 rounded-lg p-3"
                        >
                          <div className="flex items-center gap-2">
                            <File className="h-4 w-4 text-gray-500" />
                            <span className="text-sm">{file.filename}</span>
                            <Badge variant="outline" className="text-xs">
                              {formatFileSize(file.size_bytes)}
                            </Badge>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeFile(file.file_id)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            <Separator />
            
            {/* Confirmation */}
            <div className="flex items-start gap-2">
              <Checkbox
                id="confirmation"
                checked={confirmation}
                onCheckedChange={setConfirmation}
              />
              <label htmlFor="confirmation" className="text-sm leading-tight">
                I confirm that the information provided is accurate to the best of my knowledge.
              </label>
            </div>
            
            {/* Info box */}
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600 mt-0.5" />
                <p className="text-sm text-gray-600">
                  Once you submit, your order will automatically resume processing. 
                  You'll receive an update when your documents are ready.
                </p>
              </div>
            </div>
            
            {/* Submit button */}
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting || !confirmation}
              className="w-full"
              size="lg"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                  Submitting...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Submit Information
                </>
              )}
            </Button>
          </CardContent>
        </Card>
        
        {/* Previous Responses */}
        {requestData?.previous_responses?.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Previous Submissions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {requestData.previous_responses.map((resp, idx) => (
                <div key={idx} className="bg-gray-50 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <Badge variant="outline" className="text-xs">
                      Submission #{resp.version}
                    </Badge>
                    <span className="text-xs text-gray-500">
                      {formatDate(resp.submitted_at)}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600">
                    {Object.entries(resp.payload || {}).map(([key, value]) => (
                      <p key={key}>
                        <span className="font-medium">{key.replace(/_/g, ' ')}:</span> {value}
                      </p>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default ClientProvideInfoPage;
