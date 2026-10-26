"""Testes da saúde dos links (coletor/links.py).

Nenhum teste acessa a internet: os servidores são simulados com o MockTransport do httpx.
"""

import asyncio
import sys
from datetime import date, datetime

import duckdb
import httpx
import pytest

import links
import portal

DIA_1 = date(2026, 10, 24)
DIA_2 = date(2026, 10, 25)
DIA_3 = date(2026, 10, 26)


@pytest.fixture(autouse=True)
def raiz_temporaria(tmp_path, monkeypatch):
    """Aponta Bronze, Silver e estado para uma pasta temporária, e zera as esperas."""
    monkeypatch.setattr(portal, "RAIZ", tmp_path)
    monkeypatch.setattr(links, "PAUSA_POR_SERVIDOR", 0)


def cliente_falso(responder):
    """Cliente assíncrono que responde com a função 'responder'."""
    return httpx.AsyncClient(transport=httpx.MockTransport(responder), follow_redirects=True)


def resultado_do_teste(responder, link="https://x.gov.br/a.csv"):
    """Testa um link com um servidor falso e devolve a linha da Bronze como dicionário."""
    async def rodar():
        async with cliente_falso(responder) as cliente:
            return await links.testar_link(cliente, DIA_1, link, "x.gov.br")

    colunas = ["data_coleta", "link", "servidor", "metodo", "status_http", "url_final", "content_type",
               "content_length", "last_modified", "etag", "tempo_ms", "erro_tipo", "erro", "tentado_em"]
    return dict(zip(colunas, asyncio.run(rodar())))


def gravar_silver(data, lista_de_links):
    """Grava uma Silver de recursos falsa, só com a coluna link."""
    arquivo = links.arquivo_recurso(data)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    valores = ", ".join(f"('{link}')" for link in lista_de_links)
    duckdb.sql(f"COPY (SELECT * FROM (VALUES {valores}) t(link)) TO '{arquivo.as_posix()}' (FORMAT parquet)")


def tentativa(link, data, status_http, erro_tipo=None, hora=12):
    """Grava uma tentativa de teste de link na Bronze."""
    servidor = link.split("/")[2]
    linha = (data, link, servidor, "HEAD", status_http, None, None, None, None, None, 50, erro_tipo, None,
             datetime(data.year, data.month, data.day, hora))
    links.gravar_lote([linha], data)


def ler_estado():
    """Lê o arquivo de estado como {link: linha}."""
    resultado = duckdb.sql(f"SELECT * FROM '{links.arquivo_estado().as_posix()}'")
    colunas = resultado.columns
    return {linha[0]: dict(zip(colunas, linha)) for linha in resultado.fetchall()}


# --- Teste de um link ---

def test_head_com_sucesso():
    resposta = httpx.Response(200, headers={"content-type": "text/csv", "content-length": "123", "etag": "abc"})

    linha = resultado_do_teste(lambda requisicao: resposta)

    assert linha["metodo"] == "HEAD"
    assert linha["status_http"] == 200
    assert linha["content_type"] == "text/csv"
    assert linha["content_length"] == 123
    assert linha["etag"] == "abc"
    assert linha["erro_tipo"] is None


def test_usa_get_com_range_quando_o_servidor_recusa_head():
    metodos = []

    def responder(requisicao):
        metodos.append((requisicao.method, requisicao.headers.get("range")))
        return httpx.Response(405 if requisicao.method == "HEAD" else 206)

    linha = resultado_do_teste(responder)

    assert metodos == [("HEAD", None), ("GET", "bytes=0-2047")]
    assert linha["metodo"] == "GET"
    assert linha["status_http"] == 206


def test_erro_404_nao_tenta_get():
    metodos = []

    def responder(requisicao):
        metodos.append(requisicao.method)
        return httpx.Response(404)

    linha = resultado_do_teste(responder)

    assert metodos == ["HEAD"]
    assert linha["status_http"] == 404


def test_timeout_vira_tipo_de_erro():
    def responder(requisicao):
        raise httpx.ReadTimeout("demorou", request=requisicao)

    linha = resultado_do_teste(responder)

    assert linha["status_http"] is None
    assert linha["erro_tipo"] == "TIMEOUT"


def test_classifica_erros_de_dns_e_ssl():
    dns = httpx.ConnectError("[Errno 11001] getaddrinfo failed")
    ssl = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    recusada = httpx.ConnectError("Connection refused")

    assert links.classificar_erro(dns) == "DNS"
    assert links.classificar_erro(ssl) == "SSL"
    assert links.classificar_erro(recusada) == "CONEXAO"
    assert links.classificar_erro(ValueError("x")) == "OUTRO"


# --- Escolha dos links do dia ---

def test_ignora_links_que_nao_sao_http_e_repetidos():
    gravar_silver(DIA_1, ["https://a.gov.br/1", "https://a.gov.br/1", "ftp://b.gov.br/2", "sem link", "http://c.gov.br/3"])

    escolhidos = links.selecionar(DIA_1)

    assert escolhidos == {"a.gov.br": ["https://a.gov.br/1"], "c.gov.br": ["http://c.gov.br/3"]}


def test_limita_por_servidor_e_prefere_os_testados_ha_mais_tempo(monkeypatch):
    monkeypatch.setattr(links, "MAX_POR_SERVIDOR", 2)
    gravar_silver(DIA_3, ["https://a.gov.br/velho", "https://a.gov.br/recente", "https://a.gov.br/novo",
                          "https://b.gov.br/1"])
    tentativa("https://a.gov.br/velho", DIA_1, 200)
    tentativa("https://a.gov.br/recente", DIA_2, 200)
    links.atualizar_estado(DIA_1)
    links.atualizar_estado(DIA_2)

    escolhidos = links.selecionar(DIA_3)

    # Nunca testado vem primeiro, depois o testado há mais tempo; o mais recente fica de fora
    assert sorted(escolhidos["a.gov.br"]) == ["https://a.gov.br/novo", "https://a.gov.br/velho"]
    assert escolhidos["b.gov.br"] == ["https://b.gov.br/1"]


def test_retoma_sem_repetir_e_sem_passar_do_limite(monkeypatch):
    monkeypatch.setattr(links, "MAX_POR_SERVIDOR", 2)
    gravar_silver(DIA_1, ["https://a.gov.br/1", "https://a.gov.br/2", "https://a.gov.br/3"])
    tentativa("https://a.gov.br/1", DIA_1, 200)

    escolhidos = links.selecionar(DIA_1)

    # O link 1 já foi feito hoje e ocupa uma das 2 vagas: sobra só uma
    assert len(escolhidos["a.gov.br"]) == 1
    assert "https://a.gov.br/1" not in escolhidos["a.gov.br"]


def test_amostra_limita_o_total():
    gravar_silver(DIA_1, [f"https://s{i}.gov.br/x" for i in range(10)])

    escolhidos = links.selecionar(DIA_1, limite=3)

    assert sum(len(lista) for lista in escolhidos.values()) == 3


def test_sem_silver_do_dia_encerra():
    with pytest.raises(SystemExit):
        links.selecionar(DIA_1)


# --- Estado dos links ---

def test_tres_falhas_em_dias_seguidos_e_sucesso_zera():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, None, "TIMEOUT")
    links.atualizar_estado(DIA_2)
    tentativa(link, DIA_3, 404)
    links.atualizar_estado(DIA_3)

    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 3
    assert linha["falha_desde"] == DIA_1
    assert linha["ultimo_sucesso"] is None

    tentativa(link, date(2026, 10, 27), 200)
    links.atualizar_estado(date(2026, 10, 27))

    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 0
    assert linha["falha_desde"] is None
    assert linha["ultimo_sucesso"] == date(2026, 10, 27)


def test_atualizar_duas_vezes_no_dia_nao_conta_falha_em_dobro():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 500)
    links.atualizar_estado(DIA_1)
    links.atualizar_estado(DIA_1)

    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 1
    assert linha["falha_desde"] == DIA_1


def test_falha_mantem_a_data_do_ultimo_sucesso():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 200)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, 502)
    links.atualizar_estado(DIA_2)

    linha = ler_estado()[link]
    assert linha["ultimo_sucesso"] == DIA_1
    assert linha["falha_desde"] == DIA_2
    assert linha["falhas_seguidas"] == 1


def test_partes_numeradas_sem_sobrescrever():
    for _ in range(3):
        tentativa("https://a.gov.br/1", DIA_1, 200)
    pasta = links.pasta_tentativas() / f"data={DIA_1}"

    (pasta / "parte-0002.parquet").unlink()
    tentativa("https://a.gov.br/1", DIA_1, 200)

    nomes = sorted(arquivo.name for arquivo in pasta.iterdir())
    assert nomes == ["parte-0001.parquet", "parte-0003.parquet", "parte-0004.parquet"]


# --- O comando inteiro ---

def test_main_testa_grava_e_atualiza_o_estado(monkeypatch):
    def responder(requisicao):
        # Um servidor saudável e outro que sempre dá 404
        return httpx.Response(200 if requisicao.url.host == "ok.gov.br" else 404)

    gravar_silver(DIA_1, ["https://ok.gov.br/1", "https://ok.gov.br/2", "https://quebrado.gov.br/1"])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["links.py", "--data", str(DIA_1)])

    links.main()

    pasta = (links.pasta_tentativas() / f"data={DIA_1}" / "*.parquet").as_posix()
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{pasta}'").fetchall()[0][0] == 3
    estado = ler_estado()
    assert estado["https://ok.gov.br/1"]["falhas_seguidas"] == 0
    assert estado["https://quebrado.gov.br/1"]["falhas_seguidas"] == 1


def test_gravar_o_que_foi_testado_mesmo_se_interrompido(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        if len(chamadas) == 2:
            raise KeyboardInterrupt
        return httpx.Response(200)

    gravar_silver(DIA_1, ["https://a.gov.br/1", "https://a.gov.br/2", "https://a.gov.br/3"])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["links.py", "--data", str(DIA_1)])

    with pytest.raises(KeyboardInterrupt):
        links.main()

    # O primeiro link foi testado antes da interrupção e ficou gravado na Bronze
    pasta = (links.pasta_tentativas() / f"data={DIA_1}" / "*.parquet").as_posix()
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{pasta}'").fetchall()[0][0] == 1


def test_desiste_do_servidor_depois_de_falhas_de_rede_seguidas(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        raise httpx.ConnectTimeout("sem resposta", request=requisicao)

    monkeypatch.setattr(links, "FALHAS_DE_REDE_PARA_DESISTIR", 3)
    gravar_silver(DIA_1, [f"https://morto.gov.br/{i}" for i in range(10)])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["links.py", "--data", str(DIA_1)])

    links.main()

    # Só 3 chamadas de verdade; os outros 7 links foram registrados como falha sem esperar
    assert len(chamadas) == 3
    pasta = (links.pasta_tentativas() / f"data={DIA_1}" / "*.parquet").as_posix()
    tipos = dict(duckdb.sql(f"SELECT erro_tipo, COUNT(*) FROM '{pasta}' GROUP BY 1").fetchall())
    assert tipos == {"TIMEOUT": 3, "SERVIDOR_FORA": 7}
    assert all(linha["falhas_seguidas"] == 1 for linha in ler_estado().values())


def test_erro_de_um_link_nao_faz_desistir_do_servidor(monkeypatch):
    def responder(requisicao):
        # 404 não é falha de rede: o servidor está vivo
        return httpx.Response(404)

    monkeypatch.setattr(links, "FALHAS_DE_REDE_PARA_DESISTIR", 2)
    gravar_silver(DIA_1, [f"https://vivo.gov.br/{i}" for i in range(6)])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["links.py", "--data", str(DIA_1)])

    links.main()

    pasta = (links.pasta_tentativas() / f"data={DIA_1}" / "*.parquet").as_posix()
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{pasta}' WHERE status_http = 404").fetchall()[0][0] == 6