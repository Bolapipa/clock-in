"""Testes da camada Silver (coletor/silver.py e arquivos de sql/).

Monta uma Bronze falsa numa pasta temporária, gera a Silver
e confere as regras de limpeza.
"""

import json
from datetime import date, datetime

import duckdb
import pytest

import catalogo_detalhe
import catalogo_lista
import portal
import silver

HOJE = date(2026, 10, 25)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Bronze e Silver para uma pasta temporária (os SQLs continuam os do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(catalogo_detalhe, "PASTA_DETALHE", tmp_path / "dados" / "bronze" / "catalogo_detalhe")
    monkeypatch.setattr(silver, "PASTA_BRONZE", tmp_path / "dados" / "bronze")
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")


def gravar_listagem(registros, data=HOJE):
    """Grava uma listagem falsa com os registros dados."""
    linhas = [(data, 1, len(registros), json.dumps(registros), datetime(2026, 10, 25))]
    catalogo_lista.gravar_bronze(linhas, data)


def gravar_detalhe(payload, data=HOJE, coletado_em=datetime(2026, 10, 25, 12, 0)):
    """Grava um detalhe falso que deu certo."""
    linha = (data, payload["id"], "NOVA", None, 200, json.dumps(payload), None, coletado_em)
    catalogo_detalhe.gravar_lote([linha], data)


def gerar_silver(nome):
    """Gera uma tabela da Silver e devolve as linhas como dicionários."""
    con = duckdb.connect()
    silver.criar_views_bronze(con, HOJE)
    arquivo, _ = silver.gerar_tabela(con, nome, silver.TABELAS[nome], HOJE)
    resultado = con.execute(f"SELECT * FROM '{arquivo.as_posix()}'")
    colunas = [c[0] for c in resultado.description]
    linhas = [dict(zip(colunas, linha)) for linha in resultado.fetchall()]
    con.close()
    return {linha.get("id") or linha.get("recurso_id"): linha for linha in linhas}


def test_converte_datas_e_trata_indisponivel():
    gravar_listagem([
        {"id": "a", "ultimaAtualizacaoDados": "14/07/2026 17:50:30"},
        {"id": "b", "ultimaAtualizacaoDados": "Indisponível"},
    ])
    gravar_detalhe({"id": "a"})

    bases = gerar_silver("base")

    assert bases["a"]["ultima_atualizacao_dados"] == datetime(2026, 7, 14, 17, 50, 30)
    assert bases["b"]["ultima_atualizacao_dados"] is None


def test_periodicidade_vazia_vira_nao_declarada():
    gravar_listagem([{"id": "a"}, {"id": "b"}, {"id": "c"}])
    gravar_detalhe({"id": "a", "periodicidade": "MENSAL"})
    gravar_detalhe({"id": "b", "periodicidade": None})

    bases = gerar_silver("base")

    assert bases["a"]["periodicidade"] == "MENSAL"
    assert bases["a"]["periodicidade_comparavel"] is True
    assert bases["b"]["periodicidade"] == "NAO_DECLARADA"
    # Não declarada é "não comparável" (False), e não vazio
    assert bases["b"]["periodicidade_comparavel"] is False
    # Sem detalhe ainda: periodicidade desconhecida, não "não declarada"
    assert bases["c"]["periodicidade"] is None
    assert bases["c"]["periodicidade_comparavel"] is None
    assert bases["c"]["tem_detalhe"] is False


def test_usa_o_detalhe_mais_recente():
    gravar_listagem([{"id": "a"}])
    gravar_detalhe({"id": "a", "periodicidade": "ANUAL"}, date(2026, 10, 24), datetime(2026, 10, 24, 12, 0))
    gravar_detalhe({"id": "a", "periodicidade": "MENSAL"}, HOJE, datetime(2026, 10, 25, 12, 0))

    bases = gerar_silver("base")

    assert bases["a"]["periodicidade"] == "MENSAL"
    assert bases["a"]["data_detalhe"] == HOJE


def test_recursos_viram_uma_linha_por_link():
    gravar_listagem([{"id": "a"}])
    gravar_detalhe({"id": "a", "recursos": [
        {"id": "r1", "link": " https://x.gov.br/a.csv ", "formato": "csv", "dataUltimaAtualizacaoArquivo": "29/01/2024"},
        {"id": "r2", "link": "https://x.gov.br/b.pdf", "formato": "PDF", "dataUltimaAtualizacaoArquivo": None},
    ]})

    recursos = gerar_silver("recurso")

    assert set(recursos) == {"r1", "r2"}
    # Espaços removidos e formato em maiúsculas
    assert recursos["r1"]["link"] == "https://x.gov.br/a.csv"
    assert recursos["r1"]["formato"] == "CSV"
    assert recursos["r1"]["data_ultima_atualizacao_arquivo"] == date(2024, 1, 29)
    assert recursos["r2"]["data_ultima_atualizacao_arquivo"] is None


def test_base_que_saiu_da_listagem_nao_gera_recursos():
    # A base "b" tem detalhe, mas não está mais na listagem do dia
    gravar_listagem([{"id": "a"}])
    gravar_detalhe({"id": "a", "recursos": [{"id": "r1", "link": "https://x.gov.br/a.csv"}]})
    gravar_detalhe({"id": "b", "recursos": [{"id": "r2", "link": "https://x.gov.br/b.csv"}]})

    recursos = gerar_silver("recurso")

    assert set(recursos) == {"r1"}
