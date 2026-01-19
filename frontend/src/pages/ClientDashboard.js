import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { clientAPI } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { AlertCircle, Home, FileText, Shield, LogOut, CheckCircle, XCircle, Clock, MessageSquare, Bell, BellOff, Settings, User } from 'lucide-react';
import api from '../api/client';

const ClientDashboard = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await clientAPI.getDashboard();
      setData(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  const getComplianceColor = (status) => {
    switch (status) {
      case 'GREEN': return 'bg-green-50 text-green-700 border-green-200';
      case 'AMBER': return 'bg-yellow-50 text-yellow-700 border-yellow-200';
      case 'RED': return 'bg-red-50 text-red-700 border-red-200';
      default: return 'bg-gray-50 text-gray-700 border-gray-200';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="loading-spinner" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold">Compliance Vault Pro</h1>
              <p className="text-sm text-gray-300">AI-Driven Solutions & Compliance</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
              data-testid="nav-dashboard"
            >
              <Home className="w-4 h-4 mr-2" />
              Dashboard
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/properties')}
              data-testid="nav-properties"
            >
              <Home className="w-4 h-4 mr-2" />
              Properties
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/documents')}
              data-testid="nav-documents"
            >
              <FileText className="w-4 h-4 mr-2" />
              Documents
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="client-dashboard">
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Welcome */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h2 className="text-3xl font-bold text-midnight-blue mb-2">Welcome, {data?.client?.full_name}</h2>
            <p className="text-gray-600">Here's your compliance overview</p>
          </div>
          <Button 
            onClick={() => navigate('/app/assistant')}
            className="btn-secondary flex items-center gap-2"
            data-testid="ask-assistant-btn"
          >
            <MessageSquare className="w-4 h-4" />
            Ask Assistant
          </Button>
        </div>

        {/* Compliance Summary */}
        <div className="grid md:grid-cols-4 gap-6 mb-8">
          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Total Requirements</p>
                  <p className="text-3xl font-bold text-midnight-blue">
                    {data?.compliance_summary?.total_requirements || 0}
                  </p>
                </div>
                <Shield className="w-12 h-12 text-gray-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Compliant</p>
                  <p className="text-3xl font-bold text-green-600">
                    {data?.compliance_summary?.compliant || 0}
                  </p>
                </div>
                <CheckCircle className="w-12 h-12 text-green-600" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Expiring Soon</p>
                  <p className="text-3xl font-bold text-yellow-600">
                    {data?.compliance_summary?.expiring_soon || 0}
                  </p>
                </div>
                <Clock className="w-12 h-12 text-yellow-600" />
              </div>
            </CardContent>
          </Card>

          <Card className="enterprise-card">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 mb-1">Overdue</p>
                  <p className="text-3xl font-bold text-red-600">
                    {data?.compliance_summary?.overdue || 0}
                  </p>
                </div>
                <XCircle className="w-12 h-12 text-red-600" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Properties */}
        <Card className="enterprise-card">
          <CardHeader>
            <CardTitle className="text-midnight-blue">Your Properties</CardTitle>
          </CardHeader>
          <CardContent>
            {data?.properties?.length === 0 ? (
              <p className="text-gray-600">No properties found</p>
            ) : (
              <div className="space-y-4">
                {data?.properties?.map((property) => (
                  <div 
                    key={property.property_id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-smooth"
                    data-testid="property-card"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-semibold text-midnight-blue mb-1">
                          {property.address_line_1}
                        </h4>
                        <p className="text-sm text-gray-600">
                          {property.city}, {property.postcode}
                        </p>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-sm font-medium border ${getComplianceColor(property.compliance_status)}`}>
                        {property.compliance_status}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default ClientDashboard;
