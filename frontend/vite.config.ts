/// <reference types="vitest/config" />
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Plain runserver: http://127.0.0.1:8000
  // django-extensions runserver_plus --cert-file: https://127.0.0.1:8000 (set in frontend/.env)
  const djangoProxyTarget = env.VITE_DJANGO_PROXY_TARGET || 'http://127.0.0.1:8000'
  const proxyToHttps = djangoProxyTarget.startsWith('https:')

  const proxyDefaults = {
    target: djangoProxyTarget,
    changeOrigin: true,
    // Self-signed dev cert from runserver_plus — Node must not reject it
    secure: proxyToHttps ? false : true,
  }

  return {
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    plugins: [
      react(),
      tailwindcss()
    ],
    server: {
      port: 5173,
      proxy: {
        // Forward all dashboard routes to Django (API, exports, wizard, legacy HTML if any).
        '/dashboard': { ...proxyDefaults },
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      include: ['src/**/*.test.{ts,tsx}'],
    },
  }
})
