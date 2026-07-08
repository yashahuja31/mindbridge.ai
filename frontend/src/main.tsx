import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'sonner'

import './index.css'
import App from '@/App'
import { AuthProvider } from '@/context/AuthContext'

// Apply the persisted theme before first paint to avoid a flash of the wrong mode.
if (localStorage.getItem('mindbridge_theme') === 'dark') {
  document.documentElement.classList.add('dark')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
