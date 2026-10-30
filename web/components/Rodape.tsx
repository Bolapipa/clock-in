"use client";

// Rodapé em colunas: projeto, dados, stack e autor
import Link from "next/link";

import { URL_GITHUB } from "@/components/Cabecalho";
import { Marca } from "@/components/Marca";
import { useLingua } from "@/components/Provedores";
import { dataNaLingua } from "@/lib/i18n";

function Coluna({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="mb-3 font-mono text-xs text-tinta-3">{titulo}</h2>
      <ul className="space-y-2 text-sm text-tinta-2">{children}</ul>
    </div>
  );
}

const estiloLink = "transition-colors hover:text-tinta";

export function Rodape({ dataColeta }: { dataColeta: string | null }) {
  const { t, lingua } = useLingua();
  return (
    <footer className="mt-24 border-t border-linha bg-superficie">
      <div className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_repeat(4,1fr)] lg:px-8">
        <div className="max-w-xs">
          <Marca />
          <p className="mt-4 text-sm leading-relaxed text-tinta-2">{t.rodape.descricao}</p>
          {dataColeta && <p className="mt-4 font-mono text-xs text-tinta-3">{t.rodape.atualizado(dataNaLingua(dataColeta, lingua))}</p>}
        </div>
        <Coluna titulo={t.rodape.projeto}>
          <li><a className={estiloLink} href={URL_GITHUB} target="_blank" rel="noopener">GitHub</a></li>
          <li><Link className={estiloLink} href="/metodologia/">{t.nav.metodologia}</Link></li>
          <li><Link className={estiloLink} href="/desenvolvedores/">{t.nav.desenvolvedores}</Link></li>
          <li>{t.rodape.licenca}</li>
        </Coluna>
        <Coluna titulo={t.rodape.dados}>
          <li><a className={estiloLink} href="https://dados.gov.br" target="_blank" rel="noopener">dados.gov.br</a></li>
          <li>{t.rodape.fonte}</li>
        </Coluna>
        <Coluna titulo={t.rodape.stack}>
          <li>Python · DuckDB · Parquet</li>
          <li>GitHub Actions</li>
          <li>Next.js · Tailwind · WebGPU</li>
          <li>Vercel</li>
        </Coluna>
        <Coluna titulo={t.rodape.autor}>
          <li>Arthur Delacorte</li>
          <li><a className={estiloLink} href="https://github.com/Bolapipa" target="_blank" rel="noopener">github.com/Bolapipa</a></li>
          <li><a className={estiloLink} href="https://arthurdelacorte.vercel.app" target="_blank" rel="noopener">{t.rodape.portfolio}</a></li>
        </Coluna>
      </div>
      <div className="border-t border-linha">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-5 font-mono text-xs text-tinta-3 sm:px-6 lg:px-8">
          <span>© 2026 Clock-in</span>
          <span>{t.hero.kicker}</span>
        </div>
      </div>
    </footer>
  );
}
