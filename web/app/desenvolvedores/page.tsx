// Página "Dados e API"
import type { Metadata } from "next";

import { Desenvolvedores } from "@/components/textos/Desenvolvedores";

export const metadata: Metadata = {
  title: "Dados e API",
  description: "Os dados do Clock-in em JSON aberto, sem chave: resumo do Brasil, órgãos e bases, com exemplos em JavaScript, Python e curl.",
};

export default function Pagina() {
  return <Desenvolvedores />;
}
