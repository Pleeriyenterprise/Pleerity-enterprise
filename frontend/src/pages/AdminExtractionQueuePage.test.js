/**
 * Admin Extraction Review Queue: queue loads, confirm calls admin confirm API, UI refreshes.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AdminExtractionQueuePage from './AdminExtractionQueuePage';
import api from '../api/client';

jest.mock('../api/client', () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

describe('AdminExtractionQueuePage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    api.get.mockResolvedValue({
      data: {
        items: [
          {
            extraction_id: 'ext-1',
            document_id: 'doc-1',
            client_id: 'client-1',
            file_name: 'gas-cert.pdf',
            status: 'NEEDS_REVIEW',
            extracted: { doc_type: 'GAS_SAFETY', expiry_date: '2026-06-01' },
            updated_at: '2025-02-20T12:00:00Z',
          },
        ],
      },
    });
  });

  it('loads extraction queue and shows table with status badge', async () => {
    render(<AdminExtractionQueuePage />);
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/documents/admin/extraction-queue');
    });
    await waitFor(() => {
      expect(screen.getByTestId('extraction-queue-table')).toBeInTheDocument();
    });
    expect(screen.getByText('Extraction Review Queue')).toBeInTheDocument();
    expect(screen.getByText('NEEDS_REVIEW')).toBeInTheDocument();
    expect(screen.getByText(/gas-cert\.pdf/)).toBeInTheDocument();
  });

  it('confirm calls admin confirm endpoint and refreshes queue', async () => {
    api.post.mockResolvedValue({ data: { message: 'Extraction applied', document_id: 'doc-1' } });
    render(<AdminExtractionQueuePage />);
    await waitFor(() => {
      expect(screen.getByTestId('extraction-queue-table')).toBeInTheDocument();
    });
    const confirmBtn = screen.getByTestId('confirm-extraction-doc-1');
    fireEvent.click(confirmBtn);
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/documents/admin/extraction-queue/confirm', { document_id: 'doc-1' });
    });
    await waitFor(() => {
      expect(api.get).toHaveBeenCalledTimes(2); // initial + refresh after confirm
    });
  });

  it('reject calls admin reject endpoint', async () => {
    api.post.mockResolvedValue({ data: { message: 'Extraction rejected', document_id: 'doc-1' } });
    render(<AdminExtractionQueuePage />);
    await waitFor(() => {
      expect(screen.getByTestId('extraction-queue-table')).toBeInTheDocument();
    });
    const rejectBtn = screen.getByTestId('reject-extraction-doc-1');
    fireEvent.click(rejectBtn);
    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/documents/admin/extraction-queue/reject', {
        document_id: 'doc-1',
        reason: 'Admin rejected',
      });
    });
  });
});
