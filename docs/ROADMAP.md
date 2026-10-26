# Roadmap: guia fase por fase

Cada fase tem:
- **Objetivo:** o que você vai aprender e provar.
- **Tarefas:** o que fazer, na ordem.
- **Entregável:** o que precisa existir no repositório.
- **Pronto quando:** como saber que a fase acabou.
- **Estude:** conceitos e documentação.

> Este guia diz **o que** fazer em cada fase e **onde pesquisar**.
> Ao terminar cada fase: commit, atualizar o checklist abaixo e anotar decisões em [DECISOES.md](DECISOES.md).
> Modelo de dados, tabelas por camada e regras de status: [ARQUITETURA.md](ARQUITETURA.md).

## Princípio: custo zero

O Clock-in deve ser **gratuito para quem constrói e para quem usa**. Toda escolha técnica passa por esta pergunta: "isso continua de graça quando rodar todo dia, para sempre?"

| Peça | Escolha | Por quê |
|---|---|---|
| Desenvolvimento | Python + DuckDB, sem servidor de banco | Nada para instalar além do Python |
| Armazenamento | Arquivos Parquet (Bronze, Silver, Gold) | Compactos, rápidos, cabem no GitHub |
| Motor diário | GitHub Actions agendado | Grátis e sem limite de minutos em **repositório público** |
| Histórico | Parquet por mês em arquivos de release do GitHub | Até 2 GB por arquivo, sem custo |
| API | API estática: arquivos JSON gerados pelo motor | Sem servidor, sem custo, rápida |
| Site | Estático na Vercel (plano Hobby, uso não comercial) | Grátis |
| Alertas | RSS e webhook primeiro; e-mail por último | RSS é um arquivo estático; e-mail depende de serviço externo |

**Consequência:** o repositório precisa ser **público** a partir da Fase 2, quando o motor passa a rodar todo dia. Em repositório privado, a cota grátis do GitHub Actions acaba rápido.

**Limites a respeitar** (confira na documentação oficial antes de cada fase, porque mudam):
- Git: 100 MB por arquivo; repositório idealmente abaixo de 1 GB. Não versionar o histórico inteiro no Git.
- GitHub Actions: tempo máximo por job (verificar na documentação de limites). Se a coleta não couber, dividir em jobs por lote.
- Vercel Hobby: só uso não comercial; tráfego mensal limitado.

## Checklist

- [x] Validação (24/10/2026): ver [VALIDACAO.md](VALIDACAO.md)
- [x] Fase 0: Ambiente
- [x] Fase 1: Inventário (26/10/2026)
- [ ] Fase 2: Saúde dos links e motor diário
- [ ] Fase 3: Conteúdo (hash e schema)
- [ ] Fase 4: Atualização real e status
- [ ] Fase 5: Gold, histórico e nota por órgão
- [ ] Fase 6: API estática
- [ ] Fase 7: Site público
- [ ] Fase 8: Alertas
- [ ] Fase 9: Lançamento e impacto

Ritmo sugerido: uma fase por semana. As fases 1, 3 e 7 podem levar duas.

---

## Fase 0: Ambiente

**Objetivo:** ter o esqueleto do projeto rodando no seu computador, sem custo e sem servidor.

**Tarefas**
1. Crie um ambiente virtual Python (`python -m venv .venv`) e um `requirements.txt` com versões fixadas. Comece pequeno: `duckdb`, um cliente HTTP (`httpx` ou `requests`) e `pytest`.
2. Crie a estrutura de pastas (sugestão):
   ```text
   clock-in/
   ├── coletor/        # código do motor (Python)
   ├── sql/            # transformações (bronze -> silver -> gold)
   ├── dados/          # Parquet gerado localmente (fora do Git)
   ├── publicar/       # gera os JSON da API estática (Fase 6)
   ├── site/           # Fase 7
   ├── tests/          # pytest
   ├── docs/
   └── validacao/      # pesquisa já feita (não é código do produto)
   ```
3. Coloque `dados/` e `.venv/` no `.gitignore`.
4. Faça um primeiro teste com DuckDB: abrir o arquivo [`validacao/resultados/censo-2026-10-24.csv`](../validacao/resultados/censo-2026-10-24.csv), contar as bases por `portal_diz_atualizado` e gravar o resultado em Parquet dentro de `dados/`.
5. Escreva um `Makefile` ou scripts simples para os comandos do dia a dia (rodar coletor, rodar testes). (Substituída pela seção "Como rodar" do README; decisão 20.)
6. Seção "Como rodar" no README.

**Entregável:** `requirements.txt`, estrutura de pastas, `.gitignore` atualizado, primeiro script lendo CSV e gravando Parquet com DuckDB.

**Pronto quando:** em um computador novo, `python -m venv .venv`, instalar o `requirements.txt` e rodar o script de teste funciona sem erro.

**Estude:** `venv` (https://docs.python.org/3/library/venv.html), DuckDB com Python (https://duckdb.org/docs/api/python/overview), Parquet com DuckDB (https://duckdb.org/docs/data/parquet/overview).

**Concluída em 25/10/2026.** O que foi feito:
- Python 3.12, `requirements.txt` com todas as versões fixadas (`duckdb` 2.0.0, `httpx` 0.28.1, `pytest` 9.1.1 e dependências). Decisão 19.
- Pastas criadas; as vazias têm `.gitkeep` para entrarem no Git. `.gitignore` corrigido de `data/` para `dados/`.
- `coletor/teste_duckdb.py`: lê o censo, conta por `portal_diz_atualizado` (319 `true`, 19.283 `false`, iguais ao [VALIDACAO.md](VALIDACAO.md)) e grava `dados/teste/contagem.parquet`.
- Tarefa 5 (atalhos) adiada: os comandos estão na seção "Como rodar" do README. Decisão 20.
- Teste do "computador novo" feito: venv apagado, recriado e script rodando sem erro.

---

## Fase 1: Inventário

**Objetivo:** saber quais bases existem, com periodicidade declarada, links e publicador real. É o primeiro pedaço do motor.

**Tarefas**
1. Leia [API_DADOS_GOV.md](API_DADOS_GOV.md). Confirme a decisão 12 (provisória) com um teste:
   - tentar a **API oficial com chave** (preferível, se funcionar, for gratuita e trouxer `resources`, `periodiciade` e `maintainer`);
   - senão, a API pública do site (exige sessão de navegador, por exemplo com Playwright).
   Atualize a decisão 12 em [DECISOES.md](DECISOES.md) com o resultado.
   **Feito em 25/10/2026:** API oficial com chave confirmada (`coletor/teste_api_oficial.py`). O teste revelou que o detalhe de todas as bases leva cerca de 9,3 horas: ver decisão 21.
2. Escreva o coletor do catálogo: percorre a listagem paginada e, para cada base, busca o detalhe (recursos, periodicidade, responsável).
   **Listagem feita em 25/10/2026:** `coletor/catalogo_lista.py` grava a resposta crua de cada página em `dados/bronze/catalogo_lista/data=AAAA-MM-DD/`, com novas tentativas em falhas (backoff de 10 s e 20 s) e idempotência. Testes em `tests/test_catalogo_lista.py` (5 testes, API simulada). **Detalhe:** `coletor/catalogo_detalhe.py` segue a decisão 21 (carga inicial com `--completo`; depois, incremental por `ultimaAlteracaoMetadados` + rodízio de 1/30 do catálogo por dia). Grava em partes de 500 bases e retoma uma execução interrompida sem repetir o que já deu certo. O código comum da API (chave, cliente, novas tentativas) fica em `coletor/portal.py`. Testes em `tests/test_catalogo_detalhe.py`.
   **Primeira listagem completa (25/10/2026):** 1.307 páginas, 19.596 bases sem duplicatas, 40 minutos. Contra o censo de 24/10: 3 bases novas e 9 que saíram.
   **Carga inicial do detalhe (25 e 26/10/2026):** 19.596 bases em 9 horas; 19.045 com sucesso e 551 (2,8%) com `HTTP 400` e a mensagem do próprio portal `{"Erro na API":"Erro ao executar a consulta"}`. As que falham são bases atribuídas à CGU com nome numérico (por exemplo, `2096727068`). Como contam como "nova" até dar certo, o coletor tenta de novo todo dia: avaliar uma espera maior para elas.
3. Grave a **resposta crua** na Bronze: Parquet particionado por data de coleta (`dados/bronze/catalogo/data=AAAA-MM-DD/`). Nunca transforme antes de guardar.
4. Na Silver, gere as tabelas padronizadas: `base` (uma linha por base) e `recurso` (uma linha por link). Normalize a periodicidade ("Anual", "ANUAL" viram `ANUAL`).
   **Feito em 25/10/2026:** `coletor/silver.py` roda `sql/silver_base.sql` e `sql/silver_recurso.sql` e grava em `dados/silver/{base,recurso}/data=AAAA-MM-DD/`. Datas em texto brasileiro viram data; "Indisponível" vira nulo (5.709 bases, o mesmo número do censo). A API oficial já entrega a periodicidade padronizada; vazia vira `NAO_DECLARADA`. Testes em `tests/test_silver.py`. Observação: há erros de digitação no formato dos recursos (por exemplo, `CVS`), a tratar na Fase 3.
   **Silver completa (26/10/2026):** 19.596 bases, 19.045 com detalhe. Periodicidade: 13.431 não declaram (70% das bases com detalhe, o mesmo que a validação estimou), seguidas de `ANUAL` 2.077 e `MENSAL` 1.534. 127 descontinuadas. 126.168 recursos em 19.026 bases; 536 sem link e 2.094 sem formato informado. Formatos mais comuns: CSV 50.172, JSON 22.573, PDF 14.807.
5. **Publicador real:** o campo de órgão do portal atribui 95% das bases à CGU. Investigue `maintainer`, `maintainer_email`, domínio dos links e a base do painel da CGU para descobrir quem publica cada base. Documente a regra.
   **Análise parcial (26/10/2026, 7.314 bases com detalhe):**
   - Cronograma da CGU (`url_base` termina no `slug`): identifica 1.790 bases (24%).
   - Campo `organizacao` do detalhe, quando não é a CGU: acrescenta 149. Juntas, as duas fontes oficiais cobrem 1.939 (27%).
   - As outras 5.375 (73%) vieram todas por **harvest** (importadas de outros catálogos). Só 1.899 têm e-mail do responsável. Os links usam 262 domínios, e os 30 maiores cobrem 4.511 delas (84%).
   - Achado: o harvest traz bases de **governos estaduais e municipais** (por exemplo `dadosabertos.rj.gov.br`, `dados.fortaleza.ce.gov.br`, `ckan.pbh.gov.br`, `dados.al.gov.br`), não só federais. O ranking precisa da coluna `esfera` (federal, estadual, municipal).
   - Implicação: uma pequena tabela de referência, versionada no repositório, ligando cada domínio ao órgão e à esfera resolve a maior parte. `www.gov.br` precisa olhar também o primeiro trecho do caminho (`www.gov.br/<orgao>/...`).
   - Armadilha encontrada: o cronograma tem linhas sem link. Em SQL, `NOT IN` com uma lista que contém `NULL` nunca é verdadeiro; filtrar os nulos antes.
   **Feito em 26/10/2026 (catálogo completo):** `sql/silver_publicador.sql` gera `silver/publicador` com a cascata da decisão 13 (revisada) e `referencia/dominios.csv`. Resultado em 19.596 bases: domínio do link 13.613, cronograma da CGU 4.752, campo `organizacao` 355, e-mail 125, não identificado 751. Publicador identificado em **96,2%**. Esfera: federal 15.970, estadual 1.764, municipal 1.010, não classificada 101. Testes em `tests/test_silver_publicador.py`. Limitação: prefeituras com domínio `<cidade>.<uf>.gov.br` que não estão na referência aparecem como estaduais (poucos casos).
6. Baixe a base do painel da CGU e cruze com o inventário.
   **Download feito em 25/10/2026:** `coletor/painel_cgu.py` pega os links no catálogo (base `painel-de-monitoramento-de-dados-abertos`) e baixa os 2 CSVs do SharePoint da CGU acrescentando `download=1` ao link, sem enviar a chave da API para fora do dados.gov.br. Grava na Bronze o cronograma (9.956 bases previstas, 7.216 com link para o dados.gov.br) e o monitoramento (256 órgãos). Testes em `tests/test_painel_cgu.py`. O cruzamento com o inventário entra na tarefa 5: o `url_base` do cronograma termina no `slug` da base. Achados: a própria base do painel aparece no catálogo com data de atualização "Indisponível"; o campo `situacao_pda` mistura "Sem PDA" e "SEM PDA".
7. Torne a coleta **idempotente**: rodar duas vezes no mesmo dia sobrescreve a partição do dia, sem duplicar.
8. Coleta educada: pausas, `User-Agent` com contato, repetição com espera em falhas.

**Entregável:** coletor do catálogo, Bronze e Silver em Parquet, regra do publicador real documentada.

**Pronto quando:** um comando coleta o catálogo inteiro (cerca de 19.600 bases) e a Silver tem uma linha por base e por recurso, com periodicidade normalizada e publicador real preenchido para a maioria.

**Estude:** paginação de APIs, particionamento estilo Hive em Parquet, idempotência em pipelines, boas práticas de coleta (robots.txt, rate limit). (Playwright não foi necessário: a API oficial com chave funcionou.)

---

## Fase 2: Saúde dos links e motor diário

**Objetivo:** saber, todo dia, quais links funcionam e desde quando estão quebrados, com o motor rodando sozinho e de graça.

**Já corrigido no review de 26/10/2026:** o publicador mudava entre execuções (empate no `mode()` em 3.376 bases; agora o desempate é fixo e há teste de repetição); `periodicidade_comparavel` ficava nula em vez de falsa para as bases sem periodicidade; domínio do e-mail com dois endereços; links do próprio portal usados como publicador; `TRY_CAST` nos campos booleanos; Python 3.12 registrado no `pyproject.toml`.

**Etapa A, feita em 26/10/2026 (pendências 1, 4 e 5):** `coletor/estado.py` mantém `dados/estado/detalhe_atual.parquet`; o coletor do detalhe e a Silver passaram a ler dele. Rodízio pelas coletas mais antigas, espera crescente para bases que falham, parada após 20 falhas seguidas do servidor, partes numeradas pelo maior número e gravadas via arquivo temporário. Testes em `tests/test_estado.py` e `tests/test_catalogo_detalhe.py` (44 no total). Validado com os dados reais: estado de 36 MB, seleção do dia seguinte com 1.205 bases (cerca de 34 minutos) e Silver idêntica à anterior.

**Etapa B, feita em 26/10/2026 (pendência 2):** `portal.data_de_hoje()` calcula a data no fuso `America/Sao_Paulo` (pacote `tzdata`, necessário no Windows); todos os scripts aceitam `--data`; `coletor/motor.py` roda listagem, painel, detalhe e Silver em ordem, com a mesma data, para no primeiro passo obrigatório que falhar e permite retomar com `--desde`. Testes em `tests/test_motor.py` (50 no total).

**Antes de começar: pendências do review de 26/10/2026**
1. **Estado do detalhe no GitHub Actions:** a coleta incremental e a Silver leem todo o histórico de `bronze/catalogo_detalhe`, mas o release `estado-atual` (decisão 16) não o guarda. Sem isso, a primeira execução na nuvem trataria as 19.596 bases como novas (9 horas). Guardar um "detalhe atual" compacto (última versão bem-sucedida de cada base) no estado e fazer o coletor e a Silver lerem dele.
2. **Data de referência única:** os scripts chamam `date.today()` separadamente, e o runner usa UTC. Calcular uma data só (fuso `America/Sao_Paulo`) num orquestrador e passá-la com `--data` a todos os scripts.
3. **Listagem robusta:** não aceitar uma listagem menor que a do dia anterior (por exemplo, abaixo de 95%), tratar corpo que não é JSON e não deixar um teste com `--max-paginas` sobrescrever a listagem completa do dia.
4. **Detalhe robusto:** parar depois de N falhas seguidas (portal fora do ar), tentar de novo as bases com erro 400 permanente só depois de alguns dias, numerar as partes pelo maior número existente e gravar em arquivo temporário antes de renomear.
5. **Rodízio:** trocar `hash(id) % 30` pela escolha das bases com a última coleta mais antiga, que garante a revisão mensal mesmo com dias sem execução.

**Tarefas**
1. Para cada recurso, faça `HEAD`; se o servidor recusar (403, 405, 501), use `GET` com `Range: bytes=0-2047`. Timeout curto (por exemplo, 20 s).
2. Registre por tentativa: status HTTP, URL final, tipo, tamanho, `Last-Modified`, `ETag`, tempo de resposta e tipo de erro (DNS, SSL, timeout).
3. **Uma requisição por vez por servidor**, com pausa. Agrupe os links por domínio para não sobrecarregar um órgão.
4. Concorrência entre domínios diferentes (asyncio) para a coleta caber no tempo do job.
5. Regra de "fora do ar": erros 502, 503 e 520 podem ser temporários. Por exemplo, só considerar quebrado após 3 falhas em dias diferentes.
6. **Motor diário no GitHub Actions:**
   - torne o repositório **público** (ver princípio de custo zero). **Feito em 26/10/2026**, com licença MIT;
   - workflow com `schedule` (cron) que roda o coletor;
   - como o Actions começa sempre do zero, o estado precisa ser baixado no início e enviado no fim: estado atual no release `estado-atual` (sobrescrito todo dia) e histórico no release `historico-AAAA-MM`. Nenhum dado gerado é commitado no Git (decisão 16, detalhes em [ARQUITETURA.md](ARQUITETURA.md#onde-os-dados-ficam));
   - meça quanto tempo a coleta leva e, se precisar, divida em lotes.

**Entregável:** tabela de tentativas por link, regra de "fora do ar" documentada, workflow diário funcionando.

**Pronto quando:** o workflow roda sozinho todos os dias e você consegue responder "quais links estão quebrados hoje e desde quando" com uma consulta DuckDB.

**Estude:** códigos HTTP (https://developer.mozilla.org/pt-BR/docs/Web/HTTP/Status), `httpx` assíncrono (https://www.python-httpx.org/async/), GitHub Actions `schedule` (https://docs.github.com/actions/using-workflows/events-that-trigger-workflows#schedule), limites do GitHub Actions (https://docs.github.com/actions/administering-github-actions/usage-limits-billing-and-administration), releases pela CLI (`gh release upload`).

---

## Fase 3: Conteúdo (hash e schema)

**Objetivo:** medir a verdade pelo conteúdo: o arquivo mudou? as colunas mudaram?

**Tarefas**
1. Para arquivos tabulares (CSV, XLSX, JSON), baixe o arquivo (ou uma parte, se for muito grande; defina um limite) e calcule um **hash** (SHA-256).
2. Compare com o hash da coleta anterior: mudou ou não mudou.
3. Leia o **schema**: nomes das colunas, ordem e tipos inferidos. Atenção a encoding (UTF-8, Latin-1) e separador (`,` ou `;`), comuns em dados do governo. O DuckDB detecta muito disso sozinho.
4. Gere o **diff de schema** entre coletas: colunas adicionadas, removidas, renomeadas (heurística), tipo alterado.
5. Procure colunas de data dentro do arquivo e guarde a **data mais recente do conteúdo**.
6. Guarde só o necessário (hash, schema, data máxima, tamanho), não os arquivos inteiros: é o que mantém o projeto dentro dos limites gratuitos.

**Entregável:** tabelas de versões de conteúdo e de mudanças de schema.

**Pronto quando:** você consegue dizer "a base X mudou de conteúdo em tal dia" e "a base Y perdeu a coluna Z em tal dia".

**Estude:** `hashlib` (https://docs.python.org/3/library/hashlib.html), leitura de CSV no DuckDB com detecção automática (https://duckdb.org/docs/data/csv/auto_detection), schema drift.

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
4. Compare o seu status com o selo do portal e guarde a divergência (material para posts e prova do valor do projeto).
5. Testes automatizados para as regras de status, com casos inventados (pytest).

**Entregável:** status diário por base, regras documentadas em [DECISOES.md](DECISOES.md), testes.

**Pronto quando:** cada base tem um status explicável ("atrasada porque é mensal e não muda há 73 dias").

**Estude:** séries temporais simples (intervalos, mediana), window functions no DuckDB, `pytest` (https://docs.pytest.org), artigo da WU Viena sobre medidas de atualização em portais abertos (ver [PESQUISA.md](PESQUISA.md)).

---

## Fase 5: Gold, histórico e nota por órgão

**Objetivo:** transformar os dados em algo que responde perguntas: como está o Brasil, cada órgão e cada base ao longo do tempo.

**Tarefas**
1. Modele a Gold: fatos diários de status por base e dimensões de base, órgão (publicador real) e data.
2. **Nota por órgão**: fórmula simples e transparente (por exemplo, % de bases em dia, com peso menor para "não verificável"). Inspire-se na nota de Toronto e no MQA da União Europeia. Publique a fórmula.
3. Visão geral do Brasil: totais por status e evolução diária.
4. Linha do tempo por base: mudanças de conteúdo, de schema e de status.
5. Importe o censo de [validacao/resultados](../validacao/resultados) como ponto de partida histórico, se fizer sentido.

**Entregável:** tabelas Gold em Parquet, fórmula da nota documentada.

**Pronto quando:** três consultas respondem: "como está o Brasil hoje", "como está o órgão X" e "o que aconteceu com a base Y".

**Estude:** modelagem dimensional (fatos e dimensões), como comunicar métricas de forma justa.

---

## Fase 6: API estática

**Objetivo:** expor os resultados para o site e para quem quiser integrar, sem servidor e sem custo.

**Tarefas**
1. Ao fim de cada execução diária, o motor gera arquivos JSON a partir da Gold:
   - `api/resumo.json`: visão geral do Brasil;
   - `api/ranking.json`: órgãos ordenados pela nota;
   - `api/orgaos/{id}.json`: nota e bases de um órgão;
   - `api/bases/{slug}.json`: status atual e histórico de uma base.
2. Defina e documente o formato de cada arquivo (um "contrato"), com versão (`"versao": 1`), para não quebrar quem usar.
3. Publique os JSON junto com o site (Vercel). Quem quiser integrar faz um `GET` simples, como em qualquer API.
4. Escreva testes que validam os JSON gerados contra o contrato.
5. Documente a API numa página do site.

**Entregável:** geração dos JSON no workflow diário, contrato documentado, testes.

**Pronto quando:** um engenheiro consegue fazer `GET .../api/bases/{slug}.json` e decidir se roda o pipeline dele.

**Estude:** JSON Schema (https://json-schema.org), versionamento de APIs, cache HTTP em sites estáticos.

---

## Fase 7: Site público

**Objetivo:** qualquer pessoa entende em 10 segundos se uma base é confiável.

**Tarefas**
1. Páginas: início (visão geral do Brasil), base, órgão, ranking, metodologia ("como medimos") e API.
2. O site lê os JSON da API estática.
3. Simples primeiro: HTML, CSS e JavaScript, como o seu portfólio. Hospedagem na Vercel (Hobby).
4. Linguagem clara: explicar cada status em uma frase; separar "não verificável" de "desatualizado".
5. Acessível e bom no celular.
6. Página de metodologia com as regras de status e a fórmula da nota.
7. O workflow diário publica o site atualizado automaticamente.

**Entregável:** site publicado e atualizado todo dia.

**Pronto quando:** você mostra a página de uma base para alguém que não é da área e a pessoa entende o status sem explicação.

**Estude:** sites estáticos que leem JSON, acessibilidade básica (contraste, foco de teclado), deploy na Vercel.

---

## Fase 8: Alertas

**Objetivo:** levar o Clock-in para o dia a dia de quem depende de dados públicos, sem custo.

**Tarefas**
1. **RSS/Atom** por base e por órgão, gerado como arquivo estático no workflow (sem cadastro, sem custo).
2. **Webhook** (Slack, Teams, Discord) para quem quiser receber no chat: avaliar como cadastrar sem servidor (por exemplo, arquivo de configuração no repositório via pull request).
3. **E-mail** por último, só se houver um serviço com cota gratuita que atenda; cuidado com a LGPD (guardar só o necessário).
4. Gatilhos: mudou de status, mudou de schema, link quebrou, voltou a funcionar.
5. Evitar alerta duplicado e falso positivo (usar a regra de 3 falhas).

**Entregável:** RSS funcionando; webhook e e-mail conforme a decisão.

**Pronto quando:** você assina o RSS de uma base e recebe o aviso no mesmo dia em que ela muda de formato.

**Estude:** RSS/Atom, webhooks, LGPD para cadastros simples.

---

## Fase 9: Lançamento e impacto

**Objetivo:** fazer o projeto ser usado e gerar a diferença que motivou tudo.

**Tarefas**
1. Primeiro post no LinkedIn com os números da validação (com as ressalvas).
2. Relatório mensal público: "os dados abertos do Brasil em [mês]".
3. Conversar com quem pode usar ou divulgar: Open Knowledge Brasil, Base dos Dados, redações de jornalismo de dados, a própria CGU.
4. Licença de código aberto e guia de contribuição.
5. Coletar feedback e priorizar: portais estaduais e municipais? biblioteca Python? extensão de navegador?

**Entregável:** post publicado, relatório, licença e guia de contribuição.

**Pronto quando:** pelo menos uma pessoa de fora usa o Clock-in no trabalho dela.
