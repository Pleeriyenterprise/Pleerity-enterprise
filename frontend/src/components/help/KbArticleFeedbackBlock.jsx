/**
 * Helpful / not helpful feedback for a single KB article (public or client Help Centre).
 * Persists thanks state in localStorage; debounces submits; accessible controls.
 * Optional written note after vote via POST .../feedback/comment (same dedupe as thumbs).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import client from '../../api/client';
import { Button } from '../ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';
import { Textarea } from '../ui/textarea';
import { ThumbsDown, ThumbsUp, ChevronDown } from 'lucide-react';
import { toast } from '@/utils/portalNotifications';

const SESSION_KEY = 'cvp_kb_feedback_session_v1';
const COMMENT_MAX_LEN = 2000;

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
    const prev = readPersistedVote(mode, articleId) || {};
    localStorage.setItem(
      voteStorageKey(mode, articleId),
      JSON.stringify({
        ...prev,
        feedback_type: feedbackType,
        at: Date.now(),
      })
    );
  } catch {
    /* ignore quota */
  }
}

function persistCommentSubmitted(mode, articleId) {
  try {
    const key = voteStorageKey(mode, articleId);
    const raw = localStorage.getItem(key);
    if (!raw) return;
    const o = JSON.parse(raw);
    o.comment_submitted = true;
    o.comment_submitted_at = Date.now();
    localStorage.setItem(key, JSON.stringify(o));
  } catch {
    /* ignore */
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
  const [commentText, setCommentText] = useState('');
  const [commentSubmitting, setCommentSubmitting] = useState(false);
  const [commentSaved, setCommentSaved] = useState(!!persisted?.comment_submitted);
  const commentRef = useRef(null);
  const lastClickRef = useRef(0);

  useEffect(() => {
    const p = readPersistedVote(mode, articleId);
    if (p) {
      setDone(true);
      setCommentSaved(!!p.comment_submitted);
    }
  }, [articleId, mode]);

  useEffect(() => {
    if (!commentSaved && moreOpen && commentRef.current) {
      const t = window.requestAnimationFrame(() => commentRef.current?.focus());
      return () => window.cancelAnimationFrame(t);
    }
    return undefined;
  }, [moreOpen, commentSaved]);

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

  const submitComment = useCallback(async () => {
    const trimmed = commentText.trim();
    if (!trimmed || commentSubmitting || commentSaved || !articleId) return;

    setCommentSubmitting(true);
    try {
      const path =
        mode === 'client'
          ? `/client/help/articles/${encodeURIComponent(articleId)}/feedback/comment`
          : `/kb/articles/${encodeURIComponent(articleId)}/feedback/comment`;

      const body =
        mode === 'client'
          ? { comment: trimmed }
          : { comment: trimmed, session_id: getOrCreateSessionId() };

      const res = await client.post(path, body);
      persistCommentSubmitted(mode, articleId);
      setCommentSaved(true);
      setCommentText('');
      if (res.data?.duplicate) {
        toast.message('Your note was already saved.');
      } else {
        toast.success('Thanks — we received your note.');
      }
    } catch (e) {
      toast.error('Unable to save your note right now. Please try again later.');
    } finally {
      setCommentSubmitting(false);
    }
  }, [articleId, mode, commentText, commentSubmitting, commentSaved]);

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
              className="flex items-center gap-1 text-sm text-electric-teal hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-electric-teal rounded px-0.5 -mx-0.5 min-h-10"
              aria-expanded={moreOpen}
            >
              <ChevronDown className={`h-4 w-4 shrink-0 transition-transform ${moreOpen ? 'rotate-180' : ''}`} aria-hidden />
              Tell us more
            </button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 overflow-hidden">
            {commentSaved ? (
              <p className="text-sm text-gray-600 rounded-md border border-dashed border-gray-300 bg-gray-100/80 px-3 py-3">
                Thanks — we've saved your note. Your thumbs feedback stays on record for this article.
              </p>
            ) : (
              <div className="space-y-2">
                <label htmlFor={`kb-feedback-comment-${articleId}`} className="sr-only">
                  Optional written feedback about this article
                </label>
                <Textarea
                  ref={commentRef}
                  id={`kb-feedback-comment-${articleId}`}
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value.slice(0, COMMENT_MAX_LEN))}
                  placeholder="What would make this article clearer? (optional)"
                  maxLength={COMMENT_MAX_LEN}
                  rows={4}
                  className="min-h-[96px] resize-y bg-white text-gray-900 border-gray-300 focus-visible:ring-2 focus-visible:ring-electric-teal"
                  aria-label="Optional written feedback about this article"
                  disabled={commentSubmitting}
                />
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={commentSubmitting || !commentText.trim()}
                    onClick={() => submitComment()}
                    className="min-h-10 focus-visible:ring-2 focus-visible:ring-electric-teal"
                  >
                    {commentSubmitting ? 'Sending…' : 'Send note'}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={commentSubmitting}
                    className="min-h-10"
                    onClick={() => setMoreOpen(false)}
                  >
                    Cancel
                  </Button>
                  <span className="text-xs text-gray-500 ml-auto" aria-live="polite">
                    {commentText.length}/{COMMENT_MAX_LEN}
                  </span>
                </div>
              </div>
            )}
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
