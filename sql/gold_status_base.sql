-- Gold: uma linha por base por dia, com o status e o motivo em uma frase (Fase 4).
-- Origens (views criadas por coletor/gold_status.py):
--   silver_base        -> periodicidade declarada e como o portal vê a base
--   silver_base_saude  -> links testados e quebrados de cada base
--   silver_recurso     -> links de cada base e se o formato é tabular
--   conteudo_atual     -> estado do conteúdo de cada arquivo (estado/conteudo_atual)
--   ref_periodicidade  -> prazo esperado de cada periodicidade (referencia/periodicidade.csv)
-- Variáveis: data_coleta (o dia) e multiplo_parada (quantas vezes o prazo faz a base ficar "parada").

-- O que se sabe do conteúdo de cada base, juntando os arquivos tabulares dela que já foram lidos
WITH conteudo_da_base AS (
    SELECT
        r.id_base,
        COUNT(*) AS arquivos_lidos,
        -- Última mudança vista em qualquer arquivo da base
        max(c.ultima_mudanca) AS ultima_mudanca_real,
        -- Janela de observação: dias desde a primeira leitura do arquivo visto há menos tempo.
        -- Vale o menor, porque a base só "não mudou" se todos os arquivos foram vistos pelo mesmo período
        min(date_diff('day', c.primeira_leitura, getvariable('data_coleta'))) AS janela_dias,
        COALESCE(bool_or(c.ultima_mudanca_schema = getvariable('data_coleta')), false) AS schema_mudou
    FROM (SELECT DISTINCT id_base, link FROM silver_recurso WHERE formato_tabular) r
    JOIN conteudo_atual c ON c.link = r.link
    WHERE c.ultima_leitura IS NOT NULL
    GROUP BY r.id_base
),

-- Tudo o que a regra de status precisa, uma linha por base
medidas AS (
    SELECT
        b.id,
        b.slug,
        b.periodicidade,
        p.rotulo,
        p.prazo_dias,
        b.status_portal,
        COALESCE(s.qtd_links, 0) AS links_total,
        COALESCE(s.qtd_quebrados, 0) AS links_quebrados,
        COALESCE(s.fora_do_ar, false) AS fora_do_ar,
        COALESCE(c.arquivos_lidos, 0) AS arquivos_lidos,
        c.ultima_mudanca_real,
        c.janela_dias,
        COALESCE(c.schema_mudou, false) AS schema_mudou,
        -- Dias sem mudança: desde a última mudança vista; sem nenhuma mudança vista, vale a janela de observação
        CASE
            WHEN c.ultima_mudanca_real IS NOT NULL THEN date_diff('day', c.ultima_mudanca_real, getvariable('data_coleta'))
            ELSE c.janela_dias
        END AS dias_sem_mudanca
    FROM silver_base b
    LEFT JOIN silver_base_saude s ON s.id = b.id
    LEFT JOIN conteudo_da_base c ON c.id_base = b.id
    LEFT JOIN ref_periodicidade p ON p.periodicidade = b.periodicidade
),

-- Regras de status, da mais forte para a mais fraca (a primeira que vale decide)
classificadas AS (
    SELECT
        *,
        CASE
            WHEN periodicidade IS NULL THEN 'NAO_VERIFICAVEL'
            WHEN fora_do_ar THEN 'FORA_DO_AR'
            WHEN arquivos_lidos = 0 THEN 'NAO_VERIFICAVEL'
            WHEN prazo_dias IS NULL THEN 'NAO_VERIFICAVEL'
            WHEN dias_sem_mudanca > getvariable('multiplo_parada') * prazo_dias THEN 'PARADA'
            WHEN dias_sem_mudanca > prazo_dias THEN 'ATRASADA'
            -- Em dia só com uma mudança vista dentro do prazo; sem mudança vista e janela curta, não dá para dizer
            WHEN ultima_mudanca_real IS NOT NULL THEN 'EM_DIA'
            ELSE 'NAO_VERIFICAVEL'
        END AS status
    FROM medidas
)

SELECT
    getvariable('data_coleta') AS data_coleta,
    id,
    slug,
    status,
    -- Motivo: a frase que explica o status
    CASE
        WHEN status = 'FORA_DO_AR' THEN format('todos os {} links estão quebrados', links_total)
        WHEN status = 'PARADA' AND ultima_mudanca_real IS NOT NULL
            THEN format('parada porque é {} e não muda há {} dias (prazo de {} dias, mais de {}x)',
                        rotulo, dias_sem_mudanca, prazo_dias, getvariable('multiplo_parada'))
        WHEN status = 'PARADA'
            THEN format('parada porque é {} e não mudou em {} dias de leitura (prazo de {} dias, mais de {}x)',
                        rotulo, dias_sem_mudanca, prazo_dias, getvariable('multiplo_parada'))
        WHEN status = 'ATRASADA' AND ultima_mudanca_real IS NOT NULL
            THEN format('atrasada porque é {} e não muda há {} dias (prazo de {} dias)', rotulo, dias_sem_mudanca, prazo_dias)
        WHEN status = 'ATRASADA'
            THEN format('atrasada porque é {} e não mudou em {} dias de leitura (prazo de {} dias)', rotulo, dias_sem_mudanca, prazo_dias)
        WHEN status = 'EM_DIA'
            THEN format('em dia porque é {} e mudou há {} dias (prazo de {} dias)', rotulo, dias_sem_mudanca, prazo_dias)
        WHEN periodicidade IS NULL THEN 'detalhe da base ainda não coletado'
        WHEN arquivos_lidos = 0 THEN 'nenhum arquivo tabular da base foi lido'
        WHEN prazo_dias IS NULL THEN 'sem periodicidade declarada e ainda sem histórico para inferir o ritmo'
        ELSE format('ainda sem mudança vista em {} dias de leitura, menos que o prazo de {} dias', janela_dias, prazo_dias)
    END AS motivo,
    periodicidade,
    prazo_dias AS prazo_esperado_dias,
    CASE WHEN prazo_dias IS NOT NULL THEN 'DECLARADO' END AS origem_prazo,
    ultima_mudanca_real,
    dias_sem_mudanca,
    janela_dias AS janela_observacao_dias,
    links_total,
    links_quebrados,
    schema_mudou,
    status_portal,
    -- Diverge do portal: ele diz "Atualizado" e a base está atrasada ou parada, ou diz "Desatualizado" e está em dia.
    -- Se um dos lados não é verificável, não há como comparar (nulo)
    CASE
        WHEN lower(status_portal) = 'atualizado' AND status IN ('ATRASADA', 'PARADA') THEN true
        WHEN lower(status_portal) = 'desatualizado' AND status = 'EM_DIA' THEN true
        WHEN lower(status_portal) IN ('atualizado', 'desatualizado') AND status IN ('EM_DIA', 'ATRASADA', 'PARADA') THEN false
    END AS diverge_do_portal
FROM classificadas
ORDER BY id
