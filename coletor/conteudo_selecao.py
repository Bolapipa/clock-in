"""Escolha dos links que serão baixados no dia (Fase 3, decisão 27).

Entram na escolha os links dos recursos que:
- têm formato tabular (silver/recurso, coluna formato_tabular);
- não estão quebrados (silver/link_status); link ainda não testado entra;
- nunca foram baixados, ou foram tentados há CICLO_DIAS dias ou mais (estado/conteudo_atual).

Em cada servidor vão primeiro os nunca tentados e depois os tentados há mais tempo,
até MAX_POR_SERVIDOR por dia. Links já tentados hoje (retomada do dia) não se repetem.

Uso (como biblioteca):
    from conteudo_selecao import selecionar
    por_servidor = selecionar(data)   # {servidor: [(link, formato), ...]}
"""

import sys

import duckdb

import conteudo_estado
import links
import portal

# Dias entre duas leituras do mesmo arquivo (decisão 27)
CICLO_DIAS = 7

# Quantos arquivos de um mesmo servidor são baixados por dia. Provisório: calibrar com
# o tempo e o tamanho reais dos downloads
MAX_POR_SERVIDOR = 1000


def arquivo_link_status(data):
    """Arquivo da Silver de status dos links de um dia."""
    return portal.RAIZ / "dados" / "silver" / "link_status" / f"data={data}" / "link_status.parquet"


def selecionar(data, limite=None):
    """Escolhe os links do dia: {servidor: [(link, formato)]}, no máximo MAX_POR_SERVIDOR por servidor."""
    recurso = links.arquivo_recurso(data)
    if not recurso.exists():
        sys.exit(f"Silver de recursos de {data} não encontrada. Rode antes: python coletor/silver.py --data {data}")
    status = arquivo_link_status(data)
    if not status.exists():
        sys.exit(f"Silver de status dos links de {data} não encontrada. "
                 f"Rode antes: python coletor/silver_links.py --data {data}")

    con = duckdb.connect()
    conteudo_estado.carregar_estado(con)

    # Links que já foram tentados hoje (para retomar sem repetir)
    partes = conteudo_estado.partes_do_dia(data)
    if partes:
        lista = [parte.as_posix() for parte in partes]
        con.execute(f"CREATE TABLE feitos_hoje AS SELECT DISTINCT link FROM read_parquet({lista})")
    else:
        con.execute("CREATE TABLE feitos_hoje (link VARCHAR)")

    escolhidos = con.execute(f"""
        WITH
        -- Links http(s) tabulares distintos, com o servidor (o endereço sem porta nem usuário)
        candidatos AS (
            SELECT
                link,
                min(formato_limpo) AS formato,
                lower(regexp_extract(link, '^https?://(?:[^/?#@]*@)?([^/?#:]+)', 1)) AS servidor
            FROM (
                SELECT trim(link) AS link, formato_limpo
                FROM read_parquet('{recurso.as_posix()}')
                WHERE formato_tabular AND regexp_matches(lower(trim(link)), '^https?://')
            )
            GROUP BY link
        ),
        -- Fora os quebrados; fora os tentados há menos de CICLO_DIAS dias
        devidos AS (
            SELECT
                c.link,
                c.formato,
                c.servidor,
                e.ultima_tentativa,
                f.link IS NOT NULL AS feito_hoje
            FROM candidatos c
            LEFT JOIN estado e ON e.link = c.link
            LEFT JOIN read_parquet('{status.as_posix()}') s ON s.link = c.link
            LEFT JOIN feitos_hoje f ON f.link = c.link
            WHERE c.servidor <> ''
              AND NOT COALESCE(s.quebrado, false)
              AND (e.ultima_tentativa IS NULL OR e.ultima_tentativa <= CAST($data AS DATE) - $ciclo)
        ),
        -- Em cada servidor: primeiro os já feitos hoje (ocupam as vagas), depois os nunca
        -- tentados e os tentados há mais tempo
        ranqueados AS (
            SELECT
                *,
                row_number() OVER (
                    PARTITION BY servidor
                    ORDER BY feito_hoje DESC, ultima_tentativa ASC NULLS FIRST, link
                ) AS posicao
            FROM devidos
        )
        SELECT link, servidor, formato
        FROM ranqueados
        WHERE posicao <= $maximo AND NOT feito_hoje
        ORDER BY hash(link)
        LIMIT $limite
    """, {"data": data, "ciclo": CICLO_DIAS, "maximo": MAX_POR_SERVIDOR, "limite": limite or 10**9}).fetchall()
    con.close()

    por_servidor = {}
    for link, servidor, formato in escolhidos:
        por_servidor.setdefault(servidor, []).append((link, formato))

    # Os servidores com mais links começam primeiro: são eles que decidem o tempo total
    return dict(sorted(por_servidor.items(), key=lambda item: len(item[1]), reverse=True))