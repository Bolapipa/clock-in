"use client";

// Provedores do app: tema (claro, escuro ou do sistema) e língua (português ou inglês).
// A língua escolhida fica guardada no navegador; o padrão é português.
import { ThemeProvider } from "next-themes";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { TEXTOS, type Dicionario, type Lingua } from "@/lib/i18n";

const CHAVE = "clockin-lingua";

interface ContextoDaLingua {
  lingua: Lingua;
  t: Dicionario;
  trocarLingua: (lingua: Lingua) => void;
}

const Contexto = createContext<ContextoDaLingua>({ lingua: "pt", t: TEXTOS.pt, trocarLingua: () => {} });

function ProvedorDaLingua({ children }: { children: ReactNode }) {
  const [lingua, setLingua] = useState<Lingua>("pt");

  // Lê a escolha guardada depois de montar (o HTML estático sai sempre em português)
  useEffect(() => {
    try {
      const guardada = window.localStorage.getItem(CHAVE);
      if (guardada === "en" || guardada === "pt") setLingua(guardada);
    } catch {
      // Navegador sem acesso ao armazenamento: fica em português
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lingua === "pt" ? "pt-BR" : "en";
  }, [lingua]);

  const trocarLingua = useCallback((nova: Lingua) => {
    setLingua(nova);
    try {
      window.localStorage.setItem(CHAVE, nova);
    } catch {
      // Sem armazenamento: a troca vale só nesta visita
    }
  }, []);

  const valor = useMemo(() => ({ lingua, t: TEXTOS[lingua], trocarLingua }), [lingua, trocarLingua]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useLingua() {
  return useContext(Contexto);
}

export function Provedores({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <ProvedorDaLingua>{children}</ProvedorDaLingua>
    </ThemeProvider>
  );
}
