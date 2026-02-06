import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/card';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Plus, Edit, Trash, Save, X } from 'lucide-react';

const AdminFAQPage = () => {
  const [faqs, setFaqs] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ category: '', question: '', answer: '', is_active: true, display_order: 0 });
  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => { load(); }, []);

  const load = async () => {
    const res = await fetch(`${API}/api/admin/faqs/admin`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
    if (res.ok) setFaqs(await res.json());
  };

  const save = async () => {
    const endpoint = editing ? `${API}/api/admin/faqs/${editing}` : `${API}/api/admin/faqs`;
    const method = editing ? 'PUT' : 'POST';
    const res = await fetch(endpoint, { method, headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('token')}` }, body: JSON.stringify(form) });
    if (res.ok) { load(); setForm({ category: '', question: '', answer: '', is_active: true, display_order: 0 }); setEditing(null); }
  };

  const remove = async (id) => {
    if (!confirm('Delete FAQ?')) return;
    await fetch(`${API}/api/admin/faqs/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
    load();
  };

  const edit = (faq) => { setForm(faq); setEditing(faq.faq_id); };

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">FAQ Management</h1>
        <p className="text-gray-600 mb-8">Manage FAQ items - updates reflect on public FAQ page instantly</p>

        <div className="grid lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader><CardTitle>{editing ? 'Edit FAQ' : 'Add New FAQ'}</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div><Label>Category</Label><Input value={form.category} onChange={e => setForm({...form, category: e.target.value})} placeholder="General" /></div>
              <div><Label>Question</Label><Input value={form.question} onChange={e => setForm({...form, question: e.target.value})} /></div>
              <div><Label>Answer</Label><Textarea value={form.answer} onChange={e => setForm({...form, answer: e.target.value})} className="min-h-[100px]" /></div>
              <div><Label>Display Order</Label><Input type="number" value={form.display_order} onChange={e => setForm({...form, display_order: parseInt(e.target.value)})} /></div>
              <div className="flex items-center space-x-2">
                <input type="checkbox" checked={form.is_active} onChange={e => setForm({...form, is_active: e.target.checked})} />
                <label className="text-sm">Active</label>
              </div>
              <div className="flex gap-2">
                <Button onClick={save} className="bg-electric-teal hover:bg-electric-teal/90"><Save className="w-4 h-4 mr-2"/>{editing ? 'Update' : 'Add'}</Button>
                {editing && <Button onClick={() => {setEditing(null); setForm({category:'',question:'',answer:'',is_active:true,display_order:0});}} variant="outline"><X className="w-4 h-4 mr-2"/>Cancel</Button>}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>FAQ Items ({faqs.length})</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {faqs.map(f => (
                  <div key={f.faq_id} className="border rounded p-3">
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex-1">
                        <div className="text-xs text-gray-500">{f.category}</div>
                        <div className="font-semibold text-sm">{f.question}</div>
                        <div className="text-sm text-gray-600 mt-1">{f.answer.substring(0,80)}...</div>
                      </div>
                      <div className="flex gap-1">
                        <Button size="sm" variant="outline" onClick={() => edit(f)}><Edit className="w-3 h-3"/></Button>
                        <Button size="sm" variant="outline" onClick={() => remove(f.faq_id)}><Trash className="w-3 h-3"/></Button>
                      </div>
                    </div>
                    <div className="text-xs text-gray-400">Order: {f.display_order} | {f.is_active ? 'Active' : 'Inactive'}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminFAQPage;
