import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 4000,
    strictPort: false,
    // Same-origin API in development, like nginx does in production.
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://localhost:8081',
    },
  },
})
