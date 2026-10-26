"""Testes da regra do publicador real (sql/silver_publicador.sql, decisão 13).

Monta uma Bronze falsa com um caso para cada degrau da cascata,
gera a Silver e confere quem foi apontado como publicador.
A tabela de referência usada é a real (referencia/dominios.csv).
"""

import json
from datetime import date, datetime

import duckdb
import pytest

import catalogo_detalhe
import catalogo_lista
import estado
import painel_cgu
import portal
import silver

HOJE = date(2026, 10, 25)

# Uma base para cada situação: slug -> detalhe (organização, e-mail e links)
BASES = {
    "base-no-cronograma": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://exemplo.gov.br/a.csv"]},
    "base-com-organizacao": {"organizacao": "universidade-federal-x", "links": ["https://dados.ufx.edu.br/a.csv"]},
    "base-do-banco-central": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://www3.bcb.gov.br/a.csv"]},
    "base-de-prefeitura": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://dados.fortaleza.ce.gov.br/a.csv"]},
    "base-de-estado": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://www.sef.sc.gov.br/a.csv"]},
    "base-no-gov-br": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://www.gov.br/inpi/pt-br/a.csv"]},
    "base-so-com-email": {"organizacao": "controladoria-geral-da-uniao", "email": "fulano@enap.gov.br",
                          "links": ["https://drive.google.com/file/a"]},
    "base-sem-pista": {"organizacao": "controladoria-geral-da-uniao", "email": "fulano@gmail.com",
                       "links": ["https://drive.google.com/file/b"]},
    # Um link em cada domínio: empate, vence o primeiro em ordem alfabética
    "base-com-empate": {"organizacao": "controladoria-geral-da-uniao",
                        "links": ["https://b.gov.br/1.csv", "https://a.gov.br/2.csv"]},
    # Dois e-mails no mesmo campo: vale o domínio do primeiro
    "base-email-duplo": {"organizacao": "controladoria-geral-da-uniao", "email": "cren@ibge.gov.br,luciana@x.gov.br",
                         "links": ["https://drive.google.com/file/c"]},
    # Link no próprio portal (dados.gov.br) não diz quem publicou
    "base-no-portal": {"organizacao": "controladoria-geral-da-uniao", "links": ["https://wiki.dados.gov.br/x"]},
}


@pytest.fixture(scope="module")
def resultado(tmp_path_factory):
    """Gera a Silver uma vez para todos os testes.

    Devolve as linhas do publicador ({slug: linha}) e o resultado
    de 3 novas execuções, para conferir que nada muda entre elas.
    """
    raiz = tmp_path_factory.mktemp("clock-in")
    mp = pytest.MonkeyPatch()
    # try/finally: desfaz as trocas mesmo se a preparação falhar
    try:
        mp.setattr(portal, "RAIZ", raiz)
        mp.setattr(catalogo_detalhe, "PASTA_DETALHE", raiz / "dados" / "bronze" / "catalogo_detalhe")
        mp.setattr(silver, "PASTA_BRONZE", raiz / "dados" / "bronze")
        mp.setattr(silver, "PASTA_SILVER", raiz / "dados" / "silver")

        # Listagem e detalhe: o id de cada base é o próprio slug
        registros = [{"id": slug, "nome": slug} for slug in BASES]
        catalogo_lista.gravar_bronze([(HOJE, 1, len(registros), json.dumps(registros), datetime(2026, 10, 25))], HOJE)
        for slug, dados in BASES.items():
            payload = {
                "id": slug,
                "organizacao": dados["organizacao"],
                "emailResponsavel": dados.get("email"),
                "recursos": [{"id": f"{slug}-{i}", "link": link} for i, link in enumerate(dados["links"])],
            }
            linha = (HOJE, slug, "NOVA", None, 200, json.dumps(payload), None, datetime(2026, 10, 25))
            catalogo_detalhe.gravar_lote([linha], HOJE)

        # Cronograma da CGU: uma linha aponta para a base, outra não tem link
        csv = raiz / "cronograma.csv"
        csv.write_bytes(
            "Orgao;nome_base;url_base\n"
            "MINX - Ministério X;Base;https://dados.gov.br/dados/conjuntos-dados/base-no-cronograma\n"
            "MINY - Ministério Y;Sem link;\n".encode("utf-8")
        )
        painel_cgu.gravar_bronze(csv, "cronograma", HOJE, None)

        # Gera o estado, e depois base, recurso e publicador, como o silver.py faz
        estado.reconstruir()
        con = duckdb.connect()
        silver.criar_views_entrada(con, HOJE)
        silver.criar_views_referencia(con, HOJE)
        for nome, arquivo_sql in silver.TABELAS.items():
            silver.gerar_tabela(con, nome, arquivo_sql, HOJE)

        consulta = con.execute("SELECT * FROM silver_publicador")
        colunas = [c[0] for c in consulta.description]
        linhas = {linha[0]: dict(zip(colunas, linha)) for linha in consulta.fetchall()}

        # Gera o publicador mais 3 vezes e guarda o resultado de cada uma
        repeticoes = []
        for _ in range(3):
            silver.gerar_tabela(con, "publicador", silver.TABELAS["publicador"], HOJE)
            repeticoes.append(con.execute("SELECT * FROM silver_publicador ORDER BY id").fetchall())
        con.close()
    finally:
        mp.undo()
    return {"linhas": linhas, "repeticoes": repeticoes}


@pytest.fixture(scope="module")
def publicadores(resultado):
    """Atalho: só as linhas do publicador, {slug: linha}."""
    return resultado["linhas"]


def test_rodar_de_novo_da_o_mesmo_resultado(resultado):
    primeira, *outras = resultado["repeticoes"]
    assert all(outra == primeira for outra in outras)


def test_uma_linha_por_base(publicadores):
    assert set(publicadores) == set(BASES)


def test_cronograma_da_cgu_vem_primeiro(publicadores):
    base = publicadores["base-no-cronograma"]
    assert base["origem_publicador"] == "PAINEL_CGU"
    assert base["publicador"] == "MINX - Ministério X"
    assert base["esfera"] == "FEDERAL"


def test_organizacao_quando_nao_e_cgu(publicadores):
    base = publicadores["base-com-organizacao"]
    assert base["origem_publicador"] == "ORGANIZACAO"
    assert base["publicador"] == "universidade-federal-x"


def test_dominio_do_link_usa_a_referencia(publicadores):
    # www3.bcb.gov.br termina em bcb.gov.br, que está na tabela de referência
    base = publicadores["base-do-banco-central"]
    assert base["origem_publicador"] == "DOMINIO_LINK"
    assert base["publicador"] == "BCB - Banco Central do Brasil"
    assert base["esfera"] == "FEDERAL"


def test_prefeitura_pela_referencia(publicadores):
    base = publicadores["base-de-prefeitura"]
    assert base["publicador"] == "Prefeitura de Fortaleza"
    assert base["esfera"] == "MUNICIPAL"


def test_orgao_estadual_pela_uf_no_dominio(publicadores):
    base = publicadores["base-de-estado"]
    assert base["esfera"] == "ESTADUAL"


def test_www_gov_br_usa_o_caminho(publicadores):
    base = publicadores["base-no-gov-br"]
    assert base["evidencia"] == "www.gov.br/inpi"
    assert base["publicador"] == "INPI - Instituto Nacional da Propriedade Industrial"


def test_email_quando_o_link_e_hospedagem(publicadores):
    base = publicadores["base-so-com-email"]
    assert base["origem_publicador"] == "DOMINIO_EMAIL"
    assert base["evidencia"] == "enap.gov.br"
    assert base["esfera"] == "FEDERAL"


def test_empate_de_dominios_escolhe_sempre_o_mesmo(publicadores):
    base = publicadores["base-com-empate"]
    assert base["evidencia"] == "a.gov.br"


def test_email_com_dois_enderecos_usa_o_primeiro(publicadores):
    base = publicadores["base-email-duplo"]
    assert base["origem_publicador"] == "DOMINIO_EMAIL"
    assert base["evidencia"] == "ibge.gov.br"
    assert base["publicador"] == "IBGE - Fundação Instituto Brasileiro de Geografia e Estatística"


def test_link_no_proprio_portal_nao_identifica(publicadores):
    base = publicadores["base-no-portal"]
    assert base["origem_publicador"] == "NAO_IDENTIFICADO"


def test_sem_pista_fica_nao_identificado(publicadores):
    # Link no Google Drive e e-mail pessoal: nenhuma fonte serve
    base = publicadores["base-sem-pista"]
    assert base["origem_publicador"] == "NAO_IDENTIFICADO"
    assert base["publicador"] is None
    assert base["esfera"] is None
