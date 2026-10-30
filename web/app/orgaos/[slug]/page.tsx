// Página de um órgão: gerada no build para cada órgão da API (uma pasta por órgão em out/orgaos/)
import type { Metadata } from "next";
import { Suspense } from "react";

import { PaginaDoOrgao } from "@/components/orgao/PaginaDoOrgao";
import { formatarNumero, formatarPercentual, nomeLegivel } from "@/lib/dados";
import { lerListaDeOrgaos, lerResumo } from "@/lib/servidor";

// Sem a API no build, gera uma página só, que avisa que não há dados
const SEM_DADOS = "sem-dados";

export async function generateStaticParams() {
  const lista = await lerListaDeOrgaos();
  return lista?.orgaos.length ? lista.orgaos.map((orgao) => ({ slug: orgao.slug })) : [{ slug: SEM_DADOS }];
}

async function acharOrgao(slug: string) {
  const lista = await lerListaDeOrgaos();
  return lista?.orgaos.find((orgao) => orgao.slug === slug) ?? null;
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const orgao = await acharOrgao((await params).slug);
  if (!orgao) return { title: "Órgão" };
  return {
    title: nomeLegivel(orgao.nome),
    description: `${nomeLegivel(orgao.nome)}: ${formatarNumero(orgao.qtd_bases)} bases no dados.gov.br, ${formatarPercentual(orgao.percentual_ok)} dos links respondendo bem e ${formatarNumero(orgao.links_quebrados)} links quebrados.`,
  };
}

export default async function Pagina({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [orgao, resumo] = await Promise.all([acharOrgao(slug), lerResumo()]);
  // Suspense: o painel da base lê o endereço (?base=) só no navegador
  return (
    <Suspense>
      <PaginaDoOrgao orgao={orgao} dataColeta={resumo?.data_coleta ?? null} />
    </Suspense>
  );
}
