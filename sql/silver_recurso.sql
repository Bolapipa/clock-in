-- Silver: uma linha por recurso (link de arquivo) de cada base do catálogo do dia.
-- Origens (views criadas por coletor/silver.py):
--   bronze_lista   -> listagem do dia, para saber quais bases ainda existem
--   bronze_detalhe -> detalhes coletados até o dia, de onde vêm os recursos

-- Bases que estão na listagem do dia
WITH bases_do_dia AS (
    SELECT DISTINCT b ->> 'id' AS id, data_coleta
    FROM (
        SELECT unnest(from_json(payload, '["json"]')) AS b, data_coleta
        FROM bronze_lista
    )
),

-- Detalhe mais recente que deu certo de cada base
detalhe AS (
    SELECT id, arg_max(payload, coletado_em) AS payload
    FROM bronze_detalhe
    WHERE status_http = 200
    GROUP BY id
),

-- Um recurso por linha (explode a lista de recursos de cada base)
recursos AS (
    SELECT d.id AS id_base, b.data_coleta, unnest(from_json(d.payload -> 'recursos', '["json"]')) AS r
    FROM detalhe d
    JOIN bases_do_dia b USING (id)
)

SELECT
    r ->> 'id'      AS recurso_id,
    id_base,
    r ->> 'titulo'  AS titulo,
    trim(r ->> 'link') AS link,
    upper(trim(r ->> 'formato')) AS formato,
    r ->> 'tipo'    AS tipo,
    CAST(try_strptime(r ->> 'dataUltimaAtualizacaoArquivo', '%d/%m/%Y') AS DATE) AS data_ultima_atualizacao_arquivo,
    CAST(try_strptime(r ->> 'dataCatalogacao', '%d/%m/%Y') AS DATE) AS data_catalogacao,
    data_coleta
FROM recursos
ORDER BY id_base, recurso_id
