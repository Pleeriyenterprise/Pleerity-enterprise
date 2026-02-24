/**
 * Lead magnet modal: Download Free UK Landlord Compliance Checklist.
 * Captures email + consent, calls backend, redirects to thank-you page.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { toast } from 'sonner';
import api from '../../api/client';

const DISCLAIMER =
  'This checklist provides general information only and does not constitute legal advice. Requirements may vary by property type and local authority.';

export default function ChecklistDownloadModal({ open, onOpenChange }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [consent, setConsent] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error('Please enter your email.');
      return;
    }
    if (!consent) {
      toast.error('Please agree to receive the checklist.');
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post('/leads/capture/compliance-checklist', {
        email: email.trim(),
        marketing_consent: consent,
      });
      if (data.success && data.redirect_url) {
        onOpenChange?.(false);
        navigate(data.redirect_url);
      } else {
        toast.success(data.message || 'Thank you. Your checklist is ready.');
        onOpenChange?.(false);
      }
    } catch (err) {
      const msg = err.response?.data?.detail?.message || err.response?.data?.detail || err.message;
      toast.error(msg || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-xl font-bold text-midnight-blue">
            Download Free UK Landlord Compliance Checklist
          </DialogTitle>
          <DialogDescription className="text-gray-600">
            Enter your email to get the checklist. We&apos;ll send you a link to download the PDF.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="checklist-email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <Input
              id="checklist-email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full"
              required
              disabled={loading}
            />
          </div>
          <div className="flex items-start gap-3">
            <input
              id="checklist-consent"
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-electric-teal focus:ring-electric-teal"
              required
              disabled={loading}
            />
            <label htmlFor="checklist-consent" className="text-sm text-gray-700">
              I agree to receive the checklist and relevant updates from Pleerity.
            </label>
          </div>
          <p className="text-xs text-gray-500 italic">
            {DISCLAIMER}
          </p>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange?.(false)}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button type="submit" className="bg-electric-teal hover:bg-electric-teal/90" disabled={loading}>
              {loading ? 'Sending…' : 'Download Checklist'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
