// Escolhe a tela pela rota (endereço depois do #) e coloca a moldura em volta
import { Rodape, Topo } from "./components/Moldura";
import { PaginaBase, PaginaOrgao } from "./paginas/Detalhes";
import { Inicio } from "./paginas/Inicio";
import { Metodologia, PaginaApi } from "./paginas/Textos";
import { useRota } from "./lib/useRota";

export function App() {
  const rota = useRota();

  // Órgão e base pertencem ao "Início" no menu
  const ativo = rota.tipo === "metodologia" ? "metodologia" : rota.tipo === "api" ? "api" : "inicio";

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-30 focus:rounded focus:bg-superficie focus:px-4 focus:py-2"
        onClick={(evento) => { evento.preventDefault(); document.getElementById("conteudo")?.focus(); }}>
        Pular para o conteúdo
      </a>
      <Topo ativo={ativo} />
      <main id="conteudo" tabIndex={-1} className="pagina-entrada flex-1 outline-none">
        {rota.tipo === "inicio" && <Inicio />}
        {rota.tipo === "metodologia" && <Metodologia />}
        {rota.tipo === "api" && <PaginaApi />}
        {rota.tipo === "orgao" && <PaginaOrgao key={rota.orgao} slug={rota.orgao} />}
        {rota.tipo === "base" && <PaginaBase key={`${rota.orgao}/${rota.base}`} slugDoOrgao={rota.orgao} slugDaBase={rota.base} />}
      </main>
      <Rodape />
    </div>
  );
}
