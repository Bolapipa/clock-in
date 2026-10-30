// Leitura dos JSON da API (pasta api/, gerada por publicar/gerar_api.py) e ganchos do React para as telas
import { useEffect, useState } from "react";

import type { ListaDeOrgaos, Orgao, Resumo } from "./dados";

// Cada arquivo é baixado uma vez só por visita: trocar de tela e voltar não baixa de novo
const cache = new Map<string, Promise<unknown>>();

function carregar<T>(caminho: string): Promise<T> {
  if (!cache.has(caminho)) {
    const pedido = fetch(caminho).then((resposta) => {
      if (!resposta.ok) throw new Error(`${caminho}: HTTP ${resposta.status}`);
      return resposta.json();
    });
    // Se falhar, tira do cache para a próxima tentativa baixar de novo
    pedido.catch(() => cache.delete(caminho));
    cache.set(caminho, pedido);
  }
  return cache.get(caminho) as Promise<T>;
}

export type Carga<T> = { estado: "carregando" } | { estado: "erro" } | { estado: "pronto"; dados: T };

// Carrega um arquivo e devolve o estado: carregando, erro ou pronto (com os dados)
function useArquivo<T>(caminho: string | null): Carga<T> {
  const [carga, setCarga] = useState<Carga<T>>({ estado: "carregando" });

  useEffect(() => {
    if (!caminho) return;
    let ativo = true;
    setCarga({ estado: "carregando" });
    carregar<T>(caminho)
      .then((dados) => { if (ativo) setCarga({ estado: "pronto", dados }); })
      .catch(() => { if (ativo) setCarga({ estado: "erro" }); });
    // Se a tela mudar antes de terminar, o resultado antigo é ignorado
    return () => { ativo = false; };
  }, [caminho]);

  return carga;
}

export const useResumo = () => useArquivo<Resumo>("api/resumo.json");
export const useListaDeOrgaos = () => useArquivo<ListaDeOrgaos>("api/orgaos.json");
export const useOrgao = (slug: string) => useArquivo<Orgao>(`api/orgaos/${slug}.json`);
