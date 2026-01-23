import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './utils/ProtectedRoute';
import { Toaster } from './components/ui/sonner';
import TawkToWidget from './components/TawkToWidget';
import './App.css';

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
  PrivacyPage,
  TermsPage,
} from './pages/public';

// Auth & Onboarding pages
import LoginPage from './pages/LoginPage';
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
    // For now, redirect to a generic success page
    // The webhook will handle the actual provisioning
    const storedClientId = localStorage.getItem('pending_client_id');
    if (storedClientId) {
      localStorage.removeItem('pending_client_id');
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

// Admin pages
import AdminDashboard from './pages/AdminDashboard';
import AdminAssistantPage from './pages/AdminAssistantPage';
import AdminBillingPage from './pages/AdminBillingPage';
import AdminOrdersPage from './pages/AdminOrdersPage';
import AdminServiceCataloguePage from './pages/AdminServiceCataloguePage';
import AdminNotificationPreferencesPage from './pages/AdminNotificationPreferencesPage';
import AdminIntakeSchemaPage from './pages/AdminIntakeSchemaPage';
import AdminAnalyticsDashboard from './pages/AdminAnalyticsDashboard';
import AdminSupportPage from './pages/AdminSupportPage';
import AdminKnowledgeBasePage from './pages/AdminKnowledgeBasePage';
import AdminCannedResponsesPage from './pages/AdminCannedResponsesPage';
import AdminLeadsPage from './pages/AdminLeadsPage';
import AdminPostalTrackingPage from './pages/AdminPostalTrackingPage';
import AdminConsentDashboard from './pages/AdminConsentDashboard';
import AdminSiteBuilderPage from './pages/AdminSiteBuilderPage';
import AdminEnablementDashboard from './pages/AdminEnablementDashboard';
import AdminReportingPage from './pages/AdminReportingPage';
import PublicKnowledgeBasePage from './pages/public/PublicKnowledgeBasePage';
import CookieBanner from './components/CookieBanner';

function App() {
  return (
    <HelmetProvider>
      <AuthProvider>
        <BrowserRouter>
          <div className="App">
            <Routes>
              {/* ========================================
                  PUBLIC WEBSITE ROUTES (NEW)
                  No auth required, SEO-optimized
                  ======================================== */}
              <Route path="/" element={<HomePage />} />
              <Route path="/compliance-vault-pro" element={<CVPLandingPage />} />
              <Route path="/services" element={<ServicesHubPage />} />
              <Route path="/services/catalogue" element={<ServicesCataloguePage />} />
              <Route path="/services/:serviceSlug" element={<ServiceDetailPage />} />
              <Route path="/services/compliance-audits/hmo" element={<ServiceDetailPage />} />
              <Route path="/services/compliance-audits/full" element={<ServiceDetailPage />} />
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
              <Route path="/partnerships" element={<PartnershipsPage />} />
              <Route path="/legal/privacy" element={<PrivacyPage />} />
              <Route path="/legal/terms" element={<TermsPage />} />
              
              {/* Knowledge Base (Public) */}
              <Route path="/support/knowledge-base" element={<PublicKnowledgeBasePage />} />
              <Route path="/support/knowledge-base/:slug" element={<PublicKnowledgeBasePage />} />

              {/* ========================================
                  AUTH & ONBOARDING ROUTES
                  ======================================== */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/admin/signin" element={<LoginPage />} />
              <Route path="/set-password" element={<SetPasswordPage />} />
              <Route path="/intake/start" element={<IntakePage />} />
              <Route path="/onboarding-status" element={<OnboardingStatusPage />} />
              <Route path="/checkout/success" element={<CheckoutSuccessRedirect />} />
              <Route path="/checkout/cancel" element={<Navigate to="/intake/start" replace />} />

              {/* ========================================
                  CLIENT PORTAL ROUTES (Protected)
                  Existing CVP functionality - DO NOT MODIFY
                  ======================================== */}
            <Route 
              path="/app/dashboard" 
              element={
                <ProtectedRoute>
                  <ClientDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/assistant" 
              element={
                <ProtectedRoute>
                  <AssistantPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/profile" 
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/notifications" 
              element={
                <ProtectedRoute>
                  <NotificationPreferencesPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/calendar" 
              element={
                <ProtectedRoute>
                  <CalendarPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/properties/create" 
              element={
                <ProtectedRoute>
                  <PropertyCreatePage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/properties" 
              element={
                <ProtectedRoute>
                  <PropertiesPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/requirements" 
              element={
                <ProtectedRoute>
                  <RequirementsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/compliance-score" 
              element={
                <ProtectedRoute>
                  <ComplianceScorePage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/documents" 
              element={
                <ProtectedRoute>
                  <DocumentsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/documents/bulk-upload" 
              element={
                <ProtectedRoute>
                  <BulkUploadPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/reports" 
              element={
                <ProtectedRoute>
                  <ReportsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/tenant" 
              element={
                <ProtectedRoute>
                  <TenantDashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/tenants" 
              element={
                <ProtectedRoute>
                  <TenantManagementPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/properties/import" 
              element={
                <ProtectedRoute>
                  <BulkPropertyImportPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/integrations" 
              element={
                <ProtectedRoute>
                  <IntegrationsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/settings/branding" 
              element={
                <ProtectedRoute>
                  <BrandingSettingsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/billing" 
              element={
                <ProtectedRoute>
                  <BillingPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/orders/:orderId/provide-info" 
              element={
                <ProtectedRoute>
                  <ClientProvideInfoPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/app/orders" 
              element={
                <ProtectedRoute>
                  <ClientOrdersPage />
                </ProtectedRoute>
              } 
            />

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
              path="/admin/leads" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminLeadsPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/admin/postal-tracking" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminPostalTrackingPage />
                </ProtectedRoute>
              } 
            />
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

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster />
          <TawkToWidget />
          <CookieBanner />
        </div>
      </BrowserRouter>
    </AuthProvider>
    </HelmetProvider>
  );
}

export default App;
