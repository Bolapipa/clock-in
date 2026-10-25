import { chromium } from "playwright";
import fs from "node:fs";

// Percorre toda a listagem pública do dados.gov.br, com pausa entre as páginas
const saida = process.argv[2];
const TAM = 100;
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto("https://dados.gov.br/dados/conjuntos-dados", { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});
const campos = ["name", "title", "organizationTitle", "organizationEsfera", "organizationUf", "conjuntoDadosEstaAtualizado",
  "ultimaAtualizacaoDados", "ultimaAtualizacaoMetadados", "dataAtualizacao", "quantidadeRecursos", "quantidadeDownloads",
  "metadataCreated", "resourcesFormatado", "extras"];
const todos = [];
let total = Infinity;
for (let offset = 0; offset < total; offset += TAM) {
  let r = null;
  for (let tentativa = 0; tentativa < 3 && !r; tentativa++) {
    r = await page.evaluate(async (u) => { const x = await fetch(u); return x.ok ? x.json() : null; },
      `/api/publico/conjuntos-dados/buscar?offset=${offset}&tamanhoPagina=${TAM}&dadosAbertos=true`).catch(() => null);
    if (!r) await page.waitForTimeout(5000);
  }
  if (!r) { console.log("falhou offset", offset); continue; }
  total = r.totalRegistros;
  for (const it of r.registros) todos.push(Object.fromEntries(campos.map((c) => [c, it[c]])));
  if (offset % 2000 === 0) console.log("progresso", offset, "/", total);
  await page.waitForTimeout(1500);
}
fs.writeFileSync(saida + "/censo.json", JSON.stringify(todos));
console.log("salvos", todos.length, "de", total);
await browser.close();
