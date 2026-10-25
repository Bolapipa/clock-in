"""Primeiro teste do DuckDB no Clock-in (Fase 0).

Lê o censo da validação, conta as bases pelo veredito do portal
e grava o resultado em Parquet dentro de dados/teste/.
"""

from pathlib import Path

import duckdb

# Pasta raiz do projeto (a pasta acima de coletor/)
RAIZ = Path(__file__).resolve().parent.parent

# Arquivo de entrada: censo de 24/10/2026
CSV_CENSO = RAIZ / "validacao" / "resultados" / "censo-2026-10-24.csv"

# Arquivo de saída: fica em dados/, que está fora do Git
PARQUET_SAIDA = RAIZ / "dados" / "teste" / "contagem.parquet"


def main():
    # Cria a pasta de saída, se ainda não existir
    PARQUET_SAIDA.parent.mkdir(parents=True, exist_ok=True)

    # Conexão em memória: nada é gravado além do Parquet
    con = duckdb.connect()

    # Conta as bases por veredito do portal (True ou False)
    consulta = f"""
        SELECT
            portal_diz_atualizado,
            COUNT(*) AS bases
        FROM read_csv('{CSV_CENSO.as_posix()}')
        GROUP BY portal_diz_atualizado
        ORDER BY bases
    """

    # Grava o resultado da consulta em Parquet
    con.execute(f"COPY ({consulta}) TO '{PARQUET_SAIDA.as_posix()}' (FORMAT parquet)")

    # Lê o Parquet de volta para provar que a gravação funcionou
    print(f"Parquet gravado em: {PARQUET_SAIDA}")
    con.sql(f"SELECT * FROM '{PARQUET_SAIDA.as_posix()}'").show()

    # Fecha a conexão
    con.close()


# Só executa quando o arquivo é rodado direto (python coletor/teste_duckdb.py)
if __name__ == "__main__":
    main()