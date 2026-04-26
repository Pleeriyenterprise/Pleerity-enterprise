export function getPropertyDisplayName(property) {
  const p = property || {};
  const explicit = String(
    p.nickname || p.name || p.property_name || p.property_label || ''
  ).trim();
  if (explicit) return explicit;

  const line1 = String(p.address_line_1 || '').trim();
  const city = String(p.city || p.town || '').trim();
  const postcode = String(p.postcode || '').trim();

  if (line1 && city) return `${line1}, ${city}`;
  if (line1 && postcode) return `${line1}, ${postcode}`;
  if (line1) return line1;
  if (postcode) return postcode;
  return 'Unnamed property';
}

