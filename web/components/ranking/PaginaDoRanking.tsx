"use client";

// Página do ranking: os órgãos com nota pelo conteúdo, da maior para a menor.
// Tabela no computador e cartões no celular, no mesmo estilo da lista de órgãos.
import Link from "next/link";
import { useMemo, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { CampoDeBusca, Escolha, Kicker, Miolo } from "@/components/ui";
import { filtrarOrgaos, formatarNumero, formatarPercentual, linkDoOrgao, nomeLegivel, type ItemDoRanking, type Ranking } from "@/lib/dados";
import { dataNaLingua } from "@/lib/i18n";
import { cn } from "@/lib/util";

const POR_PAGINA = 25;

// Abaixo desta cobertura, poucas bases do órgão foram avaliadas e a nota merece cuidado
const COBERTURA_BAIXA = 20;

// A barra da nota muda de cor com o valor (as classes precisam estar escritas por inteiro para o Tailwind achar)
function corDaNota(nota: number): string {
  if (nota >= 80) return "bg-ok";
  if (nota >= 50) return "bg-obs";
  return "bg-queb";
}

function BarraDaNota({ nota, rotulo }: { nota: number; rotulo: string }) {
  return (
    <div role="img" aria-label={`${rotulo}: ${formatarNumero(nota)}`} className="h-2 w-full overflow-hidden rounded-full bg-superficie-2">
      <div className={cn("h-full rounded-full", corDaNota(nota))} style={{ width: `${Math.max(2, Math.min(100, nota))}%` }} />
    </div>
  );
}

export function PaginaDoRanking({ ranking, dataColeta }: { ranking: Ranking | null; dataColeta: string | null }) {
  const { t, lingua } = useLingua();
  const [texto, setTexto] = useState("");
  const [esfera, setEsfera] = useState("");
  const [paginas, setPaginas] = useState(1);

  const orgaos: ItemDoRanking[] = ranking?.orgaos ?? [];
  // A API já entrega o ranking na ordem certa; o filtro só esconde linhas
  const resultado = useMemo(() => filtrarOrgaos(orgaos, { texto, esfera }), [orgaos, texto, esfera]);
  const visiveis = resultado.slice(0, paginas * POR_PAGINA);
  const mudar = <T,>(setar: (v: T) => void) => (v: T) => { setar(v); setPaginas(1); };

  if (!ranking) return <Miolo className="py-32 text-center text-tinta-2">{t.comum.semDados}</Miolo>;

  const esferas = [{ valor: "", texto: t.mapa.todas }, ...["FEDERAL", "ESTADUAL", "MUNICIPAL", "NAO_CLASSIFICADA"].map((e) => ({ valor: e, texto: t.esferas[e] }))];
  // Em dados mais antigos a chave minimo_verificaveis não existe: usa o mínimo da decisão 45
  const minimoVerificaveis = ranking.minimo_verificaveis ?? 5;

  return (
    <>
      <section className="relative overflow-hidden border-b border-linha">
        <div aria-hidden="true" className="fundo-pontos pointer-events-none absolute inset-0 -z-10" />
        <Miolo className="pb-12 pt-14">
          <Kicker>{t.ranking.kicker}{dataColeta ? ` · ${t.hero.coleta(dataNaLingua(dataColeta, lingua))}` : ""}</Kicker>
          <h1 className="mt-4 max-w-4xl text-balance text-[clamp(2rem,4.6vw,3.6rem)] font-semibold leading-[1.02] tracking-[-0.04em] text-tinta">{t.ranking.titulo}</h1>
          <p className="mt-5 max-w-3xl text-base leading-relaxed text-tinta-2 sm:text-lg">{t.ranking.lide(ranking.minimo_bases, minimoVerificaveis)}</p>
          <p className="mt-4 max-w-3xl text-sm leading-relaxed text-tinta-2">
            {t.ranking.aviso}{" "}
            <Link href="/metodologia/#nota" className="text-tinta underline decoration-ambar underline-offset-4">{t.ranking.comoNota}</Link>
          </p>
        </Miolo>
      </section>

      <section aria-labelledby="titulo-ranking" className="py-16">
        <Miolo>
          <h2 id="titulo-ranking" className="so-leitor">{t.ranking.lista}</h2>

          {orgaos.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-linha-2 p-10 text-center text-tinta-2">{t.ranking.semRanking}</p>
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
                <CampoDeBusca rotulo={t.ranking.buscar} valor={texto} aoMudar={mudar(setTexto)} exemplo={t.ranking.exemplo} />
                <Escolha rotulo={t.ranking.esfera} valor={esfera} aoMudar={mudar(setEsfera)} opcoes={esferas} />
              </div>

              <p aria-live="polite" className="mt-4 font-mono text-xs text-tinta-3">{t.ranking.contagem(resultado.length, orgaos.length)}</p>

              {resultado.length === 0 ? (
                <p className="mt-4 rounded-2xl border border-dashed border-linha-2 p-10 text-center text-tinta-2">{t.ranking.vazio}</p>
              ) : (
                <>
                  {/* Computador: tabela */}
                  <div className="mt-4 hidden overflow-hidden rounded-2xl border border-linha bg-superficie md:block">
                    <table className="w-full text-sm">
                      <caption className="so-leitor">{t.ranking.lista}</caption>
                      <thead className="border-b border-linha bg-superficie-2 text-left text-xs text-tinta-2">
                        <tr>
                          <th scope="col" className="w-16 px-5 py-3 font-medium">{t.ranking.colunas.posicao}</th>
                          <th scope="col" className="px-3 py-3 font-medium">{t.ranking.colunas.orgao}</th>
                          <th scope="col" className="w-64 px-3 py-3 font-medium">{t.ranking.colunas.nota}</th>
                          <th scope="col" className="px-3 py-3 text-right font-medium">{t.ranking.colunas.cobertura}</th>
                          <th scope="col" className="px-5 py-3 text-right font-medium">{t.ranking.colunas.bases}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visiveis.map((orgao) => (
                          <tr key={orgao.slug} className="group relative border-b border-linha last:border-0 hover:bg-superficie-2/60">
                            <td className="numeros px-5 py-3.5 font-mono text-tinta-2">{orgao.posicao}</td>
                            <td className="px-3 py-3.5">
                              <Link href={linkDoOrgao(orgao.slug)} className="font-medium text-tinta after:absolute after:inset-0 group-hover:underline group-hover:decoration-ambar group-hover:underline-offset-4">
                                {nomeLegivel(orgao.nome)}
                              </Link>
                              <div className="mt-0.5 text-xs text-tinta-3">{t.esferas[orgao.esfera] ?? orgao.esfera}</div>
                            </td>
                            <td className="px-3 py-3.5">
                              <div className="flex items-center gap-3">
                                <span className="numeros w-12 shrink-0 text-right font-mono font-semibold text-tinta">{formatarNumero(orgao.nota)}</span>
                                <BarraDaNota nota={orgao.nota} rotulo={nomeLegivel(orgao.nome)} />
                              </div>
                            </td>
                            <td className={cn("numeros px-3 py-3.5 text-right font-mono", orgao.cobertura < COBERTURA_BAIXA ? "text-obs-texto" : "text-tinta-2")}
                              title={orgao.cobertura < COBERTURA_BAIXA ? t.ranking.coberturaBaixa : undefined}>
                              {formatarPercentual(orgao.cobertura)}
                            </td>
                            <td className="numeros px-5 py-3.5 text-right font-mono text-tinta-2">{t.ranking.basesDe(orgao.bases_verificaveis, orgao.qtd_bases)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Celular: cartões */}
                  <ul className="mt-4 grid gap-3 md:hidden">
                    {visiveis.map((orgao) => (
                      <li key={orgao.slug} className="relative rounded-2xl border border-linha bg-superficie p-4">
                        <div className="flex items-start gap-3">
                          <span className="numeros font-mono text-sm text-tinta-3">{orgao.posicao}</span>
                          <div className="min-w-0 flex-1">
                            <Link href={linkDoOrgao(orgao.slug)} className="font-medium text-tinta after:absolute after:inset-0">{nomeLegivel(orgao.nome)}</Link>
                            <div className="mt-0.5 text-xs text-tinta-3">{t.esferas[orgao.esfera] ?? orgao.esfera}</div>
                          </div>
                          <span className="numeros font-mono text-lg font-semibold text-tinta">{formatarNumero(orgao.nota)}</span>
                        </div>
                        <div className="mt-3"><BarraDaNota nota={orgao.nota} rotulo={nomeLegivel(orgao.nome)} /></div>
                        <dl className="numeros mt-3 grid grid-cols-2 gap-2 font-mono text-xs">
                          <div>
                            <dt className="text-tinta-3">{t.ranking.colunas.cobertura}</dt>
                            <dd className={orgao.cobertura < COBERTURA_BAIXA ? "text-obs-texto" : "text-tinta"}>{formatarPercentual(orgao.cobertura)}</dd>
                          </div>
                          <div>
                            <dt className="text-tinta-3">{t.ranking.colunas.bases}</dt>
                            <dd className="text-tinta">{t.ranking.basesDe(orgao.bases_verificaveis, orgao.qtd_bases)}</dd>
                          </div>
                        </dl>
                      </li>
                    ))}
                  </ul>

                  {visiveis.length < resultado.length && (
                    <div className="mt-6 text-center">
                      <button type="button" onClick={() => setPaginas((p) => p + 1)}
                        className="h-11 rounded-full border border-linha-2 bg-superficie px-6 text-sm font-medium text-tinta transition hover:border-tinta-3">
                        {t.ranking.mais}
                      </button>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </Miolo>
      </section>
    </>
  );
}
