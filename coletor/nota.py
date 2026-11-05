"""Fórmula da nota por órgão (decisão 17), usada pela API e pela série diária da Gold.

Vive num módulo só para a nota publicada na API e a nota gravada na Gold nunca divergirem,
nem no arredondamento (o round do Python e o do SQL arredondam 6,25 de jeitos diferentes).
"""

# Só entram no ranking os órgãos com pelo menos esta quantidade de bases (decisão 17)
MINIMO_BASES_NO_RANKING = 10

# E pelo menos esta quantidade de bases verificáveis: com 1 ou 2 bases lidas, a nota 100 seria sorte de amostra
# e passaria na frente de órgãos grandes e bem medidos (decisão 45)
MINIMO_VERIFICAVEIS_NO_RANKING = 5

# Peso de uma base atrasada na nota: em dia vale 1, atrasada vale metade, parada e fora do ar valem zero
PESO_ATRASADA = 0.5


def percentual(parte, total):
    """Porcentagem com 1 casa decimal; nulo quando não há total."""
    return round(100 * parte / total, 1) if total else None


def calcular_nota(status, qtd_bases):
    """Nota e cobertura de um órgão a partir da quantidade de bases por status (decisão 17).

    nota      = 100 x (em_dia + 0,5 x atrasada) / bases_verificaveis
    cobertura = 100 x bases_verificaveis / bases_total
    "Não verificável" fica fora da nota e aparece na cobertura. Sem nenhuma base verificável, a nota é nula.
    """
    verificaveis = qtd_bases - status.get("NAO_VERIFICAVEL", 0)
    pontos = status.get("EM_DIA", 0) + PESO_ATRASADA * status.get("ATRASADA", 0)
    return {
        "nota": round(100 * pontos / verificaveis, 1) if verificaveis else None,
        "cobertura": percentual(verificaveis, qtd_bases),
        "bases_verificaveis": verificaveis,
        "entra_ranking": qtd_bases >= MINIMO_BASES_NO_RANKING and verificaveis >= MINIMO_VERIFICAVEIS_NO_RANKING,
    }
