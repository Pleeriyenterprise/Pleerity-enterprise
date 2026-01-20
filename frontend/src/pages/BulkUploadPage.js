import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { 
  Upload, 
  ArrowLeft, 
  FileText, 
  CheckCircle, 
  XCircle, 
  RefreshCw,
  Sparkles,
  Trash2,
  AlertTriangle,
  CloudUpload,
  Files,
  Building2
} from 'lucide-react';

const BulkUploadPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedProperty, setSelectedProperty] = useState('');
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResults, setUploadResults] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  React.useEffect(() => {
    fetchProperties();
  }, []);

  const fetchProperties = async () => {
    try {
      const response = await clientAPI.getProperties();
      setProperties(response.data.properties || []);
    } catch (error) {
      toast.error('Failed to load properties');
    } finally {
      setLoading(false);
    }
  };

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  }, []);

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(Array.from(e.target.files));
    }
  };

  const handleFiles = (newFiles) => {
    // Filter for supported file types
    const supportedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    const validFiles = newFiles.filter(file => {
      if (supportedTypes.includes(file.type)) {
        return true;
      }
      // Check by extension as fallback
      const ext = file.name.split('.').pop()?.toLowerCase();
      return ['pdf', 'jpg', 'jpeg', 'png'].includes(ext);
    });

    const invalidCount = newFiles.length - validFiles.length;
    if (invalidCount > 0) {
      toast.warning(`${invalidCount} file(s) skipped - only PDF, JPG, PNG are supported`);
    }

    // Add unique IDs and status to files
    const filesWithMeta = validFiles.map(file => ({
      id: `${file.name}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      file,
      name: file.name,
      size: file.size,
      type: file.type,
      status: 'pending' // pending, uploading, success, error
    }));

    setFiles(prev => [...prev, ...filesWithMeta]);
    setUploadResults(null); // Clear previous results
  };

  const removeFile = (fileId) => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
  };

  const clearAllFiles = () => {
    setFiles([]);
    setUploadResults(null);
  };

  const handleUpload = async () => {
    if (!selectedProperty) {
      toast.error('Please select a property first');
      return;
    }

    if (files.length === 0) {
      toast.error('Please add files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('property_id', selectedProperty);
      
      files.forEach(f => {
        formData.append('files', f.file);
      });

      // Update all files to uploading status
      setFiles(prev => prev.map(f => ({ ...f, status: 'uploading' })));

      const response = await api.post('/documents/bulk-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      });

      // Update file statuses based on results
      const results = response.data.results || [];
      setFiles(prev => prev.map((f, idx) => {
        const result = results.find(r => r.filename === f.name);
        return {
          ...f,
          status: result?.status === 'uploaded' ? 'success' : 'error',
          documentId: result?.document_id,
          matchedRequirement: result?.matched_requirement,
          aiAnalyzed: result?.ai_analyzed,
          error: result?.error
        };
      }));

      setUploadResults(response.data.summary);

      const { successful, failed, auto_matched } = response.data.summary;
      if (failed === 0) {
        toast.success(`All ${successful} documents uploaded successfully!`);
      } else {
        toast.warning(`${successful} uploaded, ${failed} failed`);
      }

      if (auto_matched > 0) {
        toast.info(`${auto_matched} document(s) automatically matched to requirements via AI`);
      }

    } catch (error) {
      toast.error(error.response?.data?.detail || 'Bulk upload failed');
      setFiles(prev => prev.map(f => ({ ...f, status: 'error' })));
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />;
      case 'uploading':
        return <RefreshCw className="w-5 h-5 text-electric-teal animate-spin" />;
      default:
        return <FileText className="w-5 h-5 text-gray-400" />;
    }
  };

  const getDocTypeLabel = (filename) => {
    const lower = filename.toLowerCase();
    if (lower.includes('gas') || lower.includes('cp12') || lower.includes('lgsr')) {
      return { label: 'Gas Safety', color: 'bg-orange-100 text-orange-700' };
    }
    if (lower.includes('eicr') || lower.includes('electrical')) {
      return { label: 'EICR', color: 'bg-blue-100 text-blue-700' };
    }
    if (lower.includes('epc') || lower.includes('energy')) {
      return { label: 'EPC', color: 'bg-green-100 text-green-700' };
    }
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" data-testid="bulk-upload-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-testid="bulk-upload-page">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button 
                onClick={() => navigate('/app/documents')} 
                className="text-gray-300 hover:text-white"
                data-testid="back-btn"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div>
                <h1 className="text-xl font-bold">Bulk Document Upload</h1>
                <p className="text-sm text-gray-300">Upload multiple compliance certificates at once</p>
              </div>
            </div>
            <span className="text-sm text-gray-300">{user?.email}</span>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Property Selection */}
        <Card className="mb-6" data-testid="property-selection-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="w-5 h-5" />
              Select Property
            </CardTitle>
          </CardHeader>
          <CardContent>
            <select
              value={selectedProperty}
              onChange={(e) => setSelectedProperty(e.target.value)}
              className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal text-lg"
              disabled={uploading}
              data-testid="property-select"
            >
              <option value="">Choose a property...</option>
              {properties.map(p => (
                <option key={p.property_id} value={p.property_id}>
                  {p.address_line_1}, {p.city} - {p.postcode}
                </option>
              ))}
            </select>
            {!selectedProperty && (
              <p className="text-sm text-gray-500 mt-2">
                All uploaded documents will be associated with this property
              </p>
            )}
          </CardContent>
        </Card>

        {/* Drop Zone */}
        <Card className="mb-6" data-testid="dropzone-card">
          <CardContent className="p-0">
            <div
              className={`relative border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                dragActive 
                  ? 'border-electric-teal bg-teal-50' 
                  : 'border-gray-300 hover:border-electric-teal'
              } ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              data-testid="dropzone"
            >
              <input
                type="file"
                multiple
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileSelect}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={uploading}
                data-testid="file-input"
              />
              
              <CloudUpload className={`w-16 h-16 mx-auto mb-4 ${dragActive ? 'text-electric-teal' : 'text-gray-400'}`} />
              
              <h3 className="text-lg font-medium text-midnight-blue mb-2">
                {dragActive ? 'Drop files here' : 'Drag & drop files here'}
              </h3>
              <p className="text-gray-500 mb-4">or click to browse</p>
              
              <div className="flex flex-wrap justify-center gap-2 text-xs text-gray-400">
                <span className="px-2 py-1 bg-gray-100 rounded">PDF</span>
                <span className="px-2 py-1 bg-gray-100 rounded">JPG</span>
                <span className="px-2 py-1 bg-gray-100 rounded">PNG</span>
              </div>

              <p className="text-xs text-gray-400 mt-4">
                Max 10MB per file • Supports Gas Safety, EICR, EPC certificates
              </p>
            </div>
          </CardContent>
        </Card>

        {/* AI Info Banner */}
        <div className="bg-gradient-to-r from-teal-50 to-blue-50 border border-teal-200 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-electric-teal mt-0.5" />
            <div>
              <p className="text-sm font-medium text-electric-teal">Smart Auto-Matching</p>
              <p className="text-sm text-gray-600 mt-1">
                Our AI will automatically analyze each document and match it to the appropriate requirement 
                (Gas Safety, EICR, EPC, etc.) based on the certificate content.
              </p>
            </div>
          </div>
        </div>

        {/* Files Queue */}
        {files.length > 0 && (
          <Card className="mb-6" data-testid="files-queue-card">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Files className="w-5 h-5" />
                  Files to Upload ({files.length})
                </CardTitle>
                {!uploading && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={clearAllFiles}
                    data-testid="clear-all-btn"
                  >
                    <Trash2 className="w-4 h-4 mr-1" />
                    Clear All
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3" data-testid="files-list">
                {files.map((f) => {
                  const docType = getDocTypeLabel(f.name);
                  return (
                    <div 
                      key={f.id}
                      className={`flex items-center justify-between p-3 rounded-lg border ${
                        f.status === 'success' ? 'bg-green-50 border-green-200' :
                        f.status === 'error' ? 'bg-red-50 border-red-200' :
                        'bg-gray-50 border-gray-200'
                      }`}
                      data-testid={`file-item-${f.id}`}
                    >
                      <div className="flex items-center gap-3 flex-1">
                        {getStatusIcon(f.status)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 truncate">{f.name}</span>
                            {docType && (
                              <span className={`text-xs px-2 py-0.5 rounded ${docType.color}`}>
                                {docType.label}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-gray-500">
                            <span>{formatFileSize(f.size)}</span>
                            {f.aiAnalyzed && (
                              <span className="text-electric-teal flex items-center gap-1">
                                <Sparkles className="w-3 h-3" />
                                AI Matched
                              </span>
                            )}
                            {f.error && (
                              <span className="text-red-500">{f.error}</span>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {f.status === 'pending' && !uploading && (
                        <button 
                          onClick={() => removeFile(f.id)}
                          className="text-gray-400 hover:text-red-500 p-1"
                          data-testid={`remove-file-${f.id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Upload Progress */}
              {uploading && (
                <div className="mt-4">
                  <div className="flex items-center justify-between text-sm text-gray-600 mb-2">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-electric-teal h-2 rounded-full transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Upload Results Summary */}
        {uploadResults && (
          <Card className="mb-6 border-2 border-green-200" data-testid="upload-results-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-green-700">
                <CheckCircle className="w-5 h-5" />
                Upload Complete
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-4 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-midnight-blue">{uploadResults.total}</div>
                  <div className="text-sm text-gray-500">Total Files</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-600">{uploadResults.successful}</div>
                  <div className="text-sm text-gray-500">Successful</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">{uploadResults.failed}</div>
                  <div className="text-sm text-gray-500">Failed</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-electric-teal">{uploadResults.auto_matched}</div>
                  <div className="text-sm text-gray-500">AI Matched</div>
                </div>
              </div>
              
              <div className="mt-6 flex gap-3">
                <Button onClick={() => navigate('/app/documents')} className="flex-1" data-testid="view-documents-btn">
                  View All Documents
                </Button>
                <Button variant="outline" onClick={clearAllFiles} data-testid="upload-more-btn">
                  Upload More
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Upload Button */}
        {files.length > 0 && !uploadResults && (
          <div className="flex gap-4">
            <Button
              onClick={handleUpload}
              disabled={uploading || !selectedProperty}
              className="flex-1 py-6 text-lg"
              data-testid="upload-btn"
            >
              {uploading ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin mr-2" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5 mr-2" />
                  Upload {files.length} Document{files.length !== 1 ? 's' : ''}
                </>
              )}
            </Button>
          </div>
        )}

        {/* Help Text */}
        {files.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            <p>Select a property and drag files to get started</p>
            <p className="text-sm mt-2">
              Tip: Name your files descriptively (e.g., "gas_safety_cert_2024.pdf") for better AI matching
            </p>
          </div>
        )}
      </main>
    </div>
  );
};

export default BulkUploadPage;
