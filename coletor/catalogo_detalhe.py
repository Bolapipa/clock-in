"""Coletor do detalhe de cada base do dados.gov.br (Fases 1 e 2).

Segue a decisão 21 (incremental + rodízio). Busca o detalhe de:
- bases novas (nunca coletadas com sucesso);
- bases cujo ultimaAlteracaoMetadados mudou desde a última coleta;
- as bases com a coleta mais antiga, 1/30 do catálogo por dia (rodízio),
  para cada base ser revista ao menos uma vez por mês.
Bases que falharam esperam antes de nova tentativa: 1, 2, 4, 8, 16 e no máximo 30 dias.
Com --completo, busca todas (carga inicial, cerca de 9 horas).

Lê a listagem do dia (rode catalogo_lista.py antes) e o estado do dia anterior
(dados/estado/detalhe_atual.parquet). Grava a resposta crua na Bronze, em partes,
para não perder trabalho se for interrompido, e no fim atualiza o estado:
dados/bronze/catalogo_detalhe/data=AAAA-MM-DD/parte-0001.parquet

Uso:
    python coletor/catalogo_detalhe.py                  # ingestão diária
    python coletor/catalogo_detalhe.py --completo       # carga inicial
    python coletor/catalogo_detalhe.py --max-bases 20   # teste rápido
    python coletor/catalogo_detalhe.py --completo --data 2026-10-25  # retoma uma carga interrompida
"""

import argparse
import math
import os
import re
import sys
import time
from datetime import date, datetime, timezone

import duckdb

import estado
import portal

# Pastas da Bronze
PASTA_LISTA = portal.RAIZ / "dados" / "bronze" / "catalogo_lista"
PASTA_DETALHE = portal.RAIZ / "dados" / "bronze" / "catalogo_detalhe"

# Em quantos dias o rodízio percorre o catálogo inteiro
DIAS_RODIZIO = 30

# Espera máxima, em dias, antes de tentar de novo uma base que falhou
ESPERA_MAXIMA_DIAS = 30

# Quantas bases juntar antes de gravar um arquivo (parte)
TAMANHO_LOTE = 500

# Falhas seguidas do servidor (rede ou 5xx) que indicam portal fora do ar
MAX_FALHAS_SEGUIDAS = 20


def bases_a_coletar(data_coleta, completo):
    """Decide quais bases buscar hoje e por quê (NOVA, ALTERADA, RODIZIO ou COMPLETA)."""
    arquivo_lista = PASTA_LISTA / f"data={data_coleta}" / "catalogo_lista.parquet"
    if not arquivo_lista.exists():
        sys.exit(f"Listagem de {data_coleta} não encontrada. Rode antes: python coletor/catalogo_lista.py")

    con = duckdb.connect()
    estado.carregar(con)

    # Bases que já deram certo hoje (para retomar sem repetir)
    partes_hoje = sorted((PASTA_DETALHE / f"data={data_coleta}").glob("parte-*.parquet"))
    if partes_hoje:
        lista = [parte.as_posix() for parte in partes_hoje]
        con.execute(f"CREATE TABLE feitas_hoje AS SELECT DISTINCT id FROM read_parquet({lista}) WHERE status_http = 200")
    else:
        con.execute("CREATE TABLE feitas_hoje (id VARCHAR)")

    # Bases da listagem de hoje, abrindo o JSON cru de cada página
    con.execute(f"""
        CREATE TABLE hoje AS
        SELECT DISTINCT ON (r ->> 'id')
            r ->> 'id' AS id,
            r ->> 'ultimaAlteracaoMetadados' AS ultima_alteracao
        FROM (
            SELECT unnest(from_json(payload, '["json"]')) AS r
            FROM read_parquet('{arquivo_lista.as_posix()}')
        )
        WHERE r ->> 'id' IS NOT NULL
    """)

    # Quantas bases o rodízio revê por dia: 1/30 do catálogo, arredondado para cima
    total = con.execute("SELECT COUNT(*) FROM hoje").fetchall()[0][0]
    tamanho_rodizio = math.ceil(total / DIAS_RODIZIO)

    bases = con.execute("""
        WITH
        -- Junta cada base da listagem com o que o estado sabe dela
        candidatas AS (
            SELECT
                h.id,
                h.ultima_alteracao,
                e.payload IS NOT NULL AS ja_coletada,
                e.ultima_alteracao     AS alteracao_anterior,
                e.data_coleta,
                COALESCE(e.falhas_seguidas, 0) AS falhas_seguidas,
                e.ultima_tentativa
            FROM hoje h
            LEFT JOIN estado e USING (id)
            WHERE NOT EXISTS (SELECT 1 FROM feitas_hoje f WHERE f.id = h.id)
        ),
        -- Depois de falhar, a base espera 1, 2, 4, 8, 16... dias (no máximo 30)
        liberadas AS (
            SELECT
                *,
                falhas_seguidas = 0
                OR CAST($data AS DATE) >= ultima_tentativa
                   + LEAST(CAST(pow(2, falhas_seguidas - 1) AS INTEGER), $espera_maxima) AS liberada
            FROM candidatas
        ),
        -- Motivo de cada base ser coletada (ou não)
        classificadas AS (
            SELECT
                *,
                CASE
                    WHEN $completo THEN 'COMPLETA'
                    WHEN NOT liberada THEN NULL
                    WHEN NOT ja_coletada THEN 'NOVA'
                    WHEN alteracao_anterior IS DISTINCT FROM ultima_alteracao THEN 'ALTERADA'
                END AS motivo
            FROM liberadas
        ),
        -- Rodízio: entre as que sobraram, as de coleta mais antiga
        rodizio AS (
            SELECT id
            FROM classificadas
            WHERE motivo IS NULL AND ja_coletada AND liberada
            ORDER BY data_coleta, id
            LIMIT $tamanho_rodizio
        )
        SELECT
            c.id,
            c.ultima_alteracao,
            COALESCE(c.motivo, 'RODIZIO') AS motivo
        FROM classificadas c
        WHERE c.motivo IS NOT NULL
           OR EXISTS (SELECT 1 FROM rodizio r WHERE r.id = c.id)
        ORDER BY c.id
    """, {
        "data": data_coleta,
        "completo": completo,
        "espera_maxima": ESPERA_MAXIMA_DIAS,
        "tamanho_rodizio": tamanho_rodizio,
    }).fetchall()

    con.close()
    return bases


def gravar_lote(linhas, data_coleta):
    """Grava um lote de detalhes como uma nova parte na partição do dia."""
    pasta = PASTA_DETALHE / f"data={data_coleta}"
    pasta.mkdir(parents=True, exist_ok=True)

    # Próximo número: o maior que já existe + 1 (não sobrescreve se faltar uma parte no meio)
    numeros = [int(re.search(r"\d+", parte.stem).group()) for parte in pasta.glob("parte-*.parquet")]
    numero = max(numeros, default=0) + 1
    arquivo = pasta / f"parte-{numero:04d}.parquet"
    temporario = pasta / f"parte-{numero:04d}.tmp"

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

    # Grava num arquivo temporário e só depois renomeia: uma parte pela metade nunca vira .parquet
    con.execute(f"COPY catalogo_detalhe TO '{temporario.as_posix()}' (FORMAT parquet)")
    con.close()
    os.replace(temporario, arquivo)
    return arquivo


def main():
    parser = argparse.ArgumentParser(description="Coleta o detalhe das bases do dados.gov.br")
    parser.add_argument("--completo", action="store_true", help="busca todas as bases (carga inicial)")
    parser.add_argument("--max-bases", type=int, help="para depois de N bases (teste)")
    parser.add_argument("--data", type=date.fromisoformat, help="data da listagem a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()

    data_coleta = args.data or portal.data_de_hoje()
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
    falhas_do_servidor_seguidas = 0
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
                estado.atualizar(data_coleta)
                sys.exit(f"HTTP {status_http}: confira a chave no .env. O que foi coletado até aqui está gravado.")

            # Falha do servidor (rede ou 5xx) várias vezes seguidas: o portal está fora do ar
            if status_http is None or status_http >= 500:
                falhas_do_servidor_seguidas += 1
            else:
                falhas_do_servidor_seguidas = 0
            if falhas_do_servidor_seguidas >= MAX_FALHAS_SEGUIDAS:
                gravar_lote(lote, data_coleta)
                estado.atualizar(data_coleta)
                sys.exit(f"{MAX_FALHAS_SEGUIDAS} falhas seguidas do servidor: o portal parece fora do ar. "
                         "O que foi coletado até aqui está gravado.")

            # Grava a cada lote completo, para não perder trabalho
            if len(lote) == TAMANHO_LOTE:
                gravar_lote(lote, data_coleta)
                lote = []
                minutos = (time.perf_counter() - inicio) / 60
                restante = (len(bases) - numero) * minutos / numero
                print(f"  {numero}/{len(bases)} bases em {minutos:.0f} min; faltam cerca de {restante:.0f} min")

            # Pausa entre chamadas para não sobrecarregar o portal
            time.sleep(portal.PAUSA)

    # Grava o que sobrou no último lote e atualiza o estado para o próximo dia
    if lote:
        gravar_lote(lote, data_coleta)
    estado.atualizar(data_coleta)

    minutos = (time.perf_counter() - inicio) / 60
    print(f"\nConcluído: {sucessos} com sucesso, {falhas} com falha, {minutos:.1f} min")
    print(f"Gravado em: {PASTA_DETALHE / f'data={data_coleta}'}")
    print(f"Estado atualizado: {estado.arquivo_estado()}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()