"""Escolha dos links que serão baixados no dia (Fase 3, decisão 27).

Entram na escolha os links dos recursos que:
- têm formato tabular (silver/recurso, coluna formato_tabular);
- não estão quebrados (silver/link_status); link ainda não testado entra;
- nunca foram baixados, ou foram tentados há CICLO_DIAS dias ou mais (estado/conteudo_atual);
- ou falharam por um motivo passageiro (servidor fora do ar, conexão, timeout ou erro 5xx) há
  ESPERA_APOS_FALHA_PASSAGEIRA_DIAS dias ou mais: não faz sentido esperar a semana toda por uma
  instabilidade (decisão 40).

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

# Dias de espera depois de uma falha passageira, antes de tentar o arquivo de novo (decisão 40).
# Falhas passageiras: servidor fora do ar, falha de conexão, timeout e erro 5xx. Os outros erros
# (página HTML no lugar do arquivo, 403, 404...) continuam esperando o ciclo inteiro
ESPERA_APOS_FALHA_PASSAGEIRA_DIAS = 2

# Quantos arquivos de um mesmo servidor são baixados por dia. Era 1.000; subiu para 3.000 em
# 30/10/2026 porque o dadosabertos.rj.gov.br (13.557 arquivos) levaria 14 dias para fechar um ciclo.
# Os servidores seguem recebendo um pedido por vez, com pausa; o tempo do passo é o que limita
MAX_POR_SERVIDOR = 3000


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
        -- Fora os quebrados; fora os tentados há menos de CICLO_DIAS dias (ou, se a última tentativa
        -- falhou por um motivo passageiro, há menos de ESPERA_APOS_FALHA_PASSAGEIRA_DIAS dias)
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
              AND (e.ultima_tentativa IS NULL
                   OR e.ultima_tentativa <= CAST($data AS DATE) - $ciclo
                   OR (COALESCE(e.erro_tipo IN ('SERVIDOR_FORA', 'CONEXAO', 'TIMEOUT'), false)
                       OR COALESCE(starts_with(e.erro_tipo, 'HTTP_5'), false))
                      AND e.ultima_tentativa <= CAST($data AS DATE) - $espera)
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
        SELECT link, servidor, formato, posicao
        FROM ranqueados
        WHERE posicao <= $maximo AND NOT feito_hoje
        ORDER BY hash(link)
        LIMIT $limite
    """, {"data": data, "ciclo": CICLO_DIAS, "espera": ESPERA_APOS_FALHA_PASSAGEIRA_DIAS,
          "maximo": MAX_POR_SERVIDOR, "limite": limite or 10**9}).fetchall()
    con.close()

    por_servidor = {}
    for link, servidor, formato, posicao in escolhidos:
        por_servidor.setdefault(servidor, []).append((posicao, link, formato))

    # Dentro de cada servidor, volta para a ordem de prioridade (a amostra acima é embaralhada):
    # se o tempo do passo acabar, o que fica sem baixar é o que foi tentado mais recentemente
    por_servidor = {servidor: [(link, formato) for _, link, formato in sorted(itens)] for servidor, itens in por_servidor.items()}

    # Os servidores com mais links começam primeiro: são eles que decidem o tempo total
    return dict(sorted(por_servidor.items(), key=lambda item: len(item[1]), reverse=True))