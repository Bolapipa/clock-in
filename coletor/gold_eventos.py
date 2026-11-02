"""Gera os eventos do dia de cada base (Fase 8): é o que alimenta os feeds RSS.

Roda depois de gold_status.py. Grava, uma partição por data:
dados/gold/fato_evento_base/data=AAAA-MM-DD/fato_evento_base.parquet
    data, id_base, slug, tipo_evento, detalhe

Tipos de evento: STATUS_MUDOU, CONTEUDO_MUDOU, SCHEMA_MUDOU e LINK_QUEBROU (decisão 43).
O pipeline só enxerga o dia de hoje e o estado, então dois arquivos de estado fazem a ponte entre os dias:
    dados/estado/status_base.parquet     o status de cada base no dia anterior (data, id, status)
    dados/estado/evento_recente.parquet  os eventos dos últimos 30 dias (os feeds RSS leem daqui)

Rodar o mesmo dia duas vezes dá o mesmo resultado. Sem status anterior (primeiro dia), não há evento de status.

Uso:
    python coletor/gold_eventos.py                    # usa a Silver e o status de hoje
    python coletor/gold_eventos.py --data 2026-10-25  # usa os de outro dia
"""

import argparse
import os
import sys
from datetime import date, timedelta

import duckdb

import gold_status
import portal
import silver

# Nome da tabela e do arquivo SQL que a gera
TABELA = "fato_evento_base"
ARQUIVO_SQL = "gold_evento_base.sql"

# Quantos dias de eventos o estado guarda (os feeds mostram esta janela)
DIAS_RECENTES = 30


def arquivo_eventos_recentes():
    """Arquivo do estado com os eventos dos últimos dias (calculado na hora, para os testes trocarem a raiz)."""
    return portal.RAIZ / "dados" / "estado" / "evento_recente.parquet"


def arquivo_status_anterior():
    """Arquivo do estado com o status das bases em dias anteriores."""
    return portal.RAIZ / "dados" / "estado" / "status_base.parquet"


def gravar_atomico(con, consulta, destino):
    """Grava o resultado de uma consulta em Parquet sem deixar um arquivo pela metade."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(".tmp")
    con.execute(f"COPY ({consulta}) TO '{temporario.as_posix()}' (FORMAT parquet)")
    os.replace(temporario, destino)


def criar_views_entrada(con, data):
    """Cria as views e a variável usadas por sql/gold_evento_base.sql."""
    # Silver do dia: obrigatórias (bases, recursos e links testados)
    for nome in ("base", "recurso", "link_status"):
        arquivo = silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"
        if not arquivo.exists():
            sys.exit(f"Silver {nome} de {data} não encontrada. Rode antes silver.py e silver_links.py com --data {data}")
        con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Conteúdo lido no dia: sem ele não há evento de conteúdo nem de estrutura
    versao = silver.PASTA_SILVER / "versao_conteudo" / f"data={data}" / "versao_conteudo.parquet"
    if versao.exists():
        con.execute(f"CREATE OR REPLACE VIEW versao_conteudo AS SELECT * FROM read_parquet('{versao.as_posix()}')")
    else:
        con.execute("CREATE OR REPLACE TABLE versao_conteudo (link VARCHAR, mudou_conteudo BOOLEAN, mudou_schema BOOLEAN)")

    # Status do dia (Gold): sem ele não há evento de status
    status = gold_status.PASTA_GOLD / gold_status.TABELA / f"data={data}" / f"{gold_status.TABELA}.parquet"
    if status.exists():
        con.execute(f"CREATE OR REPLACE VIEW status_hoje AS SELECT * FROM read_parquet('{status.as_posix()}')")
    else:
        con.execute("CREATE OR REPLACE TABLE status_hoje (id VARCHAR, status VARCHAR, motivo VARCHAR)")

    # Último status guardado de cada base em um dia anterior ao de hoje
    anterior = arquivo_status_anterior()
    if anterior.exists():
        con.execute(f"""
            CREATE OR REPLACE VIEW status_anterior AS
            SELECT id, arg_max(status, data) AS status
            FROM read_parquet('{anterior.as_posix()}')
            WHERE data < DATE '{data}'
            GROUP BY id
        """)
    else:
        con.execute("CREATE OR REPLACE TABLE status_anterior (id VARCHAR, status VARCHAR)")

    con.execute(f"SET VARIABLE data_coleta = DATE '{data}'")


def gerar_tabela(con, data):
    """Roda o SQL dos eventos e grava o resultado na partição do dia."""
    consulta = (silver.PASTA_SQL / ARQUIVO_SQL).read_text(encoding="utf-8")
    arquivo = gold_status.PASTA_GOLD / TABELA / f"data={data}" / f"{TABELA}.parquet"
    # O SQL fica entre quebras de linha para um comentário "--" no fim não engolir o ")"
    gravar_atomico(con, f"\n{consulta}\n", arquivo)
    linhas = con.execute(f"SELECT COUNT(*) FROM read_parquet('{arquivo.as_posix()}')").fetchall()[0][0]
    return arquivo, linhas


def atualizar_estados(con, data, arquivo_do_dia):
    """Atualiza o estado dos eventos recentes e o do status, já com o dia de hoje."""
    # Eventos: os dos últimos dias que já estavam no estado, sem o dia de hoje, mais os de hoje
    recentes = arquivo_eventos_recentes()
    desde = data - timedelta(days=DIAS_RECENTES - 1)
    partes = [f"SELECT * FROM read_parquet('{arquivo_do_dia.as_posix()}')"]
    if recentes.exists():
        partes.append(f"SELECT * FROM read_parquet('{recentes.as_posix()}') WHERE data >= DATE '{desde}' AND data < DATE '{data}'")
    gravar_atomico(con, " UNION ALL ".join(partes) + " ORDER BY data, id_base, tipo_evento", recentes)

    # Status: guarda o último dia anterior de cada base (para comparar amanhã) e o de hoje.
    # Sem o status de hoje (a Gold não foi gerada), o estado fica como estava
    if con.execute("SELECT COUNT(*) FROM status_hoje").fetchall()[0][0] == 0:
        return
    anterior = arquivo_status_anterior()
    partes = [f"SELECT DATE '{data}' AS data, id, status FROM status_hoje"]
    if anterior.exists():
        partes.append(f"""
            SELECT max(data) AS data, id, arg_max(status, data) AS status
            FROM read_parquet('{anterior.as_posix()}')
            WHERE data < DATE '{data}'
            GROUP BY id
        """)
    gravar_atomico(con, " UNION ALL ".join(partes) + " ORDER BY id, data", anterior)


def main():
    parser = argparse.ArgumentParser(description="Gera os eventos do dia de cada base")
    parser.add_argument("--data", type=date.fromisoformat, help="data a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)
    arquivo, linhas = gerar_tabela(con, data)
    atualizar_estados(con, data, arquivo)
    print(f"gold/{TABELA}: {linhas} eventos -> {arquivo}")

    print("\nEventos por tipo:")
    for tipo, quantos in con.execute(f"""
        SELECT tipo_evento, COUNT(*) FROM read_parquet('{arquivo.as_posix()}') GROUP BY 1 ORDER BY 2 DESC, 1
    """).fetchall():
        print(f"  {tipo}: {quantos}")
    con.close()


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
