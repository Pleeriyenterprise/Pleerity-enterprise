import React, { useState, useEffect, useCallback } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import PublicLayout from '../../components/public/PublicLayout';
import { SEOHead } from '../../components/public/SEOHead';
import UKLandlordComplianceChecklist2026 from './articles/UKLandlordComplianceChecklist2026';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { 
  Search, 
  Calendar, 
  ArrowRight, 
  BookOpen, 
  Tag, 
  Clock,
  User,
  ChevronLeft,
  Loader2,
  FileText,
  Eye,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Static foundational guides — no empty state; SEO and product-aligned
const FEATURED_GUIDES = [
  {
    slug: 'uk-landlord-compliance-checklist-2026',
    title: 'UK Landlord Compliance Checklist (2026 Guide)',
    excerpt: 'A practical checklist for UK landlords: certificates, deadlines, and documentation.',
    section: 'UK Landlord Compliance Tracking',
  },
  {
    slug: 'gas-safety-certificate-expiry-tracking-guide',
    title: 'Gas Safety Certificate Expiry Tracking Guide',
    excerpt: 'What landlords must track for gas safety certificates and renewals.',
    section: 'Gas Safety & EICR Expiry Reminders',
  },
  {
    slug: 'understanding-eicr-expiry-reminders',
    title: 'Understanding EICR Expiry & Reminders',
    excerpt: 'EICR requirements, expiry cycles, and how to stay on top of renewals.',
    section: 'Gas Safety & EICR Expiry Reminders',
  },
  {
    slug: 'hmo-compliance-tracking-uk-explained',
    title: 'HMO Compliance Tracking UK Explained',
    excerpt: 'HMO-specific compliance obligations and how to track them in one place.',
    section: 'HMO Compliance Tracking UK',
  },
];

// Static article content for foundational guides (when no CMS post)
const getStaticArticle = (slug) => {
  const map = {
    // uk-landlord-compliance-checklist-2026 uses dedicated UKLandlordComplianceChecklist2026 component
    'gas-safety-certificate-expiry-tracking-guide': {
      title: 'Gas Safety Certificate Expiry Tracking Guide',
      excerpt: 'What landlords must track for gas safety certificates and renewals.',
      content: 'Gas safety certificates must be renewed every 12 months. Landlords need to schedule inspections, keep records, and ensure tenants receive copies. This guide explains what to track and when. Track this automatically with Compliance Vault Pro.',
    },
    'understanding-eicr-expiry-reminders': {
      title: 'Understanding EICR Expiry & Reminders',
      excerpt: 'EICR requirements, expiry cycles, and how to stay on top of renewals.',
      content: 'Electrical safety (EICR) requirements apply to most rented properties. Certificates are valid for set periods and must be renewed. This guide covers expiry cycles and how to avoid missed deadlines. Track this automatically with Compliance Vault Pro.',
    },
    'hmo-compliance-tracking-uk-explained': {
      title: 'HMO Compliance Tracking UK Explained',
      excerpt: 'HMO-specific compliance obligations and how to track them in one place.',
      content: 'HMO landlords face additional compliance obligations: licensing, fire safety, room sizes, and more. This guide explains what to track and how to keep everything in one place. Track this automatically with Compliance Vault Pro.',
    },
  };
  return map[slug] || null;
};

const InsightsHubPage = () => {
  const { slug } = useParams();
  const [searchParams] = useSearchParams();
  const categoryParam = searchParams.get('category');
  const tagParam = searchParams.get('tag');
  
  const [posts, setPosts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [popularTags, setPopularTags] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(categoryParam || null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  
  // Single post view
  const [singlePost, setSinglePost] = useState(null);
  const [postLoading, setPostLoading] = useState(false);
  
  // Format date
  const formatDate = (dateString) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };
  
  // Fetch posts
  const fetchPosts = useCallback(async () => {
    try {
      setIsLoading(true);
      let url = `${API_URL}/api/blog/posts?page=${page}&page_size=9`;
      
      if (selectedCategory) {
        url += `&category=${encodeURIComponent(selectedCategory)}`;
      }
      if (tagParam) {
        url += `&tag=${encodeURIComponent(tagParam)}`;
      }
      if (searchQuery) {
        url += `&search=${encodeURIComponent(searchQuery)}`;
      }
      
      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setPosts(data.posts || []);
        setTotalPages(data.total_pages || 1);
      }
    } catch (err) {
      console.error('Failed to fetch posts:', err);
    } finally {
      setIsLoading(false);
    }
  }, [page, selectedCategory, tagParam, searchQuery]);
  
  // Fetch categories
  const fetchCategories = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/blog/categories`);
      if (response.ok) {
        const data = await response.json();
        setCategories(data.categories || []);
      }
    } catch (err) {
      console.error('Failed to fetch categories:', err);
    }
  }, []);
  
  // Fetch popular tags
  const fetchTags = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/blog/tags/popular?limit=15`);
      if (response.ok) {
        const data = await response.json();
        setPopularTags(data.tags || []);
      }
    } catch (err) {
      console.error('Failed to fetch tags:', err);
    }
  }, []);
  
  // Fetch single post
  const fetchSinglePost = useCallback(async (postSlug) => {
    try {
      setPostLoading(true);
      const response = await fetch(`${API_URL}/api/blog/posts/${postSlug}`);
      if (response.ok) {
        const data = await response.json();
        setSinglePost(data.post);
      } else {
        setSinglePost(null);
      }
    } catch (err) {
      console.error('Failed to fetch post:', err);
      setSinglePost(null);
    } finally {
      setPostLoading(false);
    }
  }, []);
  
  // Initial data fetch
  useEffect(() => {
    if (slug) {
      fetchSinglePost(slug);
    } else {
      fetchPosts();
    }
    fetchCategories();
    fetchTags();
  }, [slug, fetchPosts, fetchSinglePost, fetchCategories, fetchTags]);
  
  // Render Markdown-like content (simple)
  const renderContent = (content) => {
    if (!content) return null;
    
    // Split by double newlines for paragraphs
    const paragraphs = content.split(/\n\n+/);
    
    return paragraphs.map((para, i) => {
      // Check for headers
      if (para.startsWith('# ')) {
        return <h1 key={i} className="text-3xl font-bold mt-8 mb-4">{para.slice(2)}</h1>;
      }
      if (para.startsWith('## ')) {
        return <h2 key={i} className="text-2xl font-bold mt-6 mb-3">{para.slice(3)}</h2>;
      }
      if (para.startsWith('### ')) {
        return <h3 key={i} className="text-xl font-bold mt-5 mb-2">{para.slice(4)}</h3>;
      }
      
      // Check for lists
      if (para.startsWith('- ')) {
        const items = para.split('\n').filter(line => line.startsWith('- '));
        return (
          <ul key={i} className="list-disc list-inside my-4 space-y-2">
            {items.map((item, j) => (
              <li key={j} className="text-gray-700">{item.slice(2)}</li>
            ))}
          </ul>
        );
      }
      
      // Regular paragraph with basic formatting
      let text = para;
      // Bold
      text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      // Italic
      text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
      
      return (
        <p 
          key={i} 
          className="text-gray-700 leading-relaxed my-4"
          dangerouslySetInnerHTML={{ __html: text }}
        />
      );
    });
  };
  
  // Single Post View
  if (slug && !postLoading && singlePost) {
    return (
      <PublicLayout>
        <SEOHead
          title={`${singlePost.meta_title || singlePost.title} - Pleerity Insights`}
          description={singlePost.meta_description || singlePost.excerpt}
          canonicalUrl={`/insights/${slug}`}
        />
        
        <article className="py-12">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            {/* Back link */}
            <Link 
              to="/insights" 
              className="inline-flex items-center text-electric-teal hover:underline mb-8"
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back to Insights
            </Link>
            
            {/* Header */}
            <header className="mb-8">
              <Badge className="mb-4">{singlePost.category}</Badge>
              <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-4">
                {singlePost.title}
              </h1>
              
              {singlePost.excerpt && (
                <p className="text-xl text-gray-600 mb-6">
                  {singlePost.excerpt}
                </p>
              )}
              
              <div className="flex items-center gap-4 text-sm text-gray-500">
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  {formatDate(singlePost.published_at)}
                </div>
                <div className="flex items-center gap-1">
                  <User className="h-4 w-4" />
                  {singlePost.author_name || 'Pleerity Team'}
                </div>
                {singlePost.view_count > 0 && (
                  <div className="flex items-center gap-1">
                    <Eye className="h-4 w-4" />
                    {singlePost.view_count} views
                  </div>
                )}
              </div>
            </header>
            
            {/* Featured Image */}
            {singlePost.featured_image && (
              <img
                src={singlePost.featured_image}
                alt={singlePost.title}
                className="w-full h-64 sm:h-96 object-cover rounded-xl mb-8"
              />
            )}
            
            {/* Content */}
            <div className="prose prose-lg max-w-none">
              {renderContent(singlePost.content)}
            </div>
            
            {/* Tags */}
            {singlePost.tags && singlePost.tags.length > 0 && (
              <div className="mt-12 pt-8 border-t">
                <div className="flex items-center gap-2 flex-wrap">
                  <Tag className="h-4 w-4 text-gray-400" />
                  {singlePost.tags.map(tag => (
                    <Link
                      key={tag}
                      to={`/insights?tag=${tag}`}
                      className="text-sm text-electric-teal hover:underline"
                    >
                      #{tag}
                    </Link>
                  ))}
                </div>
              </div>
            )}
            
            {/* CTA */}
            <div className="mt-12 bg-midnight-blue rounded-xl p-8 text-center">
              <h3 className="text-2xl font-bold text-white mb-4">
                Need Help with Compliance?
              </h3>
              <p className="text-gray-300 mb-6">
                Explore our services or get in touch with our team.
              </p>
              <div className="flex justify-center gap-4">
                <Button asChild className="bg-electric-teal hover:bg-electric-teal/90">
                  <Link to="/services/catalogue">Browse Services</Link>
                </Button>
                <Button asChild variant="outline" className="border-white text-white hover:bg-white hover:text-midnight-blue">
                  <Link to="/contact">Contact Us</Link>
                </Button>
              </div>
            </div>
          </div>
        </article>
      </PublicLayout>
    );
  }
  
  // Loading state for single post
  if (slug && postLoading) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-electric-teal" />
        </div>
      </PublicLayout>
    );
  }
  
  // Full long-form article (dedicated component)
  if (slug === 'uk-landlord-compliance-checklist-2026' && !postLoading && !singlePost) {
    return <UKLandlordComplianceChecklist2026 />;
  }

  // Static article fallback for other foundational guides
  const staticArticle = slug ? getStaticArticle(slug) : null;
  if (slug && !postLoading && !singlePost && staticArticle) {
    return (
      <PublicLayout>
        <SEOHead
          title={`${staticArticle.title} - Pleerity Insights`}
          description={staticArticle.excerpt}
          canonicalUrl={`/insights/${slug}`}
        />
        <article className="py-12">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <Link to="/insights" className="inline-flex items-center text-electric-teal hover:underline mb-8">
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back to Insights
            </Link>
            <header className="mb-8">
              <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-4">{staticArticle.title}</h1>
              <p className="text-xl text-gray-600">{staticArticle.excerpt}</p>
            </header>
            <div className="prose prose-lg max-w-none text-gray-700 space-y-4">
              {staticArticle.content.split(/(?<=\.) /).filter(Boolean).map((para, i) => (
                <p key={i}>{para.trim()}</p>
              ))}
            </div>
            <div className="mt-12 bg-midnight-blue rounded-xl p-8 text-center">
              <h3 className="text-2xl font-bold text-white mb-4">Track this automatically with Compliance Vault Pro</h3>
              <Button asChild className="bg-electric-teal hover:bg-electric-teal/90">
                <Link to="/intake/start">Start Free Trial <ArrowRight className="w-4 h-4 ml-2 inline" /></Link>
              </Button>
            </div>
          </div>
        </article>
      </PublicLayout>
    );
  }

  // Post not found (unknown slug)
  if (slug && !postLoading && !singlePost) {
    return (
      <PublicLayout>
        <div className="min-h-screen flex flex-col items-center justify-center">
          <FileText className="h-16 w-16 text-gray-300 mb-4" />
          <h1 className="text-2xl font-bold text-gray-600 mb-2">Post Not Found</h1>
          <p className="text-gray-500 mb-6">The article you&apos;re looking for doesn&apos;t exist.</p>
          <Button asChild>
            <Link to="/insights">Browse All Insights</Link>
          </Button>
        </div>
      </PublicLayout>
    );
  }
  
  // Blog Listing View — resource hub with featured guides, lead magnet, CTA
  const sectionGroups = FEATURED_GUIDES.reduce((acc, guide) => {
    if (!acc[guide.section]) acc[guide.section] = [];
    acc[guide.section].push(guide);
    return acc;
  }, {});

  return (
    <PublicLayout>
      <SEOHead
        title="Insights for UK Landlords | Compliance Tracking & Guides | Pleerity"
        description="Practical guides on UK landlord compliance tracking, gas safety and EICR expiry reminders, HMO compliance UK. Free landlord compliance checklist."
        canonicalUrl="/insights"
      />
      
      {/* Hero */}
      <section className="py-16 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-3xl mx-auto">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Insights for UK Landlords & Property Managers
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Practical guides on compliance tracking, certificates, and portfolio management.
            </p>
            <div className="relative max-w-xl mx-auto">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                placeholder="Search articles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 h-12 text-lg"
                data-testid="search-insights"
              />
            </div>
          </div>
        </div>
      </section>
      
      {/* Featured Guides — grouped by SEO section headings */}
      <section className="py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col lg:flex-row gap-8">
            <div className="lg:w-2/3">
              {Object.entries(sectionGroups).map(([sectionTitle, guides]) => (
                <div key={sectionTitle} className="mb-6">
                  <h2 className="text-2xl font-bold text-midnight-blue mb-4 pb-2 border-b-2 border-electric-teal">
                    {sectionTitle}
                  </h2>
                  <div className="grid md:grid-cols-2 gap-6">
                    {guides.map((guide) => (
                      <Card
                        key={guide.slug}
                        className="overflow-hidden hover:shadow-lg transition-shadow group border-2 border-transparent hover:border-electric-teal"
                        data-testid={`guide-card-${guide.slug}`}
                      >
                        <CardContent className="p-6">
                          <h3 className="text-xl font-bold text-midnight-blue mb-2 line-clamp-2 group-hover:text-electric-teal transition-colors">
                            <Link to={`/insights/${guide.slug}`}>{guide.title}</Link>
                          </h3>
                          <p className="text-gray-600 text-sm line-clamp-2 mb-4">{guide.excerpt}</p>
                          <Link
                            to={`/insights/${guide.slug}`}
                            className="text-electric-teal font-medium text-sm inline-flex items-center gap-1 hover:underline"
                          >
                            Read guide
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}

              {/* API posts when available (below featured guides) */}
              {!isLoading && posts.length > 0 && (
                <div className="mt-12">
                  <h2 className="text-2xl font-bold text-midnight-blue mb-4">More articles</h2>
                  <div className="grid md:grid-cols-2 gap-6">
                    {posts.map(post => (
                      <Card key={post.id} className="overflow-hidden hover:shadow-lg transition-shadow group">
                        {post.featured_image && (
                          <img src={post.featured_image} alt={post.title} className="w-full h-48 object-cover" />
                        )}
                        <CardContent className="p-6">
                          <Badge variant="outline" className="mb-3">{post.category}</Badge>
                          <h3 className="text-xl font-bold text-midnight-blue mb-2 line-clamp-2">
                            <Link to={`/insights/${post.slug}`}>{post.title}</Link>
                          </h3>
                          <p className="text-gray-600 text-sm line-clamp-2 mb-4">{post.excerpt}</p>
                          <Link to={`/insights/${post.slug}`} className="text-electric-teal font-medium text-sm flex items-center gap-1 hover:underline">
                            Read more <ArrowRight className="h-3 w-3" />
                          </Link>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                  {totalPages > 1 && (
                    <div className="flex justify-center gap-2 mt-6">
                      <Button variant="outline" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Previous</Button>
                      <span className="flex items-center px-4 text-gray-500">Page {page} of {totalPages}</span>
                      <Button variant="outline" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Next</Button>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            <aside className="lg:w-1/3">
              {popularTags.length > 0 && (
                <Card className="mb-6">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      Popular Tags
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {popularTags.map(tag => (
                        <Link key={tag.name} to={`/insights?tag=${tag.name}`} className="text-sm px-3 py-1 bg-gray-100 rounded-full hover:bg-electric-teal hover:text-white transition-colors">
                          #{tag.name} ({tag.count})
                        </Link>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              <Card className="bg-midnight-blue text-white mb-6">
                <CardHeader>
                  <CardTitle className="text-lg">Stay Updated</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-300 text-sm mb-4">
                    Get the latest property insights delivered to your inbox.
                  </p>
                  <Button asChild className="w-full bg-electric-teal hover:bg-electric-teal/90">
                    <Link to="/newsletter">Subscribe</Link>
                  </Button>
                </CardContent>
              </Card>
            </aside>
          </div>
        </div>
      </section>

      {/* Lead magnet */}
      <section className="py-12 bg-gray-50">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-2xl font-bold text-midnight-blue mb-4">
            Download Free Landlord Compliance Checklist (PDF)
          </h2>
          <p className="text-gray-600 mb-6">
            Get our one-page checklist for UK landlord compliance. We&apos;ll send the PDF to your inbox.
          </p>
          <form
            className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto"
            onSubmit={(e) => e.preventDefault()}
          >
            <Input
              type="email"
              placeholder="Your email"
              className="flex-1 h-11"
              required
            />
            <Button type="submit" className="bg-electric-teal hover:bg-electric-teal/90">
              Send me the checklist
            </Button>
          </form>
        </div>
      </section>

      {/* CTA block */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to Track Compliance Automatically?
          </h2>
          <Button size="lg" className="bg-electric-teal hover:bg-electric-teal/90 text-white" asChild>
            <Link to="/intake/start">
              Start Free Trial
              <ArrowRight className="w-5 h-5 ml-2 inline" />
            </Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
};

export default InsightsHubPage;
