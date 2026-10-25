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
- No Windows PowerShell 5.1, o `>` grava arquivos em UTF-16, que o Git trata como binário. Para gerar arquivos versionados, use `| Out-File -Encoding ascii` (ou `utf8`). Exemplo: `pip freeze | Out-File -Encoding ascii requirements.txt`.
- Depois de clonar, crie o ambiente: `python -m venv .venv`, `.venv\Scripts\Activate.ps1`, `pip install -r requirements.txt` e teste com `python coletor/teste_duckdb.py` (deve mostrar 319 e 19283).
- Crie o arquivo `.env` na raiz com a linha `CHAVE_API_DADOS_GOV=sua_chave`. A chave está em dados.gov.br, entrando com gov.br, em "Minha Conta". O `.env` não vai para o Git; confira com `python coletor/teste_api_oficial.py`.

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
- Estou aprendendo colocando a mão na massa. Divisão do trabalho:
  - CÓDIGO: você me manda o código no chat e explica o que cada parte faz, de forma simples e didática. Eu colo, rodo e mando o resultado. Não edite os arquivos de código por mim.
  - DOCUMENTAÇÃO: fica com você. Atualize README, CONTINUAR.md e docs/ diretamente sempre que uma tarefa, fase ou decisão avançar.
- Commit e push são meus; só faça quando eu pedir explicitamente.
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
- Decisões 1 a 21 registradas em docs/DECISOES.md. A 12 foi confirmada (API oficial com chave no cabeçalho chave-api-dados-abertos, chave no .env). A 15 (limite de download) é provisória até a Fase 2. A 21 (frequência da coleta do detalhe) foi decidida: carga inicial completa uma vez (cerca de 9,3 horas, no PC); depois, todo dia, detalhe só das bases novas ou com ultimaAlteracaoMetadados mudado + 1/30 do catálogo em rodízio.
- A pasta validacao/ tem scripts de pesquisa usados na validação. Não são código do produto: o motor será escrito do zero.
- Ambiente atual: Windows, PowerShell e VS Code, Python 3.12 em .venv. Usar python (não python3). No PowerShell 5.1, não gerar arquivos versionados com > (sai em UTF-16): usar | Out-File -Encoding ascii.
- ONDE PAREI: Fase 0 concluída. Fase 1: tarefa 1 concluída (API oficial confirmada); tarefa 2 com a listagem pronta em 25/10/2026 (coletor/catalogo_lista.py grava a Bronze, testes em tests/ com pytest e API simulada). O próximo passo é escrever o coletor do detalhe de cada base, seguindo a decisão 21.

O QUE QUERO AGORA
Leia o README.md e os arquivos em docs/. Confira se o .venv existe e se pytest -v passa. Em seguida, me guie pelo coletor do detalhe (Fase 1, tarefa 2), seguindo a decisão 21, mandando o código explicado parte por parte.
```

---

## Estado em 25/10/2026

| Item | Situação |
|---|---|
| Ideia | Documentada em docs/IDEIA.md, com a origem do projeto e os canais de entrega |
| Pesquisa de concorrentes | Concluída (docs/PESQUISA.md) |
| Validação | Concluída (docs/VALIDACAO.md) |
| Arquitetura | Documentada em docs/ARQUITETURA.md |
| Decisões | 1 a 21 registradas em docs/DECISOES.md (15 provisória) |
| Fase 0 (ambiente) | Concluída: venv, requirements.txt, pastas e primeiro teste com DuckDB |
| Fase 1 (inventário) | Tarefa 1 concluída (API oficial com chave). Tarefa 2: listagem pronta, detalhe pendente |
| Código do produto | coletor/catalogo_lista.py (Bronze da listagem), testes em tests/ (pytest), scripts de teste em coletor/ |
| Próximo passo | Coletor do detalhe de cada base (decisão 21) |
