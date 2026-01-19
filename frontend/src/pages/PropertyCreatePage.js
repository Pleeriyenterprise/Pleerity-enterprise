import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Alert, AlertDescription } from '../components/ui/alert';
import { ArrowLeft, Plus, CheckCircle2, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const PropertyCreatePage = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const [formData, setFormData] = useState({
    address_line_1: '',
    address_line_2: '',
    city: '',
    postcode: '',
    property_type: 'residential',
    number_of_units: 1
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);
    setLoading(true);

    try {
      const token = localStorage.getItem('auth_token');
      await axios.post(
        `${API_URL}/api/properties/create`,
        formData,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setSuccess(true);
      setTimeout(() => {
        navigate('/app/dashboard');
      }, 2000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create property');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-midnight-blue mb-2">Property Added!</h3>
            <p className="text-gray-600">Redirecting to dashboard...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate('/app/dashboard')}
                className="text-white hover:text-electric-teal"
                data-testid="back-to-dashboard-btn"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Dashboard
              </Button>
              <div className="border-l border-gray-600 pl-4">
                <h1 className="text-xl font-bold flex items-center gap-2">
                  <Plus className="w-5 h-5" />
                  Add New Property
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
              >
                Logout
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue">Property Details</CardTitle>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Address Line 1 *</label>
                <Input
                  value={formData.address_line_1}
                  onChange={(e) => setFormData({ ...formData, address_line_1: e.target.value })}
                  placeholder="123 High Street"
                  required
                  data-testid="address-1-input"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Address Line 2</label>
                <Input
                  value={formData.address_line_2}
                  onChange={(e) => setFormData({ ...formData, address_line_2: e.target.value })}
                  placeholder="Flat 4B"
                  data-testid="address-2-input"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">City *</label>
                  <Input
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    placeholder="London"
                    required
                    data-testid="city-input"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">Postcode *</label>
                  <Input
                    value={formData.postcode}
                    onChange={(e) => setFormData({ ...formData, postcode: e.target.value.toUpperCase() })}
                    placeholder="SW1A 1AA"
                    required
                    data-testid="postcode-input"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Property Type *</label>
                <select
                  value={formData.property_type}
                  onChange={(e) => setFormData({ ...formData, property_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  data-testid="property-type-select"
                >
                  <option value="residential">Residential</option>
                  <option value="hmo">HMO (House in Multiple Occupation)</option>
                  <option value="commercial">Commercial</option>
                  <option value="mixed_use">Mixed Use</option>
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700">Number of Units</label>
                <Input
                  type="number"
                  min="1"
                  value={formData.number_of_units}
                  onChange={(e) => setFormData({ ...formData, number_of_units: parseInt(e.target.value) })}
                  data-testid="units-input"
                />
              </div>

              <div className="pt-4 border-t">
                <Alert className="mb-4 bg-blue-50 border-blue-200">
                  <AlertDescription className="text-sm text-blue-800">
                    Compliance requirements will be automatically generated based on the property type.
                  </AlertDescription>
                </Alert>

                <Button
                  type="submit"
                  className="btn-primary w-full"
                  disabled={loading}
                  data-testid="create-property-btn"
                >
                  {loading ? 'Creating Property...' : 'Add Property'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default PropertyCreatePage;
