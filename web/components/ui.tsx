"use client";

// Peças pequenas reaproveitadas: cabeçalho de seção, botões, etiquetas de status, campos e a régua de links
import { Search } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useLingua } from "@/components/Provedores";
import type { ChaveDaParte, ParteDaRegua } from "@/lib/dados";
import { cn } from "@/lib/util";

export function Miolo({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8", className)}>{children}</div>;
}

// Rótulo pequeno acima do título da seção, com o ponto âmbar do "carimbo"
export function Kicker({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <p className={cn("inline-flex items-center gap-2 font-mono text-xs text-tinta-2", className)}>
      <span aria-hidden="true" className="size-1.5 rounded-full bg-ambar" />
      {children}
    </p>
  );
}

export function CabecalhoDeSecao({ kicker, titulo, lide, id, children }: { kicker: string; titulo: string; lide?: string; id?: string; children?: ReactNode }) {
  return (
    <div className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <Kicker>{kicker}</Kicker>
        <h2 id={id} className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-tinta sm:text-4xl">{titulo}</h2>
        {lide && <p className="mt-3 text-base leading-relaxed text-tinta-2 sm:text-lg">{lide}</p>}
      </div>
      {children}
    </div>
  );
}

const ESTILO_BOTAO = {
  primario: "bg-tinta text-fundo hover:bg-tinta/85",
  secundario: "border border-linha-2 bg-superficie text-tinta hover:border-tinta-3",
  ambar: "bg-ambar text-ambar-tinta hover:brightness-105",
};

export function Botao({ href, children, variante = "primario", className }: { href: string; children: ReactNode; variante?: keyof typeof ESTILO_BOTAO; className?: string }) {
  return (
    <Link href={href} className={cn("inline-flex h-11 items-center gap-2 rounded-full px-5 text-sm font-medium transition", ESTILO_BOTAO[variante], className)}>
      {children}
    </Link>
  );
}

// Cor de cada estado de link (as classes precisam estar escritas por inteiro para o Tailwind achar)
export const COR_DO_ESTADO: Record<ChaveDaParte, string> = {
  ok: "bg-ok",
  observacao: "bg-obs",
  quebrados: "bg-queb",
  nao_testados: "hachurado",
};
export const TEXTO_DO_ESTADO: Record<ChaveDaParte, string> = {
  ok: "text-ok-texto",
  observacao: "text-obs-texto",
  quebrados: "text-queb-texto",
  nao_testados: "text-tinta-2",
};

// Etiqueta de status de uma base: fundo suave, texto forte; tracejada quando não dá para dizer
const ESTILO_DO_STATUS: Record<string, string> = {
  EM_DIA: "border-transparent bg-ok/12 text-ok-texto",
  ATRASADA: "border-transparent bg-obs/15 text-obs-texto",
  PARADA: "border-transparent bg-obs/15 text-obs-texto",
  FORA_DO_AR: "border-transparent bg-queb/12 text-queb-texto",
  NAO_VERIFICAVEL: "border-dashed border-linha-2 text-tinta-2",
};

export function Status({ status, grande = false }: { status: string; grande?: boolean }) {
  const { t } = useLingua();
  return (
    <span className={cn("inline-flex items-center whitespace-nowrap rounded-full border font-medium",
      grande ? "px-3.5 py-1 text-sm" : "px-2.5 py-0.5 text-xs", ESTILO_DO_STATUS[status] ?? "border-linha text-tinta-2")}>
      {t.status[status] ?? status}
    </span>
  );
}

// Régua: uma barra com as quatro partes dos links, com largura proporcional
export function Regua({ partes, altura = "h-3", rotulo }: { partes: ParteDaRegua[]; altura?: string; rotulo: string }) {
  const { t } = useLingua();
  return (
    <div role="img" aria-label={`${rotulo}: ${partes.map((p) => `${p.quantidade} ${t.estados[p.chave]}`).join(", ")}`}
      className={cn("flex w-full gap-0.5 overflow-hidden rounded-full", altura)}>
      {partes.filter((parte) => parte.quantidade > 0).map((parte) => (
        <span key={parte.chave} className={cn("min-w-1 first:rounded-l-full last:rounded-r-full", COR_DO_ESTADO[parte.chave])}
          style={{ flex: `${parte.quantidade} 1 0` }} />
      ))}
    </div>
  );
}

export function CampoDeBusca({ rotulo, valor, aoMudar, exemplo, className }: { rotulo: string; valor: string; aoMudar: (v: string) => void; exemplo: string; className?: string }) {
  return (
    <label className={cn("relative block", className)}>
      <span className="so-leitor">{rotulo}</span>
      <Search aria-hidden="true" className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-tinta-3" />
      <input type="search" value={valor} onChange={(e) => aoMudar(e.target.value)} placeholder={exemplo} autoComplete="off"
        className="h-11 w-full rounded-full border border-linha bg-superficie pl-10 pr-4 text-sm text-tinta outline-none transition placeholder:text-tinta-3 focus:border-tinta-3" />
    </label>
  );
}

export function Escolha({ rotulo, valor, aoMudar, opcoes, className }: { rotulo: string; valor: string; aoMudar: (v: string) => void; opcoes: { valor: string; texto: string }[]; className?: string }) {
  return (
    <label className={cn("relative block", className)}>
      <span className="so-leitor">{rotulo}</span>
      <select value={valor} onChange={(e) => aoMudar(e.target.value)} aria-label={rotulo}
        className="h-11 w-full appearance-none rounded-full border border-linha bg-superficie pl-4 pr-9 text-sm text-tinta outline-none transition focus:border-tinta-3">
        {opcoes.map((opcao) => <option key={opcao.valor} value={opcao.valor}>{opcao.texto}</option>)}
      </select>
      <svg aria-hidden="true" viewBox="0 0 16 16" className="pointer-events-none absolute right-3.5 top-1/2 size-3.5 -translate-y-1/2 text-tinta-3">
        <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    </label>
  );
}

// Grupo de botões de escolha única (ex.: esferas)
export function Pilulas<T extends string>({ opcoes, valor, aoMudar, rotulo }: { opcoes: { valor: T; texto: string }[]; valor: T; aoMudar: (v: T) => void; rotulo: string }) {
  return (
    <div role="group" aria-label={rotulo} className="flex flex-wrap gap-1.5">
      {opcoes.map((opcao) => (
        <button key={opcao.valor} type="button" onClick={() => aoMudar(opcao.valor)} aria-pressed={valor === opcao.valor}
          className={cn("h-9 rounded-full border px-3.5 text-sm transition",
            valor === opcao.valor ? "border-tinta bg-tinta text-fundo" : "border-linha bg-superficie text-tinta-2 hover:text-tinta")}>
          {opcao.texto}
        </button>
      ))}
    </div>
  );
}
