import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { nodePolyfills } from "vite-plugin-node-polyfills";

export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      // Only polyfill what mqtt.js actually needs
      include: ["buffer", "process", "stream", "url", "events", "util"],
      globals: {
        Buffer: true,
        global: true,
        process: true,
      },
    }),
  ],
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom"],
          three: ["three"],
          "react-three": ["@react-three/fiber", "@react-three/drei"],
          recharts: ["recharts"],
          mqtt: ["mqtt"],
        },
      },
    },
  },
});
