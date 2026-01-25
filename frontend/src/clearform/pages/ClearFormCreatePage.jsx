/**
 * ClearForm Document Creator
 * 
 * Intent-based document generation wizard with template support.
 * Users can choose between:
 * - AI Generation (describe what you need)
 * - Template Mode (structured form with Smart Profile pre-fill)
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  ArrowLeft, 
  ArrowRight,
  Loader2,
  Mail,
  AlertTriangle,
  FileUser,
  Sparkles,
  LayoutTemplate,
  User,
  CheckCircle,
  Shield,
  Zap
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { documentsApi, creditsApi, templatesApi } from '../api/clearformApi';
import { toast } from 'sonner';

const DOCUMENT_ICONS = {
  formal_letter: Mail,
  complaint_letter: AlertTriangle,
  cv_resume: FileUser,
};

const ClearFormCreatePage = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useClearFormAuth();
  
  // Wizard state
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  
  // Data
  const [documentTypes, setDocumentTypes] = useState([]);
  const [systemTemplates, setSystemTemplates] = useState([]);
  const [smartProfiles, setSmartProfiles] = useState([]);
  const [balance, setBalance] = useState(0);
  
  // Selection state
  const [selectedType, setSelectedType] = useState(null);
  const [generationMode, setGenerationMode] = useState('ai'); // 'ai' or 'template'
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [templateSections, setTemplateSections] = useState([]);
  
  // Form data for AI mode
  const [formData, setFormData] = useState({
    intent: '',
    recipient_name: '',
    recipient_organization: '',
    sender_name: '',
    subject: '',
    tone: 'formal',
    company_name: '',
    issue_date: '',
    issue_description: '',
    desired_resolution: '',
    order_reference: '',
    full_name: '',
    job_title_target: '',
    years_experience: '',
    skills: '',
  });
  
  // Template form data (dynamic based on template)
  const [templateData, setTemplateData] = useState({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [types, walletData] = await Promise.all([
        documentsApi.getTypes(),
        creditsApi.getBalance(),
      ]);
      setDocumentTypes(types);
      setBalance(walletData.credit_balance);
    } catch (error) {
      console.error('Failed to load data:', error);
    }
  };

  // Load templates and profiles when switching to template mode
  const loadTemplatesAndProfiles = async (documentType) => {
    setLoadingTemplates(true);
    try {
      const [templatesRes, profilesRes] = await Promise.all([
        templatesApi.getSystemTemplates(documentType),
        templatesApi.getProfiles(),
      ]);
      setSystemTemplates(templatesRes.templates || []);
      setSmartProfiles(profilesRes.profiles || []);
      
      // Auto-select default profile
      const defaultProfile = profilesRes.profiles?.find(p => p.is_default);
      if (defaultProfile) {
        setSelectedProfile(defaultProfile.profile_id);
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
      toast.error('Failed to load templates');
    } finally {
      setLoadingTemplates(false);
    }
  };

  // Load template details with pre-fill
  const loadTemplateWithPrefill = async (templateId, profileId = null) => {
    try {
      const prefillData = await templatesApi.getPrefilledTemplate(templateId, profileId);
      setTemplateSections(prefillData.sections || []);
      
      // Initialize template data with prefilled values
      const initialData = {};
      prefillData.sections.forEach(section => {
        section.placeholders.forEach(p => {
          initialData[p.key] = p.prefilled_value || p.default_value || '';
        });
      });
      setTemplateData(initialData);
      
    } catch (error) {
      console.error('Failed to load template:', error);
      toast.error('Failed to load template details');
    }
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleTemplateDataChange = (key, value) => {
    setTemplateData({ ...templateData, [key]: value });
  };

  const handleTypeSelect = async (type) => {
    setSelectedType(type);
    setGenerationMode('ai'); // Default to AI mode
    setSelectedTemplate(null);
    setStep(2);
    
    // Pre-load templates for this type
    await loadTemplatesAndProfiles(type.type);
  };

  const handleModeChange = (mode) => {
    setGenerationMode(mode);
    if (mode === 'template' && selectedType) {
      // Show templates for this document type
      const availableTemplates = systemTemplates.filter(
        t => t.document_type === selectedType.type
      );
      if (availableTemplates.length === 1) {
        // Auto-select if only one template
        handleTemplateSelect(availableTemplates[0]);
      }
    }
  };

  const handleTemplateSelect = async (template) => {
    setSelectedTemplate(template);
    await loadTemplateWithPrefill(template.template_id, selectedProfile);
  };

  const handleProfileChange = async (profileId) => {
    setSelectedProfile(profileId);
    if (selectedTemplate) {
      await loadTemplateWithPrefill(selectedTemplate.template_id, profileId);
    }
  };

  const handleGenerate = async () => {
    setLoading(true);
    
    try {
      let result;
      
      if (generationMode === 'template' && selectedTemplate) {
        // Template-based generation
        result = await templatesApi.generateFromTemplate(
          selectedTemplate.template_id,
          templateData,
          selectedProfile
        );
      } else {
        // AI generation (existing flow)
        const payload = {
          document_type: selectedType.type,
          intent: formData.intent,
        };
        
        // Add type-specific fields
        if (selectedType.type === 'formal_letter') {
          Object.assign(payload, {
            recipient_name: formData.recipient_name || undefined,
            recipient_organization: formData.recipient_organization || undefined,
            sender_name: formData.sender_name || undefined,
            subject: formData.subject || undefined,
            tone: formData.tone || undefined,
          });
        } else if (selectedType.type === 'complaint_letter') {
          Object.assign(payload, {
            company_name: formData.company_name || undefined,
            issue_date: formData.issue_date || undefined,
            issue_description: formData.issue_description || undefined,
            desired_resolution: formData.desired_resolution || undefined,
            order_reference: formData.order_reference || undefined,
          });
        } else if (selectedType.type === 'cv_resume') {
          Object.assign(payload, {
            full_name: formData.full_name || undefined,
            job_title_target: formData.job_title_target || undefined,
            years_experience: formData.years_experience ? parseInt(formData.years_experience) : undefined,
            skills: formData.skills ? formData.skills.split(',').map(s => s.trim()) : undefined,
          });
        }
        
        result = await documentsApi.generate(payload);
      }
      
      toast.success('Document generation started!');
      await refreshUser();
      navigate(`/clearform/document/${result.document_id}`);
      
    } catch (error) {
      toast.error(error.message || 'Failed to generate document');
    } finally {
      setLoading(false);
    }
  };

  const canGenerate = () => {
    if (generationMode === 'template') {
      // Check required template fields
      return templateSections.every(section =>
        section.placeholders.every(p => !p.required || templateData[p.key])
      );
    }
    return formData.intent.trim().length > 0;
  };

  const getAvailableTemplates = () => {
    if (!selectedType) return [];
    return systemTemplates.filter(t => t.document_type === selectedType.type);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-500">Balance:</span>
            <span className="font-medium">{balance} credits</span>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="container mx-auto px-4 py-8 max-w-3xl">
        <Button 
          variant="ghost" 
          className="mb-6" 
          onClick={() => step === 1 ? navigate('/clearform/dashboard') : setStep(step - 1)}
        >
          <ArrowLeft className="w-4 h-4 mr-2" /> Back
        </Button>

        {/* Step 1: Select Type */}
        {step === 1 && (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Create New Document</h1>
            <p className="text-slate-600 mb-8">What type of document do you need?</p>
            
            <div className="grid gap-4">
              {documentTypes.map((type) => {
                const Icon = DOCUMENT_ICONS[type.type] || FileText;
                return (
                  <Card 
                    key={type.type} 
                    className="cursor-pointer hover:border-emerald-300 hover:shadow-md transition-all"
                    onClick={() => handleTypeSelect(type)}
                    data-testid={`select-type-${type.type}`}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="w-12 h-12 bg-emerald-100 rounded-lg flex items-center justify-center">
                            <Icon className="w-6 h-6 text-emerald-600" />
                          </div>
                          <div>
                            <CardTitle>{type.name}</CardTitle>
                            <CardDescription>{type.description}</CardDescription>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-lg font-bold text-emerald-600">{type.credit_cost}</span>
                          <span className="text-sm text-slate-500 ml-1">credit{type.credit_cost > 1 ? 's' : ''}</span>
                        </div>
                      </div>
                    </CardHeader>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Step 2: Choose Generation Mode & Enter Details */}
        {step === 2 && selectedType && (
          <>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">{selectedType.name}</h1>
            <p className="text-slate-600 mb-6">Choose how you'd like to create your document</p>
            
            {/* Generation Mode Selection */}
            <Tabs value={generationMode} onValueChange={handleModeChange} className="mb-6">
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="ai" className="flex items-center gap-2" data-testid="mode-ai">
                  <Sparkles className="w-4 h-4" />
                  AI Generation
                </TabsTrigger>
                <TabsTrigger 
                  value="template" 
                  className="flex items-center gap-2"
                  disabled={getAvailableTemplates().length === 0}
                  data-testid="mode-template"
                >
                  <LayoutTemplate className="w-4 h-4" />
                  Use Template
                  {getAvailableTemplates().length > 0 && (
                    <Badge variant="secondary" className="ml-1 text-xs">
                      {getAvailableTemplates().length}
                    </Badge>
                  )}
                </TabsTrigger>
              </TabsList>

              {/* AI Generation Mode */}
              <TabsContent value="ai" className="mt-6">
                <Card>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-purple-500" />
                      <CardTitle className="text-lg">AI-Powered Generation</CardTitle>
                    </div>
                    <CardDescription>
                      Describe what you need and our AI will create a professional document for you.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Intent - Always Required */}
                    <div className="space-y-2">
                      <Label htmlFor="intent">What do you need this document for? *</Label>
                      <Textarea
                        id="intent"
                        name="intent"
                        value={formData.intent}
                        onChange={handleChange}
                        placeholder="Describe what you want to achieve with this document..."
                        rows={3}
                        required
                        data-testid="intent-input"
                      />
                      <p className="text-xs text-slate-500">Be specific - the more detail you provide, the better the result.</p>
                    </div>

                    {/* Type-specific fields (existing code) */}
                    {selectedType.type === 'formal_letter' && (
                      <>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="recipient_name">Recipient Name</Label>
                            <Input
                              id="recipient_name"
                              name="recipient_name"
                              value={formData.recipient_name}
                              onChange={handleChange}
                              placeholder="John Doe"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="recipient_organization">Organization</Label>
                            <Input
                              id="recipient_organization"
                              name="recipient_organization"
                              value={formData.recipient_organization}
                              onChange={handleChange}
                              placeholder="ABC Company Ltd"
                            />
                          </div>
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="sender_name">Your Name</Label>
                            <Input
                              id="sender_name"
                              name="sender_name"
                              value={formData.sender_name}
                              onChange={handleChange}
                              placeholder="Jane Smith"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="subject">Subject</Label>
                            <Input
                              id="subject"
                              name="subject"
                              value={formData.subject}
                              onChange={handleChange}
                              placeholder="Regarding your inquiry"
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {selectedType.type === 'complaint_letter' && (
                      <>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="company_name">Company Name *</Label>
                            <Input
                              id="company_name"
                              name="company_name"
                              value={formData.company_name}
                              onChange={handleChange}
                              placeholder="TechStore Ltd"
                              required
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="issue_date">Issue Date</Label>
                            <Input
                              id="issue_date"
                              name="issue_date"
                              value={formData.issue_date}
                              onChange={handleChange}
                              placeholder="January 15, 2026"
                            />
                          </div>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="issue_description">Issue Description</Label>
                          <Textarea
                            id="issue_description"
                            name="issue_description"
                            value={formData.issue_description}
                            onChange={handleChange}
                            placeholder="Describe what went wrong..."
                            rows={2}
                          />
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="desired_resolution">Desired Resolution</Label>
                            <Input
                              id="desired_resolution"
                              name="desired_resolution"
                              value={formData.desired_resolution}
                              onChange={handleChange}
                              placeholder="Full refund"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="order_reference">Order/Reference Number</Label>
                            <Input
                              id="order_reference"
                              name="order_reference"
                              value={formData.order_reference}
                              onChange={handleChange}
                              placeholder="ORD-12345"
                            />
                          </div>
                        </div>
                      </>
                    )}

                    {selectedType.type === 'cv_resume' && (
                      <>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="full_name">Full Name *</Label>
                            <Input
                              id="full_name"
                              name="full_name"
                              value={formData.full_name}
                              onChange={handleChange}
                              placeholder="John Smith"
                              required
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="job_title_target">Target Role</Label>
                            <Input
                              id="job_title_target"
                              name="job_title_target"
                              value={formData.job_title_target}
                              onChange={handleChange}
                              placeholder="Senior Software Engineer"
                            />
                          </div>
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="space-y-2">
                            <Label htmlFor="years_experience">Years of Experience</Label>
                            <Input
                              id="years_experience"
                              name="years_experience"
                              type="number"
                              value={formData.years_experience}
                              onChange={handleChange}
                              placeholder="5"
                            />
                          </div>
                          <div className="space-y-2">
                            <Label htmlFor="skills">Key Skills (comma-separated)</Label>
                            <Input
                              id="skills"
                              name="skills"
                              value={formData.skills}
                              onChange={handleChange}
                              placeholder="Python, JavaScript, Leadership"
                            />
                          </div>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Template Mode */}
              <TabsContent value="template" className="mt-6">
                {loadingTemplates ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
                  </div>
                ) : (
                  <>
                    {/* Template Selection */}
                    {!selectedTemplate && (
                      <div className="space-y-4">
                        <p className="text-sm text-slate-600">
                          Choose a professional template with compliance guidelines:
                        </p>
                        {getAvailableTemplates().map((template) => (
                          <Card 
                            key={template.template_id}
                            className="cursor-pointer hover:border-emerald-300 hover:shadow-md transition-all"
                            onClick={() => handleTemplateSelect(template)}
                            data-testid={`select-template-${template.template_id}`}
                          >
                            <CardContent className="py-4">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                                    <LayoutTemplate className="w-5 h-5 text-blue-600" />
                                  </div>
                                  <div>
                                    <h4 className="font-medium text-slate-900">{template.name}</h4>
                                    <p className="text-sm text-slate-500">{template.description}</p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {template.has_rule_pack && (
                                    <Badge variant="outline" className="text-blue-600 border-blue-200">
                                      <Shield className="w-3 h-3 mr-1" />
                                      Compliance
                                    </Badge>
                                  )}
                                  <Badge className="bg-emerald-100 text-emerald-700">
                                    {template.credit_cost} credit
                                  </Badge>
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    )}

                    {/* Template Form */}
                    {selectedTemplate && (
                      <Card>
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <LayoutTemplate className="w-5 h-5 text-blue-500" />
                              <CardTitle className="text-lg">{selectedTemplate.name}</CardTitle>
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedTemplate(null)}
                            >
                              Change Template
                            </Button>
                          </div>
                          <CardDescription className="flex items-center gap-4">
                            <span>{selectedTemplate.description}</span>
                            {selectedTemplate.has_rule_pack && (
                              <Badge variant="outline" className="text-blue-600 border-blue-200">
                                <Shield className="w-3 h-3 mr-1" />
                                UK Compliance Standards
                              </Badge>
                            )}
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                          {/* Smart Profile Selector */}
                          {smartProfiles.length > 0 && (
                            <div className="p-4 bg-slate-50 rounded-lg border">
                              <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2">
                                  <User className="w-4 h-4 text-slate-600" />
                                  <span className="font-medium text-sm">Auto-fill from Smart Profile</span>
                                </div>
                                <Badge variant="secondary" className="text-xs">
                                  <Zap className="w-3 h-3 mr-1" />
                                  Saves time
                                </Badge>
                              </div>
                              <Select 
                                value={selectedProfile || ''} 
                                onValueChange={handleProfileChange}
                              >
                                <SelectTrigger data-testid="profile-selector">
                                  <SelectValue placeholder="Select a profile..." />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="">No profile</SelectItem>
                                  {smartProfiles.map((profile) => (
                                    <SelectItem 
                                      key={profile.profile_id} 
                                      value={profile.profile_id}
                                    >
                                      {profile.name} {profile.is_default && '(Default)'}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                          )}

                          {/* Dynamic Template Fields */}
                          {templateSections.map((section) => (
                            <div key={section.section_id} className="space-y-4">
                              <h4 className="font-medium text-slate-800 flex items-center gap-2">
                                {section.name}
                                {section.is_ai_enhanced && (
                                  <Badge variant="secondary" className="text-xs">
                                    <Sparkles className="w-3 h-3 mr-1" />
                                    AI Enhanced
                                  </Badge>
                                )}
                              </h4>
                              
                              {section.placeholders.map((placeholder) => (
                                <div key={placeholder.key} className="space-y-2">
                                  <Label htmlFor={placeholder.key}>
                                    {placeholder.label}
                                    {placeholder.required && ' *'}
                                    {placeholder.prefilled_value && (
                                      <Badge variant="outline" className="ml-2 text-xs text-emerald-600">
                                        <CheckCircle className="w-3 h-3 mr-1" />
                                        Pre-filled
                                      </Badge>
                                    )}
                                  </Label>
                                  {placeholder.field_type === 'text' && placeholder.key.includes('description') ? (
                                    <Textarea
                                      id={placeholder.key}
                                      value={templateData[placeholder.key] || ''}
                                      onChange={(e) => handleTemplateDataChange(placeholder.key, e.target.value)}
                                      placeholder={`Enter ${placeholder.label.toLowerCase()}...`}
                                      rows={3}
                                      data-testid={`template-field-${placeholder.key}`}
                                    />
                                  ) : (
                                    <Input
                                      id={placeholder.key}
                                      type={placeholder.field_type === 'date' ? 'text' : 'text'}
                                      value={templateData[placeholder.key] || ''}
                                      onChange={(e) => handleTemplateDataChange(placeholder.key, e.target.value)}
                                      placeholder={placeholder.default_value || `Enter ${placeholder.label.toLowerCase()}...`}
                                      data-testid={`template-field-${placeholder.key}`}
                                    />
                                  )}
                                </div>
                              ))}
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    )}
                  </>
                )}
              </TabsContent>
            </Tabs>

            {/* Generate Button */}
            <Card className="mt-6">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm">
                    <span className="text-slate-500">Cost:</span>{' '}
                    <span className="font-bold text-emerald-600">
                      {generationMode === 'template' && selectedTemplate 
                        ? selectedTemplate.credit_cost 
                        : selectedType.credit_cost} credit{selectedType.credit_cost > 1 ? 's' : ''}
                    </span>
                    <span className="text-slate-400 ml-2">
                      • Balance: {balance} credits
                    </span>
                  </div>
                  <Button 
                    onClick={handleGenerate} 
                    disabled={loading || !canGenerate() || (generationMode === 'template' && !selectedTemplate)}
                    className="gap-2 bg-emerald-600 hover:bg-emerald-700"
                    data-testid="generate-btn"
                  >
                    {loading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : generationMode === 'template' ? (
                      <LayoutTemplate className="w-4 h-4" />
                    ) : (
                      <Sparkles className="w-4 h-4" />
                    )}
                    Generate Document
                  </Button>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </main>
    </div>
  );
};

export default ClearFormCreatePage;
