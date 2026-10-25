"""Gera a camada Silver a partir da Bronze (Fase 1, tarefa 4).

Roda os arquivos SQL da pasta sql/ com o DuckDB e grava o resultado
em Parquet, uma partição por data:
dados/silver/base/data=AAAA-MM-DD/base.parquet
dados/silver/recurso/data=AAAA-MM-DD/recurso.parquet

Uso:
    python coletor/silver.py                    # usa a listagem de hoje
    python coletor/silver.py --data 2026-10-25  # usa a listagem de outro dia
"""

import argparse
import sys
from datetime import date

import duckdb

import portal

# Pastas de entrada (Bronze), de saída (Silver) e dos arquivos SQL
PASTA_BRONZE = portal.RAIZ / "dados" / "bronze"
PASTA_SILVER = portal.RAIZ / "dados" / "silver"
PASTA_SQL = portal.RAIZ / "sql"

# Tabelas da Silver: nome da tabela -> arquivo SQL que a gera
TABELAS = {
    "base": "silver_base.sql",
    "recurso": "silver_recurso.sql",
}


def criar_views_bronze(con, data):
    """Cria as views bronze_lista e bronze_detalhe, usadas pelos arquivos SQL."""
    arquivo_lista = PASTA_BRONZE / "catalogo_lista" / f"data={data}" / "catalogo_lista.parquet"
    if not arquivo_lista.exists():
        sys.exit(f"Listagem de {data} não encontrada em {arquivo_lista}")

    # Listagem: só a do dia escolhido
    con.execute(f"CREATE VIEW bronze_lista AS SELECT * FROM read_parquet('{arquivo_lista.as_posix()}')")

    # Detalhe: tudo o que foi coletado até o dia escolhido
    arquivos_detalhe = sorted((PASTA_BRONZE / "catalogo_detalhe").glob("data=*/*.parquet"))
    if not arquivos_detalhe:
        sys.exit("Nenhum detalhe coletado. Rode antes: python coletor/catalogo_detalhe.py")
    lista = [arquivo.as_posix() for arquivo in arquivos_detalhe]
    con.execute(f"""
        CREATE VIEW bronze_detalhe AS
        SELECT * FROM read_parquet({lista})
        WHERE data_coleta <= DATE '{data}'
    """)


def gerar_tabela(con, nome, arquivo_sql, data):
    """Roda um arquivo SQL e grava o resultado na partição do dia."""
    consulta = (PASTA_SQL / arquivo_sql).read_text(encoding="utf-8")

    pasta = PASTA_SILVER / nome / f"data={data}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{nome}.parquet"

    # Grava o resultado; se o arquivo do dia já existir, é substituído
    con.execute(f"COPY ({consulta}) TO '{arquivo.as_posix()}' (FORMAT parquet)")
    linhas = con.execute(f"SELECT COUNT(*) FROM '{arquivo.as_posix()}'").fetchall()[0][0]
    return arquivo, linhas


def main():
    parser = argparse.ArgumentParser(description="Gera a camada Silver a partir da Bronze")
    parser.add_argument("--data", type=date.fromisoformat, help="data da listagem a usar (AAAA-MM-DD); padrão: hoje")
    args = parser.parse_args()
    data = args.data or date.today()

    con = duckdb.connect()
    criar_views_bronze(con, data)

    for nome, arquivo_sql in TABELAS.items():
        arquivo, linhas = gerar_tabela(con, nome, arquivo_sql, data)
        print(f"silver/{nome}: {linhas} linhas -> {arquivo}")

    # Resumo: quantas bases já têm detalhe
    resumo = con.execute(f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE tem_detalhe)
        FROM '{(PASTA_SILVER / "base" / f"data={data}" / "base.parquet").as_posix()}'
    """).fetchall()[0]
    print(f"\nBases: {resumo[0]}; com detalhe: {resumo[1]}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
