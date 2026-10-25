"""Testes da escolha de bases do coletor do detalhe (decisão 21).

Os testes montam uma Bronze falsa numa pasta temporária e
conferem quais bases o coletor decide buscar, e por quê.
"""

import json
from datetime import date, datetime

import pytest

import catalogo_detalhe
import catalogo_lista
import portal

ONTEM = date(2026, 10, 24)
HOJE = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def bronze_temporaria(tmp_path, monkeypatch):
    """Aponta a Bronze para uma pasta temporária, longe de dados/ do projeto."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(catalogo_detalhe, "PASTA_LISTA", tmp_path / "dados" / "bronze" / "catalogo_lista")
    monkeypatch.setattr(catalogo_detalhe, "PASTA_DETALHE", tmp_path / "dados" / "bronze" / "catalogo_detalhe")


def gravar_listagem(bases, data):
    """Grava uma listagem falsa: bases é um dicionário {id: ultimaAlteracaoMetadados}."""
    registros = [{"id": id_base, "ultimaAlteracaoMetadados": alteracao} for id_base, alteracao in bases.items()]
    linhas = [(data, 1, len(registros), json.dumps(registros), datetime(2026, 10, 25))]
    catalogo_lista.gravar_bronze(linhas, data)


def gravar_detalhe(id_base, alteracao, data, status_http=200):
    """Grava um detalhe falso já coletado."""
    linha = (data, id_base, "NOVA", alteracao, status_http, "{}", None, datetime(2026, 10, 25))
    catalogo_detalhe.gravar_lote([linha], data)


def motivos(bases):
    """Transforma o resultado em {id: motivo}, mais fácil de conferir."""
    return {id_base: motivo for id_base, _, motivo in bases}


def test_primeira_vez_todas_sao_novas():
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"a": "NOVA", "b": "NOVA"}


def test_detecta_alterada_e_rodizio(monkeypatch):
    # Rodízio de 1 dia: toda base sem mudança entra no rodízio
    monkeypatch.setattr(catalogo_detalhe, "DIAS_RODIZIO", 1)
    gravar_detalhe("a", "2026-01-01", ONTEM)
    gravar_detalhe("b", "2026-02-01", ONTEM)
    gravar_listagem({"a": "2026-01-01", "b": "2026-10-25", "c": "2026-10-25"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"a": "RODIZIO", "b": "ALTERADA", "c": "NOVA"}


def test_falha_anterior_conta_como_nova():
    # A base só falhou ontem: nunca foi coletada com sucesso
    gravar_detalhe("a", "2026-01-01", ONTEM, status_http=404)
    gravar_listagem({"a": "2026-01-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=False)

    assert motivos(bases) == {"a": "NOVA"}


def test_retoma_sem_repetir_o_que_ja_foi_feito_hoje():
    gravar_detalhe("a", "2026-01-01", HOJE)
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=True)

    assert motivos(bases) == {"b": "COMPLETA"}


def test_completo_busca_todas():
    gravar_detalhe("a", "2026-01-01", ONTEM)
    gravar_listagem({"a": "2026-01-01", "b": "2026-02-01"}, HOJE)

    bases = catalogo_detalhe.bases_a_coletar(HOJE, completo=True)

    assert motivos(bases) == {"a": "COMPLETA", "b": "COMPLETA"}


def test_sem_listagem_do_dia_encerra():
    with pytest.raises(SystemExit):
        catalogo_detalhe.bases_a_coletar(HOJE, completo=False)


def test_lotes_viram_partes_numeradas():
    gravar_detalhe("a", "2026-01-01", HOJE)
    gravar_detalhe("b", "2026-01-01", HOJE)

    pasta = catalogo_detalhe.PASTA_DETALHE / f"data={HOJE}"
    nomes = sorted(arquivo.name for arquivo in pasta.glob("*.parquet"))

    assert nomes == ["parte-0001.parquet", "parte-0002.parquet"]
