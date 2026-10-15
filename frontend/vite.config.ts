import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // Pre-bundle the shaders engine so the lazy dynamic import resolves in dev.
  optimizeDeps: {
    include: ['shaders/react'],
  },
  server: {
    port: 5173,
  },
})
