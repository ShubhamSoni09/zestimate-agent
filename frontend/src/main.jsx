import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

const appTitle = import.meta.env.VITE_APP_TITLE?.trim() || 'Zillow Zestimate Agent'
document.title = appTitle

const siteUrl = import.meta.env.VITE_SITE_URL?.trim().replace(/\/+$/, '')
if (siteUrl) {
  let canonical = document.querySelector('link[rel="canonical"]')
  if (!canonical) {
    canonical = document.createElement('link')
    canonical.rel = 'canonical'
    document.head.appendChild(canonical)
  }
  canonical.href = siteUrl

  let ogUrl = document.querySelector('meta[property="og:url"]')
  if (!ogUrl) {
    ogUrl = document.createElement('meta')
    ogUrl.setAttribute('property', 'og:url')
    document.head.appendChild(ogUrl)
  }
  ogUrl.setAttribute('content', siteUrl)
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
