"""Gera a API estática do Clock-in (protótipo da Fase 6): arquivos JSON lidos pelo site.

Lê a Silver do dia (bases, órgão publicador e saúde dos links) e, se existir, o status
das bases (Gold). Grava, por padrão em site/api/:
    resumo.json           totais do Brasil
    orgaos.json           um resumo por órgão publicador
    orgaos/<slug>.json    o órgão e a lista das bases dele

Os arquivos são gerados a cada execução e não vão para o Git (decisão 16).

Uso:
    python publicar/gerar_api.py                        # usa a Silver de hoje
    python publicar/gerar_api.py --data 2026-10-26      # usa a Silver de outro dia
    python publicar/gerar_api.py --saida outra/pasta    # grava em outra pasta
"""

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

# Este script fica em publicar/ e usa os módulos de coletor/: rodado direto, o Python só enxerga a
# própria pasta, então coletor/ entra no caminho de importação antes dos imports abaixo
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "coletor"))

import gold_status
import portal
import silver

# Pasta de saída padrão e arquivo SQL que lista as bases
PASTA_SAIDA = portal.RAIZ / "site" / "api"
ARQUIVO_SQL = "api_base.sql"

# Um órgão com menos links testados que isto fica sem porcentagem: com poucos links, 1 ou 2 falhas
# fariam o órgão parecer muito pior (ou melhor) do que ele é
MINIMO_TESTADOS_PARA_PERCENTUAL = 30


def criar_slug(nome):
    """Nome do órgão sem acentos, em minúsculas e com hífens: 'IPEA - Instituto' vira 'ipea-instituto'."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-") or "sem-nome"


def criar_views_entrada(con, data):
    """Cria as views silver_base, silver_publicador, silver_base_saude, silver_recurso e status_base."""
    for nome in ("base", "publicador", "base_saude", "recurso"):
        arquivo = silver.PASTA_SILVER / nome / f"data={data}" / f"{nome}.parquet"
        if not arquivo.exists():
            sys.exit(f"Silver {nome} de {data} não encontrada. Rode antes silver.py e silver_links.py com --data {data}")
        con.execute(f"CREATE OR REPLACE VIEW silver_{nome} AS SELECT * FROM read_parquet('{arquivo.as_posix()}')")

    # Status das bases (Gold): sem ele, todas as bases ficam "não verificável"
    status = gold_status.PASTA_GOLD / gold_status.TABELA / f"data={data}" / f"{gold_status.TABELA}.parquet"
    if status.exists():
        con.execute(f"CREATE OR REPLACE VIEW status_base AS SELECT * FROM read_parquet('{status.as_posix()}')")
    else:
        con.execute("CREATE OR REPLACE TABLE status_base (id VARCHAR, status VARCHAR, motivo VARCHAR)")


def ler_bases(con):
    """Roda o SQL e devolve as bases como lista de dicionários."""
    consulta = (silver.PASTA_SQL / ARQUIVO_SQL).read_text(encoding="utf-8")
    resultado = con.execute(consulta)
    colunas = [coluna[0] for coluna in resultado.description]
    return [dict(zip(colunas, linha)) for linha in resultado.fetchall()]


def percentual(parte, total):
    """Porcentagem com 1 casa decimal; nulo quando não há total."""
    return round(100 * parte / total, 1) if total else None


def agrupar_por_orgao(bases):
    """Agrupa as bases por órgão e soma os links. Devolve {slug: órgão}, com as bases dentro de cada órgão."""
    nomes = sorted({base["publicador"] for base in bases})
    # O slug é fixo para um nome; se dois nomes dessem o mesmo slug, o segundo ganha um número
    slugs, usados = {}, set()
    for nome in nomes:
        slug = criar_slug(nome)
        candidato, numero = slug, 2
        while candidato in usados:
            candidato, numero = f"{slug}-{numero}", numero + 1
        usados.add(candidato)
        slugs[nome] = candidato

    orgaos = {}
    for base in bases:
        slug = slugs[base["publicador"]]
        orgao = orgaos.setdefault(slug, {"nome": base["publicador"], "slug": slug, "esfera": base["esfera"], "bases": []})
        orgao["bases"].append(base)

    for orgao in orgaos.values():
        lista = orgao["bases"]
        total = sum(base["links_total"] for base in lista)
        testados = sum(base["links_testados"] for base in lista)
        ok = sum(base["links_ok"] for base in lista)
        orgao.update({
            "qtd_bases": len(lista),
            "links_total": total,
            "links_testados": testados,
            "links_ok": ok,
            "links_em_observacao": sum(base["links_em_observacao"] for base in lista),
            "links_quebrados": sum(base["links_quebrados"] for base in lista),
            "bases_fora_do_ar": sum(base["fora_do_ar"] for base in lista),
            "percentual_ok": percentual(ok, testados) if testados >= MINIMO_TESTADOS_PARA_PERCENTUAL else None,
            "cobertura_links": percentual(testados, total),
            "status": dict(sorted(Counter(base["status"] for base in lista).items())),
        })
    return orgaos


def montar_resumo(bases, orgaos, recursos, data):
    """Totais do Brasil, para a página inicial."""
    total = sum(base["links_total"] for base in bases)
    testados = sum(base["links_testados"] for base in bases)
    ok = sum(base["links_ok"] for base in bases)
    return {
        "versao": "prototipo",
        "data_coleta": str(data),
        "gerado_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bases": len(bases),
        "recursos": recursos,
        "orgaos": len(orgaos),
        "links": {
            "total": total,
            "testados": testados,
            "ok": ok,
            "em_observacao": sum(base["links_em_observacao"] for base in bases),
            "quebrados": sum(base["links_quebrados"] for base in bases),
            "percentual_ok": percentual(ok, testados),
            "cobertura": percentual(testados, total),
        },
        "bases_fora_do_ar": sum(base["fora_do_ar"] for base in bases),
        "bases_sem_link": sum(1 for base in bases if base["links_total"] == 0),
        "status": dict(sorted(Counter(base["status"] for base in bases).items())),
        "esferas": [{"esfera": esfera, "bases": quantas} for esfera, quantas in Counter(base["esfera"] for base in bases).most_common()],
        "periodicidades": [{"periodicidade": periodicidade, "bases": quantas}
                           for periodicidade, quantas in Counter(base["periodicidade"] for base in bases).most_common()],
    }


def gravar_json(arquivo, dados):
    """Grava um JSON compacto em UTF-8, criando a pasta se faltar."""
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def gerar(con, data, saida):
    """Gera os JSON da API na pasta 'saida' e devolve (resumo, quantidade de órgãos)."""
    bases = ler_bases(con)
    orgaos = agrupar_por_orgao(bases)
    recursos = con.execute("SELECT COUNT(*) FROM silver_recurso").fetchall()[0][0]

    # Tira os órgãos de uma execução anterior que não existem mais
    for antigo in (saida / "orgaos").glob("*.json"):
        antigo.unlink()

    # Lista de órgãos, sem as bases: os mais bases primeiro
    ordenados = sorted(orgaos.values(), key=lambda orgao: (-orgao["qtd_bases"], orgao["nome"]))
    resumo_dos_orgaos = [{chave: valor for chave, valor in orgao.items() if chave != "bases"} for orgao in ordenados]
    gravar_json(saida / "orgaos.json", resumo_dos_orgaos)

    # Um arquivo por órgão, com as bases que têm problema primeiro
    for orgao in ordenados:
        bases_do_orgao = sorted(orgao["bases"], key=lambda base: (-base["links_quebrados"], -base["links_em_observacao"], base["titulo"] or ""))
        gravar_json(saida / "orgaos" / f"{orgao['slug']}.json", {**{k: v for k, v in orgao.items() if k != "bases"}, "bases": bases_do_orgao})

    resumo = montar_resumo(bases, orgaos, recursos, data)
    gravar_json(saida / "resumo.json", resumo)
    return resumo, len(orgaos)


def main():
    parser = argparse.ArgumentParser(description="Gera a API estática (JSON) do Clock-in")
    parser.add_argument("--data", type=date.fromisoformat, help="data da Silver a usar (AAAA-MM-DD); padrão: hoje em Brasília")
    parser.add_argument("--saida", type=Path, default=PASTA_SAIDA, help="pasta onde gravar os JSON (padrão: site/api)")
    args = parser.parse_args()
    data = args.data or portal.data_de_hoje()

    con = duckdb.connect()
    criar_views_entrada(con, data)
    resumo, orgaos = gerar(con, data, args.saida)
    con.close()

    links = resumo["links"]
    print(f"API de {data} gravada em {args.saida}")
    print(f"  {resumo['bases']} bases em {orgaos} órgãos; {links['testados']} links testados, "
          f"{links['percentual_ok']}% respondendo bem; {links['quebrados']} quebrados; {resumo['bases_fora_do_ar']} bases fora do ar")


# Só executa quando o arquivo é rodado direto
if __name__ == "__main__":
    main()
