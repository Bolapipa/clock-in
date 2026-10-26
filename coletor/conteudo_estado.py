"""Estado do conteúdo dos arquivos (Fase 3).

Guarda, para cada link tabular, o que se sabe do conteúdo na última leitura e quando ele mudou.
A Bronze recebe uma linha por download; o estado junta isso ao que já se sabia:

dados/bronze/conteudo_tentativa/data=AAAA-MM-DD/parte-0001.parquet
dados/estado/conteudo_atual.parquet  (uma linha por link)
    link, servidor, ultima_tentativa, ultima_leitura (último download que deu certo),
    hash_conteudo, tamanho_bytes, qtd_colunas, schema, schema_hash, erro_schema,
    verificacao_parcial, schema_anterior (schema antes da última mudança de estrutura),
    ultima_mudanca (dia em que o hash mudou), ultima_mudanca_schema (dia em que a estrutura mudou),
    erro_tipo (erro da última tentativa; nulo se deu certo)

Regras:
- Um download que falha não apaga o que já se sabia: só registra o erro e a data da tentativa.
- A primeira leitura de um link não conta como mudança: não há com o que comparar.
- Aplicar o mesmo dia duas vezes dá o mesmo resultado.
"""

import os
import re

import duckdb

import portal

# Colunas do estado, na ordem em que são gravadas
COLUNAS_ESTADO = """
    link                  VARCHAR,
    servidor              VARCHAR,
    ultima_tentativa      DATE,
    ultima_leitura        DATE,
    hash_conteudo         VARCHAR,
    tamanho_bytes         BIGINT,
    qtd_colunas           INTEGER,
    "schema"              VARCHAR,
    schema_hash           VARCHAR,
    erro_schema           VARCHAR,
    verificacao_parcial   BOOLEAN,
    schema_anterior       VARCHAR,
    ultima_mudanca        DATE,
    ultima_mudanca_schema DATE,
    erro_tipo             VARCHAR
"""

# Colunas da Bronze, na ordem em que são gravadas
COLUNAS_BRONZE = """
    data_coleta         DATE,
    link                VARCHAR,
    servidor            VARCHAR,
    status_http         INTEGER,
    tamanho_bytes       BIGINT,
    hash_conteudo       VARCHAR,
    qtd_colunas         INTEGER,
    "schema"            VARCHAR,
    schema_hash         VARCHAR,
    erro_schema         VARCHAR,
    verificacao_parcial BOOLEAN,
    erro_tipo           VARCHAR,
    tentado_em          TIMESTAMP
"""


def pasta_tentativas():
    """Pasta da Bronze das tentativas (calculada na hora, para os testes poderem trocar a raiz)."""
    return portal.RAIZ / "dados" / "bronze" / "conteudo_tentativa"


def arquivo_estado():
    """Arquivo do estado do conteúdo."""
    return portal.RAIZ / "dados" / "estado" / "conteudo_atual.parquet"


def partes_do_dia(data):
    """Arquivos de tentativas gravados na Bronze no dia."""
    return sorted((pasta_tentativas() / f"data={data}").glob("parte-*.parquet"))


def gravar_lote(linhas, data):
    """Grava um lote de tentativas como uma nova parte na partição do dia."""
    pasta = pasta_tentativas() / f"data={data}"
    pasta.mkdir(parents=True, exist_ok=True)

    # Próximo número: o maior que já existe + 1 (não sobrescreve se faltar uma parte no meio)
    numeros = [int(re.search(r"\d+", parte.stem).group()) for parte in pasta.glob("parte-*.parquet")]
    numero = max(numeros, default=0) + 1
    arquivo = pasta / f"parte-{numero:04d}.parquet"
    temporario = pasta / f"parte-{numero:04d}.tmp"

    con = duckdb.connect()
    con.execute(f"CREATE TABLE conteudo_tentativa ({COLUNAS_BRONZE})")
    con.executemany("INSERT INTO conteudo_tentativa VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas)

    # Grava num arquivo temporário e só depois renomeia: uma parte pela metade nunca vira .parquet
    con.execute(f"COPY conteudo_tentativa TO '{temporario.as_posix()}' (FORMAT parquet)")
    con.close()
    os.replace(temporario, arquivo)
    return arquivo


def carregar_estado(con):
    """Cria a tabela 'estado' na conexão: do arquivo, ou vazia na primeira vez."""
    arquivo = arquivo_estado()
    if arquivo.exists():
        con.execute(f"CREATE OR REPLACE TABLE estado AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE estado ({COLUNAS_ESTADO})")


def aplicar_dia(con, data):
    """Junta à tabela 'estado' as tentativas gravadas na Bronze no dia 'data'.

    Pode ser chamada mais de uma vez no mesmo dia: o hash de hoje já está no estado,
    então a segunda chamada não enxerga mudança nova e mantém as datas.
    """
    partes = partes_do_dia(data)
    if not partes:
        return

    lista = [parte.as_posix() for parte in partes]
    con.execute(f"CREATE OR REPLACE TEMP VIEW tentativas AS SELECT * FROM read_parquet({lista})")
    con.execute("""
        CREATE OR REPLACE TABLE estado AS
        WITH
        -- Resultado de hoje de cada link (vale a última tentativa do dia)
        hoje AS (
            SELECT
                link,
                arg_max(servidor, tentado_em)            AS servidor,
                arg_max(tamanho_bytes, tentado_em)       AS tamanho_bytes,
                arg_max(hash_conteudo, tentado_em)       AS hash_conteudo,
                arg_max(qtd_colunas, tentado_em)         AS qtd_colunas,
                arg_max("schema", tentado_em)            AS "schema",
                arg_max(schema_hash, tentado_em)         AS schema_hash,
                arg_max(erro_schema, tentado_em)         AS erro_schema,
                arg_max(verificacao_parcial, tentado_em) AS verificacao_parcial,
                arg_max(erro_tipo, tentado_em)           AS erro_tipo
            FROM tentativas
            GROUP BY link
        ),
        -- Compara o resultado de hoje com o que o estado já sabia
        novos AS (
            SELECT
                h.*,
                -- Download que deu certo: tem hash
                h.hash_conteudo IS NOT NULL AS leu,
                -- Schema lido hoje (a leitura do conteúdo pode dar certo e o schema não)
                h.schema_hash IS NOT NULL AS leu_schema,
                h.hash_conteudo IS NOT NULL AND e.hash_conteudo IS NOT NULL
                    AND e.hash_conteudo <> h.hash_conteudo AS mudou_conteudo,
                h.schema_hash IS NOT NULL AND e.schema_hash IS NOT NULL
                    AND e.schema_hash <> h.schema_hash AS mudou_schema,
                e.ultima_leitura          AS e_ultima_leitura,
                e.hash_conteudo           AS e_hash_conteudo,
                e.tamanho_bytes           AS e_tamanho_bytes,
                e.qtd_colunas             AS e_qtd_colunas,
                e."schema"                AS e_schema,
                e.schema_hash             AS e_schema_hash,
                e.erro_schema             AS e_erro_schema,
                e.verificacao_parcial     AS e_verificacao_parcial,
                e.schema_anterior         AS e_schema_anterior,
                e.ultima_mudanca          AS e_ultima_mudanca,
                e.ultima_mudanca_schema   AS e_ultima_mudanca_schema
            FROM hoje h
            LEFT JOIN estado e ON e.link = h.link
        )
        -- 1) Links sem tentativa hoje: continuam como estavam
        SELECT e.*
        FROM estado e
        WHERE NOT EXISTS (SELECT 1 FROM novos n WHERE n.link = e.link)

        UNION ALL
        -- 2) Links com tentativa hoje: leitura que deu certo substitui; falha mantém o que já se sabia
        SELECT
            link,
            servidor,
            CAST($data AS DATE),
            CASE WHEN leu THEN CAST($data AS DATE) ELSE e_ultima_leitura END,
            CASE WHEN leu THEN hash_conteudo ELSE e_hash_conteudo END,
            CASE WHEN leu THEN tamanho_bytes ELSE e_tamanho_bytes END,
            CASE WHEN leu_schema THEN qtd_colunas ELSE e_qtd_colunas END,
            CASE WHEN leu_schema THEN "schema" ELSE e_schema END,
            CASE WHEN leu_schema THEN schema_hash ELSE e_schema_hash END,
            CASE WHEN leu THEN erro_schema ELSE e_erro_schema END,
            CASE WHEN leu THEN verificacao_parcial ELSE e_verificacao_parcial END,
            CASE WHEN mudou_schema THEN e_schema ELSE e_schema_anterior END,
            CASE WHEN mudou_conteudo THEN CAST($data AS DATE) ELSE e_ultima_mudanca END,
            CASE WHEN mudou_schema THEN CAST($data AS DATE) ELSE e_ultima_mudanca_schema END,
            erro_tipo
        FROM novos
    """, {"data": data})


def salvar_estado(con):
    """Grava a tabela 'estado' no arquivo, sem deixar um arquivo pela metade."""
    arquivo = arquivo_estado()
    arquivo.parent.mkdir(parents=True, exist_ok=True)

    temporario = arquivo.with_suffix(".tmp")
    con.execute(f"COPY (SELECT * FROM estado ORDER BY link) TO '{temporario.as_posix()}' (FORMAT parquet)")
    os.replace(temporario, arquivo)


def atualizar_estado(data):
    """Atualiza o estado do conteúdo com as tentativas de um dia."""
    con = duckdb.connect()
    carregar_estado(con)
    aplicar_dia(con, data)
    salvar_estado(con)
    con.close()