"use client";

// Simulador "sete dias na vida de um link": cada dia é um botão que troca o resultado do teste, e a decisão
// do Clock-in aparece embaixo, com a explicação ao lado. A regra é a mesma do pipeline (lib/simulador.ts).
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { CabecalhoDeSecao, Miolo, Pilulas } from "@/components/ui";
import { CENARIOS, EVENTOS, proximoEvento, simular, type Cenario, type Evento, type Situacao } from "@/lib/simulador";
import { cn } from "@/lib/util";

const SIMBOLO: Record<Evento, string> = { ok: "✓", falha: "✕", inconclusivo: "?", sem_teste: "–" };
const ESTILO_DO_EVENTO: Record<Evento, string> = {
  ok: "border-ok/40 bg-ok/10 text-ok-texto",
  falha: "border-queb/40 bg-queb/10 text-queb-texto",
  inconclusivo: "border-obs/40 bg-obs/10 text-obs-texto",
  sem_teste: "border-dashed border-linha-2 bg-transparent text-tinta-3",
};
const COR_DA_SITUACAO: Record<Situacao, string> = {
  sem_resultado: "hachurado",
  respondendo: "bg-ok",
  observacao: "bg-obs",
  quebrado: "bg-queb",
};
const TEXTO_DA_SITUACAO: Record<Situacao, string> = {
  sem_resultado: "text-tinta-2",
  respondendo: "text-ok-texto",
  observacao: "text-obs-texto",
  quebrado: "text-queb-texto",
};

export function Simulador({ id = "simulador", compacto = false }: { id?: string; compacto?: boolean }) {
  const { t } = useLingua();
  const [cenario, setCenario] = useState<Cenario | "proprio">("removido");
  const [eventos, setEventos] = useState<Evento[]>(CENARIOS.removido);
  const dias = useMemo(() => simular(eventos), [eventos]);
  const ultimo = dias.at(-1)!;

  const trocarDia = (indice: number) => {
    setEventos((atual) => atual.map((evento, i) => (i === indice ? proximoEvento(evento) : evento)));
    setCenario("proprio");
  };
  const escolherCenario = (nome: Cenario | "proprio") => {
    setCenario(nome);
    if (nome !== "proprio") setEventos(CENARIOS[nome]);
  };

  const opcoesCenario = (Object.keys(CENARIOS) as Cenario[]).map((nome) => ({ valor: nome, texto: t.simulador.nomesCenarios[nome] }));

  const conteudo = (
    <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
      <div className="rounded-3xl border border-linha bg-superficie p-5 sm:p-7">
        <p className="mb-3 font-mono text-xs text-tinta-3">{t.simulador.cenarios}</p>
        <Pilulas rotulo={t.simulador.cenarios} valor={cenario === "proprio" ? ("" as Cenario) : cenario} aoMudar={escolherCenario} opcoes={opcoesCenario} />

        <ol className="mt-8 grid grid-cols-7 gap-1.5 sm:gap-3">
          {dias.map((dia, i) => (
            <li key={i} className="flex flex-col items-center gap-2">
              <span className="font-mono text-[0.68rem] text-tinta-3">{t.simulador.dia(i + 1)}</span>
              <button type="button" onClick={() => trocarDia(i)} aria-label={t.simulador.trocar(i + 1, t.simulador.eventos[dia.evento])}
                className={cn("grid aspect-square w-full max-w-16 place-items-center rounded-2xl border text-xl font-semibold transition active:scale-95 sm:text-2xl", ESTILO_DO_EVENTO[dia.evento])}>
                <AnimatePresence mode="popLayout" initial={false}>
                  <motion.span key={dia.evento} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} transition={{ duration: 0.18 }}>
                    {SIMBOLO[dia.evento]}
                  </motion.span>
                </AnimatePresence>
              </button>
              {/* A decisão do dia: a cor da situação e, ao mudar, um pulso */}
              <motion.span key={`${i}-${dia.situacao}`} initial={dia.mudou ? { scale: 0.4 } : false} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 420, damping: 18 }}
                aria-hidden="true" className={cn("size-3.5 rounded-full", COR_DA_SITUACAO[dia.situacao], dia.mudou && "ring-4 ring-ambar/25")} />
              <span className={cn("hidden text-center text-[0.68rem] leading-tight", compacto ? "2xl:block" : "sm:block", TEXTO_DA_SITUACAO[dia.situacao])}>
                {t.simulador.situacoes[dia.situacao]}
              </span>
            </li>
          ))}
        </ol>

        <ul className="mt-8 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-linha pt-5 text-xs text-tinta-2 sm:grid-cols-4">
          {EVENTOS.map((evento) => (
            <li key={evento} className="flex items-start gap-2">
              <span aria-hidden="true" className={cn("grid size-5 shrink-0 place-items-center rounded-md border text-[0.7rem] font-semibold", ESTILO_DO_EVENTO[evento])}>{SIMBOLO[evento]}</span>
              <span><span className="font-medium text-tinta">{t.simulador.eventos[evento]}</span><br />{t.simulador.eventosDetalhe[evento]}</span>
            </li>
          ))}
        </ul>
      </div>

      <aside aria-live="polite" className="flex flex-col rounded-3xl border border-linha bg-superficie p-5 sm:p-7">
        <p className="font-mono text-xs text-tinta-3">{t.simulador.situacaoFinal}</p>
        <div className="mt-3 flex items-center gap-3">
          <span aria-hidden="true" className={cn("size-4 rounded-full", COR_DA_SITUACAO[ultimo.situacao])} />
          <span className={cn("text-3xl font-semibold tracking-[-0.03em]", TEXTO_DA_SITUACAO[ultimo.situacao])}>{t.simulador.situacoes[ultimo.situacao]}</span>
        </div>
        {ultimo.falhas > 0 && <p className="mt-1 font-mono text-xs text-tinta-2">{t.simulador.falhas(ultimo.falhas)}</p>}

        <ol className="mt-6 space-y-2.5 text-sm">
          {dias.map((dia, i) => (
            <li key={i} className={cn("flex gap-3 rounded-xl px-2 py-1.5", dia.mudou && "bg-superficie-2")}>
              <span className="w-12 shrink-0 font-mono text-xs leading-5 text-tinta-3">{t.simulador.dia(i + 1)}</span>
              <span className={cn("leading-5", dia.mudou ? "text-tinta" : "text-tinta-2")}>{t.simulador.motivos[dia.motivo]}</span>
            </li>
          ))}
        </ol>
        <p className="mt-auto border-t border-linha pt-4 text-xs leading-relaxed text-tinta-3">{t.simulador.regra}</p>
      </aside>
    </div>
  );

  if (compacto) return conteudo;
  return (
    <section aria-labelledby={id} className="py-24">
      <Miolo>
        <CabecalhoDeSecao id={id} kicker={t.simulador.kicker} titulo={t.simulador.titulo} lide={t.simulador.lide} />
        {conteudo}
      </Miolo>
    </section>
  );
}
