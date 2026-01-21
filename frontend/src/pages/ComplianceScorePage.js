import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';
import { toast } from 'sonner';
import { 
  TrendingUp,
  ArrowLeft,
  Building2,
  CheckCircle,
  Clock,
  AlertTriangle,
  FileText,
  Info,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Target,
  Calendar,
  RefreshCw,
  LogOut,
  Home,
  Sparkles,
  Zap
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';

const ComplianceScorePage = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [scoreData, setScoreData] = useState(null);
  const [properties, setProperties] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [clientData, setClientData] = useState(null);
  const [showMethodology, setShowMethodology] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [scoreRes, dashboardRes, reqRes] = await Promise.all([
        api.get('/client/compliance-score'),
        api.get('/client/dashboard'),
        api.get('/client/requirements')
      ]);
      setScoreData(scoreRes.data);
      setClientData(dashboardRes.data);
      setProperties(dashboardRes.data.properties || []);
      setRequirements(reqRes.data.requirements || []);
    } catch (error) {
      toast.error('Failed to load compliance data');
    } finally {
      setLoading(false);
    }
  };

  const getPropertyScoreContribution = (propertyId) => {
    const propertyReqs = requirements.filter(r => r.property_id === propertyId);
    if (propertyReqs.length === 0) return { score: 100, count: 0, breakdown: {} };
    
    const compliant = propertyReqs.filter(r => r.status === 'COMPLIANT').length;
    const expiring = propertyReqs.filter(r => r.status === 'EXPIRING_SOON').length;
    const overdue = propertyReqs.filter(r => r.status === 'OVERDUE').length;
    const pending = propertyReqs.filter(r => r.status === 'PENDING').length;
    
    const score = Math.round(((compliant * 100) + (pending * 70) + (expiring * 40)) / propertyReqs.length);
    
    return {
      score,
      count: propertyReqs.length,
      breakdown: { compliant, expiring, overdue, pending }
    };
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-electric-teal" />
      </div>
    );
  }

  const colorClass = scoreData?.color === 'green' ? 'text-green-600' :
                     scoreData?.color === 'amber' ? 'text-amber-600' :
                     scoreData?.color === 'red' ? 'text-red-600' : 'text-gray-600';
  
  const bgColorClass = scoreData?.color === 'green' ? 'bg-green-50 border-green-200' :
                       scoreData?.color === 'amber' ? 'bg-amber-50 border-amber-200' :
                       scoreData?.color === 'red' ? 'bg-red-50 border-red-200' : 'bg-gray-50 border-gray-200';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-midnight-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <div>
                <h1 className="text-2xl font-bold">Compliance Vault Pro</h1>
                <p className="text-sm text-gray-300">AI-Driven Solutions & Compliance</p>
              </div>
              {clientData?.client?.customer_reference && (
                <span className="px-3 py-1 bg-electric-teal/20 text-electric-teal rounded-lg font-mono text-sm">
                  {clientData.client.customer_reference}
                </span>
              )}
            </div>
            <div className="flex items-center gap-4">
              <span className="text-sm">{user?.email}</span>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={logout}
                className="text-white hover:text-electric-teal"
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
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-transparent text-gray-600 hover:text-gray-900"
              onClick={() => navigate('/app/dashboard')}
            >
              <Home className="w-4 h-4 mr-2" />
              Dashboard
            </button>
            <button 
              className="flex items-center px-3 py-4 text-sm font-medium border-b-2 border-electric-teal text-electric-teal"
            >
              <TrendingUp className="w-4 h-4 mr-2" />
              Compliance Score
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" data-testid="compliance-score-page">
        {/* Back Button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate('/app/dashboard')}
          className="text-gray-600 hover:text-midnight-blue mb-6"
          data-testid="back-to-dashboard"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Button>

        {/* Main Score Card */}
        <Card className={`mb-8 border-2 ${bgColorClass}`}>
          <CardContent className="pt-6">
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              {/* Score Display */}
              <div className="flex items-center gap-6">
                <div className={`w-32 h-32 rounded-full border-8 flex items-center justify-center ${
                  scoreData?.color === 'green' ? 'border-green-500 bg-green-100' :
                  scoreData?.color === 'amber' ? 'border-amber-500 bg-amber-100' :
                  scoreData?.color === 'red' ? 'border-red-500 bg-red-100' : 'border-gray-300 bg-gray-100'
                }`}>
                  <div className="text-center">
                    <p className={`text-4xl font-bold ${colorClass}`}>{scoreData?.score || 0}</p>
                    <p className="text-sm text-gray-500">/100</p>
                  </div>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-3xl font-bold ${colorClass}`}>Grade {scoreData?.grade}</span>
                    <Target className={`w-6 h-6 ${colorClass}`} />
                  </div>
                  <p className="text-lg text-gray-700">{scoreData?.message}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    Based on {scoreData?.stats?.total_requirements || 0} requirements across {scoreData?.properties_count || 0} properties
                  </p>
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-green-600">{scoreData?.stats?.compliant || 0}</p>
                  <p className="text-xs text-gray-600">Compliant</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-amber-600">{scoreData?.stats?.expiring_soon || 0}</p>
                  <p className="text-xs text-gray-600">Expiring Soon</p>
                </div>
                <div className="text-center p-3 bg-white/50 rounded-lg">
                  <p className="text-2xl font-bold text-red-600">{scoreData?.stats?.overdue || 0}</p>
                  <p className="text-xs text-gray-600">Overdue</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* How Score is Calculated - Expandable */}
        <Card className="mb-8" data-testid="score-methodology">
          <CardHeader 
            className="cursor-pointer hover:bg-gray-50"
            onClick={() => setShowMethodology(!showMethodology)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Info className="w-5 h-5 text-electric-teal" />
                How This Score is Calculated
              </CardTitle>
              {showMethodology ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showMethodology && (
            <CardContent className="border-t">
              <div className="space-y-6">
                {/* Weighting Model */}
                <div>
                  <h4 className="font-semibold text-midnight-blue mb-3">Score Weighting Model</h4>
                  <div className="grid md:grid-cols-4 gap-4">
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-blue-700">Status</span>
                        <span className="text-lg font-bold text-blue-700">40%</span>
                      </div>
                      <p className="text-xs text-blue-600">
                        Based on requirement statuses: COMPLIANT (100pts), PENDING (70pts), EXPIRING_SOON (40pts), OVERDUE (0pts)
                      </p>
                      <p className="text-sm font-semibold text-blue-800 mt-2">
                        Your score: {scoreData?.breakdown?.status_score?.toFixed(0)}%
                      </p>
                    </div>
                    <div className="p-4 bg-purple-50 rounded-lg border border-purple-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-purple-700">Timeline</span>
                        <span className="text-lg font-bold text-purple-700">30%</span>
                      </div>
                      <p className="text-xs text-purple-600">
                        Days until next expiry: 90+ days (100pts), 60+ (90pts), 30+ (70pts), 14+ (50pts), 7+ (30pts)
                      </p>
                      <p className="text-sm font-semibold text-purple-800 mt-2">
                        Your score: {scoreData?.breakdown?.expiry_score?.toFixed(0)}%
                      </p>
                    </div>
                    <div className="p-4 bg-teal-50 rounded-lg border border-teal-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-teal-700">Documents</span>
                        <span className="text-lg font-bold text-teal-700">15%</span>
                      </div>
                      <p className="text-xs text-teal-600">
                        Percentage of requirements with uploaded documents
                      </p>
                      <p className="text-sm font-semibold text-teal-800 mt-2">
                        Your score: {scoreData?.breakdown?.document_score?.toFixed(0)}%
                        <span className="font-normal text-xs ml-1">
                          ({scoreData?.stats?.document_coverage_percent?.toFixed(0)}% coverage)
                        </span>
                      </p>
                    </div>
                    <div className="p-4 bg-red-50 rounded-lg border border-red-100">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-red-700">Overdue Penalty</span>
                        <span className="text-lg font-bold text-red-700">15%</span>
                      </div>
                      <p className="text-xs text-red-600">
                        Heavy penalty for overdue items. More overdue = lower score
                      </p>
                      <p className="text-sm font-semibold text-red-800 mt-2">
                        Your score: {scoreData?.breakdown?.overdue_penalty_score?.toFixed(0)}%
                      </p>
                    </div>
                  </div>
                </div>

                {/* Concrete Breakdown */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold text-midnight-blue mb-3">Your Current Status</h4>
                  <div className="grid md:grid-cols-3 gap-4 text-sm">
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                      <div>
                        <p className="font-medium">Status Component</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.compliant || 0}/{scoreData?.stats?.total_requirements || 0} requirements currently valid
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <Clock className="w-5 h-5 text-amber-600" />
                      <div>
                        <p className="font-medium">Expiry Timeline</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.expiring_soon || 0} items due within 30 days
                          {scoreData?.stats?.days_until_next_expiry !== null && (
                            <span className="block text-xs">
                              Next expiry: {scoreData?.stats?.days_until_next_expiry} days
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                      <FileText className="w-5 h-5 text-teal-600" />
                      <div>
                        <p className="font-medium">Documents</p>
                        <p className="text-gray-600">
                          {scoreData?.stats?.documents_uploaded || 0} documents uploaded
                          <span className="block text-xs">
                            {scoreData?.stats?.document_coverage_percent?.toFixed(0)}% requirement coverage
                          </span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Recommendations */}
        {scoreData?.recommendations?.length > 0 && (
          <Card className="mb-8">
            <CardHeader>
              <CardTitle className="text-midnight-blue flex items-center gap-2">
                <Zap className="w-5 h-5 text-electric-teal" />
                Actions to Improve Your Score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {scoreData.recommendations.map((rec, idx) => (
                  <div 
                    key={idx}
                    className={`flex items-start gap-3 p-4 rounded-lg border ${
                      rec.priority === 'high' ? 'bg-red-50 border-red-200' :
                      rec.priority === 'medium' ? 'bg-amber-50 border-amber-200' :
                      'bg-gray-50 border-gray-200'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                      rec.priority === 'high' ? 'bg-red-500' :
                      rec.priority === 'medium' ? 'bg-amber-500' :
                      'bg-gray-400'
                    }`} />
                    <div className="flex-1">
                      <p className="font-medium text-gray-800">{rec.action}</p>
                      <p className="text-sm text-gray-500 mt-1">Potential impact: {rec.impact}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      rec.priority === 'high' ? 'bg-red-100 text-red-700' :
                      rec.priority === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {rec.priority.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Per-Property Breakdown */}
        <Card>
          <CardHeader>
            <CardTitle className="text-midnight-blue flex items-center gap-2">
              <Building2 className="w-5 h-5 text-electric-teal" />
              Score by Property
            </CardTitle>
          </CardHeader>
          <CardContent>
            {properties.length === 0 ? (
              <p className="text-gray-500 text-center py-8">No properties to display</p>
            ) : (
              <div className="space-y-4">
                {properties.map((property) => {
                  const contribution = getPropertyScoreContribution(property.property_id);
                  const propertyColor = contribution.score >= 80 ? 'green' :
                                       contribution.score >= 60 ? 'amber' : 'red';
                  
                  return (
                    <div 
                      key={property.property_id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/app/properties?property_id=${property.property_id}`)}
                      data-testid={`property-score-${property.property_id}`}
                    >
                      <div className="flex items-center gap-4">
                        <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${
                          propertyColor === 'green' ? 'bg-green-100' :
                          propertyColor === 'amber' ? 'bg-amber-100' : 'bg-red-100'
                        }`}>
                          <Building2 className={`w-6 h-6 ${
                            propertyColor === 'green' ? 'text-green-600' :
                            propertyColor === 'amber' ? 'text-amber-600' : 'text-red-600'
                          }`} />
                        </div>
                        <div>
                          <h4 className="font-semibold text-midnight-blue">
                            {property.nickname || property.address_line_1}
                          </h4>
                          <p className="text-sm text-gray-500">{property.postcode}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded text-xs ${
                              contribution.breakdown.compliant > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                            }`}>
                              {contribution.breakdown.compliant} valid
                            </span>
                            {contribution.breakdown.expiring > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
                                {contribution.breakdown.expiring} expiring
                              </span>
                            )}
                            {contribution.breakdown.overdue > 0 && (
                              <span className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700">
                                {contribution.breakdown.overdue} overdue
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-gray-500 mt-1">{contribution.count} requirements</p>
                        </div>
                        <div className={`text-2xl font-bold ${
                          propertyColor === 'green' ? 'text-green-600' :
                          propertyColor === 'amber' ? 'text-amber-600' : 'text-red-600'
                        }`}>
                          {contribution.score}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default ComplianceScorePage;
