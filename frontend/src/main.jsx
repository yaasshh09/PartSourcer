import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Analytics } from '@vercel/analytics/react'
import './index.css'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
      {/* Loads and beacons from /_vercel/insights, same origin, so the
          script-src 'self' and connect-src 'self' in vercel.json cover it
          without loosening anything. Inert outside a Vercel deploy. */}
      <Analytics />
    </BrowserRouter>
  </React.StrictMode>,
)
