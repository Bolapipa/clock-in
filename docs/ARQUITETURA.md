# Arquitetura

Referência técnica do Clock-in: o que é coletado, o que é guardado, como os dados se organizam em camadas e como o resultado chega às pessoas. O [ROADMAP.md](ROADMAP.md) diz **quando** construir cada parte; este arquivo diz **o que** cada parte é. As escolhas e seus motivos estão em [DECISOES.md](DECISOES.md).

> Fase 0 concluída (ambiente e primeiro teste com DuckDB); o motor ainda não foi escrito. Nomes de tabelas e colunas abaixo são o desenho inicial: podem ser ajustados durante as fases, e cada ajuste deve ser registrado aqui.

---

## Visão geral

```text
GitHub Actions (cron diário)
  1. Baixa o estado de ontem          <- release "estado-atual" do GitHub
  2. Coleta o catálogo                 -> Bronze (resposta crua)
  3. Testa os links e lê o conteúdo    -> Silver (status HTTP, hash, schema)
  4. Calcula status e nota (DuckDB)    -> Gold (fatos e dimensões)
  5. Gera a API estática (JSON)        -> publicada na Vercel com o site
  6. Gera RSS e dispara webhooks       -> alertas
  7. Sobe o estado de hoje             -> release "estado-atual" e release do mês
```

## O que é baixado e o que é guardado

| O quê | De onde | Guardado? |
|---|---|---|
| Catálogo (lista e detalhe das bases) | API do dados.gov.br | **Sim**, resposta crua na Bronze |
| Base do painel da CGU (2 CSVs, atualizados nos primeiros 15 dias de cada mês) | SharePoint da CGU; os links vêm do catálogo (base `painel-de-monitoramento-de-dados-abertos`) | **Sim**, conteúdo cru na Bronze |
| Arquivos dos órgãos (CSV, XLSX, JSON) | Servidores de cada órgão | **Não**. Baixados para pasta temporária, medidos (hash, schema, data máxima, tamanho) e apagados |

Guardar só as medidas, e não os arquivos, é o que mantém o projeto dentro dos limites gratuitos.

## Onde os dados ficam

Não há servidor de banco de dados. O "banco" são **arquivos Parquet em pastas**, e o **DuckDB** é a biblioteca Python que lê e grava esses arquivos com SQL.

| No Databricks | No Clock-in |
|---|---|
| Spark (motor que processa) | DuckDB |
| Tabela Delta | Pasta de arquivos Parquet |
| Notebook / Lakeflow SQL | Script Python e arquivos `.sql` |
| Job agendado | Workflow do GitHub Actions com `schedule` |
| Unity Catalog | Organização por pastas (`bronze/`, `silver/`, `gold/`) |

Persistência entre execuções (decisão 16): o GitHub Actions começa do zero a cada execução, então o estado precisa ser baixado no início e enviado no fim.

| Onde | O que guarda | Como |
|---|---|---|
| Release `estado-atual` | O mínimo para comparar com ontem: último hash e schema por recurso, contador de falhas por link, Silver `base` e `recurso` do dia | Sobrescrito todo dia (`gh release upload --clobber`) |
| Release `historico-AAAA-MM` | Partições diárias do mês (Silver e Gold) | Um release por mês; até 2 GB por arquivo |
| Repositório Git | Só código e documentação | Nenhum Parquet nem JSON gerado é commitado |
| Pasta local `dados/` | Cópia de trabalho no computador | Fora do Git (`.gitignore`) |

## Estrutura do repositório

```text
clock-in/
├── coletor/        # código do motor (Python)
├── sql/            # transformações (bronze -> silver -> gold)
├── publicar/       # gera os JSON da API estática e o RSS
├── site/           # site estático
├── tests/          # pytest
├── docs/
├── validacao/      # pesquisa já feita (não é código do produto)
└── dados/          # Parquet gerado (fora do Git)
```

---

## Modelo de dados

Particionamento estilo Hive por data de coleta (`data=AAAA-MM-DD/`) em todas as tabelas diárias. Rodar duas vezes no mesmo dia sobrescreve a partição do dia (idempotência).

### Bronze: resposta crua

Regra: guardar exatamente o que veio, antes de qualquer transformação.

| Tabela | Grão | Colunas principais |
|---|---|---|
| `bronze/catalogo_lista` | uma linha por página da listagem | `data_coleta`, `pagina`, `qtd_registros`, `payload` (JSON cru, texto exato da resposta), `coletado_em` (UTC). Gerada por `coletor/catalogo_lista.py` |
| `bronze/catalogo_detalhe` | uma linha por tentativa de buscar o detalhe de uma base | `data_coleta`, `id`, `motivo` (`NOVA`, `ALTERADA`, `RODIZIO`, `COMPLETA`), `ultima_alteracao` (valor de `ultimaAlteracaoMetadados` na listagem do dia), `status_http`, `payload` (JSON cru, só quando 200), `erro`, `coletado_em` (UTC). Gravada em partes de 500 bases (`parte-0001.parquet`...). Gerada por `coletor/catalogo_detalhe.py` (decisão 21) |
| `bronze/painel_cgu_cronograma` | uma linha por base prevista nos Planos de Dados Abertos (cerca de 9.956) | colunas originais como texto (`Orgao`, `nome_base`, `previsao_abertura`, `efetiva_abertura`, `url_base`), `data_coleta`, `last_modified`, `coletado_em`. Gerada por `coletor/painel_cgu.py` |
| `bronze/painel_cgu_monitoramento` | uma linha por órgão (cerca de 256) | colunas originais como texto (`orgao`, `situacao_pda`, `link_pda`, `dt_pub_pda`, `vigencia_ini`, `vigencia_fim`), `data_coleta`, `last_modified`, `coletado_em`. Gerada por `coletor/painel_cgu.py` |

### Silver: padronizado

| Tabela | Grão | Colunas principais |
|---|---|---|
| `silver/base` | uma linha por base por dia | `id` (chave), `slug`, `titulo`, `organizacao_listagem`, `organizacao_detalhe`, `responsavel`, `email_responsavel`, `periodicidade` (valores da API; vazia vira `NAO_DECLARADA`; nula enquanto a base não tem detalhe), `periodicidade_comparavel`, `portal_diz_atualizado`, `status_portal`, `descontinuado`, `selo`, `ultima_atualizacao_dados`, `ultima_alteracao_metadados`, `data_catalogacao`, `qtd_recursos`, `tem_detalhe`, `data_detalhe`, `data_coleta`. Gerada por `sql/silver_base.sql`. A tarefa 5 acrescenta `publicador_real` e `origem_publicador` |
| `silver/recurso` | uma linha por link por dia | `recurso_id` (chave), `id_base`, `titulo`, `link`, `formato` (maiúsculas), `tipo`, `data_ultima_atualizacao_arquivo`, `data_catalogacao`, `data_coleta`. Só bases presentes na listagem do dia. Gerada por `sql/silver_recurso.sql` |
| `silver/tentativa_link` | uma linha por teste de link | `recurso_id`, `data_coleta`, `metodo` (`HEAD` ou `GET`), `status_http`, `url_final`, `content_type`, `tamanho_bytes`, `last_modified`, `etag`, `tempo_ms`, `tipo_erro` (`DNS`, `SSL`, `TIMEOUT`, `CONEXAO`) |
| `silver/versao_conteudo` | uma linha por arquivo medido | `recurso_id`, `data_coleta`, `hash_sha256`, `tamanho_bytes`, `verificacao_parcial`, `encoding`, `separador`, `colunas` (nome, ordem e tipo), `data_max_conteudo` |
| `silver/mudanca_schema` | uma linha por mudança detectada | `recurso_id`, `data_coleta`, `tipo_mudanca` (`ADICIONADA`, `REMOVIDA`, `TIPO_ALTERADO`, `RENOMEADA_PROVAVEL`), `coluna`, `tipo_antes`, `tipo_depois` |

`origem_publicador` diz qual regra da decisão 13 identificou o publicador (`PAINEL_CGU`, `EMAIL`, `DOMINIO_LINK`, `NAO_IDENTIFICADO`).

### Gold: respostas prontas

Modelo dimensional (Star Schema).

| Tabela | Tipo | Grão | Colunas principais |
|---|---|---|---|
| `gold/dim_base` | dimensão | uma linha por base | `slug`, `titulo`, `orgao_id`, `periodicidade`, `url_portal` |
| `gold/dim_orgao` | dimensão | uma linha por publicador real | `orgao_id`, `nome`, `sigla`, `esfera` |
| `gold/dim_data` | dimensão | uma linha por dia | `data`, `ano`, `mes`, `dia_semana` |
| `gold/fato_status_base_diario` | fato | uma linha por base por dia | `data`, `slug`, `status`, `motivo` (frase explicável), `prazo_esperado_dias`, `origem_prazo` (`DECLARADO` ou `INFERIDO`), `ultima_mudanca_real`, `dias_sem_mudanca`, `links_total`, `links_quebrados`, `schema_mudou`, `status_portal`, `diverge_do_portal` |
| `gold/fato_nota_orgao_diario` | fato | uma linha por órgão por dia | `data`, `orgao_id`, `bases_total`, `bases_verificaveis`, `em_dia`, `atrasada`, `parada`, `fora_do_ar`, `nao_verificavel`, `nota`, `cobertura`, `entra_ranking` |
| `gold/fato_evento_base` | fato | uma linha por acontecimento | `data`, `slug`, `tipo_evento` (`STATUS_MUDOU`, `CONTEUDO_MUDOU`, `SCHEMA_MUDOU`, `LINK_QUEBROU`, `LINK_VOLTOU`), `detalhe` |

`fato_evento_base` alimenta a linha do tempo de cada base no site e os alertas.

---

## Regras

### Link quebrado e base fora do ar (decisão 14)

- Um link é **quebrado** depois de **3 falhas em dias seguidos**. Volta a OK no primeiro sucesso.
- Uma base está **fora do ar** quando todos os seus links estão quebrados.
- Teste: `HEAD`; se o servidor responder 403, 405 ou 501, `GET` com `Range: bytes=0-2047`. Timeout de 20 s.

### Conteúdo (decisão 15)

- Arquivo de até **50 MB**: hash SHA-256 do arquivo inteiro.
- Acima de 50 MB: hash dos primeiros 50 MB, `Content-Length` como sinal adicional e `verificacao_parcial = true`.
- O schema é lido das primeiras linhas em qualquer caso.
- O limite é provisório: calibrar com os tamanhos reais medidos na Fase 2.

### Prazo esperado e status (Fase 4)

Prazo esperado:
- **Periodicidade declarada:** prazo com folga. Valores iniciais a calibrar: diária 3 dias, semanal 10, mensal 40, trimestral 100, semestral 200, anual 400.
- **Sem periodicidade:** ritmo inferido pela mediana dos intervalos entre mudanças de hash. Sem histórico suficiente, a base fica "não verificável".

Última mudança real: a data em que o hash mudou ou a data máxima dentro do conteúdo, a que for mais confiável. `Last-Modified` é só pista.

| Status | Regra |
|---|---|
| Em dia | Mudou dentro do prazo esperado |
| Atrasada | Passou do prazo esperado |
| Parada | Passou de 3 vezes o prazo esperado |
| Fora do ar | Todos os links quebrados |
| Não verificável | Só página HTML, sem arquivo, ou histórico insuficiente |

### Nota por órgão (decisão 17)

```text
nota      = 100 x (em_dia + 0,5 x atrasada) / bases_verificaveis
cobertura = 100 x bases_verificaveis / bases_total
```

- "Não verificável" fica fora da nota e aparece na cobertura, lado a lado.
- Só entram no ranking órgãos com pelo menos 10 bases.
- A fórmula é publicada na página de metodologia do site.

---

## API estática

Arquivos JSON gerados a partir da Gold ao fim de cada execução e publicados com o site na Vercel. Cada arquivo traz `"versao": 1` e `"gerado_em"`.

| Arquivo | Conteúdo |
|---|---|
| `api/resumo.json` | Visão geral do Brasil: totais por status e evolução |
| `api/ranking.json` | Órgãos ordenados pela nota, com a cobertura |
| `api/orgaos/{orgao_id}.json` | Nota, cobertura e bases de um órgão |
| `api/bases/{slug}.json` | Status atual, motivo, prazo e linha do tempo de uma base |

O contrato de cada arquivo é documentado em JSON Schema e validado por testes (Fase 6).

## Alertas

| Canal | Como | Custo |
|---|---|---|
| RSS/Atom | Arquivos estáticos por base e por órgão, gerados no workflow | Zero |
| Webhook | Slack, Teams ou Discord; cadastro por arquivo de configuração no repositório, via pull request | Zero |
| E-mail | Fora do escopo por enquanto (decisão 18) | - |

Gatilhos: registros de `fato_evento_base`. A regra das 3 falhas evita alerta falso de link quebrado.
