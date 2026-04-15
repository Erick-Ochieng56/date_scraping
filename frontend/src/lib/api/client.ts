import axios from 'axios'

/**
 * Base URL for Django.
 * - Dev: leave VITE_API_BASE unset so requests use relative URLs and the Vite proxy.
 * - Same-origin (Django serves the SPA, ngrok, etc.): keep unset — always relative to the page origin.
 * - Cross-origin only: set VITE_API_BASE to the API origin.
 */
const baseURL = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? ''

export const apiClient = axios.create({
  baseURL,
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  headers: {
    'X-Requested-With': 'XMLHttpRequest',
    // Free ngrok shows an interstitial unless this header is present on every request.
    'ngrok-skip-browser-warning': 'true',
  },
})

/** Prime CSRF cookie (and optionally session) before POST login. */
export async function bootstrapApiSession(): Promise<void> {
  try {
    await apiClient.get('/dashboard/api/auth/me/')
  } catch {
    // network errors only — unauthenticated still returns 200 with authenticated:false
  }
}
