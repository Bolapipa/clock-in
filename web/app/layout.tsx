// Moldura de todas as páginas: fontes, tema, língua, cabeçalho, rodapé e busca rápida
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { BuscaRapida } from "@/components/BuscaRapida";
import { Cabecalho } from "@/components/Cabecalho";
import { Provedores } from "@/components/Provedores";
import { Rodape } from "@/components/Rodape";
import { lerResumo } from "@/lib/servidor";

import "./globals.css";

export const metadata: Metadata = {
  // Endereço público do site: sem ele, as imagens de compartilhamento saem com endereço relativo
  metadataBase: new URL("https://clock-in-monitor.vercel.app"),
  title: { default: "Clock-in · Os dados abertos do Brasil ainda batem o ponto?", template: "%s · Clock-in" },
  description: "Monitor diário dos dados abertos do governo: testa os links de todas as bases do dados.gov.br e mostra, órgão por órgão, o que ainda responde e o que quebrou.",
  applicationName: "Clock-in",
  openGraph: {
    title: "Clock-in · Os dados abertos do Brasil ainda batem o ponto?",
    description: "Monitor diário dos links das bases do dados.gov.br, órgão por órgão.",
    type: "website",
    locale: "pt_BR",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f6f8" },
    { media: "(prefers-color-scheme: dark)", color: "#06080d" },
  ],
};

export default async function Layout({ children }: { children: ReactNode }) {
  const resumo = await lerResumo();
  return (
    <html lang="pt-BR" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="min-h-dvh">
        <Provedores>
          <Cabecalho />
          <main id="conteudo" tabIndex={-1} className="outline-none">{children}</main>
          <Rodape dataColeta={resumo?.data_coleta ?? null} />
          <BuscaRapida />
        </Provedores>
      </body>
    </html>
  );
}
