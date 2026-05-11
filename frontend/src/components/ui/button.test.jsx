import React from 'react';
import { render, screen } from '@testing-library/react';
import { Button } from './button';

describe('Button', () => {
  it('merges className after variant styles so overrides apply', () => {
    render(
      <Button type="button" className="w-full bg-midnight-blue hover:bg-midnight-blue/90">
        Submit
      </Button>
    );
    const btn = screen.getByRole('button', { name: 'Submit' });
    expect(btn.className).toContain('w-full');
    expect(btn.className).toContain('bg-midnight-blue');
  });
});
