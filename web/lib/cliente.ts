"use client";

// Leitura dos JSON da API no navegador (para o que não vai embutido no HTML: a lista na busca rápida e as
// bases de cada órgão). Cada arquivo é baixado uma vez só por visita.
import { useEffect, useState } from "react";

import type { ListaDeOrgaos, Orgao } from "./dados";

const cache = new Map<string, Promise<unknown>>();

function carregar<T>(caminho: string): Promise<T> {
  if (!cache.has(caminho)) {
    const pedido = fetch(caminho).then((resposta) => {
      if (!resposta.ok) throw new Error(`${caminho}: HTTP ${resposta.status}`);
      return resposta.json();
    });
    // Se falhar, sai do cache para a próxima tentativa baixar de novo
    pedido.catch(() => cache.delete(caminho));
    cache.set(caminho, pedido);
  }
  return cache.get(caminho) as Promise<T>;
}

export type Carga<T> = { estado: "carregando" } | { estado: "erro" } | { estado: "pronto"; dados: T };

function usarArquivo<T>(caminho: string | null): Carga<T> {
  const [carga, setCarga] = useState<Carga<T>>({ estado: "carregando" });
  useEffect(() => {
    if (!caminho) return;
    let ativo = true;
    carregar<T>(caminho)
      .then((dados) => { if (ativo) setCarga({ estado: "pronto", dados }); })
      .catch(() => { if (ativo) setCarga({ estado: "erro" }); });
    return () => { ativo = false; };
  }, [caminho]);
  return carga;
}

// 'ligado' falso não baixa nada (a busca rápida só baixa a lista quando abre)
export const usarListaDeOrgaos = (ligado = true) => usarArquivo<ListaDeOrgaos>(ligado ? "/api/orgaos.json" : null);
export const usarOrgao = (slug: string) => usarArquivo<Orgao>(`/api/orgaos/${slug}.json`);
