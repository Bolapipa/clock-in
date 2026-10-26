-- Silver: uma linha por arquivo lido no dia, com o que foi medido e se mudou.
-- Origem (view criada por coletor/silver_conteudo.py):
--   conteudo_atual -> estado do conteúdo de cada link (estado/conteudo_atual)
-- A variável data_coleta é o dia da Silver.

SELECT
    link,
    getvariable('data_coleta') AS data_coleta,
    hash_conteudo,
    tamanho_bytes,
    verificacao_parcial,
    qtd_colunas,
    "schema",
    schema_hash,
    erro_schema,
    -- Mudou hoje em relação à leitura anterior (a primeira leitura nunca conta como mudança)
    COALESCE(ultima_mudanca = getvariable('data_coleta'), false) AS mudou_conteudo,
    COALESCE(ultima_mudanca_schema = getvariable('data_coleta'), false) AS mudou_schema
FROM conteudo_atual
WHERE ultima_leitura = getvariable('data_coleta')
ORDER BY link