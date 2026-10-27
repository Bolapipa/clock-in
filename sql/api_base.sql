-- API: uma linha por base, com o órgão publicador e a saúde dos links (protótipo da Fase 6).
-- Origens (views criadas por publicar/gerar_api.py):
--   silver_base        -> título e periodicidade de cada base
--   silver_publicador  -> órgão publicador real e esfera
--   silver_base_saude  -> links testados, em observação e quebrados
--   status_base        -> status da base (Gold); vazia enquanto o status não foi gerado

SELECT
    b.id,
    b.slug,
    b.titulo,
    COALESCE(b.periodicidade, 'SEM_DETALHE') AS periodicidade,
    COALESCE(p.publicador, 'Não identificado') AS publicador,
    COALESCE(p.esfera, 'NAO_CLASSIFICADA') AS esfera,
    COALESCE(s.qtd_links, 0) AS links_total,
    COALESCE(s.qtd_testados, 0) AS links_testados,
    COALESCE(s.qtd_ok, 0) AS links_ok,
    COALESCE(s.qtd_em_observacao, 0) AS links_em_observacao,
    COALESCE(s.qtd_quebrados, 0) AS links_quebrados,
    COALESCE(s.fora_do_ar, false) AS fora_do_ar,
    COALESCE(g.status, 'NAO_VERIFICAVEL') AS status,
    g.motivo
FROM silver_base b
LEFT JOIN silver_publicador p ON p.id = b.id
LEFT JOIN silver_base_saude s ON s.id = b.id
LEFT JOIN status_base g ON g.id = b.id
ORDER BY b.id
