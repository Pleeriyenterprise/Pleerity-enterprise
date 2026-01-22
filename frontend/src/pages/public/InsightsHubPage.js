import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import PublicLayout from '../components/public/PublicLayout';
import { SEOHead } from '../components/public/SEOHead';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Search, Calendar, ArrowRight, BookOpen } from 'lucide-react';

const InsightsHubPage = () => {
  const [posts, setPosts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  // Placeholder posts for initial launch (will be replaced by API)
  const placeholderPosts = [
    {
      post_id: 'POST-001',
      slug: 'landlord-compliance-checklist-2026',
      title: 'Landlord Compliance Checklist UK (2026)',
      excerpt: 'A comprehensive guide to all the compliance requirements UK landlords need to meet in 2026.',
      category: 'landlord-compliance',
      published_at: '2026-01-15',
      featured_image: null,
    },
    {
      post_id: 'POST-002',
      slug: 'hmo-compliance-audit-what-councils-check',
      title: 'HMO Compliance Audit: What Councils Check',
      excerpt: 'Understanding what local councils look for during HMO licence inspections and compliance audits.',
      category: 'landlord-compliance',
      published_at: '2026-01-10',
      featured_image: null,
    },
    {
      post_id: 'POST-003',
      slug: 'certificates-landlords-need-scotland-england',
      title: 'What Certificates Do Landlords Need in Scotland vs England',
      excerpt: 'Key differences in compliance requirements between Scottish and English rental properties.',
      category: 'landlord-compliance',
      published_at: '2026-01-05',
      featured_image: null,
    },
    {
      post_id: 'POST-004',
      slug: 'track-eicr-gas-safety-epc-renewals',
      title: 'How to Track EICR, Gas Safety, EPC Renewals',
      excerpt: 'Best practices for managing certificate renewals across your property portfolio.',
      category: 'guides',
      published_at: '2026-01-01',
      featured_image: null,
    },
    {
      post_id: 'POST-005',
      slug: 'ai-workflow-automation-property-management',
      title: 'AI Workflow Automation in Property Management',
      excerpt: 'How artificial intelligence is transforming property management tasks and compliance tracking.',
      category: 'ai-automation',
      published_at: '2025-12-28',
      featured_image: null,
    },
    {
      post_id: 'POST-006',
      slug: 'avoid-missing-hmo-licence-renewals',
      title: 'How to Avoid Missing HMO Licence Renewals',
      excerpt: 'Tips and strategies to ensure you never miss an important HMO licence renewal deadline.',
      category: 'landlord-compliance',
      published_at: '2025-12-20',
      featured_image: null,
    },
  ];

  const categoryOptions = [
    { value: 'landlord-compliance', label: 'Landlord Compliance', count: 4 },
    { value: 'ai-automation', label: 'AI & Automation', count: 1 },
    { value: 'guides', label: 'Guides', count: 1 },
    { value: 'industry-news', label: 'Industry News', count: 0 },
  ];

  useEffect(() => {
    // Simulate API call - will be replaced with actual API
    const loadPosts = async () => {
      setIsLoading(true);
      try {
        // TODO: Replace with actual API call
        // const API_URL = process.env.REACT_APP_BACKEND_URL;
        // const response = await fetch(`${API_URL}/api/blog/posts`);
        // const data = await response.json();
        // setPosts(data.posts);
        
        // Using placeholder data for now
        setPosts(placeholderPosts);
        setCategories(categoryOptions);
      } catch (error) {
        console.error('Failed to load posts:', error);
        setPosts(placeholderPosts);
        setCategories(categoryOptions);
      } finally {
        setIsLoading(false);
      }
    };

    loadPosts();
  }, []);

  const filteredPosts = posts.filter((post) => {
    const matchesCategory = !selectedCategory || post.category === selectedCategory;
    const matchesSearch =
      !searchQuery ||
      post.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      post.excerpt.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const getCategoryLabel = (value) => {
    const category = categories.find((c) => c.value === value);
    return category?.label || value;
  };

  return (
    <PublicLayout>
      <SEOHead
        title="Insights - UK Landlord Compliance News & Guides"
        description="Expert insights on UK landlord compliance, property regulations, and HMO requirements. Stay informed with Pleerity Enterprise."
        canonicalUrl="/insights"
      />

      {/* Hero Section */}
      <section className="py-16 bg-gradient-to-b from-gray-50 to-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl sm:text-5xl font-bold text-midnight-blue mb-6">
              Insights & Resources
            </h1>
            <p className="text-xl text-gray-600 mb-8">
              Expert guides, compliance updates, and best practices for UK landlords and letting agents.
            </p>

            {/* Search */}
            <div className="relative max-w-xl mx-auto">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <Input
                type="search"
                placeholder="Search articles..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-12 pr-4 py-3 text-lg"
                data-testid="insights-search"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="py-12 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid lg:grid-cols-4 gap-8">
            {/* Sidebar - Categories */}
            <div className="lg:col-span-1">
              <div className="sticky top-24">
                <h2 className="text-lg font-semibold text-midnight-blue mb-4">Categories</h2>
                <div className="space-y-2">
                  <button
                    onClick={() => setSelectedCategory(null)}
                    className={`w-full text-left px-4 py-2 rounded-lg transition-colors ${
                      !selectedCategory
                        ? 'bg-electric-teal/10 text-electric-teal'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                    data-testid="category-all"
                  >
                    All Articles
                  </button>
                  {categories.map((category) => (
                    <button
                      key={category.value}
                      onClick={() => setSelectedCategory(category.value)}
                      className={`w-full text-left px-4 py-2 rounded-lg transition-colors flex justify-between items-center ${
                        selectedCategory === category.value
                          ? 'bg-electric-teal/10 text-electric-teal'
                          : 'text-gray-600 hover:bg-gray-100'
                      }`}
                      data-testid={`category-${category.value}`}
                    >
                      <span>{category.label}</span>
                      <span className="text-sm text-gray-400">{category.count}</span>
                    </button>
                  ))}
                </div>

                {/* CTA Card */}
                <Card className="mt-8 border-electric-teal/20 bg-electric-teal/5">
                  <CardContent className="p-6">
                    <BookOpen className="w-8 h-8 text-electric-teal mb-3" />
                    <h3 className="font-semibold text-midnight-blue mb-2">
                      Need Compliance Help?
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                      Let Compliance Vault Pro handle your compliance tracking automatically.
                    </p>
                    <Button size="sm" className="w-full bg-electric-teal hover:bg-electric-teal/90" asChild>
                      <Link to="/compliance-vault-pro">Learn More</Link>
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>

            {/* Posts Grid */}
            <div className="lg:col-span-3">
              {isLoading ? (
                <div className="grid md:grid-cols-2 gap-6">
                  {[1, 2, 3, 4].map((i) => (
                    <Card key={i} className="animate-pulse">
                      <CardContent className="p-6">
                        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
                        <div className="h-6 bg-gray-200 rounded w-3/4 mb-2" />
                        <div className="h-4 bg-gray-200 rounded w-full mb-4" />
                        <div className="h-4 bg-gray-200 rounded w-1/3" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : filteredPosts.length === 0 ? (
                <div className="text-center py-12">
                  <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-700 mb-2">No articles found</h3>
                  <p className="text-gray-500">
                    Try adjusting your search or filter criteria.
                  </p>
                </div>
              ) : (
                <div className="grid md:grid-cols-2 gap-6">
                  {filteredPosts.map((post) => (
                    <Link
                      key={post.post_id}
                      to={`/insights/${post.slug}`}
                      className="group"
                      data-testid={`post-card-${post.slug}`}
                    >
                      <Card className="h-full hover:shadow-lg transition-shadow">
                        <CardContent className="p-6">
                          <div className="flex items-center space-x-2 mb-3">
                            <Badge variant="secondary" className="text-xs">
                              {getCategoryLabel(post.category)}
                            </Badge>
                            <span className="text-xs text-gray-400 flex items-center">
                              <Calendar className="w-3 h-3 mr-1" />
                              {formatDate(post.published_at)}
                            </span>
                          </div>
                          <h3 className="text-lg font-semibold text-midnight-blue mb-2 group-hover:text-electric-teal transition-colors">
                            {post.title}
                          </h3>
                          <p className="text-gray-600 text-sm mb-4 line-clamp-2">
                            {post.excerpt}
                          </p>
                          <span className="inline-flex items-center text-electric-teal text-sm font-medium">
                            Read more
                            <ArrowRight className="w-4 h-4 ml-1 group-hover:translate-x-1 transition-transform" />
                          </span>
                        </CardContent>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Newsletter CTA */}
      <section className="py-16 bg-midnight-blue">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Stay Updated
          </h2>
          <p className="text-gray-300 mb-8">
            Get the latest compliance updates and guides delivered to your inbox.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center max-w-md mx-auto">
            <Input
              type="email"
              placeholder="Enter your email"
              className="bg-white"
            />
            <Button className="bg-electric-teal hover:bg-electric-teal/90 whitespace-nowrap">
              Subscribe
            </Button>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
};

export default InsightsHubPage;
