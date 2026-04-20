/**
 * Mirrors backend `zestimate_agent.address_validation` so the UI can catch issues before fetch.
 */

const US_STATE_ABBR =
  'AK|AL|AR|AZ|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|' +
  'MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|' +
  'PR|RI|SC|SD|TN|TX|UT|VA|VI|VT|WA|WI|WV|WY'

const RE_STATE = new RegExp(`\\b(?:${US_STATE_ABBR})\\b`, 'i')
const RE_ZIP_END = /\b\d{5}(?:-\d{4})?\s*$/
const RE_ZIP_ANY = /\b\d{5}(?:-\d{4})?\b/
const RE_STREET_NUMBER_START = /^\s*\d+[A-Za-z0-9-]*/
const RE_PO_BOX = /\bP\.?\s*O\.?\s*Box\b/i
const RE_HTTP_URL = /^https?:\/\//i

export function validateUsPropertyAddress(raw) {
  const s = (raw ?? '').trim().replace(/\s+/g, ' ')
  if (s.length < 3) {
    return { ok: false, message: 'Address is too short.' }
  }
  if (s.length > 500) {
    return { ok: false, message: 'Address is too long (max 500 characters).' }
  }

  if (RE_HTTP_URL.test(s)) {
    return { ok: false, message: 'Enter a street address, not a URL.' }
  }

  if (RE_PO_BOX.test(s)) {
    return { ok: false, message: 'Enter a physical property street address (PO Boxes are not supported).' }
  }

  if (!/[A-Za-z]/.test(s)) {
    return { ok: false, message: 'Address must include street and city text.' }
  }

  if (!/\d/.test(s)) {
    return { ok: false, message: 'Address must include a street number and ZIP code.' }
  }

  if (!RE_STREET_NUMBER_START.test(s)) {
    return { ok: false, message: 'Start with a street number (example: 525 W Prospect St, Seattle, WA 98119).' }
  }

  if (/^\d{5}(?:-\d{4})?$/.test(s)) {
    return { ok: false, message: 'Enter a full street address, not only a ZIP code.' }
  }

  const hasState = RE_STATE.test(s)
  const hasZip = RE_ZIP_ANY.test(s)
  if (!hasState && !hasZip) {
    return { ok: false, message: 'Include state (2-letter code) and ZIP code.' }
  }
  if (!hasState) {
    return { ok: false, message: 'Include the 2-letter state code (for example, WA).' }
  }
  if (!hasZip) {
    return { ok: false, message: 'Include a valid ZIP code (5 digits or ZIP+4).' }
  }
  if (!RE_ZIP_END.test(s)) {
    return { ok: false, message: 'Place ZIP code at the end of the address.' }
  }

  return { ok: true, normalized: s }
}

/** Avoid noisy blur errors on half-typed lines. */
export function shouldValidateOnBlur(value) {
  const t = (value ?? '').trim().replace(/\s+/g, ' ')
  if (t.length < 8) return false
  if (RE_HTTP_URL.test(t)) return true
  if (RE_PO_BOX.test(t)) return true
  if (!/\d/.test(t) && t.length >= 10) return true
  if (RE_STATE.test(t)) return true
  if (RE_ZIP_ANY.test(t)) return true
  if (t.includes(',')) return true
  if (t.length >= 14) return true
  return false
}
