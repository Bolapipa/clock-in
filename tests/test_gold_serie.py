"""Testes da série diária da Gold (coletor/gold_serie.py, coletor/nota.py e sql/gold_serie_*.sql).

Monta uma Silver e um status falsos numa pasta temporária, grava a série e confere cada coluna com
casos inventados. Não usa rede.
"""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

import gerar_api
import gold_serie
import gold_status
import nota
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


def montar(orgaos, data=HOJE, com_status=True, esfera="FEDERAL"):
    """Grava a Silver e o status do dia.

    orgaos: {nome do órgão: [status de cada base]}. O nome None deixa as bases sem publicador.
    "NAO_VERIFICAVEL" fica sem linha no status, como o gold_status.py faria de fato.
    Cada base tem 2 links testados, 1 deles bom e 1 quebrado.
    """
    bases, publicadores, status = [], [], []
    for indice, (nome, lista) in enumerate(orgaos.items()):
        for posicao, estado in enumerate(lista):
            id_base = f"o{indice}b{posicao:02d}"
            bases.append(id_base)
            if nome is not None:
                publicadores.append((id_base, nome, esfera))
            if estado != "NAO_VERIFICAVEL":
                status.append((id_base, estado, "motivo"))

    def destino(nome):
        return silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"

    gravar(destino("base"), "id VARCHAR, slug VARCHAR", [(b, f"base-{b}") for b in bases])
    gravar(destino("publicador"), "id VARCHAR, publicador VARCHAR, esfera VARCHAR", publicadores)
    gravar(destino("base_saude"),
           "id VARCHAR, qtd_links BIGINT, qtd_testados BIGINT, qtd_ok BIGINT, qtd_em_observacao BIGINT, qtd_quebrados BIGINT, fora_do_ar BOOLEAN",
           [(b, 2, 2, 1, 0, 1, False) for b in bases])
    if com_status:
        gravar(gold_status.PASTA_GOLD / gold_status.TABELA / f"data={data}" / f"{gold_status.TABELA}.parquet",
               "id VARCHAR, status VARCHAR, motivo VARCHAR", status)


def gerar(data=HOJE):
    """Grava a série do dia, atualiza os estados e devolve (arquivo da nota por órgão, arquivo do Brasil)."""
    con = duckdb.connect()
    gold_serie.criar_views_entrada(con, data)
    destino_nota, destino_brasil = gold_serie.gerar_tabelas(con, data)
    gold_serie.atualizar_estados(con, data, destino_nota, destino_brasil)
    con.close()
    return destino_nota, destino_brasil


def linhas(arquivo):
    """As linhas de um Parquet como lista de dicionários, em ordem."""
    cursor = duckdb.sql(f"SELECT * FROM read_parquet('{arquivo.as_posix()}') ORDER BY ALL")
    return [dict(zip(cursor.columns, linha)) for linha in cursor.fetchall()]


def por_orgao(arquivo):
    return {linha["orgao"]: linha for linha in linhas(arquivo)}


# --- Nota e contagem por órgão ---

def test_conta_as_bases_por_status_e_calcula_a_nota_de_cada_orgao():
    montar({
        "Órgão A": ["EM_DIA"] * 4 + ["ATRASADA"] * 2 + ["PARADA", "FORA_DO_AR"] + ["NAO_VERIFICAVEL"] * 2,
        "Órgão B": ["EM_DIA"] * 3,
    })

    destino_nota, _ = gerar()

    orgaos = por_orgao(destino_nota)
    # 100 x (4 + 0,5 x 2) / 8 bases verificáveis; as 2 não verificáveis só entram na cobertura (8 de 10)
    assert orgaos["Órgão A"] == {
        "data": HOJE, "orgao": "Órgão A", "esfera": "FEDERAL", "bases_total": 10, "bases_verificaveis": 8,
        "em_dia": 4, "atrasada": 2, "parada": 1, "fora_do_ar": 1, "nao_verificavel": 2,
        "nota": 62.5, "cobertura": 80.0, "entra_ranking": True,
    }
    # Só 3 bases: tem nota, mas não entra no ranking
    assert (orgaos["Órgão B"]["nota"], orgaos["Órgão B"]["entra_ranking"]) == (100.0, False)


def test_a_nota_da_gold_e_a_da_api_inclusive_no_arredondamento():
    # Uma única fórmula: a API e a Gold usam a mesma função
    assert gerar_api.calcular_nota is nota.calcular_nota
    # 100 x 1 / 16 = 6,25: o round do Python dá 6,2 (o do SQL daria 6,3), e a Gold tem que dar o mesmo da API
    montar({"Órgão A": ["EM_DIA"] + ["PARADA"] * 15})

    destino_nota, _ = gerar()

    esperado = gerar_api.calcular_nota({"EM_DIA": 1, "PARADA": 15}, 16)
    assert por_orgao(destino_nota)["Órgão A"]["nota"] == esperado["nota"] == 6.2


def test_orgao_sem_nenhuma_base_verificavel_fica_sem_nota():
    montar({"Órgão A": ["NAO_VERIFICAVEL"] * 10})

    destino_nota, _ = gerar()

    linha = por_orgao(destino_nota)["Órgão A"]
    assert (linha["nota"], linha["cobertura"], linha["bases_verificaveis"], linha["entra_ranking"]) == (None, 0.0, 0, False)


def test_base_sem_publicador_entra_em_nao_identificado():
    montar({None: ["EM_DIA"]})

    destino_nota, _ = gerar()

    linha = por_orgao(destino_nota)["Não identificado"]
    assert (linha["esfera"], linha["bases_total"], linha["em_dia"]) == ("NAO_CLASSIFICADA", 1, 1)


# --- Totais do Brasil ---

def test_linha_do_brasil_soma_os_status_os_links_e_conta_os_orgaos():
    montar({
        "Órgão A": ["EM_DIA", "ATRASADA", "NAO_VERIFICAVEL"],
        "Órgão B": ["PARADA"] * 10,
    })

    _, destino_brasil = gerar()

    # 13 bases com 2 links cada; só o Órgão B (10 bases, todas verificáveis) entra no ranking
    assert linhas(destino_brasil) == [{
        "data": HOJE, "bases": 13, "orgaos": 2, "orgaos_no_ranking": 1,
        "em_dia": 1, "atrasada": 1, "parada": 10, "fora_do_ar": 0, "nao_verificavel": 1,
        "links_total": 26, "links_testados": 26, "links_ok": 13, "links_em_observacao": 0, "links_quebrados": 13,
    }]


# --- Estados que juntam os dias ---

def test_o_estado_acumula_um_dia_depois_do_outro():
    montar({"Órgão A": ["EM_DIA"] * 10}, data=ONTEM)
    gerar(ONTEM)
    montar({"Órgão A": ["EM_DIA"] * 9 + ["PARADA"]}, data=HOJE)

    gerar(HOJE)

    historico = linhas(gold_serie.arquivo_nota_historico())
    assert [(linha["data"], linha["nota"]) for linha in historico] == [(ONTEM, 100.0), (HOJE, 90.0)]
    assert [(linha["data"], linha["bases"]) for linha in linhas(gold_serie.arquivo_brasil_historico())] == [(ONTEM, 10), (HOJE, 10)]


def test_regravar_o_mesmo_dia_troca_as_linhas_dele_sem_duplicar():
    montar({"Órgão A": ["EM_DIA"] * 10})
    gerar()
    montar({"Órgão A": ["EM_DIA"] * 5 + ["PARADA"] * 5})

    gerar()

    historico = linhas(gold_serie.arquivo_nota_historico())
    assert [(linha["data"], linha["nota"]) for linha in historico] == [(HOJE, 50.0)]
    assert len(linhas(gold_serie.arquivo_brasil_historico())) == 1


def test_regravar_um_dia_antigo_nao_apaga_os_dias_que_vieram_depois():
    montar({"Órgão A": ["EM_DIA"] * 10}, data=ONTEM)
    montar({"Órgão A": ["EM_DIA"] * 10}, data=HOJE)
    gerar(ONTEM)
    gerar(HOJE)

    gerar(ONTEM)

    assert [linha["data"] for linha in linhas(gold_serie.arquivo_nota_historico())] == [ONTEM, HOJE]
    assert [linha["data"] for linha in linhas(gold_serie.arquivo_brasil_historico())] == [ONTEM, HOJE]


# --- Entradas que faltam ---

def test_silver_do_dia_ausente_encerra():
    con = duckdb.connect()

    with pytest.raises(SystemExit):
        gold_serie.criar_views_entrada(con, HOJE)


def test_sem_o_status_do_dia_nao_grava_nada_para_nao_registrar_um_dia_falso(monkeypatch):
    montar({"Órgão A": ["EM_DIA"] * 10}, com_status=False)
    monkeypatch.setattr(sys, "argv", ["gold_serie.py", "--data", str(HOJE)])

    with pytest.raises(SystemExit) as erro:
        gold_serie.main()

    assert "gold_status.py" in str(erro.value)
    assert not (portal.RAIZ / "dados" / "gold" / gold_serie.TABELA_NOTA).exists()
    assert not gold_serie.arquivo_nota_historico().exists()
    assert not gold_serie.arquivo_brasil_historico().exists()


# --- Uso pela linha de comando ---

def test_main_grava_as_tabelas_os_estados_e_mostra_o_resumo(monkeypatch, capsys):
    montar({"Órgão A": ["EM_DIA"] * 10})
    monkeypatch.setattr(sys, "argv", ["gold_serie.py", "--data", str(HOJE)])

    gold_serie.main()

    saida = capsys.readouterr().out
    assert "1 órgãos (1 no ranking)" in saida
    assert "Série acumulada: 1 dia(s)" in saida
    assert gold_serie.arquivo_do_dia(gold_serie.TABELA_NOTA, HOJE).exists()
    assert gold_serie.arquivo_do_dia(gold_serie.TABELA_BRASIL, HOJE).exists()
    assert gold_serie.arquivo_nota_historico().exists() and gold_serie.arquivo_brasil_historico().exists()


def test_script_roda_direto_como_o_usuario_roda():
    # "python coletor/gold_serie.py" não herda o caminho de importação do pytest
    resultado = subprocess.run([sys.executable, str(Path(gold_serie.__file__)), "--help"], capture_output=True, text=True)

    assert resultado.returncode == 0, resultado.stderr
    assert "--data" in resultado.stdout
