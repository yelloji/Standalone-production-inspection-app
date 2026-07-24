import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router'

import { App } from './App'
import { BackendStatusProvider } from './state/BackendStatusContext'
import './styles.css'

const root = document.getElementById('root')

if (!root) {
  throw new Error('Application root element was not found')
}

createRoot(root).render(
  <StrictMode>
    <HashRouter>
      <BackendStatusProvider>
        <App />
      </BackendStatusProvider>
    </HashRouter>
  </StrictMode>,
)
