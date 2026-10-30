"use client";

// Herói da página inicial: a pergunta, a resposta do dia e o mostrador de links com a legenda clicável
import { ArrowDown, ArrowUpRight } from "lucide-react";
import { motion } from "motion/react";

import { Mostrador } from "@/components/Mostrador";
import { useLingua } from "@/components/Provedores";
import { Botao, COR_DO_ESTADO, Kicker, Miolo } from "@/components/ui";
import { formatarNumero, formatarPercentual, partesDaRegua, type ChaveDaParte, type Resumo } from "@/lib/dados";
import { dataNaLingua } from "@/lib/i18n";
import { cn } from "@/lib/util";

const STACK = ["Python", "DuckDB", "Parquet", "GitHub Actions", "Next.js", "WebGPU", "Vercel"];

// Entrada única e orquestrada: os blocos do texto aparecem em sequência no carregamento
const aparecer = {
  oculto: { opacity: 0, y: 14 },
  visivel: (ordem: number) => ({ opacity: 1, y: 0, transition: { delay: 0.08 * ordem, duration: 0.6, ease: [0.22, 1, 0.36, 1] as const } }),
};

export function Heroi({ resumo, selecionado, aoSelecionar }: { resumo: Resumo; selecionado: ChaveDaParte | null; aoSelecionar: (chave: ChaveDaParte | null) => void }) {
  const { t, lingua } = useLingua();
  const links = resumo.links;
  const partes = partesDaRegua({ total: links.total, ok: links.ok, emObservacao: links.em_observacao, quebrados: links.quebrados });
  const data = dataNaLingua(resumo.data_coleta, lingua);

  return (
    <section id="panorama" aria-labelledby="titulo-heroi" className="relative overflow-hidden">
      <div aria-hidden="true" className="fundo-pontos pointer-events-none absolute inset-0 -z-10" />
      {/* Brilho âmbar suave atrás do mostrador */}
      <div aria-hidden="true" className="pointer-events-none absolute -right-40 top-10 -z-10 size-[42rem] rounded-full bg-ambar/10 blur-3xl dark:bg-ambar/[0.07]" />
      <Miolo className="grid items-center gap-12 pb-16 pt-12 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:pb-24 lg:pt-20">
        <div>
          <motion.div initial="oculto" animate="visivel" custom={0} variants={aparecer}>
            <Kicker>{t.hero.kicker} · {t.hero.coleta(data)}</Kicker>
          </motion.div>
          <motion.h1 id="titulo-heroi" initial="oculto" animate="visivel" custom={1} variants={aparecer}
            className="mt-5 text-balance text-[clamp(2.6rem,6vw,4.6rem)] font-semibold leading-[0.98] tracking-[-0.045em] text-tinta">
            {t.hero.titulo}
          </motion.h1>
          <motion.p initial="oculto" animate="visivel" custom={2} variants={aparecer}
            className="mt-6 max-w-xl text-pretty text-xl leading-snug text-tinta sm:text-2xl">
            {t.resposta(links)}
          </motion.p>
          <motion.p initial="oculto" animate="visivel" custom={3} variants={aparecer} className="mt-4 max-w-xl text-pretty leading-relaxed text-tinta-2">
            {t.hero.lide(resumo.bases)}
          </motion.p>
          <motion.div initial="oculto" animate="visivel" custom={4} variants={aparecer} className="mt-8 flex flex-wrap gap-3">
            <Botao href="#orgaos">{t.hero.ctaOrgaos}<ArrowDown className="size-4" /></Botao>
            <Botao href="/metodologia/" variante="secundario">{t.hero.ctaMetodo}<ArrowUpRight className="size-4" /></Botao>
          </motion.div>
          <motion.div initial="oculto" animate="visivel" custom={5} variants={aparecer}
            className="mt-10 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-linha pt-5 font-mono text-xs text-tinta-3">
            <span>{t.hero.stack}</span>
            {STACK.map((item) => <span key={item} className="text-tinta-2">{item}</span>)}
          </motion.div>
        </div>

        <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto w-full max-w-[34rem]">
          <Mostrador partes={partes} percentual={links.percentual_ok} data={t.hero.coleta(data)} selecionado={selecionado} aoSelecionar={aoSelecionar} />
          <div className="mt-4 grid grid-cols-2 gap-2">
            {partes.map((parte) => {
              const ativo = selecionado === parte.chave;
              return (
                <button key={parte.chave} type="button" aria-pressed={ativo} onClick={() => aoSelecionar(ativo ? null : parte.chave)}
                  className={cn("group flex items-start gap-3 rounded-2xl border p-3 text-left transition",
                    ativo ? "border-tinta bg-superficie shadow-sm" : "border-linha bg-superficie/70 hover:border-linha-2")}>
                  <span aria-hidden="true" className={cn("mt-1 size-3 shrink-0 rounded-full", COR_DO_ESTADO[parte.chave])} />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-tinta">{t.estados[parte.chave]}</span>
                    <span className="numeros block font-mono text-xs text-tinta-2">{formatarNumero(parte.quantidade)} · {formatarPercentual(parte.percentual)}</span>
                  </span>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-center text-xs text-tinta-3">{t.mostrador.dica}</p>
        </motion.div>
      </Miolo>
    </section>
  );
}
