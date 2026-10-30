// Páginas de texto: metodologia ("Como medimos") e API
import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { Miolo } from "../components/Moldura";
import { Selo } from "../components/Pecas";
import { useListaDeOrgaos, useResumo } from "../lib/api";
import { EXPLICACOES_STATUS, formatarData } from "../lib/dados";
import { useTituloDaPagina } from "../lib/useRota";

function Titulo2({ children, id }: { children: ReactNode; id?: string }) {
  return <h2 id={id} className="titulo-medio mb-3 mt-12 scroll-mt-28 text-[1.5rem] leading-tight">{children}</h2>;
}

function Cabeca({ titulo, lide }: { titulo: string; lide: ReactNode }) {
  return (
    <>
      <h1 className="titulo-condensado m-0 mb-3 pt-10 text-[clamp(2.1rem,5vw,3.6rem)] leading-none">{titulo}</h1>
      <p className="m-0 max-w-[60ch] text-[1.1rem] text-tinta-suave">{lide}</p>
    </>
  );
}

// Tabela simples de duas colunas (texto alinhado à esquerda)
function TabelaSimples({ titulos, linhas }: { titulos: [string, string]; linhas: [ReactNode, ReactNode][] }) {
  return (
    <div className="overflow-x-auto rounded-lg bg-superficie">
      <table className="w-full border-collapse text-left text-[0.95rem]">
        <thead>
          <tr className="bg-faixa text-[0.85rem] text-faixa-texto">
            {titulos.map((titulo) => <th key={titulo} scope="col" className="px-4 py-3 font-semibold">{titulo}</th>)}
          </tr>
        </thead>
        <tbody>
          {linhas.map(([a, b], indice) => (
            <tr key={indice} className="border-b border-linha last:border-0">
              <td className="whitespace-nowrap px-4 py-3 align-top">{a}</td>
              <td className="px-4 py-3">{b}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const PRAZOS: [string, string][] = [
  ["Diária", "3 dias"], ["Semanal", "10 dias"], ["Quinzenal", "20 dias"], ["Mensal", "40 dias"],
  ["Trimestral", "100 dias"], ["Quadrimestral", "135 dias"], ["Semestral", "200 dias"], ["Anual", "400 dias"],
];

export function Metodologia() {
  useTituloDaPagina("Como medimos");
  return (
    <Miolo>
      <article className="prosa max-w-[72ch]">
        <Cabeca titulo="Como medimos" lide="O Clock-in só afirma o que consegue provar. Esta página explica as regras, uma a uma." />

        <nav className="metodologia-navegacao" aria-label="Nesta página">
          <a href="#o-que-faz">A coleta</a><a href="#link-quebrado">Links quebrados</a><a href="#conta-falha">Tipos de falha</a>
          <a href="#cobertura">Cobertura</a><a href="#status-base">Status das bases</a><a href="#prazos">Prazos</a><a href="#limites">Limites</a>
        </nav>

        <Titulo2 id="o-que-faz">O que o Clock-in faz</Titulo2>
        <p>
          Todo dia o Clock-in lê o catálogo do dados.gov.br, testa os links dos arquivos de cada base e guarda o resultado.
          O teste é educado: uma requisição por vez em cada servidor, com pausa entre elas, e o robô se identifica.
        </p>

        <Titulo2 id="link-quebrado">Quando um link é considerado quebrado</Titulo2>
        <p>
          Um link só é <strong>quebrado</strong> depois de <strong>3 falhas em dias diferentes seguidos</strong>. Com 1 ou 2 falhas
          ele fica <strong>em observação</strong>, e um único sucesso zera a contagem. Erros como 502, 503 e 520 costumam ser
          temporários, e acusar um órgão por uma falha de um dia seria injusto.
        </p>

        <Titulo2 id="conta-falha">O que conta e o que não conta como falha</Titulo2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border-t-4 border-ruim bg-superficie p-5">
            <h3 className="m-0 mb-2 text-lg font-bold">Conta como falha</h3>
            <ul className="com-marcador m-0 space-y-1.5">
              <li>Resposta de erro do servidor, como <strong>404</strong> (não encontrado) e <strong>500</strong>.</li>
              <li>Erro de <strong>DNS</strong>: o endereço não existe mais.</li>
              <li>Erro de <strong>certificado</strong> de segurança.</li>
            </ul>
          </div>
          <div className="rounded-lg border-t-4 border-linha-forte bg-superficie p-5">
            <h3 className="m-0 mb-2 text-lg font-bold">Não conta como falha</h3>
            <ul className="com-marcador m-0 space-y-1.5">
              <li><strong>Timeout e falha de conexão:</strong> o servidor pode só não responder ao teste.</li>
              <li><strong>Erro 403</strong> (acesso negado): proteção contra robôs de vários sites do governo.</li>
              <li><strong>Erro 405</strong> (método não permitido): o arquivo abre no navegador, mas o servidor recusa o teste.</li>
            </ul>
          </div>
        </div>
        <p>Os links que não contam ficam de fora da conta e aparecem como "não deu para testar" na régua.</p>

        <Titulo2 id="cobertura">Cobertura e porcentagens</Titulo2>
        <p>
          A <strong>cobertura</strong> é a parte dos links que conseguimos testar de verdade. A porcentagem de links respondendo
          bem só aparece para órgãos com <strong>30 ou mais links testados</strong>: com poucos links, 1 ou 2 falhas distorcem o resultado.
        </p>

        <Titulo2 id="status-base">Status de cada base</Titulo2>
        <ul className="m-0 grid list-none gap-3 p-0">
          {(["EM_DIA", "ATRASADA", "PARADA", "FORA_DO_AR", "NAO_VERIFICAVEL"] as const).map((status) => (
            <li key={status} className="grid gap-2 rounded-lg bg-superficie p-4 sm:grid-cols-[150px_1fr] sm:items-start">
              <span><Selo status={status} /></span>
              <span>{EXPLICACOES_STATUS[status]}</span>
            </li>
          ))}
        </ul>
        <p>
          O status pelo conteúdo depende de arquivos lidos ao longo de semanas. Enquanto o histórico cresce, a maioria das bases
          aparece como não verificável.
        </p>

        <Titulo2 id="prazos">Prazo esperado por periodicidade</Titulo2>
        <p>
          O prazo é a periodicidade declarada pelo órgão com uma folga. Quase 7 em cada 10 bases não declaram periodicidade e,
          por enquanto, ficam sem prazo. Uma base passa a ser <strong>parada</strong> depois de 3 vezes o prazo sem mudança.
        </p>
        <TabelaSimples titulos={["Periodicidade", "Prazo"]} linhas={PRAZOS} />

        <Titulo2 id="limites">Limites</Titulo2>
        <p>
          Os números vêm de poucos dias de testes e podem mudar bastante nas próximas semanas. O código, as decisões e os
          motivos de cada regra estão abertos no <a href="https://github.com/Bolapipa/clock-in" rel="noopener">GitHub</a>.
        </p>
      </article>
    </Miolo>
  );
}

const EXEMPLO = `const resposta = await fetch("api/resumo.json");
const resumo = await resposta.json();
console.log(resumo.links.percentual_ok, "% dos links respondendo bem");`;

// Consulta os mesmos arquivos JSON da API e exibe uma prévia formatada.
function ExploradorApi() {
  const lista = useListaDeOrgaos();
  const [tipo, setTipo] = useState("resumo");
  const [slug, setSlug] = useState("");
  const [resultado, setResultado] = useState<unknown>(null);
  const [erro, setErro] = useState("");
  const [httpStatus, setHttpStatus] = useState<number | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    if (lista.estado === "pronto" && !slug) setSlug(lista.dados.orgaos[0]?.slug ?? "");
  }, [lista, slug]);

  const caminho = tipo === "resumo" ? "api/resumo.json"
    : tipo === "orgaos" ? "api/orgaos.json"
      : `api/orgaos/${encodeURIComponent(slug)}.json`;

  const consultar = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault();
    setCarregando(true);
    setErro("");
    setResultado(null);
    setHttpStatus(null);
    try {
      const resposta = await fetch(caminho);
      setHttpStatus(resposta.status);
      if (!resposta.ok) throw new Error(`A API respondeu com HTTP ${resposta.status}.`);
      setResultado(await resposta.json());
    } catch (falha) {
      setErro(falha instanceof Error ? falha.message : "Não foi possível consultar este arquivo.");
    } finally {
      setCarregando(false);
    }
  };

  const json = resultado == null ? "" : JSON.stringify(resultado, null, 2);
  const copiarResultado = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 1800);
    } catch {
      setErro("O navegador não permitiu copiar. Selecione o texto da resposta para copiá-lo.");
    }
  };

  return (
    <section className="api-explorador" aria-labelledby="titulo-explorador-api">
      <div className="api-explorador-cabecalho">
        <div><p className="api-explorador-etiqueta">CONSULTA LOCAL</p><h3 id="titulo-explorador-api">Experimente a API</h3></div>
        {httpStatus != null && <span className={`api-http-status ${httpStatus < 400 ? "api-http-ok" : "api-http-erro"}`}>HTTP {httpStatus}</span>}
      </div>
      <form className="api-explorador-form" onSubmit={consultar}>
        <label>Arquivo
          <select value={tipo} onChange={(evento) => setTipo(evento.target.value)}>
            <option value="resumo">Resumo nacional</option>
            <option value="orgaos">Lista de órgãos</option>
            <option value="orgao">Detalhe de um órgão</option>
          </select>
        </label>
        {tipo === "orgao" && (
          <label>Órgão
            <select value={slug} onChange={(evento) => setSlug(evento.target.value)} disabled={lista.estado !== "pronto"}>
              {lista.estado === "pronto" && lista.dados.orgaos.map((orgao) => <option key={orgao.slug} value={orgao.slug}>{orgao.nome}</option>)}
            </select>
          </label>
        )}
        <button type="submit" disabled={carregando || (tipo === "orgao" && !slug)}>{carregando ? "Consultando…" : "Enviar GET"}<span aria-hidden="true"> ↗</span></button>
      </form>
      <div className="api-endpoint"><span aria-hidden="true">GET</span><code>/{caminho}</code></div>
      {carregando && <p role="status" className="api-mensagem">Buscando a resposta…</p>}
      {erro && <p role="alert" className="api-mensagem api-mensagem-erro">{erro}</p>}
      {json && (
        <div className="api-resposta">
          <div className="api-resposta-cabecalho"><span>Resposta JSON</span><button type="button" onClick={copiarResultado}>{copiado ? "Copiado" : "Copiar JSON"}</button></div>
          <pre><code>{json.length > 16000 ? `${json.slice(0, 16000)}\n… Prévia limitada. Abra o arquivo para ver a resposta completa.` : json}</code></pre>
          <a href={caminho} target="_blank" rel="noopener noreferrer">Abrir resposta completa em outra aba</a>
        </div>
      )}
    </section>
  );
}

// Bloco de código com botão de copiar
function Codigo({ texto }: { texto: string }) {
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(texto);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setCopiado(false);
    }
  };
  return (
    <div className="relative">
      <pre className="m-0 overflow-x-auto rounded-lg border-l-4 border-carimbo bg-superficie p-5 pr-24 font-mono text-[0.88rem]"><code>{texto}</code></pre>
      <button type="button" onClick={copiar}
        className="absolute right-3 top-3 rounded-md border-[1.5px] border-linha-forte bg-papel px-3 py-1 text-[0.85rem] font-semibold transition-colors hover:border-carimbo">
        {copiado ? "Copiado" : "Copiar"}
      </button>
    </div>
  );
}

export function PaginaApi() {
  useTituloDaPagina("API");
  const resumo = useResumo();
  return (
    <Miolo>
      <article className="prosa max-w-[72ch]">
        <Cabeca titulo="API" lide={<>Todos os dados deste site estão em arquivos JSON abertos, sem chave e sem limite de uso. Basta um <code className="font-mono">GET</code> em cada arquivo.</>} />

        <Titulo2>Arquivos</Titulo2>
        <TabelaSimples titulos={["Arquivo", "O que traz"]} linhas={[
          [<a href="api/resumo.json" className="font-mono">api/resumo.json</a>, "Totais do Brasil"],
          [<a href="api/orgaos.json" className="font-mono">api/orgaos.json</a>, <>Um resumo por órgão publicador (o <code className="font-mono">slug</code> de cada órgão está aqui)</>],
          [<code className="font-mono">api/orgaos/{"{slug}"}.json</code>, "Um órgão e as bases dele, com as que têm problema primeiro"],
        ]} />

        <Titulo2>Exemplo</Titulo2>
        <Codigo texto={EXEMPLO} />

        <Titulo2>Teste agora</Titulo2>
        <p>Escolha um arquivo e faça uma consulta real aos dados publicados pelo Clock-in.</p>
        <ExploradorApi />

        <Titulo2>Versões</Titulo2>
        <p>
          Todo arquivo traz <code className="font-mono">versao</code>, <code className="font-mono">data_coleta</code> e{" "}
          <code className="font-mono">gerado_em</code>. A versão só sobe quando uma chave é removida, renomeada ou muda de significado;
          chaves novas podem aparecer sem aviso, então ignore as que você não conhece. A descrição de cada campo está em{" "}
          <a href="https://github.com/Bolapipa/clock-in/blob/main/docs/API.md" rel="noopener">docs/API.md</a>.
        </p>
        {resumo.estado === "pronto" && (
          <p className="text-tinta-suave">
            Versão atual do contrato: {resumo.dados.versao}. Dados de {formatarData(resumo.dados.data_coleta)}, gerados em {resumo.dados.gerado_em}.
          </p>
        )}
      </article>
    </Miolo>
  );
}
