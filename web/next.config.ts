// Configuração do Next.js: o site é exportado como arquivos estáticos (pasta out/), sem servidor.
// A Vercel só serve os arquivos; a API (public/api) é gerada pelo pipeline antes do build.
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "export",
  // Cada página vira uma pasta com index.html (ex.: out/metodologia/index.html)
  trailingSlash: true,
  // Sem otimizador de imagens: ele precisa de servidor
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default config;
