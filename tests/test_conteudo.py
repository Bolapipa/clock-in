"""Testes da leitura de conteúdo (coletor/conteudo.py).

Cria arquivos pequenos numa pasta temporária e confere hash e schema. Não usa rede.
"""

import hashlib
import json

import duckdb

import conteudo


def test_hash_e_tamanho_batem_com_o_do_python(tmp_path):
    arquivo = tmp_path / "a.csv"
    arquivo.write_bytes(b"a;b\n1;2\n")

    hash_conteudo, tamanho = conteudo.calcular_hash(arquivo)

    assert hash_conteudo == hashlib.sha256(b"a;b\n1;2\n").hexdigest()
    assert tamanho == 8


def test_hash_muda_quando_o_conteudo_muda(tmp_path):
    arquivo = tmp_path / "a.csv"
    arquivo.write_text("a;b\n1;2\n")
    antes, _ = conteudo.calcular_hash(arquivo)

    arquivo.write_text("a;b\n1;3\n")
    depois, _ = conteudo.calcular_hash(arquivo)

    assert antes != depois


def test_hash_le_arquivo_maior_que_um_pedaco(tmp_path, monkeypatch):
    # Pedaço de 4 bytes: o arquivo precisa ser lido em vários pedaços e dar o mesmo hash
    monkeypatch.setattr(conteudo, "TAMANHO_PEDACO", 4)
    arquivo = tmp_path / "a.txt"
    arquivo.write_bytes(b"0123456789abcdef!")

    hash_conteudo, tamanho = conteudo.calcular_hash(arquivo)

    assert hash_conteudo == hashlib.sha256(b"0123456789abcdef!").hexdigest()
    assert tamanho == 17


def test_schema_de_csv_com_ponto_e_virgula(tmp_path):
    arquivo = tmp_path / "a.csv"
    arquivo.write_text("codigo;nome;valor\n1;Ana;10.5\n2;Bia;20.5\n", encoding="utf-8")

    colunas, erro = conteudo.ler_schema(arquivo, "CSV")

    assert erro is None
    assert [c[0] for c in colunas] == ["codigo", "nome", "valor"]
    assert colunas[0][1] == "BIGINT"
    assert colunas[2][1] == "DOUBLE"


def test_schema_de_csv_em_latin_1(tmp_path):
    # Sem a segunda tentativa, os bytes de "ã" e "é" não seriam UTF-8 válido
    arquivo = tmp_path / "a.csv"
    arquivo.write_bytes("nome;cidade\nJosé;São Paulo\n".encode("latin-1"))

    colunas, erro = conteudo.ler_schema(arquivo, "CSV")

    assert erro is None
    assert [c[0] for c in colunas] == ["nome", "cidade"]


def test_schema_de_json(tmp_path):
    arquivo = tmp_path / "a.json"
    arquivo.write_text(json.dumps([{"id": 1, "nome": "Ana"}, {"id": 2, "nome": "Bia"}]))

    colunas, erro = conteudo.ler_schema(arquivo, "JSON")

    assert erro is None
    assert [c[0] for c in colunas] == ["id", "nome"]


def test_schema_de_parquet(tmp_path):
    arquivo = tmp_path / "a.parquet"
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 1 AS id, 'x' AS nome) TO '{arquivo.as_posix()}' (FORMAT parquet)")
    con.close()

    colunas, erro = conteudo.ler_schema(arquivo, "PARQUET")

    assert erro is None
    assert [c[0] for c in colunas] == ["id", "nome"]


def test_formato_sem_leitura_de_schema_devolve_o_motivo(tmp_path):
    arquivo = tmp_path / "a.xlsx"
    arquivo.write_bytes(b"qualquer coisa")

    colunas, erro = conteudo.ler_schema(arquivo, "XLSX")

    assert colunas is None
    assert erro == "FORMATO_SEM_SCHEMA"


def test_arquivo_que_nao_e_do_formato_devolve_ilegivel(tmp_path):
    arquivo = tmp_path / "a.parquet"
    arquivo.write_bytes(b"isto nao e parquet")

    colunas, erro = conteudo.ler_schema(arquivo, "PARQUET")

    assert colunas is None
    assert erro == "ILEGIVEL"


def test_mesma_estrutura_mesma_assinatura_e_coluna_nova_muda(tmp_path):
    base = [("id", "BIGINT"), ("nome", "VARCHAR")]
    com_coluna_nova = base + [("valor", "DOUBLE")]
    mesma_ordem_trocada = [("nome", "VARCHAR"), ("id", "BIGINT")]

    assert conteudo.assinatura_do_schema(base) == conteudo.assinatura_do_schema(list(base))
    assert conteudo.assinatura_do_schema(base) != conteudo.assinatura_do_schema(com_coluna_nova)
    # A ordem das colunas faz parte do schema
    assert conteudo.assinatura_do_schema(base) != conteudo.assinatura_do_schema(mesma_ordem_trocada)


def test_analisar_arquivo_junta_hash_e_schema(tmp_path):
    arquivo = tmp_path / "a.csv"
    arquivo.write_text("id;nome\n1;Ana\n", encoding="utf-8")

    resultado = conteudo.analisar_arquivo(arquivo, "CSV")

    assert resultado["tamanho_bytes"] == arquivo.stat().st_size
    assert resultado["qtd_colunas"] == 2
    assert json.loads(resultado["schema"]) == [["id", "BIGINT"], ["nome", "VARCHAR"]]
    assert resultado["erro_schema"] is None
    assert len(resultado["hash_conteudo"]) == 64
    assert len(resultado["schema_hash"]) == 64


def test_analisar_arquivo_sem_schema_ainda_tem_hash(tmp_path):
    arquivo = tmp_path / "a.xlsx"
    arquivo.write_bytes(b"conteudo")

    resultado = conteudo.analisar_arquivo(arquivo, "XLSX")

    assert len(resultado["hash_conteudo"]) == 64
    assert resultado["schema"] is None
    assert resultado["qtd_colunas"] is None
    assert resultado["schema_hash"] is None
    assert resultado["erro_schema"] == "FORMATO_SEM_SCHEMA"