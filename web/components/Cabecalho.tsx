"use client";

// Cabeçalho fixo: marca, navegação, busca rápida (Ctrl K), língua e tema. No celular, o menu abre de lado.
import * as Dialog from "@radix-ui/react-dialog";
import { Menu, Moon, Search, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { abrirBusca } from "@/components/BuscaRapida";
import { IconeGithub, Marca } from "@/components/Marca";
import { useLingua } from "@/components/Provedores";
import { cn } from "@/lib/util";

export const URL_GITHUB = "https://github.com/Bolapipa/clock-in";

function useLinks() {
  const { t } = useLingua();
  return [
    { href: "/#panorama", texto: t.nav.panorama },
    { href: "/#orgaos", texto: t.nav.orgaos },
    { href: "/metodologia/", texto: t.nav.metodologia },
    { href: "/desenvolvedores/", texto: t.nav.desenvolvedores },
  ];
}

function TrocaDeLingua() {
  const { lingua, trocarLingua, t } = useLingua();
  return (
    <div role="group" aria-label={t.nav.idioma} className="flex rounded-full border border-linha bg-superficie p-0.5 font-mono text-[0.72rem]">
      {(["pt", "en"] as const).map((opcao) => (
        <button key={opcao} type="button" onClick={() => trocarLingua(opcao)} aria-pressed={lingua === opcao}
          className={cn("rounded-full px-2.5 py-1 uppercase transition-colors",
            lingua === opcao ? "bg-tinta text-fundo" : "text-tinta-2 hover:text-tinta")}>
          {opcao}
        </button>
      ))}
    </div>
  );
}

function TrocaDeTema() {
  const { resolvedTheme, setTheme } = useTheme();
  const { t } = useLingua();
  const [montado, setMontado] = useState(false);
  useEffect(() => setMontado(true), []);
  const escuro = montado && resolvedTheme === "dark";
  return (
    <button type="button" onClick={() => setTheme(escuro ? "light" : "dark")} aria-label={escuro ? t.nav.temaClaro : t.nav.temaEscuro}
      className="grid size-9 place-items-center rounded-full border border-linha bg-superficie text-tinta-2 transition-colors hover:text-tinta">
      {/* Antes de montar não se sabe o tema: mostra o ícone neutro para não piscar */}
      {escuro ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  );
}

export function Cabecalho() {
  const { t } = useLingua();
  const links = useLinks();
  const caminho = usePathname();
  const [menuAberto, setMenuAberto] = useState(false);
  const ativo = (href: string) => !href.startsWith("/#") && caminho.startsWith(href.replace(/\/$/, ""));

  return (
    <header className="sticky top-0 z-40 border-b border-linha/70 bg-fundo/80 backdrop-blur-xl supports-[backdrop-filter]:bg-fundo/65">
      <a href="#conteudo" className="so-leitor focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-superficie focus:px-3 focus:py-2">
        {t.nav.pular}
      </a>
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6 lg:px-8">
        <Link href="/" aria-label="Clock-in" className="rounded-md"><Marca /></Link>

        <nav aria-label="Principal" className="hidden items-center gap-1 md:flex">
          {links.map((link) => (
            <Link key={link.href} href={link.href} aria-current={ativo(link.href) ? "page" : undefined}
              className={cn("rounded-full px-3 py-1.5 text-sm font-medium transition-colors",
                ativo(link.href) ? "bg-superficie-2 text-tinta" : "text-tinta-2 hover:text-tinta")}>
              {link.texto}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={abrirBusca}
            className="hidden h-9 items-center gap-2 rounded-full border border-linha bg-superficie pl-3 pr-1.5 text-sm text-tinta-3 transition-colors hover:text-tinta-2 sm:flex">
            <Search className="size-4" />
            <span className="w-28 text-left lg:w-40">{t.nav.buscar}</span>
            <kbd className="rounded-full border border-linha bg-superficie-2 px-2 py-0.5 font-mono text-[0.68rem] text-tinta-3">{t.nav.atalho}</kbd>
          </button>
          <button type="button" onClick={abrirBusca} aria-label={t.nav.buscar}
            className="grid size-9 place-items-center rounded-full border border-linha bg-superficie text-tinta-2 sm:hidden">
            <Search className="size-4" />
          </button>
          <div className="hidden sm:block"><TrocaDeLingua /></div>
          <TrocaDeTema />
          <a href={URL_GITHUB} target="_blank" rel="noopener" aria-label={t.nav.github}
            className="hidden size-9 place-items-center rounded-full border border-linha bg-superficie text-tinta-2 transition-colors hover:text-tinta sm:grid">
            <IconeGithub />
          </a>

          {/* Celular: menu lateral */}
          <Dialog.Root open={menuAberto} onOpenChange={setMenuAberto}>
            <Dialog.Trigger asChild>
              <button type="button" aria-label={t.nav.menu} className="grid size-9 place-items-center rounded-full border border-linha bg-superficie text-tinta md:hidden">
                <Menu className="size-4" />
              </button>
            </Dialog.Trigger>
            <Dialog.Portal>
              <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm" />
              <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(20rem,85vw)] flex-col gap-6 border-l border-linha bg-fundo p-6 shadow-2xl">
                <div className="flex items-center justify-between">
                  <Dialog.Title asChild><span><Marca /></span></Dialog.Title>
                  <Dialog.Close aria-label={t.nav.fechar} className="grid size-9 place-items-center rounded-full border border-linha"><X className="size-4" /></Dialog.Close>
                </div>
                <Dialog.Description className="so-leitor">{t.nav.menu}</Dialog.Description>
                <nav aria-label="Principal" className="flex flex-col gap-1">
                  {links.map((link) => (
                    <Link key={link.href} href={link.href} onClick={() => setMenuAberto(false)}
                      className="rounded-lg px-3 py-2.5 text-base font-medium text-tinta hover:bg-superficie-2">
                      {link.texto}
                    </Link>
                  ))}
                </nav>
                <div className="mt-auto flex items-center justify-between">
                  <TrocaDeLingua />
                  <a href={URL_GITHUB} target="_blank" rel="noopener" className="inline-flex items-center gap-2 text-sm text-tinta-2">
                    <IconeGithub /> GitHub
                  </a>
                </div>
              </Dialog.Content>
            </Dialog.Portal>
          </Dialog.Root>
        </div>
      </div>
    </header>
  );
}
