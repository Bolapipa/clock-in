"""Gera os feeds RSS do Clock-in (Fase 8): arquivos estáticos, sem cadastro e sem custo.

Lê os eventos dos últimos 30 dias (dados/estado/evento_recente.parquet, gerado por gold_eventos.py) e a Silver do dia
(para saber o órgão e o título de cada base). Grava, por padrão em web/public/rss/ (o Next.js a leva para o site):
    geral.xml                todos os eventos recentes
    orgaos/<slug>.xml        um feed por órgão (existe para todos, mesmo sem evento: o RSS vazio é válido)
    bases/<slug-da-base>.xml um feed por base que teve algum evento recente

Os feeds são gerados a cada execução e não vão para o Git (decisão 16). O mesmo acontecimento tem sempre o mesmo
identificador (guid), então o leitor de RSS não mostra a mesma notícia duas vezes.

Uso:
    python publicar/gerar_rss.py                        # usa a Silver de hoje
    python publicar/gerar_rss.py --data 2026-10-26      # usa a Silver de outro dia
    python publicar/gerar_rss.py --saida outra/pasta    # grava em outra pasta
"""

import argparse
import shutil
import sys
from datetime import date, datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

import duckdb

# Este script fica em publicar/ e usa os módulos de coletor/: rodado direto, o Python só enxerga a
# própria pasta, então coletor/ entra no caminho de importação antes dos imports abaixo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coletor"))

import gerar_api
import portal

# Pasta de saída padrão
PASTA_SAIDA = portal.RAIZ / "web" / "public" / "rss"

# Endereço público do site: os itens dos feeds apontam para as páginas dele
URL_DO_SITE = "https://clock-in-monitor.vercel.app"

# Quantos itens cada feed leva, dos mais recentes para os mais antigos
MAX_ITENS_GERAL = 200
MAX_ITENS = 100

# Como cada tipo de evento aparece no título do item
ROTULOS = {
    "STATUS_MUDOU": "Mudou de status",
    "CONTEUDO_MUDOU": "Conteúdo mudou",
    "SCHEMA_MUDOU": "Estrutura mudou",
    "LINK_QUEBROU": "Link quebrou",
}


def ler_eventos(con):
    """Eventos recentes como lista de dicionários, dos mais novos para os mais antigos. Sem arquivo, lista vazia."""
    # A leitura é a mesma do arquivo de cada base da API, por isso vive em gerar_api.py
    return gerar_api.ler_eventos(con)


def momento(data):
    """Data do evento no formato do RSS (RFC 822), ao meio-dia UTC."""
    return format_datetime(datetime(data.year, data.month, data.day, 12, tzinfo=timezone.utc))


def montar_item(evento, base, orgao):
    """Um <item> do feed: título, endereço da página da base no site, descrição e identificador fixo."""
    titulo = f"{ROTULOS.get(evento['tipo_evento'], evento['tipo_evento'])}: {base['titulo'] or base['slug']}"
    endereco = f"{URL_DO_SITE}/orgaos/{orgao['slug']}/?base={base['slug']}"
    descricao = f"{orgao['nome']}: {evento['detalhe']}"
    guid = f"clock-in-{evento['data']}-{evento['id_base']}-{evento['tipo_evento']}"
    return (
        "<item>"
        f"<title>{escape(titulo)}</title>"
        f"<link>{escape(endereco)}</link>"
        f"<description>{escape(descricao)}</description>"
        f"<pubDate>{momento(evento['data'])}</pubDate>"
        f'<guid isPermaLink="false">{escape(guid)}</guid>'
        "</item>"
    )


def montar_feed(titulo, descricao, endereco, itens, data):
    """O XML de um feed RSS 2.0."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        f"<title>{escape(titulo)}</title>"
        f"<link>{escape(endereco)}</link>"
        f"<description>{escape(descricao)}</description>"
        "<language>pt-BR</language>"
        f"<lastBuildDate>{momento(data)}</lastBuildDate>"
        f"{''.join(itens)}"
        "</channel></rss>\n"
    )


def gravar(arquivo, texto):
    """Grava um feed em UTF-8, criando a pasta se faltar."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(texto, encoding="utf-8")


def gerar(con, data, saida):
    """Gera os feeds na pasta 'saida' e devolve (eventos usados, feeds de órgão, feeds de base)."""
    bases = gerar_api.ler_bases(con)
    orgaos = gerar_api.agrupar_por_orgao(bases)

    # De cada base: ela mesma e o órgão dela, pelo id que os eventos trazem
    por_id = {base["id"]: (base, orgao) for orgao in orgaos.values() for base in orgao["bases"]}
    # Evento de uma base que saiu do catálogo não tem para onde apontar: fica de fora
    eventos = [evento for evento in ler_eventos(con) if evento["id_base"] in por_id]

    # Tira os feeds de uma execução anterior que não existem mais
    for pasta in ("orgaos", "bases"):
        shutil.rmtree(saida / pasta, ignore_errors=True)

    def itens_de(lista, limite):
        return [montar_item(evento, *por_id[evento["id_base"]]) for evento in lista[:limite]]

    gravar(saida / "geral.xml", montar_feed(
        "Clock-in: o que mudou nos dados abertos do Brasil",
        "Bases do dados.gov.br que mudaram de status, de conteúdo ou de estrutura e links que quebraram, nos últimos 30 dias.",
        URL_DO_SITE, itens_de(eventos, MAX_ITENS_GERAL), data))

    for orgao in orgaos.values():
        ids = {base["id"] for base in orgao["bases"]}
        do_orgao = [evento for evento in eventos if evento["id_base"] in ids]
        gravar(saida / "orgaos" / f"{orgao['slug']}.xml", montar_feed(
            f"Clock-in: {orgao['nome']}",
            f"O que mudou nas bases de {orgao['nome']} nos últimos 30 dias.",
            f"{URL_DO_SITE}/orgaos/{orgao['slug']}/", itens_de(do_orgao, MAX_ITENS), data))

    com_evento = {}
    for evento in eventos:
        com_evento.setdefault(evento["id_base"], []).append(evento)
    for id_base, da_base in com_evento.items():
        base, orgao = por_id[id_base]
        gravar(saida / "bases" / f"{base['slug']}.xml", montar_feed(
            f"Clock-in: {base['titulo'] or base['slug']}",
            f"O que mudou nesta base de {orgao['nome']} nos últimos 30 dias.",
            f"{URL_DO_SITE}/orgaos/{orgao['slug']}/?base={base['slug']}", itens_de(da_base, MAX_ITENS), data))

    return len(eventos), len(orgaos), len(com_evento)


def main():
    parser = argparse.ArgumentParser(description="Gera os feeds RSS do Clock-in")
    parser.add_argument("--data", type=date.fromisoformat, help="data da Silver a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--saida", type=Path, default=PASTA_SAIDA, help="pasta onde gravar os feeds (padrão: web/public/rss)")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    gerar_api.criar_views_entrada(con, data)
    eventos, orgaos, bases = gerar(con, data, args.saida)
    con.close()

    print(f"Feeds de {data} gravados em {args.saida}")
    print(f"  {eventos} eventos recentes; feeds: 1 geral, {orgaos} de órgãos, {bases} de bases")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
