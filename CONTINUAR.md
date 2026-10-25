# Como continuar de onde paramos

Este arquivo serve para retomar o trabalho do **Clock-in** em outro computador ou em outro chat do Claude, exatamente do ponto em que parou em 25/10/2026.

O Clock-in é um projeto independente: não tem relação com outros repositórios da conta.

---

## 1. Preparar o computador

O ambiente principal é **Windows** (PowerShell e VS Code). As diferenças para Linux estão logo abaixo da tabela.

| Ferramenta | Para quê | Como conferir (Windows) |
|---|---|---|
| Git | versionamento | `git --version` |
| GitHub CLI | clonar o repositório privado | `gh auth status` (faça `gh auth login` antes) |
| Python 3 com venv | o motor do Clock-in | `python --version` e `python -m venv --help` |
| VS Code | editor | abrir o app |
| Claude Code | continuar com o Claude | `claude --version` |
| Node.js (opcional) | só para rodar de novo os scripts de validação | `node --version` |

**Não é preciso Docker, PostgreSQL nem DBeaver.** O projeto usa DuckDB, que é instalado como pacote Python dentro do ambiente virtual (decisão 7 em `docs/DECISOES.md`), seguindo a regra de custo zero.

Cuidados no Windows:
- Use `python`, não `python3`. No Windows, `python3` costuma ser um atalho da Microsoft Store que não executa nada. Com várias versões instaladas, `py -0p` lista todas e `py -3.12` escolhe uma.
- O ambiente virtual é ativado com `.venv\Scripts\Activate.ps1`. Se o PowerShell bloquear o script, rode uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- Se `gh` não for reconhecido, ele pode estar instalado fora do PATH. Chame pelo caminho completo: `& "$env:LOCALAPPDATA\Programs\GitHubCLI\bin\gh.exe" auth status`.

No Linux (por exemplo, Linux Mint): use `python3` no lugar de `python` e ative o ambiente com `source .venv/bin/activate`. Se o `python3 -m venv` reclamar, instale o pacote: `sudo apt install python3-venv`.

Clonar e configurar a identidade (PowerShell):

```powershell
cd $env:USERPROFILE
gh repo clone Bolapipa/clock-in
cd clock-in
git config user.name "Arthur Delacorte"
git config user.email "delacortearthur@gmail.com"
```

No Linux, o mesmo com `mkdir -p ~/projetos && cd ~/projetos` no lugar da primeira linha.

**Importante:** a identidade é configurada por repositório e **não vem junto com o clone**. Em todo computador novo, rode os dois `git config` acima e confira com `git config user.email`. Os commits do Clock-in são sempre com o e-mail pessoal, nunca com e-mail de trabalho.

---

## 2. Prompt para o novo chat do Claude

Abra o terminal **dentro da pasta `clock-in`**, inicie o Claude Code (`claude`) e cole o texto abaixo inteiro:

```text
Olá! Vou continuar um projeto que comecei em outro computador. Leia este contexto com atenção antes de responder.

QUEM SOU EU E COMO QUERO TRABALHAR
- Sou o Arthur, engenheiro de dados no Rio de Janeiro (Azure Databricks, PySpark, SQL, Delta Lake, arquitetura Medallion).
- Estou aprendendo colocando a mão na massa. EU escrevo o código. Você me ensina: diga exatamente o que fazer, passo a passo, de forma didática e detalhada ("agora crie este arquivo", "rode este comando", "isto serve para..."), mas não faça por mim.
- Só faça algo diretamente (criar arquivo, commit, push) quando eu pedir explicitamente.
- Sempre em português do Brasil.
- Não use emojis nem ícones, nem nas respostas nem nos arquivos.
- Quando eu mandar um print ou um erro, explique o porquê, não só a correção.
- Antes de commit ou push, confira com git status que o arquivo .env não aparece.
- Commits deste projeto são sempre com o e-mail pessoal delacortearthur@gmail.com (conta GitHub Bolapipa). Confira com git config user.email antes do primeiro commit.
- Tenho outros projetos no GitHub, mas eles são separados. Não misture nada deles com o Clock-in.

O PROJETO: CLOCK-IN (github.com/Bolapipa/clock-in, privado)
Monitor de dados abertos do Brasil: verifica todo dia se cada base do dados.gov.br ainda está viva (link funcionando, conteúdo atualizado no prazo, formato estável), medindo pelo conteúdo real e não pelo metadado do portal.
- Validação feita em 24/10/2026: censo de 19.602 bases e prova real em 119 bases. Resultados em docs/VALIDACAO.md.
- Formato: motor de coleta (Bronze/Silver/Gold) -> API estática (JSON) -> site público -> alertas.
- REGRA PRINCIPAL: CUSTO ZERO para mim e para quem usar. Stack: Python + DuckDB + Parquet, motor diário no GitHub Actions (repositório público a partir da Fase 2), API em arquivos JSON estáticos, site estático na Vercel (Hobby), alertas por RSS e webhook. Sem Docker, sem PostgreSQL, sem servidor, sem serviço pago. Antes de sugerir qualquer ferramenta, confirme que ela continua gratuita.
- Nenhum dado gerado vai para o Git: estado atual e histórico ficam em arquivos de release do GitHub (decisão 16).
- Documentação pronta: README.md, docs/IDEIA.md, docs/PESQUISA.md, docs/VALIDACAO.md, docs/API_DADOS_GOV.md, docs/ARQUITETURA.md (modelo de dados e regras), docs/ROADMAP.md, docs/DECISOES.md.
- Decisões 1 a 18 registradas em docs/DECISOES.md. As decisões 12 (acesso ao catálogo) e 15 (limite de download) são provisórias e dependem de medição nas Fases 1 e 2.
- A pasta validacao/ tem scripts de pesquisa usados na validação. Não são código do produto: o motor será escrito do zero.
- Ambiente atual: Windows, PowerShell e VS Code. Usar python (não python3).
- ONDE PAREI: documentação completa, nenhuma linha de código do produto escrita. Pendência conhecida: o .gitignore ignora data/, mas o projeto usa dados/ (corrigir na tarefa 3 da Fase 0). O próximo passo é a FASE 0 (ambiente) do docs/ROADMAP.md.

O QUE QUERO AGORA
Leia o README.md e os arquivos em docs/. Depois verifique se o meu computador tem os requisitos da Fase 0 (git, gh autenticado, python com venv) e me diga o que falta. Em seguida, me guie pela Fase 0 do docs/ROADMAP.md passo a passo, como professor, sem escrever o código por mim.
```

---

## Estado em 25/10/2026

| Item | Situação |
|---|---|
| Ideia | Documentada em docs/IDEIA.md, com a origem do projeto e os canais de entrega |
| Pesquisa de concorrentes | Concluída (docs/PESQUISA.md) |
| Validação | Concluída (docs/VALIDACAO.md) |
| Arquitetura | Documentada em docs/ARQUITETURA.md |
| Decisões | 1 a 18 registradas em docs/DECISOES.md (12 e 15 provisórias) |
| Código do produto | Não iniciado |
| Próximo passo | Fase 0 do docs/ROADMAP.md |
