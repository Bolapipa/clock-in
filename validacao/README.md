# Validação

Pesquisa feita em 24/10/2026 para provar que o problema existe. Resultados e conclusões em [docs/VALIDACAO.md](../docs/VALIDACAO.md).

> Estes scripts são **ferramentas de pesquisa**, escritas durante a validação. Não são o código do produto e não devem ser copiados para o motor: o Clock-in será escrito do zero, seguindo o [roadmap](../docs/ROADMAP.md). Servem de referência para entender a API do portal.

## Arquivos

| Arquivo | O que é |
|---|---|
| `scripts/censo.mjs` | Percorre a listagem do dados.gov.br inteira (100 por página, 1,5 s de pausa) e salva campos selecionados em `censo.json` |
| `scripts/prova-amostra.mjs` | Sorteia N bases do censo (semente fixa), busca o detalhe de cada uma e testa até 4 links por base |
| `resultados/censo-2026-10-24.csv` | Versão compacta do censo: as 19.602 bases abertas em 24/10/2026 (linha de base histórica) |
| `resultados/prova-amostra.json` | Resultado bruto da prova real: 120 bases sorteadas (semente 42), 314 links testados |

## Como rodar de novo (opcional)

Os scripts usam Node.js e Playwright, porque a API do portal só respondeu de dentro de uma página aberta (ver [docs/API_DADOS_GOV.md](../docs/API_DADOS_GOV.md)).

```bash
cd validacao/scripts
npm init -y
npm install playwright@1.49.1
npx playwright install chromium
mkdir -p ../dados
node censo.mjs ../dados                  # gera ../dados/censo.json (cerca de 10 minutos)
node prova-amostra.mjs ../dados 120 42   # gera ../dados/prova.json (cerca de 15 minutos)
```

O `censo.json` completo tem cerca de 240 MB e não fica no repositório (a pasta `validacao/dados/` está no `.gitignore`).
