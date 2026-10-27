"""Motor da coleta diária: roda a coleta e a Silver em ordem, todos com a mesma data (Fase 2).

Passos, nesta ordem:
    lista    -> catalogo_lista.py    listagem do catálogo (cerca de 40 min)
    painel   -> painel_cgu.py        arquivos do painel da CGU (opcional)
    detalhe  -> catalogo_detalhe.py  detalhe das bases novas, alteradas e do rodízio
    silver   -> silver.py            tabelas base, recurso e publicador
    links    -> links.py             teste de saúde dos links dos recursos
    silver_links -> silver_links.py  tabelas link_status e base_saude


A data é calculada uma vez, no fuso de Brasília, e passada a todos os passos
com --data. Se um passo obrigatório falhar, o motor para e os seguintes não rodam.
O painel é opcional: se falhar, a Silver usa o último cronograma coletado.

No workflow do GitHub Actions cada passo é uma etapa própria (--apenas), para aparecer com
log e tempo separados. Como cada etapa é um processo novo, o workflow passa o início da
execução (--inicio) e o orçamento de tempo continua contando do começo.

Uso:
    python coletor/motor.py                                   # execução do dia
    python coletor/motor.py --tempo-maximo 330                # o teste de links para a tempo de caber em 330 min
    python coletor/motor.py --desde detalhe                   # retoma a partir de um passo
    python coletor/motor.py --data 2026-10-26 --desde silver  # retoma um dia anterior
    python coletor/motor.py --apenas detalhe                  # roda só um passo
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
    ("links", "links.py", True),
    ("silver_links", "silver_links.py", True),
]

# Passos que sabem parar sozinhos quando o tempo acaba: recebem --tempo-maximo
PASSOS_COM_TEMPO = ("links.py",)

# Minutos do orçamento reservados para o que vem depois do teste de links (Silver dos links)
RESERVA_FINAL_MINUTOS = 15

# Menos que isto de tempo sobrando e o passo nem começa
TEMPO_MINIMO_DO_PASSO = 1


def rodar_passo(script, data, extras=()):
    """Roda um script do coletor com a data do dia e devolve o código de saída (0 = sucesso)."""
    # sys.executable é o Python que está rodando o motor (o do .venv)
    comando = [sys.executable, str(PASTA_COLETOR / script), "--data", str(data), *extras]
    return subprocess.run(comando).returncode


def main():
    nomes = [nome for nome, _, _ in PASSOS]
    parser = argparse.ArgumentParser(description="Motor da coleta diária do Clock-in")
    parser.add_argument("--data", type=date.fromisoformat, help="data da execução (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--desde", choices=nomes, default=nomes[0], help="começa a partir deste passo (para retomar)")
    parser.add_argument("--tempo-maximo", type=float, help="orçamento total do motor, em minutos: o teste de links para a tempo de caber")
    parser.add_argument("--apenas", choices=nomes, help="roda só este passo (o workflow roda um por etapa); respeita --desde")
    parser.add_argument("--inicio", type=float, help="início da execução, em segundos desde 1970 (date +%%s); o orçamento conta daí; padrão: agora")
    args = parser.parse_args()

    # A data é decidida uma vez só e vale para todos os passos
    data = args.data or portal.data_de_hoje()
    primeiro = nomes.index(args.desde)
    # --apenas escolhe um passo; se ele vem antes de --desde, não sobra nada para rodar
    passos = [passo for passo in PASSOS[primeiro:] if args.apenas in (None, passo[0])]
    print(f"Motor do dia {data}: passos {', '.join(passo[0] for passo in passos) or 'nenhum'}", flush=True)

    avisos = []
    pulados = []
    inicio_motor = time.perf_counter()
    # O orçamento de tempo conta do início da execução inteira, não só deste processo
    inicio_orcamento = args.inicio if args.inicio is not None else time.time()

    for nome, script, obrigatorio in passos:
        # flush: mostra a linha antes da saída do script, que vem de outro processo
        print(f"\n=== {nome} ({script}) ===", flush=True)

        # Com orçamento de tempo, o passo recebe o que sobrou, menos a reserva para o que vem depois
        extras = []
        if args.tempo_maximo is not None and script in PASSOS_COM_TEMPO:
            restante = args.tempo_maximo - (time.time() - inicio_orcamento) / 60 - RESERVA_FINAL_MINUTOS
            if restante < TEMPO_MINIMO_DO_PASSO:
                print(f"=== {nome}: sem tempo no orçamento de {args.tempo_maximo:.0f} min; pulado ===", flush=True)
                pulados.append(nome)
                continue
            extras = ["--tempo-maximo", f"{restante:.1f}"]

        inicio = time.perf_counter()
        # Sem extras, a chamada é a mesma de sempre
        codigo = rodar_passo(script, data, extras) if extras else rodar_passo(script, data)
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
    if pulados:
        print(f"Passos pulados por falta de tempo: {', '.join(pulados)}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()