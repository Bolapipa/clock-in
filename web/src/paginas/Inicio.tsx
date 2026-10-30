// Página inicial: a resposta do dia, a régua do Brasil, onde olhar primeiro e a lista de órgãos
import { useCallback, useMemo, useState } from "react";

import { ListaDeOrgaos } from "../components/Listas";
import { Carregando, ErroDeCarga, Miolo } from "../components/Moldura";
import { Regua } from "../components/Regua";
import { CampoDeSinais } from "../components/CampoDeSinais";
import { useListaDeOrgaos, useResumo } from "../lib/api";
import {
  ROTULOS_ESFERA, formatarData, formatarNumero, formatarPercentual, fraseDaResposta, linkDoOrgao, partesDaRegua, rotulo,
  type ChaveDaParte, type OrgaoResumo,
} from "../lib/dados";
import { useTituloDaPagina } from "../lib/useRota";

// Classes explícitas para o Tailwind manter as cores dos quatro estados no build.
const CLASSE_DO_ESTADO = {
  ok: "status-ok",
  observacao: "status-observacao",
  quebrados: "status-quebrados",
  nao_testados: "status-nao_testados",
} as const;

// Órgãos com mais links em observação ou quebrados: por onde começar a olhar
function OndeOlharPrimeiro({ orgaos }: { orgaos: OrgaoResumo[] }) {
  const destaques = useMemo(() => orgaos
    .map((orgao) => ({ orgao, problemas: orgao.links_em_observacao + orgao.links_quebrados }))
    .filter(({ problemas }) => problemas > 0)
    .sort((a, b) => b.problemas - a.problemas || a.orgao.nome.localeCompare(b.orgao.nome, "pt-BR"))
    .slice(0, 6), [orgaos]);

  if (destaques.length === 0) return null;
  return (
    <section aria-labelledby="titulo-destaques" className="mt-14">
      <h2 id="titulo-destaques" className="titulo-medio m-0 text-[1.75rem] leading-tight">Onde olhar primeiro</h2>
      <p className="mb-5 mt-1 max-w-[60ch] text-tinta-suave">Os órgãos com mais links em observação ou quebrados hoje.</p>
      <ul className="lista-destaques m-0 list-none p-0">
        {destaques.map(({ orgao, problemas }, indice) => (
          <li key={orgao.slug} className="destaque-orgao">
            <span className="destaque-ordem" aria-hidden="true">{String(indice + 1).padStart(2, "0")}</span>
            <div className="destaque-identidade">
              <a href={linkDoOrgao(orgao.slug)} className="destaque-link">{orgao.nome}</a>
              <span className="destaque-contexto">{rotulo(ROTULOS_ESFERA, orgao.esfera)} · {formatarNumero(orgao.qtd_bases)} bases</span>
            </div>
            <div className="destaque-diagnostico">
              <strong>{formatarNumero(problemas)}</strong>
              <span>links com falha recente</span>
              <small>{formatarPercentual(orgao.percentual_ok)} respondendo bem{orgao.links_quebrados > 0 && ` · ${formatarNumero(orgao.links_quebrados)} quebrados`}</small>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Inicio() {
  useTituloDaPagina();
  const resumo = useResumo();
  const lista = useListaDeOrgaos();
  const [statusFiltro, setStatusFiltro] = useState<ChaveDaParte | null>(null);
  const linksAtuais = resumo.estado === "pronto" ? resumo.dados.links : null;
  const partesAtuais = useMemo(() => linksAtuais ? partesDaRegua({
    total: linksAtuais.total, ok: linksAtuais.ok, emObservacao: linksAtuais.em_observacao, quebrados: linksAtuais.quebrados,
  }) : [], [linksAtuais?.total, linksAtuais?.ok, linksAtuais?.em_observacao, linksAtuais?.quebrados]);

  const selecionarStatus = useCallback((status: ChaveDaParte) => {
    setStatusFiltro((atual) => atual === status ? null : status);
    document.getElementById("explorar")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  }, []);

  if (resumo.estado === "carregando") return <Miolo><Carregando /></Miolo>;
  if (resumo.estado === "erro") return <Miolo><ErroDeCarga texto="Não foi possível carregar os dados do dia. Confira a conexão e recarregue a página." /></Miolo>;

  const { dados } = resumo;
  const links = dados.links;
  const partes = partesAtuais;

  return (
    <>
      <section aria-labelledby="titulo-resumo" className="hero-clock relative overflow-hidden text-white">
        <Miolo className="hero-conteudo relative z-10 grid min-h-[620px] items-center gap-12 py-16 sm:py-20 lg:grid-cols-[0.95fr_1.05fr] lg:gap-16 lg:py-24">
          <div>
            <h1 id="titulo-resumo" className="hero-titulo m-0 max-w-[12ch] text-[clamp(3.5rem,7.2vw,6rem)] font-semibold leading-[0.93] tracking-[-0.04em]">
              O dado ainda <span className="hero-destaque">bate o ponto?</span>
            </h1>
            <p className="mt-8 max-w-[47ch] text-[clamp(1.05rem,1.6vw,1.25rem)] leading-relaxed text-[#bdc8dc]">
              Monitoramos as bases do <a href="https://dados.gov.br" className="font-semibold text-white decoration-[#86a9ff]" rel="noopener">dados.gov.br</a> para mostrar quais links respondem e quais precisam de atenção.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-4">
              <a href="#explorar" className="inline-flex min-h-12 items-center gap-3 rounded-sm bg-[#f2b650] px-6 font-bold text-[#101b37] no-underline transition hover:bg-white">Explorar os dados <svg aria-hidden="true" viewBox="0 0 16 16" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 12 12 4M5 4h7v7" /></svg></a>
              <a href="#metodologia" className="font-medium text-white decoration-[#86a9ff]">Como medimos</a>
            </div>
          </div>
          <div className="comprovante" aria-label={`Leitura do dia: ${fraseDaResposta(links)}`}>
            <div className="comprovante-cabecalho">
              <span>Registro da coleta</span><time dateTime={dados.data_coleta}>{formatarData(dados.data_coleta)}</time>
            </div>
            <div className="comprovante-destaque">
              <p>Links que respondem bem</p>
              <strong>{formatarPercentual(links.percentual_ok)}</strong>
              <span aria-live="polite">{fraseDaResposta(links)}</span>
            </div>
            <div className="comprovante-estados" role="group" aria-label="Distribuição dos links monitorados">
              {partes.map((parte) => (
                <button key={parte.chave} type="button" className={`comprovante-linha ${CLASSE_DO_ESTADO[parte.chave]}`} aria-pressed={statusFiltro === parte.chave}
                  onClick={() => selecionarStatus(parte.chave)}
                  aria-label={`${formatarNumero(parte.quantidade)} ${parte.rotulo}; ${formatarPercentual(parte.percentual)} dos links. ${parte.descricao}`}
                  title={`${formatarNumero(parte.quantidade)} ${parte.rotulo} · ${formatarPercentual(parte.percentual)}. ${parte.descricao}`}>
                  <span className="comprovante-marca" aria-hidden="true" />
                  <span className="comprovante-rotulo">{parte.rotulo}</span>
                  <span className="comprovante-quantidade">{formatarNumero(parte.quantidade)}</span>
                  <span className="comprovante-percentual">{formatarPercentual(parte.percentual)}</span>
                  <span className="comprovante-trilho" aria-hidden="true"><i style={{ width: `${parte.percentual}%` }} /></span>
                </button>
              ))}
            </div>
            <div className="comprovante-rodape">
              <span><b>{formatarNumero(links.testados)}</b> links testados</span>
              <span><b>{formatarPercentual(links.cobertura)}</b> cobertura</span>
            </div>
            <p className="comprovante-dica">Selecione um estado para encontrar os órgãos relacionados.</p>
          </div>
        </Miolo>
      </section>

      <div className="corpo-inicio">
      <Miolo>
        <section aria-label="Resumo da coleta" className="grid border-y border-linha bg-superficie sm:grid-cols-2 lg:grid-cols-4 -mt-7 relative z-10">
          {[
            ["Bases monitoradas", formatarNumero(dados.bases), `${formatarNumero(dados.recursos)} recursos`],
            ["Órgãos publicadores", formatarNumero(dados.orgaos), "em todas as esferas"],
            ["Links em observação", formatarNumero(links.em_observacao), "falhas recentes"],
            ["Bases fora do ar", formatarNumero(dados.bases_fora_do_ar), "todos os links quebrados"],
          ].map(([rotulo, valor, detalhe]) => <div key={rotulo} className="indicador-resumo"><p className="eyebrow-escura m-0">{rotulo}</p><strong className="mt-3 block text-[clamp(2rem,3.5vw,2.65rem)] font-semibold tracking-[-0.03em] tabular-nums">{valor}</strong><span className="text-sm text-tinta-suave">{detalhe}</span></div>)}
        </section>
        <section aria-label="Saúde dos links" className="py-20">
          <h2 className="mb-3 mt-0 text-[clamp(2.2rem,4vw,3.8rem)] font-semibold leading-tight tracking-[-0.04em]">A saúde dos links, em detalhe.</h2>
          <p className="mb-9 max-w-[62ch] text-tinta-suave">Cada faixa mostra uma condição diferente. A cobertura indica quanto conseguimos verificar de forma conclusiva.</p>
          <div className="border-y border-linha py-6 sm:py-8"><Regua partes={partes} rotulo="Links do Brasil" /></div>
          <p className="mt-5 max-w-[80ch] text-sm text-tinta-suave"><strong className="text-tinta">Leitura inicial.</strong> O status pelo conteúdo aparece conforme o histórico de arquivos cresce. Órgãos com menos de 30 links testados ficam sem porcentagem. <a href="#metodologia">Entenda a metodologia</a>.</p>
          <CampoDeSinais partes={partes} aoSelecionar={selecionarStatus} />
        </section>
        <div id="explorar" className="scroll-mt-24 border-t border-linha pt-14">
          <h2 className="mt-0 text-[clamp(2.2rem,4vw,3.8rem)] font-semibold leading-tight tracking-[-0.04em]">Encontre quem publica.</h2>
          <p className="max-w-[60ch] text-tinta-suave">Busque um órgão, filtre por esfera e veja as bases que precisam de atenção.</p>
        </div>
        {lista.estado === "carregando" && <Carregando texto="Carregando a lista de órgãos" />}
        {lista.estado === "erro" && <ErroDeCarga texto="Não foi possível carregar a lista de órgãos. Confira a conexão e recarregue a página." />}
        {lista.estado === "pronto" && <><OndeOlharPrimeiro orgaos={lista.dados.orgaos} /><ListaDeOrgaos orgaos={lista.dados.orgaos} statusSelecionado={statusFiltro} aoMudarStatus={setStatusFiltro} /></>}
      </Miolo>
      </div>
    </>
  );
}
