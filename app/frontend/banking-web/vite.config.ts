import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    port: 5170,
    host: "0.0.0.0",
    proxy: {
      // Proxy API requests to local backend servers
      '/api/accounts/': {
        target: 'http://localhost:8070',
        changeOrigin: true
      },
      '/api/transactions/': {
        target: 'http://localhost:8071',
        changeOrigin: true
      },
      '/api/payments': {
        target: 'http://localhost:8072',
        changeOrigin: true
      },
    },
  },
  plugins: [
    react()
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
