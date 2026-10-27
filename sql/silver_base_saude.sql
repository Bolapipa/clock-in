-- Silver: uma linha por base, com a saúde dos links dos recursos dela.
-- Origens (views criadas por coletor/silver_links.py):
--   silver_base         -> todas as bases do dia
--   silver_recurso      -> os links de cada base
--   silver_link_status  -> situação de cada link testado

-- qtd_testados conta os links com algum teste conclusivo: timeout, falha de conexão e servidor
-- não testado não entram (decisão 29). Os links que ficam de fora são os "não verificados".

-- Links http(s) de cada base, sem repetir o mesmo link dentro da base
WITH links_da_base AS (
    SELECT DISTINCT id_base, link
    FROM silver_recurso
    WHERE regexp_matches(lower(link), '^https?://')
)

SELECT
    b.id,
    COUNT(l.link) AS qtd_links,
    COUNT(s.link) AS qtd_testados,
    COUNT(*) FILTER (WHERE s.falhas_seguidas = 0) AS qtd_ok,
    COUNT(*) FILTER (WHERE s.falhas_seguidas > 0 AND NOT s.quebrado) AS qtd_em_observacao,
    COUNT(*) FILTER (WHERE s.quebrado) AS qtd_quebrados,
    -- Fora do ar: a base tem links e todos estão quebrados (decisão 14)
    COUNT(l.link) > 0 AND COUNT(*) FILTER (WHERE s.quebrado) = COUNT(l.link) AS fora_do_ar,
    b.data_coleta
FROM silver_base b
LEFT JOIN links_da_base l ON l.id_base = b.id
LEFT JOIN silver_link_status s ON s.link = l.link
GROUP BY b.id, b.data_coleta
ORDER BY b.id