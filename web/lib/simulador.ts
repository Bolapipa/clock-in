// Simulador "sete dias na vida de um link": aplica, dia a dia, a mesma regra que o pipeline usa no estado
// dos links (coletor/links.py, aplicar_dia; decisões 14, 29, 31, 36 e 39):
// - resposta boa (abaixo de 400) zera as falhas;
// - falha que conta (404, 500, DNS, SSL...) soma uma falha;
// - resultado inconclusivo (timeout, conexão, 403, 405) e dia sem teste não mudam nada;
// - com 3 falhas seguidas o link é "quebrado"; com 1 ou 2, "em observação".
// As falhas contam testes, não dias do calendário: um dia sem teste não quebra a sequência.

export type Evento = "ok" | "falha" | "inconclusivo" | "sem_teste";
export type Situacao = "sem_resultado" | "respondendo" | "observacao" | "quebrado";

// Por que a situação ficou como ficou naquele dia (a tela traduz o código em uma frase)
export type Motivo =
  | "ainda_sem_resultado"
  | "primeira_resposta"
  | "continua_respondendo"
  | "voltou_a_responder"
  | "primeira_falha"
  | "segunda_falha"
  | "quebrou"
  | "continua_quebrado"
  | "inconclusivo_nada_muda"
  | "sem_teste_nada_muda";

export interface Dia {
  evento: Evento;
  falhas: number;
  situacao: Situacao;
  mudou: boolean;
  motivo: Motivo;
}

export const FALHAS_PARA_QUEBRAR = 3;

// A ordem do botão de cada dia: clicar troca para o próximo evento
export const EVENTOS: Evento[] = ["ok", "falha", "inconclusivo", "sem_teste"];

export function proximoEvento(evento: Evento): Evento {
  return EVENTOS[(EVENTOS.indexOf(evento) + 1) % EVENTOS.length];
}

function situacaoDe(testado: boolean, falhas: number): Situacao {
  if (!testado) return "sem_resultado";
  if (falhas === 0) return "respondendo";
  return falhas >= FALHAS_PARA_QUEBRAR ? "quebrado" : "observacao";
}

export function simular(eventos: Evento[]): Dia[] {
  let testado = false;
  let falhas = 0;
  const dias: Dia[] = [];

  for (const evento of eventos) {
    const antes = situacaoDe(testado, falhas);
    let motivo: Motivo;

    if (evento === "ok") {
      const tinhaFalhas = falhas > 0;
      motivo = !testado ? "primeira_resposta" : tinhaFalhas ? "voltou_a_responder" : "continua_respondendo";
      testado = true;
      falhas = 0;
    } else if (evento === "falha") {
      testado = true;
      falhas += 1;
      motivo = falhas === 1 ? "primeira_falha" : falhas === 2 ? "segunda_falha" : falhas === FALHAS_PARA_QUEBRAR ? "quebrou" : "continua_quebrado";
    } else {
      // Inconclusivo ou sem teste: o link fica exatamente como estava
      motivo = !testado ? "ainda_sem_resultado" : evento === "inconclusivo" ? "inconclusivo_nada_muda" : "sem_teste_nada_muda";
    }

    const situacao = situacaoDe(testado, falhas);
    dias.push({ evento, falhas, situacao, mudou: situacao !== antes, motivo });
  }
  return dias;
}

// Cenários prontos, cada um mostra uma parte da regra
export const CENARIOS = {
  instabilidade: ["ok", "falha", "ok", "ok", "ok", "ok", "ok"],
  removido: ["ok", "ok", "falha", "falha", "falha", "falha", "falha"],
  robos: ["ok", "inconclusivo", "inconclusivo", "inconclusivo", "inconclusivo", "ok", "ok"],
  voltou: ["falha", "falha", "falha", "ok", "ok", "ok", "ok"],
  servidorGrande: ["falha", "sem_teste", "falha", "sem_teste", "falha", "sem_teste", "ok"],
} satisfies Record<string, Evento[]>;

export type Cenario = keyof typeof CENARIOS;
