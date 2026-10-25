# Decisões do projeto

Registre aqui cada decisão importante: **o que** decidiu, **as opções** e **o porquê**. Isso vira material para entrevistas e evita rediscutir o que já foi decidido.

## Já decididas

| # | Decisão | Opções consideradas | Escolha | Motivo |
|---|---|---|---|---|
| 1 | Nome | Monitor de Dados Abertos, Dado Vivo, Clock-in Dados, Lock-in, Clock-in | Clock-in | Metáfora de "bater o ponto"; nenhum projeto de dados usa o nome. "Lock-in" descartado por ter sentido negativo em tecnologia (vendor lock-in) |
| 2 | Formato da ferramenta | App, extensão, biblioteca, site | Motor + API + site + alertas | Site e API geram impacto público; alertas levam ao dia a dia; app e extensão ficam para depois |
| 3 | Ordem de construção | Motor → site → API; motor → API → site | Validação → motor → API → site → alertas | O site usa a própria API: a lógica de status é escrita uma vez |
| 4 | Medida de atualização | Metadado do portal; `Last-Modified`; conteúdo | Conteúdo (hash, schema, datas internas), com metadado como pista | Validação mostrou selo do portal errado em 6 de 18 casos |
| 5 | Prazo esperado | Só periodicidade declarada; inferido | Declarada quando existe; inferida pelo histórico quando não | 69% das bases não declaram periodicidade |
| 6 | Custo | Serviços pagos; custo zero | **Custo zero** para quem constrói e para quem usa | Projeto de interesse público e pessoal; precisa durar sem orçamento |
| 7 | Armazenamento | PostgreSQL no Docker; DuckDB + Parquet | DuckDB + Parquet | Pipeline em lote diário; nada para hospedar; cabe no GitHub; mesmo mundo do Databricks. Docker e DBeaver deixam de ser necessários |
| 8 | Motor diário | Cron no PC; GitHub Actions; Airflow | GitHub Actions agendado | Grátis e sem limite de minutos em repositório público; roda sem o PC ligado |
| 9 | API | Servidor (FastAPI) com banco; API estática (JSON) | API estática gerada pelo motor | Sem servidor e sem custo. Perde consultas livres, mas entrega respostas prontas por base, órgão e resumo |
| 10 | Site | Vercel; GitHub Pages | Vercel (Hobby) | Grátis para uso não comercial; já usado no portfólio |
| 11 | Visibilidade do repositório | Sempre privado; público desde já; público quando o motor rodar | Privado até a Fase 1; **público a partir da Fase 2** | Em repositório privado a cota grátis do Actions acaba rápido; código aberto combina com transparência |
| 12 | Acesso ao catálogo | API oficial com chave; API pública do site via navegador | **Provisória:** API oficial com chave, se um teste de um dia mostrar que ela traz `resources`, `periodiciade` e `maintainer`; senão, API pública via Playwright | API oficial é mais estável, roda com `httpx` sem navegador e a chave fica como secret do GitHub Actions. A API pública não é documentada e deu 401 fora do navegador |
| 13 | Regra do publicador real | `maintainer`; e-mail; domínio dos links; painel da CGU | Cascata, na ordem: órgão no painel da CGU; domínio do `maintainer_email`; domínio dos links; senão "não identificado". Coluna `origem_publicador` guarda a regra usada | O campo do portal atribui 95% das bases à CGU. A cascata usa a fonte mais oficial primeiro e a coluna de origem dá rastreabilidade ao ranking |
| 14 | Regra de "fora do ar" | 1 falha; N falhas em dias diferentes | Link quebrado após **3 falhas em dias seguidos**; volta a OK no primeiro sucesso. Base fora do ar quando todos os links estão quebrados | 502, 503 e 520 somaram 18% dos links na validação e costumam ser temporários. Uma falha só geraria falso positivo no ranking e nos alertas |
| 15 | Limite de download por arquivo | Arquivo inteiro; primeiros N MB | **Provisória:** arquivo inteiro até 50 MB; acima disso, hash dos primeiros 50 MB, `Content-Length` como sinal e `verificacao_parcial = true` | Disco e tempo do runner do Actions são limitados. Calibrar o limite com os tamanhos reais medidos na Fase 2 |
| 16 | Onde guardar o histórico | Parquet no repositório; arquivos de release; repositório de dados separado | Nenhum dado no Git. Release `estado-atual` sobrescrito todo dia; release `historico-AAAA-MM` por mês; JSON da API publicado direto na Vercel | Commitar arquivos gerados todo dia faz o histórico do Git crescer para sempre. Releases são gratuitos e aceitam até 2 GB por arquivo |
| 17 | Fórmula da nota por órgão | % de bases em dia; nota com pesos (Toronto, MQA) | `nota = 100 x (em_dia + 0,5 x atrasada) / bases_verificaveis`, com `cobertura` (% verificável) publicada ao lado. Só entram no ranking órgãos com pelo menos 10 bases | Simples de explicar e publicar. Não pune o órgão por limite da medição, e a cobertura baixa fica visível, então esconder dados não vira vantagem |
| 18 | Canal de e-mail dos alertas | Não ter e-mail; serviço com cota gratuita | Sem e-mail por enquanto: RSS e webhook. Reavaliar na Fase 9 se houver demanda | E-mail exige serviço externo, cadastro e cuidados de LGPD. RSS e webhook atendem o público principal com custo zero |
| 19 | Python e bibliotecas base | Python 3.12 ou 3.13; `httpx` ou `requests`; fixar só as principais ou todas | Python 3.12, `httpx` e `requirements.txt` gerado por `pip freeze` (todas as versões fixadas, inclusive dependências) | 3.12 é o `python` padrão da máquina; usar a mesma versão no GitHub Actions. `httpx` tem modo assíncrono, necessário na Fase 2. Fixar tudo garante instalação idêntica em qualquer computador |
| 20 | Atalhos de comandos | `Makefile`; script `tarefas.ps1`; comandos no README | Comandos na seção "Como rodar" do README por enquanto. Reavaliar a partir da Fase 1, quando houver mais comandos | Windows não tem `make`; com um só script, um arquivo de atalhos não compensa |

Decisões marcadas como **provisórias** dependem de uma medição; confirme ou ajuste ao chegar na fase correspondente.

Modelo de dados e regras detalhadas em [ARQUITETURA.md](ARQUITETURA.md).

## A decidir

Nenhuma no momento. Novas decisões entram aqui com o mesmo formato:

| # | Decisão | Opções consideradas | Escolha | Motivo |
|---|---|---|---|---|
