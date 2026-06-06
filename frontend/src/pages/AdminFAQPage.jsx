import React, { useState, useMemo } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Plus, Edit, Trash, Save, X, RefreshCw } from 'lucide-react';
import { adminAPI } from '../api/client';
import { useAuthenticatedQuery } from '../hooks/useAuthenticatedQuery';
import { classifyAxiosError } from '../utils/adminFetchState';

const EMPTY_FORM = { category: '', question: '', answer: '', is_active: true, display_order: 0 };

const AdminFAQPage = () => {
  const { data, loading, error, reload } = useAuthenticatedQuery(() => adminAPI.listFaqsAdmin(), []);
  const faqs = useMemo(() => (Array.isArray(data) ? data : []), [data]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saveError, setSaveError] = useState(null);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      if (editing) {
        await adminAPI.updateFaq(editing, form);
      } else {
        await adminAPI.createFaq(form);
      }
      setForm(EMPTY_FORM);
      setEditing(null);
      reload();
    } catch (err) {
      setSaveError(classifyAxiosError(err));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id) => {
    if (!window.confirm('Delete FAQ?')) return;
    setSaveError(null);
    try {
      await adminAPI.deleteFaq(id);
      reload();
    } catch (err) {
      setSaveError(classifyAxiosError(err));
    }
  };

  const edit = (faq) => {
    setForm(faq);
    setEditing(faq.faq_id);
    setSaveError(null);
  };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-start mb-2">
          <div>
            <h1 className="text-3xl font-bold mb-2">FAQ Management</h1>
            <p className="text-gray-600 mb-8">Manage FAQ items — updates reflect on public FAQ page instantly</p>
          </div>
          <Button variant="outline" onClick={reload} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg text-amber-900 text-sm flex flex-wrap justify-between gap-2">
            <span>{error.message}</span>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={reload}>
                Retry
              </Button>
              {error.kind === 'auth_failure' && (
                <Button variant="outline" size="sm" onClick={() => { window.location.href = '/login/admin'; }}>
                  Sign in
                </Button>
              )}
            </div>
          </div>
        )}

        {saveError && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-900 text-sm">
            {saveError.message}
          </div>
        )}

        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>{editing ? 'Edit FAQ' : 'Add New FAQ'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Category</Label>
                <Input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="General" />
              </div>
              <div>
                <Label>Question</Label>
                <Input value={form.question} onChange={(e) => setForm({ ...form, question: e.target.value })} />
              </div>
              <div>
                <Label>Answer</Label>
                <Textarea value={form.answer} onChange={(e) => setForm({ ...form, answer: e.target.value })} className="min-h-[100px]" />
              </div>
              <div>
                <Label>Display Order</Label>
                <Input
                  type="number"
                  value={form.display_order}
                  onChange={(e) => setForm({ ...form, display_order: parseInt(e.target.value, 10) || 0 })}
                />
              </div>
              <div className="flex items-center space-x-2">
                <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
                <label className="text-sm">Active</label>
              </div>
              <div className="flex gap-2">
                <Button onClick={save} disabled={saving} className="bg-electric-teal hover:bg-electric-teal/90">
                  <Save className="w-4 h-4 mr-2" />
                  {editing ? 'Update' : 'Add'}
                </Button>
                {editing && (
                  <Button
                    onClick={() => {
                      setEditing(null);
                      setForm(EMPTY_FORM);
                    }}
                    variant="outline"
                  >
                    <X className="w-4 h-4 mr-2" />
                    Cancel
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>FAQ Items ({loading ? '…' : faqs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {loading ? (
                <p className="text-sm text-gray-500 py-8 text-center">Loading…</p>
              ) : !error && faqs.length === 0 ? (
                <p className="text-sm text-gray-500 py-8 text-center">No FAQ items yet.</p>
              ) : (
                <div className="space-y-3 max-h-[600px] overflow-y-auto">
                  {faqs.map((f) => (
                    <div key={f.faq_id} className="border rounded p-3">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1">
                          <div className="text-xs text-gray-500">{f.category}</div>
                          <div className="font-semibold text-sm">{f.question}</div>
                          <div className="text-sm text-gray-600 mt-1">{f.answer.substring(0, 80)}…</div>
                        </div>
                        <div className="flex gap-1">
                          <Button size="sm" variant="outline" onClick={() => edit(f)}>
                            <Edit className="w-3 h-3" />
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => remove(f.faq_id)}>
                            <Trash className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>
                      <div className="text-xs text-gray-400">
                        Order: {f.display_order} | {f.is_active ? 'Active' : 'Inactive'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminFAQPage;
