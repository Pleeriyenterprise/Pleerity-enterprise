/**
 * Items 7–8 (UI): Yes/No submit, success/thanks state, localStorage persistence on remount.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import KbArticleFeedbackBlock from './KbArticleFeedbackBlock';
import client from '../../api/client';
import { toast } from '@/utils/portalNotifications';

jest.mock('@/utils/portalNotifications', () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
    message: jest.fn(),
  },
}));

describe('KbArticleFeedbackBlock', () => {
  const articleId = 'kb-test-article-001';
  const mode = 'public';
  let postSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    postSpy = jest.spyOn(client, 'post').mockResolvedValue({
      data: { ok: true, duplicate: false, totals: { total: 1, helpful: 1, not_helpful: 0, helpful_pct: 100 } },
    });
  });

  afterEach(() => {
    postSpy.mockRestore();
  });

  it('clicking Yes calls feedback API and shows thanks (item 7)', async () => {
    render(<KbArticleFeedbackBlock articleId={articleId} mode={mode} />);

    fireEvent.click(screen.getByRole('button', { name: /yes, this article was helpful/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        `/kb/articles/${encodeURIComponent(articleId)}/feedback`,
        expect.objectContaining({ feedback_type: 'helpful', session_id: expect.any(String) })
      );
    });
    await waitFor(() => {
      expect(screen.getByTestId('kb-article-feedback-thanks')).toBeInTheDocument();
    });
    expect(toast.success).toHaveBeenCalled();
    expect(screen.getByText('Thanks for your feedback')).toBeInTheDocument();
  });

  it('Tell us more: textarea is editable and POSTs feedback comment', async () => {
    postSpy.mockImplementation((url) => {
      if (String(url).includes('/feedback/comment')) {
        return Promise.resolve({ data: { ok: true, duplicate: false } });
      }
      return Promise.resolve({
        data: { ok: true, duplicate: false, totals: { total: 1, helpful: 1, not_helpful: 0, helpful_pct: 100 } },
      });
    });

    render(<KbArticleFeedbackBlock articleId={articleId} mode={mode} />);

    fireEvent.click(screen.getByRole('button', { name: /yes, this article was helpful/i }));

    await waitFor(() => {
      expect(screen.getByTestId('kb-article-feedback-thanks')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /tell us more/i }));

    const ta = screen.getByRole('textbox', { name: /optional written feedback about this article/i });
    expect(ta).not.toBeDisabled();

    fireEvent.change(ta, { target: { value: 'Needs clearer steps' } });

    fireEvent.click(screen.getByRole('button', { name: /^send note$/i }));

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        `/kb/articles/${encodeURIComponent(articleId)}/feedback/comment`,
        expect.objectContaining({ comment: 'Needs clearer steps', session_id: expect.any(String) })
      );
    });
    expect(toast.success).toHaveBeenCalled();
  });

  it('remount shows thanks from localStorage without calling API again (item 8)', async () => {
    const key = `cvp_kb_article_vote_${mode}_${articleId}`;
    localStorage.setItem(key, JSON.stringify({ feedback_type: 'helpful', at: Date.now() }));

    render(<KbArticleFeedbackBlock articleId={articleId} mode={mode} />);

    expect(screen.getByTestId('kb-article-feedback-thanks')).toBeInTheDocument();
    expect(postSpy).not.toHaveBeenCalled();
  });
});
