// Testes do simulador: espelham os testes da regra real em tests/test_links.py, para o site nunca ensinar
// uma regra diferente da que o pipeline aplica
import { describe, expect, test } from "vitest";

import { CENARIOS, EVENTOS, proximoEvento, simular, type Evento } from "./simulador";

const situacoes = (eventos: Evento[]) => simular(eventos).map((dia) => dia.situacao);

describe("regra de quebrado", () => {
  test("três falhas seguidas quebram o link e um sucesso zera (test_tres_falhas_em_dias_seguidos_e_sucesso_zera)", () => {
    expect(situacoes(["falha", "falha", "falha", "ok"])).toEqual(["observacao", "observacao", "quebrado", "respondendo"]);
    expect(simular(["falha", "falha", "falha"]).map((d) => d.falhas)).toEqual([1, 2, 3]);
  });

  test("resultado inconclusivo no meio não zera nem soma (test_dia_inconclusivo_no_meio_nao_zera_nem_soma)", () => {
    const dias = simular(["falha", "inconclusivo", "falha", "falha"]);
    expect(dias.map((d) => d.falhas)).toEqual([1, 1, 2, 3]);
    expect(dias[1].mudou).toBe(false);
    expect(dias[3].situacao).toBe("quebrado");
  });

  test("inconclusivo depois de sucesso mantém o link como estava (test_inconclusivo_depois_de_sucesso_mantem_o_link_como_estava)", () => {
    expect(situacoes(["ok", "inconclusivo", "inconclusivo"])).toEqual(["respondendo", "respondendo", "respondendo"]);
  });

  test("link nunca testado que só deu inconclusivo fica sem resultado (test_link_nunca_testado_com_resultado_inconclusivo_fica_fora_do_estado)", () => {
    expect(situacoes(["inconclusivo", "sem_teste", "inconclusivo"])).toEqual(["sem_resultado", "sem_resultado", "sem_resultado"]);
    expect(simular(["inconclusivo"])[0].motivo).toBe("ainda_sem_resultado");
  });

  test("dia sem teste não quebra a sequência: um servidor grande testado em dias alternados também quebra (decisão 39)", () => {
    const dias = simular(CENARIOS.servidorGrande);
    expect(dias.map((d) => d.situacao)).toEqual(["observacao", "observacao", "observacao", "observacao", "quebrado", "quebrado", "respondendo"]);
    expect(dias[4].motivo).toBe("quebrou");
  });

  test("falhas além da terceira continuam quebrado, sem voltar a contar como novidade", () => {
    const dias = simular(["falha", "falha", "falha", "falha"]);
    expect(dias[3].motivo).toBe("continua_quebrado");
    expect(dias[3].mudou).toBe(false);
  });
});

describe("motivos e mudanças", () => {
  test("cada tipo de dia recebe o motivo certo", () => {
    expect(simular(["ok", "ok", "falha", "falha", "ok", "sem_teste"]).map((d) => d.motivo)).toEqual([
      "primeira_resposta", "continua_respondendo", "primeira_falha", "segunda_falha", "voltou_a_responder", "sem_teste_nada_muda",
    ]);
  });

  test("mudou só é verdadeiro quando a situação muda de fato", () => {
    expect(simular(["ok", "ok", "falha", "falha", "falha", "ok"]).map((d) => d.mudou)).toEqual([true, false, true, false, true, true]);
  });
});

describe("cenários prontos", () => {
  test("cada cenário tem sete dias e mostra o que promete", () => {
    for (const eventos of Object.values(CENARIOS)) expect(eventos).toHaveLength(7);
    expect(situacoes(CENARIOS.instabilidade)).not.toContain("quebrado");
    expect(situacoes(CENARIOS.removido).at(-1)).toBe("quebrado");
    // Bloqueio contra robôs nunca vira falha
    expect(simular(CENARIOS.robos).every((d) => d.falhas === 0)).toBe(true);
    expect(situacoes(CENARIOS.voltou)).toContain("quebrado");
    expect(situacoes(CENARIOS.voltou).at(-1)).toBe("respondendo");
  });

  test("o botão de cada dia percorre os quatro eventos e volta ao começo", () => {
    let evento: Evento = EVENTOS[0];
    const vistos = [];
    for (let i = 0; i < EVENTOS.length; i += 1) {
      vistos.push(evento);
      evento = proximoEvento(evento);
    }
    expect(vistos).toEqual(EVENTOS);
    expect(evento).toBe(EVENTOS[0]);
  });
});
