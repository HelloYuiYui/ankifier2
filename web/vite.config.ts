import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // Inside the Poetry package, so `poetry run ankifier` can serve the built
    // SPA and a real install ships it. A dist/ outside the package would be
    // excluded from the wheel.
    outDir: '../src/ankifier/static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      // Same-origin in dev, so no CORS and no VITE_API_BASE needed locally.
      // 127.0.0.1 rather than localhost: on macOS "localhost" can resolve to
      // ::1 while uvicorn binds 127.0.0.1 only, and the proxy then fails.
      '/api': { target: 'http://127.0.0.1:8000' },
    },
  },
})
