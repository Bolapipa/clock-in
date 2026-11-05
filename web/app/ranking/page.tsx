// Página do ranking: gerada no build a partir de api/ranking.json
import type { Metadata } from "next";

import { PaginaDoRanking } from "@/components/ranking/PaginaDoRanking";
import { lerRanking, lerResumo } from "@/lib/servidor";

export const metadata: Metadata = {
  title: "Ranking de órgãos",
  description: "Os órgãos que mantêm os dados abertos em dia, pela nota calculada a partir do conteúdo das bases do dados.gov.br.",
};

export default async function Pagina() {
  const [ranking, resumo] = await Promise.all([lerRanking(), lerResumo()]);
  return <PaginaDoRanking ranking={ranking} dataColeta={resumo?.data_coleta ?? null} />;
}
