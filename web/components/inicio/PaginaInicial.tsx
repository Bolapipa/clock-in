"use client";

// Página inicial: herói com o mostrador, números do dia, simulador, mapa e lista de órgãos.
// O estado escolhido no mostrador (ou na legenda) filtra a lista e leva até ela.
import { useCallback, useState } from "react";

import { Heroi } from "@/components/inicio/Heroi";
import { ListaDeOrgaos } from "@/components/inicio/ListaDeOrgaos";
import { MapaDeOrgaos } from "@/components/inicio/MapaDeOrgaos";
import { Numeros } from "@/components/inicio/Numeros";
import { Simulador } from "@/components/inicio/Simulador";
import { useLingua } from "@/components/Provedores";
import { Miolo } from "@/components/ui";
import type { ChaveDaParte, OrgaoResumo, Resumo } from "@/lib/dados";

export function PaginaInicial({ resumo, orgaos }: { resumo: Resumo | null; orgaos: OrgaoResumo[] }) {
  const { t } = useLingua();
  const [estado, setEstado] = useState<ChaveDaParte | null>(null);

  const selecionar = useCallback((chave: ChaveDaParte | null) => {
    setEstado(chave);
    if (chave) {
      // Espera a lista se refazer e rola até ela
      window.setTimeout(() => document.getElementById("orgaos")?.scrollIntoView({ behavior: "smooth", block: "start" }), 120);
    }
  }, []);

  if (!resumo) {
    return <Miolo className="py-32 text-center text-tinta-2">{t.comum.semDados}</Miolo>;
  }

  return (
    <>
      <Heroi resumo={resumo} selecionado={estado} aoSelecionar={selecionar} />
      <Numeros resumo={resumo} />
      <Simulador />
      {orgaos.length > 0 && <MapaDeOrgaos orgaos={orgaos} />}
      {orgaos.length > 0 && <ListaDeOrgaos orgaos={orgaos} estado={estado} limparEstado={() => setEstado(null)} />}
    </>
  );
}
