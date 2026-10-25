"""Coletor do detalhe de cada base do dados.gov.br (Fase 1, tarefa 2).

Segue a decisão 21 (incremental + rodízio). Busca o detalhe de:
- bases novas (nunca coletadas);
- bases cujo ultimaAlteracaoMetadados mudou desde a última coleta;
- 1/30 do catálogo em rodízio (cada base é revista ao menos 1 vez por mês).
Com --completo, busca todas (carga inicial, cerca de 9 horas).

Lê a listagem do dia (rode catalogo_lista.py antes) e grava a resposta
crua na Bronze, em lotes, para não perder trabalho se for interrompido:
dados/bronze/catalogo_detalhe/data=AAAA-MM-DD/parte-0001.parquet

Uso:
    python coletor/catalogo_detalhe.py                  # coleta diária
    python coletor/catalogo_detalhe.py --completo       # carga inicial
    python coletor/catalogo_detalhe.py --max-bases 20   # teste rápido
    python coletor/catalogo_detalhe.py --completo --data 2026-10-25  # retoma uma carga interrompida
"""

import argparse
import sys
import time
from datetime import date, datetime, timezone

import duckdb

import portal

# Pastas da Bronze
PASTA_LISTA = portal.RAIZ / "dados" / "bronze" / "catalogo_lista"
PASTA_DETALHE = portal.RAIZ / "dados" / "bronze" / "catalogo_detalhe"

# Em quantos dias o rodízio percorre o catálogo inteiro
DIAS_RODIZIO = 30

# Data de referência para contar os dias do rodízio
INICIO_RODIZIO = date(2026, 1, 1)

# Quantas bases juntar antes de gravar um arquivo (parte)
TAMANHO_LOTE = 500


def carregar_detalhes_anteriores(con):
    """Cria a tabela 'detalhe' com tudo o que já foi coletado (vazia na primeira vez)."""
    arquivos = sorted(PASTA_DETALHE.glob("data=*/*.parquet"))
    if arquivos:
        lista = [arquivo.as_posix() for arquivo in arquivos]
        con.execute(f"""
            CREATE TABLE detalhe AS
            SELECT id, ultima_alteracao, status_http, data_coleta
            FROM read_parquet({lista})
        """)
    else:
        con.execute("""
            CREATE TABLE detalhe (
                id VARCHAR, ultima_alteracao VARCHAR, status_http INTEGER, data_coleta DATE
            )
        """)


def bases_a_coletar(data_coleta, completo):
    """Decide quais bases buscar hoje e por quê (NOVA, ALTERADA, RODIZIO ou COMPLETA)."""
    arquivo_lista = PASTA_LISTA / f"data={data_coleta}" / "catalogo_lista.parquet"
    if not arquivo_lista.exists():
        sys.exit(f"Listagem de {data_coleta} não encontrada. Rode antes: python coletor/catalogo_lista.py")

    con = duckdb.connect()
    carregar_detalhes_anteriores(con)

    # Número do grupo do rodízio que toca hoje (0 a 29)
    grupo_hoje = (data_coleta - INICIO_RODIZIO).days % DIAS_RODIZIO

    bases = con.execute(f"""
        -- Bases da listagem de hoje, abrindo o JSON cru de cada página
        WITH hoje AS (
            SELECT DISTINCT
                r ->> 'id' AS id,
                r ->> 'ultimaAlteracaoMetadados' AS ultima_alteracao
            FROM (
                SELECT unnest(from_json(payload, '["json"]')) AS r
                FROM read_parquet('{arquivo_lista.as_posix()}')
            )
        ),
        -- Última versão coletada com sucesso de cada base, antes de hoje
        anterior AS (
            SELECT id, arg_max(ultima_alteracao, data_coleta) AS ultima_alteracao
            FROM detalhe
            WHERE status_http = 200 AND data_coleta < $data
            GROUP BY id
        ),
        -- Bases já coletadas hoje (para retomar sem repetir)
        feitas_hoje AS (
            SELECT DISTINCT id FROM detalhe
            WHERE status_http = 200 AND data_coleta = $data
        ),
        -- Motivo de cada base ser coletada (ou não)
        classificadas AS (
            SELECT
                h.id,
                h.ultima_alteracao,
                CASE
                    WHEN $completo THEN 'COMPLETA'
                    WHEN a.id IS NULL THEN 'NOVA'
                    WHEN a.ultima_alteracao IS DISTINCT FROM h.ultima_alteracao THEN 'ALTERADA'
                    WHEN hash(h.id) % $dias = $grupo THEN 'RODIZIO'
                END AS motivo
            FROM hoje h
            LEFT JOIN anterior a USING (id)
            WHERE h.id NOT IN (SELECT id FROM feitas_hoje)
        )
        SELECT id, ultima_alteracao, motivo
        FROM classificadas
        WHERE motivo IS NOT NULL
        ORDER BY id
    """, {"data": data_coleta, "completo": completo, "dias": DIAS_RODIZIO, "grupo": grupo_hoje}).fetchall()

    con.close()
    return bases


def gravar_lote(linhas, data_coleta):
    """Grava um lote de detalhes como uma nova parte na partição do dia."""
    pasta = PASTA_DETALHE / f"data={data_coleta}"
    pasta.mkdir(parents=True, exist_ok=True)

    # Próximo número de parte livre: parte-0001, parte-0002...
    numero = len(list(pasta.glob("parte-*.parquet"))) + 1
    arquivo = pasta / f"parte-{numero:04d}.parquet"

    con = duckdb.connect()
    con.execute("""
        CREATE TABLE catalogo_detalhe (
            data_coleta      DATE,
            id               VARCHAR,
            motivo           VARCHAR,
            ultima_alteracao VARCHAR,
            status_http      INTEGER,
            payload          VARCHAR,
            erro             VARCHAR,
            coletado_em      TIMESTAMP
        )
    """)
    con.executemany("INSERT INTO catalogo_detalhe VALUES (?, ?, ?, ?, ?, ?, ?, ?)", linhas)
    con.execute(f"COPY catalogo_detalhe TO '{arquivo.as_posix()}' (FORMAT parquet)")
    con.close()
    return arquivo


def main():
    parser = argparse.ArgumentParser(description="Coleta o detalhe das bases do dados.gov.br")
    parser.add_argument("--completo", action="store_true", help="busca todas as bases (carga inicial)")
    parser.add_argument("--max-bases", type=int, help="para depois de N bases (teste)")
    parser.add_argument("--data", type=date.fromisoformat, help="data da listagem a usar (AAAA-MM-DD); padrão: hoje")
    args = parser.parse_args()

    data_coleta = args.data or date.today()
    bases = bases_a_coletar(data_coleta, args.completo)
    if args.max_bases:
        bases = bases[: args.max_bases]

    # Resumo do que será coletado, por motivo
    motivos = {}
    for _, _, motivo in bases:
        motivos[motivo] = motivos.get(motivo, 0) + 1
    horas = len(bases) * (portal.PAUSA + 0.21) / 3600
    print(f"{len(bases)} bases a coletar {motivos}; estimativa {horas:.1f} h")
    if not bases:
        return

    lote = []
    sucessos = 0
    falhas = 0
    inicio = time.perf_counter()

    with portal.criar_cliente() as cliente:
        for numero, (id_base, ultima_alteracao, motivo) in enumerate(bases, start=1):
            status_http, payload, erro = None, None, None
            try:
                resposta = portal.buscar(cliente, f"{portal.URL_CONJUNTOS}/{id_base}")
                status_http = resposta.status_code
                # Guarda a resposta crua só quando deu certo
                if status_http == 200:
                    payload = resposta.text
                else:
                    erro = resposta.text[:300]
            except portal.FalhaPortal as falha:
                erro = str(falha)

            coletado_em = datetime.now(timezone.utc).replace(tzinfo=None)
            lote.append((data_coleta, id_base, motivo, ultima_alteracao, status_http, payload, erro, coletado_em))
            if status_http == 200:
                sucessos += 1
            else:
                falhas += 1

            # Chave inválida: não adianta continuar
            if status_http in (401, 403):
                gravar_lote(lote, data_coleta)
                sys.exit(f"HTTP {status_http}: confira a chave no .env. O que foi coletado até aqui está gravado.")

            # Grava a cada lote completo, para não perder trabalho
            if len(lote) == TAMANHO_LOTE:
                gravar_lote(lote, data_coleta)
                lote = []
                minutos = (time.perf_counter() - inicio) / 60
                restante = (len(bases) - numero) * minutos / numero
                print(f"  {numero}/{len(bases)} bases em {minutos:.0f} min; faltam cerca de {restante:.0f} min")

            # Pausa entre chamadas para não sobrecarregar o portal
            time.sleep(portal.PAUSA)

    # Grava o que sobrou no último lote
    if lote:
        gravar_lote(lote, data_coleta)

    minutos = (time.perf_counter() - inicio) / 60
    print(f"\nConcluído: {sucessos} com sucesso, {falhas} com falha, {minutos:.1f} min")
    print(f"Gravado em: {PASTA_DETALHE / f'data={data_coleta}'}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()