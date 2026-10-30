// Listas de órgãos e de bases: busca, filtro, ordem e "mostrar mais".
// No computador cada lista é uma tabela; no celular cada linha vira uma ficha aberta, sem esconder as colunas.
import { useMemo, useState, type ReactNode } from "react";

import {
  ORDENS_BASES, ORDENS_ORGAOS, ROTULOS_ESFERA, ROTULOS_PERIODICIDADE, ROTULOS_STATUS, filtrarBases, filtrarOrgaos, formatarNumero,
  formatarPercentual, lerOrdem, linkDaBase, linkDoOrgao, ordenar, partesDaRegua, rotulo,
  type Base, type ChaveDaParte, type OrgaoResumo,
} from "../lib/dados";
import { BotaoMais, CampoBusca, CampoEscolha, Marcar, Selo, Vazio, type Tom } from "./Pecas";
import { ReguaMini } from "./Regua";

const ORGAOS_POR_PAGINA = 25;
const BASES_POR_PAGINA = 50;

const COR_DO_NUMERO: Record<Tom, string> = { bom: "text-bom-texto", atencao: "text-atencao-texto font-bold", ruim: "text-ruim-texto font-bold", "": "" };

// Destaca o número só quando ele indica problema
const tomDe = (quantidade: number, tom: Tom): Tom => (quantidade > 0 ? tom : "");

interface Coluna {
  titulo: string;
  valor: ReactNode;
  tom?: Tom;
}

interface Linha {
  chave: string;
  nome: string;
  endereco: string;
  apoio: string;
  colunas: Coluna[];
}

// Uma lista que é tabela no computador e cartões no celular, com os mesmos dados
function TabelaResponsiva({ legenda, titulos, linhas }: { legenda: string; titulos: string[]; linhas: Linha[] }) {
  return (
    <>
      {/* Computador e tablet: tabela; a linha toda é clicável porque o link do nome cobre a primeira célula */}
      <div className="hidden overflow-x-auto border-y border-linha md:block" role="region" aria-label={legenda} tabIndex={0}>
        <table className="w-full border-collapse text-[0.95rem]">
          <caption className="sr-only">{legenda}</caption>
          <thead>
            <tr className="bg-faixa text-[0.85rem] text-faixa-texto">
              {titulos.map((titulo, indice) => (
                <th key={titulo} scope="col" className={`whitespace-nowrap px-3 py-3 font-semibold ${indice === 0 ? "pl-4 text-left" : "text-right last:pr-4"}`}>
                  {titulo}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {linhas.map((linha) => (
              <tr key={linha.chave} className="border-b border-linha transition-colors last:border-0 hover:bg-carimbo-fundo">
                <td className="relative min-w-[240px] py-3 pl-4 pr-3 text-left">
                  <a href={linha.endereco} className="font-semibold text-tinta decoration-carimbo decoration-2 after:absolute after:inset-0">
                    {linha.nome}
                  </a>
                  <span className="mt-0.5 block text-[0.82rem] text-tinta-suave">{linha.apoio}</span>
                </td>
                {linha.colunas.map((coluna) => (
                  <td key={coluna.titulo} className={`whitespace-nowrap px-3 py-3 text-right tabular-nums last:pr-4 ${COR_DO_NUMERO[coluna.tom ?? ""]}`}>
                    {coluna.valor}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Celular: os mesmos dados em linhas abertas, com rótulos para cada número. */}
      <ul className="lista-tabela-mobile m-0 list-none p-0 md:hidden" aria-label={legenda}>
        {linhas.map((linha) => (
          <li key={linha.chave} className="item-tabela-mobile">
            <a href={linha.endereco} className="item-tabela-link text-[1.05rem] font-semibold text-tinta decoration-carimbo decoration-2">
              {linha.nome}
            </a>
            <span className="mt-0.5 block text-[0.82rem] text-tinta-suave">{linha.apoio}</span>
            <dl className="m-0 mt-3 grid grid-cols-2 gap-x-4 gap-y-2.5">
              {linha.colunas.map((coluna) => (
                <div key={coluna.titulo}>
                  <dt className="text-[0.78rem] font-semibold text-tinta-suave">{coluna.titulo}</dt>
                  <dd className={`m-0 tabular-nums ${COR_DO_NUMERO[coluna.tom ?? ""]}`}>{coluna.valor}</dd>
                </div>
              ))}
            </dl>
          </li>
        ))}
      </ul>
    </>
  );
}

function Contagem({ achados, total, nome }: { achados: number; total: number; nome: string }) {
  return (
    <p aria-live="polite" className="my-3 text-[0.9rem] text-tinta-suave">
      {formatarNumero(achados)} de {formatarNumero(total)} {nome}
    </p>
  );
}

export function ListaDeOrgaos({ orgaos, statusSelecionado, aoMudarStatus }: {
  orgaos: OrgaoResumo[];
  statusSelecionado: ChaveDaParte | null;
  aoMudarStatus: (status: ChaveDaParte | null) => void;
}) {
  const [texto, setTexto] = useState("");
  const [esfera, setEsfera] = useState("");
  const [ordem, setOrdem] = useState(ORDENS_ORGAOS[0].valor);
  const [paginas, setPaginas] = useState(1);

  // Esferas que existem nos dados, para o filtro
  const esferas = useMemo(() => [...new Set(orgaos.map((orgao) => orgao.esfera))].sort(), [orgaos]);

  const filtrados = useMemo(() => filtrarOrgaos(orgaos, { texto, esfera }).filter((orgao) => {
    if (!statusSelecionado) return true;
    if (statusSelecionado === "ok") return orgao.links_ok > 0;
    if (statusSelecionado === "observacao") return orgao.links_em_observacao > 0;
    if (statusSelecionado === "quebrados") return orgao.links_quebrados > 0;
    return orgao.links_total - orgao.links_ok - orgao.links_em_observacao - orgao.links_quebrados > 0;
  }), [orgaos, texto, esfera, statusSelecionado]);
  const ordenados = useMemo(() => {
    const { coluna, direcao } = lerOrdem(ordem);
    return ordenar(filtrados, coluna, direcao);
  }, [filtrados, ordem]);
  const visiveis = ordenados.slice(0, paginas * ORGAOS_POR_PAGINA);

  // Qualquer mudança de busca, filtro ou ordem volta para a primeira página
  const mudar = <T,>(setar: (valor: T) => void) => (valor: T) => { setar(valor); setPaginas(1); };

  const linhas: Linha[] = visiveis.map((orgao) => {
    const partes = partesDaRegua({
      total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados,
    });
    return {
      chave: orgao.slug,
      nome: orgao.nome,
      endereco: linkDoOrgao(orgao.slug),
      apoio: rotulo(ROTULOS_ESFERA, orgao.esfera),
      colunas: [
        { titulo: "Bases", valor: formatarNumero(orgao.qtd_bases) },
        {
          titulo: "Respondendo bem",
          valor: (
            <span className="inline-flex items-center gap-2" title={orgao.percentual_ok == null ? "Poucos links testados para calcular a porcentagem" : undefined}>
              {formatarPercentual(orgao.percentual_ok)}
              <ReguaMini partes={partes} semPercentual={orgao.percentual_ok == null} />
            </span>
          ),
        },
        { titulo: "Em observação", valor: formatarNumero(orgao.links_em_observacao), tom: tomDe(orgao.links_em_observacao, "atencao") },
        { titulo: "Quebrados", valor: formatarNumero(orgao.links_quebrados), tom: tomDe(orgao.links_quebrados, "ruim") },
      ],
    };
  });

  return (
    <section aria-labelledby="titulo-orgaos" className="mt-14">
      <h2 id="titulo-orgaos" className="titulo-medio m-0 mb-4 text-[1.75rem] leading-tight">Procure um órgão</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <CampoBusca rotulo="Buscar órgão" valor={texto} aoMudar={mudar(setTexto)} exemplo="Ex.: IBGE, Fortaleza, Saúde" />
        <CampoEscolha rotulo="Esfera" valor={esfera} aoMudar={mudar(setEsfera)}
          opcoes={[{ valor: "", texto: "Todas" }, ...esferas.map((chave) => ({ valor: chave, texto: rotulo(ROTULOS_ESFERA, chave) }))]} />
        <CampoEscolha rotulo="Estado dos links" valor={statusSelecionado ?? ""}
          aoMudar={(valor) => { aoMudarStatus(valor ? valor as ChaveDaParte : null); setPaginas(1); }}
          opcoes={[{ valor: "", texto: "Todos os estados" }, { valor: "ok", texto: "Respondendo bem" }, { valor: "observacao", texto: "Em observação" }, { valor: "quebrados", texto: "Quebrados" }, { valor: "nao_testados", texto: "Não testados" }]} />
        <CampoEscolha rotulo="Ordenar por" valor={ordem} aoMudar={mudar(setOrdem)} opcoes={ORDENS_ORGAOS} />
      </div>
      <Contagem achados={filtrados.length} total={orgaos.length} nome="órgãos" />
      {filtrados.length === 0
        ? <Vazio>Nenhum órgão encontrado. Tente outro termo ou limpe os filtros de esfera e estado dos links.</Vazio>
        : <TabelaResponsiva legenda="Órgãos publicadores e o resultado dos testes de links"
            titulos={["Órgão", "Bases", "Respondendo bem", "Em observação", "Quebrados"]} linhas={linhas} />}
      {visiveis.length < ordenados.length && <BotaoMais texto="Mostrar mais órgãos" aoClicar={() => setPaginas((p) => p + 1)} />}
    </section>
  );
}

export function ListaDeBases({ slugDoOrgao, bases }: { slugDoOrgao: string; bases: Base[] }) {
  const [texto, setTexto] = useState("");
  const [ordem, setOrdem] = useState(ORDENS_BASES[0].valor);
  const [soProblemas, setSoProblemas] = useState(false);
  const [status, setStatus] = useState("");
  const [paginas, setPaginas] = useState(1);

  const filtradas = useMemo(() => filtrarBases(bases, { texto, apenasProblemas: soProblemas })
    .filter((base) => !status || base.status === status), [bases, texto, soProblemas, status]);
  const ordenadas = useMemo(() => {
    const { coluna, direcao } = lerOrdem(ordem, ORDENS_BASES[0].valor);
    return ordenar(filtradas, coluna, direcao);
  }, [filtradas, ordem]);
  const visiveis = ordenadas.slice(0, paginas * BASES_POR_PAGINA);
  const mudar = <T,>(setar: (valor: T) => void) => (valor: T) => { setar(valor); setPaginas(1); };

  const linhas: Linha[] = visiveis.map((base) => ({
    chave: base.slug,
    nome: base.titulo || base.slug,
    endereco: linkDaBase(slugDoOrgao, base.slug),
    apoio: `Periodicidade ${rotulo(ROTULOS_PERIODICIDADE, base.periodicidade).toLowerCase()}`,
    colunas: [
      { titulo: "Links", valor: formatarNumero(base.links_total) },
      { titulo: "Respondendo bem", valor: formatarNumero(base.links_ok) },
      { titulo: "Em observação", valor: formatarNumero(base.links_em_observacao), tom: tomDe(base.links_em_observacao, "atencao") },
      { titulo: "Quebrados", valor: formatarNumero(base.links_quebrados), tom: tomDe(base.links_quebrados, "ruim") },
      { titulo: "Status", valor: <Selo status={base.status} dica={base.motivo ?? undefined} /> },
    ],
  }));

  return (
    <section aria-labelledby="titulo-bases" className="mt-14">
      <h2 id="titulo-bases" className="titulo-medio m-0 mb-4 text-[1.75rem] leading-tight">Bases deste órgão</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <CampoBusca rotulo="Buscar base" valor={texto} aoMudar={mudar(setTexto)} exemplo="Parte do título da base" />
        <CampoEscolha rotulo="Status da base" valor={status} aoMudar={mudar(setStatus)}
          opcoes={[{ valor: "", texto: "Todos os status" }, ...Object.entries(ROTULOS_STATUS).map(([valor, texto]) => ({ valor, texto }))]} />
        <CampoEscolha rotulo="Ordenar por" valor={ordem} aoMudar={mudar(setOrdem)} opcoes={ORDENS_BASES} />
        <Marcar rotulo="Só bases com problema" marcado={soProblemas} aoMudar={mudar(setSoProblemas)} />
      </div>
      <Contagem achados={filtradas.length} total={bases.length} nome="bases" />
      {filtradas.length === 0
        ? <Vazio>Nenhuma base encontrada. Tente outro título ou limpe o status e o filtro de problemas.</Vazio>
        : <TabelaResponsiva legenda="Bases do órgão e o resultado dos testes de links"
            titulos={["Base", "Links", "Respondendo bem", "Em observação", "Quebrados", "Status"]} linhas={linhas} />}
      {visiveis.length < ordenadas.length && <BotaoMais texto="Mostrar mais bases" aoClicar={() => setPaginas((p) => p + 1)} />}
    </section>
  );
}
