import React from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function isExternalHref(href) {
  if (!href) return false;
  if (href.startsWith('#') || href.startsWith('/') || href.startsWith('?')) return false;
  if (/^mailto:/i.test(href) || /^tel:/i.test(href)) return false;
  return /^https?:\/\//i.test(href);
}

/**
 * Renders governed legal/marketing CMS markdown on public pages.
 * No raw HTML — markdown only (react-markdown + remark-gfm).
 */
export default function LegalContentMarkdown({ markdown, className = '' }) {
  const md = markdown ?? '';

  return (
    <div className={`legal-content-markdown help-article-markdown max-w-none text-gray-700 ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node, ...props }) => {
            void node;
            return <h1 className="text-4xl font-bold text-midnight-blue mb-8" {...props} />;
          },
          h2: ({ node, ...props }) => {
            void node;
            return <h2 className="text-2xl font-bold text-midnight-blue mb-4 mt-8" {...props} />;
          },
          h3: ({ node, ...props }) => {
            void node;
            return <h3 className="text-lg font-semibold text-midnight-blue mt-4 mb-2" {...props} />;
          },
          p: ({ node, ...props }) => {
            void node;
            return <p className="mb-3 leading-relaxed" {...props} />;
          },
          ul: ({ node, ...props }) => {
            void node;
            return <ul className="list-disc pl-6 space-y-2 mb-4" {...props} />;
          },
          ol: ({ node, ...props }) => {
            void node;
            return <ol className="list-decimal pl-6 space-y-2 mb-4" {...props} />;
          },
          a: ({ node, href, children, ...props }) => {
            void node;
            if (href && href.startsWith('/') && !href.startsWith('//')) {
              return (
                <Link to={href} className="text-electric-teal hover:underline" {...props}>
                  {children}
                </Link>
              );
            }
            const external = isExternalHref(href);
            return (
              <a
                href={href}
                className="text-electric-teal hover:underline"
                {...props}
                {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              >
                {children}
              </a>
            );
          },
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}
