"""Coletor da listagem do catálogo do dados.gov.br (Fase 1, tarefa 2).

Percorre todas as páginas da listagem da API oficial e grava a
resposta crua de cada página na Bronze, em Parquet:
dados/bronze/catalogo_lista/data=AAAA-MM-DD/catalogo_lista.parquet

Proteções: recusa uma listagem com menos de 95% das bases da listagem anterior
(portal incompleto), recusa resposta que não é JSON e não deixa um teste com
--max-paginas sobrescrever a listagem que já existe no dia.

Uso:
    python coletor/catalogo_lista.py                  # catálogo inteiro (cerca de 40 min)
    python coletor/catalogo_lista.py --max-paginas 5  # teste rápido (não sobrescreve a listagem do dia)
    python coletor/catalogo_lista.py --data 2026-10-26  # grava na partição de outro dia
    python coletor/catalogo_lista.py --aceitar-queda  # aceita uma listagem bem menor que a anterior

"""

import argparse
import sys
import time
from datetime import date, datetime, timezone

import duckdb

import portal

# Trava de segurança contra loop infinito (o catálogo tem cerca de 1.307 páginas)
LIMITE_PAGINAS = 5000


# Uma listagem com menos que esta fração das bases da anterior é recusada
MINIMO_VS_ANTERIOR = 0.95


def arquivo_da_listagem(data):
    """Caminho do arquivo da listagem de um dia na Bronze."""
    return portal.RAIZ / "dados" / "bronze" / "catalogo_lista" / f"data={data}" / "catalogo_lista.parquet"


def listagem_anterior(data_coleta):
    """Devolve (data, total de bases) da listagem mais recente anterior a data_coleta, ou None."""
    pasta = portal.RAIZ / "dados" / "bronze" / "catalogo_lista"
    datas = sorted(
        date.fromisoformat(pasta_dia.name.removeprefix("data="))
        for pasta_dia in pasta.glob("data=*")
        if (pasta_dia / "catalogo_lista.parquet").exists()
    )
    anteriores = [data for data in datas if data < data_coleta]
    if not anteriores:
        return None

    ultima = anteriores[-1]
    total = duckdb.sql(f"SELECT SUM(qtd_registros) FROM '{arquivo_da_listagem(ultima).as_posix()}'").fetchall()[0][0]
    return ultima, total


def conferir_tamanho(total, data_coleta):
    """Encerra o script se a listagem tem bem menos bases que a anterior."""
    anterior = listagem_anterior(data_coleta)
    if anterior is None:
        return

    data_anterior, total_anterior = anterior
    if total < MINIMO_VS_ANTERIOR * total_anterior:
        sys.exit(f"Listagem com {total} bases, menos de {MINIMO_VS_ANTERIOR:.0%} das {total_anterior} de {data_anterior}. "
                 "O portal pode estar incompleto. Nada foi gravado. "
                 "Se a queda for real, rode de novo com --aceitar-queda.")


def ler_registros(resposta, pagina):
    """Lê o JSON de uma página e confere que é uma lista de bases."""
    try:
        registros = resposta.json()
    except ValueError:
        sys.exit(f"Página {pagina}: a resposta não é JSON ({resposta.text[:100]!r}). Nada foi gravado.")
    if not isinstance(registros, list):
        sys.exit(f"Página {pagina}: esperava uma lista de bases, veio {type(registros).__name__}. Nada foi gravado.")
    return registros


def buscar_pagina(cliente, pagina):
    """Busca uma página da listagem; encerra o script se ela falhar de vez."""
    try:
        return portal.buscar(cliente, portal.URL_CONJUNTOS, {"pagina": pagina, "dadosAbertos": "true"})
    except portal.FalhaPortal as erro:
        sys.exit(f"Página {pagina} falhou {portal.TENTATIVAS} vezes ({erro}). Nada foi gravado.")


def gravar_bronze(linhas, data_coleta):
    """Grava as páginas coletadas em Parquet, na partição do dia."""
    # Partição estilo Hive: uma pasta por data de coleta
    arquivo = arquivo_da_listagem(data_coleta)
    arquivo.parent.mkdir(parents=True, exist_ok=True)

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
    # Lê os parâmetros opcionais
    parser = argparse.ArgumentParser(description="Coleta a listagem do catálogo do dados.gov.br")
    parser.add_argument("--max-paginas", type=int, help="para depois de N páginas (teste)")
    parser.add_argument("--data", type=date.fromisoformat, help="data da coleta (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--aceitar-queda", action="store_true", help="aceita uma listagem bem menor que a anterior")
    args = parser.parse_args()
    limite = args.max_paginas or LIMITE_PAGINAS

    # Data da coleta: define a partição do dia
    data_coleta = args.data or portal.data_de_hoje()

    # Um teste parcial nunca sobrescreve a listagem que já existe no dia
    if args.max_paginas and arquivo_da_listagem(data_coleta).exists():
        sys.exit(f"Já existe uma listagem de {data_coleta}. Um teste com --max-paginas não a sobrescreve; "
                 "use outra --data.")

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
            registros = ler_registros(resposta, pagina)
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

    # Listagem completa: confere o tamanho contra a anterior antes de gravar
    if not args.max_paginas and not args.aceitar_queda:
        conferir_tamanho(sum(linha[2] for linha in linhas), data_coleta)

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