// Testes das funções puras do site (site/app.js). Rodar com:  node --test tests/site/app.test.js
// Não abre navegador nem usa rede: só confere busca, filtros, ordenação e formatação.

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  normalizar, formatarNumero, formatarPercentual, rotulo, lerHash, filtrarOrgaos, filtrarBases, temProblema, ordenar,
  ROTULOS_PERIODICIDADE,
} = require("../../site/app.js");

const ORGAOS = [
  { nome: "IBGE - Fundação Instituto Brasileiro de Geografia", slug: "ibge", esfera: "FEDERAL", qtd_bases: 415, percentual_ok: 80.5 },
  { nome: "Prefeitura de Fortaleza", slug: "prefeitura-de-fortaleza", esfera: "MUNICIPAL", qtd_bases: 619, percentual_ok: null },
  { nome: "Governo do Estado de Alagoas", slug: "governo-do-estado-de-alagoas", esfera: "ESTADUAL", qtd_bases: 366, percentual_ok: 12.0 },
];

test("normalizar tira acentos e ignora maiúsculas", () => {
  assert.equal(normalizar("Fundação Instituto Saúde"), "fundacao instituto saude");
  assert.equal(normalizar(null), "");
});

test("formatarNumero e formatarPercentual usam o jeito brasileiro", () => {
  assert.equal(formatarNumero(19613), "19.613");
  assert.equal(formatarNumero(null), "-");
  assert.equal(formatarPercentual(84.6), "84,6%");
  assert.equal(formatarPercentual(100), "100,0%");
  assert.equal(formatarPercentual(null), "-");
});

test("rotulo usa o texto pronto ou capricha o que vier da API", () => {
  assert.equal(rotulo({ FEDERAL: "Federal" }, "FEDERAL"), "Federal");
  assert.equal(rotulo({}, "NAO_DECLARADA"), "Nao declarada");
  assert.equal(rotulo({}, "MENSAL"), "Mensal");
});

test("as periodicidades conhecidas têm rótulo com acento", () => {
  assert.equal(rotulo(ROTULOS_PERIODICIDADE, "NAO_DECLARADA"), "Não declarada");
  assert.equal(rotulo(ROTULOS_PERIODICIDADE, "DIARIA"), "Diária");
  assert.equal(rotulo(ROTULOS_PERIODICIDADE, "SOB_DEMANDA"), "Sob demanda");
  // Uma periodicidade nova que a API passe a mandar ainda aparece de forma legível
  assert.equal(rotulo(ROTULOS_PERIODICIDADE, "BIMESTRAL"), "Bimestral");
});

test("lerHash aceita só o formato #orgao=slug", () => {
  assert.equal(lerHash("#orgao=ibge"), "ibge");
  assert.equal(lerHash("#orgao=prefeitura-de-fortaleza"), "prefeitura-de-fortaleza");
  assert.equal(lerHash(""), null);
  assert.equal(lerHash("#outra=coisa"), null);
  assert.equal(lerHash("#orgao=../../etc"), null);
  assert.equal(lerHash("#orgao=A<script>"), null);
});

test("filtrarOrgaos busca por parte do nome sem acento e filtra a esfera", () => {
  assert.deepEqual(filtrarOrgaos(ORGAOS, { texto: "fundacao" }).map((o) => o.slug), ["ibge"]);
  assert.deepEqual(filtrarOrgaos(ORGAOS, { texto: "FORTALEZA" }).map((o) => o.slug), ["prefeitura-de-fortaleza"]);
  assert.deepEqual(filtrarOrgaos(ORGAOS, { esfera: "ESTADUAL" }).map((o) => o.slug), ["governo-do-estado-de-alagoas"]);
  assert.equal(filtrarOrgaos(ORGAOS, { texto: "xyz" }).length, 0);
  assert.equal(filtrarOrgaos(ORGAOS).length, 3);
});

test("ordenar não altera a lista, respeita a direção e deixa nulos no fim", () => {
  const original = [...ORGAOS];
  const decrescente = ordenar(ORGAOS, "qtd_bases", "desc").map((o) => o.slug);
  assert.deepEqual(decrescente, ["prefeitura-de-fortaleza", "ibge", "governo-do-estado-de-alagoas"]);
  assert.deepEqual(ORGAOS, original);

  assert.deepEqual(ordenar(ORGAOS, "qtd_bases", "asc").map((o) => o.slug),
    ["governo-do-estado-de-alagoas", "ibge", "prefeitura-de-fortaleza"]);

  // O percentual nulo fica por último nas duas direções
  assert.equal(ordenar(ORGAOS, "percentual_ok", "desc").at(-1).slug, "prefeitura-de-fortaleza");
  assert.equal(ordenar(ORGAOS, "percentual_ok", "asc").at(-1).slug, "prefeitura-de-fortaleza");
});

test("ordenar texto usa a ordem do português", () => {
  const nomes = ordenar(ORGAOS, "nome", "asc").map((o) => o.nome);
  assert.deepEqual(nomes, [
    "Governo do Estado de Alagoas",
    "IBGE - Fundação Instituto Brasileiro de Geografia",
    "Prefeitura de Fortaleza",
  ]);
});

const BASES = [
  { titulo: "Frota de veículos", links_quebrados: 0, links_em_observacao: 0, fora_do_ar: false },
  { titulo: "Contratos públicos", links_quebrados: 2, links_em_observacao: 0, fora_do_ar: false },
  { titulo: "Escolas", links_quebrados: 0, links_em_observacao: 1, fora_do_ar: false },
  { titulo: "Orçamento", links_quebrados: 0, links_em_observacao: 0, fora_do_ar: true },
];

test("temProblema: quebrado, em observação ou fora do ar", () => {
  assert.deepEqual(BASES.map(temProblema), [false, true, true, true]);
});

test("filtrarBases combina busca e só problemas", () => {
  assert.equal(filtrarBases(BASES, { apenasProblemas: true }).length, 3);
  assert.deepEqual(filtrarBases(BASES, { texto: "orcamento" }).map((b) => b.titulo), ["Orçamento"]);
  assert.deepEqual(filtrarBases(BASES, { texto: "frota", apenasProblemas: true }), []);
});
