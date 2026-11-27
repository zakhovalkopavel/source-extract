import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/** Comma-separated Host headers Vite may accept behind nginx (see VITE_ALLOWED_HOSTS). */
function allowedHostsFromEnv(): true | string[] {
  const raw = process.env.VITE_ALLOWED_HOSTS?.trim();
  if (!raw || raw === '*') {
    return true;
  }
  const hosts = raw
    .split(',')
    .map((h) => h.trim())
    .filter(Boolean);
  return hosts.length > 0 ? hosts : true;
}

const allowedHosts = allowedHostsFromEnv();

export default defineConfig({
  plugins: [react()],
  base: '/source-extractor/',
  server: {
    host: true,
    port: Number(process.env.VITE_PORT) || 5174,
    allowedHosts,
  },
  preview: {
    host: true,
    port: Number(process.env.VITE_PORT) || 5174,
    allowedHosts,
  },
});
