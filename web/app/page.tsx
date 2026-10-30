// Página inicial: lê a API do dia na hora do build e entrega os dados prontos para a tela
import { PaginaInicial } from "@/components/inicio/PaginaInicial";
import { lerListaDeOrgaos, lerResumo } from "@/lib/servidor";

export default async function Pagina() {
  const [resumo, lista] = await Promise.all([lerResumo(), lerListaDeOrgaos()]);
  return <PaginaInicial resumo={resumo} orgaos={lista?.orgaos ?? []} />;
}
