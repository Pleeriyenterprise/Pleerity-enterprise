import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api, { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { 
  FileText, 
  Upload, 
  ArrowLeft, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Sparkles,
  Calendar,
  User,
  Building2,
  Hash,
  AlertTriangle,
  RefreshCw,
  Eye
} from 'lucide-react';

const DocumentsPage = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [uploadForm, setUploadForm] = useState({
    property_id: '',
    requirement_id: '',
    file: null
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [docsRes, propsRes, reqsRes] = await Promise.all([
        api.get('/documents'),
        clientAPI.getProperties(),
        clientAPI.getRequirements()
      ]);
      setDocuments(docsRes.data.documents || []);
      setProperties(propsRes.data.properties || []);
      setRequirements(reqsRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadForm({ ...uploadForm, file });
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!uploadForm.file || !uploadForm.property_id || !uploadForm.requirement_id) {
      toast.error('Please fill all fields');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadForm.file);
      formData.append('property_id', uploadForm.property_id);
      formData.append('requirement_id', uploadForm.requirement_id);

      await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      toast.success('Document uploaded successfully');
      setUploadForm({ property_id: '', requirement_id: '', file: null });
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const analyzeDocument = async (documentId) => {
    setAnalyzing(documentId);
    try {
      const response = await api.post(`/documents/analyze/${documentId}`);
      
      if (response.data.extraction?.status === 'completed') {
        toast.success('Document analyzed successfully');
        // Update the document in state
        setDocuments(docs => docs.map(d => 
          d.document_id === documentId 
            ? { ...d, ai_extraction: response.data.extraction }
            : d
        ));
      } else {
        toast.error(response.data.error || 'Analysis failed');
      }
    } catch (error) {
      toast.error('Failed to analyze document');
    } finally {
      setAnalyzing(null);
    }
  };

  const getStatusBadge = (status) => {
    const badges = {
      PENDING: { icon: Clock, color: 'bg-yellow-100 text-yellow-800' },
      VERIFIED: { icon: CheckCircle, color: 'bg-green-100 text-green-800' },
      REJECTED: { icon: XCircle, color: 'bg-red-100 text-red-800' }
    };
    const badge = badges[status] || badges.PENDING;
    const Icon = badge.icon;
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 text-xs font-medium rounded-full ${badge.color}`}>
        <Icon className="w-3 h-3" />
        {status}
      </span>
    );
  };

  const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.5) return 'text-yellow-600';
    return 'text-red-600';
  };

  const filteredRequirements = requirements.filter(r => 
    r.property_id === uploadForm.property_id
  );

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button onClick={() => navigate('/app/dashboard')} className="text-gray-300 hover:text-white">
                <ArrowLeft className="w-5 h-5" />
              </button>
              <h1 className="text-xl font-bold">Documents</h1>
            </div>
            <span className="text-sm text-gray-300">{user?.email}</span>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Form */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Upload className="w-5 h-5" />
                  Upload Document
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleUpload} className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Property</label>
                    <select
                      value={uploadForm.property_id}
                      onChange={(e) => setUploadForm({ ...uploadForm, property_id: e.target.value, requirement_id: '' })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                    >
                      <option value="">Select property...</option>
                      {properties.map(p => (
                        <option key={p.property_id} value={p.property_id}>
                          {p.address_line_1}, {p.city}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Requirement</label>
                    <select
                      value={uploadForm.requirement_id}
                      onChange={(e) => setUploadForm({ ...uploadForm, requirement_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                      disabled={!uploadForm.property_id}
                    >
                      <option value="">Select requirement...</option>
                      {filteredRequirements.map(r => (
                        <option key={r.requirement_id} value={r.requirement_id}>
                          {r.description}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">File</label>
                    <input
                      type="file"
                      onChange={handleFileChange}
                      accept=".pdf,.jpg,.jpeg,.png"
                      className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-electric-teal"
                      required
                    />
                    <p className="text-xs text-gray-500 mt-1">PDF, JPG, PNG (max 10MB)</p>
                  </div>

                  <Button type="submit" disabled={uploading} className="w-full">
                    {uploading ? (
                      <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Upload className="w-4 h-4 mr-2" />
                    )}
                    Upload Document
                  </Button>
                </form>
              </CardContent>
            </Card>

            {/* AI Analysis Info */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-electric-teal" />
                  AI Document Analysis
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-gray-600">
                <p className="mb-3">
                  Our AI can automatically extract key information from your compliance documents:
                </p>
                <ul className="space-y-2">
                  <li className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-gray-400" />
                    Issue and expiry dates
                  </li>
                  <li className="flex items-center gap-2">
                    <Hash className="w-4 h-4 text-gray-400" />
                    Certificate numbers
                  </li>
                  <li className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-400" />
                    Engineer details
                  </li>
                  <li className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-gray-400" />
                    Property information
                  </li>
                </ul>
                <p className="mt-3 text-xs text-gray-500">
                  Click "Analyze" on any document to extract metadata automatically.
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Documents List */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <FileText className="w-5 h-5" />
                    Your Documents ({documents.length})
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                {documents.length === 0 ? (
                  <div className="text-center py-12">
                    <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No documents uploaded yet</p>
                    <p className="text-sm text-gray-400 mt-2">
                      Upload your compliance certificates to get started
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {documents.map((doc) => (
                      <div 
                        key={doc.document_id}
                        className="border border-gray-200 rounded-lg p-4 hover:border-electric-teal transition-colors"
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <FileText className="w-5 h-5 text-electric-teal" />
                              <span className="font-medium text-midnight-blue">
                                {doc.original_filename || 'Document'}
                              </span>
                              {getStatusBadge(doc.status)}
                            </div>
                            <p className="text-sm text-gray-500 mb-2">
                              Uploaded: {new Date(doc.uploaded_at).toLocaleDateString()}
                            </p>
                            
                            {/* AI Extraction Results */}
                            {doc.ai_extraction?.status === 'completed' && doc.ai_extraction?.data && (
                              <div className="mt-3 p-3 bg-gradient-to-r from-teal-50 to-blue-50 rounded-lg border border-teal-100">
                                <div className="flex items-center gap-2 mb-2">
                                  <Sparkles className="w-4 h-4 text-electric-teal" />
                                  <span className="text-sm font-medium text-electric-teal">AI Extracted Data</span>
                                  <span className={`text-xs ${getConfidenceColor(doc.ai_extraction.data.confidence_scores?.overall || 0)}`}>
                                    ({Math.round((doc.ai_extraction.data.confidence_scores?.overall || 0) * 100)}% confidence)
                                  </span>
                                </div>
                                <div className="grid grid-cols-2 gap-2 text-sm">
                                  {doc.ai_extraction.data.document_type && (
                                    <div>
                                      <span className="text-gray-500">Type:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.document_type}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.certificate_number && (
                                    <div>
                                      <span className="text-gray-500">Cert #:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.certificate_number}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.issue_date && (
                                    <div>
                                      <span className="text-gray-500">Issued:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.issue_date}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.expiry_date && (
                                    <div>
                                      <span className="text-gray-500">Expires:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.expiry_date}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.engineer_name && (
                                    <div>
                                      <span className="text-gray-500">Engineer:</span>{' '}
                                      <span className="font-medium">{doc.ai_extraction.data.engineer_name}</span>
                                    </div>
                                  )}
                                  {doc.ai_extraction.data.result && (
                                    <div>
                                      <span className="text-gray-500">Result:</span>{' '}
                                      <span className={`font-medium ${doc.ai_extraction.data.result === 'PASS' || doc.ai_extraction.data.result === 'SATISFACTORY' ? 'text-green-600' : 'text-red-600'}`}>
                                        {doc.ai_extraction.data.result}
                                      </span>
                                    </div>
                                  )}
                                </div>
                                {doc.ai_extraction.data.key_findings?.length > 0 && (
                                  <div className="mt-2">
                                    <span className="text-xs text-gray-500">Key Findings:</span>
                                    <ul className="text-xs text-gray-600 list-disc list-inside">
                                      {doc.ai_extraction.data.key_findings.slice(0, 3).map((f, i) => (
                                        <li key={i}>{f}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {doc.ai_extraction?.status === 'failed' && (
                              <div className="mt-3 p-3 bg-red-50 rounded-lg border border-red-100">
                                <div className="flex items-center gap-2 text-red-600">
                                  <AlertTriangle className="w-4 h-4" />
                                  <span className="text-sm">Analysis failed - try again or verify manually</span>
                                </div>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex items-center gap-2 ml-4">
                            {!doc.ai_extraction?.data && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => analyzeDocument(doc.document_id)}
                                disabled={analyzing === doc.document_id}
                              >
                                {analyzing === doc.document_id ? (
                                  <RefreshCw className="w-4 h-4 animate-spin" />
                                ) : (
                                  <>
                                    <Sparkles className="w-4 h-4 mr-1" />
                                    Analyze
                                  </>
                                )}
                              </Button>
                            )}
                            {doc.file_url && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => window.open(doc.file_url, '_blank')}
                              >
                                <Eye className="w-4 h-4" />
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
};

export default DocumentsPage;
