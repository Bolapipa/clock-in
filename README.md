# Clock-in

**Monitor de dados abertos do Brasil: o dado foi aberto, mas ainda está vivo?**

[![Licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Custo zero](https://img.shields.io/badge/custo-zero-brightgreen.svg)](docs/ROADMAP.md#princípio-custo-zero)

Cada base de dados aberta tem um "horário de trabalho": a periodicidade com que deveria ser atualizada. O Clock-in verifica, todos os dias, se cada base **bateu o ponto**: se o link funciona, se o arquivo existe, se o conteúdo foi atualizado no prazo e se a estrutura mudou. Tudo medido pelo **conteúdo real**, não pelo que o órgão declara.

> **Projeto em construção.** A ideia foi validada com dados reais (veja abaixo). O inventário do catálogo está pronto, o teste diário de links e o motor no GitHub Actions estão em validação, e a leitura do conteúdo dos arquivos está em desenvolvimento. O avanço fase a fase está no [roadmap](docs/ROADMAP.md).

---

## O problema

Quem trabalha com dados do governo (engenheiros de dados, empresas, jornalistas, pesquisadores, ONGs) monta pipelines em cima de bases publicadas no [dados.gov.br](https://dados.gov.br) e nos portais dos órgãos. Essas bases param de ser atualizadas sem aviso, mudam de formato, ficam com links quebrados ou declaram uma periodicidade que não cumprem. Hoje a pessoa só descobre quando o pipeline quebra.

## O que a validação mostrou (24/10/2026)

Censo de **todas as 19.602 bases abertas** do dados.gov.br, mais um teste real de links e datas numa amostra sorteada de 119 bases:

| Achado | Número |
|---|---|
| Bases que o próprio portal **não** marca como atualizadas | 98% |
| Bases **sem nenhuma data** de atualização dos dados | 29% |
| Bases com última atualização há **mais de 1 ano** | 47% |
| Links testados que **falharam** (amostra, 314 links) | 28% |
| Bases com **todos** os links quebrados (amostra) | 13% |
| Bases que **nem declaram** periodicidade (amostra) | 69% |
| Bases marcadas "Atualizado" pelo portal que estavam erradas (amostra) | 6 de 18 |

Detalhes, método e ressalvas em [docs/VALIDACAO.md](docs/VALIDACAO.md).

## O que já existe e a lacuna

O Painel da CGU mede se a base **foi aberta**. O dados.gov.br mostra um selo de atualização que, na prática, quase sempre diz "não verificável". Iniciativas de fora (União Europeia, Pittsburgh, Itália) medem metadados ou são scripts locais. **Ninguém verifica o conteúdo real, avisa quem depende da base e mostra a evolução por órgão.** Análise completa em [docs/PESQUISA.md](docs/PESQUISA.md).

## Como funciona

```text
              Pipeline diário (GitHub Actions, sem servidor)
 ┌────────────────────────────────────────────────────────────────────────┐
 │  Bronze              Silver                  Gold                      │
 │  respostas cruas  ─▶ dados padronizados  ─▶  status por base,          │
 │  do catálogo e       links, hash e schema    nota por órgão            │
 │  do painel da CGU    de cada arquivo         (a construir)             │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     ▼
                      API estática (arquivos JSON)
                          │                  │
                          ▼                  ▼
                   Site público           Alertas
              (base, órgão, ranking)   (RSS e webhook)
```

O que cada camada guarda:

| Camada | Conteúdo | Situação |
|---|---|---|
| **Bronze** | Resposta crua do catálogo (lista e detalhe das bases), arquivos do painel da CGU e cada teste de link | Pronta |
| **Silver** | Bases, recursos, publicador real de cada base, saúde dos links, versões de conteúdo e mudanças de schema | Pronta; conteúdo em desenvolvimento |
| **Gold** | Status diário por base, nota e ranking por órgão | A construir |

O dado fica em arquivos Parquet lidos com DuckDB. Nenhum dado gerado vai para o Git: o estado de cada dia e o histórico ficam em releases do GitHub. O modelo completo está em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

### Status de cada base

| Status | Significado |
|---|---|
| Em dia | O conteúdo mudou dentro do prazo esperado |
| Atrasada | Passou do prazo sem mudança no conteúdo |
| Parada | Muito além do prazo (por exemplo, 3x o esperado) |
| Fora do ar | Nenhum link funciona |
| Não verificável | Não há como saber (só página HTML, sem arquivo) |

O prazo esperado vem da periodicidade declarada **ou**, quando não há (70% das bases, medido no catálogo completo), do ritmo observado no histórico da própria base.

### Regras de justiça

- Um link só é considerado **quebrado** depois de 3 falhas em dias diferentes seguidos, para um erro passageiro não virar acusação.
- Timeout e falha de conexão **não contam como falha**: vários sites do governo não respondem às máquinas do GitHub, e o órgão não pode ser acusado por isso. Só contam resposta de erro do servidor, erro de DNS e erro de certificado.
- "Não verificável" nunca é tratado como "desatualizado": fica fora da nota e aparece como cobertura, lado a lado.
- Coleta educada: uma requisição por vez em cada servidor, pausa entre elas e identificação no `User-Agent`.

## Onde o projeto está

| Fase | Entrega | Situação |
|---|---|---|
| 0 | Ambiente: Python, DuckDB, estrutura do projeto | Concluída |
| 1 | Inventário: catálogo do dados.gov.br e painel da CGU (Bronze e Silver), publicador real de cada base | Concluída |
| 2 | Saúde dos links e pipeline diário no GitHub Actions | Primeira execução completa validada (4h15); agendamento diário ainda desligado |
| 3 | Conteúdo: hash e schema de cada arquivo | Em andamento |
| 4 | Atualização real: prazo esperado e status de cada base | |
| 5 | Modelo Gold: histórico, nota e ranking por órgão | |
| 6 | API estática (JSON gerado pelo motor) | |
| 7 | Site público | |
| 8 | Alertas | |
| 9 | Lançamento e impacto | |

Guia completo, com tarefas e critério de pronto de cada fase: [docs/ROADMAP.md](docs/ROADMAP.md).

### Números do catálogo (coleta de 25/10/2026)

| Item | Quantidade |
|---|---|
| Bases abertas | 19.596 |
| Recursos (links de arquivos) | 126.168 |
| Links distintos, em 714 servidores | 119.267 |
| Bases com publicador real identificado | 96,2% |

## Como rodar

Requisitos: Python 3.12 e Git. No Windows, use `python` (não `python3`).

```powershell
git clone https://github.com/Bolapipa/clock-in.git
cd clock-in
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
```

No Linux: `python3 -m venv .venv` e `source .venv/bin/activate`.

Os testes automáticos não chamam nenhuma API. Para coletar dados de verdade, o coletor precisa da chave da API do dados.gov.br no arquivo `.env` (linha `CHAVE_API_DADOS_GOV=...`, que nunca vai para o Git). A chave fica em "Minha Conta", entrando no portal com gov.br.

Todos os scripts aceitam `--data AAAA-MM-DD`. Sem ela, usam a data de hoje em Brasília, mesmo num computador em outro fuso.

| Comando | O que faz |
|---|---|
| `python coletor/motor.py` | Execução do dia, em ordem e com a mesma data: listagem, painel da CGU, detalhe, Silver, teste de links e Silver dos links |
| `python coletor/motor.py --tempo-maximo 330` | Igual ao anterior, mas o teste de links para a tempo de o motor caber em 330 minutos (o que faltou fica para o dia seguinte) |
| `python coletor/motor.py --desde detalhe` | Retoma o motor a partir de um passo (`lista`, `painel`, `detalhe`, `silver`, `links` ou `silver_links`) |
| `python coletor/motor.py --apenas detalhe` | Roda só um passo. É assim que o workflow chama o motor: uma etapa para cada passo, cada uma com seu log e seu tempo |
| `python coletor/catalogo_lista.py --max-paginas 5` | Teste rápido: coleta 5 páginas da listagem (não sobrescreve a listagem que já existe no dia) |
| `python coletor/catalogo_lista.py` | Coleta a listagem inteira para a Bronze (cerca de 40 minutos); recusa uma listagem com menos de 95% das bases da anterior |
| `python coletor/catalogo_lista.py --aceitar-queda` | Igual ao anterior, mas aceita uma listagem bem menor (use só se a queda for real) |
| `python coletor/catalogo_detalhe.py --max-bases 20` | Teste rápido: detalhe de 20 bases (precisa da listagem do dia) |
| `python coletor/catalogo_detalhe.py --completo` | Carga inicial: detalhe de todas as bases (cerca de 9 horas; pode ser retomada) |
| `python coletor/catalogo_detalhe.py` | Ingestão diária: bases novas, alteradas e o rodízio do dia |
| `python coletor/estado.py --reconstruir` | Recria o estado do detalhe (`dados/estado/`) a partir de toda a Bronze |
| `python coletor/painel_cgu.py` | Baixa os 2 arquivos do painel da CGU para a Bronze (atualizados uma vez por mês) |
| `python coletor/silver.py` | Gera a Silver (`base`, `recurso` e `publicador`) a partir da Bronze do dia |
| `python coletor/links.py --max-links 200` | Teste de links com uma amostra de 200 (precisa da Silver do dia; use `silver.py` antes) |
| `python coletor/links.py` | Testa os links dos recursos: um por vez em cada servidor, vários servidores em paralelo, no máximo 5.000 links por servidor por dia |
| `python coletor/links.py --tempo-maximo 90` | Igual ao anterior, mas para depois de 90 minutos; os links que faltaram são os primeiros do dia seguinte |
| `python coletor/links.py --reconstruir` | Recria o estado dos links a partir de toda a Bronze (use depois de mudar a regra de falha); não testa nenhum link |
| `python coletor/conteudo_baixar.py --max-links 50` | Lê o conteúdo de uma amostra de 50 arquivos (hash e schema) e apaga o que baixou; precisa da Silver e do `link_status` do dia |
| `python coletor/silver_links.py` | Gera a Silver da saúde dos links (`link_status` e `base_saude`) depois do `links.py` |
| `python coletor/nuvem.py baixar` / `subir` / `historico` | Estado e histórico nos releases do GitHub (usados pelo workflow `pipeline-diario.yml`; precisam do `gh` com login) |
| `pytest -v` | Roda os testes automáticos |

## Estrutura do repositório

```text
clock-in/
├── coletor/       # motor de coleta e Silver (Python)
├── sql/           # transformações da Silver (um arquivo por tabela)
├── referencia/    # tabelas de referência mantidas à mão
├── tests/         # testes automáticos (pytest), sem chamar nenhuma API
├── docs/          # ideia, pesquisa, validação, arquitetura, decisões e roadmap
├── validacao/     # pesquisa feita antes do projeto (não é código do produto)
└── .github/       # workflow do pipeline diário
```

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/IDEIA.md](docs/IDEIA.md) | A ideia completa: problema, público, formato da ferramenta, nome |
| [docs/PESQUISA.md](docs/PESQUISA.md) | O que já existe, o que cada um não faz, fontes |
| [docs/VALIDACAO.md](docs/VALIDACAO.md) | Método e resultados da validação |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Modelo de dados (Bronze, Silver, Gold), regras de status, API estática e alertas |
| [docs/API_DADOS_GOV.md](docs/API_DADOS_GOV.md) | Como a API do dados.gov.br funciona: a oficial (usada pelo coletor) e a do site (usada na validação) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Guia fase por fase |
| [docs/DECISOES.md](docs/DECISOES.md) | Registro das decisões técnicas e dos motivos |

## Princípio: custo zero

O Clock-in é gratuito para quem constrói e para quem usa. Toda escolha técnica passa por uma pergunta: "isso continua de graça quando rodar todo dia, para sempre?"

| Peça | Ferramenta |
|---|---|
| Coleta e transformação | Python, DuckDB, SQL |
| Armazenamento | Parquet (Bronze, Silver, Gold) em arquivos de release do GitHub; nenhum dado no Git |
| Pipeline diário | GitHub Actions agendado (repositório público: sem limite de minutos) |
| API | Arquivos JSON estáticos gerados pelo motor |
| Site | HTML, CSS e JavaScript na Vercel (plano Hobby) |
| Alertas | RSS e webhook |

## Licença

Código sob a licença [MIT](LICENSE): pode ser usado, copiado e adaptado livremente, mantendo o aviso de autoria.

---

Feito por **Arthur Delacorte** · [Portfólio](https://arthurdelacorte.vercel.app) · [LinkedIn](https://www.linkedin.com/in/arthur-viana-delacorte)
