"""Testes do download do conteúdo (coletor/conteudo_baixar.py).

Nenhum teste acessa a internet: os servidores são simulados com o MockTransport do httpx.
"""

import asyncio
import hashlib
import sys
import tempfile
from datetime import date

import duckdb
import httpx
import pytest

import conteudo_baixar
import conteudo_estado
import portal

DIA_1 = date(2026, 10, 26)
DIA_2 = date(2026, 11, 2)

CSV = b"id;nome\n1;Ana\n2;Bia\n"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    """Aponta Silver, Bronze e estado para uma pasta temporária, zera as esperas e isola os arquivos temporários."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(conteudo_baixar, "PAUSA_POR_SERVIDOR", 0)

    # Os downloads usam esta pasta: no fim de cada teste ela precisa estar vazia
    temporarios = tmp_path / "temporarios"
    temporarios.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temporarios))


def cliente_falso(responder):
    """Cliente assíncrono que responde com a função 'responder'."""
    return httpx.AsyncClient(transport=httpx.MockTransport(responder), follow_redirects=True)


def arquivos_temporarios(tmp_path):
    """O que sobrou na pasta temporária dos downloads."""
    return list((tmp_path / "temporarios").iterdir())


def gravar_silver(data, recursos, quebrados=()):
    """Grava silver/recurso (link, formato_limpo, formato_tabular) e silver/link_status falsas."""
    pasta = portal.RAIZ / "dados" / "silver"
    (pasta / "recurso" / f"data={data}").mkdir(parents=True)
    (pasta / "link_status" / f"data={data}").mkdir(parents=True)

    valores = ", ".join(f"('{link}', '{formato}', true)" for link, formato in recursos)
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores}) t(link, formato_limpo, formato_tabular))
                   TO '{(pasta / "recurso" / f"data={data}" / "recurso.parquet").as_posix()}' (FORMAT parquet)""")

    valores = ", ".join(f"('{link}', true)" for link in quebrados) or "('x', false)"
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores}) t(link, quebrado))
                   TO '{(pasta / "link_status" / f"data={data}" / "link_status.parquet").as_posix()}' (FORMAT parquet)""")


def ler_bronze(data):
    """Lê as tentativas gravadas no dia como lista de dicionários."""
    pasta = (conteudo_estado.pasta_tentativas() / f"data={data}" / "*.parquet").as_posix()
    resultado = duckdb.sql(f"SELECT * FROM '{pasta}' ORDER BY link")
    colunas = resultado.columns
    return [dict(zip(colunas, linha)) for linha in resultado.fetchall()]


def baixar(responder, itens, limite_segundos=None):
    """Roda o downloader com um servidor falso para os itens [(link, formato)] de um servidor."""
    por_servidor = {"a.gov.br": itens}
    original = conteudo_baixar.criar_cliente
    conteudo_baixar.criar_cliente = lambda: cliente_falso(responder)
    try:
        return asyncio.run(conteudo_baixar.executar(por_servidor, DIA_1, limite_segundos))
    finally:
        conteudo_baixar.criar_cliente = original


# --- Um arquivo ---

def test_baixa_csv_e_grava_hash_e_schema(tmp_path):
    link = "https://a.gov.br/a.csv"

    feitos = baixar(lambda requisicao: httpx.Response(200, content=CSV, headers={"content-type": "text/csv"}),
                    [(link, "CSV")])

    assert feitos == 1
    linha = ler_bronze(DIA_1)[0]
    assert linha["status_http"] == 200
    assert linha["hash_conteudo"] == hashlib.sha256(CSV).hexdigest()
    assert linha["tamanho_bytes"] == len(CSV)
    assert linha["qtd_colunas"] == 2
    assert linha["verificacao_parcial"] is False
    assert linha["erro_tipo"] is None
    # O arquivo baixado foi apagado
    assert arquivos_temporarios(tmp_path) == []


def test_arquivo_maior_que_o_limite_e_cortado_e_marcado_como_parcial(tmp_path, monkeypatch):
    monkeypatch.setattr(conteudo_baixar, "LIMITE_BYTES", 10)
    conteudo_completo = b"id;nome\n" + b"1;Ana\n" * 100

    baixar(lambda requisicao: httpx.Response(200, content=conteudo_completo), [("https://a.gov.br/g.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["verificacao_parcial"] is True
    assert linha["tamanho_bytes"] == 10
    # O hash vale só para os primeiros 10 bytes
    assert linha["hash_conteudo"] == hashlib.sha256(conteudo_completo[:10]).hexdigest()
    assert arquivos_temporarios(tmp_path) == []


def test_arquivo_com_exatamente_o_limite_nao_e_parcial(monkeypatch):
    monkeypatch.setattr(conteudo_baixar, "LIMITE_BYTES", len(CSV))

    baixar(lambda requisicao: httpx.Response(200, content=CSV), [("https://a.gov.br/a.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["verificacao_parcial"] is False
    assert linha["tamanho_bytes"] == len(CSV)


def test_erro_http_vira_tipo_de_erro_sem_hash(tmp_path):
    baixar(lambda requisicao: httpx.Response(404), [("https://a.gov.br/x.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["status_http"] == 404
    assert linha["erro_tipo"] == "HTTP_404"
    assert linha["hash_conteudo"] is None
    assert arquivos_temporarios(tmp_path) == []


def test_pagina_html_no_lugar_do_arquivo_nao_conta_como_leitura(tmp_path):
    html = httpx.Response(200, content=b"<html>Portal do orgao</html>", headers={"content-type": "text/html; charset=utf-8"})

    baixar(lambda requisicao: html, [("https://a.gov.br/pagina.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["status_http"] == 200
    assert linha["erro_tipo"] == "HTML"
    assert linha["hash_conteudo"] is None


def test_timeout_de_rede_vira_tipo_de_erro(tmp_path):
    def responder(requisicao):
        raise httpx.ReadTimeout("demorou", request=requisicao)

    baixar(responder, [("https://a.gov.br/x.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["status_http"] is None
    assert linha["erro_tipo"] == "TIMEOUT"
    assert arquivos_temporarios(tmp_path) == []


def test_arquivo_que_demora_demais_para_baixar_e_abandonado(tmp_path, monkeypatch):
    monkeypatch.setattr(conteudo_baixar, "TEMPO_MAXIMO_POR_ARQUIVO", 0.1)

    async def devagar():
        # Um servidor que entrega um pedaço por vez, devagar
        for _ in range(5):
            yield b"1;Ana\n"
            await asyncio.sleep(0.1)

    baixar(lambda requisicao: httpx.Response(200, content=devagar()), [("https://a.gov.br/lento.csv", "CSV")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["erro_tipo"] == "TIMEOUT"
    assert linha["hash_conteudo"] is None
    assert arquivos_temporarios(tmp_path) == []


def test_formato_sem_leitura_de_schema_guarda_so_o_hash(monkeypatch):
    baixar(lambda requisicao: httpx.Response(200, content=b"conteudo de planilha"), [("https://a.gov.br/p.xlsx", "XLSX")])

    linha = ler_bronze(DIA_1)[0]
    assert linha["hash_conteudo"] == hashlib.sha256(b"conteudo de planilha").hexdigest()
    assert linha["schema"] is None
    assert linha["erro_schema"] == "FORMATO_SEM_SCHEMA"


# --- Vários arquivos ---

def test_desiste_do_servidor_depois_de_falhas_de_rede_seguidas(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        raise httpx.ConnectTimeout("sem resposta", request=requisicao)

    monkeypatch.setattr(conteudo_baixar, "FALHAS_DE_REDE_PARA_DESISTIR", 3)

    baixar(responder, [(f"https://a.gov.br/{i}.csv", "CSV") for i in range(10)])

    # Só 3 chamadas de verdade; os outros 7 arquivos foram registrados como falha sem esperar
    assert len(chamadas) == 3
    tipos = {}
    for linha in ler_bronze(DIA_1):
        tipos[linha["erro_tipo"]] = tipos.get(linha["erro_tipo"], 0) + 1
    assert tipos == {"TIMEOUT": 3, "SERVIDOR_FORA": 7}


def test_erro_http_nao_faz_desistir_do_servidor(monkeypatch):
    monkeypatch.setattr(conteudo_baixar, "FALHAS_DE_REDE_PARA_DESISTIR", 2)

    baixar(lambda requisicao: httpx.Response(404), [(f"https://a.gov.br/{i}.csv", "CSV") for i in range(6)])

    assert sum(linha["erro_tipo"] == "HTTP_404" for linha in ler_bronze(DIA_1)) == 6


def test_para_quando_o_tempo_maximo_acaba():
    chamadas = []

    async def responder_devagar(requisicao):
        chamadas.append(requisicao.url)
        await asyncio.sleep(0.3)
        return httpx.Response(200, content=CSV)

    feitos = baixar(responder_devagar, [(f"https://a.gov.br/{i}.csv", "CSV") for i in range(5)], limite_segundos=0.2)

    # O primeiro download começou dentro do prazo e terminou; o segundo nem começou
    assert feitos == 1
    assert len(chamadas) == 1
    assert len(ler_bronze(DIA_1)) == 1


def test_grava_em_lotes_sem_perder_nada(monkeypatch):
    monkeypatch.setattr(conteudo_baixar, "TAMANHO_LOTE", 2)

    baixar(lambda requisicao: httpx.Response(200, content=CSV), [(f"https://a.gov.br/{i}.csv", "CSV") for i in range(5)])

    # 5 arquivos em lotes de 2: três partes (2 + 2 + 1)
    assert len(conteudo_estado.partes_do_dia(DIA_1)) == 3
    assert len(ler_bronze(DIA_1)) == 5


# --- O comando inteiro ---

def test_main_baixa_grava_e_atualiza_o_estado_e_acha_a_mudanca(monkeypatch):
    link = "https://a.gov.br/a.csv"
    conteudos = {DIA_1: CSV, DIA_2: b"id;nome;valor\n1;Ana;10\n"}
    dia = {"atual": DIA_1}

    def responder(requisicao):
        return httpx.Response(200, content=conteudos[dia["atual"]])

    monkeypatch.setattr(conteudo_baixar, "criar_cliente", lambda: cliente_falso(responder))

    # Primeiro dia: primeira leitura, sem mudança
    gravar_silver(DIA_1, [(link, "CSV")])
    monkeypatch.setattr(sys, "argv", ["conteudo_baixar.py", "--data", str(DIA_1)])
    conteudo_baixar.main()

    # Oito dias depois (passou o ciclo de 7 dias): o arquivo mudou de conteúdo e de estrutura
    dia["atual"] = DIA_2
    gravar_silver(DIA_2, [(link, "CSV")])
    monkeypatch.setattr(sys, "argv", ["conteudo_baixar.py", "--data", str(DIA_2)])
    conteudo_baixar.main()

    estado = duckdb.sql(f"SELECT * FROM '{conteudo_estado.arquivo_estado().as_posix()}'")
    linha = dict(zip(estado.columns, estado.fetchall()[0]))
    assert linha["ultima_leitura"] == DIA_2
    assert linha["ultima_mudanca"] == DIA_2
    assert linha["ultima_mudanca_schema"] == DIA_2
    assert linha["qtd_colunas"] == 3


def test_main_nao_baixa_link_quebrado(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        return httpx.Response(200, content=CSV)

    gravar_silver(DIA_1, [("https://a.gov.br/ok.csv", "CSV"), ("https://a.gov.br/quebrado.csv", "CSV")],
                  quebrados=["https://a.gov.br/quebrado.csv"])
    monkeypatch.setattr(conteudo_baixar, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["conteudo_baixar.py", "--data", str(DIA_1)])

    conteudo_baixar.main()

    assert [str(url) for url in chamadas] == ["https://a.gov.br/ok.csv"]


def test_tempo_maximo_zero_nao_baixa_nada_e_nao_quebra(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        return httpx.Response(200, content=CSV)

    gravar_silver(DIA_1, [("https://a.gov.br/1.csv", "CSV"), ("https://a.gov.br/2.csv", "CSV")])
    monkeypatch.setattr(conteudo_baixar, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["conteudo_baixar.py", "--data", str(DIA_1), "--tempo-maximo", "0"])

    conteudo_baixar.main()

    # Nenhuma chamada, nenhuma tentativa gravada e o comando termina sem erro
    assert chamadas == []
    assert not (conteudo_estado.pasta_tentativas() / f"data={DIA_1}").exists()