# Como a API do dados.gov.br funciona

Notas técnicas descobertas durante a validação (24/10/2026), observando as chamadas que o próprio site faz. **Não é documentação oficial**: confirme antes de depender disso e espere mudanças.

## Acesso

- O site usa endpoints em `https://dados.gov.br/api/publico/...`.
- Chamadas feitas **fora do navegador** (curl, requests) receberam **401**. Dentro de uma página aberta do dados.gov.br, as mesmas chamadas funcionam: o site obtém uma sessão anônima ao carregar.
- Durante a validação, as chamadas foram feitas de dentro de uma página aberta com Playwright (`page.evaluate(fetch(...))`), com pausa de 1,5 s entre elas.
- Alternativa preferida (decisão 12): a **API oficial**, descrita na seção abaixo.

## API oficial (lida na especificação em 25/10/2026)

Fonte: especificação OpenAPI 3.1 em `https://dados.gov.br/v3/api-docs` (título "API REST do Portal de Dados Abertos"). Documentação navegável em `https://dados.gov.br/swagger-ui/index.html` e ambiente de testes em `https://hmg.dados.gov.br/swagger-ui/index.html`. Os dados abaixo vêm da especificação; **ainda falta testar uma chamada real com chave** (Fase 1, tarefa 1).

**Autenticação:** cabeçalho `chave-api-dados-abertos` com a chave pessoal. Segundo a especificação, quem entra no portal com perfil de Consumidor obtém a chave em "Minha Conta" (lado direito da página). Organizações usam "Tokens de organização". A chave é segredo: fica no `.env` local e, na Fase 2, num secret do GitHub Actions. Nunca vai para o Git.

| Endpoint | Uso |
|---|---|
| `GET /dados/api/publico/conjuntos-dados?pagina=1&dadosAbertos=true` | Lista paginada. `pagina` é obrigatório. Filtros opcionais: `nomeConjuntoDados`, `idOrganizacao`, `isPrivado` (texto, padrão `"false"`) |
| `GET /dados/api/publico/conjuntos-dados/{id}` | Detalhe de uma base |

Campos da listagem: `id`, `title`, `nome`, `catalogacao`, `nomeOrganizacao`, `ultimaAlteracaoMetadados`, `ultimaAtualizacaoDados`, `isAtualizado`.

Campos úteis do detalhe, comparados com os critérios da decisão 12:

| Critério da decisão 12 | Campo na API oficial |
|---|---|
| `resources` | `recursos[]`: `id`, `link`, `formato`, `tipo` (`DADOS`, `DOCUMENTACAO`, `DICIONARIO_DE_DADOS`, `API`, `OUTRO`), `tamanho`, `dataUltimaAtualizacaoArquivo`, `nomeArquivo` |
| `periodiciade` | `periodicidade`, já padronizada: `DIARIA`, `SEMANAL`, `QUINZENAL`, `MENSAL`, `TRIMESTRAL`, `QUADRIMESTRAL`, `SEMESTRAL`, `ANUAL`, `SOB_DEMANDA`, `OUTRAS`, `INVALIDO` |
| `maintainer` | `responsavel` e `emailResponsavel` |

Outros campos do detalhe: `organizacao`, `atualizado`, `descontinuado`, `dataUltimaAtualizacaoArquivo`, `dataUltimaAtualizacaoMetadados`, `dataCatalogacao`, `selo`, `origemCadastro`.

No papel, a API oficial atende aos três critérios e a periodicidade já vem padronizada.

### Primeiro teste real (25/10/2026, `coletor/teste_api_oficial.py`)

- A chave funciona com `httpx`, sem navegador. Sem chave ou com chave inválida, a resposta é `HTTP 401`.
- A listagem devolve **15 bases por página**, não 100 como a API pública do site. O catálogo inteiro tem cerca de 1.307 páginas.
- Os campos da listagem batem com a especificação.
- No detalhe da primeira base: `recursos` e `responsavel` preenchidos; `periodicidade` veio `null` e o `tipo` do recurso também.

### Teste com as 15 bases da página 1 (25/10/2026)

| Campo | Preenchido |
|---|---|
| `recursos` | 15 de 15 |
| `responsavel` ou `emailResponsavel` | 15 de 15 |
| `periodicidade` | 14 de 15 (`ANUAL` 9, `MENSAL` 3, `OUTRAS` 1, `SOB_DEMANDA` 1, vazia 1) |

- Tempo médio de resposta do detalhe: **0,21 s**. Com 1,5 s de pausa, o catálogo inteiro levaria cerca de **9,3 horas** (ver decisão 21).
- Ressalva: a página 1 não é uma amostra aleatória. 14 das 15 bases têm "(Descontinuado)" no título; o campo `descontinuado` do detalhe deve ser guardado na Silver.
- `OUTRAS` e `SOB_DEMANDA` não dão prazo esperado: contam como "sem periodicidade comparável" na Fase 4.

Conclusão: decisão 12 confirmada. A API oficial com chave substitui a API pública via navegador.

### Formato real do detalhe (20 bases, 25/10/2026)

- `organizacao` vem como texto (o identificador da organização, por exemplo `ebserh-filial-hospital-universitario-onofre-lopes`), não como objeto. Em 6 das 20 bases é o órgão real; em 14 é `controladoria-geral-da-uniao` (bases coletadas por harvest). A cascata da decisão 13 continua necessária, mas este campo pode entrar nela antes do e-mail.
- Datas vêm como texto no formato brasileiro: `dd/mm/aaaa` (`coberturaTemporalInicio`, `dataCatalogacao` dos recursos) ou `dd/mm/aaaa hh:mm:ss` (`dataUltimaAtualizacaoMetadados`, `dataUltimaAtualizacaoArquivo`). A Silver precisa converter. O `ultimaAlteracaoMetadados` da listagem segue o mesmo formato.
- `atualizado` vem como texto (`Atualizado`); `descontinuado` como booleano; `selo` como texto (`Bronze`...).
- `periodicidade` nas 20 bases: `ANUAL` 7, `TRIMESTRAL` 3, `OUTRAS` 3, `SEMESTRAL` 2, `SOB_DEMANDA` 1, nula 4.
- Na carga completa (19.596 bases), o detalhe falhou para 551 (2,8%) com `HTTP 400` e `{"Erro na API":"Erro ao executar a consulta"}`. São bases atribuídas à CGU com nome numérico, aparentemente importadas de outro catálogo.
- Recursos: 111 nas 20 bases. O campo `tamanho` veio `0` mesmo com arquivo, então não serve como tamanho real; o tamanho será medido na Fase 2.

## Endpoints observados

| Endpoint | Uso |
|---|---|
| `GET /api/publico/conjuntos-dados/buscar?offset=0&tamanhoPagina=100&dadosAbertos=true` | Lista paginada. Retorna `{ registros: [...], totalRegistros: 19602 }` |
| `GET /api/publico/conjuntos-dados/{slug}` | Detalhe de uma base, com recursos (arquivos e links) |
| `GET /api/publico/conjuntos-dados/periodicidades.select` | Valores possíveis de periodicidade |
| `GET /api/publico/conjuntos-dados/organizacoes.select` | Lista de organizações |
| `GET /api/publico/conjuntos-dados/formatos.select` | Formatos |

O `slug` é o final da URL da página da base, por exemplo `https://dados.gov.br/dados/conjuntos-dados/aeronaves-registradas-no-registro-aeronautico-brasileiro-rab1`.

## Campos úteis

### Na listagem (`buscar`)

| Campo | Observação |
|---|---|
| `name` | slug da base |
| `title` | título |
| `organizationTitle` | **cuidado:** atribui 95% das bases à CGU (órgão que fez a coleta, não o publicador) |
| `conjuntoDadosEstaAtualizado` | veredito do portal (`true`/`false`) |
| `ultimaAtualizacaoDados` | data ISO; ausente em 29% das bases |
| `ultimaAtualizacaoMetadados` | data ISO |
| `quantidadeRecursos`, `quantidadeDownloads` | contagens |
| `extras` | objeto com `harvest_source_id`, datas, etc. |

### No detalhe (`/conjuntos-dados/{slug}`)

| Campo | Observação |
|---|---|
| `resources[]` | lista de recursos: `url`, `format`, `id` (é aqui que estão os links a testar) |
| `periodiciade` | periodicidade declarada (sim, com essa grafia). Valores com caixa variada: `ANUAL`, `Anual`, `-`, `SOB_DEMANDA`... normalizar |
| `statusAtualizacaoConjuntoDados` | `ATUALIZADO`, `DESATUALIZADO` ou `INDISPONIVEL` |
| `statusAtualizacaoConjuntoDadosFormatado` | texto mostrado no site ("Atualização não verificável") |
| `dataUltimaAtualizacaoDadosFormatado`, `dataUltimaAtualizacaoRecursoFormatada` | datas como texto, às vezes "Indisponível" |
| `inacessivel`, `descontinuado` | flags do portal |
| `organization` | objeto com `name` e `title` |
| `maintainer`, `maintainer_email` | responsável técnico: **pista para o publicador real** |
| `metadata_created`, `metadata_modified` | datas como texto `dd/mm/aaaa hh:mm:ss` |

## Boas práticas de coleta

- Pausa entre chamadas (1 a 2 s no portal; por servidor de órgão, uma requisição por vez).
- `User-Agent` identificando o projeto e um contato.
- Repetir com espera em caso de falha; não insistir em loop.
- Para testar links: `HEAD` primeiro; se o servidor responder 403/405/501, usar `GET` com `Range: bytes=0-2047`.
- Não baixar arquivos grandes inteiros sem necessidade.
- Guardar a resposta crua na Bronze antes de transformar.
