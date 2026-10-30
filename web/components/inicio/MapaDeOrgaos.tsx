"use client";

// Mapa de órgãos: cada bolha é um órgão (tamanho = bases, cor = parte dos links respondendo bem).
// Passar o mouse mostra os números; clicar abre o órgão. A lista logo abaixo traz os mesmos dados em texto.
import { hierarchy, pack } from "d3-hierarchy";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { CabecalhoDeSecao, Miolo, Pilulas } from "@/components/ui";
import { FAIXAS, faixaDoPercentual, type Faixa } from "@/lib/cores";
import { formatarNumero, formatarPercentual, linkDoOrgao, type OrgaoResumo } from "@/lib/dados";

const LADO = 1000;

// Cor de cada faixa: verde, verde mais claro, âmbar, laranja, vermelho e hachurado
const PREENCHIMENTO: Record<Faixa, string> = {
  otima: "var(--ok)",
  boa: "color-mix(in oklab, var(--ok) 55%, var(--superficie))",
  atencao: "var(--obs)",
  ruim: "color-mix(in oklab, var(--obs) 45%, var(--queb))",
  critica: "var(--queb)",
  sem_percentual: "url(#hachura-mapa)",
};

type Esfera = "" | "FEDERAL" | "ESTADUAL" | "MUNICIPAL";

// Rótulo dentro da bolha: só a sigla antes do " - " (ex.: "BCB - Banco Central do Brasil"); sem sigla, sem rótulo
function sigla(nome: string): string | null {
  const partes = nome.split(" - ");
  const candidata = partes[0].trim();
  return partes.length > 1 && candidata.length <= 10 && !candidata.includes(" ") ? candidata : null;
}

export function MapaDeOrgaos({ orgaos }: { orgaos: OrgaoResumo[] }) {
  const { t } = useLingua();
  const router = useRouter();
  const [esfera, setEsfera] = useState<Esfera>("");
  const [apontado, setApontado] = useState<string | null>(null);

  const bolhas = useMemo(() => {
    const filtrados = orgaos.filter((orgao) => !esfera || orgao.esfera === esfera);
    const raiz = hierarchy<{ filhos?: OrgaoResumo[] } | OrgaoResumo>({ filhos: filtrados }, (n) => ("filhos" in n ? n.filhos : undefined))
      .sum((n) => ("qtd_bases" in n ? Math.max(n.qtd_bases, 1) : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    return pack<{ filhos?: OrgaoResumo[] } | OrgaoResumo>().size([LADO, LADO]).padding(3)(raiz)
      .leaves()
      .map((folha) => ({ orgao: folha.data as OrgaoResumo, x: folha.x, y: folha.y, r: folha.r }));
  }, [orgaos, esfera]);

  const info = bolhas.find((b) => b.orgao.slug === apontado);
  const opcoes: { valor: Esfera; texto: string }[] = [
    { valor: "", texto: t.mapa.todas },
    { valor: "FEDERAL", texto: t.esferas.FEDERAL },
    { valor: "ESTADUAL", texto: t.esferas.ESTADUAL },
    { valor: "MUNICIPAL", texto: t.esferas.MUNICIPAL },
  ];

  return (
    <section aria-labelledby="titulo-mapa" className="py-24">
      <Miolo>
        <CabecalhoDeSecao id="titulo-mapa" kicker={t.mapa.kicker} titulo={t.mapa.titulo} lide={t.mapa.lide}>
          <Pilulas rotulo={t.lista.esfera} valor={esfera} aoMudar={setEsfera} opcoes={opcoes} />
        </CabecalhoDeSecao>

        <div className="grid gap-8 lg:grid-cols-[1fr_15rem]">
          <div className="relative mx-auto w-full max-w-[52rem]">
            <svg viewBox={`0 0 ${LADO} ${LADO}`} role="img" aria-label={t.mapa.descricao(bolhas.length)} className="w-full overflow-visible">
              <defs>
                <pattern id="hachura-mapa" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="8" height="8" fill="var(--superficie-2)" />
                  <line x1="0" y1="0" x2="0" y2="8" stroke="var(--nt)" strokeWidth="2.5" />
                </pattern>
              </defs>
              {bolhas.map(({ orgao, x, y, r }) => {
                const faixa = faixaDoPercentual(orgao.percentual_ok);
                const ativo = apontado === orgao.slug;
                return (
                  <g key={orgao.slug} className="cursor-pointer" onPointerEnter={() => setApontado(orgao.slug)} onPointerLeave={() => setApontado(null)}
                    onClick={() => router.push(linkDoOrgao(orgao.slug))}>
                    <motion.circle initial={false} animate={{ cx: x, cy: y, r }} transition={{ type: "spring", stiffness: 120, damping: 20 }}
                      fill={PREENCHIMENTO[faixa]} stroke={ativo ? "var(--tinta)" : orgao.links_quebrados > 0 ? "var(--queb)" : "transparent"}
                      strokeWidth={ativo ? 3 : orgao.links_quebrados > 0 ? 1.5 : 0} opacity={apontado && !ativo ? 0.55 : 1} />
                    {r > 26 && sigla(orgao.nome) && (
                      <motion.text initial={false} animate={{ x, y }} transition={{ type: "spring", stiffness: 120, damping: 20 }}
                        textAnchor="middle" dominantBaseline="central" className="pointer-events-none select-none fill-[var(--ambar-tinta)] font-sans"
                        style={{ fontSize: Math.min(r / 2.6, 30), fontWeight: 600 }}>
                        {sigla(orgao.nome)}
                      </motion.text>
                    )}
                  </g>
                );
              })}
            </svg>

            {/* Dica da bolha apontada (posição em porcentagem do quadro) */}
            {info && (
              <div className="pointer-events-none absolute z-10 w-64 -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-xl border border-linha bg-superficie/95 p-3 shadow-xl backdrop-blur"
                style={{ left: `${(info.x / LADO) * 100}%`, top: `${((info.y - info.r) / LADO) * 100}%` }}>
                <div className="text-sm font-semibold leading-snug text-tinta">{info.orgao.nome}</div>
                <dl className="numeros mt-2 grid grid-cols-3 gap-2 font-mono text-xs">
                  <div><dt className="text-tinta-3">{t.mapa.bases}</dt><dd className="text-tinta">{formatarNumero(info.orgao.qtd_bases)}</dd></div>
                  <div><dt className="text-tinta-3">{t.mapa.respondendo}</dt><dd className="text-tinta">{formatarPercentual(info.orgao.percentual_ok)}</dd></div>
                  <div><dt className="text-tinta-3">{t.mapa.quebrados}</dt><dd className={info.orgao.links_quebrados ? "text-queb-texto" : "text-tinta"}>{formatarNumero(info.orgao.links_quebrados)}</dd></div>
                </dl>
              </div>
            )}
          </div>

          <div className="self-start rounded-2xl border border-linha bg-superficie p-4">
            <p className="font-mono text-xs text-tinta-3">{t.mapa.legenda}</p>
            <ul className="mt-3 space-y-2 text-sm">
              {FAIXAS.map(({ faixa }) => (
                <li key={faixa} className="flex items-center gap-2.5 text-tinta-2">
                  <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0">
                    <circle cx="8" cy="8" r="7" fill={PREENCHIMENTO[faixa]} />
                  </svg>
                  {t.mapa.faixas[faixa]}
                </li>
              ))}
              <li className="flex items-center gap-2.5 border-t border-linha pt-2 text-tinta-2">
                <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4 shrink-0"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--queb)" strokeWidth="1.5" /></svg>
                {t.mapa.quebrados}
              </li>
            </ul>
          </div>
        </div>
      </Miolo>
    </section>
  );
}

