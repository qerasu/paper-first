import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: [".loca.lt"], // not needed in case of using render
    proxy: {
      "/api": "http://api:8000"
    }
  }
});
