/**
 * View Order Page (public, no login)
 * Token-based access from delivery email. Shows order summary and document download links.
 */
import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { FileText, Download, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function ViewOrderPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) {
      setError('Invalid or missing link. Use the link from your delivery email.');
      setLoading(false);
      return;
    }
    const fetchOrder = async () => {
      try {
        const res = await fetch(`${API_URL}/api/public/orders/view?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.detail || res.statusText || 'Failed to load order');
        }
        const json = await res.json();
        setData(json);
      } catch (e) {
        setError(e.message || 'Failed to load order');
      } finally {
        setLoading(false);
      }
    };
    fetchOrder();
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-[40vh] flex items-center justify-center p-6">
        <div className="flex flex-col items-center gap-3 text-gray-600">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p>Loading your order...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-lg mx-auto p-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-700">
              <AlertCircle className="h-5 w-5" />
              Unable to load order
            </CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-600">
              If you received this link by email, it may have expired or already been used.
              Please contact support if you need access to your documents.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const statusLabel = data?.status?.replace(/_/g, ' ') || data?.status;
  const isComplete = data?.status === 'COMPLETED' || data?.status === 'DELIVERING';

  return (
    <div className="max-w-2xl mx-auto p-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {isComplete ? (
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            ) : (
              <FileText className="h-5 w-5 text-gray-500" />
            )}
            Your order
          </CardTitle>
          <CardDescription>
            Order reference: <span className="font-mono">{data?.order_id}</span>
            {data?.service_name && (
              <> · {data.service_name}</>
            )}
          </CardDescription>
          <div className="pt-2">
            <Badge variant={isComplete ? 'default' : 'secondary'}>
              {statusLabel}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {data?.message && !data?.documents_available && (
            <p className="text-sm text-gray-600">{data.message}</p>
          )}
          {data?.documents_available && data?.documents?.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-medium text-sm text-gray-700">Download your documents</h3>
              <ul className="space-y-2">
                {data.documents.map((doc) => {
                  const href = doc.download_url?.startsWith('http') ? doc.download_url : `${API_URL}${doc.download_path || doc.download_url || ''}`;
                  return (
                    <li key={`${doc.version}-${doc.format}`}>
                      <Button
                        variant="outline"
                        className="w-full justify-start gap-2"
                        asChild
                      >
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          download
                        >
                          <Download className="h-4 w-4" />
                          {doc.label}
                        </a>
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
