"""Coletor da base do Painel de Monitoramento de Dados Abertos da CGU (Fase 1, tarefa 6).

A CGU publica dois arquivos CSV (atualizados nos primeiros 15 dias de cada mês):
- cronograma: uma linha por base prevista nos Planos de Dados Abertos, com o órgão
  responsável e o link da base no dados.gov.br;
- monitoramento: uma linha por órgão, com a situação do Plano de Dados Abertos.

Os links dos arquivos vêm do próprio catálogo (detalhe da base do painel).
Cada arquivo é gravado na Bronze sem transformação (todas as colunas como texto):
dados/bronze/painel_cgu_cronograma/data=AAAA-MM-DD/painel_cgu_cronograma.parquet
dados/bronze/painel_cgu_monitoramento/data=AAAA-MM-DD/painel_cgu_monitoramento.parquet

Uso:
    python coletor/painel_cgu.py
"""

import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import httpx

import portal

# Id da base "painel-de-monitoramento-de-dados-abertos" no catálogo
ID_PAINEL = "eda85b50-9d7a-4b01-aca4-bef32b3b8d9a"

# Título de cada arquivo no catálogo -> nome da tabela na Bronze
ARQUIVOS = {
    "Cronograma de Abertura das Bases": "cronograma",
    "Monitoramento da Política de Dados Abertos": "monitoramento",
}


def links_do_painel(cliente_api):
    """Busca no catálogo o link de cada arquivo do painel."""
    resposta = portal.buscar(cliente_api, f"{portal.URL_CONJUNTOS}/{ID_PAINEL}")
    if resposta.status_code != 200:
        sys.exit(f"Detalhe da base do painel: HTTP {resposta.status_code}")

    links = {}
    for recurso in resposta.json().get("recursos") or []:
        tabela = ARQUIVOS.get((recurso.get("titulo") or "").strip())
        if tabela:
            links[tabela] = recurso["link"]

    # Se a CGU mudar o título de um arquivo, é melhor parar do que gravar pela metade
    faltando = set(ARQUIVOS.values()) - set(links)
    if faltando:
        sys.exit(f"Arquivos do painel não encontrados no catálogo: {sorted(faltando)}")
    return links


def link_de_download(link):
    """Transforma o link de visualização do SharePoint em link de download direto."""
    separador = "&" if "?" in link else "?"
    return f"{link}{separador}download=1"


def baixar_csv(cliente_arquivos, link, destino):
    """Baixa um CSV do painel para o arquivo destino e devolve o Last-Modified."""
    try:
        resposta = portal.buscar(cliente_arquivos, link_de_download(link))
    except portal.FalhaPortal as erro:
        sys.exit(f"Download falhou ({erro}): {link}")

    # Se vier uma página HTML, o SharePoint não entregou o arquivo
    tipo = resposta.headers.get("content-type", "")
    if resposta.status_code != 200 or "html" in tipo:
        sys.exit(f"Download não devolveu o arquivo (HTTP {resposta.status_code}, {tipo}): {link}")

    destino.write_bytes(resposta.content)
    return resposta.headers.get("last-modified")


def gravar_bronze(arquivo_csv, tabela, data_coleta, last_modified):
    """Grava o CSV na Bronze, com todas as colunas como texto, na partição do dia."""
    pasta = portal.RAIZ / "dados" / "bronze" / f"painel_cgu_{tabela}" / f"data={data_coleta}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"painel_cgu_{tabela}.parquet"
    coletado_em = datetime.now(timezone.utc).replace(tzinfo=None)

    con = duckdb.connect()
    # all_varchar: guarda os valores como vieram, sem o DuckDB adivinhar tipos
    con.execute(f"""
        COPY (
            SELECT
                *,
                DATE '{data_coleta}'        AS data_coleta,
                $last_modified              AS last_modified,
                CAST($coletado_em AS TIMESTAMP) AS coletado_em
            FROM read_csv('{arquivo_csv.as_posix()}', delim = ';', header = true, all_varchar = true)
        ) TO '{arquivo.as_posix()}' (FORMAT parquet)
    """, {"last_modified": last_modified, "coletado_em": coletado_em})
    linhas = con.execute(f"SELECT COUNT(*) FROM '{arquivo.as_posix()}'").fetchall()[0][0]
    con.close()
    return arquivo, linhas


def main():
    data_coleta = date.today()

    # 1) Links dos arquivos, pelo catálogo (precisa da chave da API)
    with portal.criar_cliente() as cliente_api:
        links = links_do_painel(cliente_api)

    # 2) Download no SharePoint com outro cliente, SEM a chave da API:
    #    a chave é do dados.gov.br e não deve ser enviada a outros sites
    cabecalhos = {"User-Agent": portal.USER_AGENT}
    with httpx.Client(headers=cabecalhos, follow_redirects=True, timeout=60) as cliente_arquivos:
        with tempfile.TemporaryDirectory() as pasta_temporaria:
            for tabela, link in links.items():
                arquivo_csv = Path(pasta_temporaria) / f"{tabela}.csv"
                last_modified = baixar_csv(cliente_arquivos, link, arquivo_csv)
                arquivo, linhas = gravar_bronze(arquivo_csv, tabela, data_coleta, last_modified)
                print(f"painel_cgu_{tabela}: {linhas} linhas (arquivo de {last_modified}) -> {arquivo}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
