// Testes da geometria do mostrador e das faixas de cor do mapa
import { describe, expect, test } from "vitest";

import { faixaDoPercentual } from "./cores";
import { partesDaRegua } from "./dados";
import { arcos, distribuirPontos, estadoNoAngulo, posicoes, voltaDoPonto } from "./mostrador";

// Números reais do dia 29/10/2026
const PARTES = partesDaRegua({ total: 125342, ok: 85699, emObservacao: 2921, quebrados: 3586 });

describe("distribuirPontos", () => {
  test("soma exatamente o total pedido e respeita as proporções", () => {
    const contagem = distribuirPontos(PARTES, 6000);
    expect(Object.values(contagem).reduce((a, b) => a + b, 0)).toBe(6000);
    // 68,4% respondendo bem, com tolerância do mínimo reservado
    expect(contagem.ok / 6000).toBeGreaterThan(0.66);
    expect(contagem.ok / 6000).toBeLessThan(0.7);
  });

  test("um estado pequeno nunca some, e um estado vazio não recebe pontos", () => {
    const partes = partesDaRegua({ total: 100000, ok: 99990, emObservacao: 10, quebrados: 0 });
    const contagem = distribuirPontos(partes, 1000, 8);
    expect(contagem.observacao).toBeGreaterThanOrEqual(8);
    expect(contagem.quebrados).toBe(0);
  });

  test("sem links ou sem pontos devolve tudo zerado", () => {
    expect(Object.values(distribuirPontos(partesDaRegua({ total: 0 }), 500))).toEqual([0, 0, 0, 0]);
    expect(Object.values(distribuirPontos(PARTES, 0))).toEqual([0, 0, 0, 0]);
  });
});

describe("arcos e ângulos", () => {
  test("os arcos cobrem a volta inteira, na ordem dos estados, a partir das 12 horas", () => {
    const lista = arcos(distribuirPontos(PARTES, 4000));
    expect(lista.map((a) => a.chave)).toEqual(["ok", "observacao", "quebrados", "nao_testados"]);
    expect(lista[0].inicio).toBe(0);
    expect(lista.at(-1)?.fim).toBeCloseTo(1, 10);
  });

  test("voltaDoPonto: 12 horas é 0, 3 horas é 1/4, 6 horas é 1/2 e 9 horas é 3/4", () => {
    expect(voltaDoPonto(0, -1)).toBeCloseTo(0);
    expect(voltaDoPonto(1, 0)).toBeCloseTo(0.25);
    expect(voltaDoPonto(0, 1)).toBeCloseTo(0.5);
    expect(voltaDoPonto(-1, 0)).toBeCloseTo(0.75);
  });

  test("estadoNoAngulo acha o estado do arco apontado", () => {
    const lista = arcos(distribuirPontos(PARTES, 4000));
    expect(estadoNoAngulo(0.1, lista)).toBe("ok");
    expect(estadoNoAngulo(0.99, lista)).toBe("nao_testados");
    expect(estadoNoAngulo(1.1, lista)).toBe("ok");
  });
});

describe("posicoes", () => {
  test("cada ponto fica na coroa e dentro do arco do seu estado", () => {
    const contagem = distribuirPontos(PARTES, 3000);
    const lista = arcos(contagem);
    const dados = posicoes(contagem, 0.5);
    expect(dados.length).toBe(3000 * 4);
    const ordem = ["ok", "observacao", "quebrados", "nao_testados"];
    for (let i = 0; i < 3000; i += 1) {
      const [x, y, estado] = [dados[i * 4], dados[i * 4 + 1], dados[i * 4 + 2]];
      const raio = Math.hypot(x, y);
      expect(raio).toBeGreaterThanOrEqual(0.5 - 1e-6);
      expect(raio).toBeLessThanOrEqual(1 + 1e-6);
      expect(estadoNoAngulo(voltaDoPonto(x, y), lista)).toBe(ordem[estado]);
    }
  });

  test("a mesma semente gera o mesmo mostrador", () => {
    const contagem = distribuirPontos(PARTES, 500);
    expect(Array.from(posicoes(contagem))).toEqual(Array.from(posicoes(contagem)));
  });
});

describe("faixas de cor do mapa", () => {
  test("cada porcentagem cai na faixa certa, inclusive nas bordas", () => {
    expect(faixaDoPercentual(100)).toBe("otima");
    expect(faixaDoPercentual(98)).toBe("otima");
    expect(faixaDoPercentual(97.9)).toBe("boa");
    expect(faixaDoPercentual(90)).toBe("boa");
    expect(faixaDoPercentual(75)).toBe("atencao");
    expect(faixaDoPercentual(50)).toBe("ruim");
    expect(faixaDoPercentual(49.9)).toBe("critica");
    expect(faixaDoPercentual(0)).toBe("critica");
  });

  test("órgão sem porcentagem (poucos links testados) tem faixa própria", () => {
    expect(faixaDoPercentual(null)).toBe("sem_percentual");
    expect(faixaDoPercentual(undefined)).toBe("sem_percentual");
  });
});
