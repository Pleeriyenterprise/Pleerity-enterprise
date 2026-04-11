/**
 * User Help Centre – In-app documentation for landlords (USER audience articles).
 * Uses authenticated /api/client/help/articles and /api/client/help/categories.
 * Includes doc-grounded Help Assistant (Ask a question) – answers from published articles only.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import client from '../api/client';
import { SUPPORT_EMAIL } from '../config';
import { HelpCircle, Mail, Search, ArrowLeft, ExternalLink, MessageCircle, ThumbsUp, ThumbsDown } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent } from '../components/ui/card';
import { buildSafeQueryPath } from '../utils/clientPortalNavigation';
import { PortalFilterStack, PortalLoadingPanel } from '../components/client/ClientPortalPatterns';
import { getHelpArticleFallback } from '../content/helpArticleFallbacks';

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

  // Help Assistant (doc-grounded ask)
  const [askQuery, setAskQuery] = useState('');
  const [askLoading, setAskLoading] = useState(false);
  const [askResult, setAskResult] = useState(null);
  const [feedbackSent, setFeedbackSent] = useState(false);

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
    setArticle(null);
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
    navigate(buildSafeQueryPath('/help', { article: a?.slug }));
  };

  const backToList = () => {
    if (window.history.length > 2) {
      navigate(-1);
    } else {
      navigate('/help');
      setArticle(null);
    }
  };

  const handleAskSubmit = async (e) => {
    e?.preventDefault();
    const q = (askQuery || '').trim();
    if (!q || askLoading) return;
    setAskLoading(true);
    setAskResult(null);
    setFeedbackSent(false);
    try {
      const res = await client.post('/client/help/query', { query: q });
      setAskResult(res.data);
    } catch (err) {
      setAskResult({
        answer: 'Sorry, the help assistant is temporarily unavailable. Try browsing the articles below or email support.',
        sources: [],
        grounded: false,
      });
    } finally {
      setAskLoading(false);
    }
  };

  const handleFeedback = async (helpful) => {
    if (!askResult || feedbackSent) return;
    try {
      await client.post('/client/help/feedback', {
        query: askQuery.trim(),
        answer: askResult.answer,
        helpful,
        source_article_ids: (askResult.sources || []).map((s) => s.articleId),
      });
      setFeedbackSent(true);
    } catch {
      // ignore
    }
  };

  const fallbackArticle = slugFromUrl ? getHelpArticleFallback(slugFromUrl) : null;
  const resolvedArticle = articleLoading ? null : article || fallbackArticle;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-midnight-blue mb-2 flex items-center gap-2">
        <HelpCircle className="h-7 w-7 text-electric-teal" />
        Help Centre
      </h1>
      <p className="text-gray-600 mb-6">Guides and support for Compliance Vault Pro.</p>

      {slugFromUrl ? (
        <div className="space-y-4">
          <Button variant="ghost" size="sm" onClick={backToList} className="gap-1">
            <ArrowLeft className="h-4 w-4" /> Back to articles
          </Button>
          {articleLoading ? (
            <PortalLoadingPanel message="Loading article…" />
          ) : resolvedArticle ? (
            <Card>
              <CardContent className="pt-6">
                {article && (article.version || article.updated_at) ? (
                  <div className="text-sm text-gray-500 mb-2">
                    {article.version && `Version ${article.version}`}
                    {article.updated_at && ` · Updated ${new Date(article.updated_at).toLocaleDateString()}`}
                  </div>
                ) : null}
                <h2 className="text-xl font-semibold text-midnight-blue mb-4">{resolvedArticle.title}</h2>
                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                  {resolvedArticle.content}
                </div>
                {article?.related_articles?.length > 0 && (
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
          ) : (
            <Card>
              <CardContent className="py-8 space-y-4">
                <p className="text-midnight-blue font-medium">This help article could not be loaded.</p>
                <p className="text-sm text-gray-600">
                  It may not be published on your environment yet. Open the full Help Centre and use search for &quot;Today&quot; or
                  &quot;inbox&quot;.
                </p>
                <Button type="button" className="bg-electric-teal hover:bg-teal-600" onClick={() => navigate('/help')}>
                  Browse all articles
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      ) : (
        <>
          {/* Help Assistant: ask a question (doc-grounded only) */}
          <Card className="mb-6 border-electric-teal/30 bg-gray-50/50">
            <CardContent className="pt-6">
              <h2 className="text-base font-semibold text-midnight-blue mb-2 flex items-center gap-2">
                <MessageCircle className="h-4 w-4 text-electric-teal" />
                Ask a question
              </h2>
              <p className="text-sm text-gray-600 mb-3">
                Answers are based only on published help articles. No account data is used.
              </p>
              <form onSubmit={handleAskSubmit} className="flex flex-col sm:flex-row gap-2">
                <Input
                  placeholder="e.g. How do I upload a certificate?"
                  value={askQuery}
                  onChange={(e) => setAskQuery(e.target.value)}
                  maxLength={500}
                  className="flex-1 min-h-11"
                  disabled={askLoading}
                />
                <Button type="submit" disabled={!askQuery.trim() || askLoading} className="bg-electric-teal hover:bg-teal-600 min-h-11 w-full sm:w-auto shrink-0">
                  {askLoading ? 'Searching...' : 'Search'}
                </Button>
              </form>
              {askResult && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{askResult.answer}</p>
                  {askResult.sources?.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-gray-500 mb-1">Related articles</p>
                      <ul className="space-y-1">
                        {askResult.sources.map((s) => (
                          <li key={s.articleId}>
                            <button
                              type="button"
                              onClick={() => navigate(buildSafeQueryPath('/help', { article: s.slug }))}
                              className="text-sm text-electric-teal hover:underline"
                            >
                              {s.title}
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {!feedbackSent ? (
                    <div className="mt-3 flex items-center gap-2 text-sm text-gray-500">
                      <span>Was this helpful?</span>
                      <Button type="button" variant="ghost" size="sm" onClick={() => handleFeedback(true)} className="h-8 gap-1">
                        <ThumbsUp className="h-3.5 w-3.5" /> Yes
                      </Button>
                      <Button type="button" variant="ghost" size="sm" onClick={() => handleFeedback(false)} className="h-8 gap-1">
                        <ThumbsDown className="h-3.5 w-3.5" /> No
                      </Button>
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-gray-500">Thanks for your feedback.</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          <PortalFilterStack className="mb-6">
            <div className="relative flex-1 w-full">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              <Input
                placeholder="Search help articles..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && fetchArticles()}
                className="pl-10 min-h-11 w-full"
              />
            </div>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="border rounded-md px-3 py-2 text-sm w-full md:min-w-[180px] min-h-11"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.category_id} value={c.category_id}>
                  {c.icon} {c.name}
                </option>
              ))}
            </select>
            <Button className="min-h-11 w-full md:w-auto" onClick={fetchArticles}>Search</Button>
          </PortalFilterStack>

          {loading ? (
            <PortalLoadingPanel message="Loading articles…" />
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
