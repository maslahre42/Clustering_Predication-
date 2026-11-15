/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev-server proxy: the frontend calls same-origin /health and /api/*,
// Vite forwards them to the local FastAPI backend.
const apiProxyTarget = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/health": apiProxyTarget,
      "/api": apiProxyTarget,
    },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
