"""Guarda e recupera o estado do motor nos releases do GitHub (Fase 2).

O GitHub Actions começa do zero a cada execução. Este script faz a ponte
entre uma execução e a próxima, sem commitar nenhum dado no Git (decisão 16):

- release "estado-atual": o que o motor precisa para continuar no dia seguinte,
  num arquivo estado-AAAA-MM-DD.tar.gz. Guarda os 3 mais recentes, então uma
  gravação que falhe no meio nunca apaga o último estado bom.
  Conteúdo: dados/estado/*.parquet, a última listagem do catálogo (para a
  conferência de tamanho) e o último cronograma da CGU (para o publicador).
- release "historico-AAAA-MM": o que o dia produziu (Silver, tentativas de links,
  tentativas de leitura de conteúdo, detalhes coletados), num arquivo dia-AAAA-MM-DD.tar.gz.

Usa o GitHub CLI (gh), já instalado nos runners do Actions; lá o login vem da
variável GH_TOKEN.

Uso:
    python coletor/nuvem.py baixar                    # baixa e extrai o estado mais recente
    python coletor/nuvem.py subir --data 2026-10-25   # sobe o estado do dia (cria o release se faltar)
    python coletor/nuvem.py historico --data 2026-10-25  # sobe o que o dia produziu
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path

import portal

# Release com o estado que passa de um dia para o outro
RELEASE_ESTADO = "estado-atual"

# Quantos estados antigos ficam no release (os mais recentes)
ESTADOS_GUARDADOS = 3

# Nome de um arquivo de estado: estado-AAAA-MM-DD.tar.gz
PADRAO_ESTADO = re.compile(r"estado-\d{4}-\d{2}-\d{2}\.tar\.gz")


class FalhaGh(Exception):
    """O GitHub CLI devolveu erro."""


def localizar_gh():
    """Acha o executável do gh: no PATH ou, no Windows, na pasta padrão da instalação."""
    caminho = shutil.which("gh")
    if caminho:
        return caminho
    padrao = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "GitHubCLI" / "bin" / "gh.exe"
    if padrao.exists():
        return str(padrao)
    sys.exit("GitHub CLI (gh) não encontrado. Instale em https://cli.github.com e faça login com: gh auth login")


def gh(*argumentos):
    """Roda o gh e devolve a saída; lança FalhaGh se der erro."""
    resultado = subprocess.run([localizar_gh(), *argumentos], capture_output=True, text=True, encoding="utf-8")
    if resultado.returncode != 0:
        raise FalhaGh(resultado.stderr.strip())
    return resultado.stdout


def arquivos_do_release(tag):
    """Nomes dos arquivos de um release, ou None se o release não existe."""
    try:
        saida = gh("release", "view", tag, "--json", "assets", "--jq", ".assets[].name")
    except FalhaGh as erro:
        if "not found" in str(erro).lower():
            return None
        raise
    return [nome for nome in saida.split() if nome]


def garantir_release(tag, titulo, notas):
    """Cria o release se ele ainda não existir (sem marcá-lo como o "mais recente" do repositório)."""
    if arquivos_do_release(tag) is None:
        gh("release", "create", tag, "--title", titulo, "--notes", notas, "--latest=false")
        print(f"Release {tag} criado")


def empacotar(destino, arquivos):
    """Junta os arquivos num .tar.gz, guardando os caminhos relativos à raiz do projeto."""
    with tarfile.open(destino, "w:gz") as pacote:
        for arquivo in arquivos:
            pacote.add(arquivo, arcname=arquivo.relative_to(portal.RAIZ).as_posix())


def extrair(pacote_tar):
    """Extrai o pacote na raiz do projeto. O filtro "data" recusa caminhos absolutos e com '..'."""
    with tarfile.open(pacote_tar, "r:gz") as pacote:
        pacote.extractall(portal.RAIZ, filter="data")


def mais_recente(pasta, nome_arquivo, data):
    """Arquivo da partição mais recente com data até 'data' (ex.: a última listagem), ou None."""
    candidatos = []
    for particao in pasta.glob("data=*"):
        dia = particao.name.removeprefix("data=")
        if dia <= str(data) and (particao / nome_arquivo).exists():
            candidatos.append((dia, particao / nome_arquivo))
    return max(candidatos)[1] if candidatos else None


def arquivos_do_estado(data):
    """Arquivos que o motor precisa no dia seguinte."""
    dados = portal.RAIZ / "dados"
    arquivos = sorted((dados / "estado").glob("*.parquet"))

    # Última listagem (para a conferência de 95%) e último cronograma da CGU (para o publicador)
    listagem = mais_recente(dados / "bronze" / "catalogo_lista", "catalogo_lista.parquet", data)
    cronograma = mais_recente(dados / "bronze" / "painel_cgu_cronograma", "painel_cgu_cronograma.parquet", data)
    return arquivos + [arquivo for arquivo in (listagem, cronograma) if arquivo]


def baixar():
    """Baixa o estado mais recente do release e extrai em dados/."""
    nomes = arquivos_do_release(RELEASE_ESTADO)
    if nomes is None:
        sys.exit(f"Release {RELEASE_ESTADO} não existe. Suba o estado pela primeira vez: "
                 "python coletor/nuvem.py subir --data AAAA-MM-DD")
    estados = sorted(nome for nome in nomes if PADRAO_ESTADO.fullmatch(nome))
    if not estados:
        sys.exit(f"Nenhum estado no release {RELEASE_ESTADO}. Suba o estado: python coletor/nuvem.py subir --data AAAA-MM-DD")

    escolhido = estados[-1]
    with tempfile.TemporaryDirectory() as pasta:
        gh("release", "download", RELEASE_ESTADO, "--pattern", escolhido, "--dir", pasta)
        extrair(Path(pasta) / escolhido)
    print(f"Estado baixado: {escolhido}")


def subir(data):
    """Sobe o estado do dia e apaga os mais antigos, guardando só os ESTADOS_GUARDADOS mais recentes."""
    arquivos = arquivos_do_estado(data)
    # Nunca sobe um estado sem o detalhe: o dia seguinte trataria todas as bases como novas (9 horas)
    if portal.RAIZ / "dados" / "estado" / "detalhe_atual.parquet" not in arquivos:
        sys.exit("dados/estado/detalhe_atual.parquet não existe: nada foi enviado.")

    nome = f"estado-{data}.tar.gz"
    garantir_release(RELEASE_ESTADO, "Estado atual",
                     "Estado que o pipeline diário lê e atualiza a cada execução. Gerado por coletor/nuvem.py.")
    with tempfile.TemporaryDirectory() as pasta:
        pacote = Path(pasta) / nome
        empacotar(pacote, arquivos)
        gh("release", "upload", RELEASE_ESTADO, str(pacote), "--clobber")
    print(f"Estado enviado: {nome} ({len(arquivos)} arquivos)")

    # Só depois de enviar o novo é que os antigos saem
    estados = sorted(n for n in arquivos_do_release(RELEASE_ESTADO) if PADRAO_ESTADO.fullmatch(n))
    for antigo in estados[:-ESTADOS_GUARDADOS]:
        gh("release", "delete-asset", RELEASE_ESTADO, antigo, "--yes")
        print(f"Estado antigo removido: {antigo}")


def arquivos_do_dia(data):
    """Arquivos que o dia produziu: Silver, Gold, tentativas de links e de leitura de conteúdo, detalhes coletados."""
    dados = portal.RAIZ / "dados"
    padroes = [
        dados.glob(f"silver/*/data={data}/*.parquet"),
        dados.glob(f"gold/*/data={data}/*.parquet"),
        dados.glob(f"bronze/link_tentativa/data={data}/*.parquet"),
        dados.glob(f"bronze/conteudo_tentativa/data={data}/*.parquet"),
        dados.glob(f"bronze/catalogo_detalhe/data={data}/*.parquet"),
        dados.glob(f"bronze/catalogo_lista/data={data}/*.parquet"),
    ]
    return sorted(arquivo for padrao in padroes for arquivo in padrao)


def historico(data):
    """Sobe o que o dia produziu para o release do mês."""
    arquivos = arquivos_do_dia(data)
    if not arquivos:
        print(f"Nada produzido em {data}: nada foi enviado ao histórico.")
        return

    tag = f"historico-{data:%Y-%m}"
    garantir_release(tag, f"Histórico {data:%Y-%m}",
                     "Tabelas geradas pelo pipeline diário, um arquivo dia-AAAA-MM-DD.tar.gz por dia.")
    with tempfile.TemporaryDirectory() as pasta:
        pacote = Path(pasta) / f"dia-{data}.tar.gz"
        empacotar(pacote, arquivos)
        gh("release", "upload", tag, str(pacote), "--clobber")
    print(f"Histórico enviado: {pacote.name} ({len(arquivos)} arquivos) em {tag}")


def main():
    parser = argparse.ArgumentParser(description="Estado e histórico do motor nos releases do GitHub")
    parser.add_argument("comando", choices=["baixar", "subir", "historico"])
    parser.add_argument("--data", type=date.fromisoformat, help="data da execução (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    try:
        if args.comando == "baixar":
            baixar()
        elif args.comando == "subir":
            subir(data)
        else:
            historico(data)
    except FalhaGh as erro:
        sys.exit(f"Falha do GitHub CLI: {erro}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()