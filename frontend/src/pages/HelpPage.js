/**
 * User Help Centre – In-app documentation for landlords (USER audience articles).
 * Uses authenticated /api/client/help/articles and /api/client/help/categories.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import client from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import { HelpCircle, Mail, Search, ArrowLeft, ExternalLink } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent } from '../components/ui/card';

export default function HelpPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const slugFromUrl = searchParams.get('article');

  const [categories, setCategories] = useState([]);
  const [articles, setArticles] = useState([]);
  const [article, setArticle] = useState(null);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [articleLoading, setArticleLoading] = useState(false);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await client.get('/client/help/categories');
      setCategories(res.data.categories || []);
    } catch (e) {
      console.error('Failed to load help categories:', e);
    }
  }, []);

  const fetchArticles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (search) params.set('search', search);
      if (categoryFilter) params.set('category', categoryFilter);
      const res = await client.get(`/client/help/articles?${params.toString()}`);
      setArticles(res.data.articles || []);
    } catch (e) {
      console.error('Failed to load help articles:', e);
      setArticles([]);
    } finally {
      setLoading(false);
    }
  }, [search, categoryFilter]);

  const fetchArticle = useCallback(async (slug) => {
    if (!slug) return;
    setArticleLoading(true);
    try {
      const res = await client.get(`/client/help/articles/${slug}`);
      setArticle(res.data);
    } catch (e) {
      console.error('Failed to load article:', e);
      setArticle(null);
    } finally {
      setArticleLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  useEffect(() => {
    if (slugFromUrl) {
      fetchArticle(slugFromUrl);
    } else {
      setArticle(null);
      fetchArticles();
    }
  }, [slugFromUrl, fetchArticle, fetchArticles]);

  const openArticle = (a) => {
    navigate(`/help?article=${encodeURIComponent(a.slug)}`);
  };

  const backToList = () => {
    navigate('/help');
    setArticle(null);
  };

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-midnight-blue mb-2 flex items-center gap-2">
        <HelpCircle className="h-7 w-7 text-electric-teal" />
        Help Centre
      </h1>
      <p className="text-gray-600 mb-6">Guides and support for Compliance Vault Pro.</p>

      {article ? (
        <div className="space-y-4">
          <Button variant="ghost" size="sm" onClick={backToList} className="gap-1">
            <ArrowLeft className="h-4 w-4" /> Back to articles
          </Button>
          {articleLoading ? (
            <div className="text-gray-500 py-8">Loading...</div>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500 mb-2">
                  {article.version && `Version ${article.version}`}
                  {article.updated_at && ` · Updated ${new Date(article.updated_at).toLocaleDateString()}`}
                </div>
                <h2 className="text-xl font-semibold text-midnight-blue mb-4">{article.title}</h2>
                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                  {article.content}
                </div>
                {article.related_articles?.length > 0 && (
                  <div className="mt-8 pt-6 border-t">
                    <h3 className="text-sm font-medium text-gray-500 mb-2">Related articles</h3>
                    <ul className="space-y-1">
                      {article.related_articles.map((r) => (
                        <li key={r.slug}>
                          <button
                            type="button"
                            onClick={() => openArticle(r)}
                            className="text-electric-teal hover:underline"
                          >
                            {r.title}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <>
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search help articles..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchArticles()}
                className="pl-10"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm min-w-[180px]"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.category_id} value={c.category_id}>
                  {c.icon} {c.name}
                </option>
              ))}
            </select>
            <Button onClick={fetchArticles}>Search</Button>
          </div>

          {loading ? (
            <div className="text-gray-500 py-8">Loading articles...</div>
          ) : articles.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-gray-500">
                No articles found. Try a different search or category.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {articles.map((a) => (
                <Card
                  key={a.article_id}
                  className="cursor-pointer hover:border-electric-teal hover:shadow-sm transition-all"
                  onClick={() => openArticle(a)}
                >
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <h3 className="font-medium text-midnight-blue">{a.title}</h3>
                        <p className="text-sm text-gray-500 mt-1 line-clamp-2">{a.excerpt}</p>
                        <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                          {categories.find((c) => c.category_id === a.category_id) && (
                            <span>
                              {categories.find((c) => c.category_id === a.category_id)?.icon}{' '}
                              {categories.find((c) => c.category_id === a.category_id)?.name}
                            </span>
                          )}
                        </div>
                      </div>
                      <ExternalLink className="h-4 w-4 text-gray-400 shrink-0" />
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <div className="mt-10 pt-8 border-t">
            <p className="text-sm font-medium text-gray-700 mb-2">Still need help?</p>
            <a
              href={`mailto:${SUPPORT_EMAIL}`}
              className="flex items-center gap-3 p-4 rounded-xl border border-gray-200 bg-white hover:border-electric-teal hover:shadow-sm transition-colors"
            >
              <Mail className="w-5 h-5 text-electric-teal" />
              <div>
                <p className="font-medium text-midnight-blue">Email support</p>
                <p className="text-sm text-gray-500">{SUPPORT_EMAIL}</p>
              </div>
              <ExternalLink className="w-4 h-4 text-gray-400 ml-auto" />
            </a>
          </div>
        </>
      )}
    </div>
  );
}
