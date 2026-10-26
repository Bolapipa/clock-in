"""Testes do coletor do detalhe: escolha das bases (decisão 21) e parada de segurança.

Os testes montam uma Bronze e um estado falsos numa pasta temporária e
conferem quais bases o coletor decide buscar, e por quê.
"""

import json
import sys
from datetime import date, datetime, timedelta

import duckdb
import httpx
import pytest

import catalogo_detalhe
import catalogo_lista
import estado
import portal

ONTEM = date(2026, 10, 24)
HOJE = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def bronze_temporaria(tmp_path, monkeypatch):
    """Aponta Bronze e estado para uma pasta temporária, longe de dados/ do projeto."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(catalogo_detalhe, "PASTA_LISTA", tmp_path / "dados" / "bronze" / "catalogo_lista")
    monkeypatch.setattr(catalogo_detalhe, "PASTA_DETALHE", tmp_path / "dados" / "bronze" / "catalogo_detalhe")


def gravar_listagem(bases, data):
    """Grava uma listagem falsa: bases é um dicionário {id: ultimaAlteracaoMetadados}."""
    registros = [{"id": id_base, "ultimaAlteracaoMetadados": alteracao} for id_base, alteracao in bases.items()]
    linhas = [(data, 1, len(registros), json.dumps(registros), datetime(2026, 10, 25))]
    catalogo_lista.gravar_bronze(linhas, data)


def coletar(id_base, alteracao, data, status_http=200):
    """Simula a coleta do detalhe de uma base num dia e atualiza o estado."""
    payload = "{}" if status_http == 200 else None
    linha = (data, id_base, "NOVA", alteracao, status_http, payload, None, datetime(data.year, data.month, data.day))
    catalogo_detalhe.gravar_lote([linha], data)
    estado.atualizar(data)


def motivos(bases):
    """Transforma o resultado em {id: motivo}, mais fácil de conferir."""
    return {id_base: motivo for id_base, _, motivo in bases}


def test_primeira_vez_todas_sao_novas():
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"a": "NOVA", "b": "NOVA"}


def test_detecta_alterada_e_rodizio(monkeypatch):
    # Rodízio de 1 dia: todas as bases sem mudança entram no rodízio
    monkeypatch.setattr(catalogo_detalhe, "DIAS_RODIZIO", 1)
    coletar("a", "2026-01-01", ONTEM)
    coletar("b", "2026-02-01", ONTEM)
    gravar_listagem({"a": "2026-01-01", "b": "2026-10-25", "c": "2026-10-25"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"a": "RODIZIO", "b": "ALTERADA", "c": "NOVA"}


def test_rodizio_escolhe_as_coletas_mais_antigas(monkeypatch):
    # 3 bases e rodízio de 3 dias: 1 base por dia, a de coleta mais antiga
    monkeypatch.setattr(catalogo_detalhe, "DIAS_RODIZIO", 3)
    coletar("a", "x", date(2026, 10, 22))
    coletar("b", "x", date(2026, 10, 20))
    coletar("c", "x", date(2026, 10, 21))
    gravar_listagem({"a": "x", "b": "x", "c": "x"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"b": "RODIZIO"}


def test_falha_espera_cada_vez_mais():
    # Duas falhas seguidas: a base espera 2 dias depois da última
    coletar("a", "x", date(2026, 10, 20), status_http=400)
    coletar("a", "x", date(2026, 10, 21), status_http=400)

    gravar_listagem({"a": "x"}, date(2026, 10, 22))
    assert motivos(catalogo_detalhe.bases_a_coletar(date(2026, 10, 22), completo=False)) == {}

    gravar_listagem({"a": "x"}, date(2026, 10, 23))
    assert motivos(catalogo_detalhe.bases_a_coletar(date(2026, 10, 23), completo=False)) == {"a": "NOVA"}


def test_espera_nunca_passa_de_30_dias():
    # Simula 10 dias seguidos de falha: a espera seria 512 dias, mas o limite é 30
    dia = date(2026, 9, 1)
    for _ in range(10):
        coletar("a", "x", dia, status_http=400)
        dia += timedelta(days=1)
    ultima_falha = dia - timedelta(days=1)

    gravar_listagem({"a": "x"}, ultima_falha + timedelta(days=30))
    bases = catalogo_detalhe.bases_a_coletar(ultima_falha + timedelta(days=30), completo=False)

    assert motivos(bases) == {"a": "NOVA"}


def test_retoma_sem_repetir_o_que_ja_foi_feito_hoje():
    coletar("a", "2026-01-01", HOJE)
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=True)

    assert motivos(bases) == {"b": "COMPLETA"}


def test_completo_busca_todas():
    coletar("a", "2026-01-01", ONTEM)
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=True)

    assert motivos(bases) == {"a": "COMPLETA", "b": "COMPLETA"}


def test_sem_listagem_do_dia_encerra():
    with pytest.raises(SystemExit):
        catalogo_detalhe.bases_a_coletar(HOJE, completo=False)


def test_partes_numeradas_sem_sobrescrever():
    linha = (HOJE, "a", "NOVA", None, 200, "{}", None, datetime(2026, 10, 25))
    for _ in range(3):
        catalogo_detalhe.gravar_lote([linha], HOJE)
    pasta = catalogo_detalhe.PASTA_DETALHE / f"data={HOJE}"

    # Some a parte do meio: a próxima deve ser a 0004, sem sobrescrever a 0003
    (pasta / "parte-0002.parquet").unlink()
    catalogo_detalhe.gravar_lote([linha], HOJE)

    nomes = sorted(arquivo.name for arquivo in pasta.iterdir())
    assert nomes == ["parte-0001.parquet", "parte-0003.parquet", "parte-0004.parquet"]


def test_para_quando_o_portal_cai(monkeypatch):
    # Portal sempre devolvendo 503: o coletor para depois de 3 falhas seguidas
    monkeypatch.setattr(catalogo_detalhe, "MAX_FALHAS_SEGUIDAS", 3)
    monkeypatch.setattr(portal, "ESPERA_FALHA", 0)
    monkeypatch.setattr(portal, "PAUSA", 0)
    monkeypatch.setattr(portal, "criar_cliente",
                        lambda: httpx.Client(transport=httpx.MockTransport(lambda requisicao: httpx.Response(503))))
    monkeypatch.setattr(sys, "argv", ["catalogo_detalhe.py", "--data", str(HOJE)])
    gravar_listagem({f"base-{i}": "x" for i in range(10)}, HOJE)

    with pytest.raises(SystemExit):
        catalogo_detalhe.main()

    # Gravou as 3 tentativas e atualizou o estado antes de parar
    pasta = (catalogo_detalhe.PASTA_DETALHE / f"data={HOJE}" / "*.parquet").as_posix()
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{pasta}'").fetchall()[0][0] == 3
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{estado.arquivo_estado().as_posix()}'").fetchall()[0][0] == 3