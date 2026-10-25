"""Teste da API oficial do dados.gov.br (Fase 1, tarefa 1).

Confirma a decisão 12: com a chave, a API oficial traz
recursos, periodicidade e responsável de cada base?
Mede as 15 bases da página 1 e estima o tempo do catálogo inteiro.
"""

import os
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Pasta raiz do projeto (a pasta acima de coletor/)
RAIZ = Path(__file__).resolve().parent.parent

# Endereço da API oficial de conjuntos de dados
URL_BASE = "https://dados.gov.br/dados/api/publico/conjuntos-dados"

# Identificação do Clock-in para os servidores (coleta educada)
USER_AGENT = "clock-in/0.1 (+https://github.com/Bolapipa/clock-in)"

# Pausa entre chamadas, em segundos
PAUSA = 1.5

# Total de bases abertas no censo de 24/10/2026 (para a estimativa de tempo)
TOTAL_BASES = 19602


def main():
    # Carrega as variáveis do arquivo .env (a chave fica só lá)
    load_dotenv(RAIZ / ".env")
    chave = os.getenv("CHAVE_API_DADOS_GOV")

    # Para o script se a chave não estiver configurada
    if not chave:
        sys.exit("Chave não encontrada: crie CHAVE_API_DADOS_GOV no arquivo .env")

    # Cabeçalhos enviados em todas as chamadas
    cabecalhos = {
        "chave-api-dados-abertos": chave,
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    # Contadores do resultado
    com_recursos = 0
    com_periodicidade = 0
    com_responsavel = 0
    periodicidades = Counter()
    tempos = []

    # Cliente HTTP reaproveitado em todas as chamadas (timeout de 30 s)
    with httpx.Client(headers=cabecalhos, timeout=30) as cliente:

        # 1) Listagem: primeira página das bases abertas
        resposta = cliente.get(URL_BASE, params={"pagina": 1, "dadosAbertos": "true"})
        if resposta.status_code != 200:
            sys.exit(f"Listagem falhou: HTTP {resposta.status_code}\n{resposta.text[:300]}")

        lista = resposta.json()
        if not isinstance(lista, list) or not lista:
            sys.exit(f"Listagem veio em formato inesperado: {str(lista)[:300]}")

        print(f"Listagem OK: {len(lista)} bases na página 1\n")

        # 2) Detalhe de cada base da página
        for numero, item in enumerate(lista, start=1):
            # Pausa entre chamadas para não sobrecarregar o portal
            time.sleep(PAUSA)

            # Mede quanto tempo a chamada leva
            inicio = time.perf_counter()
            resposta = cliente.get(f"{URL_BASE}/{item['id']}")
            tempos.append(time.perf_counter() - inicio)

            if resposta.status_code != 200:
                print(f"{numero:2}. HTTP {resposta.status_code} em {item.get('nome')}")
                continue

            base = resposta.json()
            recursos = base.get("recursos") or []
            periodicidade = base.get("periodicidade")

            # Soma os critérios preenchidos
            com_recursos += bool(recursos)
            com_periodicidade += bool(periodicidade)
            com_responsavel += bool(base.get("responsavel") or base.get("emailResponsavel"))
            periodicidades[periodicidade or "(vazia)"] += 1

            print(f"{numero:2}. {periodicidade or '(vazia)':12} | {len(recursos)} recursos | {base.get('titulo', '')[:60]}")

    # Resumo da decisão 12
    total = len(lista)
    print(f"\nDecisão 12 ({total} bases):")
    print(f"  recursos:      {com_recursos}/{total}")
    print(f"  periodicidade: {com_periodicidade}/{total}")
    print(f"  responsavel:   {com_responsavel}/{total}")
    print(f"  valores de periodicidade: {dict(periodicidades)}")

    # Estimativa de tempo para o catálogo inteiro (1 detalhe por base)
    media = sum(tempos) / len(tempos)
    horas = TOTAL_BASES * (media + PAUSA) / 3600
    print(f"\nTempo médio por detalhe: {media:.2f} s")
    print(f"Estimativa para {TOTAL_BASES} bases: {horas:.1f} horas")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()