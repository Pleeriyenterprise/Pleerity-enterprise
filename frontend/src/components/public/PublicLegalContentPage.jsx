import React, { useEffect, useState } from 'react';
import PublicLayout from './PublicLayout';
import { SEOHead } from './SEOHead';
import LegalContentMarkdown from './LegalContentMarkdown';

const API_URL = process.env.REACT_APP_BACKEND_URL;

/**
 * Public legal/marketing page backed by governed CMS with server-side canonical fallback.
 */
export default function PublicLegalContentPage({
  slug,
  seoTitle,
  seoDescription,
  canonicalUrl,
  noIndex = false,
}) {
  const [page, setPage] = useState(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch(
          `${API_URL}/api/public/legal-content/${slug}`,
          { cache: 'no-store' }
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!cancelled) {
          setPage(data);
          setLoadError(false);
        }
      } catch (err) {
        if (!cancelled) setLoadError(true);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const content = page?.content || '';
  const loading = !page && !loadError;

  return (
    <PublicLayout>
      <SEOHead
        title={seoTitle}
        description={seoDescription}
        canonicalUrl={canonicalUrl}
        noIndex={noIndex}
      />
      <section className="py-16 bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {loading && (
            <p className="text-gray-400 text-sm" aria-live="polite">
              Loading…
            </p>
          )}
          {loadError && !content && (
            <p className="text-gray-600">
              Unable to load page content. Please refresh or try again later.
            </p>
          )}
          {content ? (
            <LegalContentMarkdown markdown={content} />
          ) : null}
        </div>
      </section>
    </PublicLayout>
  );
}
