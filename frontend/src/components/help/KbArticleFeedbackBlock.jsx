/**
 * Helpful / not helpful feedback for a single KB article (public or client Help Centre).
 * Persists thanks state in localStorage; debounces submits; accessible controls.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import client from '../../api/client';
import { Button } from '../ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Textarea } from '../ui/textarea';
import { ThumbsDown, ThumbsUp, ChevronDown } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

const SESSION_KEY = 'cvp_kb_feedback_session_v1';

function getOrCreateSessionId() {
  if (typeof window === 'undefined') return 'server';
  try {
    let s = localStorage.getItem(SESSION_KEY);
    if (!s || s.length < 8) {
      s =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID()
          : `anon-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
      localStorage.setItem(SESSION_KEY, s);
    }
    return s;
  } catch {
    return `sess-${Date.now()}`;
  }
}

function voteStorageKey(mode, articleId) {
  return `cvp_kb_article_vote_${mode}_${articleId}`;
}

function readPersistedVote(mode, articleId) {
  try {
    const raw = localStorage.getItem(voteStorageKey(mode, articleId));
    if (!raw) return null;
    const o = JSON.parse(raw);
    if (!o || typeof o.at !== 'number') return null;
    // Re-show thanks for 30 days without re-submitting
    if (Date.now() - o.at > 30 * 24 * 60 * 60 * 1000) {
      localStorage.removeItem(voteStorageKey(mode, articleId));
      return null;
    }
    return o;
  } catch {
    return null;
  }
}

function persistVote(mode, articleId, feedbackType) {
  try {
    localStorage.setItem(
      voteStorageKey(mode, articleId),
      JSON.stringify({ feedback_type: feedbackType, at: Date.now() })
    );
  } catch {
    /* ignore quota */
  }
}

/**
 * @param {Object} props
 * @param {string} props.articleId
 * @param {'public' | 'client'} props.mode — public KB vs authenticated client Help Centre
 */
export default function KbArticleFeedbackBlock({ articleId, mode = 'public' }) {
  const persisted = typeof window !== 'undefined' ? readPersistedVote(mode, articleId) : null;
  const [done, setDone] = useState(!!persisted);
  const [submitting, setSubmitting] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const lastClickRef = useRef(0);

  useEffect(() => {
    const p = readPersistedVote(mode, articleId);
    if (p) {
      setDone(true);
    }
  }, [articleId, mode]);

  const submit = useCallback(
    async (feedbackType) => {
      if (!articleId || submitting || done) return;
      const now = Date.now();
      if (now - lastClickRef.current < 450) return;
      lastClickRef.current = now;

      setSubmitting(true);
      try {
        const path =
          mode === 'client'
            ? `/client/help/articles/${encodeURIComponent(articleId)}/feedback`
            : `/kb/articles/${encodeURIComponent(articleId)}/feedback`;

        const body =
          mode === 'client'
            ? { feedback_type: feedbackType }
            : { feedback_type: feedbackType, session_id: getOrCreateSessionId() };

        const res = await client.post(path, body);
        if (res.data?.duplicate) {
          setDone(true);
          persistVote(mode, articleId, feedbackType);
          toast.message('Thanks — your feedback was already recorded.');
        } else {
          setDone(true);
          persistVote(mode, articleId, feedbackType);
          toast.success('Thanks for your feedback.');
        }
      } catch (e) {
        toast.error('Unable to save feedback right now. Please try again later.');
      } finally {
        setSubmitting(false);
      }
    },
    [articleId, mode, submitting, done]
  );

  if (!articleId) return null;

  if (done) {
    return (
      <div
        className="rounded-lg border border-gray-200 bg-gray-50/80 px-4 py-4 text-gray-800"
        role="status"
        aria-live="polite"
        data-testid="kb-article-feedback-thanks"
      >
        <p className="text-sm font-medium text-gray-900">Thanks for your feedback</p>
        <Collapsible open={moreOpen} onOpenChange={setMoreOpen} className="mt-3">
          <CollapsibleTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-1 text-sm text-electric-teal hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-electric-teal rounded"
              aria-expanded={moreOpen}
            >
              <ChevronDown className={`h-4 w-4 transition-transform ${moreOpen ? 'rotate-180' : ''}`} />
              Tell us more
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2">
            <Textarea
              readOnly
              disabled
              placeholder="Optional written feedback will be available in a future update."
              className="min-h-[88px] resize-none bg-white text-gray-600 cursor-not-allowed"
              aria-label="Written feedback (coming soon)"
            />
          </CollapsibleContent>
        </Collapsible>
      </div>
    );
  }

  return (
    <div
      className="rounded-lg border border-gray-200 bg-gray-50/50 px-4 py-4"
      role="group"
      aria-label="Article helpfulness"
      data-testid="kb-article-feedback"
    >
      <p className="text-gray-700 text-sm font-medium mb-3">Was this article helpful?</p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={submitting}
          onClick={() => submit('helpful')}
          className="gap-1.5 min-h-10 min-w-[5.5rem] border-gray-300 hover:border-electric-teal hover:bg-teal-50/60 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-electric-teal"
          aria-label="Yes, this article was helpful"
        >
          <ThumbsUp className="h-4 w-4 shrink-0" aria-hidden />
          Yes
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={submitting}
          onClick={() => submit('not_helpful')}
          className="gap-1.5 min-h-10 min-w-[5.5rem] border-gray-300 hover:border-amber-600/50 hover:bg-amber-50/50 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-amber-600"
          aria-label="No, this article was not helpful"
        >
          <ThumbsDown className="h-4 w-4 shrink-0" aria-hidden />
          No
        </Button>
      </div>
      {submitting && (
        <p className="text-xs text-gray-500 mt-2" aria-live="polite">
          Sending…
        </p>
      )}
    </div>
  );
}
