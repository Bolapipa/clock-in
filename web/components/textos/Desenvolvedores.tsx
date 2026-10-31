"use client";

// Dados e API: os arquivos JSON, uma prévia ao vivo e exemplos de uso com botão de copiar
import { ArrowUpRight, Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import { useLingua } from "@/components/Provedores";
import { Kicker, Miolo } from "@/components/ui";
import { cn } from "@/lib/util";

const URL_CONTRATO = "https://github.com/Bolapipa/clock-in/blob/main/docs/API.md";

const EXEMPLOS = {
  JavaScript: `const resposta = await fetch("https://clock-in-monitor.vercel.app/api/resumo.json");
const resumo = await resposta.json();
console.log(resumo.links.percentual_ok, "% dos links respondendo bem");`,
  Python: `import httpx

resumo = httpx.get("https://clock-in-monitor.vercel.app/api/resumo.json").json()
print(resumo["links"]["percentual_ok"], "% dos links respondendo bem")`,
  curl: `curl -s https://clock-in-monitor.vercel.app/api/orgaos.json | jq '.orgaos[0]'`,
};
type Linguagem = keyof typeof EXEMPLOS;

const CONTEUDO = {
  pt: {
    kicker: "Dados e API",
    titulo: "Todos os dados, em JSON aberto",
    lide: "Tudo o que o site mostra está em arquivos JSON públicos, sem chave e sem limite de uso. Basta um GET em cada arquivo. Eles são gerados de novo todo dia, depois da coleta.",
    arquivos: "Arquivos",
    ao_vivo: "Resposta ao vivo",
    exemplos: "Exemplos",
    versoes: "Versões do contrato",
    versoesTexto: "Todo arquivo traz versao, data_coleta e gerado_em. A versão só sobe quando uma chave é removida, renomeada ou muda de significado; chaves novas podem aparecer sem aviso, então ignore as que você não conhece.",
    contrato: "Descrição de cada campo",
    endpoints: [
      { caminho: "/api/resumo.json", texto: "Totais do Brasil: bases, órgãos, links por estado e status." },
      { caminho: "/api/orgaos.json", texto: "Um resumo por órgão publicador, com o slug de cada um." },
      { caminho: "/api/orgaos/{slug}.json", texto: "Um órgão e todas as bases dele, com a saúde dos links e o status." },
    ],
  },
  en: {
    kicker: "Data & API",
    titulo: "All the data, as open JSON",
    lide: "Everything the site shows lives in public JSON files, with no key and no rate limit. Just GET each file. They are regenerated every day, after the collection.",
    arquivos: "Files",
    ao_vivo: "Live response",
    exemplos: "Examples",
    versoes: "Contract versions",
    versoesTexto: "Every file carries versao, data_coleta and gerado_em. The version only goes up when a key is removed, renamed or changes meaning; new keys may appear without notice, so ignore the ones you don't know.",
    contrato: "Description of every field",
    endpoints: [
      { caminho: "/api/resumo.json", texto: "Brazil-wide totals: datasets, agencies, links by state and status." },
      { caminho: "/api/orgaos.json", texto: "One summary per publishing agency, with each slug." },
      { caminho: "/api/orgaos/{slug}.json", texto: "One agency and all its datasets, with link health and status." },
    ],
  },
};

function BotaoCopiar({ texto }: { texto: string }) {
  const { t } = useLingua();
  const [copiado, setCopiado] = useState(false);
  return (
    <button type="button" aria-label={copiado ? t.comum.copiado : t.comum.copiar}
      onClick={async () => {
        try { await navigator.clipboard.writeText(texto); setCopiado(true); window.setTimeout(() => setCopiado(false), 1800); } catch { setCopiado(false); }
      }}
      className="inline-flex h-8 items-center gap-1.5 rounded-full border border-linha bg-superficie px-3 font-mono text-xs text-tinta-2 transition hover:text-tinta">
      {copiado ? <Check className="size-3.5 text-ok-texto" /> : <Copy className="size-3.5" />}{copiado ? t.comum.copiado : t.comum.copiar}
    </button>
  );
}

function Codigo({ texto, className }: { texto: string; className?: string }) {
  return (
    <pre className={cn("overflow-x-auto rounded-2xl border border-linha bg-superficie-2 p-5 font-mono text-[0.82rem] leading-relaxed text-tinta", className)}>
      <code>{texto}</code>
    </pre>
  );
}

export function Desenvolvedores() {
  const { t, lingua } = useLingua();
  const c = CONTEUDO[lingua];
  const [linguagem, setLinguagem] = useState<Linguagem>("JavaScript");
  const [aoVivo, setAoVivo] = useState<string | null>(null);

  // Prévia ao vivo: o resumo.json deste mesmo site
  useEffect(() => {
    fetch("/api/resumo.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((json) => setAoVivo(JSON.stringify(json, null, 2)))
      .catch(() => setAoVivo(null));
  }, []);

  return (
    <Miolo className="py-16">
      <header className="max-w-3xl">
        <Kicker>{c.kicker}</Kicker>
        <h1 className="mt-4 text-[clamp(2.4rem,5vw,4rem)] font-semibold leading-[1] tracking-[-0.045em] text-tinta">{c.titulo}</h1>
        <p className="mt-5 text-lg leading-relaxed text-tinta-2">{c.lide}</p>
      </header>

      <div className="mt-14 grid gap-10 lg:grid-cols-2">
        <div className="space-y-10">
          <section aria-labelledby="arquivos">
            <h2 id="arquivos" className="text-xl font-semibold tracking-[-0.02em] text-tinta">{c.arquivos}</h2>
            <ul className="mt-4 divide-y divide-linha overflow-hidden rounded-2xl border border-linha bg-superficie">
              {c.endpoints.map((endpoint) => (
                <li key={endpoint.caminho} className="flex items-start justify-between gap-4 p-5">
                  <div>
                    <code className="font-mono text-sm text-tinta">GET {endpoint.caminho}</code>
                    <p className="mt-1 text-sm text-tinta-2">{endpoint.texto}</p>
                  </div>
                  {!endpoint.caminho.includes("{") && (
                    <a href={endpoint.caminho} target="_blank" rel="noopener" className="inline-flex shrink-0 items-center gap-1 text-sm text-tinta-2 hover:text-tinta">
                      {t.comum.abrir}<ArrowUpRight className="size-3.5" />
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="exemplos">
            <h2 id="exemplos" className="text-xl font-semibold tracking-[-0.02em] text-tinta">{c.exemplos}</h2>
            <div className="mt-4 flex items-center justify-between gap-3">
              <div role="tablist" aria-label={c.exemplos} className="flex gap-1 rounded-full border border-linha bg-superficie p-1">
                {(Object.keys(EXEMPLOS) as Linguagem[]).map((nome) => (
                  <button key={nome} role="tab" type="button" aria-selected={linguagem === nome} onClick={() => setLinguagem(nome)}
                    className={cn("rounded-full px-3 py-1 font-mono text-xs transition", linguagem === nome ? "bg-tinta text-fundo" : "text-tinta-2 hover:text-tinta")}>
                    {nome}
                  </button>
                ))}
              </div>
              <BotaoCopiar texto={EXEMPLOS[linguagem]} />
            </div>
            <Codigo texto={EXEMPLOS[linguagem]} className="mt-3" />
          </section>

          <section aria-labelledby="versoes">
            <h2 id="versoes" className="text-xl font-semibold tracking-[-0.02em] text-tinta">{c.versoes}</h2>
            <p className="mt-3 leading-relaxed text-tinta-2">{c.versoesTexto}</p>
            <a href={URL_CONTRATO} target="_blank" rel="noopener" className="mt-3 inline-flex items-center gap-1 text-sm text-tinta underline decoration-ambar underline-offset-4">
              {c.contrato}: docs/API.md<ArrowUpRight className="size-3.5" />
            </a>
          </section>
        </div>

        <section aria-labelledby="ao-vivo" className="lg:sticky lg:top-24 lg:self-start">
          <div className="flex items-center justify-between">
            <h2 id="ao-vivo" className="flex items-center gap-2 text-xl font-semibold tracking-[-0.02em] text-tinta">
              <span aria-hidden="true" className="relative flex size-2.5">
                <span className="absolute inline-flex size-full animate-ping rounded-full bg-ok opacity-60 motion-reduce:hidden" />
                <span className="relative inline-flex size-2.5 rounded-full bg-ok" />
              </span>
              {c.ao_vivo}
            </h2>
            {aoVivo && <BotaoCopiar texto={aoVivo} />}
          </div>
          <p className="mt-1 font-mono text-xs text-tinta-3">GET /api/resumo.json</p>
          {aoVivo ? <Codigo texto={aoVivo} className="mt-3 max-h-[34rem]" /> : <div className="mt-3 h-80 animate-pulse rounded-2xl bg-superficie-2" />}
        </section>
      </div>
    </Miolo>
  );
}
