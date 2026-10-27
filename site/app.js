// Clock-in: página inicial, página de cada órgão e de cada base, metodologia e API (protótipo).
// JavaScript puro, sem bibliotecas. Lê os JSON da pasta api/, gerados por publicar/gerar_api.py.

const URL_BASE_DO_PORTAL = "https://dados.gov.br/dados/conjuntos-dados/";
const ORGAOS_POR_PAGINA = 25;
const BASES_POR_PAGINA = 50;

const ROTULOS_ESFERA = { FEDERAL: "Federal", ESTADUAL: "Estadual", MUNICIPAL: "Municipal", NAO_CLASSIFICADA: "Não classificada" };
const ROTULOS_STATUS = {
  EM_DIA: "Em dia", ATRASADA: "Atrasada", PARADA: "Parada", FORA_DO_AR: "Fora do ar", NAO_VERIFICAVEL: "Não verificável",
};
const ROTULOS_PERIODICIDADE = {
  DIARIA: "Diária", SEMANAL: "Semanal", QUINZENAL: "Quinzenal", MENSAL: "Mensal", TRIMESTRAL: "Trimestral",
  QUADRIMESTRAL: "Quadrimestral", SEMESTRAL: "Semestral", ANUAL: "Anual", NAO_DECLARADA: "Não declarada",
  SOB_DEMANDA: "Sob demanda", OUTRAS: "Outras", SEM_DETALHE: "Sem detalhe",
};

// O que cada status quer dizer, em uma frase (também na página de metodologia)
const EXPLICACOES_STATUS = {
  EM_DIA: "A base mudou dentro do prazo esperado para a periodicidade dela.",
  ATRASADA: "A base passou do prazo esperado sem mudança no conteúdo.",
  PARADA: "A base passou de 3 vezes o prazo esperado sem mudança no conteúdo.",
  FORA_DO_AR: "Todos os links da base estão quebrados.",
  NAO_VERIFICAVEL: "Ainda não dá para dizer: faltam arquivos lidos ou histórico, ou a base não declara periodicidade. "
    + "Isso não quer dizer que a base esteja desatualizada.",
};

// Colunas da tabela de órgãos: chave do JSON e título
const COLUNAS_ORGAOS = [
  { chave: "nome", titulo: "Órgão" },
  { chave: "esfera", titulo: "Esfera" },
  { chave: "qtd_bases", titulo: "Bases" },
  { chave: "links_testados", titulo: "Links testados" },
  { chave: "percentual_ok", titulo: "Respondendo bem" },
  { chave: "links_em_observacao", titulo: "Em observação" },
  { chave: "links_quebrados", titulo: "Quebrados" },
  { chave: "bases_fora_do_ar", titulo: "Bases fora do ar" },
];

const COLUNAS_BASES = [
  { chave: "titulo", titulo: "Base" },
  { chave: "periodicidade", titulo: "Periodicidade" },
  { chave: "links_total", titulo: "Links" },
  { chave: "links_ok", titulo: "Respondendo bem" },
  { chave: "links_em_observacao", titulo: "Em observação" },
  { chave: "links_quebrados", titulo: "Quebrados" },
  { chave: "status", titulo: "Status" },
];

// --- Funções puras (testadas em tests/site/app.test.js) ---

// Texto sem acentos e em minúsculas, para a busca ignorar maiúsculas e acentos
function normalizar(texto) {
  return String(texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function formatarNumero(numero) {
  return numero == null ? "-" : numero.toLocaleString("pt-BR");
}

function formatarPercentual(percentual) {
  if (percentual == null) return "-";
  return percentual.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
}

// "NAO_DECLARADA" vira "Nao declarada" quando não há rótulo pronto
function rotulo(tabela, chave) {
  if (tabela[chave]) return tabela[chave];
  const texto = String(chave ?? "").toLowerCase().replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// Lê o endereço da página e diz qual tela abrir:
//   ""                          -> início
//   "#metodologia", "#api"      -> páginas de texto
//   "#orgao=slug"               -> um órgão
//   "#orgao=slug&base=slug"     -> uma base do órgão
// Qualquer outra coisa (inclusive texto estranho) volta para o início
function lerRota(hash) {
  const texto = String(hash ?? "").replace(/^#/, "");
  if (texto === "metodologia") return { tipo: "metodologia" };
  if (texto === "api") return { tipo: "api" };
  const achado = /^orgao=([a-z0-9-]+)(?:&base=([A-Za-z0-9._~-]+))?$/.exec(texto);
  if (!achado) return { tipo: "inicio" };
  return achado[2] ? { tipo: "base", orgao: achado[1], base: achado[2] } : { tipo: "orgao", orgao: achado[1] };
}

// Endereço interno da página de uma base
function linkDaBase(slugDoOrgao, slugDaBase) {
  return `#orgao=${slugDoOrgao}&base=${encodeURIComponent(slugDaBase)}`;
}

// Primeira letra maiúscula, sem mexer no resto: "nenhum arquivo lido" vira "Nenhum arquivo lido"
function primeiraMaiuscula(texto) {
  const frase = String(texto ?? "");
  return frase.charAt(0).toUpperCase() + frase.slice(1);
}

// A frase que explica o status; para um status que a API passe a mandar e a página não conheça, devolve vazio
function explicarStatus(status) {
  return EXPLICACOES_STATUS[status] ?? "";
}

function filtrarOrgaos(orgaos, { texto = "", esfera = "" } = {}) {
  const busca = normalizar(texto).trim();
  return orgaos.filter((orgao) => (!esfera || orgao.esfera === esfera) && (!busca || normalizar(orgao.nome).includes(busca)));
}

// Uma base tem problema se algum link está em observação ou quebrado, ou se está fora do ar
function temProblema(base) {
  return base.fora_do_ar || base.links_quebrados > 0 || base.links_em_observacao > 0;
}

function filtrarBases(bases, { texto = "", apenasProblemas = false } = {}) {
  const busca = normalizar(texto).trim();
  return bases.filter((base) => (!apenasProblemas || temProblema(base)) && (!busca || normalizar(base.titulo).includes(busca)));
}

// Ordena sem alterar a lista original; valores nulos ficam sempre no fim
function ordenar(lista, coluna, direcao = "desc") {
  const fator = direcao === "asc" ? 1 : -1;
  const desempate = (a, b) => String(a.nome ?? a.titulo ?? "").localeCompare(String(b.nome ?? b.titulo ?? ""), "pt-BR");
  return [...lista].sort((a, b) => {
    const x = a[coluna];
    const y = b[coluna];
    if (x == null && y == null) return desempate(a, b);
    if (x == null) return 1;
    if (y == null) return -1;
    const comparacao = typeof x === "string" ? x.localeCompare(y, "pt-BR") : Number(x) - Number(y);
    return comparacao * fator || desempate(a, b);
  });
}

// As quatro partes da régua de saúde dos links. A soma delas é sempre o total de links:
// "sem teste conclusivo" é o que sobra (timeout, 403, 405 ou ainda não alcançado pelo teste)
const PARTES_DA_REGUA = [
  { chave: "ok", rotulo: "respondendo bem" },
  { chave: "observacao", rotulo: "em observação" },
  { chave: "quebrados", rotulo: "quebrados" },
  { chave: "nao_testados", rotulo: "sem teste conclusivo" },
];

function partesDaRegua({ total, ok, emObservacao, quebrados }) {
  const valores = { ok: ok ?? 0, observacao: emObservacao ?? 0, quebrados: quebrados ?? 0 };
  valores.nao_testados = Math.max(0, (total ?? 0) - valores.ok - valores.observacao - valores.quebrados);
  const soma = Object.values(valores).reduce((a, b) => a + b, 0);
  return PARTES_DA_REGUA.map(({ chave, rotulo }) => ({
    chave, rotulo, quantidade: valores[chave], percentual: soma > 0 ? (100 * valores[chave]) / soma : 0,
  }));
}

// "nenhum está quebrado", "1 está quebrado", "4.246 estão em observação"
function contarEstados(quantidade, singular, plural = singular) {
  if (!quantidade) return `nenhum está ${singular}`;
  return quantidade === 1 ? `1 está ${singular}` : `${formatarNumero(quantidade)} estão ${plural}`;
}

// A resposta do dia, em duas frases, a partir dos totais do Brasil
function fraseDaResposta({ percentual_ok, em_observacao, quebrados }) {
  if (percentual_ok == null) return "Ainda não há links testados o bastante para dar uma porcentagem.";
  return `${formatarPercentual(percentual_ok)} dos links testados respondem bem. `
    + `${primeiraMaiuscula(contarEstados(em_observacao, "em observação"))} e ${contarEstados(quebrados, "quebrado", "quebrados")}.`;
}

// --- Tela (só roda no navegador) ---

const estado = {
  resumo: null,
  orgaos: [],
  ordem: { coluna: "qtd_bases", direcao: "desc" },
  paginaOrgaos: 1,
  orgao: null,
  ordemBases: { coluna: "links_quebrados", direcao: "desc" },
  paginaBases: 1,
};

// Cria um elemento; o texto vai sempre como texto (nunca como HTML), por segurança
function el(tag, atributos = {}, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [nome, valor] of Object.entries(atributos)) {
    if (nome === "classe") elemento.className = valor;
    else elemento.setAttribute(nome, valor);
  }
  for (const filho of filhos) elemento.append(filho);
  return elemento;
}

const $ = (id) => document.getElementById(id);

// Telas da página: só uma aparece por vez
const TELAS = ["inicio", "detalhe", "pagina-base", "pagina-metodologia", "pagina-api"];

// Qual item do menu fica marcado em cada tela (órgão e base pertencem ao início)
const MENU_DA_TELA = { inicio: "#", detalhe: "#", "pagina-base": "#", "pagina-metodologia": "#metodologia", "pagina-api": "#api" };

function mostrarTela(id, titulo) {
  for (const tela of TELAS) $(tela).hidden = tela !== id;
  for (const item of document.querySelectorAll(".menu a")) {
    if (item.getAttribute("href") === MENU_DA_TELA[id]) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  document.title = titulo ? `${titulo} · Clock-in` : "Clock-in · Monitor de dados abertos do Brasil";
  window.scrollTo(0, 0);
}

async function carregar(caminho) {
  const resposta = await fetch(caminho);
  if (!resposta.ok) throw new Error(`${caminho}: HTTP ${resposta.status}`);
  return resposta.json();
}

function mostrarErro(mensagem) {
  const caixa = $("erro");
  caixa.textContent = mensagem;
  caixa.hidden = false;
}

function cartao(titulo, valor, detalhe, tom = "") {
  return el("div", { classe: `cartao ${tom}`.trim() },
    el("div", { classe: "rotulo" }, titulo),
    el("div", { classe: "valor" }, valor),
    el("div", { classe: "detalhe" }, detalhe));
}

// Marcas de relógio sob a régua: 60 "minutos", com uma marca maior a cada 5 ("horas")
function marcasDeRelogio() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "marcas");
  svg.setAttribute("aria-hidden", "true");
  for (let minuto = 0; minuto <= 60; minuto += 1) {
    const hora = minuto % 5 === 0;
    const marca = document.createElementNS(ns, "line");
    marca.setAttribute("x1", `${(minuto / 60) * 100}%`);
    marca.setAttribute("x2", `${(minuto / 60) * 100}%`);
    marca.setAttribute("y1", "0");
    marca.setAttribute("y2", hora ? "14" : "7");
    marca.setAttribute("stroke", "currentColor");
    marca.setAttribute("stroke-width", hora ? "2" : "1");
    svg.append(marca);
  }
  return svg;
}

// Uma parte da régua: a largura vem da quantidade de links
function parteDaRegua(parte) {
  const segmento = el("i", { classe: `parte ${parte.chave}` });
  segmento.style.flexGrow = parte.quantidade;
  return segmento;
}

// Desenha a régua de saúde dos links (barra, marcas de relógio e legenda) dentro da caixa indicada
function renderizarRegua(idDaCaixa, partes) {
  const descricao = partes.map((parte) => `${formatarNumero(parte.quantidade)} ${parte.rotulo}`).join(", ");
  const regua = el("div", { classe: "regua", role: "img", "aria-label": `Links: ${descricao}` },
    ...partes.filter((parte) => parte.quantidade > 0).map(parteDaRegua));
  const legenda = el("ul", { classe: "legenda" }, ...partes.map((parte) => el("li", { classe: parte.chave },
    el("span", { classe: "amostra", "aria-hidden": "true" }),
    el("span", {}, el("strong", {}, formatarNumero(parte.quantidade)), ` ${parte.rotulo} (${formatarPercentual(parte.percentual)})`))));
  $(idDaCaixa).replaceChildren(regua, marcasDeRelogio(), legenda);
}

// Régua pequena de uma linha da tabela; fica tracejada quando o órgão tem poucos links testados
function reguaMini(orgao) {
  const mini = el("span", { classe: "mini", "aria-hidden": "true" });
  const partes = partesDaRegua({
    total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados,
  }).filter((parte) => parte.chave !== "nao_testados" && parte.quantidade > 0);
  if (orgao.percentual_ok == null || partes.length === 0) mini.classList.add("vazia");
  else mini.append(...partes.map(parteDaRegua));
  return mini;
}

function renderizarResumo(resumo) {
  const links = resumo.links;
  $("data-coleta").textContent = `Coleta de ${resumo.data_coleta.split("-").reverse().join("/")}`;
  $("resposta").textContent = fraseDaResposta(links);
  $("cartoes").replaceChildren(
    cartao("Bases monitoradas", formatarNumero(resumo.bases), `${formatarNumero(resumo.recursos)} arquivos e links`),
    cartao("Órgãos publicadores", formatarNumero(resumo.orgaos), "órgãos e entidades"),
    cartao("Links testados", formatarNumero(links.testados), `de ${formatarNumero(links.total)} (cobertura de ${formatarPercentual(links.cobertura)})`),
    cartao("Bases fora do ar", formatarNumero(resumo.bases_fora_do_ar), "todos os links quebrados", "ruim"));
  renderizarRegua("regua-brasil", partesDaRegua({
    total: links.total, ok: links.ok, emObservacao: links.em_observacao, quebrados: links.quebrados,
  }));
}

function cabecalho(colunas, ordem, aoOrdenar) {
  const linha = el("tr");
  for (const coluna of colunas) {
    const ativa = ordem.coluna === coluna.chave;
    const th = el("th", { scope: "col", "aria-sort": ativa ? (ordem.direcao === "asc" ? "ascending" : "descending") : "none" });
    const botao = el("button", { type: "button" }, coluna.titulo);
    botao.addEventListener("click", () => aoOrdenar(coluna.chave, ativa && ordem.direcao === "desc" ? "asc" : "desc"));
    th.append(botao);
    linha.append(th);
  }
  return linha;
}

function renderizarOrgaos() {
  const filtrados = filtrarOrgaos(estado.orgaos, { texto: $("busca-orgao").value, esfera: $("filtro-esfera").value });
  const ordenados = ordenar(filtrados, estado.ordem.coluna, estado.ordem.direcao);
  const visiveis = ordenados.slice(0, estado.paginaOrgaos * ORGAOS_POR_PAGINA);

  $("tabela-orgaos").tHead.replaceChildren(cabecalho(COLUNAS_ORGAOS, estado.ordem, (coluna, direcao) => {
    estado.ordem = { coluna, direcao };
    estado.paginaOrgaos = 1;
    renderizarOrgaos();
  }));

  $("tabela-orgaos").tBodies[0].replaceChildren(...visiveis.map((orgao) => {
    const linha = el("tr");
    linha.append(
      el("td", {}, el("a", { href: `#orgao=${orgao.slug}` }, orgao.nome)),
      el("td", {}, rotulo(ROTULOS_ESFERA, orgao.esfera)),
      el("td", {}, formatarNumero(orgao.qtd_bases)),
      el("td", {}, formatarNumero(orgao.links_testados)),
      el("td", { title: orgao.percentual_ok == null ? "Poucos links testados para calcular a porcentagem" : "" },
        formatarPercentual(orgao.percentual_ok), reguaMini(orgao)),
      el("td", {}, formatarNumero(orgao.links_em_observacao)),
      el("td", {}, formatarNumero(orgao.links_quebrados)),
      el("td", {}, formatarNumero(orgao.bases_fora_do_ar)));
    return linha;
  }));

  $("contagem-orgaos").textContent = `${formatarNumero(filtrados.length)} de ${formatarNumero(estado.orgaos.length)} órgãos`;
  $("mais-orgaos").hidden = visiveis.length >= ordenados.length;
}

function renderizarBases() {
  const orgao = estado.orgao;
  const filtradas = filtrarBases(orgao.bases, { texto: $("busca-base").value, apenasProblemas: $("so-problemas").checked });
  const ordenadas = ordenar(filtradas, estado.ordemBases.coluna, estado.ordemBases.direcao);
  const visiveis = ordenadas.slice(0, estado.paginaBases * BASES_POR_PAGINA);

  $("tabela-bases").tHead.replaceChildren(cabecalho(COLUNAS_BASES, estado.ordemBases, (coluna, direcao) => {
    estado.ordemBases = { coluna, direcao };
    estado.paginaBases = 1;
    renderizarBases();
  }));

  $("tabela-bases").tBodies[0].replaceChildren(...visiveis.map((base) => {
    const selo = el("span", { classe: `selo ${base.status.toLowerCase()}`, title: base.motivo ?? "" }, rotulo(ROTULOS_STATUS, base.status));
    const linha = el("tr");
    linha.append(
      el("td", {}, el("a", { href: linkDaBase(orgao.slug, base.slug) }, base.titulo || base.slug)),
      el("td", {}, rotulo(ROTULOS_PERIODICIDADE, base.periodicidade)),
      el("td", {}, formatarNumero(base.links_total)),
      el("td", {}, formatarNumero(base.links_ok)),
      el("td", {}, formatarNumero(base.links_em_observacao)),
      el("td", {}, formatarNumero(base.links_quebrados)),
      el("td", {}, selo));
    return linha;
  }));

  $("contagem-bases").textContent = `${formatarNumero(filtradas.length)} de ${formatarNumero(orgao.bases.length)} bases`;
  $("mais-bases").hidden = visiveis.length >= ordenadas.length;
}

// Carrega o arquivo de um órgão (reaproveita o que já está na memória); devolve null se falhar
async function carregarOrgao(slug) {
  if (estado.orgao && estado.orgao.slug === slug) return estado.orgao;
  try {
    estado.orgao = await carregar(`api/orgaos/${slug}.json`);
  } catch (erro) {
    mostrarErro("Não foi possível carregar este órgão.");
    return null;
  }
  // Ao trocar de órgão, a tabela de bases volta ao começo
  estado.ordemBases = { coluna: "links_quebrados", direcao: "desc" };
  estado.paginaBases = 1;
  $("busca-base").value = "";
  $("so-problemas").checked = false;
  return estado.orgao;
}

async function abrirOrgao(slug) {
  const orgao = await carregarOrgao(slug);
  if (!orgao) return;

  $("orgao-nome").textContent = orgao.nome;
  $("orgao-meta").textContent = `Esfera ${rotulo(ROTULOS_ESFERA, orgao.esfera).toLowerCase()} · ${formatarNumero(orgao.qtd_bases)} bases`;
  $("orgao-cartoes").replaceChildren(
    cartao("Links testados", formatarNumero(orgao.links_testados), `de ${formatarNumero(orgao.links_total)} (cobertura de ${formatarPercentual(orgao.cobertura_links)})`),
    cartao("Respondendo bem", formatarPercentual(orgao.percentual_ok), `${formatarNumero(orgao.links_ok)} links`, "bom"),
    cartao("Bases fora do ar", formatarNumero(orgao.bases_fora_do_ar), "todos os links quebrados", "ruim"));
  renderizarRegua("regua-orgao", partesDaRegua({
    total: orgao.links_total, ok: orgao.links_ok, emObservacao: orgao.links_em_observacao, quebrados: orgao.links_quebrados,
  }));

  mostrarTela("detalhe", orgao.nome);
  renderizarBases();
}

// Página de uma base: o status e o motivo, e a saúde dos links dela
async function abrirBase(slugDoOrgao, slugDaBase) {
  const orgao = await carregarOrgao(slugDoOrgao);
  if (!orgao) return;

  const voltar = $("voltar-orgao");
  voltar.href = `#orgao=${orgao.slug}`;
  voltar.textContent = `← ${orgao.nome}`;

  const base = orgao.bases.find((candidata) => candidata.slug === slugDaBase);
  $("base-portal").hidden = !base;
  if (!base) {
    $("base-titulo").textContent = "Base não encontrada";
    $("base-meta").textContent = "Esta base não está na coleta deste dia.";
    for (const id of ["base-motivo", "base-explicacao"]) $(id).textContent = "";
    $("base-selo").className = "selo";
    $("base-selo").textContent = "";
    $("base-cartoes").replaceChildren();
    $("regua-base").replaceChildren();
    mostrarTela("pagina-base", "Base não encontrada");
    return;
  }

  $("base-titulo").textContent = base.titulo || base.slug;
  $("base-meta").textContent = `${orgao.nome} · Periodicidade ${rotulo(ROTULOS_PERIODICIDADE, base.periodicidade).toLowerCase()}`;
  $("base-selo").className = `selo ${base.status.toLowerCase()}`;
  $("base-selo").textContent = rotulo(ROTULOS_STATUS, base.status);
  const semMotivo = base.fora_do_ar
    ? "Todos os links desta base estão quebrados."
    : "O status pelo conteúdo ainda não foi calculado para esta base.";
  $("base-motivo").textContent = primeiraMaiuscula(base.motivo ?? semMotivo);
  $("base-explicacao").textContent = explicarStatus(base.status);
  $("base-cartoes").replaceChildren(
    cartao("Links", formatarNumero(base.links_total), "cadastrados na base"),
    cartao("Testados", formatarNumero(base.links_testados), "com algum teste conclusivo"));
  renderizarRegua("regua-base", partesDaRegua({
    total: base.links_total, ok: base.links_ok, emObservacao: base.links_em_observacao, quebrados: base.links_quebrados,
  }));
  $("base-portal").href = URL_BASE_DO_PORTAL + encodeURIComponent(base.slug);
  mostrarTela("pagina-base", base.titulo || base.slug);
}

function aoMudarOEndereco() {
  const rota = lerRota(window.location.hash);
  if (rota.tipo === "orgao") abrirOrgao(rota.orgao);
  else if (rota.tipo === "base") abrirBase(rota.orgao, rota.base);
  else if (rota.tipo === "metodologia") mostrarTela("pagina-metodologia", "Como medimos");
  else if (rota.tipo === "api") mostrarTela("pagina-api", "API");
  else mostrarTela("inicio");
}

async function iniciar() {
  try {
    const [resumo, orgaos] = await Promise.all([carregar("api/resumo.json"), carregar("api/orgaos.json")]);
    estado.resumo = resumo;
    // O orgaos.json traz o cabeçalho da API e a lista na chave "orgaos"
    estado.orgaos = orgaos.orgaos;
  } catch (erro) {
    mostrarErro("Não foi possível carregar os dados. Tente de novo mais tarde.");
    return;
  }

  renderizarResumo(estado.resumo);
  $("api-versao").textContent = `Versão atual do contrato: ${estado.resumo.versao}. Dados de ${estado.resumo.data_coleta}, gerados em ${estado.resumo.gerado_em}.`;

  // Filtro de esfera: só as que existem nos dados
  const esferas = [...new Set(estado.orgaos.map((orgao) => orgao.esfera))].sort();
  $("filtro-esfera").append(...esferas.map((esfera) => el("option", { value: esfera }, rotulo(ROTULOS_ESFERA, esfera))));

  for (const id of ["busca-orgao", "filtro-esfera"]) {
    $(id).addEventListener("input", () => { estado.paginaOrgaos = 1; renderizarOrgaos(); });
  }
  for (const id of ["busca-base", "so-problemas"]) {
    $(id).addEventListener("input", () => { estado.paginaBases = 1; renderizarBases(); });
  }
  $("mais-orgaos").addEventListener("click", () => { estado.paginaOrgaos += 1; renderizarOrgaos(); });
  $("mais-bases").addEventListener("click", () => { estado.paginaBases += 1; renderizarBases(); });
  window.addEventListener("hashchange", aoMudarOEndereco);

  renderizarOrgaos();
  aoMudarOEndereco();
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", iniciar);
}

// Para os testes em Node (tests/site/app.test.js); no navegador não existe "module"
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    normalizar, formatarNumero, formatarPercentual, rotulo, lerRota, linkDaBase, explicarStatus, primeiraMaiuscula,
    filtrarOrgaos, filtrarBases, temProblema, ordenar, partesDaRegua, fraseDaResposta, ROTULOS_PERIODICIDADE, EXPLICACOES_STATUS,
  };
}
