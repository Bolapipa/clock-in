"""Gera o status de cada base (Fase 4).

Roda depois de silver.py, silver_links.py e, quando houver, dos downloads de conteúdo.
Aplica as regras de status (prazo esperado pela periodicidade declarada) e grava,
uma partição por data:
dados/gold/fato_status_base_diario/data=AAAA-MM-DD/fato_status_base_diario.parquet

Status: EM_DIA, ATRASADA, PARADA, FORA_DO_AR ou NAO_VERIFICAVEL, cada um com o motivo em uma frase.
Sem nenhum conteúdo lido ainda, as bases ficam NAO_VERIFICAVEL (ou FORA_DO_AR).

Uso:
    python coletor/gold_status.py                    # usa a Silver de hoje
    python coletor/gold_status.py --data 2026-10-25  # usa a Silver de outro dia
"""

import argparse
import sys
from datetime import date

import duckdb

import conteudo_estado
import portal
import silver

# Pasta de saída (Gold)
PASTA_GOLD = portal.RAIZ / "dados" / "gold"

# Nome da tabela e do arquivo SQL que a gera
TABELA = "fato_status_base_diario"
ARQUIVO_SQL = "gold_status_base.sql"

# Prazo esperado de cada periodicidade, mantido à mão
ARQUIVO_PRAZOS = silver.PASTA_REFERENCIA / "periodicidade.csv"

# Quantas vezes o prazo sem mudança faz a base ser "parada" (regras de status da ARQUITETURA)
MULTIPLO_PARADA = 3


def criar_views_entrada(con, data):
    """Cria as views e variáveis usadas por sql/gold_status_base.sql."""
    # Silver do dia: bases, recursos e saúde dos links
    for nome in ("base", "recurso", "base_saude"):
        arquivo = silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"
        if not arquivo.exists():
            sys.exit(f"Silver {nome} de {data} não encontrada. Rode antes silver.py e silver_links.py com --data {data}")
        con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Estado do conteúdo: sem nenhuma leitura ainda, vale uma tabela vazia (todas as bases ficam sem conteúdo)
    arquivo_estado = conteudo_estado.arquivo_estado()
    if arquivo_estado.exists():
        con.execute(f"CREATE OR REPLACE VIEW conteudo_atual AS SELECT * FROM read_parquet('{arquivo_estado.as_posix()}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE conteudo_atual ({conteudo_estado.COLUNAS_ESTADO})")

    # Tabela de prazos mantida à mão no repositório
    con.execute(f"""
        CREATE OR REPLACE VIEW ref_periodicidade AS
        SELECT periodicidade, rotulo, CAST(prazo_dias AS INTEGER) AS prazo_dias
        FROM read_csv('{ARQUIVO_PRAZOS.as_posix()}', delim = ';', header = true, all_varchar = true)
    """)

    # Variáveis lidas pelo SQL
    con.execute(f"SET VARIABLE data_coleta = DATE '{data}'")
    con.execute(f"SET VARIABLE multiplo_parada = {MULTIPLO_PARADA}")


def gerar_tabela(con, data):
    """Roda o SQL de status e grava o resultado na partição do dia."""
    consulta = (silver.PASTA_SQL / ARQUIVO_SQL).read_text(encoding="utf-8")

    pasta = PASTA_GOLD / TABELA / f"data={data}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{TABELA}.parquet"

    # O SQL fica entre quebras de linha para um comentário "--" no fim não engolir o ")"
    con.execute(f"COPY (\n{consulta}\n) TO '{arquivo.as_posix()}' (FORMAT parquet)")
    linhas = con.execute(f"SELECT COUNT(*) FROM '{arquivo.as_posix()}'").fetchall()[0][0]
    return arquivo, linhas


def main():
    parser = argparse.ArgumentParser(description="Gera o status de cada base")
    parser.add_argument("--data", type=date.fromisoformat, help="data da Silver a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)
    arquivo, linhas = gerar_tabela(con, data)
    print(f"gold/{TABELA}: {linhas} linhas -> {arquivo}")

    # Resumo: quantas bases em cada status e quantas divergem do portal
    print("\nBases por status:")
    for status, quantas in con.execute(f"""
        SELECT status, COUNT(*) FROM '{arquivo.as_posix()}' GROUP BY 1 ORDER BY 2 DESC
    """).fetchall():
        print(f"  {status}: {quantas}")
    divergem = con.execute(f"SELECT COUNT(*) FILTER (WHERE diverge_do_portal) FROM '{arquivo.as_posix()}'").fetchall()[0][0]
    print(f"\nDivergem do selo do portal: {divergem}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
