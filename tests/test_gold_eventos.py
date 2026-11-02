"""Testes dos eventos do dia (coletor/gold_eventos.py e sql/gold_evento_base.sql).

Monta uma Silver, um status e os estados falsos numa pasta temporária, gera os eventos
e confere cada tipo com casos inventados. Não usa rede.
"""

import sys
from datetime import date, timedelta

import duckdb
import pytest

import gold_eventos
import gold_status
import portal
import silver

HOJE = date(2026, 10, 26)
ONTEM = HOJE - timedelta(days=1)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Silver, Gold e estados para uma pasta temporária (o SQL continua o do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")
    monkeypatch.setattr(gold_status, "PASTA_GOLD", tmp_path / "dados" / "gold")


def gravar(arquivo, colunas, linhas):
    """Grava uma tabela falsa em Parquet: 'colunas' é 'nome TIPO, ...' e 'linhas' são tuplas."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t ({colunas})")
    if linhas:
        marcas = ", ".join("?" for _ in linhas[0])
        con.executemany(f"INSERT INTO t VALUES ({marcas})", linhas)
    con.execute(f"COPY t TO '{arquivo.as_posix()}' (FORMAT parquet)")
    con.close()


def silver_do_dia(nome, colunas, linhas, data=HOJE):
    gravar(silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet", colunas, linhas)


def montar(bases=("a",), links=None, falhas=(), mudancas=None, status=None, data=HOJE):
    """Grava a Silver do dia.

    links: {id da base: [links]}; padrão: um link por base, https://x.gov.br/<id>.csv
    falhas: (link, dias atrás da última tentativa, falhas seguidas) de cada link testado
    mudancas: (link, mudou_conteudo, mudou_schema) de cada arquivo lido no dia
    status: (id, status, motivo) de cada base no Gold
    """
    links = links or {b: [f"https://x.gov.br/{b}.csv"] for b in bases}
    silver_do_dia("base", "id VARCHAR, slug VARCHAR", [(b, f"base-{b}") for b in bases], data)
    silver_do_dia("recurso", "id_base VARCHAR, link VARCHAR", [(b, link) for b, lista in links.items() for link in lista], data)
    silver_do_dia("link_status", "link VARCHAR, ultima_tentativa DATE, falhas_seguidas INTEGER, quebrado BOOLEAN",
                  [(link, data - timedelta(days=dias), n, n >= 3) for link, dias, n in falhas], data)
    if mudancas is not None:
        silver_do_dia("versao_conteudo", "link VARCHAR, mudou_conteudo BOOLEAN, mudou_schema BOOLEAN", list(mudancas), data)
    if status is not None:
        gravar(gold_status.PASTA_GOLD / gold_status.TABELA / f"data={data}" / f"{gold_status.TABELA}.parquet",
               "id VARCHAR, status VARCHAR, motivo VARCHAR", list(status))


def estado_do_status(*linhas):
    """Grava o estado com o status guardado das bases: (data, id, status)."""
    gravar(gold_eventos.arquivo_status_anterior(), "data DATE, id VARCHAR, status VARCHAR", list(linhas))


def gerar(data=HOJE):
    """Gera os eventos do dia, atualiza os estados e devolve os eventos como [(id_base, tipo, detalhe)]."""
    con = duckdb.connect()
    gold_eventos.criar_views_entrada(con, data)
    arquivo, _ = gold_eventos.gerar_tabela(con, data)
    gold_eventos.atualizar_estados(con, data, arquivo)
    eventos = con.execute(f"SELECT id_base, tipo_evento, detalhe FROM read_parquet('{arquivo.as_posix()}') ORDER BY 1, 2").fetchall()
    con.close()
    return eventos


def ler_estado(arquivo, colunas):
    return duckdb.sql(f"SELECT {colunas} FROM read_parquet('{arquivo.as_posix()}') ORDER BY ALL").fetchall()


# --- Link que quebrou ---

def test_link_que_fecha_hoje_a_terceira_falha_gera_um_evento():
    montar(falhas=[("https://x.gov.br/a.csv", 0, 3)])

    assert gerar() == [("a", "LINK_QUEBROU", "1 link passou a ser considerado quebrado: https://x.gov.br/a.csv")]


@pytest.mark.parametrize("dias_atras, falhas", [
    (0, 2),   # ainda em observação
    (0, 4),   # já estava quebrado: a terceira falha foi num teste anterior
    (3, 3),   # fechou a terceira falha em outro dia, não hoje
])
def test_link_que_nao_quebrou_hoje_nao_gera_evento(dias_atras, falhas):
    montar(falhas=[("https://x.gov.br/a.csv", dias_atras, falhas)])

    assert gerar() == []


def test_varios_links_quebrados_da_mesma_base_viram_um_evento_com_a_contagem():
    montar(links={"a": ["https://x.gov.br/2.csv", "https://x.gov.br/1.csv", "https://x.gov.br/3.csv"]},
           falhas=[("https://x.gov.br/2.csv", 0, 3), ("https://x.gov.br/1.csv", 0, 3), ("https://x.gov.br/3.csv", 0, 2)])

    assert gerar() == [("a", "LINK_QUEBROU", "2 links passaram a ser considerados quebrados, por exemplo https://x.gov.br/1.csv")]


# --- Conteúdo e estrutura ---

def test_conteudo_e_estrutura_que_mudaram_geram_eventos_separados():
    montar(links={"a": ["https://x.gov.br/1.csv", "https://x.gov.br/2.csv"], "b": ["https://x.gov.br/3.csv"]}, bases=("a", "b"),
           mudancas=[("https://x.gov.br/1.csv", True, False), ("https://x.gov.br/2.csv", True, True), ("https://x.gov.br/3.csv", False, False)])

    assert gerar() == [
        ("a", "CONTEUDO_MUDOU", "o conteúdo de 2 arquivos mudou"),
        ("a", "SCHEMA_MUDOU", "a estrutura (colunas) de 1 arquivo mudou"),
    ]


def test_sem_leitura_de_conteudo_no_dia_nao_ha_evento_de_conteudo():
    montar()

    assert gerar() == []


# --- Mudança de status ---

def test_mudanca_de_status_traz_de_onde_para_onde_e_o_motivo():
    montar(status=[("a", "ATRASADA", "atrasada porque é mensal e não muda há 73 dias (prazo de 40 dias)")])
    estado_do_status((ONTEM, "a", "EM_DIA"))

    assert gerar() == [("a", "STATUS_MUDOU",
                        "de em dia para atrasada: atrasada porque é mensal e não muda há 73 dias (prazo de 40 dias)")]


def test_quem_era_nao_verificavel_nao_gera_evento_de_status():
    montar(status=[("a", "EM_DIA", "em dia")])
    estado_do_status((ONTEM, "a", "NAO_VERIFICAVEL"))

    assert gerar() == []


def test_status_igual_ao_anterior_nao_gera_evento():
    montar(status=[("a", "ATRASADA", "atrasada")])
    estado_do_status((ONTEM, "a", "ATRASADA"))

    assert gerar() == []


def test_primeiro_dia_sem_status_anterior_nao_gera_evento_de_status():
    montar(status=[("a", "EM_DIA", "em dia")])

    assert gerar() == []


def test_o_status_anterior_e_o_do_ultimo_dia_antes_de_hoje():
    montar(status=[("a", "PARADA", "parada")])
    # Três dias atrás estava em dia, anteontem e ontem já atrasada; hoje, parada
    estado_do_status((HOJE - timedelta(days=3), "a", "EM_DIA"), (HOJE - timedelta(days=1), "a", "ATRASADA"))

    assert gerar() == [("a", "STATUS_MUDOU", "de atrasada para parada: parada")]


# --- Estados que ligam um dia ao outro ---

def test_eventos_do_dia_entram_nos_eventos_recentes():
    montar(falhas=[("https://x.gov.br/a.csv", 0, 3)])

    gerar()

    assert ler_estado(gold_eventos.arquivo_eventos_recentes(), "data, id_base, tipo_evento") == [(HOJE, "a", "LINK_QUEBROU")]


def test_rodar_o_mesmo_dia_duas_vezes_nao_duplica_nada():
    montar(falhas=[("https://x.gov.br/a.csv", 0, 3)], status=[("a", "ATRASADA", "atrasada")])
    estado_do_status((ONTEM, "a", "EM_DIA"))

    primeira = gerar()
    recentes = ler_estado(gold_eventos.arquivo_eventos_recentes(), "*")
    status = ler_estado(gold_eventos.arquivo_status_anterior(), "*")
    segunda = gerar()

    assert primeira == segunda and len(primeira) == 2
    assert ler_estado(gold_eventos.arquivo_eventos_recentes(), "*") == recentes
    assert ler_estado(gold_eventos.arquivo_status_anterior(), "*") == status


def test_eventos_com_mais_de_30_dias_saem_do_estado():
    antigo = HOJE - timedelta(days=gold_eventos.DIAS_RECENTES)
    ainda_vale = HOJE - timedelta(days=gold_eventos.DIAS_RECENTES - 1)
    gravar(gold_eventos.arquivo_eventos_recentes(), "data DATE, id_base VARCHAR, slug VARCHAR, tipo_evento VARCHAR, detalhe VARCHAR",
           [(antigo, "a", "base-a", "SCHEMA_MUDOU", "velho"), (ainda_vale, "a", "base-a", "SCHEMA_MUDOU", "recente")])
    montar()

    gerar()

    assert [linha[0] for linha in ler_estado(gold_eventos.arquivo_eventos_recentes(), "data")] == [ainda_vale]


def test_estado_do_status_guarda_o_dia_anterior_e_o_de_hoje():
    montar(status=[("a", "ATRASADA", "atrasada")])
    estado_do_status((HOJE - timedelta(days=5), "a", "EM_DIA"), (ONTEM, "a", "EM_DIA"))

    gerar()

    # Fica só o último dia anterior de cada base e o de hoje: o resto não serve para comparar amanhã
    assert ler_estado(gold_eventos.arquivo_status_anterior(), "data, id, status") == [(ONTEM, "a", "EM_DIA"), (HOJE, "a", "ATRASADA")]


def test_sem_o_status_do_dia_o_estado_do_status_nao_muda():
    montar()
    estado_do_status((ONTEM, "a", "EM_DIA"))

    gerar()

    assert ler_estado(gold_eventos.arquivo_status_anterior(), "data, id, status") == [(ONTEM, "a", "EM_DIA")]


# --- Entradas e execução ---

def test_silver_do_dia_ausente_encerra():
    con = duckdb.connect()

    with pytest.raises(SystemExit):
        gold_eventos.criar_views_entrada(con, HOJE)


def test_main_grava_os_eventos_e_mostra_o_resumo_por_tipo(monkeypatch, capsys):
    montar(falhas=[("https://x.gov.br/a.csv", 0, 3)])
    monkeypatch.setattr(sys, "argv", ["gold_eventos.py", "--data", str(HOJE)])

    gold_eventos.main()

    saida = capsys.readouterr().out
    assert "1 eventos" in saida
    assert "LINK_QUEBROU: 1" in saida
    assert (gold_status.PASTA_GOLD / gold_eventos.TABELA / f"data={HOJE}" / f"{gold_eventos.TABELA}.parquet").exists()
