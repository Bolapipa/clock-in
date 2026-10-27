"""Testes do estado do conteúdo (coletor/conteudo_estado.py).

Grava tentativas falsas na Bronze de uma pasta temporária, atualiza o estado
e confere as datas de leitura e de mudança. Não usa rede.
"""

import json
from datetime import date, datetime

import duckdb
import pytest

import conteudo_estado
import portal

DIA_1 = date(2026, 10, 26)
DIA_2 = date(2026, 11, 2)
DIA_3 = date(2026, 11, 9)

LINK = "https://dados.gov.br/a.csv"
SCHEMA_A = json.dumps([["id", "BIGINT"], ["nome", "VARCHAR"]])
SCHEMA_B = json.dumps([["id", "BIGINT"], ["nome", "VARCHAR"], ["valor", "DOUBLE"]])


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Aponta Bronze e estado para uma pasta temporária."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)


def leitura(data, hash_conteudo, schema=SCHEMA_A, link=LINK, erro_schema=None):
    """Linha da Bronze de um download que deu certo."""
    servidor = link.split("/")[2]
    qtd = len(json.loads(schema)) if schema else None
    schema_hash = f"s-{schema}" if schema else None
    return (data, link, servidor, 200, 100, hash_conteudo, qtd, schema, schema_hash,
            erro_schema, False, None, datetime(data.year, data.month, data.day, 12))


def falha(data, link=LINK):
    """Linha da Bronze de um download que falhou."""
    servidor = link.split("/")[2]
    return (data, link, servidor, 503, None, None, None, None, None, None, None, "TIMEOUT",
            datetime(data.year, data.month, data.day, 12))


def registrar(data, *linhas):
    """Grava as tentativas do dia na Bronze e atualiza o estado."""
    conteudo_estado.gravar_lote(list(linhas), data)
    conteudo_estado.atualizar_estado(data)


def estado_do_link(link=LINK):
    """Lê a linha do estado de um link, como dicionário."""
    resultado = duckdb.sql(
        f"SELECT * FROM '{conteudo_estado.arquivo_estado().as_posix()}' WHERE link = '{link}'"
    )
    colunas = resultado.columns
    return dict(zip(colunas, resultado.fetchall()[0]))


def test_primeira_leitura_nao_conta_como_mudanca():
    registrar(DIA_1, leitura(DIA_1, "h1"))

    estado = estado_do_link()

    assert estado["hash_conteudo"] == "h1"
    assert estado["ultima_leitura"] == DIA_1
    assert estado["ultima_mudanca"] is None
    assert estado["ultima_mudanca_schema"] is None


def test_primeira_leitura_e_o_primeiro_download_que_deu_certo_e_nao_muda_depois():
    # Um download que falha antes de qualquer leitura não define a primeira leitura
    registrar(DIA_1, falha(DIA_1))
    assert estado_do_link()["primeira_leitura"] is None

    registrar(DIA_2, leitura(DIA_2, "h1"))
    registrar(DIA_3, leitura(DIA_3, "h2"))

    estado = estado_do_link()
    assert estado["primeira_leitura"] == DIA_2
    assert estado["ultima_leitura"] == DIA_3


def test_aplicar_o_mesmo_dia_duas_vezes_mantem_a_primeira_leitura():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    conteudo_estado.atualizar_estado(DIA_1)

    assert estado_do_link()["primeira_leitura"] == DIA_1


def test_mesmo_hash_atualiza_a_leitura_mas_nao_a_mudanca():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    registrar(DIA_2, leitura(DIA_2, "h1"))

    estado = estado_do_link()

    assert estado["ultima_leitura"] == DIA_2
    assert estado["ultima_mudanca"] is None


def test_hash_diferente_marca_o_dia_da_mudanca():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    registrar(DIA_2, leitura(DIA_2, "h2"))

    estado = estado_do_link()

    assert estado["hash_conteudo"] == "h2"
    assert estado["ultima_mudanca"] == DIA_2
    # A estrutura não mudou: só o conteúdo
    assert estado["ultima_mudanca_schema"] is None


def test_a_data_da_mudanca_fica_ate_a_proxima_mudanca():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    registrar(DIA_2, leitura(DIA_2, "h2"))
    registrar(DIA_3, leitura(DIA_3, "h2"))

    estado = estado_do_link()

    assert estado["ultima_leitura"] == DIA_3
    assert estado["ultima_mudanca"] == DIA_2


def test_schema_diferente_guarda_o_schema_anterior():
    registrar(DIA_1, leitura(DIA_1, "h1", SCHEMA_A))
    registrar(DIA_2, leitura(DIA_2, "h2", SCHEMA_B))

    estado = estado_do_link()

    assert estado["ultima_mudanca_schema"] == DIA_2
    assert estado["schema_anterior"] == SCHEMA_A
    assert estado["schema"] == SCHEMA_B
    assert estado["qtd_colunas"] == 3


def test_falha_nao_apaga_o_que_ja_se_sabia():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    registrar(DIA_2, falha(DIA_2))

    estado = estado_do_link()

    assert estado["hash_conteudo"] == "h1"
    assert estado["schema"] == SCHEMA_A
    assert estado["ultima_leitura"] == DIA_1
    assert estado["ultima_tentativa"] == DIA_2
    assert estado["erro_tipo"] == "TIMEOUT"


def test_leitura_depois_de_falha_limpa_o_erro():
    registrar(DIA_1, leitura(DIA_1, "h1"))
    registrar(DIA_2, falha(DIA_2))
    registrar(DIA_3, leitura(DIA_3, "h1"))

    estado = estado_do_link()

    assert estado["erro_tipo"] is None
    assert estado["ultima_leitura"] == DIA_3
    # O hash voltou igual: a falha no meio não criou mudança
    assert estado["ultima_mudanca"] is None


def test_schema_ilegivel_mantem_o_ultimo_schema_bom():
    registrar(DIA_1, leitura(DIA_1, "h1", SCHEMA_A))
    # O arquivo mudou, mas a estrutura não pôde ser lida
    registrar(DIA_2, leitura(DIA_2, "h2", schema=None, erro_schema="ILEGIVEL"))
    registrar(DIA_3, leitura(DIA_3, "h3", SCHEMA_A))

    estado = estado_do_link()

    assert estado["ultima_mudanca"] == DIA_3
    # A estrutura voltou igual à última boa: não houve mudança de schema
    assert estado["ultima_mudanca_schema"] is None
    assert estado["schema"] == SCHEMA_A
    assert estado["erro_schema"] is None


def test_aplicar_o_mesmo_dia_duas_vezes_da_o_mesmo_resultado():
    registrar(DIA_1, leitura(DIA_1, "h1", SCHEMA_A))
    registrar(DIA_2, leitura(DIA_2, "h2", SCHEMA_B))
    antes = estado_do_link()

    conteudo_estado.atualizar_estado(DIA_2)

    assert estado_do_link() == antes


def test_link_sem_tentativa_no_dia_continua_como_estava():
    outro = "https://outro.gov.br/b.csv"
    registrar(DIA_1, leitura(DIA_1, "h1"), leitura(DIA_1, "x1", link=outro))
    registrar(DIA_2, leitura(DIA_2, "h2"))

    estado_outro = estado_do_link(outro)

    assert estado_outro["hash_conteudo"] == "x1"
    assert estado_outro["ultima_tentativa"] == DIA_1


def test_gravar_lote_nao_sobrescreve_partes_do_dia():
    conteudo_estado.gravar_lote([leitura(DIA_1, "h1")], DIA_1)
    conteudo_estado.gravar_lote([leitura(DIA_1, "h2", link="https://x.gov.br/c.csv")], DIA_1)

    partes = conteudo_estado.partes_do_dia(DIA_1)

    assert [parte.name for parte in partes] == ["parte-0001.parquet", "parte-0002.parquet"]