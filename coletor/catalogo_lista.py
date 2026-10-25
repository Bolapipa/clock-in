"""Coletor da listagem do catálogo do dados.gov.br (Fase 1, tarefa 2).

Percorre todas as páginas da listagem da API oficial e grava a
resposta crua de cada página na Bronze, em Parquet:
dados/bronze/catalogo_lista/data=AAAA-MM-DD/catalogo_lista.parquet

Uso:
    python coletor/catalogo_lista.py                  # catálogo inteiro (cerca de 40 min)
    python coletor/catalogo_lista.py --max-paginas 5  # teste rápido
"""

import argparse
import sys
import time
from datetime import date, datetime, timezone

import duckdb

import portal

# Trava de segurança contra loop infinito (o catálogo tem cerca de 1.307 páginas)
LIMITE_PAGINAS = 5000


def buscar_pagina(cliente, pagina):
    """Busca uma página da listagem; encerra o script se ela falhar de vez."""
    try:
        return portal.buscar(cliente, portal.URL_CONJUNTOS, {"pagina": pagina, "dadosAbertos": "true"})
    except portal.FalhaPortal as erro:
        sys.exit(f"Página {pagina} falhou {portal.TENTATIVAS} vezes ({erro}). Nada foi gravado.")


def gravar_bronze(linhas, data_coleta):
    """Grava as páginas coletadas em Parquet, na partição do dia."""
    # Partição estilo Hive: uma pasta por data de coleta
    pasta = portal.RAIZ / "dados" / "bronze" / "catalogo_lista" / f"data={data_coleta}"
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "catalogo_lista.parquet"

    con = duckdb.connect()

    # Tabela temporária em memória com as colunas da Bronze
    con.execute("""
        CREATE TABLE catalogo_lista (
            data_coleta   DATE,
            pagina        INTEGER,
            qtd_registros INTEGER,
            payload       VARCHAR,
            coletado_em   TIMESTAMP
        )
    """)
    con.executemany("INSERT INTO catalogo_lista VALUES (?, ?, ?, ?, ?)", linhas)

    # Grava o arquivo; se já existir (segunda execução no dia), é substituído
    con.execute(f"COPY catalogo_lista TO '{arquivo.as_posix()}' (FORMAT parquet)")
    con.close()
    return arquivo


def main():
    # Lê o parâmetro opcional --max-paginas
    parser = argparse.ArgumentParser(description="Coleta a listagem do catálogo do dados.gov.br")
    parser.add_argument("--max-paginas", type=int, help="para depois de N páginas (teste)")
    args = parser.parse_args()
    limite = args.max_paginas or LIMITE_PAGINAS

    # Data da coleta: define a partição do dia
    data_coleta = date.today()
    linhas = []
    inicio = time.perf_counter()
    chegou_ao_fim = False

    with portal.criar_cliente() as cliente:
        for pagina in range(1, limite + 1):
            resposta = buscar_pagina(cliente, pagina)

            # Erro 4xx: problema na chamada (por exemplo, chave inválida)
            if resposta.status_code != 200:
                sys.exit(f"Página {pagina}: HTTP {resposta.status_code}\n{resposta.text[:300]}")

            # Lista vazia: passou da última página
            registros = resposta.json()
            if not registros:
                chegou_ao_fim = True
                break

            # Guarda a resposta crua (texto JSON), sem transformar
            coletado_em = datetime.now(timezone.utc).replace(tzinfo=None)
            linhas.append((data_coleta, pagina, len(registros), resposta.text, coletado_em))

            # Mostra o andamento a cada 50 páginas
            if pagina % 50 == 0:
                minutos = (time.perf_counter() - inicio) / 60
                print(f"  {pagina} páginas coletadas em {minutos:.1f} min")

            # Pausa entre páginas para não sobrecarregar o portal
            time.sleep(portal.PAUSA)

    # Avisa se parou pela trava, e não pelo fim do catálogo
    if not chegou_ao_fim and not args.max_paginas:
        print(f"Aviso: parou no limite de {LIMITE_PAGINAS} páginas sem chegar ao fim do catálogo")

    if not linhas:
        sys.exit("Nenhuma página coletada. Nada foi gravado.")

    arquivo = gravar_bronze(linhas, data_coleta)

    # Resumo lido do próprio Parquet gravado
    paginas, bases = duckdb.sql(
        f"SELECT COUNT(*), SUM(qtd_registros) FROM '{arquivo.as_posix()}'"
    ).fetchall()[0]
    minutos = (time.perf_counter() - inicio) / 60
    print(f"\nGravado: {arquivo}")
    print(f"{paginas} páginas, {bases} bases, {minutos:.1f} min")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()