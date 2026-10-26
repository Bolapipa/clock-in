-- Silver: uma linha por recurso (link de arquivo) de cada base do catálogo do dia.
-- Origens (views criadas por coletor/silver.py):
--   bronze_lista   -> listagem do dia, para saber quais bases ainda existem
--   detalhe_atual  -> última versão do detalhe de cada base, de onde vêm os recursos

-- Bases que estão na listagem do dia
WITH bases_do_dia AS (
    SELECT DISTINCT b ->> 'id' AS id, data_coleta
    FROM (
        SELECT unnest(from_json(payload, '["json"]')) AS b, data_coleta
        FROM bronze_lista
    )
),

-- Detalhe mais recente que deu certo de cada base (o estado já guarda só a última versão)
detalhe AS (
    SELECT id, payload
    FROM detalhe_atual
    WHERE payload IS NOT NULL
),


-- Um recurso por linha (explode a lista de recursos de cada base)
recursos AS (
    SELECT d.id AS id_base, b.data_coleta, unnest(from_json(d.payload -> 'recursos', '["json"]')) AS r
    FROM detalhe d
    JOIN bases_do_dia b USING (id)
),

-- Formato sem ruído de digitação: tira o prefixo "FILE:///APP/FTYPE/", pontos e
-- asteriscos nas pontas, e troca espaços por "+" ("ZIP SHP" e "ZIP + XML" viram "ZIP+SHP" e "ZIP+XML")
formatos AS (
    SELECT
        r,
        id_base,
        data_coleta,
        upper(trim(r ->> 'formato')) AS formato,
        NULLIF(
            replace(replace(
                regexp_replace(
                    regexp_replace(upper(trim(r ->> 'formato')), '^FILE:///APP/FTYPE/', ''),
                    '^[.*´]+|[.]+$', '', 'g'),
                ' + ', '+'), ' ', '+'),
            ''
        ) AS formato_sem_ruido
    FROM recursos
),

-- Erros de digitação comuns, corrigidos um a um (só os que têm um único sentido possível)
formatos_corrigidos AS (
    SELECT
        *,
        CASE formato_sem_ruido
            WHEN 'CVS'  THEN 'CSV'
            WHEN 'XLXS' THEN 'XLSX'
            ELSE formato_sem_ruido
        END AS formato_limpo
    FROM formatos
)

SELECT
    r ->> 'id'      AS recurso_id,
    id_base,
    r ->> 'titulo'  AS titulo,
    trim(r ->> 'link') AS link,
    formato,
    formato_limpo,
    -- Formatos que o motor consegue ler e comparar na Fase 3 (hash e schema)
    coalesce(formato_limpo IN ('CSV', 'JSON', 'XLSX', 'XLS', 'XML', 'TXT', 'ODS', 'PARQUET'), false) AS formato_tabular,
    r ->> 'tipo'    AS tipo,
    CAST(try_strptime(r ->> 'dataUltimaAtualizacaoArquivo', '%d/%m/%Y') AS DATE) AS data_ultima_atualizacao_arquivo,
    CAST(try_strptime(r ->> 'dataCatalogacao', '%d/%m/%Y') AS DATE) AS data_catalogacao,
    data_coleta
FROM formatos_corrigidos
ORDER BY id_base, recurso_id
