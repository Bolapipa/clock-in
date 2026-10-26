"""Testes da Silver do conteúdo (coletor/silver_conteudo.py, sql/silver_versao_conteudo.sql e sql/silver_mudanca_schema.sql).

Grava tentativas falsas, atualiza o estado do conteúdo numa pasta temporária,
gera a Silver e confere as mudanças de conteúdo e de estrutura. Não usa rede.
"""

import json
from datetime import date, datetime

import duckdb
import pytest

import conteudo_estado
import portal
import silver
import silver_conteudo

DIA_1 = date(2026, 10, 26)
DIA_2 = date(2026, 11, 2)

LINK = "https://dados.gov.br/a.csv"


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta estado e Silver para uma pasta temporária (os SQLs continuam os do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")


def esquema(*colunas):
    """Monta o texto JSON do schema: esquema(("id", "BIGINT"), ("nome", "VARCHAR"))."""
    return json.dumps([list(coluna) for coluna in colunas])


def leitura(data, hash_conteudo, schema, link=LINK):
    """Linha da Bronze de um download que deu certo."""
    servidor = link.split("/")[2]
    return (data, link, servidor, 200, 100, hash_conteudo, len(json.loads(schema)), schema, f"s-{schema}",
            None, False, None, datetime(data.year, data.month, data.day, 12))


def registrar(data, *linhas):
    """Grava as tentativas do dia na Bronze e atualiza o estado."""
    conteudo_estado.gravar_lote(list(linhas), data)
    conteudo_estado.atualizar_estado(data)


def gerar(data):
    """Gera a Silver do conteúdo de um dia e devolve (versao_conteudo, mudanca_schema) como listas de dicionários."""
    con = duckdb.connect()
    silver_conteudo.criar_views_entrada(con, data)
    for nome, arquivo_sql in silver_conteudo.TABELAS.items():
        silver.gerar_tabela(con, nome, arquivo_sql, data)

    def ler(tabela):
        resultado = con.execute(f"SELECT * FROM silver_{tabela}")
        colunas = [c[0] for c in resultado.description]
        return [dict(zip(colunas, linha)) for linha in resultado.fetchall()]

    saida = ler("versao_conteudo"), ler("mudanca_schema")
    con.close()
    return saida


def mudancas_do_dia(schema_antes, schema_depois):
    """Registra o schema 'antes' num dia e o 'depois' no outro; devolve as mudanças geradas no segundo dia."""
    registrar(DIA_1, leitura(DIA_1, "h1", schema_antes))
    registrar(DIA_2, leitura(DIA_2, "h2", schema_depois))
    _, mudancas = gerar(DIA_2)
    return [(m["tipo_mudanca"], m["coluna"], m["coluna_depois"], m["tipo_antes"], m["tipo_depois"]) for m in mudancas]


def test_versao_conteudo_tem_so_os_arquivos_lidos_no_dia():
    outro = "https://outro.gov.br/b.csv"
    schema = esquema(("id", "BIGINT"))
    registrar(DIA_1, leitura(DIA_1, "h1", schema), leitura(DIA_1, "x1", schema, link=outro))
    # No segundo dia só o primeiro link é lido
    registrar(DIA_2, leitura(DIA_2, "h2", schema))

    versoes, _ = gerar(DIA_2)

    assert [v["link"] for v in versoes] == [LINK]
    assert versoes[0]["data_coleta"] == DIA_2
    assert versoes[0]["hash_conteudo"] == "h2"


def test_versao_conteudo_marca_quem_mudou_de_conteudo_e_de_estrutura():
    mesmo = "https://x.gov.br/igual.csv"
    mudou = "https://x.gov.br/mudou.csv"
    antes, depois = esquema(("id", "BIGINT")), esquema(("id", "BIGINT"), ("nome", "VARCHAR"))
    registrar(DIA_1, leitura(DIA_1, "i1", antes, link=mesmo), leitura(DIA_1, "m1", antes, link=mudou))
    registrar(DIA_2, leitura(DIA_2, "i1", antes, link=mesmo), leitura(DIA_2, "m2", depois, link=mudou))

    versoes, _ = gerar(DIA_2)
    por_link = {v["link"]: v for v in versoes}

    assert (por_link[mesmo]["mudou_conteudo"], por_link[mesmo]["mudou_schema"]) == (False, False)
    assert (por_link[mudou]["mudou_conteudo"], por_link[mudou]["mudou_schema"]) == (True, True)


def test_primeira_leitura_nao_aparece_como_mudanca():
    registrar(DIA_1, leitura(DIA_1, "h1", esquema(("id", "BIGINT"))))

    versoes, mudancas = gerar(DIA_1)

    assert versoes[0]["mudou_conteudo"] is False
    assert versoes[0]["mudou_schema"] is False
    assert mudancas == []


def test_coluna_adicionada():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT")),
        esquema(("id", "BIGINT"), ("valor", "DOUBLE")),
    )

    assert resultado == [("ADICIONADA", "valor", None, None, "DOUBLE")]


def test_coluna_removida():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT"), ("valor", "DOUBLE")),
        esquema(("id", "BIGINT")),
    )

    assert resultado == [("REMOVIDA", "valor", None, "DOUBLE", None)]


def test_tipo_alterado():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT"), ("cep", "BIGINT")),
        esquema(("id", "BIGINT"), ("cep", "VARCHAR")),
    )

    assert resultado == [("TIPO_ALTERADO", "cep", None, "BIGINT", "VARCHAR")]


def test_coluna_renomeada_provavel_na_mesma_posicao_e_tipo():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT"), ("nome", "VARCHAR")),
        esquema(("id", "BIGINT"), ("nome_completo", "VARCHAR")),
    )

    # Uma linha só, e não uma REMOVIDA mais uma ADICIONADA
    assert resultado == [("RENOMEADA_PROVAVEL", "nome", "nome_completo", "VARCHAR", "VARCHAR")]


def test_troca_de_coluna_com_tipo_diferente_nao_e_renomeacao():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT"), ("nome", "VARCHAR")),
        esquema(("id", "BIGINT"), ("valor", "DOUBLE")),
    )

    assert sorted(resultado) == [
        ("ADICIONADA", "valor", None, None, "DOUBLE"),
        ("REMOVIDA", "nome", None, "VARCHAR", None),
    ]


def test_mesmas_colunas_em_outra_ordem():
    resultado = mudancas_do_dia(
        esquema(("id", "BIGINT"), ("nome", "VARCHAR")),
        esquema(("nome", "VARCHAR"), ("id", "BIGINT")),
    )

    assert resultado == [("ORDEM_ALTERADA", None, None, None, None)]


def test_mudanca_de_estrutura_de_outro_dia_nao_entra():
    registrar(DIA_1, leitura(DIA_1, "h1", esquema(("id", "BIGINT"))))
    registrar(DIA_2, leitura(DIA_2, "h2", esquema(("id", "BIGINT"), ("valor", "DOUBLE"))))

    # A mudança foi no dia 2: na Silver do dia 1 ela não existe
    _, mudancas = gerar(DIA_1)

    assert mudancas == []