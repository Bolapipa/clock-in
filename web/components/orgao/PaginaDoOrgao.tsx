"use client";

// Página do órgão: números, régua de saúde dos links, contagem de status e a lista de bases.
// Cada base abre num painel lateral; o endereço ganha ?base=, então o painel pode ser compartilhado.
import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { PainelDaBase } from "@/components/orgao/PainelDaBase";
import { useLingua } from "@/components/Provedores";
import { COR_DO_ESTADO, CampoDeBusca, Escolha, Kicker, Miolo, Regua, Status } from "@/components/ui";
import { usarOrgao } from "@/lib/cliente";
import {
  ORDENS_BASES, filtrarBases, formatarNumero, formatarPercentual, lerOrdem, nomeLegivel, ordenar, partesDaRegua, slugValido,
  type Base, type OrgaoResumo,
} from "@/lib/dados";
import { dataNaLingua } from "@/lib/i18n";
import { cn } from "@/lib/util";

const POR_PAGINA = 50;

function Ficha({ titulo, valor, sub, tom }: { titulo: string; valor: string; sub: string; tom?: string }) {
  return (
    <div className="rounded-2xl border border-linha bg-superficie p-5">
      <div className="text-sm text-tinta-2">{titulo}</div>
      <div className={cn("numeros mt-2 text-3xl font-semibold tracking-[-0.03em]", tom ?? "text-tinta")}>{valor}</div>
      <div className="mt-1 font-mono text-xs text-tinta-3">{sub}</div>
    </div>
  );
}

export function PaginaDoOrgao({ orgao, dataColeta }: { orgao: OrgaoResumo | null; dataColeta: string | null }) {
  const { t, lingua } = useLingua();
  if (!orgao) return <Miolo className="py-32 text-center text-tinta-2">{t.comum.semDados}</Miolo>;

  const partes = partesDaRegua({ total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados });
  const esfera = t.esferas[orgao.esfera] ?? orgao.esfera;

  return (
    <>
      <section className="relative overflow-hidden border-b border-linha">
        <div aria-hidden="true" className="fundo-pontos pointer-events-none absolute inset-0 -z-10" />
        <Miolo className="pb-12 pt-8">
          <nav aria-label="Você está em" className="flex items-center gap-1.5 text-sm text-tinta-3">
            <Link href="/" className="hover:text-tinta">{t.orgao.inicio}</Link>
            <ChevronRight className="size-3.5" aria-hidden="true" />
            <Link href="/#orgaos" className="hover:text-tinta">{t.orgao.orgaos}</Link>
            <ChevronRight className="size-3.5" aria-hidden="true" />
            <span aria-current="page" className="truncate text-tinta-2">{nomeLegivel(orgao.nome)}</span>
          </nav>
          <div className="mt-8">
            <Kicker>{t.orgao.resumo(esfera, orgao.qtd_bases)}{dataColeta ? ` · ${t.hero.coleta(dataNaLingua(dataColeta, lingua))}` : ""}</Kicker>
            <h1 className="mt-4 max-w-4xl text-balance text-[clamp(2rem,4.6vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.04em] text-tinta">{nomeLegivel(orgao.nome)}</h1>
          </div>

          <div className="mt-10 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Ficha titulo={t.orgao.respondendo} valor={formatarPercentual(orgao.percentual_ok)} sub={t.orgao.respondendoSub(orgao.links_ok)}
              tom={orgao.percentual_ok != null && orgao.percentual_ok >= 90 ? "text-ok-texto" : undefined} />
            <Ficha titulo={t.orgao.testados} valor={formatarNumero(orgao.links_testados)} sub={t.orgao.testadosSub(orgao.links_total, orgao.cobertura_links)} />
            <Ficha titulo={t.numeros.quebrados} valor={formatarNumero(orgao.links_quebrados)} sub={t.numeros.quebradosSub}
              tom={orgao.links_quebrados ? "text-queb-texto" : undefined} />
            <Ficha titulo={t.orgao.foraDoAr} valor={formatarNumero(orgao.bases_fora_do_ar)} sub={t.orgao.foraDoArSub}
              tom={orgao.bases_fora_do_ar ? "text-queb-texto" : undefined} />
          </div>

          <div className="mt-8 rounded-2xl border border-linha bg-superficie p-5">
            <p className="mb-3 text-sm font-medium text-tinta">{t.orgao.regua}</p>
            <Regua partes={partes} rotulo={t.orgao.regua} altura="h-4" />
            <ul className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              {partes.map((parte) => (
                <li key={parte.chave} className="flex items-start gap-2">
                  <span aria-hidden="true" className={cn("mt-1.5 size-2.5 shrink-0 rounded-full", COR_DO_ESTADO[parte.chave])} />
                  <span>
                    <span className="text-tinta">{t.estados[parte.chave]}</span>
                    <span className="numeros block font-mono text-xs text-tinta-3">{formatarNumero(parte.quantidade)} · {formatarPercentual(parte.percentual)}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </Miolo>
      </section>

      <ListaDeBases slug={orgao.slug} />
    </>
  );
}

function ListaDeBases({ slug }: { slug: string }) {
  const { t } = useLingua();
  const carga = usarOrgao(slug);
  const router = useRouter();
  const caminho = usePathname();
  const parametros = useSearchParams();
  const baseAberta = slugValido(parametros.get("base"));

  const [texto, setTexto] = useState("");
  const [ordem, setOrdem] = useState(ORDENS_BASES[0].valor);
  const [soProblemas, setSoProblemas] = useState(false);
  const [paginas, setPaginas] = useState(1);

  const bases = carga.estado === "pronto" ? carga.dados.bases : [];
  const resultado = useMemo(() => {
    const { coluna, direcao } = lerOrdem(ordem, ORDENS_BASES[0].valor);
    return ordenar(filtrarBases(bases, { texto, apenasProblemas: soProblemas }), coluna, direcao);
  }, [bases, texto, soProblemas, ordem]);
  const visiveis = resultado.slice(0, paginas * POR_PAGINA);
  const mudar = <T,>(setar: (v: T) => void) => (v: T) => { setar(v); setPaginas(1); };

  // Abrir e fechar o painel muda só o ?base= do endereço, sem rolar a página
  const abrir = useCallback((base: Base) => router.push(`${caminho}?base=${encodeURIComponent(base.slug)}`, { scroll: false }), [router, caminho]);
  const fechar = useCallback(() => router.push(caminho, { scroll: false }), [router, caminho]);
  const base = baseAberta ? bases.find((b) => b.slug === baseAberta) ?? null : null;

  const ordens = ORDENS_BASES.map((o) => ({ valor: o.valor, texto: t.orgao.ordens[o.valor] ?? o.texto }));

  return (
    <section aria-labelledby="titulo-bases" className="py-16">
      <Miolo>
        <h2 id="titulo-bases" className="text-2xl font-semibold tracking-[-0.03em] text-tinta sm:text-3xl">{t.orgao.bases}</h2>
        <div className="mt-6 grid gap-3 sm:grid-cols-[1fr_16rem_auto]">
          <CampoDeBusca rotulo={t.orgao.buscar} valor={texto} aoMudar={mudar(setTexto)} exemplo={t.orgao.exemplo} />
          <Escolha rotulo={t.lista.ordenar} valor={ordem} aoMudar={mudar(setOrdem)} opcoes={ordens} />
          <label className="flex h-11 cursor-pointer items-center gap-2.5 rounded-full border border-linha bg-superficie px-4 text-sm text-tinta">
            <input type="checkbox" checked={soProblemas} onChange={(e) => mudar(setSoProblemas)(e.target.checked)} className="size-4 accent-[var(--ambar-forte)]" />
            {t.orgao.soProblemas}
          </label>
        </div>

        {carga.estado === "carregando" && (
          <div role="status" className="mt-6 space-y-2">
            <span className="so-leitor">{t.orgao.carregando}</span>
            {Array.from({ length: 6 }, (_, i) => <div key={i} className="h-14 animate-pulse rounded-xl bg-superficie-2" />)}
          </div>
        )}
        {carga.estado === "erro" && <p role="alert" className="mt-6 rounded-2xl border border-queb/40 bg-queb/10 p-5 text-queb-texto">{t.orgao.erro}</p>}

        {carga.estado === "pronto" && (
          <>
            <p aria-live="polite" className="mt-4 font-mono text-xs text-tinta-3">{t.orgao.contagem(resultado.length, bases.length)}</p>
            {resultado.length === 0 ? (
              <p className="mt-4 rounded-2xl border border-dashed border-linha-2 p-10 text-center text-tinta-2">{t.orgao.vazio}</p>
            ) : (
              <ul className="mt-4 divide-y divide-linha overflow-hidden rounded-2xl border border-linha bg-superficie">
                {visiveis.map((b) => (
                  <li key={b.slug}>
                    <button type="button" onClick={() => abrir(b)}
                      className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-5 py-4 text-left transition hover:bg-superficie-2/60 md:grid-cols-[1fr_7rem_14rem_7rem]">
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-tinta">{b.titulo || b.slug}</span>
                        <span className="mt-0.5 block text-xs text-tinta-3">{t.orgao.periodicidade(t.periodicidades[b.periodicidade] ?? b.periodicidade)}</span>
                      </span>
                      <span className="justify-self-end md:order-last"><Status status={b.status} /></span>
                      <span className="numeros hidden font-mono text-xs text-tinta-2 md:block">{t.contarLinks(b.links_total)}</span>
                      <span className="col-span-2 md:col-span-1">
                        <Regua altura="h-2" rotulo={b.titulo ?? b.slug}
                          partes={partesDaRegua({ total: b.links_total, ok: b.links_ok, emObservacao: b.links_em_observacao, quebrados: b.links_quebrados })} />
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {visiveis.length < resultado.length && (
              <div className="mt-6 text-center">
                <button type="button" onClick={() => setPaginas((p) => p + 1)}
                  className="h-11 rounded-full border border-linha-2 bg-superficie px-6 text-sm font-medium text-tinta transition hover:border-tinta-3">
                  {t.orgao.mais}
                </button>
              </div>
            )}
          </>
        )}
      </Miolo>

      <PainelDaBase aberto={Boolean(baseAberta)} base={base} carregando={carga.estado === "carregando"} aoFechar={fechar} />
    </section>
  );
}
