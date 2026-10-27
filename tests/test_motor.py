"""Testes do motor do pipeline diário (coletor/motor.py) e da data de referência (portal.data_de_hoje).

Nenhum script de verdade é executado: rodar_passo é trocado por uma
função falsa que só anota o que foi chamado.
"""

import sys
import time
from datetime import date, datetime, timezone

import pytest

import motor
import portal

DATA = date(2026, 10, 26)


def motor_falso(monkeypatch, falham=(), argumentos=(), extras_recebidos=None):
    """Troca rodar_passo por uma função falsa e devolve a lista de chamadas.

    Se extras_recebidos for um dicionário, nele fica anotado o que cada script recebeu além da data.
    """
    chamadas = []

    def rodar_passo(script, data, extras=()):
        chamadas.append((script, data))
        if extras_recebidos is not None:
            extras_recebidos[script] = list(extras)
        # Código 1 para os scripts que devem falhar, 0 para os outros
        return 1 if script in falham else 0

    monkeypatch.setattr(motor, "rodar_passo", rodar_passo)
    monkeypatch.setattr(sys, "argv", ["motor.py", "--data", str(DATA), *argumentos])
    return chamadas


def test_data_de_hoje_usa_o_fuso_de_brasilia():
    # 01:00 em UTC do dia 27 ainda é 22:00 do dia 26 em Brasília
    agora = datetime(2026, 10, 27, 1, 0, tzinfo=timezone.utc)
    assert portal.data_de_hoje(agora) == date(2026, 10, 26)

    # 04:00 em UTC já é 01:00 do dia 27 em Brasília
    agora = datetime(2026, 10, 27, 4, 0, tzinfo=timezone.utc)
    assert portal.data_de_hoje(agora) == date(2026, 10, 27)


def test_roda_todos_os_passos_em_ordem_com_a_mesma_data(monkeypatch):
    chamadas = motor_falso(monkeypatch)

    motor.main()

    assert chamadas == [
        ("catalogo_lista.py", DATA),
        ("painel_cgu.py", DATA),
        ("catalogo_detalhe.py", DATA),
        ("silver.py", DATA),
        ("links.py", DATA),
        ("silver_links.py", DATA),
        ("conteudo_baixar.py", DATA),
        ("silver_conteudo.py", DATA),
        ("gold_status.py", DATA),
    ]


def test_para_quando_um_passo_obrigatorio_falha(monkeypatch):
    chamadas = motor_falso(monkeypatch, falham={"catalogo_lista.py"})

    with pytest.raises(SystemExit):
        motor.main()

    # A listagem falhou: detalhe e Silver não rodam com dados velhos
    assert [script for script, _ in chamadas] == ["catalogo_lista.py"]


def test_continua_quando_o_painel_falha(monkeypatch):
    chamadas = motor_falso(monkeypatch, falham={"painel_cgu.py"})

    motor.main()

    assert [script for script, _ in chamadas] == [
        "catalogo_lista.py", "painel_cgu.py", "catalogo_detalhe.py", "silver.py", "links.py", "silver_links.py",
        "conteudo_baixar.py", "silver_conteudo.py", "gold_status.py",
    ]


@pytest.mark.parametrize("opcional", ["painel_cgu.py", "conteudo_baixar.py", "silver_conteudo.py", "gold_status.py"])
def test_passo_opcional_que_falha_nao_derruba_o_dia_e_avisa_no_github(monkeypatch, capsys, opcional):
    chamadas = motor_falso(monkeypatch, falham={opcional})

    motor.main()

    # Todos os passos rodaram e o motor terminou sem erro
    assert len(chamadas) == len(motor.PASSOS)
    saida = capsys.readouterr().out
    assert "::warning::Passo opcional" in saida
    assert "Passos opcionais que falharam" in saida


def test_conteudo_roda_depois_da_silver_dos_links(monkeypatch):
    # O seletor do download lê o link_status do dia, então a Silver dos links vem antes
    chamadas = motor_falso(monkeypatch)

    motor.main()

    scripts = [script for script, _ in chamadas]
    assert scripts.index("silver_links.py") < scripts.index("conteudo_baixar.py")
    assert scripts.index("conteudo_baixar.py") < scripts.index("silver_conteudo.py") < scripts.index("gold_status.py")


def test_desde_retoma_a_partir_de_um_passo(monkeypatch):
    chamadas = motor_falso(monkeypatch, argumentos=["--desde", "detalhe"])

    motor.main()

    assert [script for script, _ in chamadas] == [
        "catalogo_detalhe.py", "silver.py", "links.py", "silver_links.py",
        "conteudo_baixar.py", "silver_conteudo.py", "gold_status.py",
    ]


def test_apenas_roda_so_um_passo(monkeypatch):
    chamadas = motor_falso(monkeypatch, argumentos=["--apenas", "detalhe"])

    motor.main()

    assert chamadas == [("catalogo_detalhe.py", DATA)]


def test_apenas_antes_do_desde_nao_roda_nada(monkeypatch):
    chamadas = motor_falso(monkeypatch, argumentos=["--apenas", "lista", "--desde", "detalhe"])

    motor.main()

    assert chamadas == []


def test_apenas_depois_do_desde_roda(monkeypatch):
    chamadas = motor_falso(monkeypatch, argumentos=["--apenas", "silver", "--desde", "detalhe"])

    motor.main()

    assert chamadas == [("silver.py", DATA)]


def test_apenas_com_passo_obrigatorio_que_falha_encerra_com_erro(monkeypatch):
    motor_falso(monkeypatch, falham={"catalogo_detalhe.py"}, argumentos=["--apenas", "detalhe"])

    # O erro faz a etapa do workflow falhar e as seguintes não rodarem
    with pytest.raises(SystemExit):
        motor.main()


def test_orcamento_conta_a_partir_do_inicio_informado(monkeypatch):
    extras = {}
    # A execução começou há 60 minutos, em outro processo
    inicio = time.time() - 60 * 60
    motor_falso(monkeypatch, argumentos=["--apenas", "links", "--tempo-maximo", "200", "--inicio", str(inicio)],
                extras_recebidos=extras)

    motor.main()

    # 200 min de orçamento, menos 60 já gastos, menos 15 de reserva, menos 60 guardados para o conteúdo
    assert 64 < float(extras["links.py"][1]) <= 65


def test_sem_orcamento_de_tempo_nenhum_passo_recebe_extras(monkeypatch):
    extras = {}
    motor_falso(monkeypatch, extras_recebidos=extras)

    motor.main()

    assert all(recebidos == [] for recebidos in extras.values())


def test_orcamento_de_tempo_chega_so_aos_passos_com_tempo(monkeypatch):
    extras = {}
    motor_falso(monkeypatch, argumentos=["--tempo-maximo", "200"], extras_recebidos=extras)

    motor.main()

    # Links: o orçamento menos a reserva final (15) e menos os 60 minutos guardados para o conteúdo
    assert extras["links.py"][0] == "--tempo-maximo"
    assert 124 < float(extras["links.py"][1]) <= 125
    # Conteúdo: o orçamento menos a reserva final, e fica com tudo o que os links não usaram
    assert extras["conteudo_baixar.py"][0] == "--tempo-maximo"
    assert 184 < float(extras["conteudo_baixar.py"][1]) <= 185
    assert extras["catalogo_lista.py"] == []
    assert extras["silver_links.py"] == []
    assert extras["gold_status.py"] == []


def test_o_teste_de_links_deixa_tempo_guardado_para_o_conteudo(monkeypatch):
    extras = {}
    motor_falso(monkeypatch, argumentos=["--tempo-maximo", "100"], extras_recebidos=extras)

    motor.main()

    # Com 100 min, os links ficam com 25 e o conteúdo com 85: o conteúdo nunca fica sem tempo por causa dos links
    assert 24 < float(extras["links.py"][1]) <= 25
    assert 84 < float(extras["conteudo_baixar.py"][1]) <= 85
    assert float(extras["conteudo_baixar.py"][1]) > motor.TEMPO_GUARDADO_PARA_O_CONTEUDO_MINUTOS


def test_sem_tempo_os_passos_com_tempo_sao_pulados_e_o_resto_continua(monkeypatch):
    # O orçamento de 10 minutos é menor que a reserva: não sobra 1 minuto para links nem para conteúdo
    chamadas = motor_falso(monkeypatch, argumentos=["--tempo-maximo", "10"])

    motor.main()

    scripts = [script for script, _ in chamadas]
    assert "links.py" not in scripts
    assert "conteudo_baixar.py" not in scripts
    assert "silver_links.py" in scripts
    assert scripts[-1] == "gold_status.py"


def test_so_o_conteudo_roda_se_os_links_ja_gastaram_o_tempo_deles(monkeypatch):
    extras = {}
    # A execução já gastou 130 min de um orçamento de 200: os links não têm mais tempo, o conteúdo ainda tem
    inicio = time.time() - 130 * 60
    chamadas = motor_falso(monkeypatch, argumentos=["--tempo-maximo", "200", "--inicio", str(inicio)], extras_recebidos=extras)

    motor.main()

    scripts = [script for script, _ in chamadas]
    assert "links.py" not in scripts
    assert 54 < float(extras["conteudo_baixar.py"][1]) <= 55


def test_rodar_passo_passa_os_extras_ao_script(monkeypatch):
    comandos = []

    class Resultado:
        returncode = 0

    def run(comando):
        comandos.append(comando)
        return Resultado()

    monkeypatch.setattr(motor.subprocess, "run", run)

    motor.rodar_passo("links.py", DATA, ["--tempo-maximo", "90.0"])

    assert comandos[0][2:] == ["--data", "2026-10-26", "--tempo-maximo", "90.0"]


def test_rodar_passo_passa_a_data_para_o_script(monkeypatch):
    comandos = []

    class Resultado:
        returncode = 0

    def run(comando):
        comandos.append(comando)
        return Resultado()

    monkeypatch.setattr(motor.subprocess, "run", run)

    assert motor.rodar_passo("silver.py", DATA) == 0
    assert comandos[0][0] == sys.executable
    assert comandos[0][1].endswith("silver.py")
    assert comandos[0][2:] == ["--data", "2026-10-26"]