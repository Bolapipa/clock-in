// Faixas de cor do mapa de órgãos: pela porcentagem de links respondendo bem.
// O texto da faixa sempre acompanha a cor (a cor nunca é a única informação)

export type Faixa = "otima" | "boa" | "atencao" | "ruim" | "critica" | "sem_percentual";

export const FAIXAS: { faixa: Faixa; minimo: number | null }[] = [
  { faixa: "otima", minimo: 98 },
  { faixa: "boa", minimo: 90 },
  { faixa: "atencao", minimo: 75 },
  { faixa: "ruim", minimo: 50 },
  { faixa: "critica", minimo: 0 },
  { faixa: "sem_percentual", minimo: null },
];

// Órgãos com poucos links testados não têm porcentagem (decisão 35) e ficam numa faixa própria
export function faixaDoPercentual(percentual: number | null | undefined): Faixa {
  if (percentual == null || Number.isNaN(percentual)) return "sem_percentual";
  return FAIXAS.find((item) => item.minimo != null && percentual >= item.minimo)?.faixa ?? "critica";
}
