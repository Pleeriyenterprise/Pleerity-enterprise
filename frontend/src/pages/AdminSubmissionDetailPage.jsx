import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ArrowLeft, Copy, AlertTriangle, MessageSquare } from 'lucide-react';

const SUBMISSION_TYPES = ['contact', 'talent', 'partnership', 'lead'];

const STATUS_OPTIONS_BY_TYPE = {
  contact: ['NEW', 'IN_PROGRESS', 'RESPONDED', 'CLOSED', 'SPAM'],
  talent: ['NEW', 'REVIEWED', 'SHORTLISTED', 'ARCHIVED', 'SPAM'],
  partnership: ['NEW', 'REVIEWED', 'APPROVED', 'REJECTED', 'ARCHIVED', 'SPAM'],
  lead: ['ACTIVE', 'CONVERTED', 'LOST', 'MERGED', 'UNSUBSCRIBED'],
};

const SubmissionDetailPage = () => {
  const { type, id } = useParams();
  const navigate = useNavigate();
  const [submission, setSubmission] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [note, setNote] = useState('');
  const [status, setStatus] = useState('');
  const [tags, setTags] = useState([]);
  const [tagsInput, setTagsInput] = useState('');
  const [updating, setUpdating] = useState(false);
  const [markSpamConfirm, setMarkSpamConfirm] = useState(false);
  const API = process.env.REACT_APP_BACKEND_URL;

  const compositeId = type && id ? `${type}-${id}` : null;

  const load = useCallback(async () => {
    if (!compositeId || !SUBMISSION_TYPES.includes(type)) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/submissions/${encodeURIComponent(compositeId)}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (!res.ok) {
        if (res.status === 404) setError('Submission not found');
        else setError('Failed to load');
        return;
      }
      const data = await res.json();
      setSubmission(data);
      setStatus(data.status || '');
      setTags(Array.isArray(data.tags) ? [...data.tags] : []);
    } catch (e) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  }, [API, compositeId, type]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCopy = (text, label) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    // Could add toast
  };

  const handlePatch = async (body) => {
    if (!body || Object.keys(body).length === 0) return;
    setUpdating(true);
    try {
      const res = await fetch(`${API}/api/admin/submissions/${encodeURIComponent(compositeId)}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(body),
      });
      if (res.ok) await load();
    } finally {
      setUpdating(false);
    }
  };

  const handleSaveStatus = () => {
    if (status === (submission?.status ?? '')) return;
    handlePatch({ status });
  };
  const handleAddTag = () => {
    const t = tagsInput.trim();
    if (!t || tags.includes(t)) return;
    const next = [...tags, t];
    setTags(next);
    setTagsInput('');
    handlePatch({ tags: next });
  };
  const handleRemoveTag = (t) => {
    const next = tags.filter((x) => x !== t);
    setTags(next);
    handlePatch({ tags: next });
  };

  const handleAddNote = async () => {
    if (!compositeId || !note.trim()) return;
    setUpdating(true);
    try {
      const res = await fetch(`${API}/api/admin/submissions/${encodeURIComponent(compositeId)}/notes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({ note: note.trim() }),
      });
      if (res.ok) {
        setNote('');
        await load();
      }
    } finally {
      setUpdating(false);
    }
  };

  const handleMarkSpam = async () => {
    if (!compositeId || !markSpamConfirm) return;
    setUpdating(true);
    try {
      const res = await fetch(`${API}/api/admin/submissions/${encodeURIComponent(compositeId)}/mark-spam`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      if (res.ok) {
        setMarkSpamConfirm(false);
        await load();
      }
    } finally {
      setUpdating(false);
    }
  };

  if (!type || !id || !SUBMISSION_TYPES.includes(type)) {
    return (
      <UnifiedAdminLayout>
        <div className="max-w-4xl mx-auto px-4 py-8">
          <p className="text-gray-600">Invalid submission route.</p>
          <Button variant="outline" className="mt-4" onClick={() => navigate(-1)}>Back</Button>
        </div>
      </UnifiedAdminLayout>
    );
  }

  const backHref = type === 'contact' ? '/admin/inbox/enquiries' : type === 'talent' ? '/admin/talent-pool' : type === 'partnership' ? '/admin/partnership-enquiries' : '/admin/leads';

  return (
    <UnifiedAdminLayout>
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Button variant="ghost" className="mb-4 -ml-2" onClick={() => navigate(backHref)}>
          <ArrowLeft className="w-4 h-4 mr-2" /> Back
        </Button>

        {loading && <p className="text-gray-600">Loading...</p>}
        {error && <p className="text-red-600">{error}</p>}
        {!loading && !error && submission && (
          <>
            <div className="flex items-center gap-2 mb-6">
              <Badge variant="outline">{type}</Badge>
              <Badge>{submission.status}</Badge>
              <span className="text-sm text-gray-500">
                {submission.created_at ? new Date(submission.created_at).toLocaleString() : ''}
              </span>
            </div>

            <Card className="p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Contact</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <span className="text-xs text-gray-500">Name</span>
                  <p className="font-medium flex items-center gap-2">
                    {submission.full_name ?? submission.name ?? '-'}
                    <Button size="sm" variant="ghost" onClick={() => handleCopy(submission.full_name || submission.name, 'Name')}>
                      <Copy className="w-3 h-3" />
                    </Button>
                  </p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Email</span>
                  <p className="font-medium flex items-center gap-2">
                    {submission.email ?? submission.work_email ?? '-'}
                    <Button size="sm" variant="ghost" onClick={() => handleCopy(submission.email || submission.work_email, 'Email')}>
                      <Copy className="w-3 h-3" />
                    </Button>
                  </p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Phone</span>
                  <p className="font-medium flex items-center gap-2">
                    {submission.phone ?? '-'}
                    <Button size="sm" variant="ghost" onClick={() => handleCopy(submission.phone, 'Phone')}>
                      <Copy className="w-3 h-3" />
                    </Button>
                  </p>
                </div>
                {(submission.company_name || submission.org_description) && (
                  <div>
                    <span className="text-xs text-gray-500">Company / Org</span>
                    <p className="font-medium">{submission.company_name || submission.org_description || '-'}</p>
                  </div>
                )}
              </div>
            </Card>

            <Card className="p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Message</h2>
              {submission.subject && <p className="text-sm text-gray-600 mb-2"><strong>Subject:</strong> {submission.subject}</p>}
              <div className="whitespace-pre-wrap text-sm border rounded p-4 bg-gray-50">
                {submission.message ?? submission.professional_summary ?? submission.problem_solved ?? submission.additional_notes ?? submission.message_summary ?? '—'}
              </div>
              {submission.admin_reply && (
                <div className="mt-4">
                  <span className="text-xs text-gray-500">Admin reply</span>
                  <div className="whitespace-pre-wrap text-sm border rounded p-4 bg-blue-50 mt-1">{submission.admin_reply}</div>
                </div>
              )}
            </Card>

            <Card className="p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4">Actions</h2>
              <div className="flex flex-wrap gap-4 items-center mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">Status</span>
                  <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {(STATUS_OPTIONS_BY_TYPE[type] || ['NEW', 'CLOSED', 'SPAM']).map(s => (
                        <SelectItem key={s} value={s}>{s}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button size="sm" onClick={handleSaveStatus} disabled={updating || status === submission.status}>Update</Button>
                </div>
                {submission.status !== 'SPAM' && (
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="destructive" onClick={() => setMarkSpamConfirm(true)} disabled={updating}>
                      <AlertTriangle className="w-4 h-4 mr-1" /> Mark spam
                    </Button>
                    {markSpamConfirm && (
                      <>
                        <span className="text-sm">Confirm?</span>
                        <Button size="sm" variant="destructive" onClick={handleMarkSpam} disabled={updating}>Yes</Button>
                        <Button size="sm" variant="outline" onClick={() => setMarkSpamConfirm(false)}>No</Button>
                      </>
                    )}
                  </div>
                )}
              </div>
              {(submission.tags || tags.length > 0) && (
                <div className="mt-4 pt-4 border-t">
                  <span className="text-sm text-gray-600 block mb-2">Tags</span>
                  <div className="flex flex-wrap gap-2 items-center">
                    {(tags.length ? tags : submission.tags || []).map((t) => (
                      <Badge key={t} variant="secondary" className="flex items-center gap-1">
                        {t}
                        <button type="button" className="ml-1 hover:text-destructive" onClick={() => handleRemoveTag(t)} aria-label={`Remove ${t}`}>×</button>
                      </Badge>
                    ))}
                    <Input
                      placeholder="Add tag..."
                      value={tagsInput}
                      onChange={(e) => setTagsInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                      className="w-32 h-8 text-sm"
                    />
                    <Button size="sm" variant="outline" onClick={handleAddTag} disabled={!tagsInput.trim() || updating}>Add</Button>
                  </div>
                </div>
              )}
              {!(submission.tags || tags.length > 0) && (
                <div className="mt-4 pt-4 border-t">
                  <span className="text-sm text-gray-600 block mb-2">Tags</span>
                  <div className="flex flex-wrap gap-2 items-center">
                    <Input
                      placeholder="Add tag..."
                      value={tagsInput}
                      onChange={(e) => setTagsInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                      className="w-32 h-8 text-sm"
                    />
                    <Button size="sm" variant="outline" onClick={handleAddTag} disabled={!tagsInput.trim() || updating}>Add</Button>
                  </div>
                </div>
              )}
            </Card>

            <Card className="p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2"><MessageSquare className="w-4 h-4" /> Notes</h2>
              <div className="flex gap-2 mb-4">
                <Textarea placeholder="Add a note..." value={note} onChange={e => setNote(e.target.value)} rows={2} className="flex-1" />
                <Button onClick={handleAddNote} disabled={updating || !note.trim()}>Add</Button>
              </div>
              <ul className="space-y-2">
                {(submission.notes || []).map((n, i) => (
                  <li key={i} className="text-sm border-l-2 pl-3 py-1 border-gray-200">
                    <span className="text-gray-500">{n.by} · {n.at ? new Date(n.at).toLocaleString() : ''}</span>
                    <p className="mt-1">{n.note}</p>
                  </li>
                ))}
                {(!submission.notes || submission.notes.length === 0) && <li className="text-gray-500 text-sm">No notes yet.</li>}
              </ul>
            </Card>

            {submission.audit && submission.audit.length > 0 && (
              <Card className="p-6">
                <h2 className="text-lg font-semibold mb-4">Audit</h2>
                <ul className="space-y-2 text-sm">
                  {submission.audit.map((a, i) => (
                    <li key={i} className="text-gray-600">
                      {a.at ? new Date(a.at).toLocaleString() : ''} — {a.by} {a.action ? `· ${a.action}` : ''} {a.changes ? JSON.stringify(a.changes) : ''}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </>
        )}
      </div>
    </UnifiedAdminLayout>
  );
};

export default SubmissionDetailPage;
