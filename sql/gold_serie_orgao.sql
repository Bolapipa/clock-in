-- Série diária: a contagem de bases por status de cada órgão publicador, no dia (Fase 5).
-- A nota e a cobertura são calculadas em coletor/nota.py, a mesma fórmula da API.
-- Origens (views criadas por coletor/gold_serie.py):
--   silver_base        -> as bases do dia
--   silver_publicador  -> órgão publicador real e esfera de cada base
--   status_hoje        -> status de cada base no dia (gold/fato_status_base_diario)

WITH bases AS (
    SELECT
        b.id,
        COALESCE(p.publicador, 'Não identificado') AS orgao,
        COALESCE(p.esfera, 'NAO_CLASSIFICADA') AS esfera,
        -- Base sem linha no status do dia ainda não é verificável
        COALESCE(s.status, 'NAO_VERIFICAVEL') AS status
    FROM silver_base b
    LEFT JOIN silver_publicador p ON p.id = b.id
    LEFT JOIN status_hoje s ON s.id = b.id
)

SELECT
    orgao,
    -- Como na API, a esfera do órgão é a da primeira base, pelo id
    arg_min(esfera, id) AS esfera,
    COUNT(*) AS bases_total,
    COUNT(*) FILTER (WHERE status = 'EM_DIA') AS em_dia,
    COUNT(*) FILTER (WHERE status = 'ATRASADA') AS atrasada,
    COUNT(*) FILTER (WHERE status = 'PARADA') AS parada,
    COUNT(*) FILTER (WHERE status = 'FORA_DO_AR') AS fora_do_ar,
    COUNT(*) FILTER (WHERE status = 'NAO_VERIFICAVEL') AS nao_verificavel
FROM bases
GROUP BY orgao
ORDER BY orgao
