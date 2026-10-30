// Geometria do mostrador da página inicial: um relógio feito de pontos, em que cada ponto é uma amostra
// dos links e cada estado ocupa um arco proporcional à sua parte (começando às 12 horas, no sentido horário).
// Tudo aqui é puro: a tela (WebGPU ou Canvas) só desenha o que estas funções calculam.

import type { ChaveDaParte, ParteDaRegua } from "./dados";

export const ORDEM_DOS_ESTADOS: ChaveDaParte[] = ["ok", "observacao", "quebrados", "nao_testados"];

// Quantos pontos cada estado recebe, somando exatamente 'total' (maiores restos). Um estado que existe
// recebe pelo menos 'minimo' pontos, para nunca sumir do mostrador por ser pequeno
export function distribuirPontos(partes: ParteDaRegua[], total: number, minimo = 8): Record<ChaveDaParte, number> {
  const soma = partes.reduce((acc, parte) => acc + parte.quantidade, 0);
  const resultado = { ok: 0, observacao: 0, quebrados: 0, nao_testados: 0 } as Record<ChaveDaParte, number>;
  if (soma === 0 || total <= 0) return resultado;

  const existentes = partes.filter((parte) => parte.quantidade > 0);
  const reservado = Math.min(total, existentes.length * minimo);
  const livre = total - reservado;
  const brutos = existentes.map((parte) => ({ chave: parte.chave, valor: (parte.quantidade / soma) * livre }));
  for (const item of brutos) resultado[item.chave] = Math.floor(item.valor) + Math.floor(reservado / existentes.length);

  // Distribui o que sobrou do arredondamento para os maiores restos
  let faltam = total - Object.values(resultado).reduce((a, b) => a + b, 0);
  const restos = [...brutos].sort((a, b) => (b.valor % 1) - (a.valor % 1));
  for (let i = 0; faltam > 0 && restos.length; i = (i + 1) % restos.length, faltam -= 1) resultado[restos[i].chave] += 1;
  return resultado;
}

// Arco de cada estado, em frações de volta (0 = 12 horas, sentido horário)
export interface Arco {
  chave: ChaveDaParte;
  inicio: number;
  fim: number;
}

export function arcos(contagens: Record<ChaveDaParte, number>): Arco[] {
  const total = ORDEM_DOS_ESTADOS.reduce((acc, chave) => acc + contagens[chave], 0);
  if (total === 0) return [];
  let inicio = 0;
  return ORDEM_DOS_ESTADOS.filter((chave) => contagens[chave] > 0).map((chave) => {
    const fim = inicio + contagens[chave] / total;
    const arco = { chave, inicio, fim };
    inicio = fim;
    return arco;
  });
}

// Qual estado está no ângulo apontado (fração de volta, 0 = 12 horas)
export function estadoNoAngulo(volta: number, lista: Arco[]): ChaveDaParte | null {
  const v = ((volta % 1) + 1) % 1;
  return lista.find((arco) => v >= arco.inicio && v < arco.fim)?.chave ?? lista.at(-1)?.chave ?? null;
}

// Converte um ponto da tela (relativo ao centro) em fração de volta a partir das 12 horas, no sentido horário
export function voltaDoPonto(x: number, y: number): number {
  const angulo = Math.atan2(x, -y);
  return (angulo / (2 * Math.PI) + 1) % 1;
}

// Gerador pseudoaleatório com semente: o mostrador sai igual em todo carregamento
function aleatorio(semente: number) {
  let s = semente >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Posições dos pontos: [x, y, estado, fase] por ponto, com x e y entre -1 e 1 (centro em 0, 0).
// Os pontos ficam numa coroa (entre raioInterno e 1) e se espalham dentro do arco do seu estado
export function posicoes(contagens: Record<ChaveDaParte, number>, raioInterno = 0.56, semente = 7): Float32Array {
  const lista = arcos(contagens);
  const total = lista.reduce((acc, arco) => acc + contagens[arco.chave], 0);
  const dados = new Float32Array(total * 4);
  const sorteio = aleatorio(semente);
  let i = 0;
  for (const arco of lista) {
    const n = contagens[arco.chave];
    const indice = ORDEM_DOS_ESTADOS.indexOf(arco.chave);
    for (let k = 0; k < n; k += 1) {
      // Espaço entre arcos: um pequeno respiro nas bordas de cada estado
      const margem = Math.min(0.004, (arco.fim - arco.inicio) * 0.15);
      const volta = arco.inicio + margem + sorteio() * (arco.fim - arco.inicio - 2 * margem);
      // Raiz quadrada: pontos distribuídos por área, sem acumular no anel interno
      const raio = Math.sqrt(raioInterno ** 2 + sorteio() * (1 - raioInterno ** 2));
      const angulo = volta * 2 * Math.PI;
      dados[i * 4] = Math.sin(angulo) * raio;
      dados[i * 4 + 1] = -Math.cos(angulo) * raio;
      dados[i * 4 + 2] = indice;
      dados[i * 4 + 3] = sorteio();
      i += 1;
    }
  }
  return dados;
}
