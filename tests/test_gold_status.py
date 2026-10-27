"""Testes do status das bases (coletor/gold_status.py e sql/gold_status_base.sql).

Monta uma Silver e um estado de conteúdo falsos numa pasta temporária, gera o status
e confere as regras com casos inventados. Não usa rede.
"""

import re
import sys
from datetime import date, timedelta

import duckdb
import pytest

import conteudo_estado
import gold_status
import portal
import silver

HOJE = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Silver, estado e Gold para uma pasta temporária (SQL e prazos continuam os do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")
    monkeypatch.setattr(gold_status, "PASTA_GOLD", tmp_path / "dados" / "gold")


def dias_atras(dias):
    """Data de 'dias' dias antes de hoje."""
    return HOJE - timedelta(days=dias)


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


def arquivo(primeira=None, mudanca=None, schema=None, tabular=True):
    """Um arquivo de uma base: datas da primeira leitura, da última mudança e da última mudança de schema."""
    return {"primeira": primeira, "mudanca": mudanca, "schema": schema, "tabular": tabular}


def base(id_base, periodicidade="MENSAL", arquivos=(), status_portal=None, links=None, quebrados=0, fora_do_ar=False):
    """Uma base inventada; links é a quantidade de links (padrão: um por arquivo)."""
    return {"id": id_base, "periodicidade": periodicidade, "arquivos": list(arquivos), "status_portal": status_portal,
            "links": len(arquivos) if links is None else links, "quebrados": quebrados, "fora_do_ar": fora_do_ar}


def montar(*bases, com_estado=True):
    """Grava a Silver (base, recurso, base_saude) e o estado do conteúdo das bases inventadas."""
    pasta = silver.PASTA_SILVER
    destino = lambda nome: pasta / nome / f"data={HOJE}" / f"{nome}.parquet"  # noqa: E731

    gravar(destino("base"), "id VARCHAR, slug VARCHAR, periodicidade VARCHAR, status_portal VARCHAR",
           [(b["id"], f"base-{b['id']}", b["periodicidade"], b["status_portal"]) for b in bases])
    gravar(destino("base_saude"), "id VARCHAR, qtd_links BIGINT, qtd_quebrados BIGINT, fora_do_ar BOOLEAN",
           [(b["id"], b["links"], b["quebrados"], b["fora_do_ar"]) for b in bases])

    recursos, estados = [], []
    for b in bases:
        for numero, a in enumerate(b["arquivos"], start=1):
            link = f"https://dados.gov.br/{b['id']}/{numero}.csv"
            recursos.append((b["id"], link, a["tabular"]))
            estados.append((link, HOJE, a["primeira"], a["mudanca"], a["schema"]))
    gravar(destino("recurso"), "id_base VARCHAR, link VARCHAR, formato_tabular BOOLEAN", recursos)

    if com_estado:
        arq_estado = conteudo_estado.arquivo_estado()
        arq_estado.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect()
        con.execute(f"CREATE TABLE conteudo_atual ({conteudo_estado.COLUNAS_ESTADO})")
        for linha in estados:
            con.execute("""INSERT INTO conteudo_atual (link, ultima_leitura, primeira_leitura, ultima_mudanca, ultima_mudanca_schema)
                           VALUES (?, ?, ?, ?, ?)""", linha)
        con.execute(f"COPY conteudo_atual TO '{arq_estado.as_posix()}' (FORMAT parquet)")
        con.close()


def gerar_status():
    """Gera o status do dia e devolve {id da base: linha como dicionário}."""
    con = duckdb.connect()
    gold_status.criar_views_entrada(con, HOJE)
    arquivo_gerado, _ = gold_status.gerar_tabela(con, HOJE)
    resultado = con.execute(f"SELECT * FROM '{arquivo_gerado.as_posix()}'")
    colunas = [c[0] for c in resultado.description]
    linhas = {linha[colunas.index("id")]: dict(zip(colunas, linha)) for linha in resultado.fetchall()}
    con.close()
    return linhas


# --- Em dia, atrasada e parada (periodicidade declarada) ---

def test_em_dia_quando_mudou_dentro_do_prazo():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(200), mudanca=dias_atras(12))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "EM_DIA"
    assert linha["prazo_esperado_dias"] == 40
    assert linha["origem_prazo"] == "DECLARADO"
    assert linha["dias_sem_mudanca"] == 12
    assert linha["ultima_mudanca_real"] == dias_atras(12)
    assert linha["motivo"] == "em dia porque é mensal e mudou há 12 dias (prazo de 40 dias)"


def test_atrasada_explica_o_motivo_em_uma_frase():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(300), mudanca=dias_atras(73))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "ATRASADA"
    assert linha["motivo"] == "atrasada porque é mensal e não muda há 73 dias (prazo de 40 dias)"


@pytest.mark.parametrize("dias, esperado", [
    (40, "EM_DIA"),      # exatamente no prazo ainda é em dia
    (41, "ATRASADA"),    # passou do prazo
    (120, "ATRASADA"),   # exatamente 3x o prazo ainda é atrasada
    (121, "PARADA"),     # passou de 3x o prazo
])
def test_limites_do_prazo_mensal(dias, esperado):
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(500), mudanca=dias_atras(dias))]))

    assert gerar_status()["a"]["status"] == esperado


def test_parada_explica_que_passou_de_tres_vezes_o_prazo():
    montar(base("a", periodicidade="ANUAL", arquivos=[arquivo(primeira=dias_atras(2000), mudanca=dias_atras(1300))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "PARADA"
    assert linha["motivo"] == "parada porque é anual e não muda há 1300 dias (prazo de 400 dias, mais de 3x)"


# --- Sem mudança vista: vale a janela de observação ---

def test_sem_mudanca_vista_e_janela_curta_nao_da_para_dizer():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(10))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "NAO_VERIFICAVEL"
    assert linha["motivo"] == "ainda sem mudança vista em 10 dias de leitura, menos que o prazo de 40 dias"


@pytest.mark.parametrize("janela, esperado", [(50, "ATRASADA"), (130, "PARADA")])
def test_sem_mudanca_vista_e_janela_longa_vira_atrasada_ou_parada(janela, esperado):
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(janela))]))

    linha = gerar_status()["a"]

    assert linha["status"] == esperado
    assert linha["ultima_mudanca_real"] is None
    assert f"não mudou em {janela} dias de leitura" in linha["motivo"]


def test_janela_vale_o_arquivo_visto_ha_menos_tempo():
    # Um arquivo é visto há 100 dias e o outro há 5: só dá para afirmar "sem mudança" por 5 dias
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(100)), arquivo(primeira=dias_atras(5))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "NAO_VERIFICAVEL"
    assert linha["janela_observacao_dias"] == 5


def test_ultima_mudanca_vale_a_mais_recente_entre_os_arquivos():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(300), mudanca=dias_atras(100)),
                               arquivo(primeira=dias_atras(300), mudanca=dias_atras(3))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "EM_DIA"
    assert linha["dias_sem_mudanca"] == 3


# --- Fora do ar e não verificável ---

def test_fora_do_ar_tem_prioridade_sobre_o_conteudo():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(200), mudanca=dias_atras(2))],
                links=3, quebrados=3, fora_do_ar=True))

    linha = gerar_status()["a"]

    assert linha["status"] == "FORA_DO_AR"
    assert linha["motivo"] == "todos os 3 links estão quebrados"
    assert linha["links_quebrados"] == 3


def test_sem_arquivo_tabular_lido_nao_e_verificavel():
    montar(base("a", links=2))

    linha = gerar_status()["a"]

    assert linha["status"] == "NAO_VERIFICAVEL"
    assert linha["motivo"] == "nenhum arquivo tabular da base foi lido"


def test_so_arquivos_tabulares_contam():
    # O arquivo não tabular tem estado, mas não entra na conta da base
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(200), mudanca=dias_atras(2), tabular=False)]))

    assert gerar_status()["a"]["status"] == "NAO_VERIFICAVEL"


@pytest.mark.parametrize("periodicidade", ["NAO_DECLARADA", "SOB_DEMANDA", "OUTRAS"])
def test_sem_periodicidade_comparavel_nao_e_verificavel(periodicidade):
    montar(base("a", periodicidade=periodicidade, arquivos=[arquivo(primeira=dias_atras(200), mudanca=dias_atras(2))]))

    linha = gerar_status()["a"]

    assert linha["status"] == "NAO_VERIFICAVEL"
    assert linha["prazo_esperado_dias"] is None
    assert linha["origem_prazo"] is None
    assert linha["motivo"] == "sem periodicidade declarada e ainda sem histórico para inferir o ritmo"


def test_base_sem_detalhe_ainda_nao_e_verificavel():
    montar(base("a", periodicidade=None))

    linha = gerar_status()["a"]

    assert linha["status"] == "NAO_VERIFICAVEL"
    assert linha["motivo"] == "detalhe da base ainda não coletado"


def test_sem_estado_do_conteudo_as_bases_ficam_nao_verificaveis():
    # Antes de qualquer download não existe o arquivo de estado: o status ainda precisa rodar
    montar(base("a", links=2), base("b", fora_do_ar=True, links=1, quebrados=1), com_estado=False)

    linhas = gerar_status()

    assert linhas["a"]["status"] == "NAO_VERIFICAVEL"
    assert linhas["b"]["status"] == "FORA_DO_AR"


# --- Periodicidades, schema e portal ---

@pytest.mark.parametrize("periodicidade, prazo", [
    ("DIARIA", 3), ("SEMANAL", 10), ("QUINZENAL", 20), ("MENSAL", 40),
    ("TRIMESTRAL", 100), ("QUADRIMESTRAL", 135), ("SEMESTRAL", 200), ("ANUAL", 400),
])
def test_prazo_de_cada_periodicidade(periodicidade, prazo):
    montar(base("a", periodicidade=periodicidade, arquivos=[arquivo(primeira=dias_atras(900), mudanca=dias_atras(1))]))

    assert gerar_status()["a"]["prazo_esperado_dias"] == prazo


def test_schema_mudou_so_conta_se_foi_hoje():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(50), mudanca=dias_atras(5), schema=HOJE)]),
           base("b", arquivos=[arquivo(primeira=dias_atras(50), mudanca=dias_atras(5), schema=dias_atras(3))]))

    linhas = gerar_status()

    assert linhas["a"]["schema_mudou"] is True
    assert linhas["b"]["schema_mudou"] is False


@pytest.mark.parametrize("portal_diz, mudanca, diverge", [
    ("Atualizado", 100, True),                      # portal diz atualizado, mas está atrasada
    ("Desatualizado", 5, True),                     # portal diz desatualizado, mas está em dia
    ("Atualizado", 5, False),                       # concordam: em dia
    ("Desatualizado", 100, False),                  # concordam: atrasada
    ("Atualização não verificável", 100, None),     # o portal não sabe: não há como comparar
])
def test_divergencia_com_o_selo_do_portal(portal_diz, mudanca, diverge):
    montar(base("a", status_portal=portal_diz, arquivos=[arquivo(primeira=dias_atras(300), mudanca=dias_atras(mudanca))]))

    assert gerar_status()["a"]["diverge_do_portal"] is diverge


def test_base_nao_verificavel_nao_diverge_do_portal():
    montar(base("a", status_portal="Atualizado", periodicidade="NAO_DECLARADA"))

    assert gerar_status()["a"]["diverge_do_portal"] is None


# --- O comando inteiro ---

def test_grava_uma_linha_por_base_na_pasta_gold():
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(50), mudanca=dias_atras(5))]), base("b"), base("c"))
    con = duckdb.connect()
    gold_status.criar_views_entrada(con, HOJE)

    arquivo_gerado, linhas = gold_status.gerar_tabela(con, HOJE)

    assert linhas == 3
    assert arquivo_gerado.parts[-3:] == (
        "fato_status_base_diario", f"data={HOJE}", "fato_status_base_diario.parquet")


def test_silver_do_dia_ausente_encerra():
    con = duckdb.connect()

    with pytest.raises(SystemExit):
        gold_status.criar_views_entrada(con, HOJE)


def test_main_gera_o_status_e_mostra_o_resumo(monkeypatch, capsys):
    montar(base("a", arquivos=[arquivo(primeira=dias_atras(300), mudanca=dias_atras(100))], status_portal="Atualizado"),
           base("b", arquivos=[arquivo(primeira=dias_atras(300), mudanca=dias_atras(5))]))
    monkeypatch.setattr(sys, "argv", ["gold_status.py", "--data", str(HOJE)])

    gold_status.main()

    saida = capsys.readouterr().out
    assert "2 linhas" in saida
    assert "ATRASADA: 1" in saida
    assert "EM_DIA: 1" in saida
    assert "Divergem do selo do portal: 1" in saida


# --- Tabela de prazos ---

def test_tabela_de_prazos_cobre_as_periodicidades_comparaveis_da_silver():
    # As periodicidades que a Silver marca como comparáveis precisam ter prazo na tabela
    sql = (silver.PASTA_SQL / "silver_base.sql").read_text(encoding="utf-8")
    bloco = sql.split("Só estas periodicidades dão um prazo esperado")[1].split("AS periodicidade_comparavel")[0]
    comparaveis = set(re.findall(r"'([A-Z_]+)'", bloco))

    prazos = dict(duckdb.sql(
        f"SELECT periodicidade, prazo_dias FROM read_csv('{gold_status.ARQUIVO_PRAZOS.as_posix()}', delim = ';', header = true)"
    ).fetchall())

    assert comparaveis == set(prazos)


def test_prazos_crescem_com_a_periodicidade():
    ordem = ["DIARIA", "SEMANAL", "QUINZENAL", "MENSAL", "TRIMESTRAL", "QUADRIMESTRAL", "SEMESTRAL", "ANUAL"]
    prazos = dict(duckdb.sql(
        f"SELECT periodicidade, prazo_dias FROM read_csv('{gold_status.ARQUIVO_PRAZOS.as_posix()}', delim = ';', header = true)"
    ).fetchall())

    valores = [prazos[periodicidade] for periodicidade in ordem]

    assert valores == sorted(valores)
    assert len(set(valores)) == len(valores)
