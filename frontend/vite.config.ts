import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: [".loca.lt", ".trycloudflare.com", ".ngrok-free.app", ".ngrok.app"],
    proxy: {
      "/api": "http://api:8000"
    }
  }
});
