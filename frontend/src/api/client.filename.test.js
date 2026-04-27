import { filenameFromContentDisposition } from './client';

describe('filenameFromContentDisposition', () => {
  it('uses server-provided filename when present', () => {
    const headers = {
      'content-disposition': 'attachment; filename="CVP_Audit_Evidence_Pack_Premier_Laurel-Gardens_2026-04-27.zip"',
    };
    expect(filenameFromContentDisposition(headers, 'fallback.zip')).toBe(
      'CVP_Audit_Evidence_Pack_Premier_Laurel-Gardens_2026-04-27.zip'
    );
  });

  it('falls back when header is missing', () => {
    expect(filenameFromContentDisposition({}, 'fallback.zip')).toBe('fallback.zip');
  });
});

