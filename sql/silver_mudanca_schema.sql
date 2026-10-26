-- Silver: uma linha por mudança de estrutura detectada no dia, coluna a coluna.
-- Origem (view criada por coletor/silver_conteudo.py):
--   conteudo_atual -> estado do conteúdo de cada link (estado/conteudo_atual)
-- A variável data_coleta é o dia da Silver.
-- O schema é um texto JSON no formato [["nome", "tipo"], ...], na ordem do arquivo.

-- Links cuja estrutura mudou hoje, com a estrutura de antes e a de agora
WITH mudados AS (
    SELECT link, schema_anterior, "schema" AS schema_atual
    FROM conteudo_atual
    WHERE ultima_mudanca_schema = getvariable('data_coleta')
),

-- Uma coluna por linha, com a posição dela no arquivo
antes AS (
    SELECT link, c.posicao, c.coluna, c.tipo
    FROM (
        SELECT link, unnest(list_transform(
            from_json(schema_anterior, '["json"]'),
            lambda x, i: {'posicao': i, 'coluna': json_extract_string(x, '$[0]'), 'tipo': json_extract_string(x, '$[1]')}
        )) AS c
        FROM mudados
    )
),
depois AS (
    SELECT link, c.posicao, c.coluna, c.tipo
    FROM (
        SELECT link, unnest(list_transform(
            from_json(schema_atual, '["json"]'),
            lambda x, i: {'posicao': i, 'coluna': json_extract_string(x, '$[0]'), 'tipo': json_extract_string(x, '$[1]')}
        )) AS c
        FROM mudados
    )
),

-- Colunas que só existiam antes e colunas que só existem agora
removidas AS (
    SELECT a.*
    FROM antes a
    WHERE NOT EXISTS (SELECT 1 FROM depois d WHERE d.link = a.link AND d.coluna = a.coluna)
),
adicionadas AS (
    SELECT d.*
    FROM depois d
    WHERE NOT EXISTS (SELECT 1 FROM antes a WHERE a.link = d.link AND a.coluna = d.coluna)
),

-- Renomeada provável: uma coluna sumiu e outra de mesmo tipo apareceu na mesma posição
renomeadas AS (
    SELECT r.link, r.coluna AS coluna_antes, a.coluna AS coluna_depois, r.tipo
    FROM removidas r
    JOIN adicionadas a ON a.link = r.link AND a.posicao = r.posicao AND a.tipo = r.tipo
),

-- Todas as mudanças coluna a coluna
mudancas AS (
    SELECT link, 'ADICIONADA' AS tipo_mudanca, coluna, CAST(NULL AS VARCHAR) AS coluna_depois,
           CAST(NULL AS VARCHAR) AS tipo_antes, tipo AS tipo_depois
    FROM adicionadas a
    WHERE NOT EXISTS (SELECT 1 FROM renomeadas n WHERE n.link = a.link AND n.coluna_depois = a.coluna)

    UNION ALL
    SELECT link, 'REMOVIDA', coluna, NULL, tipo, NULL
    FROM removidas r
    WHERE NOT EXISTS (SELECT 1 FROM renomeadas n WHERE n.link = r.link AND n.coluna_antes = r.coluna)

    UNION ALL
    SELECT link, 'RENOMEADA_PROVAVEL', coluna_antes, coluna_depois, tipo, tipo
    FROM renomeadas

    UNION ALL
    -- Mesma coluna nos dois lados, com tipo diferente
    SELECT a.link, 'TIPO_ALTERADO', a.coluna, NULL, a.tipo, d.tipo
    FROM antes a
    JOIN depois d ON d.link = a.link AND d.coluna = a.coluna
    WHERE a.tipo <> d.tipo

    UNION ALL
    -- Mesmas colunas e tipos, em outra ordem: o schema mudou, mas nenhuma das regras acima viu
    SELECT m.link, 'ORDEM_ALTERADA', NULL, NULL, NULL, NULL
    FROM mudados m
    WHERE NOT EXISTS (SELECT 1 FROM removidas r WHERE r.link = m.link)
      AND NOT EXISTS (SELECT 1 FROM adicionadas a WHERE a.link = m.link)
      AND NOT EXISTS (
          SELECT 1 FROM antes a JOIN depois d ON d.link = a.link AND d.coluna = a.coluna
          WHERE a.link = m.link AND a.tipo <> d.tipo
      )
)

SELECT
    link,
    getvariable('data_coleta') AS data_coleta,
    tipo_mudanca,
    coluna,
    coluna_depois,
    tipo_antes,
    tipo_depois
FROM mudancas
ORDER BY link, tipo_mudanca, coluna