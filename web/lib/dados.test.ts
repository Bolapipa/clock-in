// Testes das funções puras do site (lib/dados.ts). Rodar com:  npm test
// Não abre navegador nem usa rede: só confere busca, filtros, ordenação, endereços, régua e textos.
import { describe, expect, test } from "vitest";

import {
  EXPLICACOES_STATUS, ORDENS_BASES, ORDENS_ORGAOS, ROTULOS_PERIODICIDADE, explicarStatus, filtrarBases, filtrarOrgaos,
  formatarData, formatarNumero, formatarPercentual, fraseDaResposta, lerOrdem, linkDaBase, linkDoOrgao, normalizar, ordenar,
  filtrarPorEstado, partesDaRegua, primeiraMaiuscula, rotulo, slugValido, temProblema, type OrgaoResumo,
} from "./dados";

const ORGAOS = [
  { nome: "IBGE - Fundação Instituto Brasileiro de Geografia", slug: "ibge", esfera: "FEDERAL", qtd_bases: 415, percentual_ok: 80.5 },
  { nome: "Prefeitura de Fortaleza", slug: "prefeitura-de-fortaleza", esfera: "MUNICIPAL", qtd_bases: 619, percentual_ok: null },
  { nome: "Governo do Estado de Alagoas", slug: "governo-do-estado-de-alagoas", esfera: "ESTADUAL", qtd_bases: 366, percentual_ok: 12.0 },
];
// Os testes só usam algumas chaves de cada órgão
const orgaos = ORGAOS as unknown as Parameters<typeof filtrarOrgaos>[0];

const BASES = [
  { titulo: "Frota de veículos", links_quebrados: 0, links_em_observacao: 0, fora_do_ar: false },
  { titulo: "Contratos públicos", links_quebrados: 2, links_em_observacao: 0, fora_do_ar: false },
  { titulo: "Escolas", links_quebrados: 0, links_em_observacao: 1, fora_do_ar: false },
  { titulo: "Orçamento", links_quebrados: 0, links_em_observacao: 0, fora_do_ar: true },
];

describe("formatação", () => {
  test("normalizar tira acentos e ignora maiúsculas", () => {
    expect(normalizar("Fundação Instituto Saúde")).toBe("fundacao instituto saude");
    expect(normalizar(null)).toBe("");
  });

  test("formatarNumero, formatarPercentual e formatarData usam o jeito brasileiro", () => {
    expect(formatarNumero(19613)).toBe("19.613");
    expect(formatarNumero(null)).toBe("-");
    expect(formatarPercentual(84.6)).toBe("84,6%");
    expect(formatarPercentual(100)).toBe("100,0%");
    expect(formatarPercentual(null)).toBe("-");
    expect(formatarData("2026-10-26")).toBe("26/10/2026");
  });

  test("rotulo usa o texto pronto ou capricha o que vier da API", () => {
    expect(rotulo({ FEDERAL: "Federal" }, "FEDERAL")).toBe("Federal");
    expect(rotulo({}, "NAO_DECLARADA")).toBe("Nao declarada");
    expect(rotulo({}, "MENSAL")).toBe("Mensal");
  });

  test("as periodicidades conhecidas têm rótulo com acento e uma nova ainda fica legível", () => {
    expect(rotulo(ROTULOS_PERIODICIDADE, "NAO_DECLARADA")).toBe("Não declarada");
    expect(rotulo(ROTULOS_PERIODICIDADE, "DIARIA")).toBe("Diária");
    expect(rotulo(ROTULOS_PERIODICIDADE, "SOB_DEMANDA")).toBe("Sob demanda");
    expect(rotulo(ROTULOS_PERIODICIDADE, "BIMESTRAL")).toBe("Bimestral");
  });

  test("primeiraMaiuscula só mexe na primeira letra", () => {
    expect(primeiraMaiuscula("nenhum arquivo tabular da base foi lido")).toBe("Nenhum arquivo tabular da base foi lido");
    expect(primeiraMaiuscula("IBGE publica")).toBe("IBGE publica");
    expect(primeiraMaiuscula("")).toBe("");
    expect(primeiraMaiuscula(null)).toBe("");
  });

  test("explicarStatus tem uma frase para cada status e fica vazio para um desconhecido", () => {
    for (const status of ["EM_DIA", "ATRASADA", "PARADA", "FORA_DO_AR", "NAO_VERIFICAVEL"]) {
      expect(explicarStatus(status).length).toBeGreaterThan(20);
    }
    expect(explicarStatus("STATUS_NOVO")).toBe("");
    // Não verificável nunca é descrito como desatualizado
    expect(EXPLICACOES_STATUS.NAO_VERIFICAVEL).toMatch(/não quer dizer que a base esteja desatualizada/);
  });
});

describe("endereços", () => {
  test("linkDoOrgao e linkDaBase montam os caminhos e protegem caracteres especiais", () => {
    expect(linkDoOrgao("ibge")).toBe("/orgaos/ibge/");
    expect(linkDaBase("ibge", "frota-de-veiculos")).toBe("/orgaos/ibge/?base=frota-de-veiculos");
    expect(linkDaBase("ibge", "a b")).toBe("/orgaos/ibge/?base=a%20b");
  });

  test("slugValido aceita slugs normais, inclusive os que linkDaBase gera", () => {
    for (const slug of ["ibge", "frota-de-veiculos-rab1", "base-1.csv", "A_b~c"]) expect(slugValido(slug)).toBe(slug);
    const endereco = new URL(linkDaBase("ibge", "base-1.csv"), "https://exemplo.br");
    expect(slugValido(endereco.searchParams.get("base"))).toBe("base-1.csv");
  });

  test("slugValido ignora qualquer texto estranho ou malicioso", () => {
    for (const texto of ["../../etc", "A<script>", "<img src=x>", "a/b", "a b", "", "x".repeat(201), null, undefined]) {
      expect(slugValido(texto), String(texto)).toBeNull();
    }
  });
});

describe("busca, filtro e ordem", () => {
  test("filtrarOrgaos busca por parte do nome sem acento e filtra a esfera", () => {
    expect(filtrarOrgaos(orgaos, { texto: "fundacao" }).map((o) => o.slug)).toEqual(["ibge"]);
    expect(filtrarOrgaos(orgaos, { texto: "FORTALEZA" }).map((o) => o.slug)).toEqual(["prefeitura-de-fortaleza"]);
    expect(filtrarOrgaos(orgaos, { esfera: "ESTADUAL" }).map((o) => o.slug)).toEqual(["governo-do-estado-de-alagoas"]);
    expect(filtrarOrgaos(orgaos, { texto: "xyz" })).toHaveLength(0);
    expect(filtrarOrgaos(orgaos)).toHaveLength(3);
  });

  test("ordenar não altera a lista, respeita a direção e deixa nulos no fim", () => {
    const original = [...ORGAOS];
    expect(ordenar(ORGAOS, "qtd_bases", "desc").map((o) => o.slug)).toEqual(["prefeitura-de-fortaleza", "ibge", "governo-do-estado-de-alagoas"]);
    expect(ORGAOS).toEqual(original);
    expect(ordenar(ORGAOS, "qtd_bases", "asc").map((o) => o.slug)).toEqual(["governo-do-estado-de-alagoas", "ibge", "prefeitura-de-fortaleza"]);
    // O percentual nulo fica por último nas duas direções
    expect(ordenar(ORGAOS, "percentual_ok", "desc").at(-1)?.slug).toBe("prefeitura-de-fortaleza");
    expect(ordenar(ORGAOS, "percentual_ok", "asc").at(-1)?.slug).toBe("prefeitura-de-fortaleza");
  });

  test("ordenar texto usa a ordem do português", () => {
    expect(ordenar(ORGAOS, "nome", "asc").map((o) => o.nome)).toEqual([
      "Governo do Estado de Alagoas", "IBGE - Fundação Instituto Brasileiro de Geografia", "Prefeitura de Fortaleza",
    ]);
  });

  test("temProblema: quebrado, em observação ou fora do ar", () => {
    expect(BASES.map(temProblema)).toEqual([false, true, true, true]);
  });

  test("filtrarBases combina busca e só problemas", () => {
    expect(filtrarBases(BASES, { apenasProblemas: true })).toHaveLength(3);
    expect(filtrarBases(BASES, { texto: "orcamento" }).map((b) => b.titulo)).toEqual(["Orçamento"]);
    expect(filtrarBases(BASES, { texto: "frota", apenasProblemas: true })).toEqual([]);
  });

  test("lerOrdem entende 'coluna|direção' e volta para a ordem padrão com texto inválido", () => {
    expect(lerOrdem("percentual_ok|asc")).toEqual({ coluna: "percentual_ok", direcao: "asc" });
    expect(lerOrdem("nome|desc")).toEqual({ coluna: "nome", direcao: "desc" });
    expect(lerOrdem("qualquer coisa")).toEqual({ coluna: "qtd_bases", direcao: "desc" });
    expect(lerOrdem("nome|lado")).toEqual({ coluna: "qtd_bases", direcao: "desc" });
    expect(lerOrdem(null)).toEqual({ coluna: "qtd_bases", direcao: "desc" });
    expect(lerOrdem("", "links_quebrados|desc")).toEqual({ coluna: "links_quebrados", direcao: "desc" });
  });

  test("todas as formas de ordenar oferecidas na tela são válidas e começam pela ordem inicial", () => {
    for (const ordem of [...ORDENS_ORGAOS, ...ORDENS_BASES]) {
      const lida = lerOrdem(ordem.valor, "x|y");
      expect(`${lida.coluna}|${lida.direcao}`).toBe(ordem.valor);
      expect(ordem.texto.length).toBeGreaterThan(5);
    }
    expect(ORDENS_ORGAOS[0].valor).toBe("qtd_bases|desc");
    expect(ORDENS_BASES[0].valor).toBe("links_quebrados|desc");
  });
});

describe("filtro vindo do mostrador", () => {
  const orgao = (nome: string, campos: Partial<OrgaoResumo>): OrgaoResumo => ({
    nome, slug: nome.toLowerCase(), esfera: "FEDERAL", qtd_bases: 1, links_total: 10, links_testados: 10, links_ok: 10,
    links_em_observacao: 0, links_quebrados: 0, bases_fora_do_ar: 0, percentual_ok: 100, cobertura_links: 100, ...campos,
  });
  const LISTA = [
    orgao("A", { links_quebrados: 2, percentual_ok: 80 }),
    orgao("B", { links_quebrados: 9, links_em_observacao: 1, percentual_ok: 50 }),
    orgao("C", { links_testados: 4, percentual_ok: null }),
    orgao("D", { percentual_ok: 99 }),
  ];

  test("quebrados e em observação mostram só quem tem o problema, do pior para o melhor", () => {
    expect(filtrarPorEstado(LISTA, "quebrados").map((o) => o.nome)).toEqual(["B", "A"]);
    expect(filtrarPorEstado(LISTA, "observacao").map((o) => o.nome)).toEqual(["B"]);
  });

  test("não deu para testar mostra quem tem links sem teste conclusivo", () => {
    expect(filtrarPorEstado(LISTA, "nao_testados").map((o) => o.nome)).toEqual(["C"]);
  });

  test("respondendo bem só ordena (porcentagem nula no fim), e sem estado a lista volta inteira", () => {
    expect(filtrarPorEstado(LISTA, "ok").map((o) => o.nome)).toEqual(["D", "A", "B", "C"]);
    expect(filtrarPorEstado(LISTA, null)).toBe(LISTA);
  });
});

describe("régua e frase-resposta", () => {
  test("partesDaRegua: as quatro partes somam o total e o que sobra é 'não deu para testar'", () => {
    // Números reais do dia 26/10/2026: 124.375 links, 68.343 com teste conclusivo
    const partes = partesDaRegua({ total: 124375, ok: 64097, emObservacao: 4246, quebrados: 0 });
    expect(partes.map((p) => p.chave)).toEqual(["ok", "observacao", "quebrados", "nao_testados"]);
    expect(partes.map((p) => p.quantidade)).toEqual([64097, 4246, 0, 56032]);
    expect(partes.reduce((soma, p) => soma + p.quantidade, 0)).toBe(124375);
    expect(Math.abs(partes.reduce((soma, p) => soma + p.percentual, 0) - 100)).toBeLessThan(1e-9);
  });

  test("partesDaRegua aguenta total zero, campos ausentes e soma maior que o total", () => {
    expect(partesDaRegua({ total: 0 }).map((p) => [p.quantidade, p.percentual])).toEqual([[0, 0], [0, 0], [0, 0], [0, 0]]);
    // Nunca devolve quantidade negativa para os links sem teste
    expect(partesDaRegua({ total: 5, ok: 9, emObservacao: 0, quebrados: 0 })[3].quantidade).toBe(0);
  });

  test("partesDaRegua explica cada parte em linguagem simples", () => {
    const partes = partesDaRegua({ total: 10, ok: 5, emObservacao: 2, quebrados: 1 });
    expect(partes.map((p) => p.rotulo)).toEqual(["respondendo bem", "em observação", "quebrados", "não deu para testar"]);
    for (const parte of partes) expect(parte.descricao.length).toBeGreaterThan(15);
    // A regra de falha aparece na descrição: 3 falhas seguidas é quebrado
    expect(partes[2].descricao).toMatch(/3 ou mais falhas/);
  });

  test("fraseDaResposta dá a porcentagem e conta os problemas no singular e no plural", () => {
    expect(fraseDaResposta({ percentual_ok: 93.8, em_observacao: 4246, quebrados: 0 }))
      .toBe("93,8% dos links testados respondem bem. 4.246 estão em observação e nenhum está quebrado.");
    expect(fraseDaResposta({ percentual_ok: 99.9, em_observacao: 0, quebrados: 1 }))
      .toBe("99,9% dos links testados respondem bem. Nenhum está em observação e 1 está quebrado.");
    expect(fraseDaResposta({ percentual_ok: 80, em_observacao: 1, quebrados: 12 }))
      .toBe("80,0% dos links testados respondem bem. 1 está em observação e 12 estão quebrados.");
  });

  test("fraseDaResposta não inventa porcentagem quando não há links testados o bastante", () => {
    expect(fraseDaResposta({ percentual_ok: null, em_observacao: 0, quebrados: 0 })).toMatch(/Ainda não há links testados/);
  });
});
