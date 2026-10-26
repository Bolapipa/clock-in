"""Testes do estado e do histórico nos releases (coletor/nuvem.py).

Nenhum teste fala com o GitHub: o gh é trocado por um GitHub falso que
guarda os releases num dicionário.
"""

import tarfile
from datetime import date
from pathlib import Path

import pytest

import nuvem
import portal

DIA = date(2026, 10, 26)


class GithubFalso:
    """Imita os comandos do gh usados pelo nuvem.py, guardando os releases em memória."""

    def __init__(self):
        # {tag: {nome do arquivo: conteúdo}}
        self.releases = {}

    def __call__(self, *argumentos):
        comando, tag = argumentos[:2], argumentos[2]
        if comando == ("release", "view"):
            if tag not in self.releases:
                raise nuvem.FalhaGh("release not found")
            return "\n".join(self.releases[tag]) + "\n"
        if comando == ("release", "create"):
            self.releases[tag] = {}
        elif comando == ("release", "upload"):
            arquivo = Path(argumentos[3])
            self.releases[tag][arquivo.name] = arquivo.read_bytes()
        elif comando == ("release", "download"):
            nome = argumentos[argumentos.index("--pattern") + 1]
            pasta = Path(argumentos[argumentos.index("--dir") + 1])
            (pasta / nome).write_bytes(self.releases[tag][nome])
        elif comando == ("release", "delete-asset"):
            del self.releases[tag][argumentos[3]]
        return ""


@pytest.fixture
def github(monkeypatch):
    falso = GithubFalso()
    monkeypatch.setattr(nuvem, "gh", falso)
    return falso


@pytest.fixture(autouse=True)
def raiz_temporaria(tmp_path, monkeypatch):
    monkeypatch.setattr(portal, "RAIZ", tmp_path / "maquina_1")


def gravar(caminho, conteudo):
    """Grava um arquivo de mentira dentro de dados/ e devolve o caminho completo."""
    arquivo = portal.RAIZ / "dados" / caminho
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(conteudo)
    return arquivo


def montar_estado(dia, versao=b"1"):
    """Grava o que um dia de motor deixa na máquina: estado, listagem e cronograma."""
    gravar("estado/detalhe_atual.parquet", b"detalhe-" + versao)
    gravar("estado/links_atual.parquet", b"links-" + versao)
    gravar(f"bronze/catalogo_lista/data={dia}/catalogo_lista.parquet", b"lista-" + str(dia).encode())
    gravar("bronze/painel_cgu_cronograma/data=2026-10-01/painel_cgu_cronograma.parquet", b"cronograma")


def test_subir_e_baixar_devolvem_o_estado_em_outra_maquina(github, tmp_path, monkeypatch):
    montar_estado(DIA)
    # Uma listagem mais antiga que não precisa ir junto
    gravar("bronze/catalogo_lista/data=2026-10-20/catalogo_lista.parquet", b"lista-velha")

    nuvem.subir(DIA)

    # Outra máquina, sem nada: baixa e confere
    monkeypatch.setattr(portal, "RAIZ", tmp_path / "maquina_2")
    nuvem.baixar()

    dados = portal.RAIZ / "dados"
    assert (dados / "estado" / "detalhe_atual.parquet").read_bytes() == b"detalhe-1"
    assert (dados / "estado" / "links_atual.parquet").read_bytes() == b"links-1"
    assert (dados / "bronze" / "catalogo_lista" / f"data={DIA}" / "catalogo_lista.parquet").exists()
    assert not (dados / "bronze" / "catalogo_lista" / "data=2026-10-20").exists()
    assert (dados / "bronze" / "painel_cgu_cronograma" / "data=2026-10-01" / "painel_cgu_cronograma.parquet").exists()


def test_nao_sobe_estado_sem_o_detalhe(github):
    gravar("bronze/catalogo_lista/data=2026-10-26/catalogo_lista.parquet", b"lista")

    with pytest.raises(SystemExit):
        nuvem.subir(DIA)

    assert github.releases == {}


def test_guarda_so_os_tres_estados_mais_recentes(github):
    for dia in range(20, 25):
        montar_estado(date(2026, 10, dia))
        nuvem.subir(date(2026, 10, dia))

    assert sorted(github.releases["estado-atual"]) == [
        "estado-2026-10-22.tar.gz", "estado-2026-10-23.tar.gz", "estado-2026-10-24.tar.gz",
    ]


def test_baixa_o_estado_mais_recente(github, tmp_path, monkeypatch):
    montar_estado(date(2026, 10, 24), versao=b"antigo")
    nuvem.subir(date(2026, 10, 24))
    montar_estado(date(2026, 10, 25), versao=b"novo")
    nuvem.subir(date(2026, 10, 25))

    monkeypatch.setattr(portal, "RAIZ", tmp_path / "maquina_2")
    nuvem.baixar()

    assert (portal.RAIZ / "dados" / "estado" / "detalhe_atual.parquet").read_bytes() == b"detalhe-novo"


def test_baixar_sem_release_encerra_com_instrucao(github):
    with pytest.raises(SystemExit) as erro:
        nuvem.baixar()

    assert "subir" in str(erro.value)


def test_extrair_recusa_caminho_fora_da_raiz(tmp_path):
    pacote = tmp_path / "ruim.tar.gz"
    arquivo = tmp_path / "fora.txt"
    arquivo.write_text("x")
    with tarfile.open(pacote, "w:gz") as tar:
        tar.add(arquivo, arcname="../fora.txt")

    with pytest.raises(tarfile.FilterError):
        nuvem.extrair(pacote)


def test_historico_vai_para_o_release_do_mes_so_com_o_dia(github):
    gravar(f"silver/link_status/data={DIA}/link_status.parquet", b"status")
    gravar(f"bronze/link_tentativa/data={DIA}/parte-0001.parquet", b"tentativas")
    gravar("silver/link_status/data=2026-10-25/link_status.parquet", b"dia-anterior")

    nuvem.historico(DIA)

    assert list(github.releases) == ["historico-2026-10"]
    assert list(github.releases["historico-2026-10"]) == ["dia-2026-10-26.tar.gz"]

    pacote = portal.RAIZ / "dia.tar.gz"
    pacote.write_bytes(github.releases["historico-2026-10"]["dia-2026-10-26.tar.gz"])
    with tarfile.open(pacote) as tar:
        nomes = sorted(tar.getnames())
    assert nomes == [
        f"dados/bronze/link_tentativa/data={DIA}/parte-0001.parquet",
        f"dados/silver/link_status/data={DIA}/link_status.parquet",
    ]


def test_historico_sem_nada_produzido_nao_envia(github):
    nuvem.historico(DIA)

    assert github.releases == {}