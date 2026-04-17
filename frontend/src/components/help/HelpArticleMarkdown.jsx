import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function isExternalHref(href) {
  if (!href) return false;
  if (href.startsWith('#') || href.startsWith('/') || href.startsWith('?')) return false;
  if (/^mailto:/i.test(href) || /^tel:/i.test(href)) return false;
  return /^https?:\/\//i.test(href);
}

/**
 * Renders Help / Knowledge Base article bodies stored as Markdown.
 * Uses react-markdown + remark-gfm (no raw HTML injection).
 */
export default function HelpArticleMarkdown({ markdown, className = '' }) {
  const md = markdown ?? '';

  return (
    <div className={`help-article-markdown client-portal-prose max-w-none ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node, ...props }) => {
            void node;
            const external = isExternalHref(props.href);
            return <a {...props} {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})} />;
          },
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}
