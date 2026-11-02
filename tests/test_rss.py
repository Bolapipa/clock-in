"""Testes dos feeds RSS (publicar/gerar_rss.py).

Monta uma Silver e os eventos recentes falsos numa pasta temporária, gera os feeds
e confere o XML com casos inventados. Não usa rede.
"""

import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import duckdb
import pytest

import gerar_api
import gerar_rss
import gold_eventos
import gold_status
import portal
import silver

HOJE = date(2026, 10, 26)
ONTEM = HOJE - timedelta(days=1)


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Aponta Silver, Gold, estados e a saída dos feeds para uma pasta temporária (o SQL continua o do projeto)."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(silver, "PASTA_SILVER", tmp_path / "dados" / "silver")
    monkeypatch.setattr(gold_status, "PASTA_GOLD", tmp_path / "dados" / "gold")
    monkeypatch.setattr(gerar_rss, "PASTA_SAIDA", tmp_path / "web" / "public" / "rss")


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


def montar(*bases):
    """Grava a Silver das bases: cada uma é (id, título, órgão)."""
    def destino(nome):
        return silver.PASTA_SILVER / nome / f"data={HOJE}" / f"{nome}.parquet"

    gravar(destino("base"), "id VARCHAR, slug VARCHAR, titulo VARCHAR, periodicidade VARCHAR",
           [(i, f"base-{i}", titulo, "MENSAL") for i, titulo, _ in bases])
    gravar(destino("publicador"), "id VARCHAR, publicador VARCHAR, esfera VARCHAR",
           [(i, orgao, "FEDERAL") for i, _, orgao in bases])
    gravar(destino("base_saude"),
           "id VARCHAR, qtd_links BIGINT, qtd_testados BIGINT, qtd_ok BIGINT, qtd_em_observacao BIGINT, qtd_quebrados BIGINT, fora_do_ar BOOLEAN",
           [(i, 0, 0, 0, 0, 0, False) for i, _, _ in bases])
    gravar(destino("recurso"), "id_base VARCHAR, link VARCHAR", [])


def eventos_recentes(*eventos):
    """Grava o estado dos eventos recentes: (data, id da base, tipo, detalhe)."""
    gravar(gold_eventos.arquivo_eventos_recentes(), "data DATE, id_base VARCHAR, slug VARCHAR, tipo_evento VARCHAR, detalhe VARCHAR",
           [(data, i, f"base-{i}", tipo, detalhe) for data, i, tipo, detalhe in eventos])


def gerar():
    """Gera os feeds do dia e devolve a pasta de saída."""
    con = duckdb.connect()
    gerar_api.criar_views_entrada(con, HOJE)
    resultado = gerar_rss.gerar(con, HOJE, gerar_rss.PASTA_SAIDA)
    con.close()
    return gerar_rss.PASTA_SAIDA, resultado


def itens(pasta, *caminho):
    """Lê um feed e devolve os itens como [{título, link, descrição, guid, data}]."""
    canal = ET.parse(pasta.joinpath(*caminho)).getroot().find("channel")
    return [{"titulo": item.findtext("title"), "link": item.findtext("link"), "descricao": item.findtext("description"),
             "guid": item.findtext("guid"), "data": item.findtext("pubDate")} for item in canal.findall("item")]


def test_item_traz_titulo_endereco_da_base_descricao_data_e_guid_fixo():
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((HOJE, "a", "LINK_QUEBROU", "2 links passaram a ser considerados quebrados, por exemplo https://x.gov.br/1.csv"))

    pasta, _ = gerar()

    [item] = itens(pasta, "geral.xml")
    assert item["titulo"] == "Link quebrou: Base A"
    assert item["link"] == "https://clock-in-monitor.vercel.app/orgaos/orgao-a/?base=base-a"
    assert item["descricao"].startswith("Órgão A: 2 links passaram")
    assert item["guid"] == "clock-in-2026-10-26-a-LINK_QUEBROU"
    assert item["data"] == "Mon, 26 Oct 2026 12:00:00 +0000"


@pytest.mark.parametrize("tipo, rotulo", [
    ("STATUS_MUDOU", "Mudou de status"),
    ("CONTEUDO_MUDOU", "Conteúdo mudou"),
    ("SCHEMA_MUDOU", "Estrutura mudou"),
    ("LINK_QUEBROU", "Link quebrou"),
])
def test_cada_tipo_de_evento_tem_o_seu_rotulo(tipo, rotulo):
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((HOJE, "a", tipo, "detalhe"))

    pasta, _ = gerar()

    assert itens(pasta, "geral.xml")[0]["titulo"] == f"{rotulo}: Base A"


def test_feed_geral_traz_os_eventos_dos_mais_novos_para_os_mais_antigos():
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((ONTEM, "a", "SCHEMA_MUDOU", "velho"), (HOJE, "a", "CONTEUDO_MUDOU", "novo"))

    pasta, _ = gerar()

    assert [item["descricao"] for item in itens(pasta, "geral.xml")] == ["Órgão A: novo", "Órgão A: velho"]


def test_todo_orgao_tem_feed_mesmo_sem_evento_e_o_feed_vazio_e_valido():
    montar(("a", "Base A", "Órgão A"), ("b", "Base B", "Órgão B"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "mudou"))

    pasta, (_, orgaos, _) = gerar()

    assert orgaos == 2
    assert len(itens(pasta, "orgaos", "orgao-a.xml")) == 1
    assert itens(pasta, "orgaos", "orgao-b.xml") == []


def test_feed_do_orgao_so_traz_os_eventos_das_bases_dele():
    montar(("a", "Base A", "Órgão A"), ("b", "Base B", "Órgão B"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "da A"), (HOJE, "b", "SCHEMA_MUDOU", "da B"))

    pasta, _ = gerar()

    assert [item["titulo"] for item in itens(pasta, "orgaos", "orgao-b.xml")] == ["Estrutura mudou: Base B"]


def test_feed_de_base_so_existe_para_quem_teve_evento():
    montar(("a", "Base A", "Órgão A"), ("b", "Base B", "Órgão B"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "mudou"))

    pasta, (_, _, bases) = gerar()

    assert bases == 1
    assert (pasta / "bases" / "base-a.xml").exists()
    assert not (pasta / "bases" / "base-b.xml").exists()


def test_evento_de_base_que_saiu_do_catalogo_fica_de_fora():
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "fica"), (HOJE, "sumiu", "CONTEUDO_MUDOU", "some"))

    pasta, (usados, _, _) = gerar()

    assert usados == 1
    assert [item["descricao"] for item in itens(pasta, "geral.xml")] == ["Órgão A: fica"]


def test_caracteres_especiais_do_xml_sao_escapados():
    montar(("a", "Saúde & <Educação>", "Órgão A"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "de 1 > 2 & mais"))

    pasta, _ = gerar()

    [item] = itens(pasta, "geral.xml")
    assert item["titulo"] == "Conteúdo mudou: Saúde & <Educação>"
    assert item["descricao"] == "Órgão A: de 1 > 2 & mais"


def test_feed_respeita_o_limite_de_itens(monkeypatch):
    monkeypatch.setattr(gerar_rss, "MAX_ITENS_GERAL", 2)
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes(*[(HOJE - timedelta(days=dias), "a", "CONTEUDO_MUDOU", f"d{dias}") for dias in range(5)])

    pasta, _ = gerar()

    # Ficam os dois mais novos
    assert [item["descricao"] for item in itens(pasta, "geral.xml")] == ["Órgão A: d0", "Órgão A: d1"]


def test_sem_eventos_recentes_os_feeds_saem_vazios_e_nada_quebra():
    montar(("a", "Base A", "Órgão A"))

    pasta, (usados, _, bases) = gerar()

    assert (usados, bases) == (0, 0)
    assert itens(pasta, "geral.xml") == []
    assert itens(pasta, "orgaos", "orgao-a.xml") == []


def test_o_mesmo_acontecimento_tem_sempre_o_mesmo_guid():
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "mudou"))

    pasta, _ = gerar()
    primeiro = itens(pasta, "geral.xml")[0]["guid"]
    gerar()

    assert itens(pasta, "geral.xml")[0]["guid"] == primeiro


def test_feeds_de_uma_execucao_anterior_sao_removidos():
    montar(("a", "Base A", "Órgão A"), ("b", "Base B", "Órgão B"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "x"), (HOJE, "b", "CONTEUDO_MUDOU", "y"))
    pasta, _ = gerar()
    assert (pasta / "orgaos" / "orgao-b.xml").exists() and (pasta / "bases" / "base-b.xml").exists()

    montar(("a", "Base A", "Órgão A"))
    gerar()

    assert not (pasta / "orgaos" / "orgao-b.xml").exists()
    assert not (pasta / "bases" / "base-b.xml").exists()


def test_xml_em_utf8_sem_escapar_os_acentos():
    montar(("a", "Atualização diária", "Ministério da Saúde"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "mudou"))

    pasta, _ = gerar()

    texto = (pasta / "geral.xml").read_text(encoding="utf-8")
    assert texto.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "Atualização diária" in texto


def test_main_grava_os_feeds_e_mostra_o_resumo(monkeypatch, capsys, tmp_path):
    montar(("a", "Base A", "Órgão A"))
    eventos_recentes((HOJE, "a", "CONTEUDO_MUDOU", "mudou"))
    saida = tmp_path / "outra"
    monkeypatch.setattr(sys, "argv", ["gerar_rss.py", "--data", str(HOJE), "--saida", str(saida)])

    gerar_rss.main()

    assert (saida / "geral.xml").exists()
    assert "1 eventos recentes; feeds: 1 geral, 1 de órgãos, 1 de bases" in capsys.readouterr().out
