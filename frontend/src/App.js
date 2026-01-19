import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { ProtectedRoute } from './utils/ProtectedRoute';
import { Toaster } from './components/ui/sonner';
import './App.css';

// Public pages
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import SetPasswordPage from './pages/SetPasswordPage';
import IntakePage from './pages/IntakePage';
import OnboardingStatusPage from './pages/OnboardingStatusPage';

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
import AssistantPage from './pages/AssistantPage';
import ProfilePage from './pages/ProfilePage';
import PropertyCreatePage from './pages/PropertyCreatePage';
import DocumentsPage from './pages/DocumentsPage';
import NotificationPreferencesPage from './pages/NotificationPreferencesPage';

// Admin pages
import AdminDashboard from './pages/AdminDashboard';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="App">
          <Routes>
            {/* Public Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/admin/signin" element={<LoginPage />} />
            <Route path="/set-password" element={<SetPasswordPage />} />
            <Route path="/intake/start" element={<IntakePage />} />
            <Route path="/onboarding-status" element={<OnboardingStatusPage />} />
            <Route path="/checkout/success" element={<CheckoutSuccessRedirect />} />
            <Route path="/checkout/cancel" element={<Navigate to="/intake/start" replace />} />

            {/* Client Routes - Protected */}
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
                  <ClientDashboard />
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

            {/* Admin Routes - Protected */}
            <Route 
              path="/admin/dashboard" 
              element={
                <ProtectedRoute requireAdmin>
                  <AdminDashboard />
                </ProtectedRoute>
              } 
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster />
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
