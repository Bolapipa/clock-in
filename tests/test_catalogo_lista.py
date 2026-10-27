"""Testes do coletor da listagem (coletor/catalogo_lista.py).

Nenhum teste chama o portal de verdade: as respostas da API
são simuladas com o MockTransport do httpx.
"""

import sys
from datetime import date, datetime

import duckdb
import httpx
import pytest

import catalogo_lista
import portal


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
    monkeypatch.setattr(portal, "ESPERA_FALHA", 0)


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
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
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


# --- Proteções da listagem (etapa C) ---

ANTES = date(2026, 10, 25)
HOJE = date(2026, 10, 26)


def gravar_listagem(data, bases):
    """Grava uma listagem falsa de um dia, com 'bases' bases numa página só."""
    linha = (data, 1, bases, "[]", datetime(data.year, data.month, data.day, 12, 0))
    return catalogo_lista.gravar_bronze([linha], data)


def portal_falso(monkeypatch, tmp_path, bases_por_pagina, argumentos=()):
    """Aponta a Bronze para tmp_path e simula a API: uma página por item de bases_por_pagina."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(portal, "PAUSA", 0)

    def responder(requisicao):
        pagina = int(requisicao.url.params["pagina"])
        if pagina <= len(bases_por_pagina):
            registros = [{"id": f"b{pagina}-{i}"} for i in range(bases_por_pagina[pagina - 1])]
            return httpx.Response(200, json=registros)
        return httpx.Response(200, json=[])

    monkeypatch.setattr(portal, "criar_cliente", lambda: httpx.Client(transport=httpx.MockTransport(responder)))
    monkeypatch.setattr(sys, "argv", ["catalogo_lista.py", "--data", str(HOJE), *argumentos])


def total_gravado(data):
    arquivo = catalogo_lista.arquivo_da_listagem(data)
    return duckdb.sql(f"SELECT SUM(qtd_registros) FROM '{arquivo.as_posix()}'").fetchall()[0][0]


def test_resposta_que_nao_e_json_encerra():
    pagina = httpx.Response(200, text="<html>Manutencao</html>")

    with pytest.raises(SystemExit):
        catalogo_lista.ler_registros(pagina, 3)


def test_resposta_que_nao_e_lista_encerra():
    with pytest.raises(SystemExit):
        catalogo_lista.ler_registros(httpx.Response(200, json={"erro": "x"}), 3)


def test_listagem_anterior_ignora_o_proprio_dia_e_os_futuros(tmp_path, monkeypatch):
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    gravar_listagem(date(2026, 10, 24), 100)
    gravar_listagem(ANTES, 200)
    gravar_listagem(HOJE, 300)
    gravar_listagem(date(2026, 10, 27), 400)

    assert catalogo_lista.listagem_anterior(HOJE) == (ANTES, 200)


def test_sem_listagem_anterior_aceita_a_primeira(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [10])

    catalogo_lista.main()

    assert total_gravado(HOJE) == 10


def test_recusa_listagem_bem_menor_que_a_anterior(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [10])
    gravar_listagem(ANTES, 100)

    with pytest.raises(SystemExit):
        catalogo_lista.main()

    # Nada foi gravado para hoje
    assert not catalogo_lista.arquivo_da_listagem(HOJE).exists()


def test_aceita_listagem_a_partir_de_95_por_cento(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [95])
    gravar_listagem(ANTES, 100)

    catalogo_lista.main()

    assert total_gravado(HOJE) == 95


def test_aceitar_queda_grava_mesmo_assim(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [10], ["--aceitar-queda"])
    gravar_listagem(ANTES, 100)

    catalogo_lista.main()

    assert total_gravado(HOJE) == 10


def test_teste_parcial_nao_sobrescreve_listagem_do_dia(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [5, 5], ["--max-paginas", "1"])
    gravar_listagem(HOJE, 100)

    with pytest.raises(SystemExit):
        catalogo_lista.main()

    # A listagem completa continua com as 100 bases
    assert total_gravado(HOJE) == 100


def test_teste_parcial_grava_quando_nao_ha_listagem_do_dia(tmp_path, monkeypatch):
    portal_falso(monkeypatch, tmp_path, [5, 5], ["--max-paginas", "1"])
    gravar_listagem(ANTES, 1000)

    catalogo_lista.main()

    # O teste parcial não passa pela conferência de tamanho
    assert total_gravado(HOJE) == 5