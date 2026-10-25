-- Silver: uma linha por base do catálogo, na data da coleta.
-- Origens (views criadas por coletor/silver.py):
--   bronze_lista   -> listagem do dia (bronze/catalogo_lista)
--   bronze_detalhe -> detalhes coletados até o dia (bronze/catalogo_detalhe)

-- Bases da listagem do dia, uma linha por base
WITH lista AS (
    SELECT DISTINCT ON (b ->> 'id')
        b ->> 'id'                       AS id,
        b ->> 'nome'                     AS slug,
        b ->> 'title'                    AS titulo,
        b ->> 'nomeOrganizacao'          AS organizacao_listagem,
        CAST(b ->> 'isAtualizado' AS BOOLEAN) AS portal_diz_atualizado,
        b ->> 'ultimaAtualizacaoDados'   AS ultima_atualizacao_dados_texto,
        b ->> 'ultimaAlteracaoMetadados' AS ultima_alteracao_metadados_texto,
        data_coleta
    FROM (
        SELECT unnest(from_json(payload, '["json"]')) AS b, data_coleta
        FROM bronze_lista
    )
),

-- Detalhe mais recente que deu certo de cada base
detalhe AS (
    SELECT
        id,
        arg_max(payload, coletado_em)     AS payload,
        arg_max(data_coleta, coletado_em) AS data_detalhe
    FROM bronze_detalhe
    WHERE status_http = 200
    GROUP BY id
)

SELECT
    l.id,
    l.slug,
    COALESCE(l.titulo, d.payload ->> 'titulo') AS titulo,
    l.organizacao_listagem,
    d.payload ->> 'organizacao' AS organizacao_detalhe,
    d.payload ->> 'responsavel' AS responsavel,
    d.payload ->> 'emailResponsavel' AS email_responsavel,

    -- Periodicidade: vazia vira NAO_DECLARADA (sem detalhe ainda, fica nula)
    CASE
        WHEN d.id IS NULL THEN NULL
        ELSE COALESCE(NULLIF(d.payload ->> 'periodicidade', ''), 'NAO_DECLARADA')
    END AS periodicidade,

    -- Só estas periodicidades dão um prazo esperado (Fase 4)
    d.payload ->> 'periodicidade' IN (
        'DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL', 'TRIMESTRAL',
        'QUADRIMESTRAL', 'SEMESTRAL', 'ANUAL'
    ) AS periodicidade_comparavel,

    -- Como o portal vê a base
    l.portal_diz_atualizado,
    d.payload ->> 'atualizado' AS status_portal,
    CAST(d.payload ->> 'descontinuado' AS BOOLEAN) AS descontinuado,
    d.payload ->> 'selo' AS selo,

    -- Datas em texto brasileiro viram data de verdade; "Indisponível" vira nulo
    try_strptime(l.ultima_atualizacao_dados_texto, '%d/%m/%Y %H:%M:%S') AS ultima_atualizacao_dados,
    try_strptime(l.ultima_alteracao_metadados_texto, '%d/%m/%Y %H:%M:%S') AS ultima_alteracao_metadados,
    try_strptime(d.payload ->> 'dataCatalogacao', '%d/%m/%Y %H:%M:%S') AS data_catalogacao,

    json_array_length(d.payload, '$.recursos') AS qtd_recursos,

    -- Rastreabilidade: de quando é o detalhe usado
    d.id IS NOT NULL AS tem_detalhe,
    d.data_detalhe,
    l.data_coleta
FROM lista l
LEFT JOIN detalhe d USING (id)
ORDER BY l.id