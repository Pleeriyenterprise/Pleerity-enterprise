/**
 * Public Knowledge Base / FAQ Page
 * 
 * Features:
 * - Search articles
 * - Browse by category
 * - View article with view count tracking
 * - Related articles
 * - CTA to chat if no answer found
 */
import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import client from '../../api/client';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent } from '../../components/ui/card';
import PublicLayout from '../../components/public/PublicLayout';
import {
  Book,
  Search,
  ChevronRight,
  Eye,
  Tag,
  ArrowLeft,
  MessageCircle,
  Clock,
  FileText,
} from 'lucide-react';

// Category icon mapping
const categoryIcons = {
  'getting-started': '🚀',
  'billing-subscriptions': '💳',
  'account-login': '🔑',
  'cvp': '🏠',
  'documents-uploads': '📄',
  'orders-delivery': '📦',
  'reports-calendar': '📊',
  'integrations': '🔗',
  'troubleshooting': '🔧',
};

export default function PublicKnowledgeBasePage() {
  const { slug } = useParams();
  const navigate = useNavigate();
  
  // If slug is provided, show article view
  if (slug) {
    return <ArticleView slug={slug} />;
  }
  
  // Otherwise show KB index
  return <KnowledgeBaseIndex />;
}

function KnowledgeBaseIndex() {
  const navigate = useNavigate();
  const [categories, setCategories] = useState([]);
  const [featured, setFeatured] = useState({ popular: [], recent: [] });
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);

  // Fetch categories and featured articles
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [catRes, featuredRes] = await Promise.all([
          client.get('/kb/categories'),
          client.get('/kb/featured'),
        ]);
        setCategories(catRes.data.categories || []);
        setFeatured(featuredRes.data || { popular: [], recent: [] });
      } catch (error) {
        console.error('Failed to load KB data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Handle search
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const response = await client.get(`/kb/articles?search=${encodeURIComponent(query)}`);
      setSearchResults(response.data.articles || []);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        handleSearch(searchQuery);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  return (
    <PublicLayout>
      <div className="min-h-screen bg-gray-50" data-testid="public-kb-page">
        {/* Hero Section */}
        <section className="bg-gradient-to-br from-midnight-blue to-slate-800 text-white py-16">
          <div className="container mx-auto px-4 text-center">
            <Book className="h-12 w-12 mx-auto mb-4 text-electric-teal" />
            <h1 className="text-4xl font-bold mb-4">Knowledge Base</h1>
            <p className="text-xl text-gray-300 mb-8 max-w-2xl mx-auto">
              Find answers to common questions and learn how to get the most out of Pleerity
            </p>
            
            {/* Search Bar */}
            <div className="max-w-xl mx-auto relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                placeholder="Search for answers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 py-6 text-lg bg-white text-gray-900 rounded-xl shadow-lg"
                data-testid="kb-search-input"
              />
            </div>
          </div>
        </section>

        <div className="container mx-auto px-4 py-12">
          {/* Search Results */}
          {searchQuery && (
            <div className="mb-12">
              <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Search className="h-5 w-5" />
                Search Results for &quot;{searchQuery}&quot;
              </h2>
              
              {searching ? (
                <div className="text-center py-8 text-gray-500">Searching...</div>
              ) : searchResults.length > 0 ? (
                <div className="grid gap-4">
                  {searchResults.map(article => (
                    <ArticleCard key={article.article_id} article={article} />
                  ))}
                </div>
              ) : (
                <Card>
                  <CardContent className="py-8 text-center">
                    <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
                    <p className="text-gray-500 mb-4">No articles found for your search</p>
                    <Button 
                      onClick={() => {
                        // Open chat widget if available
                        if (window.openSupportChat) {
                          window.openSupportChat();
                        }
                      }}
                      className="bg-electric-teal hover:bg-electric-teal/90"
                    >
                      <MessageCircle className="h-4 w-4 mr-2" />
                      Chat with Support
                    </Button>
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {/* Categories Grid */}
          {!searchQuery && (
            <>
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Browse by Category</h2>
              
              {loading ? (
                <div className="text-center py-12 text-gray-500">Loading...</div>
              ) : (
                <div className="grid md:grid-cols-3 gap-4 mb-12">
                  {categories.map(category => (
                    <Card 
                      key={category.category_id}
                      className="hover:shadow-lg transition-all cursor-pointer group"
                      onClick={() => navigate(`/support/knowledge-base?category=${category.category_id}`)}
                      data-testid={`category-${category.category_id}`}
                    >
                      <CardContent className="py-6">
                        <div className="flex items-center gap-4">
                          <span className="text-4xl">
                            {category.icon || categoryIcons[category.category_id] || '📁'}
                          </span>
                          <div className="flex-1">
                            <h3 className="font-semibold text-gray-900 group-hover:text-electric-teal transition-colors">
                              {category.name}
                            </h3>
                            <p className="text-sm text-gray-500">
                              {category.article_count || 0} articles
                            </p>
                          </div>
                          <ChevronRight className="h-5 w-5 text-gray-400 group-hover:text-electric-teal transition-colors" />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {/* Popular Articles */}
              {featured.popular?.length > 0 && (
                <div className="mb-12">
                  <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                    <Eye className="h-6 w-6 text-teal-600" />
                    Popular Articles
                  </h2>
                  <div className="grid md:grid-cols-2 gap-4">
                    {featured.popular.slice(0, 4).map(article => (
                      <ArticleCard key={article.article_id} article={article} />
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Articles */}
              {featured.recent?.length > 0 && (
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-6 flex items-center gap-2">
                    <Clock className="h-6 w-6 text-blue-600" />
                    Recently Updated
                  </h2>
                  <div className="grid md:grid-cols-2 gap-4">
                    {featured.recent.slice(0, 4).map(article => (
                      <ArticleCard key={article.article_id} article={article} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* CTA Section */}
          <div className="mt-16 bg-gradient-to-r from-teal-500 to-cyan-600 rounded-2xl p-8 text-white text-center">
            <h2 className="text-2xl font-bold mb-4">Still need help?</h2>
            <p className="text-teal-100 mb-6 max-w-xl mx-auto">
              Our support team is available 24/7 to assist you with any questions or issues
            </p>
            <Button
              size="lg"
              variant="secondary"
              className="bg-white text-teal-700 hover:bg-gray-100"
              onClick={() => {
                if (window.openSupportChat) {
                  window.openSupportChat();
                }
              }}
            >
              <MessageCircle className="h-5 w-5 mr-2" />
              Start a Conversation
            </Button>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}

function ArticleCard({ article }) {
  const navigate = useNavigate();
  
  return (
    <Card 
      className="hover:shadow-md transition-all cursor-pointer"
      onClick={() => navigate(`/support/knowledge-base/${article.slug}`)}
      data-testid={`article-card-${article.article_id}`}
    >
      <CardContent className="py-4">
        <h3 className="font-semibold text-gray-900 hover:text-electric-teal transition-colors mb-2">
          {article.title}
        </h3>
        <p className="text-sm text-gray-500 line-clamp-2 mb-3">{article.excerpt}</p>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Eye className="h-3 w-3" />
            {article.view_count || 0} views
          </span>
          {article.tags?.length > 0 && (
            <span className="flex items-center gap-1">
              <Tag className="h-3 w-3" />
              {article.tags.slice(0, 2).join(', ')}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function ArticleView({ slug }) {
  const navigate = useNavigate();
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchArticle = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await client.get(`/kb/articles/${slug}`);
        setArticle(response.data);
      } catch (err) {
        console.error('Failed to load article:', err);
        setError('Article not found');
      } finally {
        setLoading(false);
      }
    };
    fetchArticle();
  }, [slug]);

  if (loading) {
    return (
      <PublicLayout>
        <div className="container mx-auto px-4 py-12 text-center">
          Loading article...
        </div>
      </PublicLayout>
    );
  }

  if (error || !article) {
    return (
      <PublicLayout>
        <div className="container mx-auto px-4 py-12 text-center">
          <FileText className="h-16 w-16 mx-auto text-gray-300 mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Article Not Found</h1>
          <p className="text-gray-500 mb-6">The article you are looking for does not exist or has been moved.</p>
          <Button onClick={() => navigate('/support/knowledge-base')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Knowledge Base
          </Button>
        </div>
      </PublicLayout>
    );
  }

  return (
    <PublicLayout>
      <div className="min-h-screen bg-gray-50" data-testid="kb-article-view">
        {/* Breadcrumb */}
        <div className="bg-white border-b">
          <div className="container mx-auto px-4 py-4">
            <nav className="flex items-center gap-2 text-sm text-gray-500">
              <Link to="/support/knowledge-base" className="hover:text-electric-teal">
                Knowledge Base
              </Link>
              <ChevronRight className="h-4 w-4" />
              <span className="text-gray-900 truncate">{article.title}</span>
            </nav>
          </div>
        </div>

        <div className="container mx-auto px-4 py-8">
          <div className="grid lg:grid-cols-4 gap-8">
            {/* Main Content */}
            <article className="lg:col-span-3">
              <Card>
                <CardContent className="py-8 px-6 md:px-10">
                  {/* Header */}
                  <div className="mb-8">
                    <h1 className="text-3xl font-bold text-gray-900 mb-4">{article.title}</h1>
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Eye className="h-4 w-4" />
                        {article.view_count || 0} views
                      </span>
                      <span>
                        Updated: {new Date(article.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    {article.tags?.length > 0 && (
                      <div className="flex gap-2 mt-4">
                        {article.tags.map(tag => (
                          <Badge key={tag} variant="secondary">{tag}</Badge>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div 
                    className="prose prose-gray max-w-none"
                    dangerouslySetInnerHTML={{ 
                      __html: article.content
                        .replace(/\n/g, '<br />')
                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                        .replace(/\*(.*?)\*/g, '<em>$1</em>')
                        .replace(/`(.*?)`/g, '<code>$1</code>')
                    }}
                  />

                  {/* Feedback */}
                  <div className="mt-12 pt-8 border-t">
                    <p className="text-gray-600 mb-4">Was this article helpful?</p>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm">
                        👍 Yes
                      </Button>
                      <Button variant="outline" size="sm">
                        👎 No
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Back button */}
              <div className="mt-6">
                <Button
                  variant="outline"
                  onClick={() => navigate('/support/knowledge-base')}
                >
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Knowledge Base
                </Button>
              </div>
            </article>

            {/* Sidebar */}
            <aside className="lg:col-span-1">
              {/* Related Articles */}
              {article.related_articles?.length > 0 && (
                <Card className="mb-6">
                  <CardContent className="py-6">
                    <h3 className="font-semibold text-gray-900 mb-4">Related Articles</h3>
                    <div className="space-y-3">
                      {article.related_articles.map(related => (
                        <Link
                          key={related.article_id}
                          to={`/support/knowledge-base/${related.slug}`}
                          className="block text-sm text-gray-600 hover:text-electric-teal transition-colors"
                        >
                          {related.title}
                        </Link>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Need Help CTA */}
              <Card className="bg-gradient-to-br from-teal-500 to-cyan-600 text-white">
                <CardContent className="py-6 text-center">
                  <MessageCircle className="h-8 w-8 mx-auto mb-3" />
                  <h3 className="font-semibold mb-2">Need more help?</h3>
                  <p className="text-sm text-teal-100 mb-4">
                    Chat with our support team 24/7
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="bg-white text-teal-700 hover:bg-gray-100"
                    onClick={() => {
                      if (window.openSupportChat) {
                        window.openSupportChat();
                      }
                    }}
                  >
                    Start Chat
                  </Button>
                </CardContent>
              </Card>
            </aside>
          </div>
        </div>
      </div>
    </PublicLayout>
  );
}
