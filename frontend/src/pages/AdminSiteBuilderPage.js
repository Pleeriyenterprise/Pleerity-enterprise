/**
 * Admin Site Builder CMS
 * 
 * Features:
 * - Page list with status filtering
 * - Schema-driven block editor
 * - Media library with upload
 * - Revision history with rollback
 * - Draft/Publish workflow
 * - SEO metadata management
 */
import React, { useState, useEffect, useCallback } from 'react';
import client from '../api/client';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Badge } from '../components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Switch } from '../components/ui/switch';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import {
  FileText,
  Plus,
  Search,
  Eye,
  EyeOff,
  Edit,
  Trash2,
  Save,
  Upload,
  Image,
  Video,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  History,
  RotateCcw,
  Globe,
  Rocket,
  Layout,
  Type,
  MessageSquare,
  DollarSign,
  HelpCircle,
  Users,
  Star,
  BarChart3,
  Grid,
  Layers,
  Settings,
  X,
  GripVertical,
  ExternalLink,
  Copy,
  Cpu,
  BarChart2,
  ShieldCheck,
  Home,
  Check,
  Pencil,
} from 'lucide-react';

// Block type icons mapping
const BLOCK_ICONS = {
  HERO: Layout,
  TEXT_BLOCK: Type,
  CTA: Rocket,
  FAQ: HelpCircle,
  PRICING_TABLE: DollarSign,
  FEATURES_GRID: Grid,
  TESTIMONIALS: Star,
  IMAGE_GALLERY: Image,
  VIDEO_EMBED: Video,
  CONTACT_FORM: MessageSquare,
  STATS_BAR: BarChart3,
  LOGO_CLOUD: Layers,
  TEAM_SECTION: Users,
  SPACER: Layers,
};

// Block type labels
const BLOCK_LABELS = {
  HERO: 'Hero Section',
  TEXT_BLOCK: 'Text Block',
  CTA: 'Call to Action',
  FAQ: 'FAQ Section',
  PRICING_TABLE: 'Pricing Table',
  FEATURES_GRID: 'Features Grid',
  TESTIMONIALS: 'Testimonials',
  IMAGE_GALLERY: 'Image Gallery',
  VIDEO_EMBED: 'Video Embed',
  CONTACT_FORM: 'Contact Form',
  STATS_BAR: 'Statistics Bar',
  LOGO_CLOUD: 'Logo Cloud',
  TEAM_SECTION: 'Team Section',
  SPACER: 'Spacer',
};

// Status badge colors
const STATUS_COLORS = {
  DRAFT: 'bg-yellow-100 text-yellow-800',
  PUBLISHED: 'bg-green-100 text-green-800',
  ARCHIVED: 'bg-gray-100 text-gray-600',
};

// ============================================
// Page List Component
// ============================================

const PageList = ({ pages, onSelect, onCreate, onRefresh, loading }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newPage, setNewPage] = useState({ slug: '', title: '', description: '' });
  const [creating, setCreating] = useState(false);

  const filteredPages = pages.filter(page => {
    const matchesSearch = page.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         page.slug.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || page.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleCreate = async () => {
    if (!newPage.slug || !newPage.title) {
      toast.error('Slug and title are required');
      return;
    }
    
    setCreating(true);
    try {
      await client.post('/admin/cms/pages', newPage);
      toast.success('Page created successfully');
      setShowCreateDialog(false);
      setNewPage({ slug: '', title: '', description: '' });
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create page');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">CMS Pages</h2>
          <p className="text-sm text-gray-500">Manage public-facing website pages</p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)} data-testid="create-page-btn">
          <Plus className="w-4 h-4 mr-2" />
          New Page
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            placeholder="Search pages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
            data-testid="page-search-input"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="status-filter">
            <SelectValue placeholder="All Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="DRAFT">Draft</SelectItem>
            <SelectItem value="PUBLISHED">Published</SelectItem>
            <SelectItem value="ARCHIVED">Archived</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Page Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredPages.map(page => (
          <Card
            key={page.page_id}
            className="cursor-pointer hover:border-electric-teal transition-colors"
            onClick={() => onSelect(page)}
            data-testid={`page-card-${page.slug}`}
          >
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <CardTitle className="text-base truncate">{page.title}</CardTitle>
                  <CardDescription className="text-xs mt-1">/{page.slug}</CardDescription>
                </div>
                <Badge className={STATUS_COLORS[page.status]}>{page.status}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500 line-clamp-2">
                {page.description || 'No description'}
              </p>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-400">
                <span>{page.blocks?.length || 0} blocks</span>
                <span>v{page.current_version}</span>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredPages.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No pages found</p>
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Page</DialogTitle>
            <DialogDescription>Add a new CMS-managed page to your website.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="slug">URL Slug *</Label>
              <Input
                id="slug"
                placeholder="e.g., about-us"
                value={newPage.slug}
                onChange={(e) => setNewPage({ ...newPage, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                data-testid="new-page-slug"
              />
              <p className="text-xs text-gray-500 mt-1">Only lowercase letters, numbers, and hyphens</p>
            </div>
            <div>
              <Label htmlFor="title">Page Title *</Label>
              <Input
                id="title"
                placeholder="e.g., About Us"
                value={newPage.title}
                onChange={(e) => setNewPage({ ...newPage, title: e.target.value })}
                data-testid="new-page-title"
              />
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                placeholder="Brief description of the page"
                value={newPage.description}
                onChange={(e) => setNewPage({ ...newPage, description: e.target.value })}
                rows={3}
                data-testid="new-page-description"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={creating} data-testid="confirm-create-page">
              {creating ? 'Creating...' : 'Create Page'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// ============================================
// Block Editor Component
// ============================================

const BlockEditor = ({ block, onUpdate, onDelete, onMoveUp, onMoveDown, isFirst, isLast }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(block.content);
  const Icon = BLOCK_ICONS[block.block_type] || FileText;

  const handleSave = () => {
    onUpdate({ content });
    setEditing(false);
    toast.success('Block updated');
  };

  const renderContentEditor = () => {
    switch (block.block_type) {
      case 'HERO':
        return (
          <div className="space-y-3">
            <div>
              <Label>Headline</Label>
              <Input
                value={content.headline || ''}
                onChange={(e) => setContent({ ...content, headline: e.target.value })}
              />
            </div>
            <div>
              <Label>Subheadline</Label>
              <Textarea
                value={content.subheadline || ''}
                onChange={(e) => setContent({ ...content, subheadline: e.target.value })}
                rows={2}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>CTA Text</Label>
                <Input
                  value={content.cta_text || ''}
                  onChange={(e) => setContent({ ...content, cta_text: e.target.value })}
                />
              </div>
              <div>
                <Label>CTA Link</Label>
                <Input
                  value={content.cta_link || ''}
                  onChange={(e) => setContent({ ...content, cta_link: e.target.value })}
                />
              </div>
            </div>
          </div>
        );
      
      case 'TEXT_BLOCK':
        return (
          <div className="space-y-3">
            <div>
              <Label>Title</Label>
              <Input
                value={content.title || ''}
                onChange={(e) => setContent({ ...content, title: e.target.value })}
              />
            </div>
            <div>
              <Label>Body</Label>
              <Textarea
                value={content.body || ''}
                onChange={(e) => setContent({ ...content, body: e.target.value })}
                rows={5}
              />
            </div>
          </div>
        );
      
      case 'CTA':
        return (
          <div className="space-y-3">
            <div>
              <Label>Headline</Label>
              <Input
                value={content.headline || ''}
                onChange={(e) => setContent({ ...content, headline: e.target.value })}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={content.description || ''}
                onChange={(e) => setContent({ ...content, description: e.target.value })}
                rows={2}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Button Text</Label>
                <Input
                  value={content.button_text || ''}
                  onChange={(e) => setContent({ ...content, button_text: e.target.value })}
                />
              </div>
              <div>
                <Label>Button Link</Label>
                <Input
                  value={content.button_link || ''}
                  onChange={(e) => setContent({ ...content, button_link: e.target.value })}
                />
              </div>
            </div>
          </div>
        );
      
      case 'VIDEO_EMBED':
        return (
          <div className="space-y-3">
            <div>
              <Label>Video URL (YouTube or Vimeo only)</Label>
              <Input
                value={content.video_url || ''}
                onChange={(e) => setContent({ ...content, video_url: e.target.value })}
                placeholder="https://youtube.com/watch?v=..."
              />
            </div>
            <div>
              <Label>Caption</Label>
              <Input
                value={content.caption || ''}
                onChange={(e) => setContent({ ...content, caption: e.target.value })}
              />
            </div>
          </div>
        );
      
      default:
        return (
          <div className="p-4 bg-gray-50 rounded-lg">
            <pre className="text-xs overflow-auto max-h-40">
              {JSON.stringify(content, null, 2)}
            </pre>
          </div>
        );
    }
  };

  return (
    <Card className={`${!block.visible ? 'opacity-60' : ''}`} data-testid={`block-${block.block_id}`}>
      <CardHeader className="py-3 px-4">
        <div className="flex items-center gap-3">
          <GripVertical className="w-4 h-4 text-gray-400 cursor-grab" />
          <Icon className="w-4 h-4 text-electric-teal" />
          <span className="font-medium text-sm flex-1">{BLOCK_LABELS[block.block_type]}</span>
          
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onUpdate({ visible: !block.visible })}
              title={block.visible ? 'Hide block' : 'Show block'}
            >
              {block.visible ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
            </Button>
            <Button variant="ghost" size="sm" onClick={onMoveUp} disabled={isFirst}>
              <ChevronUp className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={onMoveDown} disabled={isLast}>
              <ChevronDown className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setEditing(!editing)}>
              <Edit className="w-4 h-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={onDelete} className="text-red-500 hover:text-red-600">
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      
      {editing && (
        <CardContent className="border-t pt-4">
          {renderContentEditor()}
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
            <Button size="sm" onClick={handleSave}>
              <Save className="w-4 h-4 mr-1" />
              Save
            </Button>
          </div>
        </CardContent>
      )}
    </Card>
  );
};

// ============================================
// Page Editor Component
// ============================================

const PageEditor = ({ page, onBack, onRefresh }) => {
  const [pageData, setPageData] = useState(page);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showAddBlock, setShowAddBlock] = useState(false);
  const [showRevisions, setShowRevisions] = useState(false);
  const [revisions, setRevisions] = useState([]);
  const [loadingRevisions, setLoadingRevisions] = useState(false);
  const [editingMeta, setEditingMeta] = useState(false);

  const fetchPage = useCallback(async () => {
    try {
      const res = await client.get(`/admin/cms/pages/${page.page_id}`);
      setPageData(res.data);
    } catch (err) {
      toast.error('Failed to refresh page');
    }
  }, [page.page_id]);

  const fetchRevisions = async () => {
    setLoadingRevisions(true);
    try {
      const res = await client.get(`/admin/cms/pages/${page.page_id}/revisions`);
      setRevisions(res.data.revisions);
    } catch (err) {
      toast.error('Failed to load revisions');
    } finally {
      setLoadingRevisions(false);
    }
  };

  useEffect(() => {
    if (showRevisions) {
      fetchRevisions();
    }
  }, [showRevisions, page.page_id]);

  const handleAddBlock = async (blockType) => {
    try {
      const defaultContent = getDefaultBlockContent(blockType);
      await client.post(`/admin/cms/pages/${page.page_id}/blocks`, {
        block_type: blockType,
        content: defaultContent,
      });
      toast.success('Block added');
      setShowAddBlock(false);
      fetchPage();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add block');
    }
  };

  const handleUpdateBlock = async (blockId, updates) => {
    try {
      await client.put(`/admin/cms/pages/${page.page_id}/blocks/${blockId}`, updates);
      fetchPage();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update block');
    }
  };

  const handleDeleteBlock = async (blockId) => {
    if (!window.confirm('Delete this block?')) return;
    try {
      await client.delete(`/admin/cms/pages/${page.page_id}/blocks/${blockId}`);
      toast.success('Block deleted');
      fetchPage();
    } catch (err) {
      toast.error('Failed to delete block');
    }
  };

  const handleMoveBlock = async (blockId, direction) => {
    const blocks = [...pageData.blocks].sort((a, b) => a.order - b.order);
    const idx = blocks.findIndex(b => b.block_id === blockId);
    if (idx === -1) return;
    
    const newIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= blocks.length) return;
    
    const newOrder = blocks.map(b => b.block_id);
    [newOrder[idx], newOrder[newIdx]] = [newOrder[newIdx], newOrder[idx]];
    
    try {
      await client.put(`/admin/cms/pages/${page.page_id}/blocks/reorder`, {
        block_order: newOrder,
      });
      fetchPage();
    } catch (err) {
      toast.error('Failed to reorder blocks');
    }
  };

  const handlePublish = async () => {
    setPublishing(true);
    try {
      await client.post(`/admin/cms/pages/${page.page_id}/publish`, {
        notes: 'Published from admin console',
      });
      toast.success('Page published successfully!');
      fetchPage();
      onRefresh();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to publish');
    } finally {
      setPublishing(false);
    }
  };

  const handleRollback = async (revisionId) => {
    if (!window.confirm('Rollback to this version? This will overwrite current draft.')) return;
    try {
      await client.post(`/admin/cms/pages/${page.page_id}/rollback`, {
        revision_id: revisionId,
        notes: 'Rolled back from admin console',
      });
      toast.success('Page rolled back');
      setShowRevisions(false);
      fetchPage();
    } catch (err) {
      toast.error('Failed to rollback');
    }
  };

  const handleSaveMeta = async () => {
    setSaving(true);
    try {
      await client.put(`/admin/cms/pages/${page.page_id}`, {
        title: pageData.title,
        description: pageData.description,
      });
      toast.success('Page details saved');
      setEditingMeta(false);
      fetchPage();
    } catch (err) {
      toast.error('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const sortedBlocks = [...(pageData.blocks || [])].sort((a, b) => a.order - b.order);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="outline" onClick={onBack} data-testid="back-to-pages">
            <X className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div>
            <h2 className="text-xl font-semibold">{pageData.title}</h2>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Globe className="w-3 h-3" />
              /{pageData.slug}
              <Badge className={STATUS_COLORS[pageData.status]}>{pageData.status}</Badge>
              <span>v{pageData.current_version}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setShowRevisions(true)} data-testid="show-revisions">
            <History className="w-4 h-4 mr-2" />
            History
          </Button>
          <Button variant="outline" onClick={() => setEditingMeta(true)}>
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </Button>
          <Button
            onClick={handlePublish}
            disabled={publishing || pageData.status === 'PUBLISHED'}
            className="bg-green-600 hover:bg-green-700"
            data-testid="publish-page"
          >
            <Rocket className="w-4 h-4 mr-2" />
            {publishing ? 'Publishing...' : 'Publish'}
          </Button>
        </div>
      </div>

      {/* Block List */}
      <Card>
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Content Blocks</CardTitle>
            <Button size="sm" onClick={() => setShowAddBlock(true)} data-testid="add-block-btn">
              <Plus className="w-4 h-4 mr-1" />
              Add Block
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-4 space-y-3">
          {sortedBlocks.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Layers className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No blocks yet. Add your first block to get started.</p>
            </div>
          ) : (
            sortedBlocks.map((block, idx) => (
              <BlockEditor
                key={block.block_id}
                block={block}
                onUpdate={(updates) => handleUpdateBlock(block.block_id, updates)}
                onDelete={() => handleDeleteBlock(block.block_id)}
                onMoveUp={() => handleMoveBlock(block.block_id, 'up')}
                onMoveDown={() => handleMoveBlock(block.block_id, 'down')}
                isFirst={idx === 0}
                isLast={idx === sortedBlocks.length - 1}
              />
            ))
          )}
        </CardContent>
      </Card>

      {/* Add Block Dialog */}
      <Dialog open={showAddBlock} onOpenChange={setShowAddBlock}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Add Content Block</DialogTitle>
            <DialogDescription>Choose a block type to add to your page.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-3 gap-3 py-4">
            {Object.entries(BLOCK_LABELS).map(([type, label]) => {
              const Icon = BLOCK_ICONS[type] || FileText;
              return (
                <button
                  key={type}
                  onClick={() => handleAddBlock(type)}
                  className="flex flex-col items-center gap-2 p-4 border rounded-lg hover:border-electric-teal hover:bg-electric-teal/5 transition-colors"
                  data-testid={`add-block-${type}`}
                >
                  <Icon className="w-6 h-6 text-electric-teal" />
                  <span className="text-sm font-medium">{label}</span>
                </button>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>

      {/* Revisions Dialog */}
      <Dialog open={showRevisions} onOpenChange={setShowRevisions}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Revision History</DialogTitle>
            <DialogDescription>View and restore previous versions of this page.</DialogDescription>
          </DialogHeader>
          <div className="py-4 max-h-96 overflow-y-auto">
            {loadingRevisions ? (
              <div className="text-center py-8">
                <RefreshCw className="w-6 h-6 animate-spin mx-auto text-gray-400" />
              </div>
            ) : revisions.length === 0 ? (
              <div className="text-center py-8 text-gray-500">
                <History className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No published versions yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                {revisions.map(rev => (
                  <div
                    key={rev.revision_id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div>
                      <div className="font-medium">Version {rev.version}</div>
                      <div className="text-sm text-gray-500">
                        {new Date(rev.published_at).toLocaleString()}
                      </div>
                      {rev.notes && (
                        <div className="text-xs text-gray-400 mt-1">{rev.notes}</div>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleRollback(rev.revision_id)}
                    >
                      <RotateCcw className="w-4 h-4 mr-1" />
                      Restore
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Settings Dialog */}
      <Dialog open={editingMeta} onOpenChange={setEditingMeta}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Page Settings</DialogTitle>
            <DialogDescription>Edit page title, description, and SEO metadata.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Page Title</Label>
              <Input
                value={pageData.title}
                onChange={(e) => setPageData({ ...pageData, title: e.target.value })}
              />
            </div>
            <div>
              <Label>Description</Label>
              <Textarea
                value={pageData.description || ''}
                onChange={(e) => setPageData({ ...pageData, description: e.target.value })}
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingMeta(false)}>Cancel</Button>
            <Button onClick={handleSaveMeta} disabled={saving}>
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

// Helper: Get default content for block types
const getDefaultBlockContent = (blockType) => {
  switch (blockType) {
    case 'HERO':
      return { headline: 'Your Headline Here', subheadline: 'Add a compelling subheadline', cta_text: 'Get Started', cta_link: '/' };
    case 'TEXT_BLOCK':
      return { title: '', body: 'Enter your content here...' };
    case 'CTA':
      return { headline: 'Ready to Get Started?', button_text: 'Contact Us', button_link: '/contact' };
    case 'FAQ':
      return { title: 'Frequently Asked Questions', items: [{ question: 'Your question here?', answer: 'Your answer here.' }] };
    case 'VIDEO_EMBED':
      return { video_url: '', caption: '' };
    case 'SPACER':
      return { height: 'md' };
    default:
      return {};
  }
};

// ============================================
// Main Component
// ============================================

const AdminSiteBuilderPage = () => {
  const [activeTab, setActiveTab] = useState('pages');
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPage, setSelectedPage] = useState(null);

  const fetchPages = useCallback(async () => {
    setLoading(true);
    try {
      const res = await client.get('/admin/cms/pages');
      setPages(res.data.pages);
    } catch (err) {
      toast.error('Failed to load pages');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPages();
  }, [fetchPages]);

  return (
    <UnifiedAdminLayout>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900" data-testid="site-builder-title">
            Site Builder
          </h1>
          <p className="text-gray-500 mt-1">Manage your public website content with the CMS</p>
        </div>

        {/* Main Content */}
        {selectedPage ? (
          <PageEditor
            page={selectedPage}
            onBack={() => setSelectedPage(null)}
            onRefresh={fetchPages}
          />
        ) : (
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="pages" data-testid="tab-pages">
                <FileText className="w-4 h-4 mr-2" />
                Pages
              </TabsTrigger>
              <TabsTrigger value="marketing" data-testid="tab-marketing">
                <Globe className="w-4 h-4 mr-2" />
                Marketing Website
              </TabsTrigger>
              <TabsTrigger value="media" data-testid="tab-media">
                <Image className="w-4 h-4 mr-2" />
                Media Library
              </TabsTrigger>
            </TabsList>

            <TabsContent value="pages" className="mt-6">
              <PageList
                pages={pages}
                onSelect={setSelectedPage}
                onCreate={fetchPages}
                onRefresh={fetchPages}
                loading={loading}
              />
            </TabsContent>

            <TabsContent value="marketing" className="mt-6">
              <MarketingPages onSelectPage={setSelectedPage} />
            </TabsContent>

            <TabsContent value="media" className="mt-6">
              <MediaLibrary />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </UnifiedAdminLayout>
  );
};

// ============================================
// Marketing Pages Component
// ============================================

const CATEGORY_ICONS = {
  'ai-automation': Cpu,
  'market-research': BarChart2,
  'compliance-audits': ShieldCheck,
  'document-packs': FileText,
};

const MarketingPages = ({ onSelectPage }) => {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState({});
  const [filter, setFilter] = useState('all');
  const [expandedCategories, setExpandedCategories] = useState({});

  const fetchPages = async () => {
    setLoading(true);
    try {
      const res = await client.get('/admin/cms/marketing/pages');
      setPages(res.data.pages || []);
      setCategories(res.data.categories || {});
    } catch (err) {
      toast.error('Failed to load marketing pages');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPages();
  }, []);

  const toggleCategory = (slug) => {
    setExpandedCategories(prev => ({
      ...prev,
      [slug]: !prev[slug]
    }));
  };

  const handlePublish = async (pageId) => {
    try {
      await client.post(`/admin/cms/marketing/pages/${pageId}/publish`);
      toast.success('Page published');
      fetchPages();
    } catch (err) {
      toast.error('Failed to publish page');
    }
  };

  const handleUnpublish = async (pageId) => {
    try {
      await client.post(`/admin/cms/marketing/pages/${pageId}/unpublish`);
      toast.success('Page unpublished');
      fetchPages();
    } catch (err) {
      toast.error('Failed to unpublish page');
    }
  };

  const handleToggleVisibility = async (pageId, currentValue) => {
    try {
      await client.put(`/admin/cms/marketing/pages/${pageId}/visibility?visible=${!currentValue}`);
      toast.success('Visibility updated');
      fetchPages();
    } catch (err) {
      toast.error('Failed to update visibility');
    }
  };

  // Group pages by type
  const hubPage = pages.find(p => p.page_type === 'HUB');
  const categoryPages = pages.filter(p => p.page_type === 'CATEGORY');
  const servicePages = pages.filter(p => p.page_type === 'SERVICE');

  // Group services by category
  const servicesByCategory = servicePages.reduce((acc, page) => {
    const cat = page.category_slug || 'uncategorized';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(page);
    return acc;
  }, {});

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{pages.length}</div>
            <div className="text-sm text-gray-500">Total Pages</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-green-600">
              {pages.filter(p => p.status === 'PUBLISHED').length}
            </div>
            <div className="text-sm text-gray-500">Published</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold text-amber-600">
              {pages.filter(p => p.status === 'DRAFT').length}
            </div>
            <div className="text-sm text-gray-500">Drafts</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="text-2xl font-bold">{Object.keys(categories).length}</div>
            <div className="text-sm text-gray-500">Categories</div>
          </CardContent>
        </Card>
      </div>

      {/* Hub Page */}
      {hubPage && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center">
                <Home className="w-5 h-5 mr-2" />
                Services Hub
              </CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant={hubPage.status === 'PUBLISHED' ? 'default' : 'secondary'}>
                  {hubPage.status}
                </Badge>
                <Button size="sm" variant="outline" onClick={() => onSelectPage(hubPage)}>
                  <Pencil className="w-4 h-4 mr-1" /> Edit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => window.open('/services', '_blank')}
                >
                  <ExternalLink className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600">{hubPage.subtitle || 'Main services landing page'}</p>
            <p className="text-xs text-gray-400 mt-2">Path: {hubPage.full_path}</p>
          </CardContent>
        </Card>
      )}

      {/* Categories & Services */}
      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Categories & Services</h3>
        
        {categoryPages.map(catPage => {
          const catSlug = catPage.slug;
          const catConfig = categories[catSlug];
          const Icon = CATEGORY_ICONS[catSlug] || FileText;
          const services = servicesByCategory[catSlug] || [];
          const isExpanded = expandedCategories[catSlug] !== false;

          return (
            <Card key={catPage.page_id}>
              <CardHeader className="cursor-pointer" onClick={() => toggleCategory(catSlug)}>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center text-base">
                    <Icon className="w-5 h-5 mr-2 text-electric-teal" />
                    {catPage.title}
                    <Badge variant="outline" className="ml-2">{services.length} services</Badge>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant={catPage.status === 'PUBLISHED' ? 'default' : 'secondary'}>
                      {catPage.status}
                    </Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => { e.stopPropagation(); onSelectPage(catPage); }}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <ChevronDown className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                  </div>
                </div>
              </CardHeader>
              
              {isExpanded && services.length > 0 && (
                <CardContent className="pt-0">
                  <div className="border-t pt-4 space-y-2">
                    {services.map(service => (
                      <div
                        key={service.page_id}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${service.status === 'PUBLISHED' ? 'bg-green-500' : 'bg-amber-500'}`} />
                          <div>
                            <p className="font-medium text-sm">{service.title}</p>
                            <p className="text-xs text-gray-500">{service.full_path}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleToggleVisibility(service.page_id, service.visible_in_nav)}
                            title={service.visible_in_nav ? 'Hide from nav' : 'Show in nav'}
                          >
                            {service.visible_in_nav ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
                          </Button>
                          {service.status === 'DRAFT' ? (
                            <Button size="sm" variant="ghost" onClick={() => handlePublish(service.page_id)}>
                              <Check className="w-4 h-4 text-green-600" />
                            </Button>
                          ) : (
                            <Button size="sm" variant="ghost" onClick={() => handleUnpublish(service.page_id)}>
                              <X className="w-4 h-4 text-amber-600" />
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" onClick={() => onSelectPage(service)}>
                            <Pencil className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => window.open(service.full_path, '_blank')}
                          >
                            <ExternalLink className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
};

// ============================================
// Media Library Component
// ============================================

const MediaLibrary = () => {
  const [media, setMedia] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchMedia = async () => {
    setLoading(true);
    try {
      const res = await client.get('/admin/cms/media');
      setMedia(res.data.media);
    } catch (err) {
      toast.error('Failed to load media');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
  }, []);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('alt_text', file.name);

    setUploading(true);
    try {
      await client.post('/admin/cms/media/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      toast.success('File uploaded');
      fetchMedia();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (mediaId) => {
    if (!window.confirm('Delete this media file?')) return;
    try {
      await client.delete(`/admin/cms/media/${mediaId}`);
      toast.success('Media deleted');
      fetchMedia();
    } catch (err) {
      toast.error('Failed to delete');
    }
  };

  const filteredMedia = media.filter(m =>
    m.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (m.alt_text || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Media Library</h2>
          <p className="text-sm text-gray-500">Upload and manage images for your CMS pages</p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search media..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-64"
          />
          <label>
            <input
              type="file"
              accept="image/*"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
            <Button asChild disabled={uploading}>
              <span>
                <Upload className="w-4 h-4 mr-2" />
                {uploading ? 'Uploading...' : 'Upload'}
              </span>
            </Button>
          </label>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400" />
        </div>
      ) : filteredMedia.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Image className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No media files found</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {filteredMedia.map(item => (
            <Card key={item.media_id} className="overflow-hidden group">
              <div className="aspect-square bg-gray-100 relative">
                <img
                  src={item.file_url}
                  alt={item.alt_text || item.file_name}
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => navigator.clipboard.writeText(item.file_url)}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleDelete(item.media_id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
              <CardContent className="p-2">
                <p className="text-xs truncate">{item.file_name}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default AdminSiteBuilderPage;
