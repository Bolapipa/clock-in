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
| 6 | Repositório | Público; privado | Privado durante o desenvolvimento inicial | Abrir quando houver algo para mostrar (Fase 9) |

## A decidir

| # | Decisão | Opções consideradas | Escolha | Motivo |
|---|---|---|---|---|
| 7 | Acesso ao catálogo | API oficial com chave; API pública do site via navegador | | |
| 8 | Regra do publicador real | `maintainer`; e-mail; domínio dos links; painel da CGU | | |
| 9 | Regra de "fora do ar" | 1 falha; N falhas em dias diferentes | | |
| 10 | Limite de download por arquivo | Arquivo inteiro; primeiros N MB | | |
| 11 | Agendamento | Cron local; GitHub Actions; Airflow | | |
| 12 | Armazenamento | PostgreSQL; DuckDB/Parquet; ambos | | |
| 13 | Framework da API | FastAPI; outro | | |
| 14 | Fórmula da nota por órgão | | | |
