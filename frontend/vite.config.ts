import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

const googlePopupHeaders = {
  'Cross-Origin-Opener-Policy': 'same-origin-allow-popups',
  'Referrer-Policy': 'no-referrer-when-downgrade',
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    headers: googlePopupHeaders,
  },
  preview: {
    headers: googlePopupHeaders,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
})
