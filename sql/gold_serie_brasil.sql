-- Série diária: os totais do Brasil no dia, uma linha só (Fase 5).
-- Os dois campos de órgãos (orgaos e orgaos_no_ranking) são acrescentados por coletor/gold_serie.py.
-- Origens (views criadas por coletor/gold_serie.py):
--   silver_base        -> as bases do dia
--   silver_base_saude  -> links testados, em observação e quebrados de cada base
--   status_hoje        -> status de cada base no dia (gold/fato_status_base_diario)

WITH status_das_bases AS (
    SELECT
        b.id,
        COALESCE(s.status, 'NAO_VERIFICAVEL') AS status
    FROM silver_base b
    LEFT JOIN status_hoje s ON s.id = b.id
),

links AS (
    SELECT
        COALESCE(sum(h.qtd_links), 0) AS links_total,
        COALESCE(sum(h.qtd_testados), 0) AS links_testados,
        COALESCE(sum(h.qtd_ok), 0) AS links_ok,
        COALESCE(sum(h.qtd_em_observacao), 0) AS links_em_observacao,
        COALESCE(sum(h.qtd_quebrados), 0) AS links_quebrados
    FROM silver_base_saude h
    JOIN silver_base b ON b.id = h.id
)

SELECT
    (SELECT COUNT(*) FROM status_das_bases) AS bases,
    (SELECT COUNT(*) FROM status_das_bases WHERE status = 'EM_DIA') AS em_dia,
    (SELECT COUNT(*) FROM status_das_bases WHERE status = 'ATRASADA') AS atrasada,
    (SELECT COUNT(*) FROM status_das_bases WHERE status = 'PARADA') AS parada,
    (SELECT COUNT(*) FROM status_das_bases WHERE status = 'FORA_DO_AR') AS fora_do_ar,
    (SELECT COUNT(*) FROM status_das_bases WHERE status = 'NAO_VERIFICAVEL') AS nao_verificavel,
    l.links_total,
    l.links_testados,
    l.links_ok,
    l.links_em_observacao,
    l.links_quebrados
FROM links l
