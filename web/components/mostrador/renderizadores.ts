// Desenho dos pontos do mostrador. Dois caminhos com o mesmo resultado visual:
// - WebGPU: um shader WGSL desenha milhares de pontos de uma vez (instâncias), com brilho do ponteiro;
// - Canvas 2D: reserva para navegadores sem WebGPU, com menos pontos.
// Cada ponto chega como [x, y, estado, fase], com x e y entre -1 e 1 (lib/mostrador.ts).

export type Cor = [number, number, number];

export interface Quadro {
  tempo: number; // segundos desde o início
  varredura: number; // posição do ponteiro, em fração de volta (0 = 12 horas)
  destaque: number; // índice do estado destacado, ou -1
}

export interface Renderizador {
  tipo: "webgpu" | "canvas";
  redimensionar(largura: number, altura: number): void;
  definirCores(cores: Cor[]): void;
  desenhar(quadro: Quadro): void;
  destruir(): void;
}

// Tamanho de cada ponto: preenche a coroa sem encostar demais nos vizinhos
function raioDoPonto(raioMostrador: number, quantidade: number, raioInterno: number) {
  const area = Math.PI * (1 - raioInterno ** 2) * raioMostrador ** 2;
  return Math.max(1.2, Math.sqrt(area / Math.max(quantidade, 1) / Math.PI) * 0.62);
}

// Brilho de um ponto conforme a distância angular atrás do ponteiro (o rastro some aos poucos)
export function brilhoAtras(varredura: number, volta: number) {
  const atras = (((varredura - volta) % 1) + 1) % 1;
  return Math.exp(-atras * 9);
}

const SHADER = /* wgsl */ `
struct Uniformes {
  tamanho: vec2f,
  tempo: f32,
  varredura: f32,
  destaque: f32,
  raioPonto: f32,
  escala: f32,
  folga: f32,
  cores: array<vec4f, 4>,
};
@group(0) @binding(0) var<uniform> u: Uniformes;

struct Saida {
  @builtin(position) posicao: vec4f,
  @location(0) local: vec2f,
  @location(1) cor: vec4f,
};

@vertex
fn vs(@builtin(vertex_index) v: u32, @location(0) ponto: vec4f) -> Saida {
  var cantos = array<vec2f, 6>(vec2f(-1.0, -1.0), vec2f(1.0, -1.0), vec2f(-1.0, 1.0),
                               vec2f(-1.0, 1.0), vec2f(1.0, -1.0), vec2f(1.0, 1.0));
  let canto = cantos[v];
  let estado = u32(ponto.z);
  let fase = ponto.w;
  let volta = fract(atan2(ponto.x, -ponto.y) / 6.2831853 + 1.0);
  // Respiração: cada ponto pulsa um pouco, fora de sincronia com os vizinhos
  let respiro = 1.0 + 0.014 * sin(u.tempo * 1.4 + fase * 6.2831853);
  let atras = fract(u.varredura - volta + 1.0);
  let brilho = exp(-atras * 9.0);
  var tamanho = u.raioPonto * (1.0 + 0.8 * brilho);
  var alfa = 0.5 + 0.5 * brilho;
  if (u.destaque >= 0.0) {
    if (abs(f32(estado) - u.destaque) < 0.5) { alfa = 1.0; tamanho = tamanho * 1.2; } else { alfa = alfa * 0.16; }
  }
  let px = ponto.xy * respiro * u.escala + canto * tamanho;
  var s: Saida;
  s.posicao = vec4f(px.x / (u.tamanho.x * 0.5), -px.y / (u.tamanho.y * 0.5), 0.0, 1.0);
  s.local = canto;
  s.cor = vec4f(u.cores[estado].rgb, alfa);
  return s;
}

@fragment
fn fs(e: Saida) -> @location(0) vec4f {
  // Ponto redondo com borda suave; cor pré-multiplicada pelo alfa
  let a = smoothstep(1.0, 0.6, length(e.local)) * e.cor.a;
  return vec4f(e.cor.rgb * a, a);
}
`;

export async function criarRenderizadorWebGPU(canvas: HTMLCanvasElement, pontos: Float32Array, raioInterno: number): Promise<Renderizador | null> {
  if (typeof navigator === "undefined" || !("gpu" in navigator) || !navigator.gpu) return null;
  try {
    const adaptador = await navigator.gpu.requestAdapter({ powerPreference: "low-power" });
    if (!adaptador) return null;
    const dispositivo = await adaptador.requestDevice();
    const contexto = canvas.getContext("webgpu");
    if (!contexto) return null;
    const formato = navigator.gpu.getPreferredCanvasFormat();
    contexto.configure({ device: dispositivo, format: formato, alphaMode: "premultiplied" });

    // Erros de WebGPU não viram exceção: são conferidos aqui, e qualquer erro manda para o Canvas 2D
    dispositivo.pushErrorScope("validation");
    const modulo = dispositivo.createShaderModule({ code: SHADER });
    const compilacao = await modulo.getCompilationInfo();
    if (compilacao.messages.some((mensagem) => mensagem.type === "error")) {
      await dispositivo.popErrorScope();
      dispositivo.destroy();
      return null;
    }
    const pipeline = dispositivo.createRenderPipeline({
      layout: "auto",
      vertex: {
        module: modulo,
        entryPoint: "vs",
        buffers: [{ arrayStride: 16, stepMode: "instance", attributes: [{ shaderLocation: 0, offset: 0, format: "float32x4" }] }],
      },
      fragment: {
        module: modulo,
        entryPoint: "fs",
        targets: [{
          format: formato,
          blend: {
            color: { srcFactor: "one", dstFactor: "one-minus-src-alpha", operation: "add" },
            alpha: { srcFactor: "one", dstFactor: "one-minus-src-alpha", operation: "add" },
          },
        }],
      },
      primitive: { topology: "triangle-list" },
    });

    const instancias = dispositivo.createBuffer({ size: pontos.byteLength, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST });
    dispositivo.queue.writeBuffer(instancias, 0, pontos);
    // 2 + 6 números e 4 cores (vec4): 24 floats = 96 bytes
    const valores = new Float32Array(24);
    const uniformes = dispositivo.createBuffer({ size: valores.byteLength, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    const grupo = dispositivo.createBindGroup({ layout: pipeline.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: uniformes } }] });
    if (await dispositivo.popErrorScope()) {
      dispositivo.destroy();
      return null;
    }
    const quantidade = pontos.length / 4;
    let largura = 1;
    let altura = 1;
    let perdido = false;
    dispositivo.lost.then(() => { perdido = true; });

    return {
      tipo: "webgpu",
      redimensionar(l, a) {
        largura = l;
        altura = a;
        canvas.width = l;
        canvas.height = a;
      },
      definirCores(cores) {
        cores.forEach((cor, i) => valores.set([cor[0], cor[1], cor[2], 1], 8 + i * 4));
      },
      desenhar({ tempo, varredura, destaque }) {
        if (perdido || largura < 2) return;
        const escala = Math.min(largura, altura) * 0.5 * 0.9;
        valores.set([largura, altura, tempo, varredura, destaque, raioDoPonto(escala, quantidade, raioInterno), escala, 0], 0);
        dispositivo.queue.writeBuffer(uniformes, 0, valores);
        const comandos = dispositivo.createCommandEncoder();
        const passo = comandos.beginRenderPass({
          colorAttachments: [{ view: contexto.getCurrentTexture().createView(), loadOp: "clear", storeOp: "store", clearValue: { r: 0, g: 0, b: 0, a: 0 } }],
        });
        passo.setPipeline(pipeline);
        passo.setBindGroup(0, grupo);
        passo.setVertexBuffer(0, instancias);
        passo.draw(6, quantidade);
        passo.end();
        dispositivo.queue.submit([comandos.finish()]);
      },
      destruir() {
        instancias.destroy();
        uniformes.destroy();
        dispositivo.destroy();
      },
    };
  } catch {
    return null;
  }
}

export function criarRenderizadorCanvas(canvas: HTMLCanvasElement, pontos: Float32Array, raioInterno: number): Renderizador | null {
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  const quantidade = pontos.length / 4;
  // Volta de cada ponto, calculada uma vez
  const voltas = new Float32Array(quantidade);
  for (let i = 0; i < quantidade; i += 1) {
    voltas[i] = (Math.atan2(pontos[i * 4], -pontos[i * 4 + 1]) / (2 * Math.PI) + 1) % 1;
  }
  let largura = 1;
  let altura = 1;
  let cores: string[] = ["#000", "#000", "#000", "#000"];

  return {
    tipo: "canvas",
    redimensionar(l, a) {
      largura = l;
      altura = a;
      canvas.width = l;
      canvas.height = a;
    },
    definirCores(lista) {
      cores = lista.map(([r, g, b]) => `rgb(${Math.round(r * 255)} ${Math.round(g * 255)} ${Math.round(b * 255)})`);
    },
    desenhar({ tempo, varredura, destaque }) {
      ctx.clearRect(0, 0, largura, altura);
      const escala = Math.min(largura, altura) * 0.5 * 0.9;
      const raio = raioDoPonto(escala, quantidade, raioInterno);
      const cx = largura / 2;
      const cy = altura / 2;
      for (let i = 0; i < quantidade; i += 1) {
        const estado = pontos[i * 4 + 2];
        const respiro = 1 + 0.014 * Math.sin(tempo * 1.4 + pontos[i * 4 + 3] * 2 * Math.PI);
        const brilho = brilhoAtras(varredura, voltas[i]);
        let tamanho = raio * (1 + 0.8 * brilho);
        let alfa = 0.5 + 0.5 * brilho;
        if (destaque >= 0) {
          if (estado === destaque) { alfa = 1; tamanho *= 1.2; } else { alfa *= 0.16; }
        }
        ctx.globalAlpha = alfa;
        ctx.fillStyle = cores[estado] ?? "#888";
        ctx.beginPath();
        ctx.arc(cx + pontos[i * 4] * respiro * escala, cy + pontos[i * 4 + 1] * respiro * escala, tamanho * 0.8, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    },
    destruir() {
      ctx.clearRect(0, 0, largura, altura);
    },
  };
}
