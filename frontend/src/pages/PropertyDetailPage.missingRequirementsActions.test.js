import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PropertyDocumentsMissingRequirementList } from './PropertyDetailPage';

function row(requirementId, takeAction) {
  return {
    requirement_id: requirementId,
    requirement_code: 'gas_safety',
    requirement_type: 'gas_safety',
    status: 'MISSING',
    title: 'Gas safety',
    take_action: takeAction,
  };
}

describe('PropertyDocumentsMissingRequirementList CTA behavior', () => {
  it('does not use hardcoded upload fallback route', () => {
    const navigate = jest.fn();
    const item = row('req-1', {
      primary: {
        label: 'Resolve now',
        route: '/requirements/req-1/resolve',
        kind: 'navigate',
        handler: 'navigate',
        intent: 'guided_evidence',
      },
    });

    render(
      <MemoryRouter>
        <PropertyDocumentsMissingRequirementList
          items={[item]}
          propertyId="prop-1"
          navigate={navigate}
          rowTitle={(r) => r.title}
          rowReqId={(r) => r.requirement_id}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Resolve now' }));
    expect(navigate).toHaveBeenCalledWith('/requirements/req-1/resolve');
    expect(navigate).not.toHaveBeenCalledWith('/documents?property_id=prop-1&requirement_id=req-1');
  });

  it('document-only requirement still shows upload CTA', () => {
    const navigate = jest.fn();
    const item = row('req-doc', {
      primary: {
        label: 'Upload document',
        route: '/documents?property_id=prop-1&requirement_id=req-doc',
        kind: 'navigate',
        handler: 'navigate',
        intent: 'upload_evidence',
      },
    });

    render(
      <MemoryRouter>
        <PropertyDocumentsMissingRequirementList
          items={[item]}
          propertyId="prop-1"
          navigate={navigate}
          rowTitle={(r) => r.title}
          rowReqId={(r) => r.requirement_id}
        />
      </MemoryRouter>,
    );

    const uploadBtn = screen.getByRole('button', { name: 'Upload document' });
    expect(uploadBtn).toBeInTheDocument();
    fireEvent.click(uploadBtn);
    expect(navigate).toHaveBeenCalledWith('/documents?property_id=prop-1&requirement_id=req-doc');
  });
});
