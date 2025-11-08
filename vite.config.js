import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        // remove the `/api` prefix so the Flask app receives `/create_slides`
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
