"""Motor diário: roda a coleta e a Silver em ordem, todos com a mesma data (Fase 2).

Passos, nesta ordem:
    lista    -> catalogo_lista.py    listagem do catálogo (cerca de 40 min)
    painel   -> painel_cgu.py        arquivos do painel da CGU (opcional)
    detalhe  -> catalogo_detalhe.py  detalhe das bases novas, alteradas e do rodízio
    silver   -> silver.py            tabelas base, recurso e publicador

A data é calculada uma vez, no fuso de Brasília, e passada a todos os passos
com --data. Se um passo obrigatório falhar, o motor para e os seguintes não rodam.
O painel é opcional: se falhar, a Silver usa o último cronograma coletado.

Uso:
    python coletor/motor.py                                   # execução do dia
    python coletor/motor.py --desde detalhe                   # retoma a partir de um passo
    python coletor/motor.py --data 2026-10-26 --desde silver  # retoma um dia anterior
"""

import argparse
import subprocess
import sys
import time
from datetime import date

import portal

# Pasta dos scripts do coletor
PASTA_COLETOR = portal.RAIZ / "coletor"

# Passos do motor, na ordem em que rodam: (nome, script, obrigatório)
PASSOS = [
    ("lista", "catalogo_lista.py", True),
    ("painel", "painel_cgu.py", False),
    ("detalhe", "catalogo_detalhe.py", True),
    ("silver", "silver.py", True),
]


def rodar_passo(script, data):
    """Roda um script do coletor com a data do dia e devolve o código de saída (0 = sucesso)."""
    # sys.executable é o Python que está rodando o motor (o do .venv)
    comando = [sys.executable, str(PASTA_COLETOR / script), "--data", str(data)]
    return subprocess.run(comando).returncode


def main():
    nomes = [nome for nome, _, _ in PASSOS]
    parser = argparse.ArgumentParser(description="Motor diário do Clock-in")
    parser.add_argument("--data", type=date.fromisoformat, help="data da execução (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--desde", choices=nomes, default=nomes[0], help="começa a partir deste passo (para retomar)")
    args = parser.parse_args()

    # A data é decidida uma vez só e vale para todos os passos
    data = args.data or portal.data_de_hoje()
    primeiro = nomes.index(args.desde)
    print(f"Motor do dia {data}: passos {', '.join(nomes[primeiro:])}", flush=True)

    avisos = []
    inicio_motor = time.perf_counter()

    for nome, script, obrigatorio in PASSOS[primeiro:]:
        # flush: mostra a linha antes da saída do script, que vem de outro processo
        print(f"\n=== {nome} ({script}) ===", flush=True)
        inicio = time.perf_counter()
        codigo = rodar_passo(script, data)
        minutos = (time.perf_counter() - inicio) / 60

        if codigo == 0:
            print(f"=== {nome}: ok em {minutos:.1f} min ===", flush=True)
        elif obrigatorio:
            sys.exit(f"=== {nome}: falhou (código {codigo}) em {minutos:.1f} min. O motor parou. "
                     f"Para retomar: python coletor/motor.py --data {data} --desde {nome} ===")
        else:
            print(f"=== {nome}: falhou (código {codigo}), mas é opcional; o motor continua ===", flush=True)
            avisos.append(nome)

    minutos = (time.perf_counter() - inicio_motor) / 60
    print(f"\nMotor concluído em {minutos:.1f} min")
    if avisos:
        print(f"Passos opcionais que falharam: {', '.join(avisos)}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()