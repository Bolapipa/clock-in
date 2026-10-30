// Tipos da API (contrato versão 1, docs/API.md) e funções puras do site.
// Nada aqui toca na tela: tudo é testado em dados.test.ts

export type Esfera = "FEDERAL" | "ESTADUAL" | "MUNICIPAL" | "NAO_CLASSIFICADA" | string;
export type Status = "EM_DIA" | "ATRASADA" | "PARADA" | "FORA_DO_AR" | "NAO_VERIFICAVEL" | string;

export interface Cabecalho {
  versao: number;
  data_coleta: string;
  gerado_em: string;
}

export interface Resumo extends Cabecalho {
  bases: number;
  recursos: number;
  orgaos: number;
  links: {
    total: number;
    testados: number;
    ok: number;
    em_observacao: number;
    quebrados: number;
    percentual_ok: number | null;
    cobertura: number | null;
  };
  bases_fora_do_ar: number;
  bases_sem_link: number;
}

export interface OrgaoResumo {
  nome: string;
  slug: string;
  esfera: Esfera;
  qtd_bases: number;
  links_total: number;
  links_testados: number;
  links_ok: number;
  links_em_observacao: number;
  links_quebrados: number;
  bases_fora_do_ar: number;
  percentual_ok: number | null;
  cobertura_links: number | null;
}

export interface Base {
  id: string;
  slug: string;
  titulo: string | null;
  periodicidade: string;
  links_total: number;
  links_testados: number;
  links_ok: number;
  links_em_observacao: number;
  links_quebrados: number;
  fora_do_ar: boolean;
  status: Status;
  motivo: string | null;
}

export interface Orgao extends Cabecalho, OrgaoResumo {
  bases: Base[];
}

export interface ListaDeOrgaos extends Cabecalho {
  orgaos: OrgaoResumo[];
}

// --- Rótulos em português ---

export const ROTULOS_ESFERA: Record<string, string> = {
  FEDERAL: "Federal", ESTADUAL: "Estadual", MUNICIPAL: "Municipal", NAO_CLASSIFICADA: "Não classificada",
};
export const ROTULOS_STATUS: Record<string, string> = {
  EM_DIA: "Em dia", ATRASADA: "Atrasada", PARADA: "Parada", FORA_DO_AR: "Fora do ar", NAO_VERIFICAVEL: "Não verificável",
};
export const ROTULOS_PERIODICIDADE: Record<string, string> = {
  DIARIA: "Diária", SEMANAL: "Semanal", QUINZENAL: "Quinzenal", MENSAL: "Mensal", TRIMESTRAL: "Trimestral",
  QUADRIMESTRAL: "Quadrimestral", SEMESTRAL: "Semestral", ANUAL: "Anual", NAO_DECLARADA: "Não declarada",
  SOB_DEMANDA: "Sob demanda", OUTRAS: "Outras", SEM_DETALHE: "Sem detalhe",
};

// O que cada status quer dizer, em uma frase (também na página de metodologia)
export const EXPLICACOES_STATUS: Record<string, string> = {
  EM_DIA: "A base mudou dentro do prazo esperado para a periodicidade dela.",
  ATRASADA: "A base passou do prazo esperado sem mudança no conteúdo.",
  PARADA: "A base passou de 3 vezes o prazo esperado sem mudança no conteúdo.",
  FORA_DO_AR: "Todos os links da base estão quebrados.",
  NAO_VERIFICAVEL: "Ainda não dá para dizer: faltam arquivos lidos ou histórico, ou a base não declara periodicidade. "
    + "Isso não quer dizer que a base esteja desatualizada.",
};

// --- Formatação ---

// Texto sem acentos e em minúsculas, para a busca ignorar maiúsculas e acentos
export function normalizar(texto: unknown): string {
  return String(texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function formatarNumero(numero: number | null | undefined): string {
  return numero == null ? "-" : numero.toLocaleString("pt-BR");
}

export function formatarPercentual(percentual: number | null | undefined): string {
  if (percentual == null) return "-";
  return percentual.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "%";
}

// "2026-10-26" vira "26/10/2026"
export function formatarData(data: string): string {
  return data.split("-").reverse().join("/");
}

// "NAO_DECLARADA" vira "Nao declarada" quando não há rótulo pronto
export function rotulo(tabela: Record<string, string>, chave: string | null | undefined): string {
  if (chave && tabela[chave]) return tabela[chave];
  const texto = String(chave ?? "").toLowerCase().replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// Primeira letra maiúscula, sem mexer no resto
export function primeiraMaiuscula(texto: unknown): string {
  const frase = String(texto ?? "");
  return frase.charAt(0).toUpperCase() + frase.slice(1);
}

// A frase que explica o status; vazia para um status que a página não conheça
export function explicarStatus(status: string): string {
  return EXPLICACOES_STATUS[status] ?? "";
}

// --- Endereços das páginas ---

// Página de um órgão (cada órgão vira uma página estática no build)
export function linkDoOrgao(slug: string): string {
  return `/orgaos/${slug}/`;
}

// A base abre num painel lateral da página do órgão, indicado no endereço por ?base=
export function linkDaBase(slugDoOrgao: string, slugDaBase: string): string {
  return `/orgaos/${slugDoOrgao}/?base=${encodeURIComponent(slugDaBase)}`;
}

// O identificador vindo do endereço só é aceito se tiver o formato de um slug; qualquer outra coisa
// (texto estranho ou malicioso) é ignorada
export function slugValido(texto: string | null | undefined): string | null {
  const valor = String(texto ?? "");
  return /^[A-Za-z0-9._~-]{1,200}$/.test(valor) ? valor : null;
}

// --- Busca, filtro e ordem ---

export function filtrarOrgaos(orgaos: OrgaoResumo[], { texto = "", esfera = "" } = {}): OrgaoResumo[] {
  const busca = normalizar(texto).trim();
  return orgaos.filter((orgao) => (!esfera || orgao.esfera === esfera) && (!busca || normalizar(orgao.nome).includes(busca)));
}

// Uma base tem problema se algum link está em observação ou quebrado, ou se está fora do ar
export function temProblema(base: Pick<Base, "fora_do_ar" | "links_quebrados" | "links_em_observacao">): boolean {
  return base.fora_do_ar || base.links_quebrados > 0 || base.links_em_observacao > 0;
}

export function filtrarBases<T extends Pick<Base, "titulo" | "fora_do_ar" | "links_quebrados" | "links_em_observacao">>(
  bases: T[], { texto = "", apenasProblemas = false } = {},
): T[] {
  const busca = normalizar(texto).trim();
  return bases.filter((base) => (!apenasProblemas || temProblema(base)) && (!busca || normalizar(base.titulo).includes(busca)));
}

export type Direcao = "asc" | "desc";

// Ordena sem alterar a lista original; valores nulos ficam sempre no fim; empate desfeito pelo nome
export function ordenar<T extends object>(lista: T[], coluna: string, direcao: Direcao = "desc"): T[] {
  const fator = direcao === "asc" ? 1 : -1;
  const valor = (item: T) => (item as Record<string, unknown>)[coluna];
  const nome = (item: T) => {
    const registro = item as Record<string, unknown>;
    return String(registro.nome ?? registro.titulo ?? "");
  };
  const desempate = (a: T, b: T) => nome(a).localeCompare(nome(b), "pt-BR");
  return [...lista].sort((a, b) => {
    const x = valor(a);
    const y = valor(b);
    if (x == null && y == null) return desempate(a, b);
    if (x == null) return 1;
    if (y == null) return -1;
    const comparacao = typeof x === "string" ? x.localeCompare(String(y), "pt-BR") : Number(x) - Number(y);
    return comparacao * fator || desempate(a, b);
  });
}

// Filtro vindo do mostrador: o estado clicado mostra os órgãos que têm aquele problema, do pior para o melhor.
// "respondendo bem" não filtra nada: só ordena pelos que mais respondem
export function filtrarPorEstado(orgaos: OrgaoResumo[], estado: ChaveDaParte | null): OrgaoResumo[] {
  if (!estado) return orgaos;
  const semTeste = (orgao: OrgaoResumo) => Math.max(0, orgao.links_total - orgao.links_testados);
  if (estado === "ok") return ordenar(orgaos, "percentual_ok", "desc");
  const medida = estado === "quebrados" ? (o: OrgaoResumo) => o.links_quebrados
    : estado === "observacao" ? (o: OrgaoResumo) => o.links_em_observacao
    : semTeste;
  return orgaos.filter((orgao) => medida(orgao) > 0).sort((a, b) => medida(b) - medida(a) || a.nome.localeCompare(b.nome, "pt-BR"));
}

export interface Ordem {
  coluna: string;
  direcao: Direcao;
}

// Formas de ordenar, no formato "coluna|direção"; a primeira de cada lista é a ordem inicial
export const ORDENS_ORGAOS = [
  { valor: "qtd_bases|desc", texto: "Mais bases" },
  { valor: "links_quebrados|desc", texto: "Mais links quebrados" },
  { valor: "links_em_observacao|desc", texto: "Mais links em observação" },
  { valor: "percentual_ok|asc", texto: "Menor porcentagem respondendo bem" },
  { valor: "percentual_ok|desc", texto: "Maior porcentagem respondendo bem" },
  { valor: "nome|asc", texto: "Nome, de A a Z" },
];
export const ORDENS_BASES = [
  { valor: "links_quebrados|desc", texto: "Mais links quebrados" },
  { valor: "links_em_observacao|desc", texto: "Mais links em observação" },
  { valor: "links_total|desc", texto: "Mais links" },
  { valor: "titulo|asc", texto: "Título, de A a Z" },
];

// Lê "coluna|direção"; qualquer coisa fora disso volta para a ordem padrão
export function lerOrdem(valor: string | null | undefined, padrao = "qtd_bases|desc"): Ordem {
  const [coluna, direcao] = String(valor ?? "").split("|");
  if (!coluna || (direcao !== "asc" && direcao !== "desc")) return lerOrdem(padrao, "qtd_bases|desc");
  return { coluna, direcao };
}

// --- Régua de saúde dos links ---

export type ChaveDaParte = "ok" | "observacao" | "quebrados" | "nao_testados";

export interface ParteDaRegua {
  chave: ChaveDaParte;
  rotulo: string;
  descricao: string;
  quantidade: number;
  percentual: number;
}

// As quatro partes: a soma é sempre o total de links; "não deu para testar" é o que sobra
const PARTES_DA_REGUA: Omit<ParteDaRegua, "quantidade" | "percentual">[] = [
  { chave: "ok", rotulo: "respondendo bem", descricao: "O último teste abriu o link." },
  { chave: "observacao", rotulo: "em observação", descricao: "1 ou 2 falhas seguidas. Pode ser só uma instabilidade." },
  { chave: "quebrados", rotulo: "quebrados", descricao: "3 ou mais falhas em dias seguidos." },
  { chave: "nao_testados", rotulo: "não deu para testar", descricao: "Sem resposta, bloqueio contra robôs ou ainda não alcançado pelo teste." },
];

export function partesDaRegua({ total, ok, emObservacao, quebrados }: {
  total?: number | null; ok?: number | null; emObservacao?: number | null; quebrados?: number | null;
}): ParteDaRegua[] {
  const valores: Record<ChaveDaParte, number> = {
    ok: ok ?? 0, observacao: emObservacao ?? 0, quebrados: quebrados ?? 0, nao_testados: 0,
  };
  valores.nao_testados = Math.max(0, (total ?? 0) - valores.ok - valores.observacao - valores.quebrados);
  const soma = Object.values(valores).reduce((a, b) => a + b, 0);
  return PARTES_DA_REGUA.map((parte) => ({
    ...parte, quantidade: valores[parte.chave], percentual: soma > 0 ? (100 * valores[parte.chave]) / soma : 0,
  }));
}

// "nenhum está quebrado", "1 está quebrado", "4.246 estão em observação"
function contarEstados(quantidade: number, singular: string, plural = singular): string {
  if (!quantidade) return `nenhum está ${singular}`;
  return quantidade === 1 ? `1 está ${singular}` : `${formatarNumero(quantidade)} estão ${plural}`;
}

// A resposta do dia, em duas frases, a partir dos totais do Brasil
export function fraseDaResposta({ percentual_ok, em_observacao, quebrados }: {
  percentual_ok: number | null; em_observacao: number; quebrados: number;
}): string {
  if (percentual_ok == null) return "Ainda não há links testados o bastante para dar uma porcentagem.";
  return `${formatarPercentual(percentual_ok)} dos links testados respondem bem. `
    + `${primeiraMaiuscula(contarEstados(em_observacao, "em observação"))} e ${contarEstados(quebrados, "quebrado", "quebrados")}.`;
}
