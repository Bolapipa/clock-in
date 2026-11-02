-- Gold: uma linha por acontecimento do dia em cada base (Fase 8).
-- Origens (views criadas por coletor/gold_eventos.py):
--   silver_base         -> título e endereço (slug) de cada base
--   silver_recurso      -> a base de cada link
--   silver_link_status  -> links que passaram a ser considerados quebrados
--   versao_conteudo     -> arquivos lidos no dia e se o conteúdo ou a estrutura mudaram (silver/versao_conteudo)
--   status_hoje         -> status de cada base no dia (gold/fato_status_base_diario)
--   status_anterior     -> último status guardado de cada base, de um dia anterior (estado/status_base)
-- Variável: data_coleta (o dia).
-- Um evento por base e por tipo: uma base com vários links quebrados gera um evento só, com a contagem.

WITH links_da_base AS (
    SELECT DISTINCT id_base, link FROM silver_recurso
),

-- Link que fechou hoje a terceira falha seguida (o dia em que ele passa a ser considerado quebrado, decisão 14)
quebraram AS (
    SELECT
        r.id_base,
        COUNT(DISTINCT s.link) AS qtd,
        min(s.link) AS exemplo
    FROM silver_link_status s
    JOIN links_da_base r ON r.link = s.link
    WHERE s.quebrado
      AND s.falhas_seguidas = 3
      AND CAST(s.ultima_tentativa AS DATE) = getvariable('data_coleta')
    GROUP BY r.id_base
),

-- Arquivos lidos hoje cujo conteúdo ou estrutura mudou em relação à leitura anterior
mudancas AS (
    SELECT
        r.id_base,
        COUNT(DISTINCT v.link) FILTER (WHERE v.mudou_conteudo) AS qtd_conteudo,
        COUNT(DISTINCT v.link) FILTER (WHERE v.mudou_schema) AS qtd_schema
    FROM versao_conteudo v
    JOIN links_da_base r ON r.link = v.link
    GROUP BY r.id_base
),

-- Mudança de status. Quem era "não verificável" não gera evento: no começo, quando o histórico de leituras
-- amadurece, milhares de bases passariam a ter status de uma vez e o aviso deixaria de significar alguma coisa
mudou_status AS (
    SELECT
        h.id AS id_base,
        a.status AS antes,
        h.status AS depois,
        h.motivo
    FROM status_hoje h
    JOIN status_anterior a ON a.id = h.id
    WHERE a.status <> h.status
      AND a.status <> 'NAO_VERIFICAVEL'
),

eventos AS (
    SELECT id_base, 'LINK_QUEBROU' AS tipo_evento,
           CASE WHEN qtd = 1 THEN format('1 link passou a ser considerado quebrado: {}', exemplo)
                ELSE format('{} links passaram a ser considerados quebrados, por exemplo {}', qtd, exemplo)
           END AS detalhe
    FROM quebraram

    UNION ALL
    SELECT id_base, 'CONTEUDO_MUDOU',
           CASE WHEN qtd_conteudo = 1 THEN 'o conteúdo de 1 arquivo mudou'
                ELSE format('o conteúdo de {} arquivos mudou', qtd_conteudo)
           END
    FROM mudancas
    WHERE qtd_conteudo > 0

    UNION ALL
    SELECT id_base, 'SCHEMA_MUDOU',
           CASE WHEN qtd_schema = 1 THEN 'a estrutura (colunas) de 1 arquivo mudou'
                ELSE format('a estrutura (colunas) de {} arquivos mudou', qtd_schema)
           END
    FROM mudancas
    WHERE qtd_schema > 0

    UNION ALL
    SELECT id_base, 'STATUS_MUDOU',
           format('de {} para {}: {}', replace(lower(antes), '_', ' '), replace(lower(depois), '_', ' '), motivo)
    FROM mudou_status
)

SELECT
    getvariable('data_coleta') AS data,
    e.id_base,
    b.slug,
    e.tipo_evento,
    e.detalhe
FROM eventos e
JOIN silver_base b ON b.id = e.id_base
ORDER BY e.id_base, e.tipo_evento
