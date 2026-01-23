/**
 * Admin Knowledge Base Management Page
 * 
 * Features:
 * - Article CRUD with rich text editor
 * - Category management
 * - Draft/publish workflow
 * - Search analytics (top searches, no results)
 * - Soft delete
 * - Full audit logging
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
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
import { toast } from 'sonner';
import {
  Book,
  Plus,
  Edit2,
  Trash2,
  Eye,
  EyeOff,
  Search,
  Tag,
  FolderOpen,
  BarChart3,
  ArrowUpRight,
  CheckCircle,
  FileText,
  Globe,
  Save,
  XCircle,
  RefreshCw,
} from 'lucide-react';

export default function AdminKnowledgeBasePage() {
  useAuth(); // Ensure user is authenticated
  const [activeTab, setActiveTab] = useState('articles');
  
  // Articles state
  const [articles, setArticles] = useState([]);
  const [articlesLoading, setArticlesLoading] = useState(true);
  const [articleSearch, setArticleSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  
  // Categories state
  const [categories, setCategories] = useState([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  
  // Analytics state
  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(true);
  
  // Dialog state
  const [articleDialogOpen, setArticleDialogOpen] = useState(false);
  const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
  const [editingArticle, setEditingArticle] = useState(null);
  const [editingCategory, setEditingCategory] = useState(null);
  
  // Form state
  const [articleForm, setArticleForm] = useState({
    title: '',
    category_id: '',
    excerpt: '',
    content: '',
    tags: '',
    status: 'draft',
  });
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    icon: '📁',
    description: '',
    order: 0,
  });
  const [saving, setSaving] = useState(false);

  // Fetch articles
  const fetchArticles = useCallback(async () => {
    setArticlesLoading(true);
    try {
      const params = new URLSearchParams();
      if (articleSearch) params.append('search', articleSearch);
      if (statusFilter !== 'all') params.append('status', statusFilter);
      if (categoryFilter !== 'all') params.append('category', categoryFilter);
      
      const response = await client.get(`/admin/kb/articles?${params.toString()}`);
      setArticles(response.data.articles || []);
    } catch (error) {
      console.error('Failed to fetch articles:', error);
      toast.error('Failed to load articles');
    } finally {
      setArticlesLoading(false);
    }
  }, [articleSearch, statusFilter, categoryFilter]);

  // Fetch categories
  const fetchCategories = useCallback(async () => {
    setCategoriesLoading(true);
    try {
      const response = await client.get('/admin/kb/categories');
      setCategories(response.data.categories || []);
    } catch (error) {
      console.error('Failed to fetch categories:', error);
    } finally {
      setCategoriesLoading(false);
    }
  }, []);

  // Fetch analytics
  const fetchAnalytics = useCallback(async () => {
    setAnalyticsLoading(true);
    try {
      const response = await client.get('/admin/kb/analytics?days=30');
      setAnalytics(response.data);
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setAnalyticsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchArticles();
    fetchCategories();
    fetchAnalytics();
  }, [fetchArticles, fetchCategories, fetchAnalytics]);

  // Handle article form submit
  const handleArticleSubmit = async () => {
    if (!articleForm.title || !articleForm.category_id || !articleForm.excerpt || !articleForm.content) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...articleForm,
        tags: articleForm.tags ? articleForm.tags.split(',').map(t => t.trim()).filter(Boolean) : [],
      };

      if (editingArticle) {
        await client.put(`/admin/kb/articles/${editingArticle.article_id}`, payload);
        toast.success('Article updated');
      } else {
        await client.post('/admin/kb/articles', payload);
        toast.success('Article created');
      }

      setArticleDialogOpen(false);
      setEditingArticle(null);
      setArticleForm({ title: '', category_id: '', excerpt: '', content: '', tags: '', status: 'draft' });
      fetchArticles();
    } catch (error) {
      console.error('Failed to save article:', error);
      toast.error(error.response?.data?.detail || 'Failed to save article');
    } finally {
      setSaving(false);
    }
  };

  // Handle category form submit
  const handleCategorySubmit = async () => {
    if (!categoryForm.name) {
      toast.error('Category name is required');
      return;
    }

    setSaving(true);
    try {
      if (editingCategory) {
        await client.put(`/admin/kb/categories/${editingCategory.category_id}`, categoryForm);
        toast.success('Category updated');
      } else {
        await client.post('/admin/kb/categories', categoryForm);
        toast.success('Category created');
      }

      setCategoryDialogOpen(false);
      setEditingCategory(null);
      setCategoryForm({ name: '', icon: '📁', description: '', order: 0 });
      fetchCategories();
    } catch (error) {
      console.error('Failed to save category:', error);
      toast.error('Failed to save category');
    } finally {
      setSaving(false);
    }
  };

  // Publish/unpublish article
  const toggleArticleStatus = async (article) => {
    try {
      if (article.status === 'published') {
        await client.post(`/admin/kb/articles/${article.article_id}/unpublish`);
        toast.success('Article unpublished');
      } else {
        await client.post(`/admin/kb/articles/${article.article_id}/publish`);
        toast.success('Article published');
      }
      fetchArticles();
    } catch (error) {
      console.error('Failed to toggle status:', error);
      toast.error('Failed to update article status');
    }
  };

  // Delete article (soft)
  const deleteArticle = async (articleId) => {
    if (!window.confirm('Are you sure you want to delete this article?')) return;
    
    try {
      await client.delete(`/admin/kb/articles/${articleId}`);
      toast.success('Article deleted');
      fetchArticles();
    } catch (error) {
      console.error('Failed to delete article:', error);
      toast.error('Failed to delete article');
    }
  };

  // Delete category (soft)
  const deleteCategory = async (categoryId) => {
    if (!window.confirm('Are you sure you want to delete this category?')) return;
    
    try {
      await client.delete(`/admin/kb/categories/${categoryId}`);
      toast.success('Category deleted');
      fetchCategories();
    } catch (error) {
      console.error('Failed to delete category:', error);
      toast.error('Failed to delete category');
    }
  };

  // Open edit dialog for article
  const openEditArticle = async (article) => {
    try {
      const response = await client.get(`/admin/kb/articles/${article.article_id}`);
      const fullArticle = response.data;
      setEditingArticle(fullArticle);
      setArticleForm({
        title: fullArticle.title || '',
        category_id: fullArticle.category_id || '',
        excerpt: fullArticle.excerpt || '',
        content: fullArticle.content || '',
        tags: (fullArticle.tags || []).join(', '),
        status: fullArticle.status || 'draft',
      });
      setArticleDialogOpen(true);
    } catch (error) {
      console.error('Failed to load article:', error);
      toast.error('Failed to load article');
    }
  };

  // Open edit dialog for category
  const openEditCategory = (category) => {
    setEditingCategory(category);
    setCategoryForm({
      name: category.name || '',
      icon: category.icon || '📁',
      description: category.description || '',
      order: category.order || 0,
    });
    setCategoryDialogOpen(true);
  };

  return (
    <UnifiedAdminLayout>
    <div className="space-y-6" data-testid="admin-kb-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Book className="h-6 w-6 text-teal-600" />
            Knowledge Base
          </h1>
          <p className="text-gray-500 mt-1">Manage FAQ articles and categories</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => {
              fetchArticles();
              fetchCategories();
              fetchAnalytics();
            }}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Button
            onClick={() => {
              setEditingArticle(null);
              setArticleForm({ title: '', category_id: '', excerpt: '', content: '', tags: '', status: 'draft' });
              setArticleDialogOpen(true);
            }}
            className="bg-teal-600 hover:bg-teal-700"
            data-testid="create-article-btn"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Article
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="articles" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Articles
          </TabsTrigger>
          <TabsTrigger value="categories" className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            Categories
          </TabsTrigger>
          <TabsTrigger value="analytics" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            Analytics
          </TabsTrigger>
        </TabsList>

        {/* Articles Tab */}
        <TabsContent value="articles" className="space-y-4">
          {/* Filters */}
          <div className="flex gap-4 items-center flex-wrap">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search articles..."
                value={articleSearch}
                onChange={(e) => setArticleSearch(e.target.value)}
                className="pl-10"
                data-testid="search-articles-input"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="draft">Draft</SelectItem>
                <SelectItem value="published">Published</SelectItem>
              </SelectContent>
            </Select>
            <Select value={categoryFilter} onValueChange={setCategoryFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Category" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Categories</SelectItem>
                {categories.map(cat => (
                  <SelectItem key={cat.category_id} value={cat.category_id}>
                    {cat.icon} {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" onClick={fetchArticles}>
              Apply
            </Button>
          </div>

          {/* Articles List */}
          {articlesLoading ? (
            <div className="text-center py-12 text-gray-500">Loading articles...</div>
          ) : articles.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No articles found</p>
                <Button
                  variant="outline"
                  className="mt-4"
                  onClick={() => {
                    setEditingArticle(null);
                    setArticleDialogOpen(true);
                  }}
                >
                  Create your first article
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {articles.map(article => (
                <Card key={article.article_id} className="hover:shadow-md transition-shadow" data-testid={`article-${article.article_id}`}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant={article.status === 'published' ? 'default' : 'secondary'}>
                            {article.status === 'published' ? (
                              <><Globe className="h-3 w-3 mr-1" /> Published</>
                            ) : (
                              <><EyeOff className="h-3 w-3 mr-1" /> Draft</>
                            )}
                          </Badge>
                          <span className="text-xs text-gray-400">
                            {categories.find(c => c.category_id === article.category_id)?.icon}{' '}
                            {categories.find(c => c.category_id === article.category_id)?.name}
                          </span>
                        </div>
                        <h3 className="font-semibold text-gray-900">{article.title}</h3>
                        <p className="text-sm text-gray-500 mt-1 line-clamp-2">{article.excerpt}</p>
                        <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                          <span><Eye className="h-3 w-3 inline mr-1" />{article.view_count || 0} views</span>
                          <span>Updated: {new Date(article.updated_at).toLocaleDateString()}</span>
                          {article.tags?.length > 0 && (
                            <span><Tag className="h-3 w-3 inline mr-1" />{article.tags.join(', ')}</span>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-2 ml-4">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => toggleArticleStatus(article)}
                          title={article.status === 'published' ? 'Unpublish' : 'Publish'}
                        >
                          {article.status === 'published' ? (
                            <EyeOff className="h-4 w-4 text-amber-500" />
                          ) : (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          )}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditArticle(article)}
                          data-testid={`edit-article-${article.article_id}`}
                        >
                          <Edit2 className="h-4 w-4 text-blue-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteArticle(article.article_id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories" className="space-y-4">
          <div className="flex justify-end">
            <Button
              onClick={() => {
                setEditingCategory(null);
                setCategoryForm({ name: '', icon: '📁', description: '', order: 0 });
                setCategoryDialogOpen(true);
              }}
              className="bg-teal-600 hover:bg-teal-700"
              data-testid="create-category-btn"
            >
              <Plus className="h-4 w-4 mr-2" />
              New Category
            </Button>
          </div>

          {categoriesLoading ? (
            <div className="text-center py-12 text-gray-500">Loading categories...</div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {categories.map(category => (
                <Card key={category.category_id} className="hover:shadow-md transition-shadow">
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-2xl">{category.icon}</span>
                          <h3 className="font-semibold text-gray-900">{category.name}</h3>
                        </div>
                        {category.description && (
                          <p className="text-sm text-gray-500 mt-1">{category.description}</p>
                        )}
                        <p className="text-xs text-gray-400 mt-2">
                          {category.article_count || 0} articles • Order: {category.order}
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => openEditCategory(category)}
                        >
                          <Edit2 className="h-4 w-4 text-blue-500" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteCategory(category.category_id)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-4">
          {analyticsLoading ? (
            <div className="text-center py-12 text-gray-500">Loading analytics...</div>
          ) : analytics ? (
            <>
              {/* Stats Cards */}
              <div className="grid md:grid-cols-3 gap-4">
                <Card>
                  <CardContent className="py-4">
                    <div className="text-3xl font-bold text-teal-600">{analytics.stats?.total_published || 0}</div>
                    <div className="text-sm text-gray-500">Published Articles</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="py-4">
                    <div className="text-3xl font-bold text-blue-600">{analytics.stats?.total_articles || 0}</div>
                    <div className="text-sm text-gray-500">Total Articles</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="py-4">
                    <div className="text-3xl font-bold text-purple-600">{analytics.stats?.total_searches || 0}</div>
                    <div className="text-sm text-gray-500">Searches (30 days)</div>
                  </CardContent>
                </Card>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Top Viewed Articles */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Eye className="h-5 w-5 text-teal-600" />
                      Most Viewed Articles
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {analytics.top_viewed_articles?.length > 0 ? (
                      <div className="space-y-2">
                        {analytics.top_viewed_articles.map((article, idx) => (
                          <div key={article.article_id} className="flex items-center justify-between py-2 border-b last:border-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-400">#{idx + 1}</span>
                              <span className="text-sm">{article.title}</span>
                            </div>
                            <Badge variant="secondary">{article.view_count} views</Badge>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">No data yet</p>
                    )}
                  </CardContent>
                </Card>

                {/* Top Searches */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Search className="h-5 w-5 text-blue-600" />
                      Top Searches
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {analytics.top_searches?.length > 0 ? (
                      <div className="space-y-2">
                        {analytics.top_searches.slice(0, 10).map((item, idx) => (
                          <div key={item.query} className="flex items-center justify-between py-2 border-b last:border-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-400">#{idx + 1}</span>
                              <span className="text-sm">{item.query}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {!item.has_results && (
                                <XCircle className="h-4 w-4 text-red-400" title="No results" />
                              )}
                              <Badge variant="secondary">{item.count}</Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">No search data yet</p>
                    )}
                  </CardContent>
                </Card>

                {/* Searches with No Results */}
                <Card className="md:col-span-2">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <XCircle className="h-5 w-5 text-red-500" />
                      Searches with No Results
                      <Badge variant="destructive" className="ml-2">Action Needed</Badge>
                    </CardTitle>
                    <CardDescription>
                      Consider creating articles for these topics
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {analytics.searches_with_no_results?.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {analytics.searches_with_no_results.map(item => (
                          <Badge key={item.query} variant="outline" className="text-red-600 border-red-200">
                            {item.query} ({item.count})
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">All searches returned results</p>
                    )}
                  </CardContent>
                </Card>
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-gray-500">No analytics data available</div>
          )}
        </TabsContent>
      </Tabs>

      {/* Article Dialog */}
      <Dialog open={articleDialogOpen} onOpenChange={setArticleDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingArticle ? 'Edit Article' : 'Create Article'}</DialogTitle>
            <DialogDescription>
              {editingArticle ? 'Update the article details below' : 'Fill in the details to create a new KB article'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={articleForm.title}
                onChange={(e) => setArticleForm({ ...articleForm, title: e.target.value })}
                placeholder="How to reset your password"
                data-testid="article-title-input"
              />
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="category">Category *</Label>
                <Select
                  value={articleForm.category_id}
                  onValueChange={(val) => setArticleForm({ ...articleForm, category_id: val })}
                >
                  <SelectTrigger data-testid="article-category-select">
                    <SelectValue placeholder="Select category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map(cat => (
                      <SelectItem key={cat.category_id} value={cat.category_id}>
                        {cat.icon} {cat.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="status">Status</Label>
                <Select
                  value={articleForm.status}
                  onValueChange={(val) => setArticleForm({ ...articleForm, status: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="published">Published</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="excerpt">Excerpt/Summary *</Label>
              <Textarea
                id="excerpt"
                value={articleForm.excerpt}
                onChange={(e) => setArticleForm({ ...articleForm, excerpt: e.target.value })}
                placeholder="A brief summary that appears in search results..."
                rows={2}
                data-testid="article-excerpt-input"
              />
            </div>

            <div>
              <Label htmlFor="content">Content * (Markdown supported)</Label>
              <Textarea
                id="content"
                value={articleForm.content}
                onChange={(e) => setArticleForm({ ...articleForm, content: e.target.value })}
                placeholder="Full article content with Markdown formatting..."
                rows={12}
                className="font-mono text-sm"
                data-testid="article-content-input"
              />
            </div>

            <div>
              <Label htmlFor="tags">Tags (comma-separated)</Label>
              <Input
                id="tags"
                value={articleForm.tags}
                onChange={(e) => setArticleForm({ ...articleForm, tags: e.target.value })}
                placeholder="password, security, login"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setArticleDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleArticleSubmit}
              disabled={saving}
              className="bg-teal-600 hover:bg-teal-700"
              data-testid="save-article-btn"
            >
              {saving ? (
                <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Saving...</>
              ) : (
                <><Save className="h-4 w-4 mr-2" /> {editingArticle ? 'Update' : 'Create'}</>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Category Dialog */}
      <Dialog open={categoryDialogOpen} onOpenChange={setCategoryDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingCategory ? 'Edit Category' : 'Create Category'}</DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="cat-name">Name *</Label>
              <Input
                id="cat-name"
                value={categoryForm.name}
                onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                placeholder="Getting Started"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="cat-icon">Icon (emoji)</Label>
                <Input
                  id="cat-icon"
                  value={categoryForm.icon}
                  onChange={(e) => setCategoryForm({ ...categoryForm, icon: e.target.value })}
                  placeholder="🚀"
                />
              </div>
              <div>
                <Label htmlFor="cat-order">Display Order</Label>
                <Input
                  id="cat-order"
                  type="number"
                  value={categoryForm.order}
                  onChange={(e) => setCategoryForm({ ...categoryForm, order: parseInt(e.target.value) || 0 })}
                />
              </div>
            </div>

            <div>
              <Label htmlFor="cat-desc">Description</Label>
              <Textarea
                id="cat-desc"
                value={categoryForm.description}
                onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                placeholder="Optional description..."
                rows={2}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setCategoryDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCategorySubmit}
              disabled={saving}
              className="bg-teal-600 hover:bg-teal-700"
            >
              {saving ? 'Saving...' : editingCategory ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
