// Moldura comum a todas as telas: topo com menu, miolo centralizado, trilha de navegação, rodapé e avisos de carga
import { useEffect, useRef, useState, type ReactNode } from "react";

type ItemDoMenu = "inicio" | "metodologia" | "api";

const MENU: { chave: ItemDoMenu; texto: string; endereco: string }[] = [
  { chave: "inicio", texto: "Início", endereco: "#" },
  { chave: "metodologia", texto: "Metodologia", endereco: "#metodologia" },
  { chave: "api", texto: "API", endereco: "#api" },
];

export function Miolo({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-miolo px-4 sm:px-6 lg:px-10 ${className}`}>{children}</div>;
}

// Ícone de relógio da marca
function Relogio() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" className="text-carimbo">
      <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <path d="M12 6v6l4 2.5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Fecha a página com a mesma escala de tempo usada na leitura dos dados.
function MarcasDoRodape() {
  return (
    <svg aria-hidden="true" viewBox="0 0 600 18" preserveAspectRatio="none" className="rodape-marcas">
      {Array.from({ length: 61 }, (_, minuto) => {
        const principal = minuto % 5 === 0;
        const x = (minuto / 60) * 600;
        return <line key={minuto} x1={x} x2={x} y1="0" y2={principal ? 18 : 8} stroke="currentColor" strokeWidth={principal ? 1.5 : 1} />;
      })}
    </svg>
  );
}

// Topo fixo: continua visível ao rolar, com fundo levemente transparente
export function Topo({ ativo }: { ativo: ItemDoMenu }) {
  const [menuAberto, setMenuAberto] = useState(false);
  const cabecalhoRef = useRef<HTMLElement>(null);
  const botaoMenuRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuAberto) return;
    const fecharNoEscape = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") {
        setMenuAberto(false);
        botaoMenuRef.current?.focus();
      }
    };
    const fecharAoClicarFora = (evento: PointerEvent) => {
      if (evento.target instanceof Node && !cabecalhoRef.current?.contains(evento.target)) setMenuAberto(false);
    };
    const fecharAoMudarPagina = () => setMenuAberto(false);
    document.addEventListener("keydown", fecharNoEscape);
    document.addEventListener("pointerdown", fecharAoClicarFora);
    window.addEventListener("hashchange", fecharAoMudarPagina);
    return () => {
      document.removeEventListener("keydown", fecharNoEscape);
      document.removeEventListener("pointerdown", fecharAoClicarFora);
      window.removeEventListener("hashchange", fecharAoMudarPagina);
    };
  }, [menuAberto]);

  return (
    <header ref={cabecalhoRef} className="topo-site sticky top-0 z-20 border-b border-white/10 bg-[#101b32] text-white">
      <Miolo className="flex min-h-[72px] items-center gap-6 py-3">
        <a href="#" onClick={() => setMenuAberto(false)} className="marca-site flex items-center gap-2.5 whitespace-nowrap text-[1.45rem] font-bold tracking-[-0.06em] text-tinta no-underline"
          aria-label="Clock-in, página inicial">
          <Relogio />
          clock<span className="text-carimbo">-in.</span>
        </a>
        <button ref={botaoMenuRef} type="button" className="botao-menu ml-auto grid size-11 min-h-11 min-w-11 place-items-center rounded-full border border-linha text-tinta md:hidden"
          aria-label={menuAberto ? "Fechar menu" : "Abrir menu"} aria-expanded={menuAberto} aria-controls="menu-principal"
          onClick={() => setMenuAberto((aberto) => !aberto)}>
          <span className={`menu-glyph ${menuAberto ? "menu-glyph-aberto" : ""}`} aria-hidden="true"><i /><i /></span>
        </button>
        <nav id="menu-principal" aria-label="Principal" className={`menu-principal ml-auto hidden gap-2 sm:gap-4 md:flex ${menuAberto ? "menu-aberto" : ""}`}>
          {MENU.map((item) => (
            <a key={item.chave} href={item.endereco} aria-current={item.chave === ativo ? "page" : undefined}
              onClick={() => setMenuAberto(false)}
              className={`menu-link rounded-full px-3 py-2 text-[0.78rem] font-bold uppercase tracking-[0.08em] no-underline transition-colors sm:px-4 ${
                item.chave === ativo ? "bg-carimbo-fundo text-carimbo" : "text-tinta-suave hover:bg-carimbo-fundo hover:text-carimbo"}`}>
              {item.texto}
            </a>
          ))}
        </nav>
      </Miolo>
    </header>
  );
}

export function Rodape() {
  return (
    <footer className="rodape-clock">
      <Miolo className="rodape-conteudo">
        <div className="rodape-colunas">
          <div className="rodape-assinatura">
            <a href="#" className="rodape-marca" aria-label="Clock-in, voltar ao início">
              <span className="rodape-icone"><Relogio /></span>
              <span>clock<span className="rodape-sufixo">-in.</span></span>
            </a>
            <p>Os dados abertos também precisam bater o ponto.</p>
          </div>
          <p className="rodape-descricao">
            Uma leitura diária dos links publicados no <a href="https://dados.gov.br" rel="noopener">dados.gov.br</a>.
          </p>
          <nav className="rodape-links" aria-label="Recursos do Clock-in">
            <a href="#metodologia">Metodologia <span>Como são feitos os testes</span></a>
            <a href="#api">API aberta <span>Consulte os dados coletados</span></a>
            <a href="https://github.com/Bolapipa/clock-in" target="_blank" rel="noopener noreferrer">Código no GitHub <span>Projeto sob licença MIT</span></a>
          </nav>
        </div>
        <MarcasDoRodape />
        <div className="rodape-fechamento">
          <span>Fonte: dados.gov.br</span>
          <span>Coleta diária <i aria-hidden="true">·</i> Código aberto</span>
        </div>
      </Miolo>
    </footer>
  );
}
// Trilha de navegação: "Início / Órgão / Base"
export function Trilha({ passos }: { passos: { texto: string; endereco?: string }[] }) {
  return (
    <nav aria-label="Você está em" className="pt-6 text-[0.92rem]">
      <ol className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 p-0 text-tinta-suave [list-style:none]">
        {passos.map((passo, indice) => (
          <li key={passo.texto} className="flex items-center gap-2">
            {indice > 0 && <span aria-hidden="true">/</span>}
            {passo.endereco
              ? <a href={passo.endereco} className="font-semibold">{passo.texto}</a>
              : <span aria-current="page" className="text-tinta">{passo.texto}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

// Placa cinza pulsando enquanto os dados chegam
export function Carregando({ texto = "Carregando os dados do dia" }: { texto?: string }) {
  return (
    <div role="status" className="py-16">
      <span className="sr-only">{texto}</span>
      <div className="h-12 w-3/4 animate-pulse rounded-md bg-neutro-fundo motion-reduce:animate-none" />
      <div className="mt-4 h-6 w-1/2 animate-pulse rounded-md bg-neutro-fundo motion-reduce:animate-none" />
      <div className="mt-10 h-12 w-full animate-pulse rounded-md bg-neutro-fundo motion-reduce:animate-none" />
    </div>
  );
}

// Aviso de falha: diz o que aconteceu e o que fazer
export function ErroDeCarga({ texto }: { texto: string }) {
  return (
    <p role="alert" className="my-8 border-l-4 border-ruim bg-ruim-fundo px-4 py-3 text-ruim-texto">
      {texto}
    </p>
  );
}
