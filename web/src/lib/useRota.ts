// Rota da página a partir do endereço depois do # (funciona em qualquer hospedagem estática)
import { useEffect, useRef, useState } from "react";

import { lerRota, type Rota } from "./dados";

export function useRota(): Rota {
  const [rota, setRota] = useState<Rota>(() => lerRota(window.location.hash));
  const rotaAtual = useRef(rota);
  rotaAtual.current = rota;

  useEffect(() => {
    const aoMudar = () => {
      const fragmento = window.location.hash.replace(/^#/, "");
      const eRotaDoSite = fragmento === "metodologia" || fragmento === "api" || /^(?:orgao=)[a-z0-9-]+(?:&base=.+)?$/.test(fragmento);
      // Fragmentos de navegação dentro da página são âncoras, não rotas do app.
      if (!eRotaDoSite && fragmento && document.getElementById(fragmento)) return;

      const proxima = lerRota(window.location.hash);
      const anterior = rotaAtual.current;
      const mesmaRota = anterior.tipo === proxima.tipo
        && (anterior.tipo === "inicio" || anterior.tipo === "api" || anterior.tipo === "metodologia"
          || (anterior.tipo === "orgao" && proxima.tipo === "orgao" && anterior.orgao === proxima.orgao)
          || (anterior.tipo === "base" && proxima.tipo === "base" && anterior.orgao === proxima.orgao && anterior.base === proxima.base));
      if (mesmaRota) return;
      rotaAtual.current = proxima;
      setRota(proxima);
      // Cada tela nova começa do topo
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);

  return rota;
}

// Título da aba do navegador de cada tela
export function useTituloDaPagina(titulo?: string) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · Clock-in` : "Clock-in · Monitor de dados abertos do Brasil";
  }, [titulo]);
}
