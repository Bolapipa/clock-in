"""Testes do coletor do painel da CGU (coletor/painel_cgu.py).

Nenhum teste acessa a internet: o catálogo e o SharePoint são simulados.
"""

from datetime import date

import duckdb
import httpx
import pytest

import painel_cgu
import portal


def cliente_falso(resposta):
    """Cliente HTTP que sempre devolve a mesma resposta."""
    return httpx.Client(transport=httpx.MockTransport(lambda requisicao: resposta))


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """Zera a espera entre tentativas para os testes rodarem rápido."""
    monkeypatch.setattr(portal, "ESPERA_FALHA", 0)


def test_link_de_download():
    assert painel_cgu.link_de_download("https://x.com/a?e=1") == "https://x.com/a?e=1&download=1"
    assert painel_cgu.link_de_download("https://x.com/a") == "https://x.com/a?download=1"


def test_links_do_painel_pelo_titulo():
    recursos = [
        {"titulo": "Cronograma de Abertura das Bases", "link": "https://x/c"},
        {"titulo": " Monitoramento da Política de Dados Abertos ", "link": "https://x/m"},
        {"titulo": "Outro arquivo", "link": "https://x/o"},
    ]
    cliente = cliente_falso(httpx.Response(200, json={"recursos": recursos}))

    links = painel_cgu.links_do_painel(cliente)

    assert links == {"cronograma": "https://x/c", "monitoramento": "https://x/m"}


def test_para_se_faltar_um_arquivo():
    recursos = [{"titulo": "Cronograma de Abertura das Bases", "link": "https://x/c"}]
    cliente = cliente_falso(httpx.Response(200, json={"recursos": recursos}))

    with pytest.raises(SystemExit):
        painel_cgu.links_do_painel(cliente)


def test_recusa_pagina_html_no_lugar_do_csv(tmp_path):
    pagina = httpx.Response(200, text="<!DOCTYPE html>", headers={"content-type": "text/html"})
    cliente = cliente_falso(pagina)

    with pytest.raises(SystemExit):
        painel_cgu.baixar_csv(cliente, "https://x/c", tmp_path / "c.csv")


def test_gravar_bronze_guarda_texto_como_veio(tmp_path, monkeypatch):
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    # CSV no formato da CGU: separador ";" e quebra de linha dentro de um campo
    csv = tmp_path / "cronograma.csv"
    # write_bytes grava exatamente estes bytes (write_text no Windows trocaria \n por \r\n)
    csv.write_bytes(
        'Orgao;nome_base;previsao_abertura\n'
        'MAPA - Ministério;"Crédito\nRural";2026-10-01\n'.encode("utf-8")
    )

    arquivo, linhas = painel_cgu.gravar_bronze(csv, "cronograma", date(2026, 10, 25), "Wed, 07 Oct 2026")

    assert linhas == 1
    linha = duckdb.sql(f"SELECT * FROM '{arquivo.as_posix()}'").fetchall()[0]
    assert linha[:3] == ("MAPA - Ministério", "Crédito\nRural", "2026-10-01")
    assert arquivo.parent.name == "data=2026-10-25"
