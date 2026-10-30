// Página de um órgão (as bases dele) e página de uma base (status, motivo e saúde dos links)
import { ListaDeBases } from "../components/Listas";
import { Carregando, ErroDeCarga, Miolo, Trilha } from "../components/Moldura";
import { Ficha, Selo } from "../components/Pecas";
import { Regua } from "../components/Regua";
import { useOrgao } from "../lib/api";
import {
  ROTULOS_ESFERA, ROTULOS_PERIODICIDADE, explicarStatus, formatarNumero, formatarPercentual, linkDoOrgao,
  partesDaRegua, primeiraMaiuscula, rotulo,
} from "../lib/dados";
import { useTituloDaPagina } from "../lib/useRota";

const URL_BASE_DO_PORTAL = "https://dados.gov.br/dados/conjuntos-dados/";

export function PaginaOrgao({ slug }: { slug: string }) {
  const carga = useOrgao(slug);
  useTituloDaPagina(carga.estado === "pronto" ? carga.dados.nome : undefined);

  if (carga.estado === "carregando") return <Miolo><Carregando texto="Carregando o órgão" /></Miolo>;
  if (carga.estado === "erro") {
    return <Miolo><Trilha passos={[{ texto: "Início", endereco: "#" }, { texto: "Órgão" }]} /><ErroDeCarga texto="Não foi possível abrir este órgão. Confira o endereço ou procure o órgão na página inicial." /></Miolo>;
  }

  const orgao = carga.dados;
  const partes = partesDaRegua({
    total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados,
  });

  return (
    <Miolo>
      <Trilha passos={[{ texto: "Início", endereco: "#" }, { texto: orgao.nome }]} />
      <section className="grid items-start gap-x-12 gap-y-6 pb-2 pt-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
        <div>
          <h1 className="titulo-condensado m-0 mb-3 text-[clamp(2.1rem,5vw,3.6rem)] leading-none">{orgao.nome}</h1>
          <p className="m-0 text-tinta-suave">
            Esfera {rotulo(ROTULOS_ESFERA, orgao.esfera).toLowerCase()} · {formatarNumero(orgao.qtd_bases)} bases
          </p>
        </div>
        <Ficha itens={[
          { rotulo: "Links testados", valor: formatarNumero(orgao.links_testados), detalhe: `de ${formatarNumero(orgao.links_total)} (cobertura de ${formatarPercentual(orgao.cobertura_links)})` },
          { rotulo: "Respondendo bem", valor: formatarPercentual(orgao.percentual_ok), detalhe: `${formatarNumero(orgao.links_ok)} links`,
            // Verde só quando a porcentagem é alta de verdade
            tom: (orgao.percentual_ok ?? 0) >= 90 ? "bom" : "" },
          { rotulo: "Bases fora do ar", valor: formatarNumero(orgao.bases_fora_do_ar), detalhe: "todos os links quebrados", tom: "ruim" },
        ]} />
      </section>
      <section aria-label="Saúde dos links do órgão" className="pt-6">
        <Regua partes={partes} rotulo={`Links de ${orgao.nome}`} />
      </section>
      {/* key: ao trocar de órgão, a busca e a ordem da lista começam do zero */}
      <ListaDeBases key={orgao.slug} slugDoOrgao={orgao.slug} bases={orgao.bases} />
    </Miolo>
  );
}

export function PaginaBase({ slugDoOrgao, slugDaBase }: { slugDoOrgao: string; slugDaBase: string }) {
  const carga = useOrgao(slugDoOrgao);
  const base = carga.estado === "pronto" ? carga.dados.bases.find((candidata) => candidata.slug === slugDaBase) : undefined;
  useTituloDaPagina(carga.estado === "pronto" ? (base ? base.titulo || base.slug : "Base não encontrada") : undefined);

  if (carga.estado === "carregando") return <Miolo><Carregando texto="Carregando a base" /></Miolo>;
  if (carga.estado === "erro") {
    return <Miolo><Trilha passos={[{ texto: "Início", endereco: "#" }, { texto: "Base" }]} /><ErroDeCarga texto="Não foi possível abrir esta base. Confira o endereço ou procure a base na página do órgão." /></Miolo>;
  }

  const orgao = carga.dados;
  const trilha = [{ texto: "Início", endereco: "#" }, { texto: orgao.nome, endereco: linkDoOrgao(orgao.slug) }];

  if (!base) {
    return (
      <Miolo>
        <Trilha passos={[...trilha, { texto: "Base não encontrada" }]} />
        <h1 className="titulo-condensado mb-3 mt-5 text-[clamp(2.1rem,5vw,3.6rem)] leading-none">Base não encontrada</h1>
        <p className="text-tinta-suave">Esta base não está na coleta deste dia. Volte para a lista do órgão e procure pelo título.</p>
      </Miolo>
    );
  }

  const partes = partesDaRegua({
    total: base.links_total, ok: base.links_ok, emObservacao: base.links_em_observacao, quebrados: base.links_quebrados,
  });
  const motivo = base.motivo ?? (base.fora_do_ar ? "Todos os links desta base estão quebrados." : "O status pelo conteúdo ainda não foi calculado para esta base.");

  return (
    <Miolo>
      <Trilha passos={[...trilha, { texto: base.titulo || base.slug }]} />
      <section className="grid items-start gap-x-12 gap-y-6 pb-2 pt-5 lg:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
        <div>
          <h1 className="titulo-condensado m-0 mb-3 text-[clamp(2.1rem,5vw,3.6rem)] leading-none">{base.titulo || base.slug}</h1>
          <p className="m-0 text-tinta-suave">
            {orgao.nome} · Periodicidade {rotulo(ROTULOS_PERIODICIDADE, base.periodicidade).toLowerCase()}
          </p>
          <div className="mt-6">
            <h2 className="sr-only">Status</h2>
            <Selo status={base.status} grande />
            <p className="largura-90 m-0 mt-4 max-w-[34ch] text-[clamp(1.2rem,2.2vw,1.5rem)] font-medium leading-snug">{primeiraMaiuscula(motivo)}</p>
            <p className="m-0 mt-2 max-w-[60ch] text-tinta-suave">{explicarStatus(base.status)}</p>
          </div>
        </div>
        <Ficha itens={[
          { rotulo: "Links", valor: formatarNumero(base.links_total), detalhe: "cadastrados na base" },
          { rotulo: "Testados", valor: formatarNumero(base.links_testados), detalhe: "com algum teste conclusivo" },
        ]} />
      </section>
      <section aria-label="Saúde dos links da base" className="pt-6">
        <Regua partes={partes} rotulo="Links da base" />
        <a href={URL_BASE_DO_PORTAL + encodeURIComponent(base.slug)} target="_blank" rel="noopener"
          className="mt-8 inline-block rounded-md border-2 border-carimbo px-4 py-2.5 font-semibold no-underline transition-colors hover:bg-carimbo-fundo">
          Ver esta base no dados.gov.br
        </a>
      </section>
    </Miolo>
  );
}
