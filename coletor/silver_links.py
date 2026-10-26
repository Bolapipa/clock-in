"""Gera a Silver da saúde dos links (Fase 2).

Roda depois de silver.py e de links.py. Junta o estado dos links com os recursos
e grava, uma partição por data:
dados/silver/link_status/data=AAAA-MM-DD/link_status.parquet
dados/silver/base_saude/data=AAAA-MM-DD/base_saude.parquet

Uso:
    python coletor/silver_links.py                    # usa a Silver de hoje
    python coletor/silver_links.py --data 2026-10-25  # usa a Silver de outro dia
"""

import argparse
import sys
from datetime import date

import duckdb

import links
import portal
import silver

# Tabelas geradas, na ordem: nome da tabela -> arquivo SQL
# (base_saude usa link_status, por isso vem depois)
TABELAS = {
    "link_status": "silver_link_status.sql",
    "base_saude": "silver_base_saude.sql",
}


def criar_views_entrada(con, data):
    """Cria as views silver_base, silver_recurso e link_atual, usadas pelos arquivos SQL."""
    # Tabelas da Silver já geradas por silver.py no dia
    for nome in ("base", "recurso"):
        arquivo = silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"
        if not arquivo.exists():
            sys.exit(f"Silver {nome} de {data} não encontrada. Rode antes: python coletor/silver.py --data {data}")
        con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Estado dos links, mantido por links.py
    arquivo_estado = links.arquivo_estado()
    if not arquivo_estado.exists():
        sys.exit("Estado dos links não encontrado. Rode antes: python coletor/links.py")
    con.execute(f"CREATE OR REPLACE VIEW link_atual AS SELECT * FROM read_parquet('{arquivo_estado.as_posix()}')")

    # Regra da decisão 14, lida pelos arquivos SQL
    con.execute(f"SET VARIABLE falhas_para_quebrado = {links.FALHAS_PARA_QUEBRADO}")


def main():
    parser = argparse.ArgumentParser(description="Gera a Silver da saúde dos links")
    parser.add_argument("--data", type=date.fromisoformat, help="data da Silver a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)

    for nome, arquivo_sql in TABELAS.items():
        arquivo, linhas = silver.gerar_tabela(con, nome, arquivo_sql, data)
        print(f"silver/{nome}: {linhas} linhas -> {arquivo}")

    # Resumo: links quebrados e bases fora do ar
    testados, quebrados = con.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE quebrado) FROM silver_link_status"
    ).fetchall()[0]
    bases, fora_do_ar = con.execute(
        "SELECT COUNT(*) FILTER (WHERE qtd_links > 0), COUNT(*) FILTER (WHERE fora_do_ar) FROM silver_base_saude"
    ).fetchall()[0]
    print(f"\nLinks testados: {testados}; quebrados: {quebrados}")
    print(f"Bases com links: {bases}; fora do ar: {fora_do_ar}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()