"""Testes da escolha dos links a baixar (coletor/conteudo_selecao.py).

Monta a Silver (recurso e link_status) e o estado do conteúdo falsos numa pasta temporária
e confere quais links entram no dia. Não usa rede.
"""

import json
from datetime import date, datetime, timedelta

import duckdb
import pytest

import conteudo_estado
import conteudo_selecao
import portal

HOJE = date(2026, 11, 2)
SCHEMA = json.dumps([["id", "BIGINT"]])


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Aponta Silver e estado para uma pasta temporária."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)


def gravar_silver(recursos, quebrados=(), testados_ok=()):
    """Grava silver/recurso e silver/link_status falsas.

    recursos: lista de (link, formato_limpo, formato_tabular).
    quebrados e testados_ok: links com a situação registrada em link_status.
    """
    pasta = portal.RAIZ / "dados" / "silver"
    (pasta / "recurso" / f"data={HOJE}").mkdir(parents=True)
    (pasta / "link_status" / f"data={HOJE}").mkdir(parents=True)

    valores = ", ".join(f"('{link}', '{formato}', {str(tabular).lower()})" for link, formato, tabular in recursos)
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores}) t(link, formato_limpo, formato_tabular))
                   TO '{(pasta / "recurso" / f"data={HOJE}" / "recurso.parquet").as_posix()}' (FORMAT parquet)""")

    situacoes = [(link, True) for link in quebrados] + [(link, False) for link in testados_ok]
    valores = ", ".join(f"('{link}', {str(q).lower()})" for link, q in situacoes) or "('x', false)"
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores}) t(link, quebrado))
                   TO '{(pasta / "link_status" / f"data={HOJE}" / "link_status.parquet").as_posix()}' (FORMAT parquet)""")


def registrar_tentativa(link, data):
    """Registra no estado que o link foi baixado (com sucesso) em uma data."""
    servidor = link.split("/")[2]
    linha = (data, link, servidor, 200, 100, "h", 1, SCHEMA, "s", None, False, None,
             datetime(data.year, data.month, data.day, 12))
    conteudo_estado.gravar_lote([linha], data)
    conteudo_estado.atualizar_estado(data)


def links_escolhidos(por_servidor):
    """Todos os links escolhidos, sem o agrupamento por servidor."""
    return sorted(link for itens in por_servidor.values() for link, _ in itens)


def test_escolhe_so_formato_tabular_e_http():
    gravar_silver([
        ("https://a.gov.br/1.csv", "CSV", True),
        ("https://a.gov.br/2.pdf", "PDF", False),
        ("ftp://a.gov.br/3.csv", "CSV", True),
    ])

    por_servidor = conteudo_selecao.selecionar(HOJE)

    assert links_escolhidos(por_servidor) == ["https://a.gov.br/1.csv"]
    assert por_servidor["a.gov.br"] == [("https://a.gov.br/1.csv", "CSV")]


def test_links_quebrados_ficam_de_fora_e_nao_testados_entram():
    gravar_silver(
        [
            ("https://a.gov.br/quebrado.csv", "CSV", True),
            ("https://a.gov.br/ok.csv", "CSV", True),
            ("https://a.gov.br/novo.csv", "CSV", True),
        ],
        quebrados=["https://a.gov.br/quebrado.csv"],
        testados_ok=["https://a.gov.br/ok.csv"],
    )

    escolhidos = links_escolhidos(conteudo_selecao.selecionar(HOJE))

    assert escolhidos == ["https://a.gov.br/novo.csv", "https://a.gov.br/ok.csv"]


def test_lido_ha_menos_de_sete_dias_fica_de_fora():
    recente = "https://a.gov.br/recente.csv"
    no_limite = "https://a.gov.br/limite.csv"
    antigo = "https://a.gov.br/antigo.csv"
    gravar_silver([(recente, "CSV", True), (no_limite, "CSV", True), (antigo, "CSV", True)])
    registrar_tentativa(recente, HOJE - timedelta(days=6))
    registrar_tentativa(no_limite, HOJE - timedelta(days=7))
    registrar_tentativa(antigo, HOJE - timedelta(days=30))

    escolhidos = links_escolhidos(conteudo_selecao.selecionar(HOJE))

    # Com 7 dias exatos já vence o ciclo; com 6 ainda não
    assert escolhidos == [antigo, no_limite]


def test_nunca_lidos_vem_antes_dos_lidos_ha_mais_tempo(monkeypatch):
    monkeypatch.setattr(conteudo_selecao, "MAX_POR_SERVIDOR", 2)
    nunca = "https://a.gov.br/nunca.csv"
    velho = "https://a.gov.br/velho.csv"
    menos_velho = "https://a.gov.br/menos_velho.csv"
    gravar_silver([(nunca, "CSV", True), (velho, "CSV", True), (menos_velho, "CSV", True)])
    registrar_tentativa(velho, HOJE - timedelta(days=40))
    registrar_tentativa(menos_velho, HOJE - timedelta(days=10))

    # Só 2 vagas no servidor: ficam o nunca lido e o lido há mais tempo
    escolhidos = links_escolhidos(conteudo_selecao.selecionar(HOJE))

    assert escolhidos == [nunca, velho]


def test_limite_por_servidor_nao_afeta_outros_servidores(monkeypatch):
    monkeypatch.setattr(conteudo_selecao, "MAX_POR_SERVIDOR", 2)
    gravar_silver(
        [(f"https://a.gov.br/{i}.csv", "CSV", True) for i in range(5)]
        + [(f"https://b.gov.br/{i}.csv", "CSV", True) for i in range(1)]
    )

    por_servidor = conteudo_selecao.selecionar(HOJE)

    assert len(por_servidor["a.gov.br"]) == 2
    assert len(por_servidor["b.gov.br"]) == 1
    # O servidor com mais links vem primeiro
    assert list(por_servidor) == ["a.gov.br", "b.gov.br"]


def test_retomada_nao_repete_o_que_ja_foi_tentado_hoje():
    feito = "https://a.gov.br/feito.csv"
    falta = "https://a.gov.br/falta.csv"
    gravar_silver([(feito, "CSV", True), (falta, "CSV", True)])
    registrar_tentativa(feito, HOJE)

    escolhidos = links_escolhidos(conteudo_selecao.selecionar(HOJE))

    assert escolhidos == [falta]


def test_link_repetido_em_varias_bases_aparece_uma_vez():
    gravar_silver([
        ("https://a.gov.br/1.csv", "CSV", True),
        ("https://a.gov.br/1.csv", "CSV", True),
    ])

    assert links_escolhidos(conteudo_selecao.selecionar(HOJE)) == ["https://a.gov.br/1.csv"]


def test_limite_global_para_testes():
    gravar_silver([(f"https://a.gov.br/{i}.csv", "CSV", True) for i in range(10)])

    por_servidor = conteudo_selecao.selecionar(HOJE, limite=3)

    assert len(links_escolhidos(por_servidor)) == 3


def test_sem_a_silver_de_status_dos_links_o_script_para(tmp_path):
    gravar_silver([("https://a.gov.br/1.csv", "CSV", True)])
    conteudo_selecao.arquivo_link_status(HOJE).unlink()

    with pytest.raises(SystemExit):
        conteudo_selecao.selecionar(HOJE)