"""Testes da saúde dos links (coletor/links.py).

Nenhum teste acessa a internet: os servidores são simulados com o MockTransport do httpx.
"""

import asyncio
import shutil
import sys
import time
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


def tentativa(link, data, status_http, erro_tipo=None, hora=12, content_length=None, last_modified=None, etag=None):
    """Grava uma tentativa de teste de link na Bronze."""
    servidor = link.split("/")[2]
    linha = (data, link, servidor, "HEAD", status_http, None, None, content_length, last_modified, etag, 50, erro_tipo,
             None, datetime(data.year, data.month, data.day, hora))
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
    # Erro de DNS conta como falha (timeout não conta: decisão 29)
    tentativa(link, DIA_2, None, "DNS")
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


@pytest.mark.parametrize("erro", ["TIMEOUT", "CONEXAO", "SERVIDOR_FORA"])
def test_resultado_inconclusivo_nao_conta_como_falha(erro):
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, None, erro)
    links.atualizar_estado(DIA_2)

    # O dia sem resposta não soma falha: o link continua como estava
    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 1
    assert linha["ultima_tentativa"] == DIA_1
    assert linha["status_http"] == 503


def test_http_403_nao_conta_como_falha():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, 403)
    links.atualizar_estado(DIA_2)

    # O 403 é bloqueio do teste, não prova que o link quebrou: o link continua como estava
    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 1
    assert linha["ultima_tentativa"] == DIA_1
    assert linha["status_http"] == 503


def test_link_nunca_testado_que_deu_403_fica_fora_do_estado():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 403)
    links.atualizar_estado(DIA_1)

    assert link not in ler_estado()


@pytest.mark.parametrize("status", [401, 404, 410, 500, 502])
def test_outros_status_de_erro_continuam_contando_como_falha(status):
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, status)
    links.atualizar_estado(DIA_2)

    assert ler_estado()[link]["falhas_seguidas"] == 2


@pytest.mark.parametrize("erro", ["DNS", "SSL"])
def test_dns_e_ssl_contam_como_falha(erro):
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, None, erro)
    links.atualizar_estado(DIA_2)

    assert ler_estado()[link]["falhas_seguidas"] == 2


def test_link_nunca_testado_com_resultado_inconclusivo_fica_fora_do_estado():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, None, "SERVIDOR_FORA")
    links.atualizar_estado(DIA_1)

    assert link not in ler_estado()


def test_dia_inconclusivo_no_meio_nao_zera_nem_soma():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, None, "TIMEOUT")
    links.atualizar_estado(DIA_2)
    tentativa(link, DIA_3, 404)
    links.atualizar_estado(DIA_3)

    # Duas falhas de verdade em dias diferentes: ainda não é quebrado (decisão 14)
    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 2
    assert linha["falha_desde"] == DIA_1


def test_inconclusivo_depois_de_sucesso_mantem_o_link_como_estava():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 200)
    links.atualizar_estado(DIA_1)
    tentativa(link, DIA_2, None, "TIMEOUT")
    links.atualizar_estado(DIA_2)

    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 0
    assert linha["ultimo_sucesso"] == DIA_1
    assert linha["ultima_tentativa"] == DIA_1


def test_reconstruir_refaz_o_estado_com_a_regra_atual(monkeypatch):
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    tentativa(link, DIA_2, None, "TIMEOUT")
    tentativa(link, DIA_3, 404)

    # Estado feito com a regra antiga (o timeout contava como falha): 3 falhas, link quebrado
    with monkeypatch.context() as antiga:
        antiga.setattr(links, "ERROS_INCONCLUSIVOS", ())
        for dia in (DIA_1, DIA_2, DIA_3):
            links.atualizar_estado(dia)
    assert ler_estado()[link]["falhas_seguidas"] == 3

    dias = links.reconstruir_estado()

    assert dias == ["2026-10-24", "2026-10-25", "2026-10-26"]
    linha = ler_estado()[link]
    assert linha["falhas_seguidas"] == 2
    assert linha["falha_desde"] == DIA_1


def test_reconstruir_sem_bronze_encerra_sem_mexer_no_estado():
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    links.atualizar_estado(DIA_1)
    shutil.rmtree(links.pasta_tentativas())

    with pytest.raises(SystemExit):
        links.reconstruir_estado()

    assert ler_estado()[link]["falhas_seguidas"] == 1


def test_main_reconstruir_nao_testa_nada_e_recria_o_estado(monkeypatch, capsys):
    link = "https://a.gov.br/1"
    tentativa(link, DIA_1, 503)
    monkeypatch.setattr(sys, "argv", ["links.py", "--reconstruir"])

    links.main()

    assert ler_estado()[link]["falhas_seguidas"] == 1
    assert "1 dia(s)" in capsys.readouterr().out


# --- Sinal de mudança pelos metadados (sem baixar o arquivo) ---

LINK_ARQUIVO = "https://a.gov.br/grande.csv"


def test_primeira_resposta_guarda_os_metadados_e_nao_conta_como_mudanca():
    tentativa(LINK_ARQUIVO, DIA_1, 200, content_length=5000, last_modified="Mon, 01 Jan 2026", etag='"v1"')
    links.atualizar_estado(DIA_1)

    linha = ler_estado()[LINK_ARQUIVO]
    assert (linha["content_length"], linha["last_modified"], linha["etag"]) == (5000, "Mon, 01 Jan 2026", '"v1"')
    assert linha["ultima_mudanca_metadados"] is None


def test_metadados_iguais_nao_contam_como_mudanca():
    for dia in (DIA_1, DIA_2):
        tentativa(LINK_ARQUIVO, dia, 200, content_length=5000, last_modified="Mon, 01 Jan 2026", etag='"v1"')
        links.atualizar_estado(dia)

    assert ler_estado()[LINK_ARQUIVO]["ultima_mudanca_metadados"] is None


@pytest.mark.parametrize("campo, novo", [
    ("content_length", 6000),
    ("last_modified", "Tue, 02 Feb 2026"),
    ("etag", '"v2"'),
])
def test_mudanca_de_qualquer_metadado_marca_o_dia(campo, novo):
    antes = {"content_length": 5000, "last_modified": "Mon, 01 Jan 2026", "etag": '"v1"'}
    tentativa(LINK_ARQUIVO, DIA_1, 200, **antes)
    links.atualizar_estado(DIA_1)
    tentativa(LINK_ARQUIVO, DIA_2, 200, **{**antes, campo: novo})
    links.atualizar_estado(DIA_2)

    assert ler_estado()[LINK_ARQUIVO]["ultima_mudanca_metadados"] == DIA_2


def test_tamanho_de_resposta_206_nao_conta_como_mudanca():
    # No GET com Range (206) o Content-Length é o tamanho do pedaço, não o do arquivo
    tentativa(LINK_ARQUIVO, DIA_1, 200, content_length=5000)
    links.atualizar_estado(DIA_1)
    tentativa(LINK_ARQUIVO, DIA_2, 206, content_length=2048)
    links.atualizar_estado(DIA_2)

    linha = ler_estado()[LINK_ARQUIVO]
    assert linha["ultima_mudanca_metadados"] is None
    assert linha["content_length"] == 5000


def test_campo_ausente_nao_apaga_o_anterior_nem_conta_como_mudanca():
    tentativa(LINK_ARQUIVO, DIA_1, 200, content_length=5000, etag='"v1"')
    links.atualizar_estado(DIA_1)
    tentativa(LINK_ARQUIVO, DIA_2, 200)
    links.atualizar_estado(DIA_2)

    linha = ler_estado()[LINK_ARQUIVO]
    assert (linha["content_length"], linha["etag"]) == (5000, '"v1"')
    assert linha["ultima_mudanca_metadados"] is None


@pytest.mark.parametrize("status, erro", [(503, None), (None, "TIMEOUT")])
def test_falha_ou_resultado_inconclusivo_mantem_os_metadados(status, erro):
    tentativa(LINK_ARQUIVO, DIA_1, 200, content_length=5000, last_modified="Mon, 01 Jan 2026", etag='"v1"')
    links.atualizar_estado(DIA_1)
    tentativa(LINK_ARQUIVO, DIA_2, status, erro)
    links.atualizar_estado(DIA_2)

    linha = ler_estado()[LINK_ARQUIVO]
    assert (linha["content_length"], linha["last_modified"], linha["etag"]) == (5000, "Mon, 01 Jan 2026", '"v1"')
    assert linha["ultima_mudanca_metadados"] is None


def test_aplicar_o_mesmo_dia_duas_vezes_mantem_a_data_da_mudanca():
    tentativa(LINK_ARQUIVO, DIA_1, 200, etag='"v1"')
    links.atualizar_estado(DIA_1)
    tentativa(LINK_ARQUIVO, DIA_2, 200, etag='"v2"')
    links.atualizar_estado(DIA_2)
    links.atualizar_estado(DIA_2)

    assert ler_estado()[LINK_ARQUIVO]["ultima_mudanca_metadados"] == DIA_2


def test_estado_antigo_sem_as_colunas_novas_continua_funcionando():
    # Estado gravado antes do sinal de mudança: só as 8 colunas originais
    arquivo = links.arquivo_estado()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    duckdb.sql(f"""COPY (SELECT 'https://a.gov.br/velho.csv' AS link, 'a.gov.br' AS servidor, DATE '2026-10-23' AS ultima_tentativa,
                         200 AS status_http, NULL::VARCHAR AS erro_tipo, 0 AS falhas_seguidas, NULL::DATE AS falha_desde,
                         DATE '2026-10-23' AS ultimo_sucesso)
                   TO '{arquivo.as_posix()}' (FORMAT parquet)""")
    tentativa("https://a.gov.br/velho.csv", DIA_1, 200, etag='"v1"')
    links.atualizar_estado(DIA_1)

    linha = ler_estado()["https://a.gov.br/velho.csv"]
    assert linha["etag"] == '"v1"'
    assert linha["ultima_mudanca_metadados"] is None
    assert linha["ultimo_sucesso"] == DIA_1


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


def test_para_quando_o_tempo_maximo_acaba(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        # Cada teste leva 0,3 s, mais que o limite de 0,2 s
        time.sleep(0.3)
        return httpx.Response(200)

    gravar_silver(DIA_1, [f"https://a.gov.br/{i}" for i in range(5)])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))

    feitos = asyncio.run(links.executar(links.selecionar(DIA_1), DIA_1, limite_segundos=0.2))

    # O primeiro teste começou dentro do prazo e terminou; o segundo nem começou
    assert feitos == 1
    assert len(chamadas) == 1
    # O que foi testado ficou gravado
    pasta = (links.pasta_tentativas() / f"data={DIA_1}" / "*.parquet").as_posix()
    assert duckdb.sql(f"SELECT COUNT(*) FROM '{pasta}'").fetchall()[0][0] == 1


def test_tempo_maximo_zero_nao_testa_nada_e_nao_quebra(monkeypatch):
    chamadas = []

    def responder(requisicao):
        chamadas.append(requisicao.url)
        return httpx.Response(200)

    gravar_silver(DIA_1, ["https://a.gov.br/1", "https://a.gov.br/2"])
    monkeypatch.setattr(links, "criar_cliente", lambda: cliente_falso(responder))
    monkeypatch.setattr(sys, "argv", ["links.py", "--data", str(DIA_1), "--tempo-maximo", "0"])

    links.main()

    # Nenhuma chamada, nenhuma tentativa gravada e o comando termina sem erro
    assert chamadas == []
    assert not (links.pasta_tentativas() / f"data={DIA_1}").exists()


def test_link_sem_teste_por_falta_de_tempo_volta_no_dia_seguinte(monkeypatch):
    gravar_silver(DIA_2, ["https://a.gov.br/testado", "https://a.gov.br/ficou"])
    tentativa("https://a.gov.br/testado", DIA_1, 200)
    links.atualizar_estado(DIA_1)
    monkeypatch.setattr(links, "MAX_POR_SERVIDOR", 1)

    escolhidos = links.selecionar(DIA_2)

    # Com uma vaga só, vai o que nunca foi testado
    assert escolhidos == {"a.gov.br": ["https://a.gov.br/ficou"]}


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