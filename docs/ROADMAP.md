# Roadmap: guia fase por fase

Cada fase tem:
- **Objetivo:** o que você vai aprender e provar.
- **Tarefas:** o que fazer, na ordem.
- **Entregável:** o que precisa existir no repositório.
- **Pronto quando:** como saber que a fase acabou.
- **Estude:** conceitos e documentação.

> Regra do projeto: você escreve todo o código. Este guia diz **o que** fazer e **onde pesquisar**, não **como** fazer.
> Ao terminar cada fase: commit, atualizar o checklist abaixo e anotar decisões em [DECISOES.md](DECISOES.md).

## Checklist

- [x] Validação (24/10/2026): ver [VALIDACAO.md](VALIDACAO.md)
- [ ] Fase 0: Ambiente
- [ ] Fase 1: Inventário
- [ ] Fase 2: Saúde dos links
- [ ] Fase 3: Conteúdo (hash e schema)
- [ ] Fase 4: Atualização real e status
- [ ] Fase 5: Modelo Gold, histórico e nota por órgão
- [ ] Fase 6: API pública
- [ ] Fase 7: Site público
- [ ] Fase 8: Alertas
- [ ] Fase 9: Lançamento e impacto

Ritmo sugerido: uma fase por semana. As fases 1, 3 e 7 podem levar duas.

---

## Fase 0: Ambiente

**Objetivo:** ter o esqueleto do projeto rodando: Python isolado, PostgreSQL no Docker e uma estrutura de pastas clara.

**Tarefas**
1. Crie um ambiente virtual Python (`python3 -m venv .venv`) e um `requirements.txt` com versões fixadas. Comece pequeno: cliente HTTP (`httpx` ou `requests`), driver do Postgres (`psycopg` 3) e `python-dotenv`.
2. Crie o `docker-compose.yml` com `postgres:17` (versão major fixada), volume nomeado, `healthcheck` com `pg_isready`, `.env` fora do Git e `.env.example` dentro.
3. Crie a estrutura de pastas (sugestão):
   ```text
   clock-in/
   ├── coletor/        # código do motor (Python)
   ├── sql/            # schemas e transformações (bronze, silver, gold)
   ├── api/            # Fase 6
   ├── site/           # Fase 7
   ├── tests/          # pytest
   ├── docs/
   └── validacao/      # pesquisa já feita (não é código do produto)
   ```
4. Crie os schemas `bronze`, `silver` e `gold` no Postgres.
5. Escreva um `Makefile` ou scripts simples para os comandos do dia a dia (subir banco, rodar coletor, rodar testes).
6. Seção "Como rodar" no README.

**Entregável:** `docker-compose.yml`, `.env.example`, `requirements.txt`, estrutura de pastas, schemas criados.

**Pronto quando:** `docker compose up -d` sobe o banco `healthy`, o ambiente virtual instala sem erro e `psql` mostra os três schemas.

**Estude:** `venv` (https://docs.python.org/3/library/venv.html), Docker Compose, schemas no PostgreSQL (https://www.postgresql.org/docs/current/ddl-schemas.html).

---

## Fase 1: Inventário

**Objetivo:** saber quais bases existem, com periodicidade declarada, links e publicador real. É o primeiro pedaço do motor.

**Tarefas**
1. Leia [API_DADOS_GOV.md](API_DADOS_GOV.md). Decida como acessar o catálogo:
   - tentar a **API oficial com chave** (preferível, se funcionar);
   - ou a API pública do site (exige sessão de navegador, por exemplo com Playwright).
   Registre a escolha e o porquê em [DECISOES.md](DECISOES.md).
2. Escreva o coletor do catálogo: percorre a listagem paginada e, para cada base, busca o detalhe (recursos, periodicidade, responsável).
3. Grave a **resposta crua** na Bronze (por exemplo, uma tabela com `coletado_em`, `slug`, `payload jsonb`). Nunca transforme antes de guardar.
4. Na Silver, crie as tabelas padronizadas: `base` (uma linha por base) e `recurso` (uma linha por link). Normalize a periodicidade ("Anual", "ANUAL" viram `ANUAL`).
5. **Publicador real:** o campo de órgão do portal atribui 95% das bases à CGU. Investigue `maintainer`, `maintainer_email`, domínio dos links e a base do painel da CGU para descobrir quem publica cada base. Documente a regra.
6. Baixe a base do painel da CGU e cruze com o inventário (quais bases do painel não estão no portal e vice-versa).
7. Torne a coleta **incremental e idempotente**: rodar duas vezes no mesmo dia não duplica nada.
8. Coleta educada: pausas, `User-Agent` com contato, repetição com espera em falhas.

**Entregável:** coletor do catálogo, tabelas Bronze e Silver, regra do publicador real documentada.

**Pronto quando:** um comando coleta o catálogo inteiro (cerca de 19.600 bases) e a Silver tem uma linha por base e por recurso, com periodicidade normalizada e publicador real preenchido para a maioria.

**Estude:** paginação de APIs, `jsonb` no PostgreSQL (https://www.postgresql.org/docs/current/datatype-json.html), idempotência e `INSERT ... ON CONFLICT` (https://www.postgresql.org/docs/current/sql-insert.html), Playwright (https://playwright.dev/python/), boas práticas de web scraping (robots.txt, rate limit).

---

## Fase 2: Saúde dos links

**Objetivo:** saber, todo dia, quais links funcionam e desde quando estão quebrados.

**Tarefas**
1. Para cada recurso, faça `HEAD`; se o servidor recusar (403, 405, 501), use `GET` com `Range: bytes=0-2047`. Timeout curto (por exemplo, 20 s).
2. Registre por tentativa: status HTTP, URL final (redirecionamentos), tipo, tamanho, `Last-Modified`, `ETag`, tempo de resposta e tipo de erro (DNS, SSL, timeout).
3. **Uma requisição por vez por servidor**, com pausa. Agrupe os links por domínio para não sobrecarregar um órgão.
4. Defina a regra de "fora do ar": erros 502, 503 e 520 podem ser temporários. Por exemplo, só considerar quebrado após 3 falhas em dias diferentes.
5. Use concorrência entre domínios diferentes (asyncio ou threads) para a coleta caber no dia.
6. Agende a execução diária (GitHub Actions com `schedule`, ou cron local no começo).

**Entregável:** tabela de tentativas por link, regra de "fora do ar" documentada, execução agendada.

**Pronto quando:** você consegue responder "quais links estão quebrados hoje e desde quando" com uma consulta SQL.

**Estude:** códigos HTTP (https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Status), `HEAD` e `Range`, `asyncio` e `httpx` assíncrono (https://www.python-httpx.org/async/), GitHub Actions `schedule` (https://docs.github.com/actions/using-workflows/events-that-trigger-workflows#schedule).

---

## Fase 3: Conteúdo (hash e schema)

**Objetivo:** medir a verdade pelo conteúdo: o arquivo mudou? as colunas mudaram?

**Tarefas**
1. Para arquivos tabulares (CSV, XLSX, JSON), baixe o arquivo (ou uma parte, se for muito grande; defina um limite) e calcule um **hash** (SHA-256).
2. Compare com o hash da coleta anterior: mudou ou não mudou.
3. Leia o **schema**: nomes das colunas, ordem e tipos inferidos. Atenção a encoding (UTF-8, Latin-1) e separador (`,` ou `;`), comuns em dados do governo.
4. Gere o **diff de schema** entre coletas: colunas adicionadas, removidas, renomeadas (heurística), tipo alterado.
5. Procure colunas de data dentro do arquivo e guarde a **data mais recente do conteúdo**.
6. Guarde só o necessário (hash, schema, data máxima, tamanho), não os arquivos inteiros.

**Entregável:** tabelas de versões de conteúdo e de mudanças de schema.

**Pronto quando:** você consegue dizer "a base X mudou de conteúdo em tal dia" e "a base Y perdeu a coluna Z em tal dia".

**Estude:** `hashlib` (https://docs.python.org/3/library/hashlib.html), leitura de CSV com detecção de encoding e separador (`csv.Sniffer`), schema drift, `pyarrow` ou `polars` para inferir tipos.

---

## Fase 4: Atualização real e status

**Objetivo:** dar a cada base um status justo: em dia, atrasada, parada, fora do ar ou não verificável.

**Tarefas**
1. **Prazo esperado** de cada base:
   - se declara periodicidade, use-a com uma folga (por exemplo, mensal = 40 dias);
   - se não declara (69% dos casos), **infira o ritmo** pelo histórico de mudanças de hash (mediana dos intervalos). Com pouco histórico, marque como "não verificável" até ter dados suficientes.
2. **Última mudança real:** a data em que o hash mudou ou a data máxima do conteúdo, a que for mais confiável. `Last-Modified` só como pista.
3. Regras de status (defina e documente):
   - Em dia: mudou dentro do prazo;
   - Atrasada: passou do prazo;
   - Parada: passou de, por exemplo, 3x o prazo;
   - Fora do ar: nenhum link funciona (pela regra da Fase 2);
   - Não verificável: só página HTML, sem arquivo, ou histórico insuficiente.
4. Compare o seu status com o selo do portal e guarde a divergência (é material para posts e para provar o valor do projeto).
5. Testes automatizados para as regras de status, com casos inventados (pytest).

**Entregável:** tabela de status diário por base, regras documentadas em [DECISOES.md](DECISOES.md), testes.

**Pronto quando:** cada base tem um status explicável ("atrasada porque é mensal e não muda há 73 dias").

**Estude:** séries temporais simples (intervalos, mediana), `pytest` (https://docs.pytest.org), artigo da WU Viena sobre medidas de atualização em portais abertos (ver [PESQUISA.md](PESQUISA.md)).

---

## Fase 5: Modelo Gold, histórico e nota por órgão

**Objetivo:** transformar os dados em algo que responde perguntas: como está o Brasil, cada órgão e cada base ao longo do tempo.

**Tarefas**
1. Modele a Gold: fatos diários de status por base e dimensões de base, órgão (publicador real) e data.
2. **Nota por órgão**: defina uma fórmula simples e transparente (por exemplo, % de bases em dia, com peso menor para "não verificável"). Inspire-se na nota de Toronto e no MQA da União Europeia. Publique a fórmula.
3. Visão geral do Brasil: totais por status e evolução diária.
4. Linha do tempo por base: mudanças de conteúdo, de schema e de status.
5. Importe o censo de [validacao/resultados](../validacao/resultados) como ponto de partida histórico, se fizer sentido.

**Entregável:** tabelas ou views Gold, fórmula da nota documentada.

**Pronto quando:** três consultas respondem: "como está o Brasil hoje", "como está o órgão X" e "o que aconteceu com a base Y".

**Estude:** modelagem dimensional (fatos e dimensões), views e materialized views no PostgreSQL, como comunicar métricas de forma justa.

---

## Fase 6: API pública (só leitura)

**Objetivo:** expor os resultados para o site e para quem quiser integrar.

**Tarefas**
1. Escolha o framework (sugestão: FastAPI) e registre em [DECISOES.md](DECISOES.md).
2. Endpoints mínimos:
   - `GET /bases/{slug}`: status atual e histórico;
   - `GET /orgaos/{id}`: nota e bases;
   - `GET /resumo`: visão geral do Brasil;
   - `GET /ranking`: órgãos ordenados pela nota.
3. Paginação, filtros simples, documentação automática (OpenAPI).
4. Usuário do banco **somente leitura** para a API.
5. Cache e limite de requisições.
6. Testes da API.

**Entregável:** API rodando localmente, documentação OpenAPI, testes.

**Pronto quando:** um engenheiro consegue consultar `GET /bases/{slug}` e decidir se roda o pipeline dele.

**Estude:** FastAPI (https://fastapi.tiangolo.com), OpenAPI, roles e `GRANT` no PostgreSQL, cache HTTP.

---

## Fase 7: Site público

**Objetivo:** qualquer pessoa entende em 10 segundos se uma base é confiável.

**Tarefas**
1. Páginas: início (visão geral do Brasil), base, órgão, ranking, metodologia ("como medimos").
2. O site consome a sua API (não acessa o banco direto).
3. Simples primeiro: HTML, CSS e JavaScript, como o seu portfólio. Hospedagem na Vercel.
4. Linguagem clara: explicar cada status em uma frase; separar "não verificável" de "desatualizado".
5. Acessível e bom no celular.
6. Página de metodologia com as regras de status e a fórmula da nota.

**Entregável:** site publicado.

**Pronto quando:** você mostra a página de uma base para alguém que não é da área e a pessoa entende o status sem explicação.

**Estude:** design de dashboards públicos, acessibilidade básica (contraste, foco de teclado), deploy na Vercel.

---

## Fase 8: Alertas

**Objetivo:** levar o Clock-in para o dia a dia de quem depende de dados públicos.

**Tarefas**
1. **RSS** por base e por órgão (mais simples, sem cadastro).
2. **Webhook** (Slack, Teams, Discord) por base seguida.
3. **E-mail** com confirmação de cadastro e descadastro fácil (cuidado com a LGPD: guardar só o necessário).
4. Gatilhos: mudou de status, mudou de schema, link quebrou, voltou a funcionar.
5. Evitar alerta duplicado e alerta de falso positivo (usar a regra de 3 falhas).

**Entregável:** RSS, webhook e e-mail funcionando.

**Pronto quando:** você segue uma base e recebe um aviso no mesmo dia em que ela muda de formato.

**Estude:** RSS/Atom, webhooks, envio de e-mail transacional, LGPD para cadastros simples.

---

## Fase 9: Lançamento e impacto

**Objetivo:** fazer o projeto ser usado e gerar a diferença que motivou tudo.

**Tarefas**
1. Primeiro post no LinkedIn com os números da validação (com as ressalvas).
2. Relatório mensal público: "os dados abertos do Brasil em [mês]".
3. Conversar com quem pode usar ou divulgar: Open Knowledge Brasil, Base dos Dados, redações de jornalismo de dados, a própria CGU.
4. Abrir o código (repositório público), licença e guia de contribuição.
5. Coletar feedback e priorizar: portais estaduais e municipais? biblioteca Python? extensão de navegador?

**Entregável:** post publicado, relatório, repositório público.

**Pronto quando:** pelo menos uma pessoa de fora usa o Clock-in no trabalho dela.
