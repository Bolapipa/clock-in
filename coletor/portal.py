"""Acesso à API oficial do dados.gov.br, usado por todos os coletores.

Reúne o que é comum: endereço, chave, identificação e
as novas tentativas em caso de falha.
"""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

# Pasta raiz do projeto (a pasta acima de coletor/)
RAIZ = Path(__file__).resolve().parent.parent

# Endereço dos conjuntos de dados na API oficial
URL_CONJUNTOS = "https://dados.gov.br/dados/api/publico/conjuntos-dados"

# Identificação do Clock-in para os servidores (coleta educada)
USER_AGENT = "clock-in/0.1 (+https://github.com/Bolapipa/clock-in)"

# Pausa entre chamadas, em segundos
PAUSA = 1.5

# Quantas vezes tentar uma chamada antes de desistir
TENTATIVAS = 3

# Espera após a primeira falha, em segundos (dobra a cada nova falha)
ESPERA_FALHA = 10


# Fuso de referência do projeto: o "dia" de uma coleta é o dia em Brasília
FUSO = ZoneInfo("America/Sao_Paulo")


class FalhaPortal(Exception):
    """A chamada falhou em todas as tentativas."""


def data_de_hoje(agora=None):
    """Data de hoje em Brasília, mesmo num computador em outro fuso (o GitHub Actions usa UTC)."""
    agora = agora or datetime.now(timezone.utc)
    return agora.astimezone(FUSO).date()


def criar_cliente():
    """Cria o cliente HTTP com a chave do .env e a identificação do projeto."""
    load_dotenv(RAIZ / ".env")
    chave = os.getenv("CHAVE_API_DADOS_GOV")
    if not chave:
        sys.exit("Chave não encontrada: crie CHAVE_API_DADOS_GOV no arquivo .env")

    cabecalhos = {
        "chave-api-dados-abertos": chave,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    return httpx.Client(headers=cabecalhos, timeout=30)


def buscar(cliente, url, params=None):
    """Faz um GET, tentando de novo em erros temporários.

    Devolve a resposta quando é 200 ou um erro 4xx (exceto 429),
    que não melhora repetindo. Lança FalhaPortal se todas as
    tentativas falharem.
    """
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = cliente.get(url, params=params)

            # 200 é sucesso; erro 4xx (exceto 429) não melhora repetindo
            if resposta.status_code == 200 or (400 <= resposta.status_code < 500 and resposta.status_code != 429):
                return resposta
            motivo = f"HTTP {resposta.status_code}"

        # Falhas de rede: timeout, DNS, conexão recusada
        except httpx.HTTPError as erro:
            motivo = type(erro).__name__

        # Espera cada vez maior antes da próxima tentativa: 10 s, 20 s
        if tentativa < TENTATIVAS:
            espera = ESPERA_FALHA * 2 ** (tentativa - 1)
            print(f"  {motivo}; tentativa {tentativa}/{TENTATIVAS}, nova tentativa em {espera} s")
            time.sleep(espera)

    raise FalhaPortal(motivo)
