/**
 * ClearForm Organizations Page
 * 
 * Team management dashboard for institutional accounts.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { 
  Users, 
  Plus,
  Settings,
  CreditCard,
  Mail,
  MoreVertical,
  UserPlus,
  Shield,
  Crown,
  Building2,
  ArrowLeft,
  Loader2,
  CheckCircle,
  Clock,
  X
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
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
import { organizationsApi } from '../api/clearformApi';
import { toast } from 'sonner';

const ClearFormOrganizationsPage = () => {
  const navigate = useNavigate();
  const { user } = useClearFormAuth();
  const [loading, setLoading] = useState(true);
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrg, setSelectedOrg] = useState(null);
  const [members, setMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [creating, setCreating] = useState(false);
  const [inviting, setInviting] = useState(false);

  // Form states
  const [newOrgName, setNewOrgName] = useState('');
  const [newOrgDescription, setNewOrgDescription] = useState('');
  const [newOrgType, setNewOrgType] = useState('SMALL_BUSINESS');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('MEMBER');
  const [inviteMessage, setInviteMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    const loadOrganizations = async () => {
      setLoading(true);
      try {
        const data = await organizationsApi.getUserOrganizations();
        if (cancelled) return;
        setOrganizations(data.organizations || []);
        if (data.organizations?.length > 0) {
          setSelectedOrg(data.organizations[0]);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to load organizations:', error);
          toast.error('Failed to load organizations');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadOrganizations();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedOrg?.org_id) return;
    const loadOrgDetails = async (orgId) => {
      try {
        const [membersData, invitationsData] = await Promise.all([
          organizationsApi.getMembers(orgId),
          organizationsApi.getPendingInvitations(orgId).catch(() => ({ invitations: [] })),
        ]);
        setMembers(membersData.members || []);
        setInvitations(invitationsData.invitations || []);
      } catch (error) {
        console.error('Failed to load org details:', error);
      }
    };
    loadOrgDetails(selectedOrg.org_id);
  }, [selectedOrg]);

  const handleCreateOrg = async () => {
    if (!newOrgName.trim()) {
      toast.error('Organization name is required');
      return;
    }

    setCreating(true);
    try {
      const data = await organizationsApi.createOrganization({
        name: newOrgName,
        description: newOrgDescription,
        org_type: newOrgType,
      });
      
      toast.success('Organization created successfully!');
      setShowCreateDialog(false);
      setNewOrgName('');
      setNewOrgDescription('');
      setNewOrgType('SMALL_BUSINESS');
      
      // Reload and select new org
      await loadOrganizations();
      if (data.organization) {
        setSelectedOrg(data.organization);
      }
    } catch (error) {
      toast.error(error.message || 'Failed to create organization');
    } finally {
      setCreating(false);
    }
  };

  const handleInviteMember = async () => {
    if (!inviteEmail.trim()) {
      toast.error('Email is required');
      return;
    }

    setInviting(true);
    try {
      await organizationsApi.inviteMember(selectedOrg.org_id, {
        email: inviteEmail,
        role: inviteRole,
        message: inviteMessage,
      });
      
      toast.success('Invitation sent successfully!');
      setShowInviteDialog(false);
      setInviteEmail('');
      setInviteRole('MEMBER');
      setInviteMessage('');
      
      // Reload invitations
      loadOrgDetails(selectedOrg.org_id);
    } catch (error) {
      toast.error(error.message || 'Failed to send invitation');
    } finally {
      setInviting(false);
    }
  };

  const getRoleIcon = (role) => {
    switch (role) {
      case 'OWNER':
        return <Crown className="w-4 h-4 text-amber-500" />;
      case 'ADMIN':
        return <Shield className="w-4 h-4 text-purple-500" />;
      case 'MANAGER':
        return <Users className="w-4 h-4 text-blue-500" />;
      default:
        return <Users className="w-4 h-4 text-gray-400" />;
    }
  };

  const getRoleBadgeVariant = (role) => {
    switch (role) {
      case 'OWNER':
        return 'bg-amber-100 text-amber-700';
      case 'ADMIN':
        return 'bg-purple-100 text-purple-700';
      case 'MANAGER':
        return 'bg-blue-100 text-blue-700';
      default:
        return 'bg-gray-100 text-gray-700';
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
      <main className="container mx-auto px-4 py-8 max-w-6xl">
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
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Team Management</h1>
            <p className="text-slate-500">Manage your organization and team members</p>
          </div>
          
          {organizations.length === 0 ? (
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button data-testid="create-org-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Organization
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Create Organization</DialogTitle>
                  <DialogDescription>
                    Set up your team account to collaborate with others.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="org-name">Organization Name</Label>
                    <Input
                      id="org-name"
                      placeholder="e.g., Acme Properties Ltd"
                      value={newOrgName}
                      onChange={(e) => setNewOrgName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="org-description">Description (optional)</Label>
                    <Textarea
                      id="org-description"
                      placeholder="Brief description of your organization"
                      value={newOrgDescription}
                      onChange={(e) => setNewOrgDescription(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="org-type">Organization Type</Label>
                    <Select value={newOrgType} onValueChange={setNewOrgType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="SMALL_BUSINESS">Small Business</SelectItem>
                        <SelectItem value="ENTERPRISE">Enterprise</SelectItem>
                        <SelectItem value="NONPROFIT">Non-Profit</SelectItem>
                        <SelectItem value="EDUCATIONAL">Educational</SelectItem>
                        <SelectItem value="GOVERNMENT">Government</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateOrg} disabled={creating}>
                    {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                    Create Organization
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          ) : (
            <div className="flex items-center gap-2">
              <Select 
                value={selectedOrg?.org_id} 
                onValueChange={(id) => setSelectedOrg(organizations.find(o => o.org_id === id))}
              >
                <SelectTrigger className="w-[200px]">
                  <SelectValue placeholder="Select organization" />
                </SelectTrigger>
                <SelectContent>
                  {organizations.map((org) => (
                    <SelectItem key={org.org_id} value={org.org_id}>
                      {org.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {organizations.length === 0 ? (
          /* No Organizations State */
          <Card>
            <CardContent className="py-16 text-center">
              <Building2 className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-slate-900 mb-2">No Organization Yet</h3>
              <p className="text-slate-500 mb-6 max-w-md mx-auto">
                Create an organization to collaborate with your team, share credits, and manage documents together.
              </p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="w-4 h-4 mr-2" />
                Create Your Organization
              </Button>
            </CardContent>
          </Card>
        ) : selectedOrg && (
          /* Organization Dashboard */
          <div className="space-y-6">
            {/* Stats Cards */}
            <div className="grid md:grid-cols-3 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-500">
                    Shared Credit Pool
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-slate-900">
                      {selectedOrg.credit_balance || 0}
                    </span>
                    <span className="text-slate-500">credits</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-500">
                    Team Members
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-slate-900">
                      {members.length}
                    </span>
                    <span className="text-slate-500">members</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-slate-500">
                    Pending Invitations
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-slate-900">
                      {invitations.length}
                    </span>
                    <span className="text-slate-500">pending</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Members Section */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Team Members</CardTitle>
                  <CardDescription>Manage who has access to your organization</CardDescription>
                </div>
                <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
                  <DialogTrigger asChild>
                    <Button size="sm" data-testid="invite-member-btn">
                      <UserPlus className="w-4 h-4 mr-2" />
                      Invite Member
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Invite Team Member</DialogTitle>
                      <DialogDescription>
                        Send an invitation to join {selectedOrg.name}
                      </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                      <div className="space-y-2">
                        <Label htmlFor="invite-email">Email Address</Label>
                        <Input
                          id="invite-email"
                          type="email"
                          placeholder="colleague@example.com"
                          value={inviteEmail}
                          onChange={(e) => setInviteEmail(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="invite-role">Role</Label>
                        <Select value={inviteRole} onValueChange={setInviteRole}>
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="ADMIN">Admin - Full access</SelectItem>
                            <SelectItem value="MANAGER">Manager - Can manage members</SelectItem>
                            <SelectItem value="MEMBER">Member - Standard access</SelectItem>
                            <SelectItem value="VIEWER">Viewer - Read-only access</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="invite-message">Personal Message (optional)</Label>
                        <Textarea
                          id="invite-message"
                          placeholder="Add a personal note to your invitation..."
                          value={inviteMessage}
                          onChange={(e) => setInviteMessage(e.target.value)}
                        />
                      </div>
                    </div>
                    <DialogFooter>
                      <Button variant="outline" onClick={() => setShowInviteDialog(false)}>
                        Cancel
                      </Button>
                      <Button onClick={handleInviteMember} disabled={inviting}>
                        {inviting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                        Send Invitation
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </CardHeader>
              <CardContent>
                {members.length === 0 ? (
                  <div className="text-center py-8 text-slate-500">
                    <Users className="w-12 h-12 mx-auto mb-4 text-slate-300" />
                    <p>No team members yet. Invite someone to get started!</p>
                  </div>
                ) : (
                  <div className="divide-y">
                    {members.map((member) => (
                      <div 
                        key={member.member_id || member.user_id} 
                        className="flex items-center justify-between py-4"
                        data-testid={`member-${member.user_id}`}
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center">
                            <span className="text-sm font-medium text-slate-600">
                              {member.email?.[0]?.toUpperCase() || '?'}
                            </span>
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">
                              {member.full_name || member.email}
                            </p>
                            <p className="text-sm text-slate-500">{member.email}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${getRoleBadgeVariant(member.role)}`}>
                            {getRoleIcon(member.role)}
                            {member.role}
                          </span>
                          {member.role !== 'OWNER' && selectedOrg.user_role === 'OWNER' && (
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="sm">
                                  <MoreVertical className="w-4 h-4" />
                                </Button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end">
                                <DropdownMenuItem>Change Role</DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem className="text-red-600">
                                  Remove Member
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Pending Invitations */}
            {invitations.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Pending Invitations</CardTitle>
                  <CardDescription>Invitations waiting for response</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="divide-y">
                    {invitations.map((invitation) => (
                      <div 
                        key={invitation.invitation_id} 
                        className="flex items-center justify-between py-4"
                      >
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 bg-amber-50 rounded-full flex items-center justify-center">
                            <Mail className="w-5 h-5 text-amber-500" />
                          </div>
                          <div>
                            <p className="font-medium text-slate-900">{invitation.email}</p>
                            <div className="flex items-center gap-2 text-sm text-slate-500">
                              <Clock className="w-3 h-3" />
                              <span>
                                Sent {new Date(invitation.created_at).toLocaleDateString()}
                              </span>
                              <span>•</span>
                              <span className="capitalize">{invitation.role.toLowerCase()} role</span>
                            </div>
                          </div>
                        </div>
                        <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200">
                          Pending
                        </Badge>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Organization Settings */}
            <Card>
              <CardHeader>
                <CardTitle>Organization Settings</CardTitle>
                <CardDescription>Manage your organization details</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <Label className="text-slate-500">Organization Name</Label>
                    <p className="font-medium text-slate-900">{selectedOrg.name}</p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Organization Type</Label>
                    <p className="font-medium text-slate-900 capitalize">
                      {selectedOrg.org_type?.replace(/_/g, ' ').toLowerCase() || 'Small Business'}
                    </p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Your Role</Label>
                    <p className="font-medium text-slate-900 flex items-center gap-2">
                      {getRoleIcon(selectedOrg.user_role)}
                      {selectedOrg.user_role}
                    </p>
                  </div>
                  <div>
                    <Label className="text-slate-500">Created</Label>
                    <p className="font-medium text-slate-900">
                      {new Date(selectedOrg.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
};

export default ClearFormOrganizationsPage;
