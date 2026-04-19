import { useState } from 'react'
import { shouldValidateOnBlur, validateUsPropertyAddress } from './addressValidation'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

/** Shown as placeholder only; field starts empty. */
const ADDRESS_PLACEHOLDER = '525 W Prospect Street #A, Seattle, WA 98119'

function formatApiError(payload) {
  const detail = payload?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((e) => e.msg ?? JSON.stringify(e)).join(' ')
  }
  return 'Request failed.'
}

function App() {
  const [address, setAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldError, setFieldError] = useState('')
  const [result, setResult] = useState(null)

  const handleAddressChange = (event) => {
    setAddress(event.target.value)
    setFieldError('')
    setError('')
  }

  const handleAddressBlur = () => {
    if (!shouldValidateOnBlur(address)) {
      setFieldError('')
      return
    }
    const check = validateUsPropertyAddress(address)
    setFieldError(check.ok ? '' : check.message)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setFieldError('')
    setResult(null)

    const trimmed = address.trim()
    if (!trimmed) {
      setFieldError('Please enter a US property address, Zillow URL, or ZPID.')
      return
    }

    const local = validateUsPropertyAddress(trimmed)
    if (!local.ok) {
      setFieldError(local.message)
      return
    }

    setLoading(true)
    try {
      const response = await fetch(`${API_BASE}/zestimate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: local.normalized }),
      })

      const payload = await response.json()
      if (!response.ok) {
        throw new Error(formatApiError(payload))
      }
      setResult(payload)
    } catch (err) {
      setError(err.message || 'Could not fetch Zestimate.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container">
      <h1>Zillow Estimate Agent</h1>
      <p className="subtitle">
        US street address (with or without commas), a Zillow property URL, or a ZPID.
      </p>

      <form
        className="card"
        onSubmit={handleSubmit}
        noValidate
        aria-busy={loading ? 'true' : 'false'}
      >
        <label htmlFor="address">Property address</label>
        <input
          id="address"
          type="text"
          className={fieldError ? 'input-invalid' : ''}
          placeholder={ADDRESS_PLACEHOLDER}
          value={address}
          onChange={handleAddressChange}
          onBlur={handleAddressBlur}
          disabled={loading}
          aria-invalid={fieldError ? 'true' : 'false'}
          aria-describedby={fieldError || error ? 'address-feedback' : undefined}
        />
        <button type="submit" className="submit-btn" disabled={loading}>
          {loading ? (
            <>
              <span className="btn-spinner" aria-hidden="true" />
              Fetching…
            </>
          ) : (
            'Get Zestimate'
          )}
        </button>
        {loading ? (
          <div className="loader-panel" role="status" aria-live="polite">
            <div className="loader-bar-track" aria-hidden="true">
              <div className="loader-bar-indeterminate" />
            </div>
            <p className="loader-caption">Hang tight — your zestimate is on the way.</p>
          </div>
        ) : null}
      </form>

      {fieldError || error ? (
        <div id="address-feedback" className="form-feedback">
          {fieldError ? <p className="field-error">{fieldError}</p> : null}
          {error ? <p className="error">{error}</p> : null}
        </div>
      ) : null}

      {result ? (
        <section className="card result">
          <h2>Result</h2>
          <p><strong>Address:</strong> {result.address}</p>
          <p><strong>Zestimate:</strong> ${Number(result.zestimate).toLocaleString()}</p>
          <p>
            <strong>Property URL:</strong>{' '}
            <a href={result.property_url} target="_blank" rel="noreferrer">
              Open Zillow page
            </a>
          </p>
        </section>
      ) : null}
    </main>
  )
}

export default App
