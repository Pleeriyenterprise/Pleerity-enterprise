/**
 * ClearForm Workspaces & Profiles Page
 * 
 * Manage workspaces and smart profiles for document pre-filling.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  FolderKanban,
  Plus,
  User,
  Building,
  Home,
  ArrowLeft,
  Loader2,
  MoreVertical,
  Edit,
  Trash2,
  Star,
  StarOff,
  CheckCircle
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import { useClearFormAuth } from '../contexts/ClearFormAuthContext';
import { workspacesApi, profilesApi } from '../api/clearformApi';
import { toast } from 'sonner';

const ClearFormWorkspacesPage = () => {
  const navigate = useNavigate();
  const { user } = useClearFormAuth();
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('profiles');
  
  // Workspaces state
  const [workspaces, setWorkspaces] = useState([]);
  const [showCreateWorkspace, setShowCreateWorkspace] = useState(false);
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceDescription, setNewWorkspaceDescription] = useState('');
  const [creatingWorkspace, setCreatingWorkspace] = useState(false);
  
  // Profiles state
  const [profiles, setProfiles] = useState([]);
  const [showCreateProfile, setShowCreateProfile] = useState(false);
  const [profileName, setProfileName] = useState('');
  const [profileType, setProfileType] = useState('PERSONAL');
  const [profileData, setProfileData] = useState({});
  const [creatingProfile, setCreatingProfile] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [workspacesData, profilesData] = await Promise.all([
        workspacesApi.getWorkspaces().catch(() => ({ workspaces: [] })),
        profilesApi.getProfiles().catch(() => ({ profiles: [] })),
      ]);
      setWorkspaces(workspacesData.workspaces || []);
      setProfiles(profilesData.profiles || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWorkspace = async () => {
    if (!newWorkspaceName.trim()) {
      toast.error('Workspace name is required');
      return;
    }

    setCreatingWorkspace(true);
    try {
      await workspacesApi.createWorkspace({
        name: newWorkspaceName,
        description: newWorkspaceDescription,
      });
      toast.success('Workspace created!');
      setShowCreateWorkspace(false);
      setNewWorkspaceName('');
      setNewWorkspaceDescription('');
      loadData();
    } catch (error) {
      toast.error(error.message || 'Failed to create workspace');
    } finally {
      setCreatingWorkspace(false);
    }
  };

  const handleCreateProfile = async () => {
    if (!profileName.trim()) {
      toast.error('Profile name is required');
      return;
    }

    setCreatingProfile(true);
    try {
      await profilesApi.createProfile({
        name: profileName,
        profile_type: profileType,
        data: profileData,
      });
      toast.success('Profile created!');
      setShowCreateProfile(false);
      setProfileName('');
      setProfileType('PERSONAL');
      setProfileData({});
      loadData();
    } catch (error) {
      toast.error(error.message || 'Failed to create profile');
    } finally {
      setCreatingProfile(false);
    }
  };

  const handleToggleFavorite = async (profileId, currentFavorite) => {
    try {
      await profilesApi.updateProfile(profileId, { is_favorite: !currentFavorite });
      setProfiles(profiles.map(p => 
        p.profile_id === profileId ? { ...p, is_favorite: !currentFavorite } : p
      ));
      toast.success(currentFavorite ? 'Removed from favorites' : 'Added to favorites');
    } catch (error) {
      toast.error('Failed to update profile');
    }
  };

  const handleDeleteProfile = async (profileId) => {
    if (!confirm('Are you sure you want to delete this profile?')) return;
    
    try {
      await profilesApi.deleteProfile(profileId);
      setProfiles(profiles.filter(p => p.profile_id !== profileId));
      toast.success('Profile deleted');
    } catch (error) {
      toast.error('Failed to delete profile');
    }
  };

  const getProfileIcon = (type) => {
    switch (type) {
      case 'PERSONAL':
        return <User className="w-5 h-5 text-blue-500" />;
      case 'BUSINESS':
        return <Building className="w-5 h-5 text-purple-500" />;
      case 'PROPERTY':
        return <Home className="w-5 h-5 text-emerald-500" />;
      default:
        return <User className="w-5 h-5 text-gray-500" />;
    }
  };

  const getProfileFields = (type) => {
    switch (type) {
      case 'PERSONAL':
        return [
          { key: 'full_name', label: 'Full Name', type: 'text' },
          { key: 'email', label: 'Email', type: 'email' },
          { key: 'phone', label: 'Phone', type: 'tel' },
          { key: 'address', label: 'Address', type: 'textarea' },
          { key: 'date_of_birth', label: 'Date of Birth', type: 'date' },
        ];
      case 'BUSINESS':
        return [
          { key: 'company_name', label: 'Company Name', type: 'text' },
          { key: 'registration_number', label: 'Registration Number', type: 'text' },
          { key: 'vat_number', label: 'VAT Number', type: 'text' },
          { key: 'business_address', label: 'Business Address', type: 'textarea' },
          { key: 'contact_email', label: 'Contact Email', type: 'email' },
          { key: 'contact_phone', label: 'Contact Phone', type: 'tel' },
        ];
      case 'PROPERTY':
        return [
          { key: 'property_address', label: 'Property Address', type: 'textarea' },
          { key: 'property_type', label: 'Property Type', type: 'text' },
          { key: 'bedrooms', label: 'Bedrooms', type: 'number' },
          { key: 'monthly_rent', label: 'Monthly Rent (£)', type: 'number' },
          { key: 'deposit_amount', label: 'Deposit Amount (£)', type: 'number' },
        ];
      default:
        return [];
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
              <p className="text-xs text-slate-500">{user?.credit_balance || 0} credits</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 max-w-5xl">
        {/* Back Link */}
        <Button 
          variant="ghost" 
          className="mb-6"
          onClick={() => navigate('/clearform/dashboard')}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Button>

        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">Workspaces & Profiles</h1>
          <p className="text-slate-500">Manage your workspaces and save profiles for faster document creation</p>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="profiles" className="flex items-center gap-2">
              <User className="w-4 h-4" />
              Smart Profiles
            </TabsTrigger>
            <TabsTrigger value="workspaces" className="flex items-center gap-2">
              <FolderKanban className="w-4 h-4" />
              Workspaces
            </TabsTrigger>
          </TabsList>

          {/* Smart Profiles Tab */}
          <TabsContent value="profiles" className="space-y-6">
            <div className="flex justify-between items-center">
              <p className="text-sm text-slate-500">
                Save your commonly used information to auto-fill documents
              </p>
              <Dialog open={showCreateProfile} onOpenChange={setShowCreateProfile}>
                <DialogTrigger asChild>
                  <Button data-testid="create-profile-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    New Profile
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
                  <DialogHeader>
                    <DialogTitle>Create Smart Profile</DialogTitle>
                    <DialogDescription>
                      Save information to quickly fill documents
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>Profile Name</Label>
                      <Input
                        placeholder="e.g., My Personal Details"
                        value={profileName}
                        onChange={(e) => setProfileName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Profile Type</Label>
                      <Select value={profileType} onValueChange={(v) => { setProfileType(v); setProfileData({}); }}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="PERSONAL">Personal Details</SelectItem>
                          <SelectItem value="BUSINESS">Business Details</SelectItem>
                          <SelectItem value="PROPERTY">Property Details</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    
                    <div className="border-t pt-4 space-y-3">
                      <Label className="text-slate-500">Profile Data</Label>
                      {getProfileFields(profileType).map((field) => (
                        <div key={field.key} className="space-y-1">
                          <Label className="text-sm">{field.label}</Label>
                          {field.type === 'textarea' ? (
                            <Textarea
                              placeholder={field.label}
                              value={profileData[field.key] || ''}
                              onChange={(e) => setProfileData({ ...profileData, [field.key]: e.target.value })}
                              rows={2}
                            />
                          ) : (
                            <Input
                              type={field.type}
                              placeholder={field.label}
                              value={profileData[field.key] || ''}
                              onChange={(e) => setProfileData({ ...profileData, [field.key]: e.target.value })}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowCreateProfile(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateProfile} disabled={creatingProfile}>
                      {creatingProfile ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Create Profile
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            {profiles.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <User className="w-12 h-12 text-slate-300 mx-auto mb-4" />
                  <h3 className="font-semibold text-slate-900 mb-2">No Profiles Yet</h3>
                  <p className="text-slate-500 mb-4">
                    Create profiles to save your frequently used information
                  </p>
                  <Button onClick={() => setShowCreateProfile(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Your First Profile
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {profiles.map((profile) => (
                  <Card key={profile.profile_id} className="relative" data-testid={`profile-${profile.profile_id}`}>
                    <CardHeader className="pb-2">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                            {getProfileIcon(profile.profile_type)}
                          </div>
                          <div>
                            <CardTitle className="text-base flex items-center gap-2">
                              {profile.name}
                              {profile.is_favorite && (
                                <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
                              )}
                            </CardTitle>
                            <Badge variant="outline" className="text-xs capitalize mt-1">
                              {profile.profile_type?.toLowerCase()}
                            </Badge>
                          </div>
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreVertical className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => handleToggleFavorite(profile.profile_id, profile.is_favorite)}>
                              {profile.is_favorite ? (
                                <><StarOff className="w-4 h-4 mr-2" /> Remove from Favorites</>
                              ) : (
                                <><Star className="w-4 h-4 mr-2" /> Add to Favorites</>
                              )}
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Edit className="w-4 h-4 mr-2" /> Edit Profile
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem 
                              className="text-red-600"
                              onClick={() => handleDeleteProfile(profile.profile_id)}
                            >
                              <Trash2 className="w-4 h-4 mr-2" /> Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="text-sm text-slate-500">
                        {Object.keys(profile.data || {}).length} fields saved
                      </div>
                      {profile.last_used_at && (
                        <div className="text-xs text-slate-400 mt-1">
                          Last used: {new Date(profile.last_used_at).toLocaleDateString()}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Workspaces Tab */}
          <TabsContent value="workspaces" className="space-y-6">
            <div className="flex justify-between items-center">
              <p className="text-sm text-slate-500">
                Organize your documents into workspaces
              </p>
              <Dialog open={showCreateWorkspace} onOpenChange={setShowCreateWorkspace}>
                <DialogTrigger asChild>
                  <Button data-testid="create-workspace-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    New Workspace
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create Workspace</DialogTitle>
                    <DialogDescription>
                      Create a new workspace to organize your documents
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>Workspace Name</Label>
                      <Input
                        placeholder="e.g., Rental Properties"
                        value={newWorkspaceName}
                        onChange={(e) => setNewWorkspaceName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Description (optional)</Label>
                      <Textarea
                        placeholder="Brief description of this workspace"
                        value={newWorkspaceDescription}
                        onChange={(e) => setNewWorkspaceDescription(e.target.value)}
                      />
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setShowCreateWorkspace(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleCreateWorkspace} disabled={creatingWorkspace}>
                      {creatingWorkspace ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                      Create Workspace
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              {workspaces.map((workspace) => (
                <Card key={workspace.workspace_id} className="cursor-pointer hover:shadow-lg transition-shadow" data-testid={`workspace-${workspace.workspace_id}`}>
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center">
                          <FolderKanban className="w-5 h-5 text-emerald-600" />
                        </div>
                        <div>
                          <CardTitle className="text-base flex items-center gap-2">
                            {workspace.name}
                            {workspace.is_default && (
                              <Badge variant="outline" className="text-xs">Default</Badge>
                            )}
                          </CardTitle>
                          <CardDescription className="text-sm">
                            {workspace.description || 'No description'}
                          </CardDescription>
                        </div>
                      </div>
                      {!workspace.is_default && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreVertical className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem>
                              <CheckCircle className="w-4 h-4 mr-2" /> Set as Default
                            </DropdownMenuItem>
                            <DropdownMenuItem>
                              <Edit className="w-4 h-4 mr-2" /> Edit
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-red-600">
                              <Trash2 className="w-4 h-4 mr-2" /> Archive
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="text-sm text-slate-500">
                      {workspace.document_count || 0} documents
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      Created: {new Date(workspace.created_at).toLocaleDateString()}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default ClearFormWorkspacesPage;
