/**
 * ClearForm Dashboard
 * 
 * Main dashboard for authenticated ClearForm users.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FileText, 
  Plus, 
  CreditCard, 
  Folder, 
  LogOut, 
  Loader2,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Users
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { creditsApi, documentsApi } from '../api/clearformApi';

const ClearFormDashboard = () => {
  const navigate = useNavigate();
  const { user, logout, refreshUser } = useClearFormAuth();
  const [wallet, setWallet] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [walletData, vaultData] = await Promise.all([
        creditsApi.getWallet(),
        documentsApi.getVault(1, 10),
      ]);
      setWallet(walletData);
      setDocuments(vaultData.items);
      await refreshUser();
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/clearform');
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle className="w-4 h-4 text-emerald-500" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'GENERATING':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-yellow-500" />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/clearform/dashboard" className="flex items-center gap-3">
            <img 
              src="/pleerity-logo.jpg" 
              alt="Pleerity" 
              className="h-8 w-auto"
            />
            <div className="flex flex-col">
              <span className="text-lg font-bold text-slate-900">ClearForm</span>
              <span className="text-xs text-slate-500">by Pleerity</span>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium text-slate-900">{user?.full_name}</p>
              <p className="text-xs text-slate-500">{wallet?.total_balance || 0} credits</p>
            </div>
            <Button variant="ghost" size="icon" onClick={handleLogout} data-testid="logout-btn">
              <LogOut className="w-5 h-5" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        {/* Stats Cards */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">Credit Balance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-900">{wallet?.total_balance || 0}</div>
              {wallet?.expiring_soon > 0 && (
                <p className="text-sm text-yellow-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="w-3 h-3" />
                  {wallet.expiring_soon} expiring soon
                </p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-slate-500">Documents This Month</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-slate-900">{wallet?.documents_generated_this_month || 0}</div>
              <p className="text-sm text-slate-500 mt-1">
                {wallet?.credits_used_this_month || 0} credits used
              </p>
            </CardContent>
          </Card>
          
          <Card className="bg-emerald-50 border-emerald-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-emerald-700">Create Document</CardTitle>
            </CardHeader>
            <CardContent>
              <Button 
                className="w-full gap-2" 
                onClick={() => navigate('/clearform/create')}
                data-testid="create-document-btn"
              >
                <Plus className="w-4 h-4" /> New Document
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => navigate('/clearform/vault')} data-testid="vault-card">
            <CardHeader>
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                  <Folder className="w-6 h-6 text-slate-600" />
                </div>
                <div>
                  <CardTitle>Document Vault</CardTitle>
                  <CardDescription>Access all your generated documents</CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
          
          <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => navigate('/clearform/credits')} data-testid="credits-card">
            <CardHeader>
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                  <CreditCard className="w-6 h-6 text-slate-600" />
                </div>
                <div>
                  <CardTitle>Buy Credits</CardTitle>
                  <CardDescription>Top up your credit balance</CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
          
          <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={() => navigate('/clearform/team')} data-testid="team-card">
            <CardHeader>
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-slate-100 rounded-lg flex items-center justify-center">
                  <Users className="w-6 h-6 text-slate-600" />
                </div>
                <div>
                  <CardTitle>Team Management</CardTitle>
                  <CardDescription>Manage your organization & members</CardDescription>
                </div>
              </div>
            </CardHeader>
          </Card>
        </div>

        {/* Recent Documents */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Documents</CardTitle>
              <CardDescription>Your latest generated documents</CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={() => navigate('/clearform/vault')}>
              View All
            </Button>
          </CardHeader>
          <CardContent>
            {documents.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                <p className="text-slate-500">No documents yet</p>
                <Button className="mt-4" onClick={() => navigate('/clearform/create')}>
                  Create Your First Document
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div 
                    key={doc.document_id} 
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/clearform/document/${doc.document_id}`)}
                    data-testid={`document-item-${doc.document_id}`}
                  >
                    <div className="flex items-center gap-3">
                      {getStatusIcon(doc.status)}
                      <div>
                        <p className="font-medium text-slate-900">{doc.title}</p>
                        <p className="text-sm text-slate-500">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded capitalize">
                      {doc.document_type.replace('_', ' ')}
                    </span>
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

export default ClearFormDashboard;
