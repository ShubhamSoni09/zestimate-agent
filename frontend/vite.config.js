import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // '/' keeps asset URLs absolute from the site root — correct for Vercel at https://*.vercel.app/
  base: '/',
  plugins: [react()],
})
