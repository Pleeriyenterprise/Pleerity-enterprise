/**
 * Compliance Vault Assistant: chat renders, property scope selector, sources list when citations present.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import AssistantPage from './AssistantPage';
import axios from 'axios';

jest.mock('axios');
jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'test@test.com' }, logout: jest.fn() }),
}));

describe('AssistantPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    axios.get.mockResolvedValue({ data: { properties: [{ property_id: 'prop-1', nickname: 'Property 1', postcode: 'SW1A 1AA' }] } });
  });

  it('renders chat and disclaimer', async () => {
    render(<AssistantPage />);
    await waitFor(() => {
      expect(screen.getByTestId('assistant-disclaimer')).toBeInTheDocument();
    });
    expect(screen.getByTestId('chat-messages')).toBeInTheDocument();
    expect(screen.getByTestId('assistant-input')).toBeInTheDocument();
  });

  it('renders property scope selector', async () => {
    render(<AssistantPage />);
    await waitFor(() => {
      expect(screen.getByTestId('assistant-scope')).toBeInTheDocument();
    });
    const scope = screen.getByTestId('assistant-scope');
    expect(scope).toHaveValue('');
    expect(scope.tagName).toBe('SELECT');
  });

  it('calls chat with message and optional property_id', async () => {
    axios.post.mockResolvedValue({
      data: {
        conversation_id: 'conv-1',
        answer: 'Your gas safety expires in 2026.',
        citations: [],
        safety_flags: {},
      },
    });
    render(<AssistantPage />);
    await waitFor(() => {
      expect(screen.getByTestId('assistant-input')).toBeInTheDocument();
    });
    const input = screen.getByPlaceholderText(/Ask about your compliance/i);
    const scope = screen.getByTestId('assistant-scope');
    fireEvent.change(scope, { target: { value: 'prop-1' } });
    fireEvent.change(input, { target: { value: 'When is my gas safety expiry?' } });
    const btn = screen.getByTestId('send-question-btn');
    fireEvent.click(btn);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/assistant/chat'),
        expect.objectContaining({
          message: 'When is my gas safety expiry?',
          property_id: 'prop-1',
        }),
        expect.any(Object)
      );
    });
  });
});
