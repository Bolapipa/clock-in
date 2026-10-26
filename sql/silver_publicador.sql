-- Silver: quem publica cada base (decisão 13), uma linha por base.
-- Origens (views criadas por coletor/silver.py):
--   silver_base, silver_recurso -> tabelas da Silver do mesmo dia
--   painel_cronograma           -> cronograma do painel da CGU (bronze/painel_cgu_cronograma)
--   ref_dominios                -> referencia/dominios.csv (nomes e esferas mantidos à mão)
--
-- Cascata: a primeira fonte que responde vence.
--   1. PAINEL_CGU     -> órgão do cronograma da CGU, ligado pelo slug
--   2. ORGANIZACAO    -> campo organizacao do detalhe, quando não é a CGU
--   3. DOMINIO_LINK   -> domínio mais comum dos links da base (sem serviços de hospedagem)
--   4. DOMINIO_EMAIL  -> domínio do e-mail do responsável (sem e-mails pessoais)
--   5. NAO_IDENTIFICADO

WITH
-- Serviços de hospedagem: o link não diz quem publicou
hospedagem AS (
    SELECT unnest([
        'google.com', 'googleusercontent.com', 'amazonaws.com', 'sharepoint.com',
        'powerbi.com', 'windows.net', 'live.com', 'github.com', 'githubusercontent.com',
        'dropbox.com', 'repositorio.dados.gov.br'
    ]) AS dominio
),

-- E-mails pessoais: o domínio não diz qual é o órgão
email_pessoal AS (
    SELECT unnest([
        'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'yahoo.com.br',
        'live.com', 'bol.com.br', 'uol.com.br', 'terra.com.br', 'icloud.com'
    ]) AS dominio
),

-- Fonte 1: cronograma da CGU, ligado pelo slug no fim do link da base
cronograma AS (
    SELECT
        lower(regexp_extract(url_base, '/(?:conjuntos-dados|dataset)/([^/?#]+)', 1)) AS slug,
        -- poucos slugs aparecem com 2 órgãos: min() escolhe sempre o mesmo
        min(Orgao) AS orgao
    FROM painel_cronograma
    -- só linhas com link de base (linhas sem link virariam NULL no join)
    WHERE url_base ~ '/(conjuntos-dados|dataset)/'
    GROUP BY 1
),

-- Fonte 3: domínio de cada link
links AS (
    SELECT
        id_base AS id,
        -- só caracteres válidos de domínio (links malformados ficam com host vazio)
        regexp_extract(lower(link), '^https?://([a-z0-9.-]+)', 1) AS host,
        regexp_extract(lower(link), '^https?://[^/]+/([^/?#]+)', 1) AS trecho
    FROM silver_recurso
),
links_validos AS (
    SELECT l.*
    FROM links l
    WHERE l.host <> ''
      AND NOT EXISTS (
          SELECT 1 FROM hospedagem h
          WHERE l.host = h.dominio OR l.host LIKE '%.' || h.dominio
      )
),
dominio_link AS (
    SELECT
        id,
        -- www.gov.br hospeda vários órgãos: usa também o primeiro trecho do caminho (www.gov.br/inpi)
        mode(CASE WHEN host = 'www.gov.br' AND trecho <> '' THEN 'www.gov.br/' || trecho ELSE host END) AS dominio
    FROM links_validos
    GROUP BY id
),

-- Fonte 4: domínio do e-mail do responsável
dominio_email AS (
    SELECT id, lower(split_part(email_responsavel, '@', 2)) AS dominio
    FROM silver_base
    WHERE email_responsavel LIKE '%@%'
),

-- A cascata: qual fonte responde primeiro
cascata AS (
    SELECT
        b.id,
        b.data_coleta,
        CASE
            WHEN c.orgao IS NOT NULL THEN 'PAINEL_CGU'
            WHEN b.organizacao_detalhe <> 'controladoria-geral-da-uniao' THEN 'ORGANIZACAO'
            WHEN dl.dominio IS NOT NULL THEN 'DOMINIO_LINK'
            WHEN de.dominio IS NOT NULL
                 AND de.dominio NOT IN (SELECT dominio FROM email_pessoal) THEN 'DOMINIO_EMAIL'
            ELSE 'NAO_IDENTIFICADO'
        END AS origem_publicador,
        c.orgao,
        b.organizacao_detalhe,
        dl.dominio AS dominio_link,
        de.dominio AS dominio_email
    FROM silver_base b
    LEFT JOIN cronograma c USING (slug)
    LEFT JOIN dominio_link dl USING (id)
    LEFT JOIN dominio_email de USING (id)
),

-- Evidência: o valor exato que a fonte escolhida forneceu (rastreabilidade)
com_evidencia AS (
    SELECT
        *,
        CASE origem_publicador
            WHEN 'PAINEL_CGU' THEN orgao
            WHEN 'ORGANIZACAO' THEN organizacao_detalhe
            WHEN 'DOMINIO_LINK' THEN dominio_link
            WHEN 'DOMINIO_EMAIL' THEN dominio_email
        END AS evidencia
    FROM cascata
),

-- Tabela de referência: vale a entrada mais específica (o domínio mais longo que bate)
referencia AS (
    SELECT
        e.id,
        arg_max(r.orgao, length(r.dominio))  AS orgao,
        arg_max(r.esfera, length(r.dominio)) AS esfera
    FROM com_evidencia e
    JOIN ref_dominios r
      ON e.origem_publicador IN ('DOMINIO_LINK', 'DOMINIO_EMAIL')
     AND (e.evidencia = r.dominio OR e.evidencia LIKE '%.' || r.dominio)
    GROUP BY e.id
)

SELECT
    e.id,

    -- Nome do publicador: da fonte oficial, da tabela de referência ou o próprio domínio
    CASE
        WHEN e.origem_publicador IN ('PAINEL_CGU', 'ORGANIZACAO') THEN e.evidencia
        ELSE COALESCE(r.orgao, e.evidencia)
    END AS publicador,

    -- Esfera: fontes oficiais só têm órgãos federais; domínios seguem a referência ou o formato
    CASE
        WHEN e.origem_publicador IN ('PAINEL_CGU', 'ORGANIZACAO') THEN 'FEDERAL'
        WHEN e.origem_publicador = 'NAO_IDENTIFICADO' THEN NULL
        WHEN r.esfera IS NOT NULL THEN r.esfera
        -- <algo>.<uf>.gov.br: órgão estadual (prefeituras conhecidas estão na referência)
        WHEN regexp_matches(e.evidencia, '(^|\.)(ac|al|ap|am|ba|ce|df|es|go|ma|mt|ms|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to)\.gov\.br$') THEN 'ESTADUAL'
        -- .gov.br sem UF, Judiciário, Legislativo e Forças Armadas: federal
        WHEN regexp_matches(e.evidencia, '\.(gov|jus|leg|mil)\.br(/|$)') THEN 'FEDERAL'
        -- universidades e institutos federais seguem o padrão uf*, if*, cefet*
        WHEN regexp_matches(e.evidencia, '(^|\.)(uf[a-z]*|unb|unifesp|unifesspa|unifei|unila|unilab|univasf|unipampa|unifap|unir|if[a-z-]+|cefet[a-z-]*|utfpr)\.(edu\.)?br$') THEN 'FEDERAL'
        ELSE 'NAO_CLASSIFICADA'
    END AS esfera,

    e.origem_publicador,
    e.evidencia,
    e.data_coleta
FROM com_evidencia e
LEFT JOIN referencia r USING (id)
ORDER BY e.id