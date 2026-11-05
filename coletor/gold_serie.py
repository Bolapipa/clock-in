"""Grava a série diária da Gold (Fase 5): a nota de cada órgão e os totais do Brasil, dia a dia.

Roda depois de gold_status.py. Grava, uma partição por data:
dados/gold/fato_nota_orgao_diario/data=AAAA-MM-DD/fato_nota_orgao_diario.parquet
    data, orgao, esfera, bases_total, bases_verificaveis, em_dia, atrasada, parada, fora_do_ar,
    nao_verificavel, nota, cobertura, entra_ranking
dados/gold/fato_brasil_diario/data=AAAA-MM-DD/fato_brasil_diario.parquet
    data, bases, orgaos, orgaos_no_ranking, em_dia, atrasada, parada, fora_do_ar, nao_verificavel,
    links_total, links_testados, links_ok, links_em_observacao, links_quebrados

O pipeline só enxerga o dia de hoje e o estado, então dois arquivos de estado guardam a série inteira
(a evolução só existe a partir do primeiro dia gravado, por isso este passo roda todo dia):
    dados/estado/nota_orgao_historico.parquet   uma linha por órgão por dia
    dados/estado/brasil_historico.parquet       uma linha por dia

A nota usa a mesma fórmula da API (coletor/nota.py). Rodar o mesmo dia duas vezes dá o mesmo resultado:
só as linhas daquele dia são regravadas. Sem o status do dia (a Gold de status não foi gerada), nada é
gravado, porque uma linha cheia de "não verificável" seria um dia falso na série.

Uso:
    python coletor/gold_serie.py                    # usa a Silver e o status de hoje
    python coletor/gold_serie.py --data 2026-10-25  # usa os de outro dia
"""

import argparse
import os
import sys
from datetime import date

import duckdb

import gold_status
import portal
import silver
from nota import calcular_nota

# Nomes das tabelas e dos arquivos SQL que contam as bases
TABELA_NOTA = "fato_nota_orgao_diario"
TABELA_BRASIL = "fato_brasil_diario"
SQL_ORGAO = "gold_serie_orgao.sql"
SQL_BRASIL = "gold_serie_brasil.sql"

# Os status que a nota conhece, na ordem das colunas de contagem
STATUS = ("EM_DIA", "ATRASADA", "PARADA", "FORA_DO_AR", "NAO_VERIFICAVEL")

COLUNAS_NOTA = ("data DATE, orgao VARCHAR, esfera VARCHAR, bases_total BIGINT, bases_verificaveis BIGINT, em_dia BIGINT, "
                "atrasada BIGINT, parada BIGINT, fora_do_ar BIGINT, nao_verificavel BIGINT, nota DOUBLE, cobertura DOUBLE, "
                "entra_ranking BOOLEAN")
COLUNAS_BRASIL = ("data DATE, bases BIGINT, orgaos BIGINT, orgaos_no_ranking BIGINT, em_dia BIGINT, atrasada BIGINT, "
                  "parada BIGINT, fora_do_ar BIGINT, nao_verificavel BIGINT, links_total BIGINT, links_testados BIGINT, "
                  "links_ok BIGINT, links_em_observacao BIGINT, links_quebrados BIGINT")


def arquivo_nota_historico():
    """Arquivo do estado com a nota de cada órgão em cada dia (calculado na hora, para os testes trocarem a raiz)."""
    return portal.RAIZ / "dados" / "estado" / "nota_orgao_historico.parquet"


def arquivo_brasil_historico():
    """Arquivo do estado com os totais do Brasil em cada dia."""
    return portal.RAIZ / "dados" / "estado" / "brasil_historico.parquet"


def arquivo_do_dia(tabela, data):
    """Onde a partição de um dia de uma tabela Gold fica."""
    return gold_status.PASTA_GOLD / tabela / f"data={data}" / f"{tabela}.parquet"


def gravar_atomico(con, consulta, destino):
    """Grava o resultado de uma consulta em Parquet sem deixar um arquivo pela metade."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    con.execute(f"COPY ({consulta}) TO '{temporario.as_posix()}' (FORMAT parquet)")
    os.replace(temporario, destino)


def gravar_linhas(con, colunas, linhas, destino):
    """Grava linhas (tuplas) numa tabela Parquet com as colunas dadas, sem deixar um arquivo pela metade."""
    con.execute(f"CREATE OR REPLACE TEMP TABLE saida ({colunas})")
    if linhas:
        marcas = ", ".join("?" for _ in linhas[0])
        con.executemany(f"INSERT INTO saida VALUES ({marcas})", linhas)
    gravar_atomico(con, "SELECT * FROM saida", destino)


def criar_views_entrada(con, data):
    """Cria as views silver_base, silver_publicador, silver_base_saude e status_hoje usadas pelos SQL da série."""
    for nome in ("base", "publicador", "base_saude"):
        arquivo = silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"
        if not arquivo.exists():
            sys.exit(f"Silver {nome} de {data} não encontrada. Rode antes silver.py e silver_links.py com --data {data}")
        con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Status do dia (Gold): sem ele não há série para gravar (a main confere)
    status = arquivo_do_dia(gold_status.TABELA, data)
    if status.exists():
        con.execute(f"CREATE OR REPLACE VIEW status_hoje AS SELECT * FROM read_parquet('{status.as_posix()}')")
    else:
        con.execute("CREATE OR REPLACE TABLE status_hoje (id VARCHAR, status VARCHAR, motivo VARCHAR)")


def ler_como_dicionarios(con, arquivo_sql):
    """Roda um SQL da pasta sql/ e devolve as linhas como lista de dicionários."""
    consulta = (silver.PASTA_SQL / arquivo_sql).read_text(encoding="utf-8")
    # O SQL fica entre quebras de linha para um comentário "--" no fim não engolir nada
    resultado = con.execute(f"\n{consulta}\n")
    colunas = [coluna[0] for coluna in resultado.description]
    return [dict(zip(colunas, linha)) for linha in resultado.fetchall()]


def gerar_tabelas(con, data):
    """Grava as duas partições do dia e devolve (arquivo da nota por órgão, arquivo do Brasil)."""
    linhas_orgaos = []
    for orgao in ler_como_dicionarios(con, SQL_ORGAO):
        por_status = {status: orgao[status.lower()] for status in STATUS}
        nota = calcular_nota(por_status, orgao["bases_total"])
        linhas_orgaos.append((
            data, orgao["orgao"], orgao["esfera"], orgao["bases_total"], nota["bases_verificaveis"],
            orgao["em_dia"], orgao["atrasada"], orgao["parada"], orgao["fora_do_ar"], orgao["nao_verificavel"],
            nota["nota"], nota["cobertura"], nota["entra_ranking"],
        ))
    destino_nota = arquivo_do_dia(TABELA_NOTA, data)
    gravar_linhas(con, COLUNAS_NOTA, linhas_orgaos, destino_nota)

    # O Brasil: os totais do SQL mais a quantidade de órgãos, que vem das linhas acima
    brasil = ler_como_dicionarios(con, SQL_BRASIL)[0]
    entram = sum(1 for linha in linhas_orgaos if linha[-1])
    linha_brasil = (
        data, brasil["bases"], len(linhas_orgaos), entram, brasil["em_dia"], brasil["atrasada"], brasil["parada"],
        brasil["fora_do_ar"], brasil["nao_verificavel"], brasil["links_total"], brasil["links_testados"],
        brasil["links_ok"], brasil["links_em_observacao"], brasil["links_quebrados"],
    )
    destino_brasil = arquivo_do_dia(TABELA_BRASIL, data)
    gravar_linhas(con, COLUNAS_BRASIL, [linha_brasil], destino_brasil)
    return destino_nota, destino_brasil


def atualizar_estado(con, data, arquivo_do_dia_gravado, estado, ordem):
    """Põe o dia no estado: as linhas dos outros dias ficam como estavam e as do dia são trocadas."""
    partes = [f"SELECT * FROM read_parquet('{arquivo_do_dia_gravado.as_posix()}')"]
    if estado.exists():
        # Diferente de "dias anteriores": regravar um dia antigo não apaga os dias que vieram depois
        partes.append(f"SELECT * FROM read_parquet('{estado.as_posix()}') WHERE data <> DATE '{data}'")
    gravar_atomico(con, " UNION ALL ".join(partes) + f" ORDER BY {ordem}", estado)


def atualizar_estados(con, data, destino_nota, destino_brasil):
    """Atualiza os dois estados da série, já com o dia de hoje."""
    atualizar_estado(con, data, destino_nota, arquivo_nota_historico(), "data, orgao")
    atualizar_estado(con, data, destino_brasil, arquivo_brasil_historico(), "data")


def main():
    parser = argparse.ArgumentParser(description="Grava a série diária da nota por órgão e dos totais do Brasil")
    parser.add_argument("--data", type=date.fromisoformat, help="data a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)
    if con.execute("SELECT COUNT(*) FROM status_hoje").fetchall()[0][0] == 0:
        sys.exit(f"Status de {data} não encontrado: rode antes gold_status.py com --data {data}. "
                 "A série não foi gravada, para não registrar um dia falso.")

    destino_nota, destino_brasil = gerar_tabelas(con, data)
    atualizar_estados(con, data, destino_nota, destino_brasil)

    brasil = con.execute(f"SELECT * FROM read_parquet('{destino_brasil.as_posix()}')").fetchall()[0]
    print(f"gold/{TABELA_NOTA}: {brasil[2]} órgãos ({brasil[3]} no ranking) -> {destino_nota}")
    print(f"gold/{TABELA_BRASIL}: {brasil[1]} bases -> {destino_brasil}")
    dias = con.execute(f"SELECT COUNT(DISTINCT data) FROM read_parquet('{arquivo_brasil_historico().as_posix()}')").fetchall()[0][0]
    print(f"Série acumulada: {dias} dia(s) no estado")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
