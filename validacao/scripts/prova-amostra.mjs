import { chromium } from "playwright";
import fs from "node:fs";

// Prova real: para uma amostra de bases, busca o detalhe no portal e testa os links dos arquivos
const [pasta, tamanhoAmostra = "120", semente = "42"] = process.argv.slice(2);
const censo = JSON.parse(fs.readFileSync(`${pasta}/censo.json`, "utf8"));

// Sorteio reprodutível (mesma semente, mesma amostra)
let s = Number(semente);
const aleatorio = () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const embaralhado = censo.map((c) => [aleatorio(), c]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
const amostra = embaralhado.slice(0, Number(tamanhoAmostra));

const UA = "Mozilla/5.0 (validacao de dados abertos; contato: delacortearthur@gmail.com)";

async function testarLink(url) {
  const inicio = Date.now();
  const base = { url };
  for (const metodo of ["HEAD", "GET"]) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 20000);
    try {
      const r = await fetch(url, {
        method: metodo, redirect: "follow", signal: ctrl.signal,
        headers: { "User-Agent": UA, ...(metodo === "GET" ? { Range: "bytes=0-2047" } : {}) },
      });
      clearTimeout(t);
      // Alguns servidores recusam HEAD; nesse caso tenta GET com Range
      if (metodo === "HEAD" && [403, 405, 501].includes(r.status)) continue;
      if (metodo === "GET") await r.body?.cancel().catch(() => {});
      return {
        ...base, metodo, status: r.status, urlFinal: r.url,
        tipo: r.headers.get("content-type"), tamanho: r.headers.get("content-length"),
        lastModified: r.headers.get("last-modified"), ms: Date.now() - inicio,
      };
    } catch (e) {
      clearTimeout(t);
      if (metodo === "GET") return { ...base, metodo, erro: e.name === "AbortError" ? "timeout" : (e.cause?.code || e.message).slice(0, 80) };
    }
  }
  return { ...base, erro: "sem resposta" };
}

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto("https://dados.gov.br/dados/conjuntos-dados", { waitUntil: "networkidle", timeout: 60000 }).catch(() => {});

const resultados = [];
for (const [i, base] of amostra.entries()) {
  const det = await page.evaluate(async (n) => {
    const r = await fetch(`/api/publico/conjuntos-dados/${n}`);
    return r.ok ? r.json() : null;
  }, base.name).catch(() => null);
  await page.waitForTimeout(1500);
  if (!det) { resultados.push({ name: base.name, erroDetalhe: true }); continue; }

  const recursos = (det.resources || []).slice(0, 4);
  const links = [];
  for (const rec of recursos) {
    if (!rec.url) continue;
    links.push({ formato: rec.format, ...(await testarLink(rec.url)) });
  }
  resultados.push({
    name: base.name, titulo: det.title, orgao: det.organization?.title, esfera: base.organizationEsfera,
    periodicidade: det.periodiciade, statusPortal: det.statusAtualizacaoConjuntoDadosFormatado,
    statusPortalCodigo: det.statusAtualizacaoConjuntoDados, inacessivel: det.inacessivel, descontinuado: det.descontinuado,
    ultimaAtualizacaoDados: det.dataUltimaAtualizacaoDadosFormatado, ultimaAtualizacaoRecurso: det.dataUltimaAtualizacaoRecursoFormatada,
    ultimaAtualizacaoMetadados: det.dataUltimaAtualizacaoMetadados, criado: det.metadata_created,
    totalRecursos: det.num_resources, links,
  });
  if ((i + 1) % 20 === 0) console.log("progresso", i + 1, "/", amostra.length);
}
fs.writeFileSync(`${pasta}/prova.json`, JSON.stringify(resultados, null, 1));
console.log("salvos", resultados.length);
await browser.close();
