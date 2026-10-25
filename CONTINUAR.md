# Como continuar de onde paramos

Este arquivo serve para retomar o trabalho em **outro computador** ou em **outro chat do Claude**, exatamente do ponto em que parou em 24/10/2026.

São três partes:
1. O que fazer **antes de sair** do computador atual.
2. Como preparar o **computador novo**.
3. O **prompt** para colar no novo chat do Claude.

---

## 1. Antes de sair do computador atual

- [ ] **fleet-ops-db:** o print da Fase 0 (`docs/img/fase0-compose-healthy.png`) ainda **não foi commitado**. Se não fizer o commit e o push, ele fica só neste computador:
  ```bash
  cd ~/fleet-ops-db
  git add docs/img/fase0-compose-healthy.png
  git commit -m "docs: print do ambiente da fase 0"
  git push
  ```
- [ ] **Ideias locais:** a pasta `~/ideias_projetos/` tem os arquivos `ideia.txt`. O conteúdo já foi para o GitHub (este repositório e o `metricwhy`), então não é preciso copiar.
- [ ] **Senha do banco:** o arquivo `.env` do `fleet-ops-db` não vai para o Git. No computador novo você cria outro a partir do `.env.example` (pode usar outra senha).

---

## 2. Preparar o computador novo

Se for Linux Mint, siga o guia que já existe no `fleet-ops-db`: `docs/SETUP_LINUX_MINT.md`. Resumo do que precisa:

| Ferramenta | Para quê | Como conferir |
|---|---|---|
| Git | versionamento | `git --version` |
| GitHub CLI | clonar repositórios privados, issues | `gh auth status` (faça `gh auth login` antes) |
| Docker e Docker Compose | PostgreSQL | `docker compose version` e `docker run hello-world` |
| Python 3 com venv | o motor do Clock-in | `python3 -m venv --help` |
| Cliente `psql` | conectar no banco | `psql --version` |
| DBeaver | ver o banco visualmente | abrir o app |
| VS Code | editor | abrir o app |
| Claude Code | continuar com o Claude | `claude --version` |
| Node.js (opcional) | só para rodar de novo os scripts de validação | `node --version` |

Clonar os repositórios:

```bash
mkdir -p ~/projetos && cd ~/projetos
gh repo clone Bolapipa/clock-in
gh repo clone Bolapipa/fleet-ops-db
gh repo clone Bolapipa/metricwhy
gh repo clone Bolapipa/Bolapipa.github.io portfolio   # opcional: código do portfólio
```

Configure sua identidade em cada repositório (o seu e-mail pessoal, usado em todos os commits até agora):

```bash
git config user.name "Arthur Delacorte"
git config user.email "delacortearthur@gmail.com"
```

---

## 3. Prompt para o novo chat do Claude

Abra o terminal **dentro da pasta `clock-in`** que você clonou, inicie o Claude Code (`claude`) e cole o texto abaixo inteiro:

```text
Olá! Vou continuar um trabalho que comecei em outro computador. Leia este contexto com atenção antes de responder.

QUEM SOU EU E COMO QUERO TRABALHAR
- Sou o Arthur, engenheiro de dados no Rio de Janeiro (Azure Databricks, PySpark, SQL, Delta Lake, Medallion). Trabalho na OceanPact.
- Estou aprendendo colocando a mão na massa. EU escrevo o código. Você me ensina: diga exatamente o que fazer, passo a passo, de forma didática e detalhada ("agora crie este arquivo", "rode este comando", "isto serve para..."), mas não faça por mim.
- Só faça algo diretamente (criar arquivo, commit, push) quando eu pedir explicitamente.
- Sempre em português do Brasil.
- Não use emojis nem ícones, nem nas respostas nem nos arquivos.
- Quando eu mandar um print ou um erro, explique o porquê, não só a correção.
- Antes de commit ou push, confira com `git status` que o arquivo .env não aparece.

MEUS PROJETOS (todos em github.com/Bolapipa)

1) clock-in (privado) - FOCO ATUAL
   Monitor de dados abertos do Brasil: verifica todo dia se cada base do dados.gov.br ainda está viva (link funcionando, conteúdo atualizado no prazo, formato estável), medindo pelo conteúdo real e não pelo metadado.
   - Validação feita em 24/10/2026: censo de 19.602 bases e prova real em 119 bases. Resultados em docs/VALIDACAO.md.
   - Formato: motor de coleta (Bronze/Silver/Gold) -> API só leitura -> site público -> alertas.
   - Toda a documentação está pronta: README.md, docs/IDEIA.md, docs/PESQUISA.md, docs/VALIDACAO.md, docs/API_DADOS_GOV.md, docs/ROADMAP.md, docs/DECISOES.md.
   - ONDE PAREI: nenhuma linha de código do produto foi escrita. O próximo passo é a FASE 0 (ambiente) do docs/ROADMAP.md.

2) fleet-ops-db (público) - PAUSADO
   Banco OLTP em PostgreSQL de uma frota marítima fictícia, para aprender modelagem, performance, segurança e CDC.
   - Fase 0 concluída: docker-compose.yml com postgres:17, .env/.env.example, healthcheck, conexão pelo psql e pelo DBeaver.
   - Fase 1 (modelagem) não iniciada. Decidi pausar para focar no clock-in e voltar depois.

3) metricwhy (privado) - SÓ IDEIA
   Ferramenta que explica por que um número já publicado mudou (dado atrasado, reprocessamento, duplicidade ou mudança de regra). Documentação no README e em docs/IDEIA.md daquele repositório. Não iniciar agora.

4) Portfólio - CONCLUÍDO
   https://arthurdelacorte.vercel.app (repositório Bolapipa/Bolapipa.github.io, branch main, deploy automático na Vercel).
   O endereço antigo bolapipa.github.io redireciona para a Vercel pela branch gh-pages. Não mexer na branch gh-pages.
   No portfólio, o fleet-ops-db aparece como job "em construção" com data-parcial="1" (fase 1 de 8): atualizar quando eu concluir fases.

O QUE QUERO AGORA
Leia o README.md e os arquivos em docs/ deste repositório (clock-in). Depois verifique se o meu computador tem os requisitos da Fase 0 (git, gh, docker, docker compose, python3 com venv, psql) e me diga o que falta. Em seguida, me guie pela Fase 0 do docs/ROADMAP.md passo a passo, como professor, sem escrever o código por mim.
```

---

## Resumo do estado em 24/10/2026

| Projeto | Estado | Próximo passo |
|---|---|---|
| clock-in | Validado e documentado | Fase 0 do roadmap |
| fleet-ops-db | Fase 0 concluída, pausado | Commitar o print; depois Fase 1 (modelagem) |
| metricwhy | Ideia documentada | Nada por enquanto |
| Portfólio | No ar na Vercel | Atualizar o progresso do fleet-ops-db quando voltar a ele |
