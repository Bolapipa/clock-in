/// <reference types="@webgpu/types" />

import { useEffect, useRef } from "react";

import { formatarNumero, type ParteDaRegua } from "../lib/dados";

const CORES: Record<ParteDaRegua["chave"], [number, number, number]> = {
  ok: [65, 201, 139],
  observacao: [242, 182, 58],
  quebrados: [255, 112, 88],
  nao_testados: [132, 151, 180],
};

// Grade proporcional aos estados reais; os pontos representam amostras, não links individuais.
export function CampoDeSinais({ partes, aoSelecionar }: { partes: ParteDaRegua[]; aoSelecionar: (chave: ParteDaRegua["chave"]) => void }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fallbackRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const fallbackCanvas = fallbackRef.current;
    if (!canvas || !fallbackCanvas) return;
    const contexto = fallbackCanvas.getContext("2d");
    if (!contexto) return;

    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const shares = partes.map((parte) => parte.percentual / 100);
    const cores = partes.map((parte) => CORES[parte.chave]);
    let gpuDevice: GPUDevice | undefined;
    let gpuContext: GPUCanvasContext | null = null;
    let pipeline: GPURenderPipeline | undefined;
    let bindGroup: GPUBindGroup | undefined;
    let uniformBuffer: GPUBuffer | undefined;
    let animationFrame = 0;
    let disposed = false;
    let width = 0;
    let height = 0;
    let pointerX = -1000;
    let pointerY = -1000;
    const startedAt = performance.now();

    const drawFallback = () => {
      if (!width || !height) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      contexto.setTransform(dpr, 0, 0, dpr, 0, 0);
      contexto.clearRect(0, 0, width, height);
      const gapX = 17 / dpr;
      const gapY = 17 / dpr;
      const raioDeInfluencia = 115 / dpr;
      const cols = Math.max(1, Math.floor(width / gapX));
      const rows = Math.max(1, Math.floor(height / gapY));
      const total = cols * rows;
      const cumulative: number[] = [];
      shares.reduce((sum, share, index) => (cumulative[index] = sum + share, sum + share), 0);

      for (let index = 0; index < total; index += 1) {
        const fraction = (index + 0.5) / total;
        const stateIndex = Math.max(0, cumulative.findIndex((limit) => fraction <= limit));
        const x = (index % cols) * gapX + gapX / 2;
        const y = Math.floor(index / cols) * gapY + gapY / 2;
        const distance = Math.hypot(x - pointerX, y - pointerY);
        const brightness = distance < raioDeInfluencia ? 1 + (1 - distance / raioDeInfluencia) * 1.2 : 0.65;
        const [red, green, blue] = cores[stateIndex] ?? CORES.nao_testados;
        contexto.beginPath();
        contexto.arc(x, y, (distance < raioDeInfluencia ? 3.2 : 2.1) / dpr, 0, Math.PI * 2);
        contexto.fillStyle = `rgba(${Math.min(255, red * brightness)}, ${Math.min(255, green * brightness)}, ${Math.min(255, blue * brightness)}, ${distance < raioDeInfluencia ? 0.98 : 0.7})`;
        contexto.fill();
      }
    };

    const shader = /* wgsl */ `
      struct Uniforms {
        resolution: vec2<f32>,
        pointer: vec2<f32>,
        shares: vec4<f32>,
        time: f32,
        padding: f32,
      };
      @group(0) @binding(0) var<uniform> data: Uniforms;

      @vertex fn vertexMain(@builtin(vertex_index) index: u32) -> @builtin(position) vec4<f32> {
        var positions = array<vec2<f32>, 3>(vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
        return vec4(positions[index], 0.0, 1.0);
      }

      @fragment fn fragmentMain(@builtin(position) position: vec4<f32>) -> @location(0) vec4<f32> {
        let pixel = position.xy;
        let pitch = vec2<f32>(17.0, 17.0);
        let cell = floor(pixel / pitch);
        let center = (cell + vec2<f32>(0.5, 0.5)) * pitch;
        let local = pixel - center;
        let count = max(1.0, floor(data.resolution.x / pitch.x) * floor(data.resolution.y / pitch.y));
        let pointIndex = floor(cell.y * floor(data.resolution.x / pitch.x) + cell.x);
        let fraction = (pointIndex + 0.5) / count;
        let first = data.shares.x;
        let second = first + data.shares.y;
        let third = second + data.shares.z;
        var color = vec3<f32>(0.52, 0.59, 0.70);
        if (fraction <= first) { color = vec3<f32>(0.25, 0.79, 0.54); }
        else if (fraction <= second) { color = vec3<f32>(0.95, 0.71, 0.23); }
        else if (fraction <= third) { color = vec3<f32>(1.0, 0.44, 0.35); }

        let distanceToPointer = distance(center, data.pointer);
        let influence = max(0.0, 1.0 - distanceToPointer / 115.0);
        let pulse = 0.96 + 0.04 * sin(data.time * 1.2 - distanceToPointer * 0.018);
        let radius = mix(2.0, 3.6, influence);
        let dot = 1.0 - smoothstep(radius - 0.7, radius + 0.7, length(local));
        if (dot <= 0.0) { return vec4(0.06, 0.10, 0.17, 1.0); }
        let lit = color * (0.58 + influence * 1.05) * pulse;
        return vec4(lit, 1.0);
      }
    `;

    const render = (time = 0) => {
      if (disposed) return;
      if (gpuDevice && gpuContext && pipeline && uniformBuffer) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const values = new Float32Array([width * dpr, height * dpr, pointerX * dpr, pointerY * dpr, ...shares, time / 1000, 0, 0, 0]);
        gpuDevice.queue.writeBuffer(uniformBuffer, 0, values);
        const encoder = gpuDevice.createCommandEncoder();
        const pass = encoder.beginRenderPass({
          colorAttachments: [{
            view: gpuContext.getCurrentTexture().createView(),
            clearValue: { r: 0.06, g: 0.10, b: 0.17, a: 1 },
            loadOp: "clear",
            storeOp: "store",
          }],
        });
        pass.setPipeline(pipeline);
        if (bindGroup) pass.setBindGroup(0, bindGroup);
        pass.draw(3);
        pass.end();
        gpuDevice.queue.submit([encoder.finish()]);
      } else {
        drawFallback();
      }
      if (gpuDevice && gpuContext && pipeline && !prefersReducedMotion.matches) {
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(render);
      }
    };

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      fallbackCanvas.width = canvas.width;
      fallbackCanvas.height = canvas.height;
      gpuContext?.configure({ device: gpuDevice!, format: navigator.gpu.getPreferredCanvasFormat(), alphaMode: "opaque" });
      render(performance.now() - startedAt);
    };

    const updatePointer = (event: PointerEvent) => {
      const rect = fallbackCanvas.getBoundingClientRect();
      pointerX = event.clientX - rect.left;
      pointerY = event.clientY - rect.top;
      if (!gpuDevice || prefersReducedMotion.matches) render(performance.now() - startedAt);
    };
    const clearPointer = () => {
      pointerX = -1000;
      pointerY = -1000;
      if (!gpuDevice || prefersReducedMotion.matches) render(performance.now() - startedAt);
    };
    const selectAtPointer = (event: MouseEvent) => {
      const rect = fallbackCanvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const cols = Math.max(1, Math.floor((rect.width * dpr) / 17));
      const rows = Math.max(1, Math.floor((rect.height * dpr) / 17));
      const col = Math.min(cols - 1, Math.floor(((event.clientX - rect.left) * dpr) / 17));
      const row = Math.min(rows - 1, Math.floor(((event.clientY - rect.top) * dpr) / 17));
      const fraction = (row * cols + col + 0.5) / (cols * rows);
      let acumulado = 0;
      const indice = shares.findIndex((share) => {
        acumulado += share;
        return share > 0 && fraction <= acumulado;
      });
      const parte = partes[indice];
      if (parte) aoSelecionar(parte.chave);
    };
    const onMotionChange = () => {
      cancelAnimationFrame(animationFrame);
      if (!prefersReducedMotion.matches) render(performance.now() - startedAt);
    };

    fallbackCanvas.addEventListener("pointermove", updatePointer);
    fallbackCanvas.addEventListener("pointerleave", clearPointer);
    fallbackCanvas.addEventListener("click", selectAtPointer);
    prefersReducedMotion.addEventListener("change", onMotionChange);
    const observer = new ResizeObserver(resize);
    observer.observe(fallbackCanvas);

    const startGpu = async () => {
      try {
        if (!navigator.gpu) { render(); return; }
        const adapter = await navigator.gpu.requestAdapter();
        if (!adapter || disposed) { render(); return; }
        gpuDevice = await adapter.requestDevice();
        if (disposed) { gpuDevice.destroy(); return; }
        gpuContext = canvas.getContext("webgpu");
        if (!gpuContext) { gpuDevice.destroy(); gpuDevice = undefined; render(); return; }
        uniformBuffer = gpuDevice.createBuffer({ size: 48, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
        const module = gpuDevice.createShaderModule({ code: shader });
        const compilation = await module.getCompilationInfo();
        if (disposed) return;
        if (compilation.messages.some((message) => message.type === "error")) throw new Error("Falha ao compilar o shader WebGPU.");
        pipeline = gpuDevice.createRenderPipeline({
          layout: "auto",
          vertex: { module, entryPoint: "vertexMain" },
          fragment: { module, entryPoint: "fragmentMain", targets: [{ format: navigator.gpu.getPreferredCanvasFormat() }] },
          primitive: { topology: "triangle-list" },
        });
        bindGroup = gpuDevice.createBindGroup({
          layout: pipeline.getBindGroupLayout(0),
          entries: [{ binding: 0, resource: { buffer: uniformBuffer } }],
        });
        canvas.classList.add("campo-sinais-pronto");
        resize();
      } catch {
        // O canvas 2D mantém a mesma visualização quando o WebGPU não inicializa.
        gpuDevice?.destroy();
        gpuDevice = undefined;
        gpuContext = null;
        render();
      }
    };

    void startGpu();
    resize();
    return () => {
      disposed = true;
      cancelAnimationFrame(animationFrame);
      observer.disconnect();
      fallbackCanvas.removeEventListener("pointermove", updatePointer);
      fallbackCanvas.removeEventListener("pointerleave", clearPointer);
      fallbackCanvas.removeEventListener("click", selectAtPointer);
      prefersReducedMotion.removeEventListener("change", onMotionChange);
      uniformBuffer?.destroy();
      gpuDevice?.destroy();
      gpuContext?.unconfigure();
      canvas.classList.remove("campo-sinais-pronto");
    };
  }, [partes, aoSelecionar]);

  return (
    <figure className="campo-sinais" aria-label="Visualização proporcional dos estados dos links">
      <div className="campo-sinais-cabecalho"><strong>Campo de resposta</strong><span>AMOSTRA · DADOS DE HOJE</span></div>
      <div className="campo-sinais-visual">
        <canvas ref={fallbackRef} className="campo-sinais-canvas campo-sinais-fallback" aria-hidden="true" />
        <canvas ref={canvasRef} className="campo-sinais-canvas campo-sinais-gpu" aria-hidden="true" />
      </div>
      <div className="campo-sinais-legenda" aria-hidden="true">
        {partes.map((parte) => <span key={parte.chave}><i className={`campo-sinais-marca campo-sinais-${parte.chave}`} />{parte.rotulo}</span>)}
      </div>
      <p className="campo-sinais-nota">Amostra proporcional de {formatarNumero(partes.reduce((total, parte) => total + parte.quantidade, 0))} links. Passe o cursor para iluminar; clique num grupo para filtrar os órgãos.</p>
    </figure>
  );
}
