import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Alert, AlertDescription } from '../components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Save, RotateCcw, FileText, AlertCircle, Check } from 'lucide-react';

const AdminLegalContentPage = () => {
  const [activeTab, setActiveTab] = useState('privacy');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  
  const [content, setContent] = useState({
    privacy: { slug: 'privacy', title: 'Privacy Policy', content: '', version: 0 },
    terms: { slug: 'terms', title: 'Terms of Service', content: '', version: 0 },
    cookies: { slug: 'cookies', title: 'Cookie Policy', content: '', version: 0 },
    accessibility: { slug: 'accessibility', title: 'Accessibility Statement', content: '', version: 0 },
    careers: { slug: 'careers', title: 'Careers', content: '', version: 0 },
    partnerships: { slug: 'partnerships', title: 'Partnerships', content: '', version: 0 },
    about: { slug: 'about', title: 'About Us', content: '', version: 0 },
  });

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    loadAllContent();
  }, []);

  const loadAllContent = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/admin/legal-content`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        const contentMap = {};
        data.forEach(item => {
          contentMap[item.slug] = item;
        });
        setContent(prev => ({ ...prev, ...contentMap }));
      }
    } catch (error) {
      console.error('Failed to load legal content:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (slug) => {
    setSaving(true);
    setMessage(null);

    try {
      const response = await fetch(`${API_URL}/api/admin/legal-content/${slug}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(content[slug])
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: `Saved! Version ${result.content.version}` });
        
        setContent(prev => ({
          ...prev,
          [slug]: result.content
        }));

        setTimeout(() => setMessage(null), 3000);
      } else {
        setMessage({ type: 'error', text: 'Failed to save. Please try again.' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error. Please try again.' });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (slug) => {
    if (!window.confirm(`Reset ${content[slug].title} to default content? This cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/api/admin/legal-content/${slug}/reset-default`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Reset to default content' });
        await loadAllContent();
      } else {
        setMessage({ type: 'error', text: 'Failed to reset' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Network error' });
    }
  };

  const updateField = (slug, field, value) => {
    setContent(prev => ({
      ...prev,
      [slug]: { ...prev[slug], [field]: value }
    }));
  };

  const tabs = [
    { value: 'privacy', label: 'Privacy Policy', icon: FileText, category: 'Legal' },
    { value: 'terms', label: 'Terms', icon: FileText, category: 'Legal' },
    { value: 'cookies', label: 'Cookies', icon: FileText, category: 'Legal' },
    { value: 'accessibility', label: 'Accessibility', icon: FileText, category: 'Legal' },
    { value: 'careers', label: 'Careers', icon: FileText, category: 'Marketing' },
    { value: 'partnerships', label: 'Partnerships', icon: FileText, category: 'Marketing' },
    { value: 'about', label: 'About Us', icon: FileText, category: 'Marketing' },
  ];

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-midnight-blue">Legal Content Management</h1>
          <p className="text-gray-600 mt-2">
            Edit legal pages. Changes apply instantly. All edits are audited.
          </p>
        </div>

        {message && (
          <Alert className={`mb-6 ${message.type === 'success' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
            {message.type === 'success' ? <Check className="h-4 w-4 text-green-600" /> : <AlertCircle className="h-4 w-4 text-red-600" />}
            <AlertDescription className={message.type === 'success' ? 'text-green-700' : 'text-red-700'}>
              {message.text}
            </AlertDescription>
          </Alert>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-7">
            {tabs.map(tab => (
              <TabsTrigger key={tab.value} value={tab.value} className="text-xs">
                <tab.icon className="w-4 h-4 mr-1" />
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {tabs.map(tab => (
            <TabsContent key={tab.value} value={tab.value}>
              <Card>
                <CardHeader>
                  <CardTitle>{content[tab.value].title}</CardTitle>
                  <CardDescription>
                    Version {content[tab.value].version} | Last updated: {content[tab.value].updated_at ? new Date(content[tab.value].updated_at).toLocaleString() : 'Never'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">Page Title</label>
                    <Input
                      value={content[tab.value].title}
                      onChange={(e) => updateField(tab.value, 'title', e.target.value)}
                      placeholder="Page title"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      Content (Markdown supported)
                    </label>
                    <Textarea
                      value={content[tab.value].content}
                      onChange={(e) => updateField(tab.value, 'content', e.target.value)}
                      placeholder="Enter legal content here..."
                      className="min-h-[400px] font-mono text-sm"
                    />
                    <p className="text-xs text-gray-500 mt-2">
                      {content[tab.value].content.length} characters
                    </p>
                  </div>

                  <div className="flex gap-3">
                    <Button
                      onClick={() => handleSave(tab.value)}
                      disabled={saving}
                      className="bg-electric-teal hover:bg-electric-teal/90"
                    >
                      <Save className="w-4 h-4 mr-2" />
                      {saving ? 'Saving...' : 'Save Changes'}
                    </Button>

                    <Button
                      onClick={() => handleReset(tab.value)}
                      variant="outline"
                      disabled={saving}
                    >
                      <RotateCcw className="w-4 h-4 mr-2" />
                      Reset to Default
                    </Button>
                  </div>

                  <div className="text-xs text-gray-500 mt-4 p-4 bg-gray-50 rounded">
                    <p className="font-semibold mb-2">⚠️ Important:</p>
                    <ul className="list-disc list-inside space-y-1">
                      <li>Changes apply immediately</li>
                      <li>All edits are logged</li>
                      <li>Version history preserved</li>
                    </ul>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminLegalContentPage;
