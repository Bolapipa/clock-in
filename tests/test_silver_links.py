"""Testes da Silver da saúde dos links (coletor/silver_links.py e sql/silver_link_status.sql, sql/silver_base_saude.sql).

Monta uma Silver e um estado de links falsos numa pasta temporária,
gera as tabelas e confere as regras de "quebrado" e "fora do ar".
"""

from datetime import date, datetime

import duckdb
import pytest

import links
import portal
import silver
import silver_links

DIA_1 = date(2026, 10, 24)
DIA_2 = date(2026, 10, 25)
HOJE = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Silver e estado para uma pasta temporária (os SQLs continuam os do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")


def gravar_silver(bases, recursos):
    """Grava silver/base (lista de ids) e silver/recurso (lista de (id_base, link)) falsas."""
    pasta = silver.PASTA_SILVER
    (pasta / "base" / f"data={HOJE}").mkdir(parents=True)
    (pasta / "recurso" / f"data={HOJE}").mkdir(parents=True)

    valores_base = ", ".join(f"('{id_base}', DATE '{HOJE}')" for id_base in bases)
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores_base}) t(id, data_coleta))
                   TO '{(pasta / "base" / f"data={HOJE}" / "base.parquet").as_posix()}' (FORMAT parquet)""")

    valores_recurso = ", ".join(f"('{id_base}', '{link}', DATE '{HOJE}')" for id_base, link in recursos)
    duckdb.sql(f"""COPY (SELECT * FROM (VALUES {valores_recurso}) t(id_base, link, data_coleta))
                   TO '{(pasta / "recurso" / f"data={HOJE}" / "recurso.parquet").as_posix()}' (FORMAT parquet)""")


def registrar_teste(link, data, status_http, etag=None):
    """Registra um teste de link na Bronze e atualiza o estado do dia."""
    servidor = link.split("/")[2]
    linha = (data, link, servidor, "HEAD", status_http, None, None, None, None, etag, 50, None, None,
             datetime(data.year, data.month, data.day, 12))
    links.gravar_lote([linha], data)
    links.atualizar_estado(data)


def gerar():
    """Gera a Silver dos links e devolve (link_status, base_saude), cada uma como {chave: linha}."""
    con = duckdb.connect()
    silver_links.criar_views_entrada(con, HOJE)
    for nome, arquivo_sql in silver_links.TABELAS.items():
        silver.gerar_tabela(con, nome, arquivo_sql, HOJE)

    def ler(tabela, chave):
        resultado = con.execute(f"SELECT * FROM silver_{tabela}")
        colunas = [c[0] for c in resultado.description]
        return {linha[colunas.index(chave)]: dict(zip(colunas, linha)) for linha in resultado.fetchall()}

    saida = ler("link_status", "link"), ler("base_saude", "id")
    con.close()
    return saida


def quebrar(link):
    """Deixa um link com 3 falhas em 3 dias seguidos, ou seja, quebrado."""
    registrar_teste(link, DIA_1, 404)
    registrar_teste(link, DIA_2, 404)
    registrar_teste(link, HOJE, 404)


def test_link_quebrado_depois_de_tres_falhas_com_a_data_de_inicio():
    gravar_silver(["a"], [("a", "https://x.gov.br/1")])
    quebrar("https://x.gov.br/1")

    status, _ = gerar()

    linha = status["https://x.gov.br/1"]
    assert linha["quebrado"] is True
    assert linha["quebrado_desde"] == DIA_1
    assert linha["falhas_seguidas"] == 3
    assert linha["ultimo_status_http"] == 404


def test_link_status_traz_os_metadados_e_o_dia_em_que_mudaram():
    gravar_silver(["a"], [("a", "https://x.gov.br/1")])
    registrar_teste("https://x.gov.br/1", DIA_2, 200, etag='"v1"')
    registrar_teste("https://x.gov.br/1", HOJE, 200, etag='"v2"')

    status, _ = gerar()

    linha = status["https://x.gov.br/1"]
    assert linha["etag"] == '"v2"'
    assert linha["ultima_mudanca_metadados"] == HOJE


def test_link_com_duas_falhas_ainda_nao_esta_quebrado():
    gravar_silver(["a"], [("a", "https://x.gov.br/1")])
    registrar_teste("https://x.gov.br/1", DIA_2, 503)
    registrar_teste("https://x.gov.br/1", HOJE, 503)

    status, saude = gerar()

    assert status["https://x.gov.br/1"]["quebrado"] is False
    assert status["https://x.gov.br/1"]["quebrado_desde"] is None
    assert saude["a"]["qtd_em_observacao"] == 1
    assert saude["a"]["fora_do_ar"] is False


def test_base_fora_do_ar_so_quando_todos_os_links_estao_quebrados():
    gravar_silver(
        ["tudo_quebrado", "metade", "sem_links"],
        [("tudo_quebrado", "https://x.gov.br/1"), ("tudo_quebrado", "https://x.gov.br/2"),
         ("metade", "https://x.gov.br/3"), ("metade", "https://x.gov.br/4")],
    )
    for link in ("https://x.gov.br/1", "https://x.gov.br/2", "https://x.gov.br/3"):
        quebrar(link)
    registrar_teste("https://x.gov.br/4", HOJE, 200)

    _, saude = gerar()

    assert saude["tudo_quebrado"]["fora_do_ar"] is True
    assert saude["tudo_quebrado"]["qtd_quebrados"] == 2
    assert saude["metade"]["fora_do_ar"] is False
    assert (saude["metade"]["qtd_quebrados"], saude["metade"]["qtd_ok"]) == (1, 1)
    # Base sem links aparece, mas nunca fica "fora do ar"
    assert saude["sem_links"]["qtd_links"] == 0
    assert saude["sem_links"]["fora_do_ar"] is False


def test_link_ainda_nao_testado_nao_conta_como_quebrado():
    gravar_silver(["a"], [("a", "https://x.gov.br/1"), ("a", "https://x.gov.br/2")])
    quebrar("https://x.gov.br/1")

    _, saude = gerar()

    # O segundo link nunca foi testado: a base não pode ser dada como fora do ar
    assert saude["a"]["qtd_links"] == 2
    assert saude["a"]["qtd_testados"] == 1
    assert saude["a"]["fora_do_ar"] is False


def test_link_repetido_na_mesma_base_conta_uma_vez_e_em_duas_bases_conta_nas_duas():
    gravar_silver(
        ["a", "b"],
        [("a", "https://x.gov.br/1"), ("a", "https://x.gov.br/1"), ("b", "https://x.gov.br/1")],
    )
    quebrar("https://x.gov.br/1")

    _, saude = gerar()

    assert saude["a"]["qtd_links"] == 1
    assert saude["b"]["qtd_links"] == 1
    assert saude["a"]["fora_do_ar"] and saude["b"]["fora_do_ar"]


def test_links_que_sairam_dos_recursos_ficam_fora_da_tabela():
    gravar_silver(["a"], [("a", "https://x.gov.br/1")])
    registrar_teste("https://x.gov.br/1", HOJE, 200)
    registrar_teste("https://x.gov.br/removido", HOJE, 200)

    status, _ = gerar()

    assert list(status) == ["https://x.gov.br/1"]


def test_ignora_links_que_nao_sao_http():
    gravar_silver(["a"], [("a", "ftp://x.gov.br/1"), ("a", "sem link")])
    # Só para existir um estado de links (o link testado não é de nenhuma base)
    registrar_teste("https://y.gov.br/1", HOJE, 200)

    _, saude = gerar()

    assert saude["a"]["qtd_links"] == 0


def test_sem_estado_dos_links_encerra():
    gravar_silver(["a"], [("a", "https://x.gov.br/1")])

    with pytest.raises(SystemExit):
        gerar()