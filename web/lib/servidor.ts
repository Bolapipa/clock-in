// Leitura dos JSON da API na hora do build (só no servidor). A API é gerada pelo pipeline em public/api
// antes do "next build"; sem ela (por exemplo, numa máquina sem dados), as páginas mostram um aviso.
// Só é importado por páginas (componentes de servidor): usa o sistema de arquivos.
import { readFile } from "node:fs/promises";
import path from "node:path";

import type { ListaDeOrgaos, Resumo } from "./dados";

const PASTA_API = path.join(process.cwd(), "public", "api");

async function lerJson<T>(...partes: string[]): Promise<T | null> {
  try {
    return JSON.parse(await readFile(path.join(PASTA_API, ...partes), "utf-8")) as T;
  } catch {
    return null;
  }
}

export const lerResumo = () => lerJson<Resumo>("resumo.json");
export const lerListaDeOrgaos = () => lerJson<ListaDeOrgaos>("orgaos.json");
