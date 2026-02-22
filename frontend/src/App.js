import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { AuthProvider } from './contexts/AuthContext';
import { EntitlementsProvider } from './contexts/EntitlementsContext';
import { ProtectedRoute } from './utils/ProtectedRoute';
import { EntitlementProtectedRoute } from './utils/EntitlementProtectedRoute';
import { Toaster } from './components/ui/sonner';
import TawkToWidget from './components/TawkToWidget';
import './App.css';

// Build stamp for deployment verification (set REACT_APP_BUILD_SHA in CI/CD)
if (typeof window !== 'undefined') {
  window.__CVP_BUILD_SHA = process.env.REACT_APP_BUILD_SHA || '(not set)';
}
if (process.env.REACT_APP_BUILD_SHA) {
  console.log('[CVP] Build SHA:', process.env.REACT_APP_BUILD_SHA);
}

// ClearForm - Separate Product
import ClearFormApp from './clearform/ClearFormApp';

// Public Website Pages (NEW)
import {
  HomePage,
  CVPLandingPage,
  ServicesHubPage,
  ServiceDetailPage,
  ServicesCataloguePage,
  ServiceOrderPage,
  OrderSuccessPage,
  PricingPage,
  BookingPage,
  InsightsHubPage,
  AboutPage,
  ContactPage,
  CareersPage,
  PartnershipsPage,
  TalentPoolWizard,
  PartnershipEnquiryForm,
  PrivacyPage,
  TermsPage,
  CookiePolicyPage,
  ServicesHubPageCMS,
  CategoryPageCMS,
  ServicePageCMS,
} from './pages/public';

// New public pages
import AssureStackPage from './pages/public/AssureStackPage';
import AccessibilityPage from './pages/public/AccessibilityPage';
import FAQPage from './pages/public/FAQPage';
import NewsletterPage from './pages/public/NewsletterPage';

// Auth & Onboarding pages
import PortalSelectorPage from './pages/PortalSelectorPage';
import ClientLoginPage from './pages/ClientLoginPage';
import AdminLoginPage from './pages/AdminLoginPage';
import LoginPage from './pages/LoginPage'; // Legacy - keep for backwards compatibility
import SetPasswordPage from './pages/SetPasswordPage';
import IntakePage from './pages/IntakePage';
import OnboardingStatusPage from './pages/OnboardingStatusPage';
import AdminBlogPage from './pages/AdminBlogPage';

// Checkout success redirect component
const CheckoutSuccessRedirect = () => {
  const [searchParams] = React.useState(() => new URLSearchParams(window.location.search));
  const sessionId = searchParams.get('session_id');
  
  // Extract client_id from session or redirect to onboarding
  React.useEffect(() => {
    const storedClientId = localStorage.getItem('pending_client_id');
    if (storedClientId) {
      localStorage.removeItem('pending_client_id');
      sessionStorage.setItem('pleerity_stripe_redirect', Date.now().toString());
      window.location.href = `/onboarding-status?client_id=${storedClientId}`;
    } else {
      window.location.href = '/';
    }
  }, []);
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-electric-teal mx-auto mb-4"></div>
        <p className="text-gray-600">Processing your payment...</p>
      </div>
    </div>
  );
};

// Client pages
import ClientDashboard from './pages/ClientDashboard';
import PropertiesPage from './pages/PropertiesPage';
import RequirementsPage from './pages/RequirementsPage';
import ComplianceScorePage from './pages/ComplianceScorePage';
import AssistantPage from './pages/AssistantPage';
import ProfilePage from './pages/ProfilePage';
import PropertyCreatePage from './pages/PropertyCreatePage';
import DocumentsPage from './pages/DocumentsPage';
import BulkUploadPage from './pages/BulkUploadPage';
import ReportsPage from './pages/ReportsPage';
import NotificationPreferencesPage from './pages/NotificationPreferencesPage';
import CalendarPage from './pages/CalendarPage';
import TenantDashboard from './pages/TenantDashboard';
import TenantManagementPage from './pages/TenantManagementPage';
import BulkPropertyImportPage from './pages/BulkPropertyImportPage';
import IntegrationsPage from './pages/IntegrationsPage';
import BrandingSettingsPage from './pages/BrandingSettingsPage';
import BillingPage from './pages/BillingPage';
import ClientProvideInfoPage from './pages/ClientProvideInfoPage';
import ClientOrdersPage from './pages/ClientOrdersPage';
import UnifiedIntakeWizard from './pages/UnifiedIntakeWizard';
import OrderConfirmationPage from './pages/OrderConfirmationPage';
import ClientAuditLogPage from './pages/ClientAuditLogPage';

// Admin pages
import AdminDashboard from './pages/AdminDashboard';
import AdminAssistantPage from './pages/AdminAssistantPage';
import AdminBillingPage from './pages/AdminBillingPage';
import AdminPendingPaymentsPage from './pages/AdminPendingPaymentsPage';
import AdminOrdersPage from './pages/AdminOrdersPage';
import AdminServiceCataloguePage from './pages/AdminServiceCataloguePage';
import AdminNotificationPreferencesPage from './pages/AdminNotificationPreferencesPage';
import AdminIntakeSchemaPage from './pages/AdminIntakeSchemaPage';
import AdminAnalyticsDashboard from './pages/AdminAnalyticsDashboard';
import AdminSupportPage from './pages/AdminSupportPage';
import AdminKnowledgeBasePage from './pages/AdminKnowledgeBasePage';
import AdminLegalContentPage from './pages/AdminLegalContentPage';
import AdminCannedResponsesPage from './pages/AdminCannedResponsesPage';
import AdminLeadsPage from './pages/AdminLeadsPage';
import AdminTalentPoolPage from './pages/AdminTalentPoolPage';
import AdminPartnershipEnquiriesPage from './pages/AdminPartnershipEnquiriesPage';
import AdminContactEnquiriesPage from './pages/AdminContactEnquiriesPage';
import AdminFAQPage from './pages/AdminFAQPage';
import AdminNewsletterPage from './pages/AdminNewsletterPage';
import AdminInsightsFeedbackPage from './pages/AdminInsightsFeedbackPage';
import AdminPostalTrackingPage from './pages/AdminPostalTrackingPage';
import AdminConsentDashboard from './pages/AdminConsentDashboard';
import AdminSiteBuilderPage from './pages/AdminSiteBuilderPage';
import AdminEnablementDashboard from './pages/AdminEnablementDashboard';
import AdminNotificationHealthPage from './pages/AdminNotificationHealthPage';
import AdminReportingPage from './pages/AdminReportingPage';
import AdminTeamPage from './pages/AdminTeamPage';
import AdminPromptManagerPage from './pages/AdminPromptManagerPage';
import AdminClearFormUsersPage from './pages/AdminClearFormUsersPage';
import AdminClearFormDocumentsPage from './pages/AdminClearFormDocumentsPage';
import SharedReportPage from './pages/SharedReportPage';
import PublicKnowledgeBasePage from './pages/public/PublicKnowledgeBasePage';
import CookieBanner from './components/CookieBanner';
import ErrorBoundary from './components/ErrorBoundary';
import DebugPanel from './components/DebugPanel';
import ClientPortal from './components/ClientPortal';
import SettingsLayout from './components/SettingsLayout';
import HelpPage from './pages/HelpPage';
import PropertyDetailPage from './pages/PropertyDetailPage';

function RedirectToProperty() {
  const { propertyId } = useParams();
  return <Navigate to={propertyId ? `/properties/${propertyId}` : '/properties'} replace />;
}

function App() {
  return (
    <HelmetProvider>
      <AuthProvider>
        <EntitlementsProvider>
        <BrowserRouter>
          <ErrorBoundary>
          <div className="App">
            <Routes>
              {/* ========================================
                  CLEARFORM - SEPARATE PRODUCT
                  Completely isolated from Pleerity
                  ======================================== */}
              <Route path="/clearform/*" element={<ClearFormApp />} />

              {/* ========================================
                  PUBLIC WEBSITE ROUTES (NEW)
                  No auth required, SEO-optimized
                  ======================================== */}
              <Route path="/" element={<HomePage />} />
              <Route path="/compliance-vault-pro" element={<CVPLandingPage />} />
              
              {/* CMS-Driven Marketing Pages */}
              <Route path="/services" element={<ServicesHubPageCMS />} />
              {/* Legacy route must come BEFORE dynamic routes */}
              <Route path="/services/catalogue" element={<ServicesCataloguePage />} />
              <Route path="/services/:categorySlug" element={<CategoryPageCMS />} />
              <Route path="/services/:categorySlug/:serviceSlug" element={<ServicePageCMS />} />
              
              <Route path="/order/:serviceCode" element={<ServiceOrderPage />} />
              <Route path="/order-success" element={<OrderSuccessPage />} />
              <Route path="/pricing" element={<PricingPage />} />
              <Route path="/booking" element={<BookingPage />} />
              <Route path="/insights" element={<InsightsHubPage />} />
              <Route path="/insights/:slug" element={<InsightsHubPage />} />
              <Route path="/insights/category/:category" element={<InsightsHubPage />} />
              <Route path="/about" element={<AboutPage />} />
              <Route path="/contact" element={<ContactPage />} />
              <Route path="/careers" element={<CareersPage />} />
              <Route path="/careers/talent-pool" element={<TalentPoolWizard />} />
              <Route path="/partnerships" element={<PartnershipsPage />} />
              <Route path="/partnerships/enquiry" element={<PartnershipEnquiryForm />} />
              <Route path="/legal/privacy" element={<PrivacyPage />} />
              <Route path="/legal/terms" element={<TermsPage />} />
              <Route path="/legal/cookies" element={<CookiePolicyPage />} />
              
              {/* New Marketing Pages */}
              <Route path="/products/assurestack" element={<AssureStackPage />} />
              <Route path="/accessibility" element={<AccessibilityPage />} />
              <Route path="/faq" element={<FAQPage />} />
              <Route path="/newsletter" element={<NewsletterPage />} />
              
              {/* Knowledge Base (Public) */}
              <Route path="/support/knowledge-base" element={<PublicKnowledgeBasePage />} />
              <Route path="/support/knowledge-base/:slug" element={<PublicKnowledgeBasePage />} />
              
              {/* Shared Reports (Public) */}
              <Route path="/shared/report/:shareId" element={<SharedReportPage />} />

              {/* ========================================
                  AUTH & ONBOARDING ROUTES
                  ======================================== */}
              <Route path="/login" element={<PortalSelectorPage />} />
              <Route path="/login/client" element={<ClientLoginPage />} />
              <Route path="/login/admin" element={<AdminLoginPage />} />
              <Route path="/admin/signin" element={<AdminLoginPage />} /> {/* Legacy admin route */}
              <Route path="/set-password" element={<SetPasswordPage />} />
              <Route path="/intake/start" element={<IntakePage />} />
              <Route path="/onboarding-status" element={<OnboardingStatusPage />} />
              <Route path="/checkout/success" element={<CheckoutSuccessRedirect />} />
              <Route path="/checkout/cancel" element={<Navigate to="/intake/start" replace />} />

              {/* ========================================
                  CLIENT PORTAL ROUTES (Enterprise UI)
                  /dashboard, /properties, /requirements, etc. + /app/* redirects
                  ======================================== */}
            <Route path="/dashboard" element={<ClientPortal><ClientDashboard /></ClientPortal>} />
            <Route path="/properties" element={<ClientPortal><PropertiesPage /></ClientPortal>} />
            <Route path="/properties/:propertyId" element={<ClientPortal><PropertyDetailPage /></ClientPortal>} />
            <Route path="/properties/create" element={<ClientPortal><PropertyCreatePage /></ClientPortal>} />
            <Route path="/properties/import" element={<ClientPortal><BulkPropertyImportPage /></ClientPortal>} />
            <Route path="/requirements" element={<ClientPortal><RequirementsPage /></ClientPortal>} />
            <Route path="/documents" element={<ClientPortal><DocumentsPage /></ClientPortal>} />
            <Route path="/audit-log" element={<ClientPortal><ClientAuditLogPage /></ClientPortal>} />
            <Route path="/documents/bulk-upload" element={<ClientPortal><BulkUploadPage /></ClientPortal>} />
            <Route path="/calendar" element={<ClientPortal><CalendarPage /></ClientPortal>} />
            <Route path="/reports" element={<ClientPortal><ReportsPage /></ClientPortal>} />
            <Route path="/compliance-score" element={<ClientPortal><ComplianceScorePage /></ClientPortal>} />
            <Route path="/assistant" element={<ClientPortal><AssistantPage /></ClientPortal>} />
            <Route path="/help" element={<ClientPortal><HelpPage /></ClientPortal>} />
            <Route path="/settings" element={<ClientPortal><SettingsLayout /></ClientPortal>}>
              <Route index element={<Navigate to="/settings/profile" replace />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="notifications" element={<NotificationPreferencesPage />} />
              <Route path="billing" element={<BillingPage />} />
            </Route>
            <Route path="/tenant" element={<ClientPortal><TenantDashboard /></ClientPortal>} />
            <Route path="/tenants" element={<ClientPortal><EntitlementProtectedRoute requiredFeature="tenant_portal"><TenantManagementPage /></EntitlementProtectedRoute></ClientPortal>} />
            <Route path="/integrations" element={<ClientPortal><EntitlementProtectedRoute requiredFeature="webhooks"><IntegrationsPage /></EntitlementProtectedRoute></ClientPortal>} />
            <Route path="/orders/:orderId/provide-info" element={<ClientPortal><ClientProvideInfoPage /></ClientPortal>} />
            <Route path="/orders" element={<ClientPortal><ClientOrdersPage /></ClientPortal>} />

            {/* Redirect legacy /app/* to new paths */}
            <Route path="/app/dashboard" element={<Navigate to="/dashboard" replace />} />
            <Route path="/app/assistant" element={<Navigate to="/assistant" replace />} />
            <Route path="/app/profile" element={<Navigate to="/settings/profile" replace />} />
            <Route path="/app/notifications" element={<Navigate to="/settings/notifications" replace />} />
            <Route path="/app/calendar" element={<Navigate to="/calendar" replace />} />
            <Route path="/app/properties/create" element={<Navigate to="/properties/create" replace />} />
            <Route path="/app/properties" element={<Navigate to="/properties" replace />} />
            <Route path="/app/property/:propertyId" element={<RedirectToProperty />} />
            <Route path="/app/requirements" element={<Navigate to="/requirements" replace />} />
            <Route path="/app/compliance-score" element={<Navigate to="/compliance-score" replace />} />
            <Route path="/app/documents" element={<Navigate to="/documents" replace />} />
            <Route path="/app/documents/bulk-upload" element={<Navigate to="/documents/bulk-upload" replace />} />
            <Route path="/app/audit-log" element={<Navigate to="/audit-log" replace />} />
            <Route path="/app/reports" element={<Navigate to="/reports" replace />} />
            <Route path="/app/tenant" element={<Navigate to="/tenant" replace />} />
            <Route path="/app/tenants" element={<Navigate to="/tenants" replace />} />
            <Route path="/app/properties/import" element={<Navigate to="/properties/import" replace />} />
            <Route path="/app/integrations" element={<Navigate to="/integrations" replace />} />
            <Route path="/app/billing" element={<Navigate to="/settings/billing" replace />} />
            <Route path="/app/orders/:orderId/provide-info" element={<Navigate to="/orders/:orderId/provide-info" replace />} />
            <Route path="/app/orders" element={<Navigate to="/orders" replace />} />

            {/* ========================================
                  ORDER INTAKE WIZARD (Public)
                  ======================================== */}
            <Route 
              path="/order/intake" 
              element={<UnifiedIntakeWizard />} 
            />
            <Route 
              path="/order/intake/:draftId" 
              element={<UnifiedIntakeWizard />} 
            />
            <Route 
              path="/order/confirmation" 
              element={<OrderConfirmationPage />} 
            />

            {/* ========================================
                  ADMIN PORTAL ROUTES (Protected)
                  Existing CVP functionality - DO NOT MODIFY
                  ======================================== */}
            <Route 
              path="/admin/dashboard" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/assistant" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminAssistantPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/billing" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminBillingPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/orders" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminOrdersPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/services" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminServiceCataloguePage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/blog" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminBlogPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/notifications/preferences" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminNotificationPreferencesPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/intake-schema" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminIntakeSchemaPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/intake-schema/:serviceCode" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminIntakeSchemaPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/analytics" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminAnalyticsDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/reporting" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminReportingPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/team" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminTeamPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/prompts" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminPromptManagerPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/support" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminSupportPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/knowledge-base" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminKnowledgeBasePage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/support/responses" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminCannedResponsesPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/settings/legal" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminLegalContentPage />
                </ProtectedRoute>
              } 
            />
            <Route path="/admin/leads" element={<ProtectedRoute requireAdmin><AdminLeadsPage /></ProtectedRoute>} />
            <Route path="/admin/pending-payments" element={<ProtectedRoute requireAdmin><AdminPendingPaymentsPage /></ProtectedRoute>} />
            <Route path="/admin/talent-pool" element={<ProtectedRoute requireAdmin><AdminTalentPoolPage /></ProtectedRoute>} />
            <Route path="/admin/partnership-enquiries" element={<ProtectedRoute requireAdmin><AdminPartnershipEnquiriesPage /></ProtectedRoute>} />
            <Route path="/admin/inbox/enquiries" element={<ProtectedRoute requireAdmin><AdminContactEnquiriesPage /></ProtectedRoute>} />
            <Route path="/admin/content/faqs" element={<ProtectedRoute requireAdmin><AdminFAQPage /></ProtectedRoute>} />
            <Route path="/admin/marketing/newsletter" element={<ProtectedRoute requireAdmin><AdminNewsletterPage /></ProtectedRoute>} />
            <Route path="/admin/content/feedback" element={<ProtectedRoute requireAdmin><AdminInsightsFeedbackPage /></ProtectedRoute>} />
            <Route path="/admin/postal-tracking" element={<ProtectedRoute requireAdmin><AdminPostalTrackingPage /></ProtectedRoute>} />
            <Route 
              path="/admin/privacy/consent" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminConsentDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/site-builder" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminSiteBuilderPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/enablement" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminEnablementDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/notification-health" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminNotificationHealthPage />
                </ProtectedRoute>
              } 
            />

            {/* ClearForm Admin Routes */}
            <Route 
              path="/admin/clearform/users" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminClearFormUsersPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/clearform/documents" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminClearFormDocumentsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/clearform/organizations" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminClearFormUsersPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/clearform/document-types" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminClearFormDocumentsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/clearform/audit" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminClearFormUsersPage />
                </ProtectedRoute>
              } 
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster />
          <TawkToWidget />
          <CookieBanner />
          <DebugPanel />
        </div>
          </ErrorBoundary>
      </BrowserRouter>
        </EntitlementsProvider>
    </AuthProvider>
    </HelmetProvider>
  );
}

export default App;
