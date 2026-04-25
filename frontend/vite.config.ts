import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const API = 'http://localhost:8000'
const WS  = 'ws://localhost:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 3000,
    proxy: {
      '/hcp':          { target: API, changeOrigin: true },
      '/log':          { target: API, changeOrigin: true },
      '/interaction':  { target: API, changeOrigin: true },
      '/interactions': { target: API, changeOrigin: true },
      '/metadata':     { target: API, changeOrigin: true },
      '/tags':         { target: API, changeOrigin: true },
      '/users':        { target: API, changeOrigin: true },
      '/auth':         { target: API, changeOrigin: true },
      '/health':       { target: API, changeOrigin: true },
      '/ws':           { target: WS,  ws: true },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './setupTests.ts',
  },
})
