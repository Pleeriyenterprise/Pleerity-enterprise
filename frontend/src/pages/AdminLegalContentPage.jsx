import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Save, RotateCcw, FileText, AlertCircle, Check, RefreshCw, Database, Eye, Pencil, ExternalLink } from 'lucide-react';
import apiClient from '../api/client';
import LegalContentMarkdown from '../components/public/LegalContentMarkdown';

const EMPTY_ROW = (slug, title) => ({
  slug,
  title,
  content: '',
  version: 0,
  updated_at: null,
  updated_by: null,
  content_length: 0,
});

const INITIAL_CONTENT = {
  privacy: EMPTY_ROW('privacy', 'Privacy Policy'),
  terms: EMPTY_ROW('terms', 'Terms of Service'),
  cookies: EMPTY_ROW('cookies', 'Cookie Policy'),
  accessibility: EMPTY_ROW('accessibility', 'Accessibility Statement'),
  careers: EMPTY_ROW('careers', 'Careers'),
  partnerships: EMPTY_ROW('partnerships', 'Partnerships'),
  about: EMPTY_ROW('about', 'About Us'),
};

const LIVE_PAGE_PATHS = {
  privacy: '/legal/privacy',
  terms: '/legal/terms',
  cookies: '/legal/cookies',
  accessibility: '/accessibility',
  careers: '/careers',
  partnerships: '/partnerships',
  about: '/about',
};

const TABS = [
  { value: 'privacy', label: 'Privacy Policy', icon: FileText },
  { value: 'terms', label: 'Terms', icon: FileText },
  { value: 'cookies', label: 'Cookies', icon: FileText },
  { value: 'accessibility', label: 'Accessibility', icon: FileText },
  { value: 'careers', label: 'Careers', icon: FileText },
  { value: 'partnerships', label: 'Partnerships', icon: FileText },
  { value: 'about', label: 'About Us', icon: FileText },
];

function normalizeRow(row, slug) {
  const fallback = INITIAL_CONTENT[slug] || EMPTY_ROW(slug, slug);
  if (!row || typeof row !== 'object') return { ...fallback };
  const content = row.content ?? '';
  return {
    slug: row.slug || slug,
    title: row.title || fallback.title,
    content,
    version: Number(row.version) || 0,
    updated_at: row.updated_at ?? null,
    updated_by: row.updated_by ?? null,
    content_length: row.content_length ?? content.length,
    provenance: row.provenance ?? null,
  };
}

function formatUpdatedAt(value) {
  if (!value) return 'Never';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? 'Never' : d.toLocaleString();
}

const AdminLegalContentPage = () => {
  const [activeTab, setActiveTab] = useState('privacy');
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [message, setMessage] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [content, setContent] = useState(INITIAL_CONTENT);
  const [editorMode, setEditorMode] = useState('edit');
  const [preview, setPreview] = useState({
    loading: false,
    content: '',
    sanitizationApplied: false,
    error: null,
    stale: false,
  });

  const applyRow = useCallback((slug, row) => {
    setContent((prev) => ({
      ...prev,
      [slug]: normalizeRow(row, slug),
    }));
  }, []);

  const loadSlug = useCallback(async (slug, { quiet = false } = {}) => {
    if (!quiet) setTabLoading(true);
    try {
      const { data } = await apiClient.get(`/admin/legal-content/${slug}`);
      applyRow(slug, data);
      return data;
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail || error.message;
      setLoadError(`Failed to load ${slug} (${status || 'network'}): ${detail}`);
      return null;
    } finally {
      if (!quiet) setTabLoading(false);
    }
  }, [applyRow]);

  const loadAllContent = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const { data } = await apiClient.get('/admin/legal-content');
      if (!Array.isArray(data)) {
        throw new Error('Unexpected admin legal content response');
      }
      const next = { ...INITIAL_CONTENT };
      data.forEach((item) => {
        if (item?.slug) {
          next[item.slug] = normalizeRow(item, item.slug);
        }
      });
      setContent(next);
    } catch (error) {
      const status = error?.response?.status;
      const detail = error?.response?.data?.detail || error.message;
      setLoadError(`Failed to load legal content (${status || 'network'}): ${detail}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAllContent();
  }, [loadAllContent]);

  useEffect(() => {
    loadSlug(activeTab, { quiet: true });
  }, [activeTab, loadSlug]);

  useEffect(() => {
    setEditorMode('edit');
    setPreview({
      loading: false,
      content: '',
      sanitizationApplied: false,
      error: null,
      stale: false,
    });
  }, [activeTab]);

  const refreshPreview = useCallback(async (slug) => {
    const row = content[slug];
    if (!row) return;
    setPreview((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const { data } = await apiClient.post(`/admin/legal-content/${slug}/preview`, {
        title: row.title,
        content: row.content,
      });
      setPreview({
        loading: false,
        content: data.content || '',
        sanitizationApplied: Boolean(data.sanitization_applied),
        error: null,
        stale: false,
      });
    } catch (error) {
      const detail = error?.response?.data?.detail || error.message || 'Preview failed';
      setPreview((prev) => ({
        ...prev,
        loading: false,
        error: String(detail),
        stale: false,
      }));
    }
  }, [content]);

  const activeDraftContent = content[activeTab]?.content ?? '';
  const activeDraftTitle = content[activeTab]?.title ?? '';

  useEffect(() => {
    if (editorMode !== 'preview') return;
    setPreview((prev) => (prev.content ? { ...prev, stale: true } : prev));
  }, [activeDraftContent, activeDraftTitle, editorMode, activeTab]);

  const openPreview = (slug) => {
    setEditorMode('preview');
    refreshPreview(slug);
  };

  const handleSave = async (slug) => {
    setSaving(true);
    setMessage(null);
    const row = content[slug];
    try {
      const { data } = await apiClient.put(`/admin/legal-content/${slug}`, {
        slug,
        title: row.title,
        content: row.content,
      });
      if (data?.content) {
        applyRow(slug, data.content);
      } else {
        await loadSlug(slug, { quiet: true });
      }
      setMessage({
        type: 'success',
        text: data?.message || `Saved and published to the public page (version ${data?.content?.version ?? row.version + 1}).`,
      });
      setTimeout(() => setMessage(null), 4000);
    } catch (error) {
      const detail = error?.response?.data?.detail || 'Failed to save. Please try again.';
      setMessage({ type: 'error', text: String(detail) });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (slug) => {
    if (
      !window.confirm(
        `Reset ${content[slug].title} to the canonical default? This publishes immediately and is versioned in audit history.`
      )
    ) {
      return;
    }
    try {
      const { data } = await apiClient.post(`/admin/legal-content/${slug}/reset-default`);
      if (data?.content) {
        applyRow(slug, data.content);
      }
      await loadAllContent();
      setMessage({
        type: 'success',
        text: data?.message || 'Reset to canonical default and published.',
      });
    } catch (error) {
      const detail = error?.response?.data?.detail || 'Failed to reset';
      setMessage({ type: 'error', text: String(detail) });
    }
  };

  const handleSeed = async () => {
    if (
      !window.confirm(
        'Seed all legal pages from canonical published copy? Existing custom content is not overwritten.'
      )
    ) {
      return;
    }
    setSeeding(true);
    try {
      const { data } = await apiClient.post('/admin/legal-content/seed-canonical');
      await loadAllContent();
      await loadSlug(activeTab, { quiet: true });
      setMessage({
        type: 'success',
        text: data?.message || 'Canonical content seed completed.',
      });
    } catch (error) {
      const detail = error?.response?.data?.detail || 'Failed to seed canonical content';
      setMessage({ type: 'error', text: String(detail) });
    } finally {
      setSeeding(false);
    }
  };

  const updateField = (slug, field, value) => {
    setContent((prev) => ({
      ...prev,
      [slug]: { ...prev[slug], [field]: value },
    }));
  };

  const active = content[activeTab] || INITIAL_CONTENT[activeTab];
  const isEmptyEditor = (active.content || '').length < 100;

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-midnight-blue">Legal Content Management</h1>
            <p className="text-gray-600 mt-2">
              Edit legal and marketing pages. Changes publish to the public site after save. All edits are
              versioned and audited.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={loadAllContent} disabled={loading || saving || seeding}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
            <Button variant="outline" onClick={handleSeed} disabled={loading || saving || seeding}>
              <Database className="w-4 h-4 mr-2" />
              {seeding ? 'Seeding…' : 'Seed published content'}
            </Button>
          </div>
        </div>

        {loadError && (
          <Alert className="mb-6 bg-red-50 border-red-200">
            <AlertCircle className="h-4 w-4 text-red-600" />
            <AlertDescription className="text-red-700">{loadError}</AlertDescription>
          </Alert>
        )}

        {message && (
          <Alert className={`mb-6 ${message.type === 'success' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            {message.type === 'success' ? <Check className="h-4 w-4 text-green-600" /> : <AlertCircle className="h-4 w-4 text-red-600" />}
            <AlertDescription className={message.type === 'success' ? 'text-green-700' : 'text-red-700'}>
              {message.text}
            </AlertDescription>
          </Alert>
        )}

        {isEmptyEditor && !loading && (
          <Alert className="mb-6 bg-amber-50 border-amber-200">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-amber-800">
              This page has no CMS content loaded. Use <strong>Seed published content</strong> or{' '}
              <strong>Reset to Default</strong> before editing to avoid overwriting published copy with empty text.
            </AlertDescription>
          </Alert>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-7">
            {TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value} className="text-xs">
                <tab.icon className="w-4 h-4 mr-1" />
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {TABS.map((tab) => {
            const row = content[tab.value] || INITIAL_CONTENT[tab.value];
            return (
              <TabsContent key={tab.value} value={tab.value}>
                <Card>
                  <CardHeader>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <CardTitle>{row.title}</CardTitle>
                        <CardDescription>
                          Version {row.version} | Last updated: {formatUpdatedAt(row.updated_at)}
                          {loading || tabLoading ? ' · Loading…' : ''}
                        </CardDescription>
                      </div>
                      <a
                        href={LIVE_PAGE_PATHS[tab.value]}
                        target="_blank"
                        rel="noopener noreferrer"
                        data-testid={`admin-legal-live-link-${tab.value}`}
                        className="inline-flex items-center text-sm text-electric-teal hover:underline shrink-0"
                      >
                        <ExternalLink className="w-4 h-4 mr-1" />
                        View live page
                      </a>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div>
                      <label className="text-sm font-medium text-gray-700 mb-2 block">Page Title</label>
                      <Input
                        value={row.title}
                        onChange={(e) => updateField(tab.value, 'title', e.target.value)}
                        placeholder="Page title"
                        disabled={loading}
                      />
                    </div>

                    <div>
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between mb-2">
                        <label className="text-sm font-medium text-gray-700">
                          Content (Markdown supported)
                        </label>
                        <div className="flex gap-2">
                          <Button
                            type="button"
                            variant={editorMode === 'edit' && activeTab === tab.value ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => setEditorMode('edit')}
                            disabled={loading}
                            data-testid={`admin-legal-edit-btn-${tab.value}`}
                          >
                            <Pencil className="w-4 h-4 mr-1" />
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant={editorMode === 'preview' && activeTab === tab.value ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => openPreview(tab.value)}
                            disabled={loading}
                            data-testid={`admin-legal-preview-btn-${tab.value}`}
                          >
                            <Eye className="w-4 h-4 mr-1" />
                            Preview
                          </Button>
                        </div>
                      </div>

                      {editorMode === 'edit' || activeTab !== tab.value ? (
                        <>
                          <Textarea
                            value={row.content}
                            onChange={(e) => updateField(tab.value, 'content', e.target.value)}
                            placeholder="Enter legal content here..."
                            className="min-h-[400px] font-mono text-sm"
                            disabled={loading}
                          />
                          <p className="text-xs text-gray-500 mt-2">
                            {(row.content || '').length} characters
                          </p>
                        </>
                      ) : (
                        <div className="space-y-3">
                          <p className="text-xs text-gray-500">
                            Preview uses the same markdown renderer and save-time sanitisation as the public site.
                            Marketing header/footer are not shown. Use <strong>View live page</strong> to compare the
                            currently published page.
                          </p>
                          {preview.sanitizationApplied && !preview.loading && (
                            <Alert className="bg-amber-50 border-amber-200">
                              <AlertCircle className="h-4 w-4 text-amber-600" />
                              <AlertDescription className="text-amber-800">
                                Unsafe HTML was removed from your draft. The preview below matches what will be saved.
                              </AlertDescription>
                            </Alert>
                          )}
                          {preview.stale && !preview.loading && (
                            <div className="flex items-center gap-3">
                              <p className="text-xs text-amber-700">Draft changed since last preview.</p>
                              <Button type="button" variant="outline" size="sm" onClick={() => refreshPreview(tab.value)}>
                                <RefreshCw className="w-4 h-4 mr-1" />
                                Refresh preview
                              </Button>
                            </div>
                          )}
                          {preview.error && (
                            <Alert className="bg-red-50 border-red-200">
                              <AlertCircle className="h-4 w-4 text-red-600" />
                              <AlertDescription className="text-red-700">{preview.error}</AlertDescription>
                            </Alert>
                          )}
                          <div
                            className="border rounded-lg bg-white p-6 min-h-[400px]"
                            data-testid={`admin-legal-preview-pane-${tab.value}`}
                          >
                            {preview.loading && (
                              <p className="text-sm text-gray-400" aria-live="polite">
                                Generating preview…
                              </p>
                            )}
                            {!preview.loading && preview.content && (
                              <div className="max-w-4xl mx-auto">
                                <LegalContentMarkdown markdown={preview.content} />
                              </div>
                            )}
                            {!preview.loading && !preview.content && !preview.error && (
                              <p className="text-sm text-gray-500">No content to preview.</p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="flex gap-3">
                      <Button
                        onClick={() => handleSave(tab.value)}
                        disabled={saving || loading}
                        className="bg-electric-teal hover:bg-electric-teal/90"
                      >
                        <Save className="w-4 h-4 mr-2" />
                        {saving ? 'Saving...' : 'Save & Publish'}
                      </Button>

                      <Button
                        onClick={() => handleReset(tab.value)}
                        variant="outline"
                        disabled={saving || loading}
                      >
                        <RotateCcw className="w-4 h-4 mr-2" />
                        Reset to Default
                      </Button>
                    </div>

                    <div className="text-xs text-gray-500 mt-4 p-4 bg-gray-50 rounded">
                      <p className="font-semibold mb-2">Publication governance</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li>Editor loads the same governed CMS content published on the public site</li>
                        <li>Preview applies save-time sanitisation and the public markdown renderer before publish</li>
                        <li>Saving publishes to the matching public URL immediately</li>
                        <li>All edits and resets are logged with version history</li>
                        <li>Unsafe HTML/scripts are stripped on save</li>
                      </ul>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            );
          })}
        </Tabs>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminLegalContentPage;
