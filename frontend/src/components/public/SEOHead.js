import React from 'react';
import { Helmet } from 'react-helmet-async';
import { SITE_URL, SCHEMA_LOGO_URL, branding } from '../../config/branding';

/**
 * SEOHead - Manages all SEO meta tags for public pages
 * Phase 1: Best-effort SPA SEO with react-helmet-async
 */
export const SEOHead = ({
  title,
  description,
  canonicalUrl,
  ogImage,
  ogType = 'website',
  schema = null,
  noIndex = false,
}) => {
  const defaultOgImage = (typeof ogImage === 'string' && ogImage) ? ogImage : branding.ogImageUrlFallback;
  const fullTitle = title ? `${title} | ${branding.companyName}` : `${branding.companyName} - ${branding.tagline}`;
  const fullCanonical = canonicalUrl ? `${SITE_URL}${canonicalUrl}` : SITE_URL;
  const fullOgImage = defaultOgImage.startsWith('http') ? defaultOgImage : `${SITE_URL}${defaultOgImage}`;

  return (
    <Helmet>
      {/* Primary Meta Tags */}
      <title>{fullTitle}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={fullCanonical} />

      {noIndex && <meta name="robots" content="noindex, nofollow" />}

      {/* Open Graph / Facebook */}
      <meta property="og:type" content={ogType} />
      <meta property="og:url" content={fullCanonical} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={fullOgImage} />
      <meta property="og:site_name" content={branding.companyName} />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:url" content={fullCanonical} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={fullOgImage} />

      {/* Schema.org JSON-LD (single object or array of schemas) */}
      {schema && (Array.isArray(schema) ? schema : [schema]).map((s, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(s)}
        </script>
      ))}
    </Helmet>
  );
};

// Pre-defined schemas
export const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Pleerity Enterprise Ltd",
  "url": "https://pleerity.com",
  "logo": SCHEMA_LOGO_URL,
  "description": "AI-powered compliance and workflow automation for UK landlords and letting agents.",
  "address": {
    "@type": "PostalAddress",
    "addressCountry": "GB"
  },
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "email": "info@pleerityenterprise.co.uk"
  }
};

export const productSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Compliance Vault Pro",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "description": "The all-in-one compliance platform for UK landlords. Track certificates, automate reminders, and stay compliant.",
  "offers": {
    "@type": "AggregateOffer",
    "lowPrice": "19",
    "highPrice": "79",
    "priceCurrency": "GBP",
    "offerCount": 3
  }
};

export const createServiceSchema = (name, description) => ({
  "@context": "https://schema.org",
  "@type": "Service",
  "name": name,
  "description": description,
  "provider": {
    "@type": "Organization",
    "name": "Pleerity Enterprise Ltd"
  },
  "areaServed": {
    "@type": "Country",
    "name": "United Kingdom"
  }
});

export const createArticleSchema = (title, excerpt, publishedAt, updatedAt) => ({
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": title,
  "description": excerpt,
  "datePublished": publishedAt,
  "dateModified": updatedAt || publishedAt,
  "author": {
    "@type": "Organization",
    "name": "Pleerity Enterprise"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Pleerity Enterprise Ltd",
    "logo": {
      "@type": "ImageObject",
      "url": SCHEMA_LOGO_URL
    }
  }
});

/** FAQ schema for rich results (array of { question, answer }) */
export const createFAQSchema = (faqs) => ({
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": (faqs || []).map(({ question, answer }) => ({
    "@type": "Question",
    "name": question,
    "acceptedAnswer": {
      "@type": "Answer",
      "text": answer
    }
  }))
});

export default SEOHead;
