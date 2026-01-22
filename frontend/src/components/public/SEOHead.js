import React from 'react';
import { Helmet } from 'react-helmet-async';

/**
 * SEOHead - Manages all SEO meta tags for public pages
 * Phase 1: Best-effort SPA SEO with react-helmet-async
 */
export const SEOHead = ({
  title,
  description,
  canonicalUrl,
  ogImage = '/og-default.png',
  ogType = 'website',
  schema = null,
  noIndex = false,
}) => {
  const siteUrl = 'https://pleerity.com';
  const fullTitle = title ? `${title} | Pleerity Enterprise` : 'Pleerity Enterprise - AI-Powered Landlord Compliance';
  const fullCanonical = canonicalUrl ? `${siteUrl}${canonicalUrl}` : siteUrl;
  const fullOgImage = ogImage.startsWith('http') ? ogImage : `${siteUrl}${ogImage}`;

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
      <meta property="og:site_name" content="Pleerity Enterprise" />

      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:url" content={fullCanonical} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={fullOgImage} />

      {/* Schema.org JSON-LD */}
      {schema && (
        <script type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      )}
    </Helmet>
  );
};

// Pre-defined schemas
export const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Pleerity Enterprise Ltd",
  "url": "https://pleerity.com",
  "logo": "https://pleerity.com/logo.png",
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
      "url": "https://pleerity.com/logo.png"
    }
  }
});

export default SEOHead;
