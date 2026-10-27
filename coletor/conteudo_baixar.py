"""Download do conteúdo dos arquivos (Fase 3).

Para cada link escolhido por conteudo_selecao.py, baixa o arquivo para uma pasta temporária,
tira o hash e o schema (conteudo.py), grava o resultado na Bronze e apaga o arquivo:
nenhum arquivo dos órgãos fica guardado, só o hash, o tamanho e o schema.

Coleta educada:
- uma requisição por vez em cada servidor, com pausa entre elas;
- vários servidores ao mesmo tempo, para caber no tempo do job;
- o servidor que falha 5 vezes seguidas na rede é dispensado no resto do dia.

Limites (decisão 15, provisórios): arquivo grande é cortado em LIMITE_BYTES e o hash vale só
para essa parte (verificacao_parcial = true). Página HTML no lugar do arquivo não conta como leitura.

Cada tentativa vai para a Bronze e o estado de cada link é mantido em um arquivo:
dados/bronze/conteudo_tentativa/data=AAAA-MM-DD/parte-0001.parquet
dados/estado/conteudo_atual.parquet  (ver conteudo_estado.py)

Uso:
    python coletor/conteudo_baixar.py                    # links do dia, pela decisão 27
    python coletor/conteudo_baixar.py --max-links 50     # teste com uma amostra
    python coletor/conteudo_baixar.py --tempo-maximo 90  # para depois de 90 minutos
    python coletor/conteudo_baixar.py --data 2026-10-26  # usa a Silver de outro dia (retoma o dia)
"""

import argparse
import asyncio
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import httpx

import conteudo
import conteudo_estado
import conteudo_selecao
import links
import portal

# Tempo máximo sem receber nada do servidor, em segundos
TIMEOUT = 60

# Tempo máximo para baixar um arquivo inteiro, em segundos (um servidor que "pinga" bytes não prende o job)
TEMPO_MAXIMO_POR_ARQUIVO = 120

# Pausa entre dois downloads do mesmo servidor, em segundos
PAUSA_POR_SERVIDOR = 1.0

# Quantos servidores são baixados ao mesmo tempo (menos que no teste de links: download pesa mais)
SERVIDORES_SIMULTANEOS = 50

# Tamanho máximo lido de cada arquivo (decisão 15, provisório): 50 MB
LIMITE_BYTES = 50 * 1024 * 1024

# Quantas tentativas juntar antes de gravar um arquivo (parte)
TAMANHO_LOTE = 1000

# Falhas de rede seguidas num servidor que fazem o download desistir dele no dia
FALHAS_DE_REDE_PARA_DESISTIR = 5

# Tipos de erro que indicam o servidor inteiro com problema (e não só aquele arquivo)
ERROS_DE_REDE = links.ERROS_DE_REDE

# Posição de erro_tipo nas linhas da Bronze (ver montar_linha)
POSICAO_ERRO_TIPO = 11


def criar_cliente():
    """Cria o cliente HTTP assíncrono. Sem a chave da API: os links são de outros sites."""
    limites = httpx.Limits(max_connections=SERVIDORES_SIMULTANEOS + 20, max_keepalive_connections=20)
    return httpx.AsyncClient(
        headers={"User-Agent": portal.USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        limits=limites,
    )


def montar_linha(data, link, servidor, status_http, resultado=None, parcial=None, erro_tipo=None):
    """Monta a linha da Bronze com o resultado de um download.

    resultado é o dicionário de conteudo.analisar_arquivo (None quando não houve leitura).
    """
    tentado_em = datetime.now(timezone.utc).replace(tzinfo=None)
    r = resultado or {}
    return (data, link, servidor, status_http, r.get("tamanho_bytes"), r.get("hash_conteudo"),
            r.get("qtd_colunas"), r.get("schema"), r.get("schema_hash"), r.get("erro_schema"),
            parcial, erro_tipo, tentado_em)


async def baixar_para_disco(cliente, link, destino):
    """Baixa o arquivo para 'destino'. Devolve (status_http, parcial, erro_tipo).

    erro_tipo é None quando o arquivo foi baixado: inteiro, ou só os primeiros LIMITE_BYTES (parcial).
    Os erros tratados aqui são HTTP_<status>, HTML e TIMEOUT; falhas de rede viram exceção.
    """
    inicio = time.perf_counter()
    async with cliente.stream("GET", link) as resposta:
        status = resposta.status_code
        if status >= 400:
            return status, False, f"HTTP_{status}"

        # Página HTML no lugar do arquivo (link que abre uma tela do órgão): o hash dela não diz nada sobre os dados
        if "text/html" in resposta.headers.get("content-type", "").lower():
            return status, False, "HTML"

        baixados = 0
        parcial = False
        with open(destino, "wb") as arquivo:
            async for pedaco in resposta.aiter_bytes():
                if time.perf_counter() - inicio > TEMPO_MAXIMO_POR_ARQUIVO:
                    return status, False, "TIMEOUT"

                # Passou do limite: guarda só o que cabe e para de baixar
                restante = LIMITE_BYTES - baixados
                if len(pedaco) > restante:
                    arquivo.write(pedaco[:restante])
                    parcial = True
                    break
                arquivo.write(pedaco)
                baixados += len(pedaco)
    return status, parcial, None


async def baixar_link(cliente, data, link, servidor, formato):
    """Baixa e analisa um link. Qualquer falha vira uma linha de erro: um arquivo ruim não derruba os outros."""
    try:
        # A pasta temporária (e o arquivo dentro dela) some no fim, com sucesso ou erro
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / "arquivo"
            status, parcial, erro_tipo = await baixar_para_disco(cliente, link, destino)
            if erro_tipo:
                return montar_linha(data, link, servidor, status, erro_tipo=erro_tipo)

            # A leitura do arquivo usa o disco e a CPU: roda fora do laço de eventos, para não travar os outros downloads
            resultado = await asyncio.to_thread(conteudo.analisar_arquivo, destino, formato)
            return montar_linha(data, link, servidor, status, resultado, parcial)
    except Exception as erro:
        return montar_linha(data, link, servidor, None, erro_tipo=links.classificar_erro(erro))


async def executar(por_servidor, data, limite_segundos=None):
    """Baixa os links: um por vez em cada servidor, vários servidores em paralelo.

    Com limite_segundos, para de começar downloads novos quando o tempo acaba. Os links que
    ficaram sem leitura não entram no estado e voltam primeiro no dia seguinte.
    Devolve quantos links foram tentados.
    """
    total = sum(len(itens) for itens in por_servidor.values())
    buffer = []
    feitos = 0
    inicio = time.perf_counter()
    prazo = None if limite_segundos is None else inicio + limite_segundos
    semaforo = asyncio.Semaphore(SERVIDORES_SIMULTANEOS)

    async with criar_cliente() as cliente:

        async def baixar_servidor(servidor, itens):
            nonlocal feitos
            async with semaforo:
                falhas_de_rede = 0
                for link, formato in itens:
                    # O tempo acabou: este servidor para aqui (um download em andamento termina normalmente)
                    if prazo is not None and time.perf_counter() >= prazo:
                        return

                    # Servidor que falhou várias vezes seguidas: não espera mais timeouts, só registra a falha
                    desistiu = falhas_de_rede >= FALHAS_DE_REDE_PARA_DESISTIR
                    if desistiu:
                        linha = montar_linha(data, link, servidor, None, erro_tipo="SERVIDOR_FORA")
                    else:
                        linha = await baixar_link(cliente, data, link, servidor, formato)
                        falhas_de_rede = falhas_de_rede + 1 if linha[POSICAO_ERRO_TIPO] in ERROS_DE_REDE else 0
                    buffer.append(linha)
                    feitos += 1

                    # Grava a cada lote completo, para não perder trabalho
                    if len(buffer) >= TAMANHO_LOTE:
                        conteudo_estado.gravar_lote(list(buffer), data)
                        buffer.clear()
                        minutos = (time.perf_counter() - inicio) / 60
                        print(f"  {feitos}/{total} arquivos em {minutos:.0f} min", flush=True)

                    # Pausa entre dois downloads do mesmo servidor (sem pausa se nada foi pedido ao servidor)
                    if not desistiu:
                        await asyncio.sleep(PAUSA_POR_SERVIDOR)

        try:
            await asyncio.gather(*(baixar_servidor(s, itens) for s, itens in por_servidor.items()))
        finally:
            # Mesmo interrompido, grava o que já foi baixado
            if buffer:
                conteudo_estado.gravar_lote(list(buffer), data)

    return feitos


def resumo(data):
    """Imprime o resultado do dia, lido da Bronze."""
    partes = [parte.as_posix() for parte in conteudo_estado.partes_do_dia(data)]
    con = duckdb.connect()
    con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet({partes})")
    total, lidos, parciais, sem_schema = con.execute("""
        SELECT COUNT(*),
               COUNT(hash_conteudo),
               COUNT(*) FILTER (WHERE verificacao_parcial),
               COUNT(*) FILTER (WHERE hash_conteudo IS NOT NULL AND "schema" IS NULL)
        FROM t
    """).fetchall()[0]
    print(f"\n{total} arquivos tentados: {lidos} ({lidos / total:.1%}) lidos; "
          f"{parciais} só em parte (acima do limite); {sem_schema} sem schema legível")
    for tipo, quantos in con.execute("""
        SELECT erro_tipo, COUNT(*) FROM t WHERE erro_tipo IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 12
    """).fetchall():
        print(f"  {tipo}: {quantos}")
    con.close()


def main():
    parser = argparse.ArgumentParser(description="Baixa o conteúdo dos arquivos e registra hash e schema")
    parser.add_argument("--data", type=date.fromisoformat, help="data da execução (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--max-links", type=int, help="baixa só uma amostra de N arquivos (teste)")
    parser.add_argument("--tempo-maximo", type=float, help="para de baixar depois de N minutos (o que faltou fica para o dia seguinte)")
    args = parser.parse_args()

    data = args.data or portal.data_de_hoje()
    por_servidor = conteudo_selecao.selecionar(data, args.max_links)

    total = sum(len(itens) for itens in por_servidor.values())
    if not total:
        print(f"Nenhum arquivo a baixar em {data}.")
        return
    maior = max(len(itens) for itens in por_servidor.values())
    print(f"{total} arquivos em {len(por_servidor)} servidores; o maior tem {maior}", flush=True)

    limite = None if args.tempo_maximo is None else args.tempo_maximo * 60
    feitos = asyncio.run(executar(por_servidor, data, limite))
    if feitos < total:
        print(f"\nTempo máximo de {args.tempo_maximo:.0f} min atingido: {feitos} de {total} arquivos tentados. "
              "Os demais ficam para o dia seguinte (os nunca lidos e os lidos há mais tempo vão primeiro).")
    conteudo_estado.atualizar_estado(data)

    # Sem nenhuma tentativa hoje (o tempo acabou antes da primeira), não há o que resumir
    if feitos:
        resumo(data)
    print(f"\nEstado atualizado: {conteudo_estado.arquivo_estado()}")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()