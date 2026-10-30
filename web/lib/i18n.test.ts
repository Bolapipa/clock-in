// Testes dos textos em português e inglês: as duas línguas têm as mesmas chaves e as frases montadas fazem sentido
import { describe, expect, test } from "vitest";

import { TEXTOS, dataNaLingua } from "./i18n";

// Todas as chaves de um objeto, em profundidade (funções contam como folhas)
function chaves(objeto: object, prefixo = ""): string[] {
  return Object.entries(objeto).flatMap(([chave, valor]) =>
    valor && typeof valor === "object" && !Array.isArray(valor) ? chaves(valor, `${prefixo}${chave}.`) : [`${prefixo}${chave}`]);
}

describe("dicionário", () => {
  test("português e inglês têm exatamente as mesmas chaves", () => {
    expect(chaves(TEXTOS.en).sort()).toEqual(chaves(TEXTOS.pt).sort());
  });

  test("nenhum texto ficou vazio sem querer (só o aviso de GPU pode ser vazio)", () => {
    for (const lingua of ["pt", "en"] as const) {
      const vazios = chaves(TEXTOS[lingua]).filter((caminho) => {
        const valor = caminho.split(".").reduce<unknown>((atual, parte) => (atual as Record<string, unknown>)[parte], TEXTOS[lingua]);
        return valor === "";
      });
      expect(vazios, lingua).toEqual(["mostrador.semGpu"]);
    }
  });
});

describe("frases montadas", () => {
  const links = { percentual_ok: 92.9, em_observacao: 2921, quebrados: 3586 };

  test("a resposta do dia sai nas duas línguas", () => {
    expect(TEXTOS.pt.resposta(links)).toBe("92,9% dos links testados respondem bem. 2.921 estão em observação e 3.586 estão quebrados.");
    expect(TEXTOS.en.resposta(links)).toContain("of tested links respond well");
    expect(TEXTOS.en.resposta({ percentual_ok: 99, em_observacao: 0, quebrados: 1 })).toContain("None is under watch and 1 is broken");
  });

  test("sem porcentagem, nenhuma língua inventa número", () => {
    expect(TEXTOS.pt.resposta({ percentual_ok: null, em_observacao: 0, quebrados: 0 })).toMatch(/Ainda não há links testados/);
    expect(TEXTOS.en.resposta({ percentual_ok: null, em_observacao: 0, quebrados: 0 })).toMatch(/not enough tested links/);
  });

  test("a data sai no formato de cada língua e uma data inválida volta como veio", () => {
    expect(dataNaLingua("2026-10-29", "pt")).toBe("29/10/2026");
    expect(dataNaLingua("2026-10-29", "en")).toMatch(/Oct\s+29,\s+2026/);
    expect(dataNaLingua("sem-data", "pt")).toBe("sem-data");
  });
});
