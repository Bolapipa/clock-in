"use client";

// O dia em números: cada valor conta até o número real quando a faixa aparece na tela
import { useInView } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { Miolo } from "@/components/ui";
import { formatarNumero, type Resumo } from "@/lib/dados";
import { cn } from "@/lib/util";

function Contador({ valor }: { valor: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const visto = useInView(ref, { once: true, margin: "-10% 0px" });
  const [atual, setAtual] = useState(valor);

  useEffect(() => {
    if (!visto) return;
    // Quem pediu "reduzir movimento" vê o número final direto
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setAtual(valor); return; }
    const duracao = 1400;
    const inicio = performance.now();
    let quadro = 0;
    const passo = (agora: number) => {
      const progresso = Math.min(1, (agora - inicio) / duracao);
      // Desacelera no fim (cúbica)
      setAtual(Math.round(valor * (1 - (1 - progresso) ** 3)));
      if (progresso < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    // Garantia: se a animação não rodar (aba em segundo plano), o número final aparece mesmo assim
    const garantia = window.setTimeout(() => setAtual(valor), duracao + 300);
    return () => { cancelAnimationFrame(quadro); window.clearTimeout(garantia); };
  }, [visto, valor]);

  return <span ref={ref} className="numeros">{formatarNumero(atual)}</span>;
}

export function Numeros({ resumo }: { resumo: Resumo }) {
  const { t } = useLingua();
  const itens = [
    { titulo: t.numeros.bases, valor: resumo.bases, sub: t.numeros.basesSub(resumo.recursos), tom: "" },
    { titulo: t.numeros.orgaos, valor: resumo.orgaos, sub: t.numeros.orgaosSub, tom: "" },
    { titulo: t.numeros.testados, valor: resumo.links.testados, sub: t.numeros.testadosSub(resumo.links.total, resumo.links.cobertura), tom: "" },
    { titulo: t.numeros.quebrados, valor: resumo.links.quebrados, sub: t.numeros.quebradosSub, tom: "text-queb-texto" },
    { titulo: t.numeros.foraDoAr, valor: resumo.bases_fora_do_ar, sub: t.numeros.foraDoArSub, tom: "text-queb-texto" },
  ];
  return (
    <section aria-label={t.numeros.titulo} className="border-y border-linha bg-superficie">
      <Miolo className="grid grid-cols-2 divide-linha md:grid-cols-5 md:divide-x">
        {itens.map((item, i) => (
          <div key={item.titulo} className={cn("px-2 py-8 md:px-6", i === 0 && "md:pl-0", i === 4 && "col-span-2 md:col-span-1")}>
            <div className="text-sm text-tinta-2">{item.titulo}</div>
            <div className={cn("mt-2 text-3xl font-semibold tracking-[-0.03em] sm:text-4xl", item.tom || "text-tinta")}>
              <Contador valor={item.valor} />
            </div>
            <div className="mt-1.5 font-mono text-xs text-tinta-3">{item.sub}</div>
          </div>
        ))}
      </Miolo>
    </section>
  );
}
