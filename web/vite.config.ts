/// <reference types="vitest" />
// Configuração do Vite (servidor de desenvolvimento e build) e do Vitest (testes)
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Caminhos relativos: o site funciona em qualquer endereço (Vercel, subpasta, preview local)
  base: "./",
  test: {
    environment: "node",
  },
});
