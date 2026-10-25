/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = process.env.BACKEND_URL ?? "http://backend:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": backend, "/media": backend },
    // Les volumes Docker montés depuis Windows/macOS ne propagent pas les événements fichiers.
    watch: { usePolling: true, interval: 300 },
  },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"] },
});
