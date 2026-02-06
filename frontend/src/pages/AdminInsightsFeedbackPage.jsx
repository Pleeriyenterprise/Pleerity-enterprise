import React, { useState, useEffect } from 'react';
import UnifiedAdminLayout from '../components/admin/UnifiedAdminLayout';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { ThumbsUp, ThumbsDown, MessageSquare } from 'lucide-react';

const AdminInsightsFeedbackPage = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const API = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => { load(); }, []);

  const load = async () => {
    try {
      const res = await fetch(`${API}/api/admin/feedback/list`, { headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` } });
      if (res.ok) setData(await res.json());
    } catch(e) {}
    finally { setLoading(false); }
  };

  const colors = {'NEW':'bg-blue-100 text-blue-700','REVIEWED':'bg-gray-100 text-gray-700','ACTIONED':'bg-green-100 text-green-700','ARCHIVED':'bg-gray-100 text-gray-500'};

  return (
    <UnifiedAdminLayout>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold mb-2">Insights Feedback</h1>
        <p className="text-gray-600 mb-8">User feedback on blog articles and insights</p>

        <Card>
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold">Date</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Article</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Helpful?</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Comment</th>
                <th className="px-4 py-3 text-left text-xs font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {loading ? <tr><td colSpan="5" className="px-4 py-8 text-center">Loading...</td></tr> :
              data.length === 0 ? <tr><td colSpan="5" className="px-4 py-8 text-center">No feedback</td></tr> :
              data.map(f => (
                <tr key={f.feedback_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm">{new Date(f.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-sm">{f.article_title}</td>
                  <td className="px-4 py-3">{f.was_helpful ? <ThumbsUp className="w-4 h-4 text-green-600"/> : <ThumbsDown className="w-4 h-4 text-red-600"/>}</td>
                  <td className="px-4 py-3 text-sm text-gray-600">{f.comment || '-'}</td>
                  <td className="px-4 py-3"><Badge className={colors[f.status]}>{f.status}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </UnifiedAdminLayout>
  );
};

export default AdminInsightsFeedbackPage;
