"""Saúde dos links dos recursos (Fase 2).

Para cada link de recurso da Silver, testa se ele responde: faz um HEAD e,
se o servidor recusar (400, 403, 405 ou 501), um GET pedindo só os 2 primeiros KB.
Registra status, tempo, tipo de resposta e tipo de erro (DNS, SSL, timeout...).

Coleta educada:
- uma requisição por vez em cada servidor, com pausa entre elas;
- vários servidores ao mesmo tempo, para caber no tempo do job;
- no máximo MAX_POR_SERVIDOR links por servidor por dia: os testados há mais
  tempo vão primeiro, e os que nunca foram testados vão antes de todos.

Cada tentativa vai para a Bronze e o estado de cada link é mantido em um arquivo:
dados/bronze/link_tentativa/data=AAAA-MM-DD/parte-0001.parquet
dados/estado/links_atual.parquet  (uma linha por link)
    link, servidor, ultima_tentativa, status_http, erro_tipo,
    falhas_seguidas (dias seguidos com falha; zera no sucesso),
    falha_desde (primeira falha da série atual), ultimo_sucesso

Um link está quebrado com 3 falhas seguidas em dias diferentes (decisão 14).

Uso:
    python coletor/links.py                    # links do dia, a partir da Silver (recurso)
    python coletor/links.py --max-links 200    # teste com uma amostra
    python coletor/links.py --data 2026-10-26  # usa a Silver de outro dia (retoma o dia)
"""

import argparse
import asyncio
import os
import re
import sys
import time
from datetime import date, datetime, timezone

import duckdb
import httpx

import portal

# Tempo máximo de cada chamada, em segundos
TIMEOUT = 20

# Pausa entre dois links do mesmo servidor, em segundos
PAUSA_POR_SERVIDOR = 1.0

# Quantos links de um mesmo servidor são testados por dia
MAX_POR_SERVIDOR = 5000

# Quantos servidores são testados ao mesmo tempo
SERVIDORES_SIMULTANEOS = 100

# Quantas tentativas juntar antes de gravar um arquivo (parte)
TAMANHO_LOTE = 5000

# Falhas seguidas, em dias diferentes, para o link ser considerado quebrado
FALHAS_PARA_QUEBRADO = 3

# Falhas de rede seguidas num servidor que fazem o teste desistir dele no dia: sem isso,
# um servidor fora do ar com milhares de links gastaria 20 s de timeout em cada um
FALHAS_DE_REDE_PARA_DESISTIR = 5

# Tipos de erro que indicam o servidor inteiro com problema (e não só aquele link)
ERROS_DE_REDE = ("TIMEOUT", "DNS", "SSL", "CONEXAO")

# Posição de erro_tipo nas linhas da Bronze (ver montar_linha)
POSICAO_ERRO_TIPO = 11

# Status em que o HEAD não vale: o servidor não aceita esse método, então tenta GET
STATUS_SEM_HEAD = (400, 403, 405, 501)

# Colunas do estado, na ordem em que são gravadas
COLUNAS_ESTADO = """
    link             VARCHAR,
    servidor         VARCHAR,
    ultima_tentativa DATE,
    status_http      INTEGER,
    erro_tipo        VARCHAR,
    falhas_seguidas  INTEGER,
    falha_desde      DATE,
    ultimo_sucesso   DATE
"""


def pasta_tentativas():
    """Pasta da Bronze das tentativas (calculada na hora, para os testes poderem trocar a raiz)."""
    return portal.RAIZ / "dados" / "bronze" / "link_tentativa"


def arquivo_estado():
    """Arquivo do estado dos links."""
    return portal.RAIZ / "dados" / "estado" / "links_atual.parquet"


def arquivo_recurso(data):
    """Arquivo da Silver de recursos de um dia."""
    return portal.RAIZ / "dados" / "silver" / "recurso" / f"data={data}" / "recurso.parquet"


def criar_cliente():
    """Cria o cliente HTTP assíncrono. Sem a chave da API: os links são de outros sites."""
    limites = httpx.Limits(max_connections=SERVIDORES_SIMULTANEOS + 20, max_keepalive_connections=20)
    return httpx.AsyncClient(
        headers={"User-Agent": portal.USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        limits=limites,
    )


def classificar_erro(erro):
    """Resume uma exceção do httpx num tipo de erro: DNS, SSL, TIMEOUT, CONEXAO..."""
    texto = str(erro).lower()
    if isinstance(erro, httpx.TimeoutException):
        return "TIMEOUT"
    if isinstance(erro, httpx.TooManyRedirects):
        return "REDIRECIONAMENTOS"
    if isinstance(erro, httpx.InvalidURL):
        return "URL_INVALIDA"
    if re.search(r"getaddrinfo|name or service|nodename|name resolution", texto):
        return "DNS"
    if re.search(r"ssl|certificate", texto):
        return "SSL"
    if isinstance(erro, httpx.TransportError):
        return "CONEXAO"
    return "OUTRO"


def montar_linha(data, link, servidor, metodo, inicio, resposta=None, erro=None):
    """Monta a linha da Bronze com o resultado de um teste."""
    tempo_ms = round((time.perf_counter() - inicio) * 1000)
    tentado_em = datetime.now(timezone.utc).replace(tzinfo=None)

    if resposta is None:
        texto = f"{type(erro).__name__}: {erro}"[:300]
        return (data, link, servidor, metodo, None, None, None, None, None, None,
                tempo_ms, classificar_erro(erro), texto, tentado_em)

    tamanho = resposta.headers.get("content-length", "")
    return (data, link, servidor, metodo, resposta.status_code, str(resposta.url),
            resposta.headers.get("content-type"), int(tamanho) if tamanho.isdigit() else None,
            resposta.headers.get("last-modified"), resposta.headers.get("etag"),
            tempo_ms, None, None, tentado_em)


def montar_linha_desistida(data, link, servidor):
    """Linha de um link que não foi testado porque o servidor já falhou várias vezes seguidas hoje."""
    tentado_em = datetime.now(timezone.utc).replace(tzinfo=None)
    return (data, link, servidor, None, None, None, None, None, None, None,
            0, "SERVIDOR_FORA", "servidor sem resposta nos testes anteriores do dia", tentado_em)


async def testar_link(cliente, data, link, servidor):
    """Testa um link: HEAD e, se o servidor recusar o método, GET dos 2 primeiros KB."""
    inicio = time.perf_counter()
    metodo = "HEAD"
    try:
        resposta = await cliente.head(link)
        if resposta.status_code in STATUS_SEM_HEAD:
            metodo = "GET"
            # stream: lê só os cabeçalhos; o corpo não é baixado
            async with cliente.stream("GET", link, headers={"Range": "bytes=0-2047"}) as resposta:
                return montar_linha(data, link, servidor, metodo, inicio, resposta=resposta)
        return montar_linha(data, link, servidor, metodo, inicio, resposta=resposta)
    # Qualquer falha vira uma linha de erro: um link ruim não pode derrubar o teste dos outros
    except Exception as erro:
        return montar_linha(data, link, servidor, metodo, inicio, erro=erro)


def carregar_estado(con):
    """Cria a tabela 'estado' na conexão: do arquivo, ou vazia na primeira vez."""
    arquivo = arquivo_estado()
    if arquivo.exists():
        con.execute(f"CREATE OR REPLACE TABLE estado AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")
    else:
        con.execute(f"CREATE OR REPLACE TABLE estado ({COLUNAS_ESTADO})")


def partes_do_dia(data):
    """Arquivos de tentativas gravados na Bronze no dia."""
    return sorted((pasta_tentativas() / f"data={data}").glob("parte-*.parquet"))


def selecionar(data, limite=None):
    """Escolhe os links do dia: {servidor: [links]}, no máximo MAX_POR_SERVIDOR por servidor."""
    recurso = arquivo_recurso(data)
    if not recurso.exists():
        sys.exit(f"Silver de recursos de {data} não encontrada. Rode antes: python coletor/silver.py --data {data}")

    con = duckdb.connect()
    carregar_estado(con)

    # Links que já foram testados hoje (para retomar sem repetir)
    partes = partes_do_dia(data)
    if partes:
        lista = [parte.as_posix() for parte in partes]
        con.execute(f"CREATE TABLE feitos_hoje AS SELECT DISTINCT link FROM read_parquet({lista})")
    else:
        con.execute("CREATE TABLE feitos_hoje (link VARCHAR)")

    escolhidos = con.execute(f"""
        WITH
        -- Links http(s) distintos, com o servidor (o endereço sem porta nem usuário)
        links AS (
            SELECT
                link,
                lower(regexp_extract(link, '^https?://(?:[^/?#@]*@)?([^/?#:]+)', 1)) AS servidor
            FROM (
                SELECT DISTINCT trim(link) AS link
                FROM read_parquet('{recurso.as_posix()}')
                WHERE regexp_matches(lower(trim(link)), '^https?://')
            )
        ),
        -- Em cada servidor: primeiro os já feitos hoje (ocupam as vagas), depois os nunca
        -- testados e os testados há mais tempo
        ranqueados AS (
            SELECT
                l.link,
                l.servidor,
                f.link IS NOT NULL AS feito_hoje,
                row_number() OVER (
                    PARTITION BY l.servidor
                    ORDER BY (f.link IS NOT NULL) DESC, e.ultima_tentativa ASC NULLS FIRST, l.link
                ) AS posicao
            FROM links l
            LEFT JOIN estado e ON e.link = l.link
            LEFT JOIN feitos_hoje f ON f.link = l.link
            WHERE l.servidor <> ''
        )
        SELECT link, servidor
        FROM ranqueados
        WHERE posicao <= $maximo AND NOT feito_hoje
        ORDER BY hash(link)
        LIMIT $limite
    """, {"maximo": MAX_POR_SERVIDOR, "limite": limite or 10**9}).fetchall()
    con.close()

    por_servidor = {}
    for link, servidor in escolhidos:
        por_servidor.setdefault(servidor, []).append(link)

    # Os servidores com mais links começam primeiro: são eles que decidem o tempo total
    return dict(sorted(por_servidor.items(), key=lambda item: len(item[1]), reverse=True))


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
    con.execute("""
        CREATE TABLE link_tentativa (
            data_coleta    DATE,
            link           VARCHAR,
            servidor       VARCHAR,
            metodo         VARCHAR,
            status_http    INTEGER,
            url_final      VARCHAR,
            content_type   VARCHAR,
            content_length BIGINT,
            last_modified  VARCHAR,
            etag           VARCHAR,
            tempo_ms       INTEGER,
            erro_tipo      VARCHAR,
            erro           VARCHAR,
            tentado_em     TIMESTAMP
        )
    """)
    con.executemany("INSERT INTO link_tentativa VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas)

    # Grava num arquivo temporário e só depois renomeia: uma parte pela metade nunca vira .parquet
    con.execute(f"COPY link_tentativa TO '{temporario.as_posix()}' (FORMAT parquet)")
    con.close()
    os.replace(temporario, arquivo)
    return arquivo


async def executar(por_servidor, data):
    """Testa os links: um por vez em cada servidor, vários servidores em paralelo."""
    total = sum(len(links) for links in por_servidor.values())
    buffer = []
    feitos = 0
    inicio = time.perf_counter()
    semaforo = asyncio.Semaphore(SERVIDORES_SIMULTANEOS)

    async with criar_cliente() as cliente:

        async def testar_servidor(servidor, links):
            nonlocal feitos
            async with semaforo:
                falhas_de_rede = 0
                for link in links:
                    # Servidor que falhou várias vezes seguidas: não espera mais timeouts, só registra a falha
                    desistiu = falhas_de_rede >= FALHAS_DE_REDE_PARA_DESISTIR
                    if desistiu:
                        linha = montar_linha_desistida(data, link, servidor)
                    else:
                        linha = await testar_link(cliente, data, link, servidor)
                        falhas_de_rede = falhas_de_rede + 1 if linha[POSICAO_ERRO_TIPO] in ERROS_DE_REDE else 0
                    buffer.append(linha)
                    feitos += 1

                    # Grava a cada lote completo, para não perder trabalho
                    if len(buffer) >= TAMANHO_LOTE:
                        gravar_lote(list(buffer), data)
                        buffer.clear()
                        minutos = (time.perf_counter() - inicio) / 60
                        print(f"  {feitos}/{total} links em {minutos:.0f} min", flush=True)

                    # Pausa entre dois links do mesmo servidor (sem pausa se nada foi pedido ao servidor)
                    if not desistiu:
                        await asyncio.sleep(PAUSA_POR_SERVIDOR)

        try:
            await asyncio.gather(*(testar_servidor(s, links) for s, links in por_servidor.items()))
        finally:
            # Mesmo interrompido, grava o que já foi testado
            if buffer:
                gravar_lote(list(buffer), data)


def aplicar_dia(con, data):
    """Junta à tabela 'estado' as tentativas gravadas na Bronze no dia 'data'.

    Pode ser chamada mais de uma vez no mesmo dia sem contar a falha em dobro.
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
                arg_max(servidor, tentado_em)    AS servidor,
                arg_max(status_http, tentado_em) AS status_http,
                arg_max(erro_tipo, tentado_em)   AS erro_tipo
            FROM tentativas
            GROUP BY link
        ),
        -- Combina o resultado de hoje com o estado de ontem
        novos AS (
            SELECT
                h.*,
                h.status_http IS NOT NULL AND h.status_http < 400 AS ok,
                CASE
                    WHEN h.status_http IS NOT NULL AND h.status_http < 400 THEN 0
                    WHEN e.ultima_tentativa = CAST($data AS DATE) THEN e.falhas_seguidas
                    ELSE COALESCE(e.falhas_seguidas, 0) + 1
                END AS falhas_seguidas,
                e.falha_desde    AS falha_desde_anterior,
                e.ultimo_sucesso AS ultimo_sucesso_anterior
            FROM hoje h
            LEFT JOIN estado e ON e.link = h.link
        )
        -- 1) Links sem tentativa hoje: continuam como estavam
        SELECT e.*
        FROM estado e
        WHERE NOT EXISTS (SELECT 1 FROM hoje h WHERE h.link = e.link)

        UNION ALL
        -- 2) Links testados hoje: sucesso zera as falhas; falha soma uma (só uma vez por dia)
        SELECT
            link, servidor, CAST($data AS DATE), status_http, erro_tipo, falhas_seguidas,
            CASE WHEN ok THEN NULL WHEN falhas_seguidas = 1 THEN CAST($data AS DATE) ELSE falha_desde_anterior END,
            CASE WHEN ok THEN CAST($data AS DATE) ELSE ultimo_sucesso_anterior END
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
    """Atualiza o estado dos links com as tentativas de um dia."""
    con = duckdb.connect()
    carregar_estado(con)
    aplicar_dia(con, data)
    salvar_estado(con)
    con.close()


def resumo(data):
    """Imprime o resultado do dia, lido da Bronze."""
    partes = [parte.as_posix() for parte in partes_do_dia(data)]
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet({partes})")
    total, ok, mediana, p95 = con.execute("""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE status_http < 400),
               median(tempo_ms), quantile_cont(tempo_ms, 0.95)
        FROM t
    """).fetchall()[0]
    print(f"\n{total} links testados: {ok} ({ok / total:.1%}) responderam com sucesso; "
          f"tempo mediano {mediana:.0f} ms, p95 {p95:.0f} ms")
    for status, quantos in con.execute("""
        SELECT COALESCE(CAST(status_http AS VARCHAR), erro_tipo), COUNT(*)
        FROM t GROUP BY 1 ORDER BY 2 DESC LIMIT 12
    """).fetchall():
        print(f"  {status}: {quantos}")
    con.close()


def main():
    parser = argparse.ArgumentParser(description="Testa a saúde dos links dos recursos")
    parser.add_argument("--data", type=date.fromisoformat, help="data da execução (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--max-links", type=int, help="testa só uma amostra de N links (teste)")
    args = parser.parse_args()

    data = args.data or portal.data_de_hoje()
    por_servidor = selecionar(data, args.max_links)

    total = sum(len(links) for links in por_servidor.values())
    if not total:
        print(f"Nenhum link a testar em {data}.")
        return
    maior = max(len(links) for links in por_servidor.values())
    horas = maior * (PAUSA_POR_SERVIDOR + 0.3) / 3600
    print(f"{total} links em {len(por_servidor)} servidores; o maior tem {maior}; estimativa {horas:.1f} h", flush=True)

    asyncio.run(executar(por_servidor, data))
    atualizar_estado(data)

    resumo(data)
    print(f"\nEstado atualizado: {arquivo_estado()}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()