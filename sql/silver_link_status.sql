-- Silver: uma linha por link testado, com a situação atual dele.
-- Origens (views criadas por coletor/silver_links.py):
--   link_atual      -> estado de cada link (estado/links_atual)
--   silver_recurso  -> recursos do dia, para manter só os links que ainda existem
-- A variável falhas_para_quebrado vem de links.FALHAS_PARA_QUEBRADO (decisão 14).

SELECT
    a.link,
    a.servidor,
    a.ultima_tentativa,
    a.status_http AS ultimo_status_http,
    a.erro_tipo   AS ultimo_erro_tipo,
    a.falhas_seguidas,
    a.falhas_seguidas >= getvariable('falhas_para_quebrado') AS quebrado,
    CASE
        WHEN a.falhas_seguidas >= getvariable('falhas_para_quebrado') THEN a.falha_desde
    END AS quebrado_desde,
    a.ultimo_sucesso,
    (SELECT max(data_coleta) FROM silver_recurso) AS data_coleta
FROM link_atual a
WHERE EXISTS (SELECT 1 FROM silver_recurso r WHERE r.link = a.link)
ORDER BY a.link