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

## A decidir

| # | Decisão | Opções consideradas | Escolha | Motivo |
|---|---|---|---|---|
| 12 | Acesso ao catálogo | API oficial com chave; API pública do site via navegador | | |
| 13 | Regra do publicador real | `maintainer`; e-mail; domínio dos links; painel da CGU | | |
| 14 | Regra de "fora do ar" | 1 falha; N falhas em dias diferentes | | |
| 15 | Limite de download por arquivo | Arquivo inteiro; primeiros N MB | | |
| 16 | Onde guardar o histórico | Parquet no repositório; arquivos de release; repositório de dados separado | | |
| 17 | Fórmula da nota por órgão | | | |
| 18 | Canal de e-mail dos alertas | Não ter e-mail; serviço com cota gratuita | | |
