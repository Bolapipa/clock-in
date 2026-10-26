"""Estado entre execuções: a última versão do detalhe de cada base (Fase 2).

O GitHub Actions começa do zero a cada execução. Em vez de depender de todo
o histórico da Bronze, o motor guarda um arquivo pequeno com o que precisa
para continuar no dia seguinte (decisão 16):

dados/estado/detalhe_atual.parquet  (uma linha por base)
    id                -> id da base
    ultima_alteracao  -> ultimaAlteracaoMetadados da listagem no último sucesso
    payload           -> JSON cru do último detalhe que deu certo (nulo se nunca deu)
    data_coleta       -> data do último sucesso
    coletado_em       -> horário (UTC) do último sucesso
    falhas_seguidas   -> dias seguidos com falha (zera no sucesso)
    ultima_tentativa  -> data da última tentativa, com ou sem sucesso
    ultimo_erro       -> mensagem da última falha

Uso:
    python coletor/estado.py --reconstruir   # recria o estado a partir de toda a Bronze
"""

import argparse
import os
from datetime import date

import duckdb

import portal

# Colunas do estado, na ordem em que são gravadas
COLUNAS = """
    id               VARCHAR,
    ultima_alteracao VARCHAR,
    payload          VARCHAR,
    data_coleta      DATE,
    coletado_em      TIMESTAMP,
    falhas_seguidas  INTEGER,
    ultima_tentativa DATE,
    ultimo_erro      VARCHAR
"""


def pasta_detalhe():
    """Pasta da Bronze do detalhe (calculada na hora, para os testes poderem trocar a raiz)."""
    return portal.RAIZ / "dados" / "bronze" / "catalogo_detalhe"


def arquivo_estado():
    """Arquivo do estado do detalhe."""
    return portal.RAIZ / "dados" / "estado" / "detalhe_atual.parquet"


def carregar(con):
    """Cria a tabela 'estado' na conexão: do arquivo, ou vazia na primeira vez."""
    arquivo = arquivo_estado()
    if arquivo.exists():
        con.execute(f"CREATE OR REPLACE TABLE estado AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE estado ({COLUNAS})")


def aplicar_dia(con, data):
    """Junta à tabela 'estado' as tentativas gravadas na Bronze no dia 'data'.

    Pode ser chamada mais de uma vez no mesmo dia sem contar a falha em dobro.
    """
    partes = sorted((pasta_detalhe() / f"data={data}").glob("parte-*.parquet"))
    if not partes:
        return

    lista = [parte.as_posix() for parte in partes]
    con.execute(f"CREATE OR REPLACE TEMP VIEW tentativas AS SELECT * FROM read_parquet({lista})")
    con.execute("""
        CREATE OR REPLACE TABLE estado AS
        WITH
        -- Bases que deram certo hoje: vale a tentativa mais recente que deu certo
        sucesso AS (
            SELECT
                id,
                arg_max(ultima_alteracao, coletado_em) AS ultima_alteracao,
                arg_max(payload, coletado_em)          AS payload,
                max(coletado_em)                        AS coletado_em
            FROM tentativas
            WHERE status_http = 200
            GROUP BY id
        ),
        -- Bases que só falharam hoje: guarda a última mensagem de erro
        falha AS (
            SELECT
                t.id,
                arg_max(COALESCE(t.erro, 'HTTP ' || t.status_http), t.coletado_em) AS erro
            FROM tentativas t
            WHERE NOT EXISTS (SELECT 1 FROM sucesso s WHERE s.id = t.id)
            GROUP BY t.id
        )
        -- 1) Bases sem tentativa hoje: continuam como estavam
        SELECT e.*
        FROM estado e
        WHERE NOT EXISTS (SELECT 1 FROM tentativas t WHERE t.id = e.id)

        UNION ALL
        -- 2) Sucesso hoje: nova versão, contador de falhas zerado
        SELECT
            s.id, s.ultima_alteracao, s.payload,
            CAST($data AS DATE), s.coletado_em,
            0, CAST($data AS DATE), NULL
        FROM sucesso s

        UNION ALL
        -- 3) Falha hoje: mantém a última versão boa e soma uma falha
        --    (só uma vez por dia, mesmo se esta função rodar de novo)
        SELECT
            f.id, e.ultima_alteracao, e.payload,
            e.data_coleta, e.coletado_em,
            CASE
                WHEN e.ultima_tentativa = CAST($data AS DATE) THEN e.falhas_seguidas
                ELSE COALESCE(e.falhas_seguidas, 0) + 1
            END,
            CAST($data AS DATE), f.erro
        FROM falha f
        LEFT JOIN estado e USING (id)
    """, {"data": data})


def salvar(con):
    """Grava a tabela 'estado' no arquivo, sem deixar um arquivo pela metade."""
    arquivo = arquivo_estado()
    arquivo.parent.mkdir(parents=True, exist_ok=True)

    # Grava num arquivo temporário e só depois troca: se cair no meio, o estado antigo continua inteiro
    temporario = arquivo.with_suffix(".tmp")
    con.execute(f"COPY (SELECT * FROM estado ORDER BY id) TO '{temporario.as_posix()}' (FORMAT parquet)")
    os.replace(temporario, arquivo)


def atualizar(data):
    """Atualiza o estado com as tentativas de um dia."""
    con = duckdb.connect()
    carregar(con)
    aplicar_dia(con, data)
    salvar(con)
    con.close()


def reconstruir():
    """Recria o estado do zero, aplicando todos os dias da Bronze em ordem."""
    datas = sorted(
        date.fromisoformat(pasta.name.removeprefix("data="))
        for pasta in pasta_detalhe().glob("data=*")
    )
    con = duckdb.connect()
    con.execute(f"CREATE OR REPLACE TABLE estado ({COLUNAS})")
    for data in datas:
        aplicar_dia(con, data)
    salvar(con)
    bases, com_sucesso = con.execute("SELECT COUNT(*), COUNT(payload) FROM estado").fetchall()[0]
    con.close()
    return len(datas), bases, com_sucesso


def main():
    parser = argparse.ArgumentParser(description="Estado do detalhe entre execuções")
    parser.add_argument("--reconstruir", action="store_true", help="recria o estado a partir de toda a Bronze")
    args = parser.parse_args()

    if args.reconstruir:
        dias, bases, com_sucesso = reconstruir()
        print(f"Estado reconstruído com {dias} dia(s): {bases} bases, {com_sucesso} com detalhe")
        print(f"Gravado em: {arquivo_estado()}")
    else:
        parser.print_help()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()