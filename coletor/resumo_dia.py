"""Resumo do dia: os números principais da execução, em Markdown (painel do GitHub Actions).

Lê o que o pipeline gravou no dia (Bronze, Silver e Gold) e imprime um texto. No workflow, a saída
vai para o painel da execução ($GITHUB_STEP_SUMMARY), onde dá para ler em um minuto o que aconteceu,
sem abrir os logs. Cada seção é independente: se um passo não rodou, a seção avisa e o resto continua.

Uso:
    python coletor/resumo_dia.py                    # resumo de hoje
    python coletor/resumo_dia.py --data 2026-10-27  # resumo de outro dia
"""

import argparse
from datetime import date

import duckdb

import links
import portal


def milhar(numero):
    """19613 vira '19.613'."""
    return f"{numero:,}".replace(",", ".")


def decimal(numero, casas=1):
    """84.6 vira '84,6'."""
    return f"{numero:.{casas}f}".replace(".", ",")


def percentual(parte, total):
    """'84,6%' ou '-' quando não há total."""
    return f"{decimal(100 * parte / total)}%" if total else "-"


def arquivos_do_dia(tabela, data):
    """Arquivos Parquet de uma tabela no dia, por exemplo 'bronze/link_tentativa'."""
    return sorted((portal.RAIZ / "dados" / tabela / f"data={data}").glob("*.parquet"))


def abrir(con, nome, tabela, data):
    """Cria a view 'nome' com a tabela do dia; devolve False se o dia não tem arquivos."""
    lista = arquivos_do_dia(tabela, data)
    if not lista:
        return False
    caminhos = ", ".join(f"'{arquivo.as_posix()}'" for arquivo in lista)
    con.execute(f"CREATE OR REPLACE VIEW {nome} AS SELECT * FROM read_parquet([{caminhos}])")
    return True


def tabela_md(cabecalho, linhas):
    """Tabela em Markdown: cabecalho é (coluna1, coluna2) e linhas é uma lista de (valor1, valor2)."""
    saida = [f"| {cabecalho[0]} | {cabecalho[1]} |", "|---|---|"]
    saida += [f"| {a} | {b} |" for a, b in linhas]
    return saida


def secao_catalogo(con, data):
    """Bases na listagem e detalhes coletados."""
    saida = ["## Catálogo", ""]
    if not abrir(con, "lista", "bronze/catalogo_lista", data):
        return saida + ["Sem listagem neste dia: o passo da listagem não rodou.", ""], False

    bases = con.execute("SELECT COALESCE(SUM(qtd_registros), 0) FROM lista").fetchall()[0][0]
    linhas = [("Bases na listagem", milhar(bases))]
    if abrir(con, "detalhe", "bronze/catalogo_detalhe", data):
        total, ok = con.execute("SELECT COUNT(*), COUNT(*) FILTER (WHERE status_http = 200) FROM detalhe").fetchall()[0]
        motivos = con.execute("SELECT motivo, COUNT(*) FROM detalhe GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
        por_motivo = ", ".join(f"{motivo.lower()}: {milhar(quantas)}" for motivo, quantas in motivos)
        linhas += [("Detalhes coletados", f"{milhar(ok)} de {milhar(total)} ({por_motivo})"), ("Detalhes com falha", milhar(total - ok))]
    else:
        linhas.append(("Detalhes coletados", "nenhum"))
    return saida + tabela_md(("Item", "Valor"), linhas) + [""], True


def secao_links(con, data):
    """Resultado do teste de links e a saúde dos links depois dele."""
    saida = ["## Links", ""]
    if not abrir(con, "tentativas", "bronze/link_tentativa", data):
        return saida + ["Sem teste de links neste dia: o passo não rodou ou não teve tempo.", ""], False

    # As mesmas regras do estado dos links: resultado inconclusivo não conta como falha (decisões 29, 31 e 36)
    erros, status = list(links.ERROS_INCONCLUSIVOS), list(links.STATUS_INCONCLUSIVOS)
    total, ok, inconclusivos, desistidos, minutos = con.execute(f"""
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE status_http < 400),
               COUNT(*) FILTER (WHERE (status_http IS NULL AND list_contains({erros!r}, erro_tipo)) OR list_contains({status!r}, status_http)),
               COUNT(DISTINCT servidor) FILTER (WHERE erro_tipo = 'SERVIDOR_FORA'),
               COALESCE(date_diff('minute', MIN(tentado_em), MAX(tentado_em)), 0)
        FROM tentativas
    """).fetchall()[0]
    falhas = total - ok - inconclusivos
    linhas = [
        ("Links testados no dia", milhar(total)),
        ("Responderam bem (abaixo de 400)", f"{milhar(ok)} ({percentual(ok, total)})"),
        ("Inconclusivos (não contam como falha)", f"{milhar(inconclusivos)} ({percentual(inconclusivos, total)})"),
        ("Falhas que contam", f"{milhar(falhas)} ({percentual(falhas, total)})"),
        ("Servidores que o teste desistiu de consultar", milhar(desistidos)),
        ("Duração do teste", f"{milhar(minutos)} min"),
    ]
    saida += tabela_md(("Item", "Valor"), linhas) + [""]

    comuns = con.execute("""
        SELECT CASE WHEN status_http IS NULL THEN erro_tipo ELSE 'HTTP ' || status_http END AS resultado, COUNT(*)
        FROM tentativas WHERE status_http IS NULL OR status_http >= 400 GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 8
    """).fetchall()
    if comuns:
        saida += ["Erros mais comuns:", ""] + tabela_md(("Resultado", "Links"), [(r, milhar(q)) for r, q in comuns]) + [""]

    if abrir(con, "link_status", "silver/link_status", data):
        observacao, quebrados = con.execute("""
            SELECT COUNT(*) FILTER (WHERE falhas_seguidas BETWEEN 1 AND 2), COUNT(*) FILTER (WHERE quebrado) FROM link_status
        """).fetchall()[0]
        linhas = [("Links em observação (1 ou 2 falhas seguidas)", milhar(observacao)), ("Links quebrados (3 ou mais)", milhar(quebrados))]
        if abrir(con, "base_saude", "silver/base_saude", data):
            fora = con.execute("SELECT COUNT(*) FILTER (WHERE fora_do_ar) FROM base_saude").fetchall()[0][0]
            linhas.append(("Bases fora do ar", milhar(fora)))
        saida += tabela_md(("Situação depois do teste", "Quantidade"), linhas) + [""]
    else:
        saida += ["A Silver dos links não foi gerada neste dia.", ""]
    return saida, True


def secao_conteudo(con, data):
    """Download e leitura do conteúdo dos arquivos (hash e schema)."""
    saida = ["## Conteúdo dos arquivos", ""]
    if not abrir(con, "leituras", "bronze/conteudo_tentativa", data):
        return saida + ["Nenhum arquivo foi baixado neste dia: o passo não rodou ou não teve tempo.", ""], False

    total, lidos, parciais, bytes_lidos, minutos = con.execute("""
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE hash_conteudo IS NOT NULL),
               COUNT(*) FILTER (WHERE hash_conteudo IS NOT NULL AND verificacao_parcial),
               COALESCE(SUM(tamanho_bytes) FILTER (WHERE hash_conteudo IS NOT NULL), 0),
               COALESCE(date_diff('minute', MIN(tentado_em), MAX(tentado_em)), 0)
        FROM leituras
    """).fetchall()[0]
    linhas = [
        ("Arquivos tentados", milhar(total)),
        ("Lidos com sucesso (hash e schema)", f"{milhar(lidos)} ({percentual(lidos, total)})"),
        ("Lidos só em parte (acima do limite de tamanho)", milhar(parciais)),
        ("Com erro", milhar(total - lidos)),
        ("Volume lido", f"{decimal(bytes_lidos / 1e9, 2)} GB"),
        ("Duração do download", f"{milhar(minutos)} min"),
    ]
    if abrir(con, "versao_conteudo", "silver/versao_conteudo", data):
        mudou_conteudo, mudou_schema = con.execute("""
            SELECT COUNT(*) FILTER (WHERE mudou_conteudo), COUNT(*) FILTER (WHERE mudou_schema) FROM versao_conteudo
        """).fetchall()[0]
        linhas += [("Mudaram de conteúdo hoje", milhar(mudou_conteudo)), ("Mudaram de schema hoje", milhar(mudou_schema))]
    saida += tabela_md(("Item", "Valor"), linhas) + [""]

    erros = con.execute("""
        SELECT erro_tipo, COUNT(*) FROM leituras WHERE erro_tipo IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 6
    """).fetchall()
    if erros:
        saida += ["Erros mais comuns:", ""] + tabela_md(("Erro", "Arquivos"), [(e, milhar(q)) for e, q in erros]) + [""]
    return saida, True


def secao_status(con, data):
    """Status de cada base (Gold)."""
    saida = ["## Status das bases", ""]
    if not abrir(con, "status", "gold/fato_status_base_diario", data):
        return saida + ["O status das bases não foi gerado neste dia.", ""], False

    por_status = con.execute("SELECT status, COUNT(*) FROM status GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
    divergem = con.execute("SELECT COUNT(*) FILTER (WHERE diverge_do_portal) FROM status").fetchall()[0][0]
    saida += tabela_md(("Status", "Bases"), [(nome, milhar(quantas)) for nome, quantas in por_status])
    return saida + ["", f"Divergem do selo do portal: {milhar(divergem)}", ""], True


def secao_estado(data):
    """Tamanho dos arquivos de estado que o próximo dia vai baixar."""
    saida = ["## Estado para o próximo dia", ""]
    arquivos = sorted((portal.RAIZ / "dados" / "estado").glob("*.parquet"))
    if not arquivos:
        return saida + ["Nenhum arquivo de estado.", ""], False
    linhas = [(arquivo.name, f"{decimal(arquivo.stat().st_size / 1e6)} MB") for arquivo in arquivos]
    return saida + tabela_md(("Arquivo", "Tamanho"), linhas) + [""], True


def gerar_resumo(data):
    """Monta o resumo do dia, em Markdown, e devolve o texto."""
    con = duckdb.connect()
    secoes = [
        ("Catálogo", secao_catalogo(con, data)),
        ("Links", secao_links(con, data)),
        ("Conteúdo", secao_conteudo(con, data)),
        ("Status", secao_status(con, data)),
        ("Estado", secao_estado(data)),
    ]
    con.close()

    texto = [f"# Resumo do dia {data}", ""]
    sem_dados = [nome for nome, (_, tem_dados) in secoes if not tem_dados]
    if sem_dados:
        texto += [f"**Atenção:** sem dados em: {', '.join(sem_dados)}.", ""]
    for _, (linhas, _) in secoes:
        texto += linhas
    return "\n".join(texto)


def main():
    parser = argparse.ArgumentParser(description="Resumo do dia em Markdown")
    parser.add_argument("--data", type=date.fromisoformat, help="data do resumo (AAAA-MM-DD); padrão: hoje em Brasília")
    args = parser.parse_args()
    print(gerar_resumo(args.data or portal.data_de_hoje()))


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
