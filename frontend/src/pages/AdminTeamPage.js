/**
 * Admin Team Permissions Page
 * Manage roles, permissions, and admin users with custom role builder
 */
import React, { useState, useEffect, useCallback } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import {
  Users, Shield, Plus, Edit, Trash2, CheckCircle, XCircle,
  RefreshCw, UserPlus, Lock, Unlock, Eye, Settings, Save
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from '../components/ui/select';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle
} from '../components/ui/dialog';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow
} from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Switch } from '../components/ui/switch';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import client from '../api/client';

// Stat Card component
function StatCard({ title, value, icon: Icon, color = 'blue', description }) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    amber: 'bg-amber-100 text-amber-600',
  };
  
  return (
    <Card data-testid={`stat-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-4">
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{title}</p>
          {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminTeamPage() {
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(false);
  const [permissions, setPermissions] = useState({});
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);
  const [myPermissions, setMyPermissions] = useState({});
  
  // Dialogs
  const [showRoleDialog, setShowRoleDialog] = useState(false);
  const [showUserDialog, setShowUserDialog] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  
  // Role form
  const [roleForm, setRoleForm] = useState({
    name: '',
    description: '',
    permissions: {}
  });
  
  // User form
  const [userForm, setUserForm] = useState({
    email: '',
    name: '',
    role_id: '',
    send_invite: true
  });
  
  // Fetch all data
  const fetchData = useCallback(async () => {
    try {
      const [permRes, rolesRes, usersRes, myPermRes] = await Promise.all([
        client.get('/admin/team/permissions'),
        client.get('/admin/team/roles'),
        client.get('/admin/team/users'),
        client.get('/admin/team/me/permissions')
      ]);
      
      setPermissions(permRes.data.permissions || {});
      setRoles(rolesRes.data.roles || []);
      setUsers(usersRes.data.users || []);
      setMyPermissions(myPermRes.data);
    } catch (error) {
      console.error('Failed to fetch team data:', error);
      toast.error('Failed to load team data');
    }
  }, []);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  // Role handlers
  const openCreateRole = () => {
    setEditingRole(null);
    setRoleForm({ name: '', description: '', permissions: {} });
    setShowRoleDialog(true);
  };
  
  const openEditRole = (role) => {
    if (role.is_system) {
      toast.error('Built-in roles cannot be modified');
      return;
    }
    setEditingRole(role);
    setRoleForm({
      name: role.name,
      description: role.description || '',
      permissions: { ...role.permissions }
    });
    setShowRoleDialog(true);
  };
  
  const handleSaveRole = async () => {
    if (!roleForm.name.trim()) {
      toast.error('Role name is required');
      return;
    }
    
    setLoading(true);
    try {
      if (editingRole) {
        await client.put(`/admin/team/roles/${editingRole.role_id}`, {
          name: roleForm.name,
          description: roleForm.description,
          permissions: roleForm.permissions
        });
        toast.success('Role updated successfully');
      } else {
        await client.post('/admin/team/roles', {
          name: roleForm.name,
          description: roleForm.description,
          permissions: roleForm.permissions
        });
        toast.success('Role created successfully');
      }
      setShowRoleDialog(false);
      fetchData();
    } catch (error) {
      console.error('Failed to save role:', error);
      toast.error(error.response?.data?.detail || 'Failed to save role');
    } finally {
      setLoading(false);
    }
  };
  
  const handleDeleteRole = async (roleId) => {
    if (!window.confirm('Are you sure you want to delete this role?')) return;
    
    try {
      await client.delete(`/admin/team/roles/${roleId}`);
      toast.success('Role deleted');
      fetchData();
    } catch (error) {
      console.error('Failed to delete role:', error);
      toast.error(error.response?.data?.detail || 'Failed to delete role');
    }
  };
  
  // Permission toggle in role builder
  const togglePermission = (category, action) => {
    const current = roleForm.permissions[category] || [];
    const updated = current.includes(action)
      ? current.filter(a => a !== action)
      : [...current, action];
    
    setRoleForm({
      ...roleForm,
      permissions: {
        ...roleForm.permissions,
        [category]: updated
      }
    });
  };
  
  // User handlers
  const openCreateUser = () => {
    setUserForm({ email: '', name: '', role_id: '', send_invite: true });
    setShowUserDialog(true);
  };
  
  const handleCreateUser = async () => {
    if (!userForm.email || !userForm.name || !userForm.role_id) {
      toast.error('Please fill all required fields');
      return;
    }
    
    setLoading(true);
    try {
      await client.post('/admin/team/users', userForm);
      toast.success('User created successfully');
      setShowUserDialog(false);
      fetchData();
    } catch (error) {
      console.error('Failed to create user:', error);
      toast.error(error.response?.data?.detail || 'Failed to create user');
    } finally {
      setLoading(false);
    }
  };
  
  const handleToggleUser = async (userId, currentStatus) => {
    try {
      await client.put(`/admin/team/users/${userId}`, {
        is_active: currentStatus !== 'ACTIVE'
      });
      toast.success('User status updated');
      fetchData();
    } catch (error) {
      console.error('Failed to update user:', error);
      toast.error(error.response?.data?.detail || 'Failed to update user');
    }
  };
  
  const handleChangeUserRole = async (userId, newRoleId) => {
    try {
      await client.put(`/admin/team/users/${userId}`, { role_id: newRoleId });
      toast.success('User role updated');
      fetchData();
    } catch (error) {
      console.error('Failed to update user role:', error);
      toast.error(error.response?.data?.detail || 'Failed to update role');
    }
  };
  
  const activeUsers = users.filter(u => u.status === 'ACTIVE').length;
  const customRoles = roles.filter(r => !r.is_system).length;
  
  return (
    <UnifiedAdminLayout>
      <div className="p-6 space-y-6" data-testid="admin-team-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Team Permissions</h1>
            <p className="text-gray-500">
              Manage admin users and roles • Your role: <Badge variant="outline">{myPermissions.role_name}</Badge>
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={openCreateRole} data-testid="create-role-btn">
              <Shield className="h-4 w-4 mr-2" />
              New Role
            </Button>
            <Button onClick={openCreateUser} data-testid="create-user-btn">
              <UserPlus className="h-4 w-4 mr-2" />
              Add User
            </Button>
          </div>
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Admin Users"
            value={users.length}
            icon={Users}
            color="blue"
            description={`${activeUsers} active`}
          />
          <StatCard
            title="Built-in Roles"
            value={roles.filter(r => r.is_system).length}
            icon={Lock}
            color="purple"
            description="System roles"
          />
          <StatCard
            title="Custom Roles"
            value={customRoles}
            icon={Unlock}
            color="green"
            description="User-defined"
          />
          <StatCard
            title="Permission Categories"
            value={Object.keys(permissions).length}
            icon={Shield}
            color="amber"
            description="Access areas"
          />
        </div>
        
        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="users" data-testid="tab-users">
              <Users className="h-4 w-4 mr-2" />
              Users ({users.length})
            </TabsTrigger>
            <TabsTrigger value="roles" data-testid="tab-roles">
              <Shield className="h-4 w-4 mr-2" />
              Roles ({roles.length})
            </TabsTrigger>
          </TabsList>
          
          {/* Users Tab */}
          <TabsContent value="users" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Admin Users</CardTitle>
                <CardDescription>Manage user access and role assignments</CardDescription>
              </CardHeader>
              <CardContent>
                {users.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Last Login</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {users.map(user => (
                        <TableRow key={user.portal_user_id} data-testid={`user-row-${user.portal_user_id}`}>
                          <TableCell className="font-medium">{user.name}</TableCell>
                          <TableCell>{user.email}</TableCell>
                          <TableCell>
                            <Select
                              value={user.role_id || 'super_admin'}
                              onValueChange={v => handleChangeUserRole(user.portal_user_id, v)}
                            >
                              <SelectTrigger className="w-[160px]">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {roles.map(role => (
                                  <SelectItem key={role.role_id} value={role.role_id}>
                                    {role.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell>
                            <Badge variant={user.status === 'ACTIVE' ? 'default' : 'secondary'}>
                              {user.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm text-gray-500">
                            {user.last_login
                              ? new Date(user.last_login).toLocaleDateString()
                              : 'Never'}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleUser(user.portal_user_id, user.status)}
                              title={user.status === 'ACTIVE' ? 'Disable' : 'Enable'}
                            >
                              {user.status === 'ACTIVE' ? (
                                <XCircle className="h-4 w-4 text-red-500" />
                              ) : (
                                <CheckCircle className="h-4 w-4 text-green-500" />
                              )}
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <Users className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No admin users found</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
          
          {/* Roles Tab */}
          <TabsContent value="roles" className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Roles</CardTitle>
                <CardDescription>Built-in and custom roles with their permissions</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Role Name</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Users</TableHead>
                      <TableHead>Permissions</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {roles.map(role => (
                      <TableRow key={role.role_id} data-testid={`role-row-${role.role_id}`}>
                        <TableCell className="font-medium">{role.name}</TableCell>
                        <TableCell className="text-sm text-gray-500 max-w-[200px] truncate">
                          {role.description}
                        </TableCell>
                        <TableCell>
                          <Badge variant={role.is_system ? 'secondary' : 'outline'}>
                            {role.is_system ? 'Built-in' : 'Custom'}
                          </Badge>
                        </TableCell>
                        <TableCell>{role.user_count}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1 max-w-[200px]">
                            {Object.keys(role.permissions || {}).slice(0, 3).map(cat => (
                              <Badge key={cat} variant="outline" className="text-xs">
                                {cat}
                              </Badge>
                            ))}
                            {Object.keys(role.permissions || {}).length > 3 && (
                              <Badge variant="outline" className="text-xs">
                                +{Object.keys(role.permissions).length - 3} more
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEditRole(role)}
                              disabled={role.is_system}
                              title={role.is_system ? 'Built-in roles cannot be edited' : 'Edit'}
                            >
                              <Edit className="h-4 w-4" />
                            </Button>
                            {!role.is_system && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteRole(role.role_id)}
                                title="Delete"
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        
        {/* Create/Edit Role Dialog */}
        <Dialog open={showRoleDialog} onOpenChange={setShowRoleDialog}>
          <DialogContent className="sm:max-w-[700px] max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{editingRole ? 'Edit Role' : 'Create Custom Role'}</DialogTitle>
              <DialogDescription>
                Define permissions for this role
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-6 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Role Name *</Label>
                  <Input
                    value={roleForm.name}
                    onChange={e => setRoleForm({ ...roleForm, name: e.target.value })}
                    placeholder="e.g., Marketing Manager"
                    data-testid="role-name-input"
                  />
                </div>
                <div>
                  <Label>Description</Label>
                  <Input
                    value={roleForm.description}
                    onChange={e => setRoleForm({ ...roleForm, description: e.target.value })}
                    placeholder="Brief description"
                  />
                </div>
              </div>
              
              <div>
                <Label className="text-base font-semibold">Permissions</Label>
                <p className="text-sm text-gray-500 mb-4">Select the permissions for this role</p>
                
                <div className="space-y-4 border rounded-lg p-4 max-h-[300px] overflow-y-auto">
                  {Object.entries(permissions).map(([category, config]) => (
                    <div key={category} className="border-b pb-4 last:border-0">
                      <div className="flex items-center justify-between mb-2">
                        <div>
                          <p className="font-medium">{config.label}</p>
                          <p className="text-xs text-gray-500">{config.description}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {config.actions.map(action => (
                          <label
                            key={`${category}-${action}`}
                            className="flex items-center gap-2 px-3 py-1.5 border rounded cursor-pointer hover:bg-gray-50"
                          >
                            <Checkbox
                              checked={(roleForm.permissions[category] || []).includes(action)}
                              onCheckedChange={() => togglePermission(category, action)}
                            />
                            <span className="text-sm capitalize">{action}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowRoleDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleSaveRole} disabled={loading} data-testid="save-role-btn">
                {loading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                {editingRole ? 'Update Role' : 'Create Role'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Add User Dialog */}
        <Dialog open={showUserDialog} onOpenChange={setShowUserDialog}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Add Admin User</DialogTitle>
              <DialogDescription>
                Create a new admin user with assigned role
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              <div>
                <Label>Full Name *</Label>
                <Input
                  value={userForm.name}
                  onChange={e => setUserForm({ ...userForm, name: e.target.value })}
                  placeholder="John Smith"
                  data-testid="user-name-input"
                />
              </div>
              
              <div>
                <Label>Email Address *</Label>
                <Input
                  type="email"
                  value={userForm.email}
                  onChange={e => setUserForm({ ...userForm, email: e.target.value })}
                  placeholder="john@company.com"
                  data-testid="user-email-input"
                />
              </div>
              
              <div>
                <Label>Role *</Label>
                <Select
                  value={userForm.role_id}
                  onValueChange={v => setUserForm({ ...userForm, role_id: v })}
                >
                  <SelectTrigger data-testid="user-role-select">
                    <SelectValue placeholder="Select a role" />
                  </SelectTrigger>
                  <SelectContent>
                    {roles.map(role => (
                      <SelectItem key={role.role_id} value={role.role_id}>
                        {role.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex items-center justify-between">
                <div>
                  <Label>Send Invitation Email</Label>
                  <p className="text-xs text-gray-500">User will receive a password setup email</p>
                </div>
                <Switch
                  checked={userForm.send_invite}
                  onCheckedChange={v => setUserForm({ ...userForm, send_invite: v })}
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowUserDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateUser} disabled={loading} data-testid="save-user-btn">
                {loading ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : <UserPlus className="h-4 w-4 mr-2" />}
                Add User
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </UnifiedAdminLayout>
  );
}
