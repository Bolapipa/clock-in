"""Testes do resumo do dia (coletor/resumo_dia.py).

Monta Bronze, Silver e Gold falsas numa pasta temporária e confere os números do texto. Não usa rede.
"""

import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import pytest

import portal
import resumo_dia

HOJE = date(2026, 10, 27)


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Aponta a raiz do projeto para uma pasta temporária."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)


def gravar(tabela, colunas, linhas, nome="parte-0001.parquet"):
    """Grava uma tabela falsa do dia: tabela é 'bronze/link_tentativa', colunas é 'nome TIPO, ...'."""
    arquivo = portal.RAIZ / "dados" / tabela / f"data={HOJE}" / nome
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE t ({colunas})")
    if linhas:
        con.executemany(f"INSERT INTO t VALUES ({', '.join('?' for _ in linhas[0])})", linhas)
    con.execute(f"COPY t TO '{arquivo.as_posix()}' (FORMAT parquet)")
    con.close()


def hora(minuto):
    """Um horário do dia, para as tentativas."""
    return datetime(2026, 10, 27, 3, minuto)


def tentativa(link, servidor, status, erro=None, minuto=0):
    """Uma linha de link_tentativa: só as colunas que o resumo usa."""
    return (link, servidor, status, erro, hora(minuto))


COLUNAS_LINKS = "link VARCHAR, servidor VARCHAR, status_http INTEGER, erro_tipo VARCHAR, tentado_em TIMESTAMP"


def montar_tudo():
    """Um dia completo, com números fáceis de conferir."""
    gravar("bronze/catalogo_lista", "qtd_registros INTEGER", [(100,), (50,)])
    gravar("bronze/catalogo_detalhe", "motivo VARCHAR, status_http INTEGER",
           [("NOVA", 200), ("ALTERADA", 200), ("ALTERADA", 200), ("RODIZIO", 500)])
    gravar("bronze/link_tentativa", COLUNAS_LINKS, [
        tentativa("a1", "a.gov.br", 200, minuto=0),
        tentativa("a2", "a.gov.br", 301, minuto=10),
        tentativa("b1", "b.gov.br", 404, minuto=20),
        tentativa("b2", "b.gov.br", 500, minuto=30),
        tentativa("c1", "c.gov.br", 403, minuto=40),
        tentativa("c2", "c.gov.br", 405, minuto=50),
        tentativa("d1", "d.gov.br", None, "TIMEOUT", minuto=55),
        tentativa("d2", "d.gov.br", None, "SERVIDOR_FORA", minuto=59),
        tentativa("e1", "e.gov.br", None, "DNS", minuto=59),
    ])
    gravar("silver/link_status", "falhas_seguidas INTEGER, quebrado BOOLEAN",
           [(0, False), (1, False), (2, False), (3, True), (5, True)])
    gravar("silver/base_saude", "fora_do_ar BOOLEAN", [(True,), (False,), (True,)])
    gravar("bronze/conteudo_tentativa", "tamanho_bytes BIGINT, hash_conteudo VARCHAR, verificacao_parcial BOOLEAN, erro_tipo VARCHAR, tentado_em TIMESTAMP", [
        (2_000_000_000, "h1", False, None, hora(0)),
        (3_000_000_000, "h2", True, None, hora(20)),
        (None, None, None, "HTML", hora(30)),
        (None, None, None, "TIMEOUT", hora(40)),
    ])
    gravar("silver/versao_conteudo", "mudou_conteudo BOOLEAN, mudou_schema BOOLEAN", [(True, False), (True, True), (False, False)])
    gravar("gold/fato_status_base_diario", "status VARCHAR, diverge_do_portal BOOLEAN",
           [("NAO_VERIFICAVEL", None), ("NAO_VERIFICAVEL", None), ("EM_DIA", False), ("ATRASADA", True)])
    estado = portal.RAIZ / "dados" / "estado"
    estado.mkdir(parents=True, exist_ok=True)
    (estado / "links_atual.parquet").write_bytes(b"x" * 2_500_000)


def test_formatacao_dos_numeros():
    assert resumo_dia.milhar(19613) == "19.613"
    assert resumo_dia.milhar(0) == "0"
    assert resumo_dia.decimal(84.6) == "84,6"
    assert resumo_dia.decimal(5.0, 2) == "5,00"
    assert resumo_dia.percentual(1, 8) == "12,5%"
    assert resumo_dia.percentual(3, 0) == "-"


def test_catalogo():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "# Resumo do dia 2026-10-27" in texto
    assert "| Bases na listagem | 150 |" in texto
    assert "| Detalhes coletados | 3 de 4 (alterada: 2, nova: 1, rodizio: 1) |" in texto
    assert "| Detalhes com falha | 1 |" in texto


def test_links_separa_ok_inconclusivos_e_falhas():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "| Links testados no dia | 9 |" in texto
    assert "| Responderam bem (abaixo de 400) | 2 (22,2%) |" in texto
    # 403, 405, timeout e servidor não testado não contam como falha (decisões 29, 31 e 36)
    assert "| Inconclusivos (não contam como falha) | 4 (44,4%) |" in texto
    # Falhas que contam: 404, 500 e o erro de DNS
    assert "| Falhas que contam | 3 (33,3%) |" in texto
    assert "| Servidores que o teste desistiu de consultar | 1 |" in texto
    assert "| Duração do teste | 59 min |" in texto


def test_links_lista_os_erros_mais_comuns_e_a_situacao_depois_do_teste():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "| HTTP 404 | 1 |" in texto and "| DNS | 1 |" in texto and "| TIMEOUT | 1 |" in texto
    assert "| HTTP 200 |" not in texto
    assert "| Links em observação (1 ou 2 falhas seguidas) | 2 |" in texto
    assert "| Links quebrados (3 ou mais) | 2 |" in texto
    assert "| Bases fora do ar | 2 |" in texto


def test_conteudo():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "| Arquivos tentados | 4 |" in texto
    assert "| Lidos com sucesso (hash e schema) | 2 (50,0%) |" in texto
    assert "| Lidos só em parte (acima do limite de tamanho) | 1 |" in texto
    assert "| Com erro | 2 |" in texto
    assert "| Volume lido | 5,00 GB |" in texto
    assert "| Duração do download | 40 min |" in texto
    assert "| Mudaram de conteúdo hoje | 2 |" in texto
    assert "| Mudaram de schema hoje | 1 |" in texto
    assert "| HTML | 1 |" in texto


def test_status_e_estado():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "| NAO_VERIFICAVEL | 2 |" in texto and "| EM_DIA | 1 |" in texto and "| ATRASADA | 1 |" in texto
    assert "Divergem do selo do portal: 1" in texto
    assert "| links_atual.parquet | 2,5 MB |" in texto


def test_dia_completo_nao_tem_aviso_de_falta():
    montar_tudo()

    assert "Atenção" not in resumo_dia.gerar_resumo(HOJE)


def test_dia_sem_nada_avisa_cada_secao_e_nao_quebra():
    texto = resumo_dia.gerar_resumo(HOJE)

    assert "**Atenção:** sem dados em: Catálogo, Links, Conteúdo, Status, Estado." in texto
    assert "Sem listagem neste dia" in texto
    assert "Sem teste de links neste dia" in texto
    assert "Nenhum arquivo foi baixado neste dia" in texto
    assert "O status das bases não foi gerado neste dia" in texto


def test_so_o_conteudo_faltando_e_avisado_e_o_resto_aparece():
    # Cenário típico: o download de conteúdo não teve tempo, mas o resto do dia rodou
    montar_tudo()
    for arquivo in (portal.RAIZ / "dados" / "bronze" / "conteudo_tentativa" / f"data={HOJE}").glob("*.parquet"):
        arquivo.unlink()

    texto = resumo_dia.gerar_resumo(HOJE)

    assert "**Atenção:** sem dados em: Conteúdo." in texto
    assert "| Links testados no dia | 9 |" in texto


def test_dia_de_outra_data_nao_mistura_com_hoje():
    montar_tudo()

    texto = resumo_dia.gerar_resumo(date(2026, 10, 26))

    assert "Sem teste de links neste dia" in texto
    assert "| Links testados no dia | 9 |" not in texto


def test_main_imprime_o_resumo(monkeypatch, capsys):
    montar_tudo()
    monkeypatch.setattr(sys, "argv", ["resumo_dia.py", "--data", str(HOJE)])

    resumo_dia.main()

    assert capsys.readouterr().out.startswith("# Resumo do dia 2026-10-27")


def test_script_roda_direto_como_o_workflow_roda():
    # O workflow roda "python coletor/resumo_dia.py": o script precisa funcionar fora do pytest
    ambiente = {chave: valor for chave, valor in os.environ.items() if chave != "PYTHONPATH"}

    resultado = subprocess.run([sys.executable, str(Path(resumo_dia.__file__)), "--help"], capture_output=True, text=True, env=ambiente)

    assert resultado.returncode == 0, resultado.stderr
    assert "--data" in resultado.stdout
