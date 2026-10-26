"""Testes do motor diário (coletor/motor.py) e da data de referência (portal.data_de_hoje).

Nenhum script de verdade é executado: rodar_passo é trocado por uma
função falsa que só anota o que foi chamado.
"""

import sys
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
    ]


def test_desde_retoma_a_partir_de_um_passo(monkeypatch):
    chamadas = motor_falso(monkeypatch, argumentos=["--desde", "detalhe"])

    motor.main()

    assert [script for script, _ in chamadas] == ["catalogo_detalhe.py", "silver.py", "links.py", "silver_links.py"]


def test_sem_orcamento_de_tempo_nenhum_passo_recebe_extras(monkeypatch):
    extras = {}
    motor_falso(monkeypatch, extras_recebidos=extras)

    motor.main()

    assert all(recebidos == [] for recebidos in extras.values())


def test_orcamento_de_tempo_chega_so_ao_teste_de_links(monkeypatch):
    extras = {}
    motor_falso(monkeypatch, argumentos=["--tempo-maximo", "100"], extras_recebidos=extras)

    motor.main()

    # Quase todo o orçamento, menos a reserva de 15 minutos para o que vem depois
    assert extras["links.py"][0] == "--tempo-maximo"
    assert 84 < float(extras["links.py"][1]) <= 85
    assert extras["catalogo_lista.py"] == []
    assert extras["silver_links.py"] == []


def test_sem_tempo_o_teste_de_links_e_pulado_e_o_resto_continua(monkeypatch):
    # O orçamento de 10 minutos é menor que a reserva: sobra menos de 1 minuto para os links
    chamadas = motor_falso(monkeypatch, argumentos=["--tempo-maximo", "10"])

    motor.main()

    scripts = [script for script, _ in chamadas]
    assert "links.py" not in scripts
    assert scripts[-1] == "silver_links.py"


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