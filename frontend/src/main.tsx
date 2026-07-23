import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Apply the saved (or OS-preferred) theme before first paint to avoid a flash.
const storedTheme = localStorage.getItem('ateric-theme')
const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
document.documentElement.classList.toggle('dark', storedTheme ? storedTheme === 'dark' : prefersDark)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
