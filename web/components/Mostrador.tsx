"use client";

// Mostrador da página inicial: um relógio feito de pontos, um para cada amostra dos links, na cor do estado.
// O ponteiro varre o mostrador como quem "bate o ponto". Passar o mouse mostra o estado; clicar filtra os órgãos.
import { useTheme } from "next-themes";
import { useEffect, useMemo, useRef, useState } from "react";

import { criarRenderizadorCanvas, criarRenderizadorWebGPU, type Cor, type Renderizador } from "@/components/mostrador/renderizadores";
import { useLingua } from "@/components/Provedores";
import { formatarNumero, formatarPercentual, type ChaveDaParte, type ParteDaRegua } from "@/lib/dados";
import { ORDEM_DOS_ESTADOS, arcos, distribuirPontos, estadoNoAngulo, posicoes, voltaDoPonto } from "@/lib/mostrador";

const RAIO_INTERNO = 0.58;
const PONTOS_WEBGPU = 9000;
const PONTOS_CANVAS = 2600;
const SEGUNDOS_POR_VOLTA = 9;
const PRAZO_DO_WEBGPU_MS = 2500;
const VARIAVEIS_DE_COR = ["--ok", "--obs", "--queb", "--nt"];

// Lê as cores do tema atual nas variáveis CSS e converte para números entre 0 e 1
function lerCores(): Cor[] {
  const estilo = getComputedStyle(document.documentElement);
  return VARIAVEIS_DE_COR.map((nome) => {
    const hex = estilo.getPropertyValue(nome).trim().replace("#", "");
    const valor = Number.parseInt(hex.length === 3 ? hex.split("").map((c) => c + c).join("") : hex, 16);
    return [((valor >> 16) & 255) / 255, ((valor >> 8) & 255) / 255, (valor & 255) / 255];
  });
}

interface Props {
  partes: ParteDaRegua[];
  percentual: number | null;
  data: string;
  selecionado: ChaveDaParte | null;
  aoSelecionar: (chave: ChaveDaParte | null) => void;
}

export function Mostrador({ partes, percentual, data, selecionado, aoSelecionar }: Props) {
  const { t } = useLingua();
  const { resolvedTheme } = useTheme();
  const caixa = useRef<HTMLDivElement>(null);
  // Dois canvas: um para WebGPU e um de reserva para o Canvas 2D (um canvas que tentou WebGPU não aceita 2D)
  const telaGpu = useRef<HTMLCanvasElement>(null);
  const tela2d = useRef<HTMLCanvasElement>(null);
  const ponteiro = useRef<SVGGElement>(null);
  const renderizador = useRef<Renderizador | null>(null);
  const [tipo, setTipo] = useState<"webgpu" | "canvas" | null>(null);
  const [apontado, setApontado] = useState<{ chave: ChaveDaParte; x: number; y: number } | null>(null);
  const destaque = apontado?.chave ?? selecionado;
  const destaqueRef = useRef(-1);
  destaqueRef.current = destaque ? ORDEM_DOS_ESTADOS.indexOf(destaque) : -1;

  const listaArcos = useMemo(() => arcos(distribuirPontos(partes, 1000, 6)), [partes]);
  const porChave = useMemo(() => Object.fromEntries(partes.map((parte) => [parte.chave, parte])) as Record<ChaveDaParte, ParteDaRegua>, [partes]);

  // Cria o renderizador uma vez (WebGPU se houver; senão Canvas 2D) e anima enquanto o mostrador está na tela
  useEffect(() => {
    const canvasGpu = telaGpu.current;
    const canvas2d = tela2d.current;
    const elemento = caixa.current;
    if (!canvasGpu || !canvas2d || !elemento) return;
    let cancelado = false;
    let quadro = 0;
    let visivel = true;
    const parado = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const inicio = performance.now();

    const redimensionar = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      // Mede a caixa pelo tamanho de layout (o canvas ocupa ela inteira; o de reserva pode estar escondido).
      // offsetWidth ignora a animação de entrada (escala), que deixaria o desenho menor e borrado
      const width = elemento.offsetWidth;
      const height = elemento.offsetHeight;
      renderizador.current?.redimensionar(Math.round(width * dpr), Math.round(height * dpr));
    };

    const desenhar = (agora: number) => {
      const tempo = (agora - inicio) / 1000;
      // Parado (reduzir movimento): o ponteiro fica fixo perto das 12 horas
      const varredura = parado ? 0.12 : (tempo / SEGUNDOS_POR_VOLTA) % 1;
      renderizador.current?.desenhar({ tempo: parado ? 0 : tempo, varredura, destaque: destaqueRef.current });
      ponteiro.current?.setAttribute("transform", `rotate(${(varredura * 360).toFixed(2)})`);
    };

    const laco = (agora: number) => {
      desenhar(agora);
      if (!parado && visivel) quadro = requestAnimationFrame(laco);
    };

    (async () => {
      // O WebGPU tem prazo: um driver ruim pode travar a inicialização em vez de falhar. Passado o prazo,
      // o Canvas 2D assume, e um renderizador WebGPU que ficar pronto tarde demais é descartado
      let expirou = false;
      const tentativa = criarRenderizadorWebGPU(canvasGpu, posicoes(distribuirPontos(partes, PONTOS_WEBGPU), RAIO_INTERNO), RAIO_INTERNO);
      tentativa.then((tardio) => { if (expirou) tardio?.destruir(); });
      let pronto: Renderizador | null = await Promise.race([
        tentativa,
        new Promise<null>((resolve) => window.setTimeout(() => { expirou = true; resolve(null); }, PRAZO_DO_WEBGPU_MS)),
      ]);
      if (pronto) expirou = false;
      if (!pronto) {
        // Sem WebGPU: desenha com Canvas 2D no canvas de reserva, com menos pontos
        pronto = criarRenderizadorCanvas(canvas2d, posicoes(distribuirPontos(partes, PONTOS_CANVAS), RAIO_INTERNO), RAIO_INTERNO);
      }
      if (cancelado || !pronto) { pronto?.destruir(); return; }
      renderizador.current = pronto;
      setTipo(pronto.tipo);
      pronto.definirCores(lerCores());
      redimensionar();
      quadro = requestAnimationFrame(laco);
    })();

    const observadorDeTamanho = new ResizeObserver(() => { redimensionar(); if (parado || !visivel) desenhar(performance.now()); });
    observadorDeTamanho.observe(elemento);
    // Fora da tela, para de desenhar (economiza bateria)
    const observadorDeTela = new IntersectionObserver(([entrada]) => {
      visivel = entrada.isIntersecting;
      cancelAnimationFrame(quadro);
      if (visivel && !parado && renderizador.current) quadro = requestAnimationFrame(laco);
    });
    observadorDeTela.observe(elemento);

    return () => {
      cancelado = true;
      cancelAnimationFrame(quadro);
      observadorDeTamanho.disconnect();
      observadorDeTela.disconnect();
      renderizador.current?.destruir();
      renderizador.current = null;
    };
  }, [partes]);

  // Troca de tema: relê as cores
  useEffect(() => {
    const id = requestAnimationFrame(() => renderizador.current?.definirCores(lerCores()));
    return () => cancelAnimationFrame(id);
  }, [resolvedTheme, tipo]);

  // Ponto apontado: fora da coroa não há estado
  const estadoNoPonteiro = (evento: { clientX: number; clientY: number }) => {
    const caixaAtual = caixa.current?.getBoundingClientRect();
    if (!caixaAtual) return null;
    const raio = Math.min(caixaAtual.width, caixaAtual.height) * 0.5 * 0.9;
    const x = evento.clientX - caixaAtual.left - caixaAtual.width / 2;
    const y = evento.clientY - caixaAtual.top - caixaAtual.height / 2;
    const distancia = Math.hypot(x, y) / raio;
    if (distancia < RAIO_INTERNO - 0.04 || distancia > 1.08) return null;
    const chave = estadoNoAngulo(voltaDoPonto(x, y), listaArcos);
    return chave ? { chave, x: evento.clientX - caixaAtual.left, y: evento.clientY - caixaAtual.top } : null;
  };

  const descricao = t.mostrador.descricao(partes.map((parte) => `${formatarNumero(parte.quantidade)} ${t.estados[parte.chave]}`).join(", "));
  const info = apontado ? porChave[apontado.chave] : null;

  return (
    <div ref={caixa} role="img" aria-label={descricao}
      className="relative aspect-square w-full select-none [touch-action:manipulation]"
      onPointerMove={(evento) => setApontado(estadoNoPonteiro(evento))}
      onPointerLeave={() => setApontado(null)}
      onClick={(evento) => {
        const alvo = estadoNoPonteiro(evento);
        if (alvo) aoSelecionar(selecionado === alvo.chave ? null : alvo.chave);
      }}
      style={{ cursor: apontado ? "pointer" : "default" }}>
      <canvas ref={telaGpu} className={tipo === "canvas" ? "hidden" : "absolute inset-0 size-full"} />
      <canvas ref={tela2d} className={tipo === "canvas" ? "absolute inset-0 size-full" : "hidden"} />

      {/* Marcas do relógio (60 minutos, 12 horas) e o ponteiro */}
      <svg viewBox="-1 -1 2 2" className="pointer-events-none absolute inset-0 size-full text-tinta-3" aria-hidden="true">
        {Array.from({ length: 60 }, (_, minuto) => {
          const hora = minuto % 5 === 0;
          return <line key={minuto} x1="0" y1={hora ? -0.995 : -0.985} x2="0" y2={hora ? -0.935 : -0.955}
            stroke="currentColor" strokeWidth={hora ? 0.012 : 0.006} strokeLinecap="round" transform={`rotate(${minuto * 6})`} opacity={hora ? 0.9 : 0.5} />;
        })}
        <g ref={ponteiro}>
          <line x1="0" y1="-0.47" x2="0" y2="-0.93" stroke="var(--ambar)" strokeWidth="0.012" strokeLinecap="round" />
          <circle cx="0" cy="-0.93" r="0.016" fill="var(--ambar)" />
        </g>
      </svg>

      {/* Centro: a resposta do dia */}
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
        <div className="max-w-[46%]">
          <div className="numeros text-[clamp(2.4rem,7vw,4.6rem)] font-semibold leading-none tracking-[-0.04em] text-tinta">
            {formatarPercentual(percentual)}
          </div>
          <div className="mt-2 text-sm text-tinta-2">{t.mostrador.centro}</div>
          <div className="mt-3 font-mono text-[0.7rem] text-tinta-3">{data}</div>
        </div>
      </div>

      {/* Dica ao apontar um arco */}
      {apontado && info && (
        <div className="pointer-events-none absolute z-10 w-56 -translate-x-1/2 -translate-y-[calc(100%+14px)] rounded-xl border border-linha bg-superficie/95 p-3 text-left shadow-xl backdrop-blur"
          style={{ left: apontado.x, top: apontado.y }}>
          <div className="text-sm font-semibold text-tinta">{t.estados[info.chave]}</div>
          <div className="numeros mt-1 font-mono text-xs text-tinta-2">
            {formatarNumero(info.quantidade)} {t.mostrador.links} · {formatarPercentual(info.percentual)}
          </div>
          <div className="mt-1.5 text-xs leading-snug text-tinta-3">{t.estadosDescricao[info.chave]}</div>
        </div>
      )}

      {tipo && <span className="so-leitor" data-renderizador={tipo} />}
    </div>
  );
}
