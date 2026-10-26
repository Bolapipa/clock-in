"""Gera a camada Silver a partir da Bronze (Fase 1, tarefas 4 e 5).

Roda os arquivos SQL da pasta sql/ com o DuckDB e grava o resultado
em Parquet, uma partição por data:
dados/silver/base/data=AAAA-MM-DD/base.parquet
dados/silver/recurso/data=AAAA-MM-DD/recurso.parquet
dados/silver/publicador/data=AAAA-MM-DD/publicador.parquet

Uso:
    python coletor/silver.py                    # usa a listagem de hoje
    python coletor/silver.py --data 2026-10-25  # usa a listagem de outro dia
"""

import argparse
import sys
from datetime import date

import duckdb

import portal

# Pastas de entrada (Bronze), de saída (Silver), dos arquivos SQL e das tabelas de referência
PASTA_BRONZE = portal.RAIZ / "dados" / "bronze"
PASTA_SILVER = portal.RAIZ / "dados" / "silver"
PASTA_SQL = portal.RAIZ / "sql"
PASTA_REFERENCIA = portal.RAIZ / "referencia"

# Tabelas da Silver, na ordem em que são geradas: nome da tabela -> arquivo SQL
# (publicador usa base e recurso, por isso vem por último)
TABELAS = {
    "base": "silver_base.sql",
    "recurso": "silver_recurso.sql",
    "publicador": "silver_publicador.sql",
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


def criar_views_referencia(con, data):
    """Cria as views painel_cronograma e ref_dominios, usadas pelo SQL do publicador."""
    # Cronograma da CGU: a coleta mais recente até o dia escolhido (o painel muda uma vez por mês)
    pastas = sorted((PASTA_BRONZE / "painel_cgu_cronograma").glob("data=*"))
    pastas = [pasta for pasta in pastas if pasta.name.removeprefix("data=") <= str(data)]
    if not pastas:
        sys.exit("Cronograma da CGU não encontrado. Rode antes: python coletor/painel_cgu.py")
    arquivo = pastas[-1] / "painel_cgu_cronograma.parquet"
    con.execute(f"CREATE VIEW painel_cronograma AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Tabela de referência mantida à mão no repositório
    arquivo = PASTA_REFERENCIA / "dominios.csv"
    con.execute(f"""
        CREATE VIEW ref_dominios AS
        SELECT * FROM read_csv('{arquivo.as_posix()}', delim = ';', header = true, all_varchar = true)
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

    # Deixa a tabela gerada disponível para os próximos SQLs (ex.: silver_base)
    con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")
    return arquivo, linhas


def main():
    parser = argparse.ArgumentParser(description="Gera a camada Silver a partir da Bronze")
    parser.add_argument("--data", type=date.fromisoformat, help="data da listagem a usar (AAAA-MM-DD); padrão: hoje")
    args = parser.parse_args()
    data = args.data or date.today()

    con = duckdb.connect()
    criar_views_bronze(con, data)
    criar_views_referencia(con, data)

    for nome, arquivo_sql in TABELAS.items():
        arquivo, linhas = gerar_tabela(con, nome, arquivo_sql, data)
        print(f"silver/{nome}: {linhas} linhas -> {arquivo}")

    # Resumo: quantas bases já têm detalhe e de onde veio o publicador
    resumo = con.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE tem_detalhe) FROM silver_base").fetchall()[0]
    print(f"\nBases: {resumo[0]}; com detalhe: {resumo[1]}")
    for origem, bases in con.execute("""
        SELECT origem_publicador, COUNT(*) FROM silver_publicador GROUP BY 1 ORDER BY 2 DESC
    """).fetchall():
        print(f"  publicador via {origem}: {bases}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()