"""Gera a Silver do conteúdo dos arquivos (Fase 3).

Roda depois de a leitura dos arquivos atualizar o estado do conteúdo. Grava, uma partição por data:
dados/silver/versao_conteudo/data=AAAA-MM-DD/versao_conteudo.parquet  (arquivos lidos no dia)
dados/silver/mudanca_schema/data=AAAA-MM-DD/mudanca_schema.parquet    (mudanças de estrutura do dia)

Uso:
    python coletor/silver_conteudo.py                    # usa a data de hoje em Brasília
    python coletor/silver_conteudo.py --data 2026-10-26  # outro dia
"""

import argparse
import sys
from datetime import date

import duckdb

import conteudo_estado
import portal
import silver

# Tabelas geradas: nome da tabela -> arquivo SQL
TABELAS = {
    "versao_conteudo": "silver_versao_conteudo.sql",
    "mudanca_schema": "silver_mudanca_schema.sql",
}


def criar_views_entrada(con, data):
    """Cria a view conteudo_atual e a variável data_coleta, usadas pelos arquivos SQL."""
    arquivo_estado = conteudo_estado.arquivo_estado()
    if not arquivo_estado.exists():
        sys.exit("Estado do conteúdo não encontrado. Rode antes a leitura dos arquivos.")
    con.execute(f"CREATE OR REPLACE VIEW conteudo_atual AS SELECT * FROM read_parquet('{arquivo_estado.as_posix()}')")

    # Dia da Silver, lido pelos arquivos SQL
    con.execute(f"SET VARIABLE data_coleta = DATE '{data}'")


def main():
    parser = argparse.ArgumentParser(description="Gera a Silver do conteúdo dos arquivos")
    parser.add_argument("--data", type=date.fromisoformat, help="data da Silver (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)

    for nome, arquivo_sql in TABELAS.items():
        arquivo, linhas = silver.gerar_tabela(con, nome, arquivo_sql, data)
        print(f"silver/{nome}: {linhas} linhas -> {arquivo}")

    # Resumo do dia
    lidos, mudaram, mudaram_schema = con.execute("""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE mudou_conteudo), COUNT(*) FILTER (WHERE mudou_schema)
        FROM silver_versao_conteudo
    """).fetchall()[0]
    print(f"\nArquivos lidos: {lidos}; conteúdo mudou: {mudaram}; estrutura mudou: {mudaram_schema}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()