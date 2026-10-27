// Clock-in: página inicial e página de cada órgão (protótipo).
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

// Colunas da tabela de órgãos: chave do JSON, título e se o texto vai à esquerda
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

// Lê "#orgao=slug" do endereço da página; devolve o slug ou null
function lerHash(hash) {
  const achado = /^#orgao=([a-z0-9-]+)$/.exec(hash ?? "");
  return achado ? achado[1] : null;
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

function renderizarResumo(resumo) {
  const links = resumo.links;
  $("data-coleta").textContent = `Dados de ${resumo.data_coleta.split("-").reverse().join("/")}`;
  $("cartoes").replaceChildren(
    cartao("Bases monitoradas", formatarNumero(resumo.bases), `${formatarNumero(resumo.recursos)} arquivos e links`),
    cartao("Órgãos publicadores", formatarNumero(resumo.orgaos), "órgãos e entidades"),
    cartao("Links testados", formatarNumero(links.testados), `de ${formatarNumero(links.total)} (cobertura de ${formatarPercentual(links.cobertura)})`),
    cartao("Respondendo bem", formatarPercentual(links.percentual_ok), `${formatarNumero(links.ok)} links`, "bom"),
    cartao("Em observação", formatarNumero(links.em_observacao), "1 ou 2 falhas seguidas", "atencao"),
    cartao("Quebrados", formatarNumero(links.quebrados), "3 ou mais falhas seguidas", "ruim"),
    cartao("Bases fora do ar", formatarNumero(resumo.bases_fora_do_ar), "todos os links quebrados", "ruim"));
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

function barraDePercentual(percentual) {
  const barra = el("span", { classe: "barra", "aria-hidden": "true" }, el("i"));
  barra.firstChild.style.width = `${percentual ?? 0}%`;
  return barra;
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
        formatarPercentual(orgao.percentual_ok), barraDePercentual(orgao.percentual_ok)),
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
      el("td", {}, el("a", { href: URL_BASE_DO_PORTAL + base.slug, rel: "noopener" }, base.titulo || base.slug)),
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

async function abrirOrgao(slug) {
  try {
    estado.orgao = await carregar(`api/orgaos/${slug}.json`);
  } catch (erro) {
    mostrarErro("Não foi possível carregar este órgão.");
    return;
  }
  const orgao = estado.orgao;
  estado.ordemBases = { coluna: "links_quebrados", direcao: "desc" };
  estado.paginaBases = 1;
  $("busca-base").value = "";
  $("so-problemas").checked = false;

  document.title = `${orgao.nome} · Clock-in`;
  $("orgao-nome").textContent = orgao.nome;
  $("orgao-meta").textContent = `Esfera ${rotulo(ROTULOS_ESFERA, orgao.esfera).toLowerCase()} · ${formatarNumero(orgao.qtd_bases)} bases`;
  $("orgao-cartoes").replaceChildren(
    cartao("Links testados", formatarNumero(orgao.links_testados), `de ${formatarNumero(orgao.links_total)} (cobertura de ${formatarPercentual(orgao.cobertura_links)})`),
    cartao("Respondendo bem", formatarPercentual(orgao.percentual_ok), `${formatarNumero(orgao.links_ok)} links`, "bom"),
    cartao("Em observação", formatarNumero(orgao.links_em_observacao), "1 ou 2 falhas seguidas", "atencao"),
    cartao("Quebrados", formatarNumero(orgao.links_quebrados), "3 ou mais falhas seguidas", "ruim"),
    cartao("Bases fora do ar", formatarNumero(orgao.bases_fora_do_ar), "todos os links quebrados", "ruim"));

  $("inicio").hidden = true;
  $("detalhe").hidden = false;
  renderizarBases();
  window.scrollTo(0, 0);
}

function mostrarInicio() {
  document.title = "Clock-in · Monitor de dados abertos do Brasil";
  $("detalhe").hidden = true;
  $("inicio").hidden = false;
}

function aoMudarOEndereco() {
  const slug = lerHash(window.location.hash);
  if (slug) abrirOrgao(slug);
  else mostrarInicio();
}

async function iniciar() {
  try {
    [estado.resumo, estado.orgaos] = await Promise.all([carregar("api/resumo.json"), carregar("api/orgaos.json")]);
  } catch (erro) {
    mostrarErro("Não foi possível carregar os dados. Tente de novo mais tarde.");
    return;
  }

  renderizarResumo(estado.resumo);

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
    normalizar, formatarNumero, formatarPercentual, rotulo, lerHash, filtrarOrgaos, filtrarBases, temProblema, ordenar,
    ROTULOS_PERIODICIDADE,
  };
}
