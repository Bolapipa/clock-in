# Como a API do dados.gov.br funciona

Notas técnicas descobertas durante a validação (24/10/2026), observando as chamadas que o próprio site faz. **Não é documentação oficial**: confirme antes de depender disso e espere mudanças.

## Acesso

- O site usa endpoints em `https://dados.gov.br/api/publico/...`.
- Chamadas feitas **fora do navegador** (curl, requests) receberam **401**. Dentro de uma página aberta do dados.gov.br, as mesmas chamadas funcionam: o site obtém uma sessão anônima ao carregar.
- Durante a validação, as chamadas foram feitas de dentro de uma página aberta com Playwright (`page.evaluate(fetch(...))`), com pausa de 1,5 s entre elas.
- Alternativa a estudar na Fase 1: a **API oficial** listada em `https://dados.gov.br/dados/api/`, que segundo catálogos de terceiros exige autenticação (cadastro gov.br e uma chave). O nome do cabeçalho e os parâmetros **não foram verificados**: ler a documentação oficial. Se funcionar, é o caminho mais correto e estável.

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
