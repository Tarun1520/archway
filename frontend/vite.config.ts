// Vite is the tool that serves the frontend while developing (`npm run dev`)
// and bundles it for release (`npm run build`).
//
// `defineConfig` is imported from "vitest/config" instead of "vite" so this one
// file can also hold the settings for Vitest, the test runner.
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import vercel from './vercel.json'

// Node's environment, read without Node's type definitions (this project does not install them).
const environment = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {}
const assignedPort = environment.PORT
// Where the backend is (a second one can be tried by setting ARCHWAY_BACKEND_URL).
const backendUrl = environment.ARCHWAY_BACKEND_URL || 'http://127.0.0.1:8000'

// The security headers the deployed site sends (vercel.json is the one place they are written). `vite preview`
// serves the BUILT app with the same headers, so the strict Content-Security-Policy can be tried locally first.
// (The dev server cannot use the CSP: its hot reload injects inline scripts. It still refuses to be framed.)
const deployedHeaders = Object.fromEntries(vercel.headers[0].headers.map((header) => [header.key, header.value]))
const { 'Strict-Transport-Security': _hstsOnlyOverHttps, ...previewHeaders } = deployedHeaders

export default defineConfig({
  plugins: [
    react(), // lets Vite understand React components (.tsx files)
    tailwindcss(), // turns Tailwind class names into real CSS
  ],
  server: {
    // The preview tool hands out a free port through the PORT variable; by hand, 5173 is used.
    port: Number(assignedPort) || 5173,
    strictPort: true, // fail loudly if the port is taken instead of picking another
    // While developing, any request to a URL starting with /api is passed on
    // to the backend (backend/run.py, port 8000). The frontend code can then
    // simply call "/api/..." without knowing where the backend lives.
    // `ws: true` passes WebSockets on too (Archy's live listening, /api/voice/listen).
    proxy: {
      '/api': { target: backendUrl, ws: true },
    },
    headers: { 'X-Frame-Options': 'DENY', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer' },
  },
  preview: {
    proxy: {
      '/api': { target: backendUrl, ws: true },
    },
    headers: previewHeaders,
  },
  build: {
    sourcemap: false, // the shipped code does not include a readable copy of the source
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
