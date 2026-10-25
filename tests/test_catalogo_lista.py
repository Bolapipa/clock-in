"""Testes do coletor da listagem (coletor/catalogo_lista.py).

Nenhum teste chama o portal de verdade: as respostas da API
são simuladas com o MockTransport do httpx.
"""

from datetime import date, datetime

import duckdb
import httpx
import pytest

import catalogo_lista


def cliente_falso(respostas):
    """Cria um cliente HTTP que devolve as respostas da lista, em ordem."""
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao)
        return respostas[len(chamadas) - 1]

    cliente = httpx.Client(transport=httpx.MockTransport(responder))
    return cliente, chamadas


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    """Zera a espera entre tentativas para os testes rodarem rápido."""
    monkeypatch.setattr(catalogo_lista, "ESPERA_FALHA", 0)


def test_sucesso_na_primeira_tentativa():
    cliente, chamadas = cliente_falso([httpx.Response(200, json=[{"id": "1"}])])

    resposta = catalogo_lista.buscar_pagina(cliente, 1)

    assert resposta.status_code == 200
    assert len(chamadas) == 1
    # Confere os parâmetros enviados à API
    assert chamadas[0].url.params["pagina"] == "1"
    assert chamadas[0].url.params["dadosAbertos"] == "true"


def test_tenta_de_novo_quando_servidor_falha():
    cliente, chamadas = cliente_falso([
        httpx.Response(503),
        httpx.Response(200, json=[]),
    ])

    resposta = catalogo_lista.buscar_pagina(cliente, 1)

    assert resposta.status_code == 200
    assert len(chamadas) == 2


def test_nao_repete_erro_de_chave():
    cliente, chamadas = cliente_falso([httpx.Response(401)])

    resposta = catalogo_lista.buscar_pagina(cliente, 1)

    # 401 volta na hora, sem novas tentativas
    assert resposta.status_code == 401
    assert len(chamadas) == 1


def test_desiste_depois_de_tres_falhas():
    cliente, chamadas = cliente_falso([httpx.Response(503)] * 3)

    with pytest.raises(SystemExit):
        catalogo_lista.buscar_pagina(cliente, 1)

    assert len(chamadas) == 3


def test_gravar_bronze_nao_duplica(tmp_path, monkeypatch):
    # Grava numa pasta temporária, não em dados/ do projeto
    monkeypatch.setattr(catalogo_lista, "RAIZ", tmp_path)
    linhas = [
        (date(2026, 10, 25), 1, 15, '[{"id": "a"}]', datetime(2026, 10, 25, 12, 0)),
        (date(2026, 10, 25), 2, 7, '[{"id": "b"}]', datetime(2026, 10, 25, 12, 1)),
    ]

    # Grava duas vezes no mesmo dia
    catalogo_lista.gravar_bronze(linhas, date(2026, 10, 25))
    arquivo = catalogo_lista.gravar_bronze(linhas, date(2026, 10, 25))

    # A partição do dia tem as 2 páginas, não 4
    assert arquivo.parent.name == "data=2026-10-25"
    total = duckdb.sql(f"SELECT COUNT(*) FROM '{arquivo.as_posix()}'").fetchall()[0][0]
    assert total == 2
