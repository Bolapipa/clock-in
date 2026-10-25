# Como continuar de onde paramos

Este arquivo serve para retomar o trabalho do **Clock-in** em outro computador ou em outro chat do Claude, exatamente do ponto em que parou em 24/10/2026.

O Clock-in é um projeto independente: não tem relação com outros repositórios da conta.

---

## 1. Preparar o computador

| Ferramenta | Para quê | Como conferir |
|---|---|---|
| Git | versionamento | `git --version` |
| GitHub CLI | clonar o repositório privado | `gh auth status` (faça `gh auth login` antes) |
| Docker e Docker Compose | PostgreSQL | `docker compose version` e `docker run hello-world` |
| Python 3 com venv | o motor do Clock-in | `python3 -m venv --help` |
| Cliente `psql` | conectar no banco | `psql --version` |
| DBeaver | ver o banco visualmente | abrir o app |
| VS Code | editor | abrir o app |
| Claude Code | continuar com o Claude | `claude --version` |
| Node.js (opcional) | só para rodar de novo os scripts de validação | `node --version` |

No Linux Mint (base Ubuntu), o Docker deve ser instalado pelo repositório oficial usando o codinome do Ubuntu: https://docs.docker.com/engine/install/ubuntu/. Depois, `sudo usermod -aG docker $USER` e sair e entrar de novo na sessão.

Clonar e configurar a identidade:

```bash
mkdir -p ~/projetos && cd ~/projetos
gh repo clone Bolapipa/clock-in
cd clock-in
git config user.name "Arthur Delacorte"
git config user.email "delacortearthur@gmail.com"
```

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
- Tenho outros projetos no GitHub, mas eles são separados. Não misture nada deles com o Clock-in.

O PROJETO: CLOCK-IN (github.com/Bolapipa/clock-in, privado)
Monitor de dados abertos do Brasil: verifica todo dia se cada base do dados.gov.br ainda está viva (link funcionando, conteúdo atualizado no prazo, formato estável), medindo pelo conteúdo real e não pelo metadado do portal.
- Validação feita em 24/10/2026: censo de 19.602 bases e prova real em 119 bases. Resultados em docs/VALIDACAO.md.
- Formato: motor de coleta (Bronze/Silver/Gold) -> API só leitura -> site público -> alertas.
- Documentação pronta: README.md, docs/IDEIA.md, docs/PESQUISA.md, docs/VALIDACAO.md, docs/API_DADOS_GOV.md, docs/ROADMAP.md, docs/DECISOES.md.
- A pasta validacao/ tem scripts de pesquisa usados na validação. Não são código do produto: o motor será escrito do zero.
- ONDE PAREI: nenhuma linha de código do produto foi escrita. O próximo passo é a FASE 0 (ambiente) do docs/ROADMAP.md.

O QUE QUERO AGORA
Leia o README.md e os arquivos em docs/. Depois verifique se o meu computador tem os requisitos da Fase 0 (git, gh, docker, docker compose, python3 com venv, psql) e me diga o que falta. Em seguida, me guie pela Fase 0 do docs/ROADMAP.md passo a passo, como professor, sem escrever o código por mim.
```

---

## Estado em 24/10/2026

| Item | Situação |
|---|---|
| Ideia | Documentada em docs/IDEIA.md |
| Pesquisa de concorrentes | Concluída (docs/PESQUISA.md) |
| Validação | Concluída (docs/VALIDACAO.md) |
| Código do produto | Não iniciado |
| Próximo passo | Fase 0 do docs/ROADMAP.md |
