/**
 * Mirrors backend `zestimate_agent.address_validation` so the UI can catch issues before fetch.
 */

const US_STATE_ABBR =
  'AK|AL|AR|AZ|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|' +
  'MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|' +
  'PR|RI|SC|SD|TN|TX|UT|VA|VI|VT|WA|WI|WV|WY'

const RE_STATE = new RegExp(`\\b(?:${US_STATE_ABBR})\\b`, 'i')
const RE_ZIP_END = /\b\d{5}(?:-\d{4})?\s*$/
const RE_ZPID = /^\d{6,12}$/

export function validateUsPropertyAddress(raw) {
  const s = (raw ?? '').trim().replace(/\s+/g, ' ')
  if (s.length < 3) {
    return { ok: false, message: 'Address is too short.' }
  }
  if (s.length > 500) {
    return { ok: false, message: 'Address is too long (max 500 characters).' }
  }

  const low = s.toLowerCase()
  if (low.startsWith('http://') || low.startsWith('https://')) {
    if (low.includes('zillow.com')) {
      return { ok: true, normalized: s }
    }
    return {
      ok: false,
      message: 'Only Zillow URLs are accepted as links (must contain zillow.com).',
    }
  }

  if (RE_ZPID.test(s)) {
    return { ok: true, normalized: s }
  }

  if (RE_STATE.test(s)) {
    return { ok: true, normalized: s }
  }

  if (RE_ZIP_END.test(s)) {
    if (/^\d{5}(?:-\d{4})?$/.test(s)) {
      return { ok: false, message: 'Enter a full street address, not only a ZIP code.' }
    }
    return { ok: true, normalized: s }
  }

  if (s.includes(',') && /\d/.test(s) && s.length >= 10) {
    return { ok: true, normalized: s }
  }

  return {
    ok: false,
    message:
      'Enter a US-style property address (street, city, ST and ZIP), a Zillow homedetails/search URL, or a numeric ZPID.',
  }
}

/** Avoid noisy blur errors on half-typed lines. */
export function shouldValidateOnBlur(value) {
  const t = (value ?? '').trim().replace(/\s+/g, ' ')
  if (t.length < 8) return false
  if (/^https?:\/\//i.test(t)) return true
  if (RE_ZPID.test(t)) return true
  if (RE_STATE.test(t)) return true
  if (RE_ZIP_END.test(t)) return true
  if (t.includes(',')) return true
  if (t.length >= 14) return true
  return false
}
