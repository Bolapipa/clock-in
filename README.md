# Clock-in

**Monitor de dados abertos do Brasil: o dado foi aberto, mas ainda está vivo?**

Cada base de dados aberta tem um "horário de trabalho": a periodicidade com que deveria ser atualizada. O Clock-in verifica, todos os dias, se cada base **bateu o ponto**: se o link funciona, se o arquivo existe, se o conteúdo foi atualizado no prazo e se o formato mudou. Tudo medido pelo **conteúdo real**, não pelo que o órgão declara.

> Projeto em construção. A ideia foi validada com dados reais (ver abaixo) e a Fase 0 (ambiente) está concluída. O código é escrito fase por fase, seguindo o [roadmap](docs/ROADMAP.md).

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

## Como vai funcionar

```text
           ┌───────────────────────────── Motor de coleta (diário) ─────────────────────────────┐
fontes ──▶ │ Bronze: catálogo + respostas cruas ─▶ Silver: padronizado ─▶ Gold: status por base │
           │ (dados.gov.br, painel CGU)            (links, hash, schema)   (nota por órgão)     │
           └──────────────────────────────────────────────┬─────────────────────────────────────┘
                                                          ▼
                                           API estática (arquivos JSON)
                                                 │           │
                                                 ▼           ▼
                                          Site público    Alertas
                                     (base, órgão, ranking) (e-mail, RSS, webhook)
```

Ordem de construção: **validação → motor → API → site → alertas**. O site usa a própria API, então a lógica de "qual o status desta base" é escrita uma vez só.

### Status de cada base

| Status | Significado |
|---|---|
| Em dia | O conteúdo mudou dentro do prazo esperado |
| Atrasada | Passou do prazo sem mudança no conteúdo |
| Parada | Muito além do prazo (por exemplo, 3x o esperado) |
| Fora do ar | Nenhum link funciona |
| Não verificável | Não há como saber (só página HTML, sem arquivo) |

O prazo esperado vem da periodicidade declarada **ou**, quando não há (69% dos casos), do ritmo observado no histórico da própria base.

## Como rodar

Requisitos: Python 3.12 e Git. No Windows, use `python` (não `python3`).

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python coletor/teste_duckdb.py
```

No Linux: `python3 -m venv .venv` e `source .venv/bin/activate`.

## Roadmap

| Fase | Entrega |
|---|---|
| 0 | Ambiente: Python, DuckDB, estrutura do projeto |
| 1 | Inventário: coletor do catálogo do dados.gov.br (Bronze) |
| 2 | Saúde dos links e motor diário no GitHub Actions |
| 3 | Conteúdo: hash e schema de cada arquivo |
| 4 | Atualização real: prazo esperado e status de cada base |
| 5 | Modelo Gold: histórico, nota e ranking por órgão |
| 6 | API estática (JSON gerado pelo motor) |
| 7 | Site público |
| 8 | Alertas |
| 9 | Lançamento e impacto |

Guia completo, com tarefas, critério de pronto e o que estudar: [docs/ROADMAP.md](docs/ROADMAP.md).

## Documentação

| Arquivo | Conteúdo |
|---|---|
| [docs/IDEIA.md](docs/IDEIA.md) | A ideia completa: problema, público, formato da ferramenta, nome |
| [docs/PESQUISA.md](docs/PESQUISA.md) | O que já existe, o que cada um não faz, fontes |
| [docs/VALIDACAO.md](docs/VALIDACAO.md) | Método e resultados da validação |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Modelo de dados (Bronze, Silver, Gold), regras de status, API estática e alertas |
| [docs/API_DADOS_GOV.md](docs/API_DADOS_GOV.md) | Como a API do dados.gov.br funciona (descoberto na validação) |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Guia fase por fase |
| [docs/DECISOES.md](docs/DECISOES.md) | Registro de decisões técnicas |
| [CONTINUAR.md](CONTINUAR.md) | Como retomar o trabalho em outro computador ou em outro chat |

## Regras do projeto

- **Custo zero:** gratuito para quem constrói e para quem usa. Sem servidor, sem banco hospedado, sem serviço pago. Detalhes no [roadmap](docs/ROADMAP.md#princípio-custo-zero).
- O código do produto é escrito por mim, fase por fase. O roadmap diz **o que** fazer e **onde estudar**.
- Coleta educada: pausas entre requisições, identificação no User-Agent, nada de sobrecarregar servidores públicos.
- Ser justo no ranking: separar "não verificável" de "desatualizado" e publicar a regra.

## Stack prevista (custo zero)

| Peça | Ferramenta |
|---|---|
| Coleta e transformação | Python, DuckDB, SQL |
| Armazenamento | Parquet (Bronze, Silver, Gold) em arquivos de release do GitHub; nenhum dado no Git |
| Motor diário | GitHub Actions agendado (repositório público a partir da Fase 2) |
| API | Arquivos JSON estáticos gerados pelo motor |
| Site | HTML, CSS e JavaScript na Vercel (plano Hobby) |
| Alertas | RSS e webhook |

---

Feito por **Arthur Delacorte** · [Portfólio](https://arthurdelacorte.vercel.app) · [LinkedIn](https://www.linkedin.com/in/arthur-viana-delacorte)
