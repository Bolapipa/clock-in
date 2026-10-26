"""Testes do estado do detalhe (coletor/estado.py).

Grava tentativas falsas na Bronze, atualiza o estado e confere
o que ele guarda para o dia seguinte.
"""

from datetime import date, datetime

import duckdb
import pytest

import catalogo_detalhe
import estado
import portal

DIA_1 = date(2026, 10, 24)
DIA_2 = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def raiz_temporaria(tmp_path, monkeypatch):
    """Aponta Bronze e estado para uma pasta temporária."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(catalogo_detalhe, "PASTA_DETALHE", tmp_path / "dados" / "bronze" / "catalogo_detalhe")


def tentativa(id_base, data, status_http, payload=None, alteracao="2026-01-01", hora=12):
    """Grava uma tentativa de buscar o detalhe na Bronze."""
    erro = None if status_http == 200 else f"erro {status_http}"
    linha = (data, id_base, "NOVA", alteracao, status_http, payload, erro, datetime(data.year, data.month, data.day, hora))
    catalogo_detalhe.gravar_lote([linha], data)


def ler_estado():
    """Lê o arquivo de estado como {id: linha}."""
    resultado = duckdb.sql(f"SELECT * FROM '{estado.arquivo_estado().as_posix()}'")
    colunas = resultado.columns
    return {linha[0]: dict(zip(colunas, linha)) for linha in resultado.fetchall()}


def test_sucesso_vira_versao_atual():
    tentativa("a", DIA_1, 200, payload='{"v": 1}')
    estado.atualizar(DIA_1)

    linha = ler_estado()["a"]
    assert linha["payload"] == '{"v": 1}'
    assert linha["data_coleta"] == DIA_1
    assert linha["falhas_seguidas"] == 0


def test_falha_mantem_a_ultima_versao_boa():
    tentativa("a", DIA_1, 200, payload='{"v": 1}')
    estado.atualizar(DIA_1)
    tentativa("a", DIA_2, 503)
    estado.atualizar(DIA_2)

    linha = ler_estado()["a"]
    assert linha["payload"] == '{"v": 1}'
    assert linha["data_coleta"] == DIA_1
    assert linha["falhas_seguidas"] == 1
    assert linha["ultima_tentativa"] == DIA_2
    assert linha["ultimo_erro"] == "erro 503"


def test_atualizar_duas_vezes_no_dia_nao_conta_falha_em_dobro():
    tentativa("a", DIA_1, 400)
    estado.atualizar(DIA_1)
    estado.atualizar(DIA_1)

    assert ler_estado()["a"]["falhas_seguidas"] == 1


def test_falhas_somam_por_dia_e_sucesso_zera():
    tentativa("a", DIA_1, 400)
    estado.atualizar(DIA_1)
    tentativa("a", DIA_2, 400)
    estado.atualizar(DIA_2)
    assert ler_estado()["a"]["falhas_seguidas"] == 2

    tentativa("a", date(2026, 10, 26), 200, payload="{}")
    estado.atualizar(date(2026, 10, 26))
    assert ler_estado()["a"]["falhas_seguidas"] == 0


def test_sucesso_no_mesmo_dia_vence_a_falha():
    tentativa("a", DIA_1, 503, hora=10)
    tentativa("a", DIA_1, 200, payload="{}", hora=11)
    estado.atualizar(DIA_1)

    linha = ler_estado()["a"]
    assert linha["payload"] == "{}"
    assert linha["falhas_seguidas"] == 0


def test_reconstruir_da_o_mesmo_que_atualizar_dia_a_dia():
    tentativa("a", DIA_1, 200, payload='{"v": 1}')
    tentativa("b", DIA_1, 400)
    estado.atualizar(DIA_1)
    tentativa("a", DIA_2, 503)
    tentativa("b", DIA_2, 200, payload='{"v": 2}')
    estado.atualizar(DIA_2)
    dia_a_dia = ler_estado()

    estado.arquivo_estado().unlink()
    estado.reconstruir()

    assert ler_estado() == dia_a_dia