"use client";

// Lista de órgãos: busca, esfera, ordem e o filtro vindo do mostrador. Tabela no computador, cartões no celular.
import { X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { CabecalhoDeSecao, CampoDeBusca, Escolha, Miolo, Regua } from "@/components/ui";
import {
  ORDENS_ORGAOS, filtrarOrgaos, filtrarPorEstado, formatarNumero, formatarPercentual, lerOrdem, linkDoOrgao, ordenar,
  partesDaRegua, type ChaveDaParte, type OrgaoResumo,
} from "@/lib/dados";
import { cn } from "@/lib/util";

const POR_PAGINA = 25;

export function ListaDeOrgaos({ orgaos, estado, limparEstado }: { orgaos: OrgaoResumo[]; estado: ChaveDaParte | null; limparEstado: () => void }) {
  const { t } = useLingua();
  const [texto, setTexto] = useState("");
  const [esfera, setEsfera] = useState("");
  const [ordem, setOrdem] = useState(ORDENS_ORGAOS[0].valor);
  const [paginas, setPaginas] = useState(1);

  const resultado = useMemo(() => {
    const filtrados = filtrarOrgaos(orgaos, { texto, esfera });
    // Com um estado escolhido no mostrador, a ordem é a do problema escolhido
    if (estado) return filtrarPorEstado(filtrados, estado);
    const { coluna, direcao } = lerOrdem(ordem);
    return ordenar(filtrados, coluna, direcao);
  }, [orgaos, texto, esfera, ordem, estado]);
  const visiveis = resultado.slice(0, paginas * POR_PAGINA);
  const mudar = <T,>(setar: (v: T) => void) => (v: T) => { setar(v); setPaginas(1); };

  const esferas = [{ valor: "", texto: t.mapa.todas }, ...["FEDERAL", "ESTADUAL", "MUNICIPAL", "NAO_CLASSIFICADA"].map((e) => ({ valor: e, texto: t.esferas[e] }))];
  const ordens = ORDENS_ORGAOS.map((o) => ({ valor: o.valor, texto: t.lista.ordens[o.valor] ?? o.texto }));

  return (
    <section id="orgaos" aria-labelledby="titulo-lista" className="scroll-mt-20 py-24">
      <Miolo>
        <CabecalhoDeSecao id="titulo-lista" kicker={t.lista.kicker} titulo={t.lista.titulo} />

        <div className="grid gap-3 sm:grid-cols-[1fr_12rem_16rem]">
          <CampoDeBusca rotulo={t.lista.buscar} valor={texto} aoMudar={mudar(setTexto)} exemplo={t.lista.exemplo} />
          <Escolha rotulo={t.lista.esfera} valor={esfera} aoMudar={mudar(setEsfera)} opcoes={esferas} />
          <Escolha rotulo={t.lista.ordenar} valor={ordem} aoMudar={mudar(setOrdem)} opcoes={ordens} />
        </div>

        <div className="mt-4 flex min-h-8 flex-wrap items-center gap-3">
          <p aria-live="polite" className="font-mono text-xs text-tinta-3">{t.lista.contagem(resultado.length, orgaos.length)}</p>
          {estado && (
            <button type="button" onClick={limparEstado}
              className="inline-flex items-center gap-1.5 rounded-full border border-ambar/50 bg-ambar/10 px-3 py-1 text-xs text-tinta">
              {t.lista.filtroEstado(t.estados[estado])}<X className="size-3.5" aria-label={t.lista.limparFiltro} />
            </button>
          )}
        </div>

        {resultado.length === 0 ? (
          <p className="mt-6 rounded-2xl border border-dashed border-linha-2 p-10 text-center text-tinta-2">{t.lista.vazio}</p>
        ) : (
          <>
            {/* Computador: tabela */}
            <div className="mt-4 hidden overflow-hidden rounded-2xl border border-linha bg-superficie md:block">
              <table className="w-full text-sm">
                <caption className="so-leitor">{t.lista.titulo}</caption>
                <thead className="border-b border-linha bg-superficie-2 text-left text-xs text-tinta-2">
                  <tr>
                    <th scope="col" className="px-5 py-3 font-medium">{t.lista.colunas.orgao}</th>
                    <th scope="col" className="px-3 py-3 text-right font-medium">{t.lista.colunas.bases}</th>
                    <th scope="col" className="w-64 px-3 py-3 font-medium">{t.lista.colunas.respondendo}</th>
                    <th scope="col" className="px-3 py-3 text-right font-medium">{t.lista.colunas.observacao}</th>
                    <th scope="col" className="px-5 py-3 text-right font-medium">{t.lista.colunas.quebrados}</th>
                  </tr>
                </thead>
                <tbody>
                  {visiveis.map((orgao) => (
                    <tr key={orgao.slug} className="group relative border-b border-linha last:border-0 hover:bg-superficie-2/60">
                      <td className="px-5 py-3.5">
                        <Link href={linkDoOrgao(orgao.slug)} className="font-medium text-tinta after:absolute after:inset-0 group-hover:underline group-hover:decoration-ambar group-hover:underline-offset-4">
                          {orgao.nome}
                        </Link>
                        <div className="mt-0.5 text-xs text-tinta-3">{t.esferas[orgao.esfera] ?? orgao.esfera}</div>
                      </td>
                      <td className="numeros px-3 py-3.5 text-right font-mono text-tinta-2">{formatarNumero(orgao.qtd_bases)}</td>
                      <td className="px-3 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="numeros w-14 shrink-0 text-right font-mono text-tinta" title={orgao.percentual_ok == null ? t.lista.semPercentual : undefined}>
                            {formatarPercentual(orgao.percentual_ok)}
                          </span>
                          <Regua altura="h-2" rotulo={orgao.nome} partes={partesDaRegua({ total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados })} />
                        </div>
                      </td>
                      <td className={cn("numeros px-3 py-3.5 text-right font-mono", orgao.links_em_observacao ? "text-obs-texto" : "text-tinta-3")}>{formatarNumero(orgao.links_em_observacao)}</td>
                      <td className={cn("numeros px-5 py-3.5 text-right font-mono", orgao.links_quebrados ? "font-semibold text-queb-texto" : "text-tinta-3")}>{formatarNumero(orgao.links_quebrados)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Celular: cartões */}
            <ul className="mt-4 grid gap-3 md:hidden">
              {visiveis.map((orgao) => (
                <li key={orgao.slug} className="relative rounded-2xl border border-linha bg-superficie p-4">
                  <Link href={linkDoOrgao(orgao.slug)} className="font-medium text-tinta after:absolute after:inset-0">{orgao.nome}</Link>
                  <div className="mt-0.5 text-xs text-tinta-3">{t.esferas[orgao.esfera] ?? orgao.esfera} · {formatarNumero(orgao.qtd_bases)} {t.mapa.bases}</div>
                  <div className="mt-3"><Regua altura="h-2" rotulo={orgao.nome} partes={partesDaRegua({ total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados })} /></div>
                  <dl className="numeros mt-3 grid grid-cols-3 gap-2 font-mono text-xs">
                    <div><dt className="text-tinta-3">{t.lista.colunas.respondendo}</dt><dd className="text-tinta">{formatarPercentual(orgao.percentual_ok)}</dd></div>
                    <div><dt className="text-tinta-3">{t.lista.colunas.observacao}</dt><dd className={orgao.links_em_observacao ? "text-obs-texto" : "text-tinta"}>{formatarNumero(orgao.links_em_observacao)}</dd></div>
                    <div><dt className="text-tinta-3">{t.lista.colunas.quebrados}</dt><dd className={orgao.links_quebrados ? "text-queb-texto" : "text-tinta"}>{formatarNumero(orgao.links_quebrados)}</dd></div>
                  </dl>
                </li>
              ))}
            </ul>

            {visiveis.length < resultado.length && (
              <div className="mt-6 text-center">
                <button type="button" onClick={() => setPaginas((p) => p + 1)}
                  className="h-11 rounded-full border border-linha-2 bg-superficie px-6 text-sm font-medium text-tinta transition hover:border-tinta-3">
                  {t.lista.mais}
                </button>
              </div>
            )}
          </>
        )}
      </Miolo>
    </section>
  );
}
