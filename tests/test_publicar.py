"""Testes da API estática (publicar/gerar_api.py e sql/api_base.sql).

Monta uma Silver falsa numa pasta temporária, gera os JSON e confere o que o site vai ler. Não usa rede.
"""

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import duckdb
import pytest

import gerar_api
import gold_status
import portal
import silver

HOJE = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Silver, Gold e a saída da API para uma pasta temporária (o SQL continua o do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")
    monkeypatch.setattr(gold_status, "PASTA_GOLD", tmp_path / "dados" / "gold")
    monkeypatch.setattr(gerar_api, "PASTA_SAIDA", tmp_path / "site" / "api")


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


def base(id_base, publicador="Órgão A", esfera="FEDERAL", periodicidade="MENSAL", links=0, testados=0, ok=0,
         observacao=0, quebrados=0, fora_do_ar=False, titulo=None):
    """Uma base inventada. publicador=None deixa a base sem linha em silver/publicador."""
    return {"id": id_base, "slug": f"base-{id_base}", "titulo": titulo or f"Base {id_base}", "periodicidade": periodicidade,
            "publicador": publicador, "esfera": esfera, "links": links, "testados": testados, "ok": ok,
            "observacao": observacao, "quebrados": quebrados, "fora_do_ar": fora_do_ar}


def montar(*bases, recursos=0):
    """Grava a Silver (base, publicador, base_saude, recurso) das bases inventadas."""
    def destino(nome):
        return silver.PASTA_SILVER / nome / f"data={HOJE}" / f"{nome}.parquet"

    gravar(destino("base"), "id VARCHAR, slug VARCHAR, titulo VARCHAR, periodicidade VARCHAR",
           [(b["id"], b["slug"], b["titulo"], b["periodicidade"]) for b in bases])
    gravar(destino("publicador"), "id VARCHAR, publicador VARCHAR, esfera VARCHAR",
           [(b["id"], b["publicador"], b["esfera"]) for b in bases if b["publicador"] is not None])
    gravar(destino("base_saude"),
           "id VARCHAR, qtd_links BIGINT, qtd_testados BIGINT, qtd_ok BIGINT, qtd_em_observacao BIGINT, qtd_quebrados BIGINT, fora_do_ar BOOLEAN",
           [(b["id"], b["links"], b["testados"], b["ok"], b["observacao"], b["quebrados"], b["fora_do_ar"]) for b in bases])
    gravar(destino("recurso"), "id_base VARCHAR, link VARCHAR",
           [(bases[0]["id"], f"https://x.gov.br/{i}") for i in range(recursos)])


def gravar_status(*linhas):
    """Grava o status das bases (Gold) como o gold_status.py faria: (id, status, motivo)."""
    arquivo = gold_status.PASTA_GOLD / gold_status.TABELA / f"data={HOJE}" / f"{gold_status.TABELA}.parquet"
    gravar(arquivo, "id VARCHAR, status VARCHAR, motivo VARCHAR", list(linhas))


def gerar():
    """Gera a API do dia na pasta padrão de teste e devolve (pasta, resumo)."""
    con = duckdb.connect()
    gerar_api.criar_views_entrada(con, HOJE)
    resumo, _ = gerar_api.gerar(con, HOJE, gerar_api.PASTA_SAIDA)
    con.close()
    return gerar_api.PASTA_SAIDA, resumo


def ler(pasta, *caminho):
    """Lê um JSON gerado."""
    return json.loads(pasta.joinpath(*caminho).read_text(encoding="utf-8"))


# --- Slug do órgão ---

@pytest.mark.parametrize("nome, esperado", [
    ("IPEA - Instituto de Pesquisa Econômica Aplicada", "ipea-instituto-de-pesquisa-economica-aplicada"),
    ("Prefeitura de Belo Horizonte", "prefeitura-de-belo-horizonte"),
    ("  Governo   do Estado  ", "governo-do-estado"),
    ("Não identificado", "nao-identificado"),
    ("!!!", "sem-nome"),
    ("", "sem-nome"),
])
def test_slug_do_orgao(nome, esperado):
    assert gerar_api.criar_slug(nome) == esperado


# --- Resumo do Brasil ---

def test_resumo_soma_bases_recursos_e_links():
    montar(base("a", "Órgão A", links=10, testados=8, ok=6, observacao=1, quebrados=1),
           base("b", "Órgão B", links=5, testados=5, ok=5),
           base("c", "Órgão B", links=0), recursos=7)

    _, resumo = gerar()

    assert (resumo["bases"], resumo["recursos"], resumo["orgaos"]) == (3, 7, 2)
    assert resumo["links"] == {"total": 15, "testados": 13, "ok": 11, "em_observacao": 1, "quebrados": 1,
                               "percentual_ok": 84.6, "cobertura": 86.7}
    assert resumo["bases_sem_link"] == 1
    assert resumo["data_coleta"] == "2026-10-26"
    assert resumo["versao"] == "prototipo"


def test_resumo_conta_bases_fora_do_ar_esferas_e_periodicidades():
    montar(base("a", esfera="FEDERAL", periodicidade="MENSAL", links=2, quebrados=2, fora_do_ar=True),
           base("b", esfera="FEDERAL", periodicidade="MENSAL"),
           base("c", "Prefeitura", esfera="MUNICIPAL", periodicidade="ANUAL"))

    _, resumo = gerar()

    assert resumo["bases_fora_do_ar"] == 1
    assert resumo["esferas"] == [{"esfera": "FEDERAL", "bases": 2}, {"esfera": "MUNICIPAL", "bases": 1}]
    assert resumo["periodicidades"] == [{"periodicidade": "MENSAL", "bases": 2}, {"periodicidade": "ANUAL", "bases": 1}]


def test_sem_testes_nao_ha_percentual_nem_divisao_por_zero():
    montar(base("a", links=0))

    _, resumo = gerar()

    assert resumo["links"]["percentual_ok"] is None
    assert resumo["links"]["cobertura"] is None


# --- Órgãos ---

def test_orgaos_ordenados_pelo_numero_de_bases_e_depois_pelo_nome():
    montar(base("1", "Zeta"), base("2", "Beta"), base("3", "Beta"), base("4", "Alfa"))

    pasta, _ = gerar()

    nomes = [orgao["nome"] for orgao in ler(pasta, "orgaos.json")]
    assert nomes == ["Beta", "Alfa", "Zeta"]


def test_orgao_resume_links_cobertura_e_status():
    montar(base("a", "Órgão A", links=40, testados=30, ok=24, observacao=6, quebrados=0),
           base("b", "Órgão A", links=20, testados=20, ok=16, observacao=3, quebrados=1, fora_do_ar=False))

    pasta, _ = gerar()

    orgao = ler(pasta, "orgaos.json")[0]
    assert orgao["qtd_bases"] == 2
    assert (orgao["links_total"], orgao["links_testados"], orgao["links_ok"]) == (60, 50, 40)
    assert (orgao["links_em_observacao"], orgao["links_quebrados"]) == (9, 1)
    assert orgao["percentual_ok"] == 80.0
    assert orgao["cobertura_links"] == 83.3
    assert orgao["status"] == {"NAO_VERIFICAVEL": 2}
    # A lista de órgãos não carrega as bases (elas ficam no arquivo de cada órgão)
    assert "bases" not in orgao


@pytest.mark.parametrize("testados, esperado", [(29, None), (30, 100.0)])
def test_porcentagem_do_orgao_so_com_links_testados_suficientes(testados, esperado):
    montar(base("a", "Órgão A", links=testados, testados=testados, ok=testados))

    pasta, _ = gerar()

    orgao = ler(pasta, "orgaos.json")[0]
    assert orgao["percentual_ok"] == esperado
    # A cobertura continua aparecendo, para o leitor ver o tamanho da amostra
    assert orgao["cobertura_links"] == 100.0
    assert gerar_api.MINIMO_TESTADOS_PARA_PERCENTUAL == 30


def test_base_sem_publicador_vira_orgao_nao_identificado():
    montar(base("a", None, esfera=None), base("b", "Órgão B"))

    pasta, _ = gerar()

    orgaos = {orgao["slug"]: orgao for orgao in ler(pasta, "orgaos.json")}
    assert orgaos["nao-identificado"]["nome"] == "Não identificado"
    assert orgaos["nao-identificado"]["esfera"] == "NAO_CLASSIFICADA"
    assert (pasta / "orgaos" / "nao-identificado.json").exists()


def test_arquivo_do_orgao_traz_as_bases_com_problema_primeiro():
    montar(base("a", titulo="Sem problema", links=2, testados=2, ok=2),
           base("b", titulo="Em observação", links=2, testados=2, ok=1, observacao=1),
           base("c", titulo="Quebrada", links=2, testados=2, ok=0, quebrados=2, fora_do_ar=True))

    pasta, _ = gerar()

    orgao = ler(pasta, "orgaos", "orgao-a.json")
    assert [b["titulo"] for b in orgao["bases"]] == ["Quebrada", "Em observação", "Sem problema"]
    assert orgao["nome"] == "Órgão A"
    primeira = orgao["bases"][0]
    assert (primeira["id"], primeira["slug"], primeira["fora_do_ar"], primeira["links_quebrados"]) == ("c", "base-c", True, 2)


def test_nomes_que_dao_o_mesmo_slug_ganham_um_numero():
    montar(base("a", "Órgão X"), base("b", "Orgao-X"))

    pasta, _ = gerar()

    slugs = sorted(orgao["slug"] for orgao in ler(pasta, "orgaos.json"))
    assert slugs == ["orgao-x", "orgao-x-2"]


# --- Status (Gold) ---

def test_sem_gold_todas_as_bases_ficam_nao_verificaveis():
    montar(base("a"), base("b"))

    pasta, resumo = gerar()

    assert resumo["status"] == {"NAO_VERIFICAVEL": 2}
    assert all(b["status"] == "NAO_VERIFICAVEL" and b["motivo"] is None for b in ler(pasta, "orgaos", "orgao-a.json")["bases"])


def test_status_e_motivo_vem_do_gold_quando_existe():
    montar(base("a", titulo="A"), base("b", titulo="B"))
    gravar_status(("a", "ATRASADA", "atrasada porque é mensal e não muda há 73 dias (prazo de 40 dias)"))

    pasta, resumo = gerar()

    assert resumo["status"] == {"ATRASADA": 1, "NAO_VERIFICAVEL": 1}
    bases = {b["id"]: b for b in ler(pasta, "orgaos", "orgao-a.json")["bases"]}
    assert bases["a"]["status"] == "ATRASADA"
    assert bases["a"]["motivo"].startswith("atrasada porque é mensal")
    assert bases["b"]["status"] == "NAO_VERIFICAVEL"


# --- Arquivos ---

def test_json_em_utf8_sem_escapar_os_acentos():
    montar(base("a", "Ministério da Saúde", titulo="Atualização diária"))

    pasta, _ = gerar()

    texto = (pasta / "orgaos" / "ministerio-da-saude.json").read_text(encoding="utf-8")
    assert "Ministério da Saúde" in texto
    assert "Atualização diária" in texto


def test_orgaos_de_uma_execucao_anterior_sao_removidos():
    montar(base("a", "Órgão A"), base("b", "Órgão B"))
    pasta, _ = gerar()
    assert (pasta / "orgaos" / "orgao-b.json").exists()

    montar(base("a", "Órgão A"))
    gerar()

    assert not (pasta / "orgaos" / "orgao-b.json").exists()
    assert (pasta / "orgaos" / "orgao-a.json").exists()


def test_silver_do_dia_ausente_encerra():
    con = duckdb.connect()

    with pytest.raises(SystemExit):
        gerar_api.criar_views_entrada(con, HOJE)


def test_main_grava_os_tres_tipos_de_arquivo_e_mostra_o_resumo(monkeypatch, capsys):
    montar(base("a", links=4, testados=4, ok=3, quebrados=1))
    monkeypatch.setattr(sys, "argv", ["gerar_api.py", "--data", str(HOJE)])

    gerar_api.main()

    pasta = gerar_api.PASTA_SAIDA
    assert (pasta / "resumo.json").exists() and (pasta / "orgaos.json").exists() and (pasta / "orgaos" / "orgao-a.json").exists()
    assert "1 bases em 1 órgãos" in capsys.readouterr().out


def test_script_roda_direto_como_o_usuario_roda():
    # "python publicar/gerar_api.py" não herda o caminho de importação do pytest: o script precisa achar coletor/ sozinho
    ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "PYTHONPATH"}

    resultado = subprocess.run([sys.executable, str(Path(gerar_api.__file__)), "--help"], capture_output=True, text=True, env=ambiente)

    assert resultado.returncode == 0, resultado.stderr
    assert "--saida" in resultado.stdout


def test_main_aceita_outra_pasta_de_saida(monkeypatch, tmp_path):
    montar(base("a"))
    destino = tmp_path / "outra"
    monkeypatch.setattr(sys, "argv", ["gerar_api.py", "--data", str(HOJE), "--saida", str(destino)])

    gerar_api.main()

    assert (destino / "resumo.json").exists()
    assert not (gerar_api.PASTA_SAIDA / "resumo.json").exists()
