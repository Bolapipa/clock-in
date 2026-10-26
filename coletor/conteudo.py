"""Leitura do conteúdo de um arquivo baixado (Fase 3).

Dado um arquivo que já está no disco, calcula:
- o hash (SHA-256) e o tamanho, que dizem se o conteúdo mudou entre duas coletas;
- o schema, ou seja, o nome e o tipo de cada coluna, que diz se a estrutura mudou.

Este módulo não usa a rede: o download fica em outro módulo e entrega o caminho do arquivo.
O DuckDB descobre sozinho o separador e os tipos; a codificação é tentada em UTF-8 e depois Latin-1,
que são as comuns em dados do governo.

Uso (como biblioteca):
    from conteudo import analisar_arquivo
    resultado = analisar_arquivo(caminho, "CSV")
"""

import hashlib
import json

import duckdb

# Tamanho do pedaço lido por vez ao calcular o hash (1 MB): o arquivo nunca é carregado inteiro na memória
TAMANHO_PEDACO = 1024 * 1024

# Formatos de que o DuckDB lê o schema sozinho. Os demais (XLSX, XLS, ODS, XML) ficam só com o hash por enquanto
FORMATOS_COM_SCHEMA = ("CSV", "TXT", "JSON", "PARQUET")

# Codificações tentadas, na ordem, em arquivos de texto
CODIFICACOES = ("utf-8", "latin-1")


def calcular_hash(caminho):
    """Devolve o SHA-256 (em texto) e o tamanho em bytes do arquivo."""
    resumo = hashlib.sha256()
    tamanho = 0
    with open(caminho, "rb") as arquivo:
        # Lê em pedaços até o fim do arquivo
        while pedaco := arquivo.read(TAMANHO_PEDACO):
            resumo.update(pedaco)
            tamanho += len(pedaco)
    return resumo.hexdigest(), tamanho


def descrever(con, consulta, parametros):
    """Roda um DESCRIBE no DuckDB e devolve a lista de (nome, tipo) das colunas."""
    linhas = con.execute(f"DESCRIBE {consulta}", parametros).fetchall()
    return [(linha[0], linha[1]) for linha in linhas]


def ler_schema(caminho, formato):
    """Lê o schema de um arquivo. Devolve (colunas, erro).

    colunas é uma lista de (nome, tipo) na ordem do arquivo, ou None se não deu para ler.
    erro é None quando deu certo, ou um texto curto: FORMATO_SEM_SCHEMA ou ILEGIVEL.
    """
    if formato not in FORMATOS_COM_SCHEMA:
        return None, "FORMATO_SEM_SCHEMA"

    arquivo = str(caminho)
    con = duckdb.connect()
    try:
        if formato == "PARQUET":
            return descrever(con, "SELECT * FROM read_parquet(?)", [arquivo]), None
        if formato == "JSON":
            return descrever(con, "SELECT * FROM read_json(?)", [arquivo]), None
        # CSV e TXT: tenta cada codificação até uma funcionar
        for codificacao in CODIFICACOES:
            try:
                return descrever(con, "SELECT * FROM read_csv(?, encoding = ?)", [arquivo, codificacao]), None
            except duckdb.Error:
                continue
        return None, "ILEGIVEL"
    except duckdb.Error:
        return None, "ILEGIVEL"
    finally:
        con.close()


def assinatura_do_schema(colunas):
    """Hash curto do schema (nomes, tipos e ordem): dois schemas iguais têm a mesma assinatura."""
    texto = json.dumps(colunas, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def analisar_arquivo(caminho, formato):
    """Hash, tamanho e schema de um arquivo, num dicionário pronto para gravar."""
    hash_conteudo, tamanho = calcular_hash(caminho)
    colunas, erro = ler_schema(caminho, formato)
    return {
        "hash_conteudo": hash_conteudo,
        "tamanho_bytes": tamanho,
        "qtd_colunas": len(colunas) if colunas is not None else None,
        # O schema vai como texto JSON: [["nome", "tipo"], ...]
        "schema": json.dumps(colunas, ensure_ascii=False) if colunas is not None else None,
        "schema_hash": assinatura_do_schema(colunas) if colunas is not None else None,
        "erro_schema": erro,
    }