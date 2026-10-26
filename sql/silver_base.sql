-- Silver: uma linha por base do catálogo, na data da coleta.
-- Origens (views criadas por coletor/silver.py):
--   bronze_lista   -> listagem do dia (bronze/catalogo_lista)
--   detalhe_atual  -> última versão do detalhe de cada base (estado/detalhe_atual)

-- Bases da listagem do dia, uma linha por base
WITH lista AS (
    SELECT DISTINCT ON (b ->> 'id')
        b ->> 'id'                       AS id,
        b ->> 'nome'                     AS slug,
        b ->> 'title'                    AS titulo,
        b ->> 'nomeOrganizacao'          AS organizacao_listagem,
        TRY_CAST(b ->> 'isAtualizado' AS BOOLEAN) AS portal_diz_atualizado,
        b ->> 'ultimaAtualizacaoDados'   AS ultima_atualizacao_dados_texto,
        b ->> 'ultimaAlteracaoMetadados' AS ultima_alteracao_metadados_texto,
        data_coleta
    FROM (
        SELECT unnest(from_json(payload, '["json"]')) AS b, data_coleta
        FROM bronze_lista
    )
),

-- Detalhe mais recente que deu certo de cada base (o estado já guarda só a última versão)
detalhe AS (
    SELECT id, payload, data_coleta AS data_detalhe
    FROM detalhe_atual
    WHERE payload IS NOT NULL
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

    -- Só estas periodicidades dão um prazo esperado (Fase 4).
    -- Periodicidade vazia é "não comparável" (false); sem detalhe ainda, fica nula
    CASE
        WHEN d.id IS NULL THEN NULL
        ELSE COALESCE(d.payload ->> 'periodicidade' IN (
            'DIARIA', 'SEMANAL', 'QUINZENAL', 'MENSAL', 'TRIMESTRAL',
            'QUADRIMESTRAL', 'SEMESTRAL', 'ANUAL'
        ), false)
    END AS periodicidade_comparavel,

    -- Como o portal vê a base
    l.portal_diz_atualizado,
    d.payload ->> 'atualizado' AS status_portal,
    TRY_CAST(d.payload ->> 'descontinuado' AS BOOLEAN) AS descontinuado,
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
