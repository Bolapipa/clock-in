# API do Clock-in

A API é um conjunto de **arquivos JSON estáticos**, gerados todo dia por `publicar/gerar_api.py` e publicados junto com o site. Não há servidor, chave nem limite de uso: basta um `GET` em cada arquivo. Os dados vêm do [dados.gov.br](https://dados.gov.br) e mostram, por órgão publicador, se os links das bases ainda funcionam.

Esta é a **versão 1** do contrato. Ela ainda é um protótipo: traz a saúde dos links por órgão e por base, e o status por conteúdo (em dia, atrasada, parada) vai aparecendo conforme o histórico de leituras cresce.

## Arquivos

| Arquivo | O que traz |
|---|---|
| `api/resumo.json` | Totais do Brasil |
| `api/orgaos.json` | Um resumo por órgão publicador, dos que têm mais bases para os que têm menos |
| `api/orgaos/{slug}.json` | Um órgão e as bases dele, com as que têm problema primeiro |

O `slug` de um órgão é o nome dele sem acentos, em minúsculas e com hífens (por exemplo, `ibge-fundacao-instituto-brasileiro-de-geografia-e-estatistica`). Ele aparece no `orgaos.json`.

Exemplo, em JavaScript:

```js
const resposta = await fetch("api/resumo.json");
const resumo = await resposta.json();
console.log(resumo.links.percentual_ok, "% dos links respondendo bem");
```

## Cabeçalho de todo arquivo

| Chave | Tipo | Significado |
|---|---|---|
| `versao` | inteiro | Versão do contrato (hoje, `1`) |
| `data_coleta` | texto `AAAA-MM-DD` | Dia dos dados |
| `gerado_em` | texto `AAAA-MM-DDTHH:MM:SSZ` | Momento da geração, em UTC. Os arquivos de uma mesma execução têm o mesmo valor |

## `resumo.json`

| Chave | Tipo | Significado |
|---|---|---|
| `bases` | inteiro | Bases monitoradas |
| `recursos` | inteiro | Arquivos e links cadastrados nas bases |
| `orgaos` | inteiro | Órgãos publicadores |
| `links.total` | inteiro | Links http(s) das bases (um link em duas bases conta duas vezes) |
| `links.testados` | inteiro | Links com algum teste conclusivo |
| `links.ok` | inteiro | Links cujo último teste conclusivo foi bom |
| `links.em_observacao` | inteiro | Links com 1 ou 2 falhas seguidas |
| `links.quebrados` | inteiro | Links com 3 ou mais falhas seguidas, em dias diferentes |
| `links.percentual_ok` | número ou `null` | `ok` sobre `testados`, em %, com 1 casa decimal |
| `links.cobertura` | número ou `null` | `testados` sobre `total`, em % |
| `bases_fora_do_ar` | inteiro | Bases com links e todos eles quebrados |
| `bases_sem_link` | inteiro | Bases sem nenhum link http(s) |
| `status` | objeto | Quantidade de bases por status (veja abaixo) |
| `esferas` | lista | `{ "esfera": ..., "bases": ... }`, da mais comum para a menos comum |
| `periodicidades` | lista | `{ "periodicidade": ..., "bases": ... }`, da mais comum para a menos comum |

## `orgaos.json`

Além do cabeçalho, traz a chave `orgaos`, uma lista de objetos com as chaves abaixo (as mesmas do arquivo de cada órgão, menos `bases`).

| Chave | Tipo | Significado |
|---|---|---|
| `nome` | texto | Nome do órgão publicador. Bases sem órgão identificado ficam em "Não identificado" |
| `slug` | texto | Nome do arquivo em `api/orgaos/` |
| `esfera` | texto | `FEDERAL`, `ESTADUAL`, `MUNICIPAL` ou `NAO_CLASSIFICADA` |
| `qtd_bases` | inteiro | Bases do órgão |
| `links_total`, `links_testados`, `links_ok`, `links_em_observacao`, `links_quebrados` | inteiro | Como em `resumo.json`, para as bases do órgão |
| `bases_fora_do_ar` | inteiro | Bases do órgão fora do ar |
| `percentual_ok` | número ou `null` | `null` quando o órgão tem **menos de 30 links testados**: com poucos links, 1 ou 2 falhas distorcem a porcentagem |
| `cobertura_links` | número ou `null` | `links_testados` sobre `links_total`, em % |
| `status` | objeto | Quantidade de bases do órgão por status |

## `orgaos/{slug}.json`

Traz o cabeçalho, as chaves do órgão acima e a lista `bases`, com um objeto por base:

| Chave | Tipo | Significado |
|---|---|---|
| `id` | texto | Identificador da base no dados.gov.br |
| `slug` | texto | Final do endereço da base: `https://dados.gov.br/dados/conjuntos-dados/{slug}` |
| `titulo` | texto | Título da base |
| `periodicidade` | texto | Veja abaixo |
| `publicador`, `esfera` | texto | Órgão e esfera |
| `links_total`, `links_testados`, `links_ok`, `links_em_observacao`, `links_quebrados` | inteiro | Como acima, para a base |
| `fora_do_ar` | booleano | Tem links e todos estão quebrados |
| `status` | texto | Veja abaixo |
| `motivo` | texto ou `null` | O motivo do status em uma frase, quando o status já foi calculado |

## Valores possíveis

**Status:** `EM_DIA`, `ATRASADA`, `PARADA`, `FORA_DO_AR` e `NAO_VERIFICAVEL`. "Não verificável" não é "desatualizada": quer dizer que ainda não dá para afirmar nada (faltam arquivos lidos ou histórico, ou a base não declara periodicidade).

**Periodicidade:** `DIARIA`, `SEMANAL`, `QUINZENAL`, `MENSAL`, `TRIMESTRAL`, `QUADRIMESTRAL`, `SEMESTRAL`, `ANUAL`, `NAO_DECLARADA`, `SOB_DEMANDA`, `OUTRAS` e `SEM_DETALHE` (o detalhe da base ainda não foi coletado).

## Como os links são contados

- Cada link recebe um teste por dia. Um link só é **quebrado** depois de 3 falhas em dias diferentes seguidos; com 1 ou 2 falhas fica **em observação**.
- Timeout, falha de conexão, servidor não testado e os códigos HTTP 403 e 405 **não contam como falha nem como sucesso**: o link continua como estava e, se nunca foi testado de verdade, não entra em `links_testados`.
- A regra completa e os motivos estão nas [decisões do projeto](DECISOES.md) (14, 29, 31 e 36).

## Versões

`versao` sobe quando uma chave é **removida, renomeada ou muda de significado**. Acrescentar uma chave nova não muda a versão, então um leitor deve ignorar as chaves que não conhece. Os testes em `tests/test_publicar.py` fixam o conjunto de chaves de cada arquivo.
