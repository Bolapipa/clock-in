// Peças pequenas reaproveitadas nas telas: ficha de totais, etiqueta de status e campos de busca
import type { ReactNode } from "react";

import { ROTULOS_STATUS, rotulo, type Status } from "../lib/dados";

export type Tom = "bom" | "atencao" | "ruim" | "";

const COR_DO_VALOR: Record<Tom, string> = {
  bom: "text-bom-texto",
  atencao: "text-atencao-texto",
  ruim: "text-ruim-texto",
  "": "",
};

export interface ItemDaFicha {
  rotulo: string;
  valor: string;
  detalhe?: string;
  tom?: Tom;
}

// Ficha: números principais em uma superfície com hierarquia clara.
export function Ficha({ titulo, itens }: { titulo?: string; itens: ItemDaFicha[] }) {
  return (
    <aside className="overflow-hidden rounded-2xl border border-linha bg-superficie px-6 py-4 shadow-sm">
      {titulo && <h2 className="mb-2 mt-0 text-xs font-bold uppercase tracking-[0.15em] text-carimbo">{titulo}</h2>}
      <dl className="m-0 divide-y divide-linha">
        {itens.map((item) => (
          <div key={item.rotulo} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-4">
            <dt className="text-sm font-medium text-tinta-suave">{item.rotulo}</dt>
            <dd className={`m-0 text-3xl font-semibold leading-none tracking-[-0.05em] tabular-nums ${COR_DO_VALOR[item.tom ?? ""]}`}>
              {item.valor}
            </dd>
            {item.detalhe && <dd className="col-span-2 row-start-2 mt-1 text-xs text-tinta-suave">{item.detalhe}</dd>}
          </div>
        ))}
      </dl>
    </aside>
  );
}

// Etiqueta de status: fundo claro e texto escuro; o texto sempre diz o estado e a cor só reforça.
// Tracejada quando ainda não dá para dizer
const ESTILO_DO_SELO: Record<string, string> = {
  EM_DIA: "bg-bom-fundo text-bom-texto border-transparent",
  ATRASADA: "bg-atencao-fundo text-atencao-texto border-transparent",
  PARADA: "bg-atencao-fundo text-atencao-texto border-transparent",
  FORA_DO_AR: "bg-ruim-fundo text-ruim-texto border-transparent",
  NAO_VERIFICAVEL: "bg-neutro-fundo text-tinta border-dashed border-linha-forte",
};

export function Selo({ status, grande = false, dica }: { status: Status; grande?: boolean; dica?: string }) {
  return (
    <span title={dica}
      className={`inline-block whitespace-nowrap rounded border-[1.5px] font-semibold ${grande ? "px-3.5 py-1 text-lg" : "px-2.5 py-0.5 text-[0.85rem]"} ${
        ESTILO_DO_SELO[status] ?? "border-transparent bg-neutro-fundo text-tinta"}`}>
      {rotulo(ROTULOS_STATUS, status)}
    </span>
  );
}

const ESTILO_DO_CAMPO = "h-12 w-full rounded-sm border-[1.5px] border-linha-forte bg-superficie px-3 text-base font-normal text-tinta "
  + "transition-colors placeholder:text-tinta-suave hover:border-tinta-suave";

// Campo com rótulo em cima; o rótulo envolve o campo, então clicar no texto foca o campo
function Campo({ rotulo: texto, children, larga = false }: { rotulo: string; children: ReactNode; larga?: boolean }) {
  return (
    <label className={`flex flex-col gap-1.5 text-[0.9rem] font-semibold text-tinta-suave ${larga ? "sm:col-span-2" : ""}`}>
      <span>{texto}</span>
      {children}
    </label>
  );
}

export function CampoBusca({ rotulo: texto, valor, aoMudar, exemplo }: {
  rotulo: string; valor: string; aoMudar: (valor: string) => void; exemplo: string;
}) {
  return (
    <Campo rotulo={texto} larga>
      <span className="relative block">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="pointer-events-none absolute left-3.5 top-1/2 size-5 -translate-y-1/2 text-tinta-suave"
          fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
        </svg>
        <input type="search" value={valor} onChange={(evento) => aoMudar(evento.target.value)} placeholder={exemplo}
          autoComplete="off" className={`${ESTILO_DO_CAMPO} pl-11`} />
      </span>
    </Campo>
  );
}

export function CampoEscolha({ rotulo: texto, valor, aoMudar, opcoes }: {
  rotulo: string; valor: string; aoMudar: (valor: string) => void; opcoes: { valor: string; texto: string }[];
}) {
  return (
    <Campo rotulo={texto}>
      <select value={valor} onChange={(evento) => aoMudar(evento.target.value)} className={ESTILO_DO_CAMPO}>
        {opcoes.map((opcao) => <option key={opcao.valor} value={opcao.valor}>{opcao.texto}</option>)}
      </select>
    </Campo>
  );
}

export function Marcar({ rotulo: texto, marcado, aoMudar }: { rotulo: string; marcado: boolean; aoMudar: (marcado: boolean) => void }) {
  return (
    <label className="flex h-12 cursor-pointer items-center gap-2.5 self-end font-medium">
      <input type="checkbox" checked={marcado} onChange={(evento) => aoMudar(evento.target.checked)} className="size-5 accent-carimbo" />
      {texto}
    </label>
  );
}

export function BotaoMais({ texto, aoClicar }: { texto: string; aoClicar: () => void }) {
  return (
    <button type="button" onClick={aoClicar} className="botao-mais mt-5">
      <span>{texto}</span>
      <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3v13M5 11l5 5 5-5" />
      </svg>
    </button>
  );
}

// Mensagem quando a busca não acha nada: diz o que fazer
export function Vazio({ children }: { children: ReactNode }) {
  return <p className="my-4 rounded-lg bg-superficie px-6 py-8 text-center text-tinta-suave">{children}</p>;
}
