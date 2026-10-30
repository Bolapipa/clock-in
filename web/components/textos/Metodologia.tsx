"use client";

// Metodologia ("Como medimos"): as regras, uma a uma, com índice fixo ao lado e o simulador embutido
import type { ReactNode } from "react";

import { Simulador } from "@/components/inicio/Simulador";
import { useLingua } from "@/components/Provedores";
import { Kicker, Miolo, Status } from "@/components/ui";

const URL_DECISOES = "https://github.com/Bolapipa/clock-in/blob/main/docs/DECISOES.md";
const PRAZOS: [string, number][] = [
  ["DIARIA", 3], ["SEMANAL", 10], ["QUINZENAL", 20], ["MENSAL", 40], ["TRIMESTRAL", 100], ["QUADRIMESTRAL", 135], ["SEMESTRAL", 200], ["ANUAL", 400],
];
const STATUS = ["EM_DIA", "ATRASADA", "PARADA", "FORA_DO_AR", "NAO_VERIFICAVEL"];

function Secao({ id, titulo, children }: { id: string; titulo: string; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-titulo`} className="scroll-mt-24 border-t border-linha py-12 first:border-0 first:pt-0">
      <h2 id={`${id}-titulo`} className="text-2xl font-semibold tracking-[-0.03em] text-tinta">{titulo}</h2>
      <div className="mt-5 space-y-4 text-[1.0625rem] leading-relaxed text-tinta-2 [&_strong]:font-semibold [&_strong]:text-tinta">{children}</div>
    </section>
  );
}

const CONTEUDO = {
  pt: {
    kicker: "Metodologia",
    titulo: "Como medimos",
    lide: "O Clock-in só afirma o que consegue provar. Esta página explica as regras, uma a uma, e cada regra tem uma decisão registrada no repositório.",
    indice: "Nesta página",
    secoes: {
      faz: "O que o Clock-in faz",
      quebrado: "Quando um link é quebrado",
      conta: "O que conta e o que não conta como falha",
      cobertura: "Cobertura e porcentagens",
      status: "Status de cada base",
      prazos: "Prazo esperado por periodicidade",
      limites: "Limites",
    },
    faz: (
      <>
        <p>Todo dia, um pipeline no GitHub Actions lê o catálogo do <strong>dados.gov.br</strong>, testa os links dos arquivos de cada base e guarda tudo em camadas (Bronze, Silver e Gold) em arquivos Parquet, processados com DuckDB.</p>
        <p>O teste é <strong>educado</strong>: um pedido por vez em cada servidor, com pausa entre eles, e o robô se identifica. Cada servidor ocupa no máximo 90 minutos por dia; o que não coube volta primeiro no dia seguinte.</p>
      </>
    ),
    quebrado: (
      <p>Um link só é <strong>quebrado</strong> depois de <strong>3 falhas em testes seguidos</strong>. Com 1 ou 2 falhas ele fica <strong>em observação</strong>, e uma única resposta boa zera a contagem. Experimente abaixo:</p>
    ),
    contaTitulo: "Conta como falha",
    conta: ["Resposta de erro do servidor, como 404 (não encontrado), 410, 500 e 400.", "Erro de DNS: o endereço não existe mais.", "Erro de certificado de segurança."],
    naoContaTitulo: "Não conta como falha",
    naoConta: ["Timeout e falha de conexão: o servidor pode só não ter respondido ao teste.", "Erro 403: proteção contra robôs de vários sites do governo.", "Erro 405: o arquivo abre no navegador, mas o servidor recusa o método do teste."],
    contaRodape: "Os links que não contam ficam como estavam e aparecem como \"não deu para testar\".",
    cobertura: (
      <>
        <p>A <strong>cobertura</strong> é a parte dos links que conseguimos testar de forma conclusiva. A porcentagem de links respondendo bem só aparece para órgãos com <strong>30 ou mais links testados</strong>: com poucos links, uma ou duas falhas distorcem o resultado.</p>
      </>
    ),
    status: "O status pelo conteúdo depende de arquivos lidos ao longo de semanas (hash e estrutura). Enquanto o histórico cresce, a maioria das bases aparece como não verificável.",
    prazos: "O prazo é a periodicidade declarada pelo órgão, com folga. Uma base é parada depois de 3 vezes o prazo sem mudança. Quase 7 em cada 10 bases não declaram periodicidade; para elas, o ritmo será inferido pelo histórico.",
    periodicidade: "Periodicidade",
    prazo: "Prazo",
    dias: (n: number) => `${n} dias`,
    limites: (
      <>
        <p>Os números vêm de poucos dias de testes e podem mudar bastante nas próximas semanas. O teste roda a partir do GitHub, fora do Brasil, e alguns servidores tratam esse acesso de forma diferente.</p>
        <p>Cada regra desta página, com o motivo e as alternativas, está registrada em <a className="text-tinta underline decoration-ambar underline-offset-4" href={URL_DECISOES} target="_blank" rel="noopener">docs/DECISOES.md</a>.</p>
      </>
    ),
  },
  en: {
    kicker: "Methodology",
    titulo: "How we measure",
    lide: "Clock-in only states what it can prove. This page explains the rules one by one, and each rule has a decision recorded in the repository.",
    indice: "On this page",
    secoes: {
      faz: "What Clock-in does",
      quebrado: "When a link is broken",
      conta: "What counts as a failure",
      cobertura: "Coverage and percentages",
      status: "Dataset status",
      prazos: "Expected interval by frequency",
      limites: "Limitations",
    },
    faz: (
      <>
        <p>Every day, a GitHub Actions pipeline reads the <strong>dados.gov.br</strong> catalog, tests the file links of every dataset and stores everything in layers (Bronze, Silver and Gold) as Parquet files processed with DuckDB.</p>
        <p>The test is <strong>polite</strong>: one request at a time per server, with a pause between them, and the robot identifies itself. Each server takes at most 90 minutes a day; whatever did not fit goes first the next day.</p>
      </>
    ),
    quebrado: (
      <p>A link is only <strong>broken</strong> after <strong>3 failures in consecutive tests</strong>. With 1 or 2 failures it is <strong>under watch</strong>, and a single good response resets the count. Try it below:</p>
    ),
    contaTitulo: "Counts as a failure",
    conta: ["Server error responses such as 404 (not found), 410, 500 and 400.", "DNS error: the address no longer exists.", "Security certificate error."],
    naoContaTitulo: "Does not count",
    naoConta: ["Timeout and connection failure: the server may just not have answered the test.", "Error 403: anti-bot protection used by many government sites.", "Error 405: the file opens in a browser, but the server refuses the test method."],
    contaRodape: "Links that do not count stay as they were and appear as \"could not test\".",
    cobertura: (
      <p><strong>Coverage</strong> is the share of links we could test conclusively. The share of links responding is only shown for agencies with <strong>30 or more tested links</strong>: with few links, one or two failures distort the result.</p>
    ),
    status: "Content-based status depends on files read over weeks (hash and structure). While the history grows, most datasets appear as not verifiable.",
    prazos: "The interval is the frequency declared by the agency, with some slack. A dataset is stalled after 3 times the interval without changes. Almost 7 in 10 datasets declare no frequency; for them, the pace will be inferred from history.",
    periodicidade: "Frequency",
    prazo: "Interval",
    dias: (n: number) => `${n} days`,
    limites: (
      <>
        <p>The numbers come from a few days of tests and may change a lot in the coming weeks. The test runs from GitHub, outside Brazil, and some servers treat that access differently.</p>
        <p>Every rule on this page, with its reasons and alternatives, is recorded in <a className="text-tinta underline decoration-ambar underline-offset-4" href={URL_DECISOES} target="_blank" rel="noopener">docs/DECISOES.md</a>.</p>
      </>
    ),
  },
};

export function Metodologia() {
  const { t, lingua } = useLingua();
  const c = CONTEUDO[lingua];
  const indice = Object.entries(c.secoes) as [keyof typeof c.secoes, string][];

  return (
    <Miolo className="py-16">
      <header className="max-w-3xl">
        <Kicker>{c.kicker}</Kicker>
        <h1 className="mt-4 text-[clamp(2.4rem,5vw,4rem)] font-semibold leading-[1] tracking-[-0.045em] text-tinta">{c.titulo}</h1>
        <p className="mt-5 text-lg leading-relaxed text-tinta-2">{c.lide}</p>
      </header>

      <div className="mt-14 grid gap-12 lg:grid-cols-[13rem_1fr]">
        <nav aria-label={c.indice} className="hidden lg:block">
          <div className="sticky top-24">
            <p className="font-mono text-xs text-tinta-3">{c.indice}</p>
            <ol className="mt-3 space-y-1.5 border-l border-linha text-sm">
              {indice.map(([chave, titulo]) => (
                <li key={chave}><a href={`#${chave}`} className="-ml-px block border-l border-transparent py-0.5 pl-4 text-tinta-2 transition hover:border-ambar hover:text-tinta">{titulo}</a></li>
              ))}
            </ol>
          </div>
        </nav>

        <div className="min-w-0">
          <Secao id="faz" titulo={c.secoes.faz}>{c.faz}</Secao>
          <Secao id="quebrado" titulo={c.secoes.quebrado}>
            {c.quebrado}
            <div className="pt-4 text-base"><Simulador compacto /></div>
          </Secao>
          <Secao id="conta" titulo={c.secoes.conta}>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-2xl border border-queb/30 bg-queb/[0.06] p-5">
                <p className="font-semibold text-queb-texto">{c.contaTitulo}</p>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-base">{c.conta.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
              <div className="rounded-2xl border border-linha bg-superficie p-5">
                <p className="font-semibold text-tinta">{c.naoContaTitulo}</p>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-base">{c.naoConta.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            </div>
            <p>{c.contaRodape}</p>
          </Secao>
          <Secao id="cobertura" titulo={c.secoes.cobertura}>{c.cobertura}</Secao>
          <Secao id="status" titulo={c.secoes.status}>
            <ul className="grid gap-2">
              {STATUS.map((status) => (
                <li key={status} className="grid gap-3 rounded-2xl border border-linha bg-superficie p-4 sm:grid-cols-[10rem_1fr] sm:items-start">
                  <span><Status status={status} /></span>
                  <span className="text-base">{t.statusExplicacao[status]}</span>
                </li>
              ))}
            </ul>
            <p>{c.status}</p>
          </Secao>
          <Secao id="prazos" titulo={c.secoes.prazos}>
            <p>{c.prazos}</p>
            <div className="overflow-hidden rounded-2xl border border-linha bg-superficie">
              <table className="w-full text-left text-base">
                <thead className="border-b border-linha bg-superficie-2 text-xs text-tinta-2">
                  <tr><th scope="col" className="px-5 py-3 font-medium">{c.periodicidade}</th><th scope="col" className="px-5 py-3 text-right font-medium">{c.prazo}</th></tr>
                </thead>
                <tbody>
                  {PRAZOS.map(([chave, dias]) => (
                    <tr key={chave} className="border-b border-linha last:border-0">
                      <td className="px-5 py-3 text-tinta">{t.periodicidades[chave]}</td>
                      <td className="numeros px-5 py-3 text-right font-mono text-tinta-2">{c.dias(dias)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Secao>
          <Secao id="limites" titulo={c.secoes.limites}>{c.limites}</Secao>
        </div>
      </div>
    </Miolo>
  );
}
